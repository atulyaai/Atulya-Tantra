# Remote access setup

Atulya supports a reverse-proxy deployment while keeping the Python app bound to loopback. It does **not** create a public server, DNS name, TLS certificate, firewall rule, or private-network account for you. Those depend on your hosting/network provider.

## Temporary home-computer hosting

A home laptop or desktop can act as Atulya's server while it is powered on, awake, connected to the internet, and running both Atulya and the remote-access connector. Its local models and databases remain on that computer. Closing the lid, sleep, a reboot, home internet outage, or a provider outage makes Atulya unavailable. Keep the app on loopback and make the connector the only network path to it.

## Which machine/network setup fits?

| What you have | How Atulya runs | Safe access path | Readiness |
| --- | --- | --- | --- |
| One personal laptop/desktop, no server | Treat that PC as the host; keep the app, models, and databases there | Same PC: `localhost`; own devices away from home: private Tailscale Serve | Windows logon hosting is installed and health-checked on this PC; private tunnel hookup and cross-device verification remain |
| Home LAN/private network | One always-on PC or mini-PC hosts Atulya; other home devices are clients | Private overlay HTTPS (preferred); LAN-only access would need a trusted local TLS proxy and host firewall rules | Avoid direct router port forwarding |
| One rented/cloud server | A single Linux/Windows host runs Atulya and persistent data | Domain DNS + Caddy/another TLS proxy, with app port private | Documented pattern; actual deployment unverified |
| Several private servers/devices | One designated Atulya host, other machines connect over VPN/tailnet | Private overlay network and restricted ACLs | Use a single active app/data writer until cluster support is complete |
| Multiple app servers / cluster | Load balancer sends requests to interchangeable app replicas; shared database, sessions, jobs, and file/model storage | Internal network plus external TLS proxy/WAF | **Not supported yet**; SQLite, local model processes, and in-process polling need redesign first |
| Temporary public demo | Atulya stays on the PC; short-lived tunnel gives an ephemeral HTTPS URL | Cloudflare Quick Tunnel | Development/demo only; public URL, no uptime guarantee, and changing RP/passkey origin |

## Free/open-source and paid options

