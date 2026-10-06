# Setup: the whole system on one page

Every stage in the order you actually do them: **install → folders → files → brains →
tools → MQTT → channels → what's still missing → evolving.**

State column:

| Mark | Means |
|---|---|
| **Live** | written, tested, and it has been run for real |
| **Built** | written and unit-tested; **never run on real hardware/accounts** |
| **Planned** | not written yet |

Nothing here is claimed as proven that isn't proven. See [STATUS.md](STATUS.md) for the
capability detail and [ROADMAP.md](ROADMAP.md) for why the order is what it is.

---

## 1. One command to install

| Where | Command | Notes |
|---|---|---|
| **Linux / SSH / WSL** | `curl -fsSL https://raw.githubusercontent.com/atulyaai/Atulya-Tantra/main/install.sh \| bash` | Clones into `~/Atulya-Tantra`, installs Python, git and Node if missing, asks for your settings one at a time, builds, checks. Same thing cPanel-style |
| Linux, already cloned | `bash install.sh` | Reuses the checkout it sits in instead of fetching a second copy |
| Linux, no prompts | `bash install.sh --yes` | Takes every default — VPS, CI, container |
| Linux, report only | `bash install.sh --check` | Changes nothing |
| **Windows PowerShell** | `git clone https://github.com/atulyaai/Atulya-Tantra.git; cd Atulya-Tantra; python install.py` | The guided installer: shows what is configured, asks only for what is missing, builds the dashboard, checks it works |
| Windows, report only | `python install.py --doctor` | Changes nothing |
| Windows, unattended | `python install.py --yes` | cPanel, VPS, CI |
| Either, pin the profile | `python install.py --profile full` | `basic` / `voice` / `full` / `server` — no prompts |
| Either, start by itself | `python install.py --service` | systemd unit on Linux, sign-in shortcut on Windows |
| **Planned** `install.ps1` | `irm https://raw.githubusercontent.com/atulyaai/Atulya-Tantra/main/install.ps1 \| iex` | Not written. Today's Windows path needs git + Python already present. This would make Windows a true one-liner |

### Day-to-day commands

| Task | Linux | Windows |
|---|---|---|
| Start | `. .venv/bin/activate && python -m atulya.sevak` or `./start.sh` | `python -m atulya.sevak` or `start.bat` |
| Start at boot | `sudo systemctl enable --now atulya` | `python install.py --service` |
| Status | `systemctl status atulya` | Task Manager |
| Logs | `journalctl -u atulya -f` | console window |
| Health | `curl -i http://127.0.0.1:8501/api/health` | `Invoke-WebRequest http://127.0.0.1:8501/api/health` |
| Open the UI | http://localhost:8501 | http://localhost:8501 (Chrome/Edge, allow mic) |
| Update | `cd ~/Atulya-Tantra && git pull && bash install.sh --yes` | `git pull; python install.py --doctor` |
| Rebuild the web UI | `python frontend/build.py` | `python frontend/build.py` |

> **Behind nginx/Caddy?** Set `ATULYA_HOST=127.0.0.1`. On a phone-only LAN set
> `ATULYA_HOST=0.0.0.0`. Changing it needs a restart.

---

## 2. Jarvis' basic folders

| Folder | What lives in it | In git? |
|---|---|---|
| `atulya/` | The assistant. 21 top-level modules | ✅ |
| `atulya/mastishk/` | **Brain** — tiers, provider catalogue, router, safety rules, tool belt, local model | ✅ |
| `atulya/kriya/` | **Actions** — money, calendar, news, MQTT, reminders, media, the action engine | ✅ |
| `atulya/dwar/` | **Web/API** — routes, agent routes, channel webhooks, system routes | ✅ |
| `atulya/kosh/` | Storage layer shared by the modules above | ✅ |
| `atulya/runtime/` | In-process runtime pieces | ✅ |
| `atulya/dut.py` | CLI — talk to Atulya from a terminal | ✅ |
| `atulya/sevak.py` | The server: FastAPI app, static mount, startup | ✅ |
| `kosh/` | **Your data.** Everything Atulya learns about you | ❌ gitignored |
| `runtime/` | Models, scratch, downloaded weights | ❌ gitignored |
| `assets/` | `ATULYA_DATA_DIR` — data shipped with the project | ✅ |
| `frontend/` | Web UI source + build (**planned rename → `webui/`**) | ✅ |
| `docs/` | This file, STATUS, ROADMAP, DEPLOYMENT, RECIPES, DEVICES, CONTRIBUTING | ✅ |
| `tests/` | 981 tests | ✅ |
| `examples/` | Termux phone helper, GPU/Colab route (**planned removal**) | ✅ |
| `tools/` | Repo maintenance — the personal-value audit | ✅ |
| `.venv/` | Python environment | ❌ |
| `frontend/node_modules/` | Web build tools | ❌ |

