import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import __version__
from . import core


class AtulyaHandler(BaseHTTPRequestHandler):
    server_version = f"AtulyaLaunch/{__version__}"

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            self.send_html(render_dashboard())
            return
        if path == "/api/status":
            self.send_json(core.system_status())
            return
        if path == "/api/sites":
            self.send_json(list(core.site_list().values()))
            return
        if path == "/api/backups":
            self.send_json(list(core.backup_list().values()))
            return
        if path == "/api/security":
            self.send_json(core.security_scan())
            return
        if path == "/api/dashboard":
            self.send_json(core.dashboard_data())
            return
        if path == "/api/audit":
            if not self.authorized():
                self.send_error(HTTPStatus.UNAUTHORIZED, "Missing or invalid bearer token")
                return
            self.send_json(core.audit_list())
            return
        if path == "/api/files":
            if not self.authorized():
                self.send_error(HTTPStatus.UNAUTHORIZED, "Missing or invalid bearer token")
                return
            query = parse_qs(urlparse(self.path).query)
            try:
                self.send_json(
                    core.file_list(
                        query.get("domain", [""])[0],
                        query.get("path", ["."])[0],
                    )
                )
            except ValueError as error:
                self.send_json({"error": str(error)}, status=HTTPStatus.BAD_REQUEST)
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/login":
            payload = self.read_json()
            token = core.login(payload.get("username", ""), payload.get("password", ""))
            if not token:
                self.send_error(HTTPStatus.UNAUTHORIZED, "Invalid username or password")
                return
            self.send_json({"session_token": token})
            return
        if path == "/api/sites":
            if not self.authorized():
                self.send_error(HTTPStatus.UNAUTHORIZED, "Missing or invalid bearer token")
                return
            payload = self.read_json()
            try:
                site = core.site_create(
                    payload.get("domain", ""),
                    web_root=payload.get("web_root"),
                    proxy_pass=payload.get("proxy_pass"),
                    php=bool(payload.get("php")),
                )
            except ValueError as error:
                self.send_json({"error": str(error)}, status=HTTPStatus.BAD_REQUEST)
                return
            self.send_json(site, status=HTTPStatus.CREATED)
            return
        if path == "/api/backups":
            if not self.authorized():
                self.send_error(HTTPStatus.UNAUTHORIZED, "Missing or invalid bearer token")
                return
            payload = self.read_json()
            self.send_json(core.backup_create(payload.get("name")), status=HTTPStatus.CREATED)
            return
        if path == "/api/backups/restore":
            if not self.authorized():
                self.send_error(HTTPStatus.UNAUTHORIZED, "Missing or invalid bearer token")
                return
            payload = self.read_json()
            try:
                self.send_json(core.backup_restore(payload.get("name", "")))
            except ValueError as error:
                self.send_json({"error": str(error)}, status=HTTPStatus.BAD_REQUEST)
            return
        if path == "/api/files/write":
            if not self.authorized():
                self.send_error(HTTPStatus.UNAUTHORIZED, "Missing or invalid bearer token")
                return
            payload = self.read_json()
            try:
                self.send_json(
                    core.file_write(
                        payload.get("domain", ""),
                        payload.get("path", ""),
                        payload.get("content", ""),
                    )
                )
            except ValueError as error:
                self.send_json({"error": str(error)}, status=HTTPStatus.BAD_REQUEST)
            return
        if path == "/api/files/mkdir":
            if not self.authorized():
                self.send_error(HTTPStatus.UNAUTHORIZED, "Missing or invalid bearer token")
                return
            payload = self.read_json()
            try:
                self.send_json(core.file_mkdir(payload.get("domain", ""), payload.get("path", "")))
            except ValueError as error:
                self.send_json({"error": str(error)}, status=HTTPStatus.BAD_REQUEST)
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_DELETE(self):
        path = urlparse(self.path).path
        if path == "/api/files":
            if not self.authorized():
                self.send_error(HTTPStatus.UNAUTHORIZED, "Missing or invalid bearer token")
                return
            query = parse_qs(urlparse(self.path).query)
            try:
                self.send_json(
                    core.file_delete(
                        query.get("domain", [""])[0],
                        query.get("path", [""])[0],
                    )
                )
            except ValueError as error:
                self.send_json({"error": str(error)}, status=HTTPStatus.BAD_REQUEST)
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def authorized(self):
        expected = core.get_api_token()
        header = self.headers.get("Authorization", "")
        if header == f"Bearer {expected}":
            return True
        if header.startswith("Bearer "):
            return core.validate_session(header.removeprefix("Bearer ").strip())
        return False

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        body = self.rfile.read(length).decode("utf-8")
        return json.loads(body)

    def send_json(self, payload, status=HTTPStatus.OK):
        data = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def send_html(self, html):
        data = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        return


