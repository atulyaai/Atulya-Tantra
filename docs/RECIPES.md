# Recipes

Step-by-step tutorials that sit **beside** the production path, not in it.
The production path itself is [DEPLOYMENT.md](DEPLOYMENT.md).

| Recipe | What you get |
|---|---|
| [Run it on an Oracle free VM behind Cloudflare](#run-it-on-an-oracle-free-vm-behind-cloudflare) | A public `https://` Atulya with no open inbound web port |
| [Telegram Mini App](#telegram-mini-app-the-hologram-on-your-phone) | The hologram inside Telegram, no password prompt |
| [Leaked Telegram bot token](#leaked-telegram-bot-token) | Damage containment |
| [Pair a phone with Termux](#pair-a-phone-with-termux) | SMS/notification/location sync, ring the phone |
| [Pair another computer](#pair-another-computer) | A second machine that can act for Atulya |
| [Google Drive and Gmail (MCP + OAuth)](#google-drive-and-gmail-mcp--oauth) | Drive and mailbox access |

---

## Run it on an Oracle free VM behind Cloudflare

This guide targets Oracle Cloud's Always Free eligible compute in your chosen home region. Oracle
capacity and eligibility vary; check the console's displayed cost before creating anything. The
public app is `https://atulya.example.com`. Keep the VM firewall closed to inbound web traffic:
cloudflared makes an outbound tunnel.

> Docker is used throughout this recipe. See the warning at the top of
> [DEPLOYMENT.md](DEPLOYMENT.md): **the image has never been built** (ROADMAP fix F1). Verify the
> image builds locally before you commit a VM to it.

### 1. Create the VM

1. Sign in at [Oracle Cloud](https://cloud.oracle.com/). Open **☰ → Compute → Instances → Create
   instance**. **PASS:** the Create instance page is open.
2. Name it `atulya`; select an Always Free eligible image and shape shown as eligible in your
   account; create an SSH key pair and save the private key somewhere safe. **PASS:** the review
   shows the eligible shape and estimated cost is $0. **FAIL:** stop if the console shows a charge
   or no eligible shape.
3. Click **Create** and wait for **Running**. **PASS:** copy the public IPv4 address and connect
   using the saved SSH key. **FAIL:** resolve any subnet/security-list warning before continuing.
4. In the instance subnet's security list, allow SSH (TCP 22) only from your current public IP. Do
   not add inbound 80/443; the tunnel needs outbound connectivity only. **PASS:** inbound rules
   show SSH restricted to your IP and no public web ports.

### 2. Install Docker

1. Connect over SSH. Run the official Docker Engine install instructions for the VM's Linux image
   from [Docker Engine documentation](https://docs.docker.com/engine/install/). Add your account to
   the Docker group only if you understand that group grants root-equivalent control; otherwise use
   `sudo docker`.
2. Run `docker --version` and `docker compose version`. **PASS:** both print versions. **FAIL:**
   revisit the Docker instructions for the exact image.
3. Clone the repository and enter it: `git clone https://github.com/atulyaai/Atulya-Tantra.git &&
   cd Atulya-Tantra`. **PASS:** `docker-compose.yml` and `Dockerfile` are present.

### 3. Configure secrets and start Atulya

1. Copy `.env.example` to `.env`; edit it on the VM. Set `ATULYA_HOST=0.0.0.0`,
   `ATULYA_HTTPS=off`, `ATULYA_PC_CONTROL=off`, and `ATULYA_PUBLIC_URL=https://atulya.example.com`.
   **Leave `ATULYA_JWT_SECRET_FILE` unset** so Atulya creates its persistent signing key in the
   mounted `data/` directory. Leave Telegram values blank unless you intentionally configure
   Telegram. **PASS:** these names and values are present; no secrets have been pasted into chat
   or committed.
2. Add `CF_TUNNEL_TOKEN=` to `.env`; fill it after creating the tunnel. Protect `.env` with
   `chmod 600 .env`. **PASS:** the tunnel token stays only in `.env` and is not committed.
3. Start only Atulya first: `docker compose up -d --build atulya`. This avoids Compose requiring
   the tunnel token before Cloudflare has issued it. **PASS:** `docker compose ps atulya` shows
   Atulya running. **FAIL:** inspect `docker compose logs atulya` and correct the reported
   configuration.

### 4. Create the Cloudflare Tunnel and DNS

1. Sign in at [Cloudflare Zero Trust](https://one.dash.cloudflare.com/). Open **Networks → Tunnels
   → Create a tunnel**, select **Cloudflared**, name it `atulya-oracle`, and follow the Linux
   connector instructions. **PASS:** the tunnel status is **Healthy** after the connector is
   running.
2. In the tunnel's **Public hostnames** page, add hostname `atulya.example.com`, service type
   **HTTP**, URL `atulya:8501` when using the Compose connector (or `http://127.0.0.1:8501` for the
   systemd/host connector). **PASS:** the hostname appears and the tunnel reports Healthy.
3. Put the tunnel token in `.env` as `CF_TUNNEL_TOKEN=...`, then run `docker compose up -d
   cloudflared`; never paste the token into chat or commit it. Cloudflare's hostname setup creates
   the DNS record. **PASS:** DNS shows the tunnel CNAME and `https://atulya.example.com` reaches
   the app. **FAIL:** check the tunnel connector logs and hostname target.
4. Optional config-file deployment: copy `cloudflared-config.yml.example` to
   `/etc/cloudflared/config.yml`, replace both UUID placeholders, install the credentials JSON at
   the shown path, and run `cloudflared tunnel run <UUID>`. Do not run this host-based alternative
   alongside the Compose connector for the same tunnel.

### 5. Require Cloudflare Access login

1. In Zero Trust, open **Access → Applications → Add an application → Self-hosted**. Set the
   application domain to `atulya.example.com`. **PASS:** the application is listed.
2. Add an **Allow** policy with **Include → Emails →** only the owner's email address. Do not use a
   broad email-domain rule. **PASS:** only that exact email appears in the Include rule.
3. Add exact path policies before the catch-all: `/api/pairing/enroll`, `/api/phone/*`, and
   `/agent/*` use **Bypass** because phone and computer companions cannot complete an interactive
   Access login. The app still checks paired device tokens. Do not bypass any wider path. Set
   Cloudflare rate limits on these paths (for example, 10 requests/minute per source IP with a
   temporary block); tune after normal use. Then apply the email-only **Allow** policy to
   everything else. **PASS:** a private browser is redirected to Access for `/`; only those exact
   device paths reach the origin without Access. **FAIL:** if any other path opens without login,
   disable the Access application until its policy is corrected.
4. Verify enrollment, phone sync, and `/agent/` only with paired device tokens. **PASS:** requests
   without a token fail; a valid paired token reaches only its device-specific routes. Cloudflare
   Bypass is safe only because the app checks device tokens and Cloudflare rate limits the paths.
5. Rate-limit `/api/pairing/enroll` separately (for example, 10 attempts/minute/source IP) and use
   a higher limit for the polling/sync paths (for example, 60 requests/minute/source IP) so an
   opted-in phone syncing three categories every 15 seconds is not blocked. **PASS:** normal
   polling continues while bursts are capped. **FAIL:** tune the limit without removing the rate
   rule.

### 6. Systemd alternative

Use this instead of Compose's restart policy only if you prefer systemd to manage the Compose
stack. Copy the repository to `/opt/atulya`, create `/etc/systemd/system/server.service` from
`server.service` in the repository root, and verify its `WorkingDirectory` and Docker path. Run
`sudo systemctl daemon-reload && sudo systemctl enable --now server`. **PASS:** `sudo systemctl
status server` says active (exited), and `docker compose ps` shows both services running. Do not
configure both systemd and Compose restart management.

---

## Telegram Mini App (the hologram on your phone)

The Mini App is this same dashboard opened inside Telegram: the hologram fills the screen, the menu
is a tap away, and the account that signs you in comes from Telegram instead of a password.

### What it needs

1. A **public HTTPS address**. Telegram only loads `https://` URLs it can reach from its own
   servers, so `http://127.0.0.1:8501` will never work as a Mini App URL — a Cloudflare or
   Tailscale tunnel is enough. **PASS:** the address opens in an ordinary phone browser before you
   involve Telegram at all.
2. `ATULYA_TELEGRAM_BOT_TOKEN` and `ATULYA_TELEGRAM_ALLOWLIST` in `.env` (the installer asks for
   both; the allowlist is a comma-separated list of numeric Telegram user ids, and
   `atulya doctor` fails while it is empty). An **empty allowlist admits nobody** — deliberately,
   because this endpoint hands out sessions.
3. `ATULYA_PUBLIC_URL` set to that same public HTTPS origin (the installer prompts for it, or add
   it to `.env` yourself). It is what the Mini App and the bot menu button point at.

### Extra bot accounts (Bot Management Mode)

For the hologram Mini App you only need the one bot above. If you want **additional** bot
accounts:

1. Enable **Bot Management Mode** for the main bot in the @BotFather Mini App, once.
2. Send `/newbot` to Atulya and tap **Create an Atulya bot**. Telegram creates the managed bot;
   Atulya stores its token in the local `.env`, restricts it to the creating Telegram account, and
   starts it automatically.
3. `/deletebot` lists bots. `/removebot ID`, then `/removebot ID confirm`, disconnects and revokes
   one. Permanently deleting the Telegram account still requires confirmation in @BotFather.

Other channels (WhatsApp, Discord, Slack …) need the account's own credentials, OAuth consent or
device pairing. Atulya cannot bypass those provider-controlled steps.

### Register it with BotFather

1. Open **@BotFather** in Telegram and send `/newapp`, then choose your bot, a title, and a short
   name.
2. When asked for the URL, give the public HTTPS address from step 1. **PASS:** BotFather replies
   with an app link; opening it from inside Telegram lands on the hologram with no password
   prompt.

### What stops an imposter

Telegram signs the page's `initData` with the bot's token as it opens.
`POST /api/miniapp/session` re-computes that signature, refuses anything **stale** (a captured link
must stop working rather than become a key), refuses anyone **off the allowlist**, and answers with
a **one-hour** JWT. Possessing a signature is not enough on its own: it has to name an account that
was already allowed to operate Atulya through chat, which is exactly what
`ATULYA_TELEGRAM_ALLOWLIST` governs everywhere else.

- **PASS:** the app opens straight into the hologram and the dashboard menu works.
- **FAIL:** `503` means no bot token is configured; `401` means the signature did not check out
  (most often a bot token in `.env` that is not the one the app was registered with, or a page
  opened outside Telegram); `403` means the account is not on `ATULYA_TELEGRAM_ALLOWLIST`.

### Behind Cloudflare Access

Cloudflare Access cannot complete an interactive login inside a Telegram webview, and it would
bounce the page away before the page could sign itself in. Give the Mini App its **own hostname**
(for example `hologram.example.com`) with no Access application on it, and keep the main hostname
behind Access. What that hostname exposes is precisely what an allowlisted Telegram user can
already do through chat — but that is not nothing, so keep the allowlist to the accounts you
actually use. `ATULYA_REQUIRE_LOGIN=on` does not affect this endpoint: it only disables the
passwordless sign-in used by browsers and by the phone app.

---

## Leaked Telegram bot token

> **Revoke it immediately:** open Telegram and message **@BotFather**, send `/revoke`, choose the
> affected bot, and follow the prompts. Put the newly issued token only in the server's `.env` and
> restart the service. A leaked token must be treated as compromised even if it was only pasted
> into a private conversation.

---

## Pair a phone with Termux

This companion can read private SMS, notification text, and location. Leave each sync switch off
unless you intentionally want that category shared with your Atulya server. A paired token can be
disconnected in the app at any time.

For background browser notifications, install the optional `push` extra (the Docker image includes
it), set a VAPID public key, private key, and `mailto:` subject in the server environment, and
restart Atulya. Never share or commit the private key. If these values are absent, foreground
WebSocket alerts continue and the app says background delivery is not configured.

1. On Android, install **Termux** and **Termux:API** from the same source. The official Termux
   installation guide lists supported sources; do not mix APK sources because the add-on
   signatures must match. **PASS:** both apps install and open.
   [Official Termux installation guide](https://github.com/termux/termux-app#installation)
2. In Atulya, open **Menu → Action engine → Paired phones and computers → Pair a phone**. Keep the
   six-digit code private and use it within ten minutes. **PASS:** the code and expiry appear on
   screen.
3. Open Termux and type `pkg update -y && pkg install -y termux-api jq curl`. When Android asks,
   allow only the permissions for the features you intend to use. For notifications, open Android
   **Settings → Apps → Special app access → Notification access**, select **Termux:API**, and
   enable access. **PASS:** `termux-sms-list -l 1`, `termux-notification-list`, and
   `termux-location -p network -r once` return data for permitted categories. **FAIL:** reopen the
   Android permission page and check Termux:API is installed from the same source as Termux.
4. Download the helper: `curl -fsSL
   https://raw.githubusercontent.com/atulyaai/Atulya-Tantra/main/examples/termux_phone.sh -o
   termux_phone.sh`. **PASS:** `test -s termux_phone.sh` succeeds.
5. In the same Termux window, type `export ATULYA_SERVER=https://atulya.example.com` (or your
   local server address), then `export ATULYA_PAIR_CODE=000000` with the code shown by Atulya,
   then `export ATULYA_SYNC_SMS=off ATULYA_SYNC_NOTIFICATIONS=off ATULYA_SYNC_LOCATION=off`, then
   `bash termux_phone.sh`. The helper securely stores the paired token in Termux's private home
   folder. **PASS:** it says the companion is connected, and the phone appears under Paired phones
   and computers. **FAIL:** check that the code has not expired and that
   `/api/pairing/enroll` is reachable.
6. To enable a data category, stop the helper with Ctrl+C, set only the relevant flag to `on` (for
   example `export ATULYA_SYNC_NOTIFICATIONS=on`), and run it again. To verify a ring request,
   select the paired phone in Atulya and request **ring**; keep the app open and confirm the phone
   vibrates. **PASS:** the phone inbox receives only enabled categories and the phone responds to a
   queued command. **FAIL:** turn the category back off and check Android permissions and network
   access.
7. To stop sharing, turn the flags off and stop the helper. To revoke access, open **Paired phones
   and computers → Disconnect** next to that phone. **PASS:** the device disappears from active
   pairings and its old token no longer works.

---

## Pair another computer

1. On the computer running Atulya, open **Menu → Action engine → Paired phones and computers →
   Pair another computer**. Keep the six-digit code private. **PASS:** an unexpired code is
   visible.
2. On the computer to pair, clone the project, install its Python dependencies with `python -m
   pip install -e .`, and run `python -m atulya.companion --server https://atulya.example.com --name "My
   laptop"`. Enter the pairing code when prompted. **PASS:** the companion confirms it paired and
   saves its device token in the current user's private config folder; the token is never shown in
   the command line.
3. Leave the command running while you use Atulya. **PASS:** the computer appears in the
   paired-device list as recently seen. Ask Atulya to check that computer; approve the action when
   asked, then ask "show the latest computer results." **FAIL:** verify its name, network access,
   and that its pairing has not been disconnected.
4. To disconnect, open the paired-device list and click **Disconnect** for that computer.
   **PASS:** future tasks are rejected. The paired agent uses the same allowed-folder and command
   rules as local control; it is not an unrestricted remote shell.

---

## Google Drive and Gmail (MCP + OAuth)

> **Simpler option:** Atulya has built-in Google sign-in for Gmail and Calendar. In the web UI open
> **About you → Google account**: an admin pastes an OAuth client ID and secret once (the page
> shows the redirect URI to register), then each user clicks **Connect Google**. The MCP servers
> below are only needed for Google Drive or other MCP clients.

Both servers ship **disabled**. Enable them only after the local credentials below exist in `.env`.
**Never commit `.env` or downloaded Google credential JSON files.**

### Google Drive

Drive uses the free service-account path, which is simpler than user OAuth for a server process.

1. Open Google Cloud Console.
2. Create or select a project.
3. Enable the Google Drive API.
4. Create a service account.
5. Create a JSON key for that service account.
6. Share the Drive files or folders Atulya may access with the service-account email.
7. Put the minified JSON into `.env`:

```env
GOOGLE_SERVICE_ACCOUNT_KEY={"type":"service_account","project_id":"..."}
```

8. Set `google_drive.enabled` to `true` in `atulya/mcp_servers.json`.

### Gmail

Gmail uses OAuth because it acts on a real mailbox.

1. Open Google Cloud Console.
2. Create or select a project.
3. Enable the Gmail API.
4. Configure the OAuth consent screen.
5. Create an OAuth client.
6. Add this local redirect URI:

```text
http://localhost:3000/callback
```

7. Put the client values into `.env`:

```env
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GMAIL_OAUTH_PORT=3000
```

8. Generate the refresh token:

```powershell
npm.cmd install mcp-gmail
node install/generate_gmail_refresh_token.mjs
```

9. Copy only the printed `GMAIL_REFRESH_TOKEN=...` line into `.env`.
10. There is no `gmail` entry to flip: Gmail is a built-in tool (`send_email`, `fetch_emails` in
    `atulya/actions/email.py`), not an MCP server.

### Verify

```powershell
python -m atulya.cli readiness
```

If either Google server is enabled without credentials, readiness reports `production-candidate`
and shows the missing env var. When both enabled servers have their credentials, the dashboard
startup can connect them through the MCP client manager.
