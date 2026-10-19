"""Separate server worker: consumes approved fixed operations and verifies results."""
import argparse
import subprocess
import time
from pathlib import Path

import httpx
from atulya.operations import Operations


def execute(job):
    if job.get("kind") != "restart" or job.get("target") != "atulya.service" or job.get("owner") != "admin":
        return False, "Refused an operation outside the fixed allowlist."
    try:
        result = subprocess.run(["sudo", "-n", "systemctl", "restart", "atulya.service"], capture_output=True, timeout=45)
        if result.returncode:
            return False, f"Service manager rejected restart (exit {result.returncode}); inspect owner logs."
        deadline = time.monotonic() + 50
        with httpx.Client(trust_env=False, timeout=3) as client:
            while time.monotonic() < deadline:
                state = subprocess.run(["systemctl", "is-active", "atulya.service"], capture_output=True, timeout=5)
                try:
                    health = client.get("http://127.0.0.1:8501/api/health", headers={"Host": "localhost:8501"})
                    if state.returncode == 0 and health.status_code == 200 and health.json().get("status") == "ok":
                        return True, "Atulya restarted; systemd active and local health check passed."
                except (httpx.HTTPError, ValueError):
                    pass
                time.sleep(2)
        return False, "Restart requested, but service health did not recover before timeout."
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"Operation could not complete ({type(exc).__name__}); execution is unconfirmed."


def observe_health(ops):
    import psutil
    disk = psutil.disk_usage(str(ops.path.parent)).percent
    memory = psutil.virtual_memory().percent
    state = subprocess.run(["systemctl", "is-active", "atulya.service"], capture_output=True, timeout=5)
    service_down = state.returncode != 0
    ops.observe("service", service_down, "Atulya server service is unavailable." if service_down else "Atulya server service recovered.")
    ops.observe("disk", disk >= 95, f"Server disk usage is critical: {disk:.0f}%." if disk >= 95 else "Server disk usage recovered below 95%.")
    ops.observe("memory", memory >= 95, f"Server memory usage is critical: {memory:.0f}%." if memory >= 95 else "Server memory usage recovered below 95%.")


def poll_once(ops, executor=execute):
    ops.heartbeat()
    job = ops.claim()
    if job is None:
        return None
    ok, message = executor(job)
    ops.finish(job, ok, message)
    return {"id": job["id"], "success": ok}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    args.data_dir.mkdir(parents=True, exist_ok=True)
    # Hold a process lock across health verification so two worker services cannot
    # overlap a restart. A crashed running job is never replayed.
    import fcntl
    worker_lock = (args.data_dir / "operations-worker.lock").open("a+b")
    try:
        fcntl.flock(worker_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        raise SystemExit("An operations worker already holds this data directory") from None
    ops = Operations(args.data_dir)
    last_observed = 0
    while True:
        try:
            result = poll_once(ops)
            if result:
                outcome = "unconfirmed" if result["success"] is None else "executed" if result["success"] else "failed"
                print(f"Operation {result['id']}: {outcome}", flush=True)
            if time.monotonic() - last_observed > 30:
                observe_health(ops)
                last_observed = time.monotonic()
        except Exception as exc:
            print(f"Operations worker error: {type(exc).__name__}", flush=True)
        time.sleep(2)


if __name__ == "__main__":
    main()