| Goal | Free/low-cost path | What it depends on |
| --- | --- | --- |
| Use Atulya only on this PC | Run the local app at `http://localhost:8501` | No server, DNS, or tunnel; only works on this PC |
| Use it from your own phone/laptop across networks | Tailscale Serve over private HTTPS | Tailscale client on each device, tailnet account/consent, and HTTPS enabled; the client has open-source components, while the control service is hosted. Atulya still needs automatic origin/route integration |
| Demo from anywhere without a domain | Cloudflare Quick Tunnel | Free/open-source `cloudflared` client and hosted Cloudflare tunnel; temporary random URL, service availability not guaranteed, and public reachability |
| Fully self-hosted private mesh | Headscale control server with compatible clients | A public/reachable control-server host and DNS; Headscale is open source, but it still needs somewhere to run and does not provide the relay/server hardware by itself. See [Headscale](https://headscale.net/).
| Stable public URL without a paid DNS domain | Free dynamic DNS provider + Caddy TLS | Home router must accept inbound connections and support port forwarding; CGNAT or ISP filtering can make this impossible. Opening ports needs deliberate firewall/security configuration.
| Self-hosted tunnel without a third-party tunnel service | An open-source tunnel such as `frp` or `rathole` | Requires a reachable public VPS/server; the tunnel software can be free while the server/network may not be.
| Paid/managed hosting | Keep an existing VPS/domain, or use a paid managed tunnel/server | More stable support and capacity; retain Atulya authentication, TLS, backups, and ownership checks.

“Free software”, “free service”, and “free server hardware” are different. A tunnel may eliminate domain fees while still relying on a hosted provider; fully self-hosting still needs a reachable computer somewhere. If the user already pays for a server, domain, VPN, or cloud service, Atulya should detect/configure that option instead of forcing a new provider.

You do not need to own a separate server to start. Your PC is the server while Atulya runs there; your phone or another computer is a client. When the PC sleeps, shuts down, loses internet, or is away from power, remote access stops. On a laptop, keep-awake should apply only while plugged in so hosting does not silently drain the battery.

## Cluster prerequisites

Atulya is not cluster-ready. Before running more than one app replica, move SQLite-backed user/session/conversation/calendar/reminder state to a shared transactional database; move reminder delivery, Telegram polling, and other background jobs into one elected/leased worker or durable queue; store uploaded and model assets on shared/object storage or a deliberate model service; make request rate limits and setup challenges shared; add health/readiness and graceful shutdown; then test replica restarts, database failover, duplicate job delivery, rolling upgrades, and restore/rollback. Kubernetes can replace failed stateless pods through Deployments, but it cannot make Atulya's current local SQLite files or in-process workers shared automatically. See [Kubernetes workload controllers](https://kubernetes.io/docs/concepts/workloads/controllers/) and [Docker Compose production guidance](https://docs.docker.com/compose/how-tos/production/).

### Recommended for your own devices: private Tailscale Serve

Tailscale Serve makes a local service available over HTTPS to devices on your private tailnet; access rules still apply. It uses a tailnet DNS name and requires Tailscale on the host and each client device, an account, and HTTPS enabled for that tailnet. After installing/signing in on the home computer and client devices, start Atulya locally, configure Serve to proxy port 8501, and set `ATULYA_PUBLIC_ORIGIN` to the HTTPS tailnet URL that Serve reports. Because the URL is stable for the device, its passkey origin can persist across restarts. See [Tailscale Serve](https://tailscale.com/docs/features/tailscale-serve) and [HTTPS certificates](https://tailscale.com/docs/how-to/set-up-https-certificates).

This is the preferred temporary setup for a personal assistant: it is reachable from your devices across networks without opening the Atulya port to the public internet. Account login, installing Tailscale, and enabling tailnet HTTPS are user setup steps; Atulya cannot silently create or consent to a tailnet.

### Temporary public demo: Cloudflare Quick Tunnel

Cloudflare Quick Tunnels provide a random `trycloudflare.com` HTTPS URL without an account or custom domain, but Cloudflare documents them for testing/development and says they have no uptime guarantee. Anyone with the URL can reach the service unless an access restriction is added; stopping the process ends the URL. Each new URL changes the WebAuthn origin, so passkeys enrolled on a previous random hostname will not work at the new one. Use only synthetic/non-sensitive data, keep the setup-token gate on, and do not treat this as an always-available server. See [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).

Atulya does not yet have a supervised launcher that discovers a new temporary URL, configures the public origin, starts both processes, reports the URL safely, and handles restart/cleanup. That automation is tracked in the TODO; do not rely on a temporary public tunnel for routine access.

### Home host operating checklist

- Connect the computer to reliable power and network; disable sleep while serving, and configure restart after OS updates/reboots.
- Run Atulya under a dedicated non-admin OS account where possible; keep Windows Firewall/router access limited to the tunnel or private overlay.
- Keep `ATULYA_HOST=127.0.0.1`; never port-forward 8501 directly.
- Put `data/` and `models/` on persistent storage; back up `data/` before updates and before migrating to the permanent server.
- Monitor core API, model, storage, tunnel, and messaging-channel health separately. A recovered model must not hide a disconnected tunnel or a stopped Telegram poller.
- Use exponential backoff and bounded retries for recoverable network failures; avoid tight restart loops, duplicate polling processes, and duplicate reminder deliveries.
- Expect home upload bandwidth and local CPU/GPU/RAM to limit image, speech, and model work when using several devices at once.

## Requirements

- A server that stays online and a DNS name pointing to it.
- Inbound TCP 80 and 443 available to a TLS reverse proxy (or an equivalent private-network HTTPS endpoint).
- A reverse proxy on the same host, with its upstream restricted to `127.0.0.1:8501`.
- A random first-admin setup token of at least 32 characters, removed after enrollment.

## Same-host Caddy example

Replace `jarvis.example.com` with your DNS name in both the environment and Caddy configuration. Caddy obtains and renews HTTPS certificates when DNS and inbound reachability are configured.

```caddyfile
jarvis.example.com {
    reverse_proxy 127.0.0.1:8501
}
```

Configure the app environment:

```dotenv
ATULYA_HOST=127.0.0.1
ATULYA_PORT=8501
ATULYA_PUBLIC_ORIGIN=https://jarvis.example.com
ATULYA_TRUSTED_PROXY_IPS=127.0.0.1,::1
ATULYA_ADMIN_SETUP_TOKEN=<random-secret-at-least-32-characters>
```

Start the app and Caddy on the host. Do not expose port 8501 to the internet. First passkey registration on a non-local origin requires the setup token in the Atulya sign-in panel; after creating the administrator passkey, remove the token from configuration and restart the app. The token does not replace the passkey and cannot log in after first enrollment.

## Verification checklist

- `atulya doctor` reports the configuration without printing any secrets.
- `https://jarvis.example.com/api/health` responds through the proxy.
- `/api/auth/status` reports remote setup state but no token value.
- First-admin registration is rejected without the token and starts with the correct public RP ID when the token is supplied.
- Passkey sign-in works from a second device/browser over HTTPS.
- A forged Host, wrong origin, untrusted forwarded-proto header, or direct internet connection to port 8501 is rejected/unreachable.

Atulya currently has one administrator account; private records are scoped to the authenticated principal, and Telegram records use a separate sender identity. Additional account provisioning and linking Telegram or future channels to human accounts remain open work. This recipe is suitable only for the current trusted administrator behind a correctly configured TLS proxy; independent remote deployment verification remains open.
