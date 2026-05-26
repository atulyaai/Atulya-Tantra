#!/usr/bin/env python3
"""generate_train_ipynb.py — Generate the colab-ssh train.ipynb."""
import json

cells = []

def md(text):
    cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [text]
    })

def code(text):
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [text]
    })

md("# 🧬 NP-DNA Colab Worker — SSH Remote Control\n━━━━━━━━━━━━━━━━━━━━\n\n**Flow:**\n1. Run this cell → mounts Drive + starts SSH tunnel (via colab-ssh + ngrok)\n2. Copy the SSH command shown below and send it to the local controller\n3. The controller will SSH in, train on one dataset chunk, save back to Drive\n4. When done, this session finishes. Controller will ask you to start a new one for the next chunk.")

code("""# ① Mount Google Drive
from google.colab import drive
drive.mount('/content/drive')
print('✅ Drive mounted')""")

code("""# ② Install dependencies
import subprocess, sys, os, time, json, threading, shutil

def run(cmd, **kw):
    print(f"$ {cmd}")
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, **kw)

# Install colab-ssh
run("pip install -q colab-ssh --upgrade")
run("apt-get -qq update && apt-get -qq install -y openssh-server > /dev/null 2>&1")

# Copy source from Drive
DRIVE_BASE = "/content/drive/MyDrive/npdna_training"
if os.path.exists(f"{DRIVE_BASE}/source/tantra"):
    if os.path.exists("/content/tantra"):
        shutil.rmtree("/content/tantra")
    shutil.copytree(f"{DRIVE_BASE}/source/tantra", "/content/tantra")
    sys.path.insert(0, "/content")
    print("✅ Source copied from Drive")

# Copy colab_worker.py
if os.path.exists(f"{DRIVE_BASE}/colab_worker.py"):
    shutil.copy(f"{DRIVE_BASE}/colab_worker.py", "/content/colab_worker.py")
    print("✅ colab_worker.py copied")
    import colab_worker  # noqa: F401

import torch
print(f"🖥️  GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'}")""")

code("""# ③ Start SSH tunnel via colab-ssh
from colab_ssh import launch_ssh_cloudflared

# This sets up SSH with password
PASSWORD = "atulya"
try:
    launch_ssh_cloudflared(password=PASSWORD)
    print("\\n" + "=" * 60)
    print("🔑 SSH PASSWORD: atulya")
    print("=" * 60)
except Exception as e:
    print(f"colab-ssh error: {e}")
    print("Trying ngrok method directly...")
    
    # Fallback: start SSH + ngrok manually
    run("service ssh start")
    run(f"echo -e '{PASSWORD}\\\\n{PASSWORD}' | passwd root")
    
    # Install ngrok
    if not os.path.exists("/content/ngrok"):
        run("wget -q https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz -O /content/ngrok.tgz")
        run("tar -xzf /content/ngrok.tgz -C /content/")
        os.chmod("/content/ngrok", 0o755)
    
    # Start ngrok tunnel to SSH
    ngrok_process = subprocess.Popen(
        ["/content/ngrok", "tcp", "22", "--log", "/content/ngrok.log"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    time.sleep(5)
    
    # Get the ngrok URL
    try:
        import requests
        tunnels = requests.get("http://localhost:4040/api/tunnels").json()
        for t in tunnels.get("tunnels", []):
            if t.get("proto") == "tcp":
                pub_url = t["public_url"].replace("tcp://", "")
                host, port = pub_url.rsplit(":", 1)
                print("\\n" + "=" * 60)
                print("🔑 SSH PASSWORD: atulya")
                print(f"🌐 SSH: ssh root@{host} -p {port}")
                print("=" * 60)
                break
        else:
            print("⚠️  Could not get ngrok URL. Check /content/ngrok.log")
    except Exception as e2:
        print(f"⚠️  ngrok tunnel error: {e2}")
        print(f"   Check /content/ngrok.log for details")""")

code("""# ④ Wait for training commands from controller
# The controller will SSH in and run colab_worker.py
# This cell keeps the session alive until training completes

import time, os, json

DRIVE_BASE = "/content/drive/MyDrive/npdna_training"
monitor_dir = f"{DRIVE_BASE}/commands"
os.makedirs(monitor_dir, exist_ok=True)

print("\\n" + "=" * 60)
print("⏳ Waiting for controller to SSH in and start training...")
print("=" * 60)

# Write a heartbeat so controller knows Colab is alive
heartbeat_file = f"{monitor_dir}/colab_heartbeat.json"
with open(heartbeat_file, "w") as f:
    json.dump({"status": "alive", "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU", "time": time.ctime()}, f)

# Poll for DONE marker from worker
check_interval = 30
while True:
    try:
        # Check if any worker finished on Drive
        workers_dir = f"{DRIVE_BASE}/workers"
        if os.path.exists(workers_dir):
            for w in os.listdir(workers_dir):
                done_path = os.path.join(workers_dir, w, "DONE")
                if os.path.exists(done_path):
                    with open(done_path) as f:
                        result = json.load(f)
                    print(f"\\n✅ Worker {w} completed!")
                    print(f"   Chunk: {result.get('chunk', '?')}")
                    print(f"   Steps: {result.get('steps', '?')}")
                    print(f"   Time: {result.get('train_seconds', 0)/60:.1f} min")
                    print(f"   Loss: {result.get('final_loss', 'N/A')}")
                    print("\\n🔄 You can close this Colab session now.")
                    print("   Controller will pick up the checkpoint and request next chunk.")
                    # Keep running so Drive syncs
                    time.sleep(600)
                    sys.exit(0)
    except Exception:
        pass
    
    # Update heartbeat
    try:
        with open(heartbeat_file, "w") as f:
            json.dump({"status": "alive", "time": time.ctime()}, f)
    except Exception:
        pass
    
    time.sleep(check_interval)""")

notebook = {
    "cells": cells,
    "metadata": {
        "accelerator": "GPU",
        "colab": {"provenance": []},
        "kernelspec": {"display_name": "Python 3", "name": "python3"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 0,
}

with open("F:/Atulya Tantra/training_collab/train.ipynb", "w") as f:
    json.dump(notebook, f, indent=2)

print("✅ train.ipynb generated with colab-ssh tunnel")
