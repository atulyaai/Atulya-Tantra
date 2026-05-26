#!/usr/bin/env python3
"""controller.py — Local NP-DNA training controller.

Manages the full cycle:
  1. Optionally chunk large datasets (or use existing chunks)
  2. Upload one chunk + current checkpoint to Drive
  3. Guide user to open Colab notebook with colab-ssh
  4. SSH in → run colab_worker.py on current chunk
  5. Monitor training via Drive polling
  6. Download checkpoint + merge into base
  7. Repeat for next chunk

Usage:
    python training_collab/controller.py                    # interactive mode
    python training_collab/controller.py --auto             # automated (needs SSH info)
    python training_collab/controller.py --list-chunks      # show available chunks
    python training_collab/controller.py --next-chunk       # show next unprocessed chunk
    python training_collab/controller.py --deploy-chunks    # upload chunks to Drive
    python training_collab/controller.py --run-chunk conversation_chunk_001.jsonl --ssh "ssh root@host -p 22"
"""
import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

from rclone_utils import find_rclone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

# ── Paths ────────────────────────────────────────────────────────────────────
PROJECT = Path(__file__).resolve().parents[1]
CHUNKS_DIR = PROJECT / "data" / "chunks"
INDEX_FILE = CHUNKS_DIR / "data_chunks.json"
LOCAL_CHECKPOINT = PROJECT / "tantra" / "outputs" / "npdna"
LOCAL_SYNC_DIR = PROJECT / "colab_sync" / "workers"
COLAB_DIR = PROJECT / "training_collab"
RCLONE_REMOTE = os.environ.get("ATULYA_RCLONE_REMOTE", "gdrive").rstrip(":")
DRIVE_ROOT = os.environ.get("ATULYA_DRIVE_ROOT", "npdna_training").strip("/")
DRIVE = f"{RCLONE_REMOTE}:{DRIVE_ROOT}"
DRIVE_CHUNKS = f"{DRIVE}/chunks"
DRIVE_CHECKPOINT = f"{DRIVE}/base_checkpoint"
DRIVE_WORKERS = f"{DRIVE}/workers"
DRIVE_COMMANDS = f"{DRIVE}/commands"

# Track processed chunks
STATE_FILE = COLAB_DIR / ".controller_state.json"


def rclone(*args, check=True, **kw):
    """Run rclone command, return CompletedProcess."""
    cmd = [find_rclone() or "rclone"] + [str(a) for a in args]
    print(f"  rclone {' '.join(str(a) for a in args)}")
    return subprocess.run(cmd, capture_output=True, text=True, check=check, **kw)


# ── Chunk management ────────────────────────────────────────────────────────

def load_chunk_index() -> list[dict]:
    """Return list of chunk metadata from index file."""
    if not INDEX_FILE.exists():
        print(f"❌ No chunk index at {INDEX_FILE}")
        print("   Run: python training_collab/chunk_data.py")
        sys.exit(1)
    with open(INDEX_FILE) as f:
        data = json.load(f)
    return data.get("chunks", [])


