# demo: try a bigger brain

Three ways to get a smarter or faster brain than the tiny default.

## 1. Cloud key (easiest, fastest)
Put a key in `.env` (see README, Brains). Your questions go to that company.

## 2. Bigger local model on your PC
```
pip install -e ".[brain]" huggingface_hub
python demo/try_model.py --list              # sizes and which fits your free RAM
python demo/try_model.py --model 4b          # download to demo/models/ and benchmark
python demo/try_model.py --model 4b --use    # also make Atulya use it (writes .env)
```
Results are appended to `demo/results.md`.

Measured on a 4-core CPU (no GPU), words per second:
0.6b 37.0, 1.7b 15.9, 4b 7.5, 8b 4.2.

**Honest finding:** raw speed is fine, but a whole Atulya answer was much slower
(18.4 s with 0.6b, 83.9 s with 4b for one sentence), because each turn also
sends a long instruction and tool prompt. On CPU, bigger local models make that
worse. A GPU (route 3) or a cloud key avoids it.

## 3. Free GPU on Google Colab
1. Open `demo/colab/atulya_remote_brain.ipynb` in Colab, choose a GPU runtime, run all cells.
2. It prints a command. Run it on your PC:
```
python demo/connect_remote.py --url https://xxxx.trycloudflare.com/v1 --key KEY --model NAME
python demo/connect_remote.py --remove       # disconnect
```
Caveats: the notebook has not been run on Colab by its author. Your questions
pass through Colab and a public tunnel (protected only by the random key).
Colab limits and terms apply, and sessions end.