### Inside `kosh/` — your memory

| Path | Holds |
|---|---|
| `kosh/chat_history.json` | Conversation log |
| `kosh/users.json` | Accounts |
| `kosh/jwt_secret.key` | Sign-in key, created once |
| `kosh/identity.json` | Persona — missing means "using defaults" |
| `kosh/agent/profiles/` | What it has learned about each person |
| `kosh/agent/routines.json` | Multi-step plans ("movie mode") |
| `kosh/agent/triggers.json` | Proactive triggers ("tell me when…") |
| `kosh/agent/audit.jsonl` | Every action the brain took, hash-chained |
| `kosh/agent/money.json` | Spend, budgets, bills — local file only |
| `kosh/memory/vector_atulya_memory.json` | Vector memory |
| `kosh/memory/session_search.db` | Searchable sessions |
| `kosh/state/mood.json` | Current mood |
| `kosh/channels/` | Per-channel state |
| `kosh/audio/{stt,tts}/` | Voice cache |

---

## 3. File names you touch

| File | Purpose | Edit? |
|---|---|---|
| `.env` | **All of your settings.** Never committed | ✅ yes, this is the one |
| `.env.example` | The annotated template — start here | read it |
| `install.sh` | Linux: software → clone → settings → build | only to change the installer |
| `install.py` | Windows installer + `--doctor` | only to change the installer |
| `start.sh` / `start.bat` | Daily launcher (Linux / Windows) | rarely |
| `atulya/setu_servers.json` | **MCP servers** — enable/disable | ✅ yes |
| `mqtt_config.json` | **MQTT broker** connection | created by `mqtt_configure` |
| `kosh/agent/triggers.json` | Your proactive triggers | ✅ or just ask it |
| `kosh/agent/routines.json` | Your routines | ✅ or just ask it |
| `cloudflared-config.yml.example` | Cloudflare tunnel template | copy, then edit |
| `docker-compose.yml` / `Dockerfile` | Container path (**unverified — F1**) | only if you use Docker |
| `tools/.personal-values` | Your domain/IP/ids, for the audit | ✅ yours, gitignored |
| `atulya/setu.py` | The MCP client | rarely |
| `atulya/mastishk/suchi.py` | The 22-provider catalogue | when adding a provider |
| `frontend/build.py` | Builds the web UI | rarely |

---

## 4. Connect models and APIs (the brain)

**Twenty-two providers, fourteen of them free-tier.** The router measures each configured
brain and tries the fastest first. `.env` is read top to bottom — **the first occurrence of a
name wins**.