def run_server(host="127.0.0.1", port=8080):
    core.panel_init()
    server = ThreadingHTTPServer((host, int(port)), AtulyaHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def render_dashboard():
    data = core.dashboard_data()
    status = data["status"]
    security = data["security"]
    sites = data["sites"]
    backups = data["backups"]
    rows = "\n".join(
        f"<tr><td>{site['domain']}</td><td>{site.get('web_root', '-')}</td><td>{site.get('proxy_pass') or '-'}</td></tr>"
        for site in sites
    ) or "<tr><td colspan='3'>No sites yet. Use the CLI or API to create one.</td></tr>"
    backup_rows = "\n".join(
        f"<tr><td>{backup['name']}</td><td>{backup.get('created_at', '-')}</td><td>{backup.get('size', 0)}</td></tr>"
        for backup in backups
    ) or "<tr><td colspan='3'>No backups yet.</td></tr>"
    issues = "\n".join(
        f"<li><strong>{issue['level']}</strong> {issue['check']}: {issue['message']}</li>"
        for issue in security["issues"]
    ) or "<li>No high-risk local configuration issues found.</li>"
    services = "\n".join(
        f"<span class='pill'>{name}: {state}</span>" for name, state in status["services"].items()
    )
    audit_rows = "\n".join(
        f"<tr><td>{event['time']}</td><td>{event['action']}</td><td>{event['status']}</td></tr>"
        for event in data["audit"]
    ) or "<tr><td colspan='3'>No audit events yet.</td></tr>"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Atulya Launch</title>
  <style>
    body {{ margin: 0; font-family: Segoe UI, Arial, sans-serif; background: #f6f7f9; color: #171a1f; }}
    header {{ background: #101820; color: white; padding: 18px 28px; display: flex; justify-content: space-between; align-items: center; }}
    main {{ padding: 24px; max-width: 1180px; margin: 0 auto; }}
    h1, h2 {{ margin: 0; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; margin: 20px 0; }}
    .card {{ background: white; border: 1px solid #d9dee7; border-radius: 8px; padding: 16px; }}
    .metric {{ font-size: 28px; font-weight: 700; margin-top: 10px; }}
    table {{ width: 100%; border-collapse: collapse; background: white; border: 1px solid #d9dee7; }}
    th, td {{ text-align: left; padding: 10px 12px; border-bottom: 1px solid #edf0f4; }}
    th {{ background: #eef2f6; }}
    .pill {{ display: inline-block; margin: 4px 6px 4px 0; padding: 5px 8px; background: #e8eef4; border-radius: 999px; font-size: 13px; }}
    .muted {{ color: #5b6472; }}
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Atulya Launch</h1>
      <div class="muted">Local hosting panel MVP</div>
    </div>
    <div>Security score: <strong>{security['score']}/100</strong></div>
  </header>
  <main>
    <section class="grid">
      <div class="card"><h2>Sites</h2><div class="metric">{status['sites']}</div></div>
      <div class="card"><h2>Backups</h2><div class="metric">{status['backups']}</div></div>
      <div class="card"><h2>Disk Used</h2><div class="metric">{status['disk']['percent']}%</div></div>
      <div class="card"><h2>CPU Cores</h2><div class="metric">{status['cpu_count']}</div></div>
    </section>
    <section class="card">
      <h2>Services</h2>
      <p>{services}</p>
    </section>
    <section>
      <h2>Sites</h2>
      <table><thead><tr><th>Domain</th><th>Web Root</th><th>Proxy</th></tr></thead><tbody>{rows}</tbody></table>
    </section>
    <section>
      <h2>Backups</h2>
      <table><thead><tr><th>Name</th><th>Created</th><th>Bytes</th></tr></thead><tbody>{backup_rows}</tbody></table>
    </section>
    <section class="card">
      <h2>Security Checks</h2>
      <ul>{issues}</ul>
    </section>
    <section>
      <h2>Audit Log</h2>
      <table><thead><tr><th>Time</th><th>Action</th><th>Status</th></tr></thead><tbody>{audit_rows}</tbody></table>
    </section>
    <p class="muted">Config directory: {status['config_dir']}</p>
  </main>
</body>
</html>"""
