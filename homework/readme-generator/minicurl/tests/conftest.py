"""Shared fixtures: in-process local HTTP server (no external network)."""

from __future__ import annotations

import gzip
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs

import pytest


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, code: int, body: bytes, ctype: str = "text/plain",
              extra: dict[str, str] | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self):
        parts = urlsplit(self.path)
        path = parts.path
        query = parse_qs(parts.query)
        if path == "/hello":
            self._send(200, b"hello world")
        elif path == "/headers":
            dumped = json.dumps(dict(self.headers)).encode()
            self._send(200, dumped, "application/json")
        elif path == "/redirect":
            self._send(302, b"", extra={"Location": "/hello"})
        elif path == "/loop":
            self._send(302, b"", extra={"Location": "/loop"})
        elif path == "/slow":
            time.sleep(5)
            self._send(200, b"slow done")
        elif path == "/status":
            code = int(query.get("code", ["200"])[0])
            self._send(code, f"status {code}".encode())
        elif path == "/gzip":
            payload = gzip.compress(b"gzip body here")
            self._send(200, payload, extra={"Content-Encoding": "gzip"})
        elif path == "/auth":
            self._send(200, json.dumps(
                {"authorization": self.headers.get("Authorization")}
            ).encode(), "application/json")
        else:
            self._send(404, b"not found")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        parts = urlsplit(self.path)
        if parts.path == "/echo":
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = repr(raw)
            payload = {
                "method": "POST",
                "body": text,
                "content_type": self.headers.get("Content-Type"),
                "content_length": self.headers.get("Content-Length"),
                "x_cli": self.headers.get("X-Cli"),
            }
            self._send(200, json.dumps(payload).encode(), "application/json")
        elif parts.path == "/upload":
            payload = {
                "method": "POST",
                "bytes": len(raw),
                "content_type": self.headers.get("Content-Type"),
            }
            self._send(200, json.dumps(payload).encode(), "application/json")
        else:
            self._send(404, b"not found")

    def log_message(self, *args):
        pass


@pytest.fixture(scope="session")
def base_url():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join()