| # | Provider | Key variable | Model variable | Cost | Get a key |
|---|---|---|---|---|---|
| 1 | Claude (Anthropic) | `ANTHROPIC_API_KEY` | `ATULYA_CLAUDE_MODEL` | paid | console.anthropic.com/settings/keys |
| 2 | ChatGPT / OpenAI | `OPENAI_API_KEY` | `ATULYA_OPENAI_MODEL` | paid | platform.openai.com/api-keys |
| 3 | Google Gemini | `GEMINI_API_KEY` | `ATULYA_GEMINI_MODEL` | **free tier** | aistudio.google.com/app/apikey |
| 4 | Groq (very fast) | `GROQ_API_KEY` | `ATULYA_GROQ_MODEL` | **free tier** | console.groq.com/keys |
| 5 | NVIDIA NIM | `NVIDIA_API_KEY` | `ATULYA_NVIDIA_MODEL` | **free tier** | build.nvidia.com |
| 6 | OpenRouter | `OPENROUTER_API_KEY` | `ATULYA_OPENROUTER_MODEL` | **free tier** | openrouter.ai/keys |
| 7 | OpenCode Go | `OPENCODE_API_KEY` | `ATULYA_OPENCODE_MODEL` | paid | opencode.ai/auth |
| 8 | Mistral | `MISTRAL_API_KEY` | `ATULYA_MISTRAL_MODEL` | **free tier** | console.mistral.ai/api-keys |
| 9 | DeepSeek | `DEEPSEEK_API_KEY` | `ATULYA_DEEPSEEK_MODEL` | paid | platform.deepseek.com/api_keys |
| 10 | Qwen (DashScope) | `DASHSCOPE_API_KEY` | `ATULYA_QWEN_MODEL` | **free tier** | bailian.console.alibabacloud.com |
| 11 | Grok (xAI) | `XAI_API_KEY` | `ATULYA_XAI_MODEL` | paid | console.x.ai |
| 12 | Together AI | `TOGETHER_API_KEY` | `ATULYA_TOGETHER_MODEL` | **free tier** | api.together.ai/settings/api-keys |
| 13 | Fireworks AI | `FIREWORKS_API_KEY` | `ATULYA_FIREWORKS_MODEL` | **free tier** | fireworks.ai/account/api-keys |
| 14 | Cerebras (very fast) | `CEREBRAS_API_KEY` | `ATULYA_CEREBRAS_MODEL` | **free tier** | cloud.cerebras.ai |
| 15 | SambaNova | `SAMBANOVA_API_KEY` | `ATULYA_SAMBANOVA_MODEL` | **free tier** | cloud.sambanova.ai/apis |
| 16 | Perplexity (web answers) | `PERPLEXITY_API_KEY` | `ATULYA_PERPLEXITY_MODEL` | paid | perplexity.ai/settings/api |
| 17 | Kimi (Moonshot) | `MOONSHOT_API_KEY` | `ATULYA_MOONSHOT_MODEL` | paid | platform.moonshot.ai |
| 18 | GLM (Zhipu) | `ZHIPU_API_KEY` | `ATULYA_ZHIPU_MODEL` | **free tier** | open.bigmodel.cn |
| 19 | SiliconFlow | `SILICONFLOW_API_KEY` | `ATULYA_SILICONFLOW_MODEL` | **free tier** | cloud.siliconflow.com |
| 20 | Hugging Face | `HF_TOKEN` | `ATULYA_HF_MODEL` | **free tier** | huggingface.co/settings/tokens |
| 21 | GitHub Models | `GITHUB_MODELS_TOKEN` | `ATULYA_GITHUB_MODEL` | **free tier** | github.com/settings/tokens |
| 22 | Your own (LM Studio, vLLM, any OpenAI-style URL) | `ATULYA_CUSTOM_KEY` | `ATULYA_CUSTOM_MODEL` | local | — |

Catalogue lives in **`atulya/mastishk/suchi.py`**. Adding a provider is one `Spec(...)` line.

### Brain size — one setting

| `ATULYA_BRAIN=` | What you get | Needs |
|---|---|---|
| `tiny` *(default)* | Qwen3-0.6B, ~380 MB, fully offline, no Ollama, no torch | `pip install -e ".[brain]"` |
| `balanced` | Qwen3-1.7B, better answers, slower | same |
| `power` | Qwen3-4B, best local, 14–90 s per answer on CPU | same |
| `cloud` | Configured cloud providers first; tiny local stays as the offline fallback | a key from the table above |

Also useful: `ATULYA_MAX_TOOL_SCHEMAS` (how many tools the model sees — small models do
better with fewer), `ATULYA_AUTO_APPROVE` (what runs without asking).

**No key at all?** It still works: offline persona replies, plus every command that does not
need a model.

### Other integrations

