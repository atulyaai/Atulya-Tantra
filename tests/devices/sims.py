"""Simulated devices that speak the real protocols over real sockets, so drivers are tested end to end.

Each simulator records every request it receives. They are written from the public protocol descriptions
(Roku ECP, Tasmota commands, WLED JSON API, Kodi JSON-RPC, Shelly gen-1 HTTP), not captured from real hardware.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote


class Sim:
    """A tiny HTTP server on a free loopback port. ``routes`` maps (method, path-prefix) -> (status, body)."""

    def __init__(self, routes=None):
        self.requests: list[dict] = []
        self.routes = routes or {}
        sim = self

        class Handler(BaseHTTPRequestHandler):
            def _serve(self):
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length).decode() if length else ""
                try:
                    body = json.loads(raw) if raw else None
                except json.JSONDecodeError:
                    body = raw
                sim.requests.append({"method": self.command, "path": self.path, "json": body, "headers": dict(self.headers)})
                status, text = 404, "not found"
                for (method, prefix), (st, out) in sorted(sim.routes.items(), key=lambda kv: -len(kv[0][1])):
                    if method == self.command and unquote(self.path).startswith(unquote(prefix)):
                        status, text = st, out() if callable(out) else out
                        break
                data = text.encode()
                self.send_response(status)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            do_GET = do_POST = do_PUT = do_DELETE = _serve

            def log_message(self, *a):  # silence
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()


def roku():
    info = "<device-info><model-name>Roku Ultra</model-name><friendly-device-name>Living room</friendly-device-name></device-info>"
    return Sim({("GET", "/query/device-info"): (200, info), ("POST", "/keypress/"): (200, ""), ("POST", "/launch/"): (200, "")})


def tasmota():
    return Sim({("GET", "/cm?cmnd=Status"): (200, '{"Status":{"Module":1,"FriendlyName":["Lamp"]},"StatusNET":{"IPAddress":"x"}}'),
                ("GET", "/cm?cmnd="): (200, '{"POWER":"ON"}')})


def wled():
    return Sim({("GET", "/json/info"): (200, '{"ver":"0.14","brand":"WLED","name":"Strip"}'), ("POST", "/json/state"): (200, '{"success":true}'),
                ("GET", "/json/state"): (200, '{"on":true,"bri":128}')})


def kodi():
    return Sim({("GET", "/jsonrpc"): (200, '{"id":1,"jsonrpc":"2.0","result":{"version":{"major":12}}}'),
                ("POST", "/jsonrpc"): (200, '{"id":1,"jsonrpc":"2.0","result":"OK"}')})


def shelly():
    return Sim({("GET", "/shelly"): (200, '{"type":"SHSW-1","mac":"AABBCC"}'), ("GET", "/relay/0"): (200, '{"ison":true}')})