def load_state() -> dict:
    """Load controller state (processed chunks)."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"processed_chunks": [], "current_chunk": None, "total_chunks": 0}


def save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def deploy_chunks():
    """Upload all chunks to Drive chunk directory."""
    print("📤 Deploying chunks to Drive...")
    os.makedirs(CHUNKS_DIR, exist_ok=True)

    # Upload chunks directory
    result = rclone("copy", str(CHUNKS_DIR), DRIVE_CHUNKS, "--progress")
    print(f"   Exit code: {result.returncode}")

    # Also upload colab_worker.py to Drive root
    rclone("copy", str(COLAB_DIR / "colab_worker.py"), DRIVE, "--progress")
    print("✅ Chunks + colab_worker.py deployed to Drive")


def deploy_checkpoint():
    """Upload current base checkpoint to Drive."""
    print("📤 Deploying checkpoint to Drive...")
    if not LOCAL_CHECKPOINT.exists():
        print(f"⚠️  No checkpoint at {LOCAL_CHECKPOINT}")
        return False
    rclone(
        "copy",
        str(LOCAL_CHECKPOINT),
        DRIVE_CHECKPOINT,
        "--exclude",
        "*.log",
        "--exclude",
        "live_metrics.jsonl",
        "--exclude",
        "backups/**",
        "--exclude",
        "versions/**",
        "--exclude",
        "checkpoints/**",
        "--progress",
    )
    print("✅ Checkpoint deployed")
    return True


# ── Colab interaction ──────────────────────────────────────────────────────

def wait_for_colab_heartbeat(timeout_min: int = 10) -> bool:
    """Poll Drive for colab heartbeat to verify Colab is alive."""
    print(f"⏳ Waiting for Colab heartbeat (timeout: {timeout_min}min)...")
    start = time.time()
    while time.time() - start < timeout_min * 60:
        result = rclone("cat", f"{DRIVE_COMMANDS}/colab_heartbeat.json", check=False)
        if result.returncode == 0 and result.stdout.strip():
            try:
                hb = json.loads(result.stdout)
                print(f"✅ Colab alive! GPU: {hb.get('gpu', '?')}, time: {hb.get('time', '?')}")
                return True
            except json.JSONDecodeError:
                pass
        time.sleep(5)
    print("❌ No Colab heartbeat detected. Is the notebook running?")
    return False


def poll_worker_done(worker_dir_name: str, timeout_min: int = 120) -> dict | None:
    """Poll Drive for worker DONE marker."""
    remote_worker = f"{DRIVE_WORKERS}/{worker_dir_name}"
    print(f"⏳ Monitoring {worker_dir_name} (timeout: {timeout_min}min)...")
    start = time.time()
    last_status_time = 0
    while time.time() - start < timeout_min * 60:
        # Check DONE
        result = rclone("cat", f"{remote_worker}/DONE", check=False)
        if result.returncode == 0 and result.stdout.strip():
            try:
                payload = json.loads(result.stdout)
                print(f"\n✅ Worker DONE! Chunk: {payload.get('chunk', '?')}")
                print(f"   Steps: {payload.get('steps', '?')}, Loss: {payload.get('final_loss', 'N/A')}")
                print(f"   Time: {payload.get('train_seconds', 0)/60:.1f} min")
                return payload
            except json.JSONDecodeError:
                print("\n✅ Worker DONE marker found (no JSON payload)")
                return {"chunk": "unknown"}

        # Periodically show status
        now = time.time()
        if now - last_status_time > 60:
            elapsed = now - start
            print(f"   Still waiting... ({elapsed/60:.0f}min elapsed)")
            last_status_time = now

        time.sleep(15)

    print(f"❌ Worker did not complete within {timeout_min}min")
    return None


def download_checkpoint(worker_dir_name: str) -> Path | None:
    """Download worker checkpoint from Drive."""
    remote_worker = f"{DRIVE_WORKERS}/{worker_dir_name}"
    local_worker = LOCAL_SYNC_DIR / worker_dir_name
    os.makedirs(local_worker, exist_ok=True)

    rclone("copy", remote_worker, str(local_worker), "--progress")

    # Find the checkpoint.
    model = local_worker / "model.pt"
    if model.exists() and model.stat().st_size > 100:
        print(f"Downloaded model.pt ({model.stat().st_size/1e6:.1f}MB)")
        return local_worker

    final = local_worker / "final.pt"
    if final.exists() and final.stat().st_size > 100:
        print(f"✅ Downloaded final.pt ({final.stat().st_size/1e6:.1f}MB)")
        return final

    ckpt_dir = local_worker / "checkpoints"
    if ckpt_dir.exists():
        ckpts = sorted(ckpt_dir.glob("*.pt"))
        if ckpts:
            latest = ckpts[-1]
            print(f"✅ Downloaded {latest.name} ({latest.stat().st_size/1e6:.1f}MB)")
            return latest

    print("❌ No checkpoint found in downloaded worker dir")
    return None


def merge_checkpoint(checkpoint_paths: list[Path]) -> Path | None:
    """FedAvg merge checkpoints into base checkpoint."""
    if not checkpoint_paths:
        print("❌ No checkpoints to merge")
        return None

    if len(checkpoint_paths) == 1 and checkpoint_paths[0].is_dir():
        worker_checkpoint = checkpoint_paths[0]
        for name in ("model.pt", "metadata.json", "tokenizer.json"):
            src = worker_checkpoint / name
            if src.exists():
                shutil.copy2(src, LOCAL_CHECKPOINT / name)
        cortex_src = worker_checkpoint / "cortex"
        if cortex_src.exists():
            shutil.copytree(cortex_src, LOCAL_CHECKPOINT / "cortex", dirs_exist_ok=True)
        print(f"Promoted worker checkpoint into {LOCAL_CHECKPOINT}")
        return LOCAL_CHECKPOINT / "model.pt"

    import torch

    print(f"🔀 Merging {len(checkpoint_paths)} checkpoint(s)...")
    merged = None
    count = 0
    for ckpt in checkpoint_paths:
        print(f"   Loading {ckpt.name}...")
        state = torch.load(ckpt, map_location="cpu")
        if merged is None:
            merged = {k: v.clone() for k, v in state.items()}
        else:
            for k in merged:
                merged[k] += state[k]
        count += 1

    for k in merged:
        merged[k] /= count

    output = LOCAL_CHECKPOINT / "colab_merged.pt"
    torch.save(merged, output)
    total_params = sum(v.numel() for v in merged.values()) / 1e6
    print(f"✅ Merged checkpoint: {output} ({total_params:.0f}M params)")

    # Copy to base checkpoint directory for next iteration
    for f in LOCAL_CHECKPOINT.glob("*.pt"):
        if f.name != "colab_merged.pt":
            f.unlink()
    shutil.copy2(output, LOCAL_CHECKPOINT / "model.pt")

    return output


# ── SSH interaction ─────────────────────────────────────────────────────────

def ssh_command(ssh_target: str) -> list[str]:
    """Parse an SSH destination or pasted SSH command into argv."""
    parts = shlex.split(ssh_target, posix=False)
    if parts and parts[0].lower() == "ssh":
        parts = parts[1:]
    if not parts:
        raise ValueError("SSH target is empty")
    destination = next((part for part in parts if "@" in part), None)
    if destination is None:
        destination = f"root@{parts.pop(0)}"
    else:
        parts.remove(destination)
    return [
        "ssh",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        *parts,
        destination,
    ]


def validate_ssh_target(ssh_target: str) -> None:
    """Reject placeholders and malformed SSH ports before uploading inputs."""
    argv = ssh_command(ssh_target)
    destination = argv[-1]
    host = destination.split("@", 1)[-1]
    placeholders = {"host", "hostname", "port", "<host>", "<port>"}
    if host.lower() in placeholders or "<" in host or ">" in host:
        raise ValueError("replace HOST with the real hostname printed by the Colab notebook")
    if "-p" in argv:
        port_index = argv.index("-p") + 1
        if port_index >= len(argv) - 1:
            raise ValueError("SSH -p requires the numeric port printed by the Colab notebook")
        port = argv[port_index]
        if port.lower() in placeholders or not port.isdigit():
            raise ValueError("replace PORT with the numeric port printed by the Colab notebook")
        if not 1 <= int(port) <= 65535:
            raise ValueError("SSH port must be between 1 and 65535")


def ssh_run(ssh_host: str, command: str, timeout_min: int = 30) -> subprocess.CompletedProcess:
    """Run a command on Colab via SSH and stream output."""
    full_cmd = [*ssh_command(ssh_host), command]
    print(f"🔌 SSH: {command[:80]}...")
    return subprocess.run(
        full_cmd,
        timeout=timeout_min * 60,
        capture_output=True,
        text=True,
    )


# ── Main controller loop ────────────────────────────────────────────────────

def list_chunks():
    """Display available chunks."""
    chunks = load_chunk_index()
    state = load_state()
    processed = set(state.get("processed_chunks", []))

    print(f"\nAvailable chunks ({len(chunks)} total):")
    for i, c in enumerate(chunks, 1):
        marker = "x" if c["name"] in processed else " "
        size_mb = c["size_bytes"] / 1e6
        print(f"   [{marker}] {c['name']:45s} {size_mb:7.1f}MB  ({c['source']})")
    print(f"\nProcessed: {len(processed)}/{len(chunks)}")


def next_chunk() -> dict | None:
    """Return the next unprocessed chunk."""
    chunks = load_chunk_index()
    state = load_state()
    processed = set(state.get("processed_chunks", []))

    for c in chunks:
        if c["name"] not in processed:
            return c
    return None


def run_cycle(
    chunk: dict,
    ssh_host: str | None,
    steps: int = 5000,
    deploy_first: bool = True,
    timeout_min: int = 120,
) -> bool:
    """Run one complete train-merge cycle for a single chunk.

    Steps:
        1. Deploy chunk + checkpoint to Drive
        2. Upload colab_worker.py to Drive
        3. If SSH host provided: SSH in and start training
        4. Poll Drive for DONE marker
        5. Download checkpoint
        6. Merge into base
    """
    chunk_name = chunk["name"]
    worker_dir = f"worker_{chunk_name.replace('.jsonl', '').replace('.txt', '')}"

    print(f"\n{'='*60}")
    print(f"🔵 CYCLE: {chunk_name}")
    print(f"{'='*60}")

    # 1. Deploy
    if deploy_first:
        deploy_checkpoint()
        # Upload this chunk specifically
        chunk_local = CHUNKS_DIR / chunk_name
        if chunk_local.exists():
            rclone("copy", str(chunk_local), DRIVE_CHUNKS, "--progress")
        # Upload colab_worker.py
        rclone("copy", str(COLAB_DIR / "colab_worker.py"), DRIVE, "--progress")

    # 2. SSH in and start training (if host provided)
    if ssh_host:
        worker_output = f"/content/drive/MyDrive/{DRIVE_ROOT}/workers/{worker_dir}"
        cmd = (
            f"python colab_worker.py "
            f"--chunk {shlex.quote(chunk_name)} "
            f"--steps {steps} "
            f"--output-dir {shlex.quote(worker_output)}"
        )
        print("🔌 Starting training via SSH...")
        try:
            result = ssh_run(ssh_host, f"cd /content && nohup {cmd} > /content/train.log 2>&1 &", timeout_min=5)
            if result.returncode != 0:
                detail = (result.stderr or result.stdout or "no SSH error output").strip()
                print(f"SSH launch failed ({result.returncode}): {detail[:300]}")
                return False
            print("Training launched; polling Drive for completion.")
        except subprocess.TimeoutExpired:
            print("SSH launch timed out before confirmation.")
            return False

    # 3. Poll Drive for completion
    result = poll_worker_done(worker_dir, timeout_min=timeout_min)
    if not result:
        return False

    # 4. Download checkpoint
    ckpt = download_checkpoint(worker_dir)
    if not ckpt:
        return False

    # 5. Merge
    merge_checkpoint([ckpt])

    # 6. Update state
    state = load_state()
    processed = state.get("processed_chunks", [])
    if chunk_name not in processed:
        processed.append(chunk_name)
    state["processed_chunks"] = processed
    state["current_chunk"] = None
    state["total_chunks"] = len(load_chunk_index())
    save_state(state)

    return True


# ── Interactive mode ────────────────────────────────────────────────────────

def interactive():
    """Walk user through the process interactively."""
    print("\n🧬 NP-DNA Colab Controller — Interactive Mode")
    print("=" * 60)

    # Ensure chunks exist
    chunks = load_chunk_index()
    state = load_state()
    processed = set(state.get("processed_chunks", []))

    print(f"\n📊 {len(chunks)} total chunks, {len(processed)} processed")
    if len(processed) > 0:
        print("   Last checkpoint merged into base. The next chunk will continue from there.")

    unprocessed = [c for c in chunks if c["name"] not in processed]
    if not unprocessed:
        print("\n✅ All chunks processed! Training complete.")
        return

    # Deploy chunks and checkpoint to Drive
    print("\n📤 Step 1: Deploy to Drive")
    deploy_chunks()
    deploy_checkpoint()
    # Upload colab_worker.py
    rclone("copy", str(COLAB_DIR / "colab_worker.py"), DRIVE, "--progress")

    for chunk in unprocessed:
        chunk_name = chunk["name"]
        size_mb = chunk["size_bytes"] / 1e6
        print(f"\n{'='*60}")
        print(f"📦 Next chunk: {chunk_name} ({size_mb:.1f}MB)")
        print(f"{'='*60}")

        # Deploy this specific chunk
        chunk_local = CHUNKS_DIR / chunk_name
        if chunk_local.exists():
            print("📤 Uploading chunk to Drive...")
            rclone("copy", str(chunk_local), DRIVE_CHUNKS, "--progress")

        print("\n🔴 Step 2: Open Colab and run the notebook")
        print("   1. Go to: https://colab.research.google.com/drive/<NOTEBOOK_ID>")
        print("   2. Run all cells (mount Drive + start SSH)")
        print("   3. Copy the SSH command shown in the output")
        print("\n   Then paste the SSH command below (or 'skip' to skip this chunk,")
        print("   'exit' to stop):")

        ssh_info = input("\nSSH command > ").strip()
        if ssh_info.lower() in ("exit", "quit"):
            print("Exiting.")
            break
        if ssh_info.lower() == "skip":
            state["processed_chunks"].append(chunk_name)
            save_state(state)
            continue
        if not ssh_info:
            print("⏭️  No SSH info, marking as skipped")
            continue

        # Parse SSH info: ssh root@host -p port
        ssh_host = None
        if "@" in ssh_info:
            parts = ssh_info.replace("ssh ", "").split()
            for p in parts:
                if "@" in p:
                    ssh_host = p.split("@")[1]
                    break
        if not ssh_host:
            print("⚠️  Could not parse SSH host, continuing with Drive polling only...")

        # Run training
        worker_dir = f"worker_{chunk_name.replace('.jsonl', '').replace('.txt', '')}"
        cmd = (
            f"cd /content && nohup python colab_worker.py "
            f"--chunk {chunk_name} "
            f"--steps 5000 "
            f"--output-dir /content/drive/MyDrive/{DRIVE_ROOT}/workers/{worker_dir} "
            f"> /content/train.log 2>&1 &"
        )

        if ssh_host:
            try:
                print("🔌 Starting training via SSH...")
                run_result = subprocess.run(
                    ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
                     f"root@{ssh_host}", cmd],
                    timeout=30, capture_output=True, text=True
                )
                if run_result.returncode != 0:
                    print(f"⚠️  SSH warning: {run_result.stderr[:200]}")
                print("   Training started in background. Polling Drive for completion...")
            except subprocess.TimeoutExpired:
                print("   SSH timed out (expected for nohup). Training should be running.")
            except Exception as e:
                print(f"❌ SSH failed: {e}")
                print("   Continuing to poll Drive anyway...")

        # Poll for completion
        result = poll_worker_done(worker_dir, timeout_min=120)
        if result:
            ckpt = download_checkpoint(worker_dir)
            if ckpt:
                merge_checkpoint([ckpt])
                # Deploy merged checkpoint to Drive for next chunk
                deploy_checkpoint()
                print(f"\n✅ Chunk {chunk_name} complete! Ready for next chunk.")

        state = load_state()
        processed_list = state.get("processed_chunks", [])
        if chunk_name not in processed_list:
            processed_list.append(chunk_name)
        state["processed_chunks"] = processed_list
        save_state(state)

        print("\n🔄 Next chunk ready. Open a NEW Colab session and run the notebook again.")
        again = input("\nContinue to next chunk? (Y/n) > ").strip().lower()
        if again == "n":
            break

    print("\n🎉 Controller finished!")


# ── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="NP-DNA Training Controller")
    parser.add_argument("--list-chunks", action="store_true", help="List available chunks")
    parser.add_argument("--next-chunk", action="store_true", help="Show next unprocessed chunk")
    parser.add_argument("--deploy-chunks", action="store_true", help="Upload chunks to Drive")
    parser.add_argument("--deploy-checkpoint", action="store_true", help="Upload checkpoint to Drive")
    parser.add_argument("--run-chunk", metavar="NAME", help="Run one named chunk and retrieve its checkpoint")
    parser.add_argument("--ssh", dest="ssh_target", help="SSH destination or pasted SSH command for --run-chunk")
    parser.add_argument("--steps", type=int, default=5000, help="Training steps for --run-chunk")
    parser.add_argument("--timeout-min", type=int, default=120, help="Completion timeout for --run-chunk")
    parser.add_argument("--no-deploy", action="store_true", help="Skip uploads before --run-chunk")
    parser.add_argument("--reset", action="store_true", help="Reset processed chunks")
    parser.add_argument("--auto", action="store_true", help="Automated mode (non-interactive)")
    args = parser.parse_args()

    if args.reset:
        save_state({"processed_chunks": [], "current_chunk": None, "total_chunks": 0})
        print("✅ State reset")
        return

    if args.list_chunks:
        list_chunks()
        return

    if args.next_chunk:
        c = next_chunk()
        if c:
            print(f"Next: {c['name']} ({c['size_bytes']/1e6:.1f}MB) from {c['source']}")
        else:
            print("✅ All chunks processed!")
        return

    if args.deploy_chunks:
        deploy_chunks()
        return

    if args.deploy_checkpoint:
        deploy_checkpoint()
        return

    if args.run_chunk:
        chunks = {chunk["name"]: chunk for chunk in load_chunk_index()}
        chunk = chunks.get(args.run_chunk)
        if not chunk:
            parser.error(f"unknown chunk: {args.run_chunk}")
        if not args.ssh_target:
            parser.error("--run-chunk requires --ssh")
        try:
            validate_ssh_target(args.ssh_target)
        except ValueError as exc:
            parser.error(f"invalid --ssh value: {exc}")
        success = run_cycle(
            chunk,
            args.ssh_target,
            steps=args.steps,
            deploy_first=not args.no_deploy,
            timeout_min=args.timeout_min,
        )
        sys.exit(0 if success else 1)

    # Default: interactive mode
    if args.auto:
        print("⚠️  --auto mode not fully implemented yet. Use interactive mode.")
        print("   Will still start with --deploy-chunks + --deploy-checkpoint.")
        deploy_chunks()
        deploy_checkpoint()
        rclone("copy", str(COLAB_DIR / "colab_worker.py"), DRIVE, "--progress")
        return

    interactive()


if __name__ == "__main__":
    main()