| What | Variables |
|---|---|
| Google Drive | `GOOGLE_SERVICE_ACCOUNT_KEY` (minified JSON) |
| Gmail | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN` |
| Google sign-in / Calendar | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `ATULYA_PUBLIC_URL` |
| Home Assistant | `HOME_ASSISTANT_URL`, `HOME_ASSISTANT_TOKEN` |
| Web push (PWA) | `ATULYA_VAPID_PUBLIC_KEY`, `ATULYA_VAPID_PRIVATE_KEY`, `ATULYA_VAPID_SUBJECT` |
| Cloudflare tunnel | `CF_TUNNEL_TOKEN` |
| Voice in/out | `pip install -e ".[voice]"` |

**Easiest route:** the web UI → **Menu → Brains & keys** → paste key, pick model, **Test**,
Remove. Saved to `.env`, owner-only, never shown again.

---

## 5. MCP servers

Ten are declared in **`atulya/setu_servers.json`**; four ship enabled. They all shell out to
`npx`, so **Node.js is required**.

| Server | Enabled | Package | What it gives Atulya | Needs |
|---|---|---|---|---|
| `filesystem` | ✅ | `@modelcontextprotocol/server-filesystem` | Read/write files | Node |
| `git` | ✅ | `mcp-git` | Commits, diffs, history | Node |
| `playwright` | ✅ | `@playwright/mcp` | A real browser — the web agent | Node + `playwright install chromium` |
| `fetch` | ✅ | `@modelcontextprotocol/server-fetch` | Fetch a URL | Node |
| `mqtt` | ❌ | `mcp-mqtt` | Publish/subscribe to a broker | Node + broker |
| `brave-search` | ❌ | `@modelcontextprotocol/server-brave-search` | Web search | Node + `BRAVE_API_KEY` |
| `memory` | ❌ | `@modelcontextprotocol/server-memory` | Knowledge graph memory | Node |
| `twilio` | ❌ | `mcp-twilio` | Calls and SMS | Node + Twilio account |
| `google_drive` | ❌ | `mcp-google-drive` | Drive files | Node + Google creds |
| `home-assistant` | ❌ | HTTP to `:8123/mcp` | Smart home | Running HA + token |

Turn one on: set `"enabled": true`, restart. Check them in the dashboard.

> **Status:** all four enabled servers currently **fail to connect** on the live server even
> though Node is installed. Not yet diagnosed — see §8.

---

## 6. MQTT

Two independent paths; you can use either or both.

| | Native watcher | MCP server |
|---|---|---|
| File | `atulya/kriya/mqtt.py` | `atulya/setu_servers.json` → `mqtt` |
| What it does | Subscribes and republishes each message as an **event** the brain can react to | Exposes publish/subscribe as **tools** the brain can call |
| Default | broker unset → **idles** | disabled |
| Port | `1883` | `1883` |
| Subscribe | `atulya/#` | — |
| Event name | `mqtt.<topic>` | — |
| Needs | `paho-mqtt` | Node + `mcp-mqtt` |

**Configure by talking to it** (writes `mqtt_config.json`):

| Tool | Does |
|---|---|
| `mqtt_configure(host, port, subscribe, username, password)` | Set the broker |
| `mqtt_status()` | `MQTT not configured. Use mqtt_configure to set a broker.` when empty |

Reconnects with backoff on error. Useful for sensors, Home Assistant, ESP32 boards, Tasmota
plugs — anything that publishes on a topic.

---

## 7. Channels — where messages come from and go

Sixteen channel types are declared in `atulya/sandesh.py`.

| Channel | State | Notes |
|---|---|---|
| **Telegram** | **Live** | Bot token + allowlist; voice replies; Mini App via `ATULYA_PUBLIC_URL` |
| **Webchat** | **Live** | The web UI itself |
| **Email** | **Built** | Outbound replies, inbound watching |
| **Web push** | **Built** | VAPID keys; PWA delivery |
| **WhatsApp** | **Built** | Cloud API webhook — `POST /api/channels/whatsapp`, signature-checked with `ATULYA_WHATSAPP_APP_SECRET` |
| **Slack** | **Built** | `POST /api/channels/slack` |
| **Discord** | **Built** | `POST /api/channels/discord`, Ed25519 with `ATULYA_DISCORD_PUBLIC_KEY` |
| **Console** | **Live** | `python -m atulya.dut` from a terminal |
| Twilio (calls/SMS) | **Built** | A5 — needs a real Twilio account |
| Signal, Matrix, iMessage, Teams, IRC, Feishu, Line, QQ | **Planned** | Declared in the enum, no wiring |
| Generic webhook | **Built** | `POST` anything in |

