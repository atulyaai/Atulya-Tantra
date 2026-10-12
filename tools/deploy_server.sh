#!/usr/bin/env sh
# Server-side deploy, run by the GitHub Actions deploy key (forced command; it can run nothing else).
# Pull main, install changed dependencies, restart, health-check; roll back to the previous commit on failure.
set -eu
cd "$HOME/Atulya-Tantra"
previous=$(git rev-parse HEAD)
git fetch -q origin main
target=$(git rev-parse origin/main)
if [ "$previous" = "$target" ]; then echo "already at $target"; exit 0; fi
git reset -q --hard "$target"
if ! git diff --quiet "$previous" "$target" -- requirements.lock.txt; then
    .venv/bin/python -m pip install -q -r requirements.lock.txt
fi
# New voices/models or packages declared in setup (models only; skips the large PC models).
# A failed model download must not block the code update; the old models keep working.
ATULYA_SKIP_MODELS=1 .venv/bin/python tools/bootstrap.py >/dev/null || echo "warning: model setup failed (see above)" >&2
sudo systemctl restart atulya.service
for i in $(seq 1 30); do
    if curl -fsS -o /dev/null -H "Host: localhost:8501" http://127.0.0.1:8501/api/health; then
        echo "deployed $target (was $previous)"
        exit 0
    fi
    sleep 2
done
echo "health check failed; rolling back to $previous" >&2
git reset -q --hard "$previous"
sudo systemctl restart atulya.service
exit 1