### Webhook setup

| Channel | Endpoint | Env vars |
|---|---|---|
| WhatsApp | `https://your.host/api/channels/whatsapp` | `ATULYA_WHATSAPP_VERIFY_TOKEN`, `ATULYA_WHATSAPP_APP_SECRET` |
| Slack | `https://your.host/api/channels/slack` | — |
| Discord | `https://your.host/api/channels/discord` | `ATULYA_DISCORD_PUBLIC_KEY` |

Every inbound message is checked against the **allowlist** before the brain sees it. Anything
that spends, sends or deletes **asks first**.

### Phone / device channels

| Channel | File | State |
|---|---|---|
| Phone pairing + inbox | `atulya/phone.py` | Built |
| Android listener | `atulya/shruti_phone.py` | Built, unverified on hardware |
| Termux companion | `examples/termux_phone.sh` | Needs `ATULYA_SERVER` |
| TV / Android / smart home | `atulya/upakaran.py` | Built, 52 tests, no real hardware |
| PC control | `atulya/kriya/` | Built, gated by confirmation |

---

## 8. What else Jarvis needs

Straight from [ROADMAP.md](ROADMAP.md). **Order matters: each row needs the one above it.**

### Blocking — the difference between a demo and a product

| # | Missing | State | Who |
|---|---|---|---|
| 1 | **Everything proven on real hardware** — mic, camera, TV, phone, PC control, Windows media keys | Needs you | **You**: report what breaks, I fix |
| 2 | **Docker / packaged build never verified** (F1) | Open | Me |
| 3 | **Fast answers by default** — local CPU takes 14–90 s per sentence | Partially open | Me + a cloud key |
| 4 | **Web agent on a real browser** — everything real-world sits behind it (A1) | Logic done, never run live | Me + you watching |
| 5 | **Hindi voice quality** + a trained wake word | Unverified | Me + real recordings |
| 6 | **Identity** — voice ID wired into permissions; face recognition | Not integrated | Me |

### Feature gaps

| # | What a real Jarvis has | State |
|---|---|---|
| 7 | Sees the screen: OCR, click by label, find a file | Built, mocked tests only |
| 8 | Acts on the web: shopping, booking, bills | `web_task` has hard stops (never pays); flows not built |
| 9 | Messages/calls by voice | Built; Twilio account unverified |
| 10 | Phone companion: push, ring, location, notifications | Built; real Android unverified |
| 11 | Long background jobs that report back | Cron runner with persist/cancel/5-min bound; open-ended research **not built** |
| 12 | Gets better from feedback | Feedback recorded and guides replies; **fine-tuning not built** |
| 13 | Smart-home scenes across providers | Engine built; needs hardware verification |
| 14 | Safer by construction: OS sandbox, per-route rate limits, guest roles | Audit chain + confirmations exist; sandbox **not built** |
| 15 | Install, update, backup, restore, CI | Installer done; **updater/rollback and backup/restore not built** |

### Bugs currently open on the live server

| # | Problem | State |
|---|---|---|
| B1 | Telegram `409 Conflict` — a second Atulya is still running on your PC | **Needs you** to stop it |
| B2 | All four enabled MCP servers fail to connect | Open — not yet diagnosed |
| B3 | HTTPS not re-verified after the server rebuild | Open — one `curl` |
| B4 | `kosh/identity.json` missing → default persona | Open |
| B5 | `release.yml` — keep or delete? | **Needs your answer** |
| B6 | DeepSeek key returns 401 | **Needs a working key** |
| B7 | `ROADMAP.md` names `providers_catalog.py`; the real file is `atulya/mastishk/suchi.py`. `adesh.py` says "eleven other providers" — there are eight | Open, docs drift |

---

## 9. AGI: self-improving and evolving

Honest answer: **this is not an AGI and does not pretend to be.** What follows separates what
actually exists from what would have to be built.

### Exists today

| Capability | Where | How it works |
|---|---|---|
| **Learns your facts** | `kosh/agent/profiles/` | Account-scoped preferences and profile facts, fed back into replies |
| **Remembers the conversation** | `kosh/chat_history.json`, `kosh/memory/` | Session search DB + vector memory + a live memory tree in the UI |
| **Feedback loop** | chat UI | Thumbs up/down and "that was wrong"; recent corrections guide later replies |
| **Self-authored triggers** | `kosh/agent/triggers.json` | You say "whenever X, do Y" and it writes the rule |
| **Learns routines** | `kosh/agent/routines.json` | Multi-step plans it can chain and call |
| **Acts on a schedule** | cron runner | Persists status, supports cancel, 5-minute bound, marks interrupted work after restart instead of replaying it |
| **Self-audit** | `kosh/agent/audit.jsonl` | Every tool call the brain made, hash-chained so tampering is visible |
| **Refuses its own unsafe actions** | `atulya/mastishk/` | Safety rules sit **outside** the model — approval, never pay, never order, never delete silently |
| **Picks its own brain** | `atulya/mastishk/vahak.py` | Measures each provider, tries the fastest, falls through on failure |
| **Notices when it is failing** | router | All models down → says so plainly instead of looping |
| **Improves with hardware** | `ATULYA_MAX_TOOL_SCHEMAS` | Fewer tools shown to small models; measured 2,100 → 350 prompt tokens |

### Not built — what "self-improving" would actually require

| # | Missing | Why it is hard | State |
|---|---|---|---|
| G1 | **Automatic model fine-tuning** from your feedback | Needs a training loop, a held-out set, and a guard against learning your mistakes | Not built |
| G2 | **Self-authored tools** — writing its own capability and using it | An LLM that can add code can add bad code. Needs a sandbox, a test gate and your approval | Not built |
| G3 | **Nightly self-review** — "what did I get wrong today, and what rule would fix it?" | Safe version: proposes a trigger or a prompt change, you approve it | Not built |
| G4 | **Memory consolidation** — merging, forgetting, ranking what matters | Vector memory stores; it does not prune or re-rank | Partially |
| G5 | **Measuring its own improvement** | Needs a regression set it runs against on every change | Not built |
| G6 | **Sub-agents / open-ended research** | Long-horizon planning with a budget and a report-back | Not built |
| G7 | **Uncertainty-aware replies** | Knows when it does not know, asks instead of guessing | Partial — some tools confirm |
| G8 | **OS-level sandbox** | The real prerequisite for letting it act on its own | Not built |

### The safe order to build them

| Step | Do | Gate |
|---|---|---|
| 1 | G5 first — a fixed set of questions with known answers | Run it on every commit; nothing merges without it |
| 2 | G3 nightly self-review, **proposal only** | It writes a diff; a human clicks Apply |
| 3 | G4 memory consolidation | Dry-run mode, nothing deleted until you approve |
| 4 | G1 fine-tune from approved feedback | Only corrections you marked "yes, that was right" |
| 5 | G6 sub-agents | Hard token/time budget, audit every call |
| 6 | G2 self-authored tools | G8 must exist first: OS sandbox + G5 test gate + confirm-first |

> **Rule that does not change:** anything that spends money, books, sends, deletes or changes
> its own code **must ask first**. Self-improvement without a sandbox is how assistants go
> wrong — the sandbox is not optional, it is step zero.

---

## 10. Left to build

| # | Item | Owner |
|---|---|---|
| 1 | Stop your PC instance so Telegram replies (B1) | **You** |
| 2 | `release.yml` keep or delete (B5) | **You** |
| 3 | Working DeepSeek key (B6) | **You** |
| 4 | Real-hardware pass — mic, camera, TV, phone | **You** |
| 5 | Diagnose the four failing MCP servers (B2) | Me |
| 6 | Re-verify HTTPS after rebuild (B3) | Me |
| 7 | `install.ps1` one-liner | Me |
| 8 | `frontend/` → `webui/` | Me |
| 9 | Webui reorganise + HUD | Me |
| 10 | Remove `examples/` | Me |
| 11 | `kosh/` → `data/` (deliberately last) | Me |
| 12 | Docs drift: `providers_catalog.py`, "eleven providers" (B7) | Me |
| 13 | Docker build verification (F1) | Me |
| 14 | G5 self-measurement, then G3 self-review | Me, in that order |
