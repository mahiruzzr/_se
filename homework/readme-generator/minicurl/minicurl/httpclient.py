"""Core HTTP engine built on the standard library (http.client + ssl).

Gives us explicit control over redirects, streaming, timings and TLS which
is what makes a curl-like client interesting to use.
"""

from __future__ import annotations

import http.client
import socket
import ssl
import time
import zlib
from dataclasses import dataclass, field
from typing import Callable, Iterable

from .errors import (
    ConnectError,
    DnsError,
    ProtocolError,
    RedirectError,
    SslError,
    TimeoutError_,
)
from .urlparse import Target, parse_url

ChunkSink = Callable[[bytes], None]

REDIRECT_STATUSES = {301, 302, 303, 307, 308}
CHUNK_SIZE = 64 * 1024

DEFAULT_USER_AGENT = "minicurl/0.1.0 (like curl)"


@dataclass
class Request:
    method: str = "GET"
    url: str = ""
    headers: list[tuple[str, str]] = field(default_factory=list)
    body: bytes | None = None
    timeout: float = 300.0
    connect_timeout: float | None = None
    follow_redirects: bool = False
    max_redirects: int = 50
    insecure: bool = False
    proxy: str | None = None
    auth: tuple[str, str] | None = None
    accept_encoding: str | None = None
    http_version: str = "1.1"  # "1.1" or "1.0"
    decompress: bool = True


@dataclass
class Response:
    status: int
    reason: str
    headers: list[tuple[str, str]]
    url: str                       # effective URL after redirects
    redirects: list[str] = field(default_factory=list)
    timings: dict[str, float] = field(default_factory=dict)
    bytes_downloaded: int = 0
    content_length: int | None = None
    content_type: str | None = None
    remote_ip: str | None = None

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 400

    def header(self, name: str, default: str | None = None) -> str | None:
        for key, value in self.headers:
            if key.lower() == name.lower():
                return value
        return default

    @property
    def all_headers(self) -> str:
        return "".join(f"{k}: {v}\r\n" for k, v in self.headers)


class HttpClient:
    """Single-shot HTTP client with curl-like behaviour."""

    def __init__(self, verbose: Callable[[str], None] | None = None):
        self.verbose = verbose or (lambda _msg: None)

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #
    def run(self, request: Request, sink: ChunkSink | None = None,
            on_response: Callable[[Response], None] | None = None) -> Response:
        """Execute the request, streaming body chunks to `sink` when given.

        `on_response` fires once, right before the final response body is
        pumped - it lets callers act on status/headers (--fail, -i, --max-filesize)
        before any body byte is written.

        Returns the final Response (after redirects).  When redirects are
        followed the body of intermediate responses is discarded.
        """
        target = _parse(request.url)
        seen: list[str] = []
        method = request.method.upper()
        body = request.body
        headers = list(request.headers)
        total_time = time.perf_counter()

        while True:
            response, stream = self._exchange(target, method, body, headers, request)

            if request.follow_redirects and response.status in REDIRECT_STATUSES:
                location = response.header("location")
                if location:
                    # Drain / close the intermediate body.
                    stream.close()
                    if len(seen) >= request.max_redirects:
                        raise RedirectError(
                            "Maximum ({}) redirects followed".format(request.max_redirects)
                        )
                    if response.status in (301, 302, 303) and method not in ("GET", "HEAD"):
                        # curl turns POST into GET on 301/302/303.
                        method, body = "GET", None
                        headers = [
                            (k, v) for k, v in headers
                            if k.lower() not in ("content-length", "content-type",
                                                 "transfer-encoding")
                        ]
                    if response.status == 303 and method != "HEAD":
                        method, body = "GET", None
                    seen.append(target.url)
                    self.verbose(f"< Location: {location}")
                    target = _resolve(target, location)
                    self.verbose(f"* Issue another request to {target.url}")
                    continue
                stream.close()

            if on_response is not None:
                on_response(response)

            downloaded = self._pump(stream, response, sink, request.decompress)
            response.bytes_downloaded = downloaded
            response.url = target.url
            response.redirects = seen
            response.timings["total"] = time.perf_counter() - total_time
            return response

    # ------------------------------------------------------------------ #
    # internals
    # ------------------------------------------------------------------ #
    def _exchange(
        self,
        target: Target,
        method: str,
        body: bytes | None,
        headers: list[tuple[str, str]],
        request: Request,
    ) -> tuple[Response, http.client.HTTPResponse]:
        conn: http.client.HTTPConnection
        start = time.perf_counter()
        timeout = request.connect_timeout or request.timeout

        if target.scheme == "https":
            context = ssl.create_default_context()
            if request.insecure:
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
            conn = http.client.HTTPSConnection(
                target.host, target.port, timeout=request.timeout, context=context
            )
        else:
            conn = http.client.HTTPConnection(target.host, target.port, timeout=request.timeout)

        if request.proxy:
            self._apply_proxy(conn, request.proxy, target)

        if request.http_version == "1.0":
            # http.client speaks HTTP/1.1 by default; tweak the private
            # version markers so the request line says HTTP/1.0.
            conn._http_vsn = 10
            conn._http_vsn_str = "HTTP/1.0"

        try:
            self.verbose(f"*   Trying {target.host}:{target.port}...")
            conn.connect()
        except socket.gaierror as exc:
            raise DnsError(f"Could not resolve host: {target.host}") from exc
        except ssl.SSLError as exc:
            raise SslError(f"SSL connect error: {exc}") from exc
        except socket.timeout as exc:
            raise TimeoutError_(f"Connection timed out after {timeout} seconds") from exc
        except (ConnectionError, OSError, http.client.HTTPException) as exc:
            raise ConnectError(
                f"Failed to connect to {target.host} port {target.port}: {exc}"
            ) from exc

        connected_at = time.perf_counter()
        remote_ip = None
        try:
            remote_ip = conn.sock.getpeername()[0] if conn.sock else None
        except OSError:
            pass

        out_headers = self._build_headers(target, request, headers, body, method)
        self.verbose(f"> {method} {target.request_uri} HTTP/{request.http_version}")
        for key, value in out_headers:
            self.verbose(f"> {key}: {value}")
        self.verbose("> ")

        try:
            conn.request(method, target.request_uri, body=body, headers=dict(_dedupe(out_headers)))
            resp = conn.getresponse()
        except socket.timeout as exc:
            conn.close()
            raise TimeoutError_(f"Operation timed out after {request.timeout} seconds") from exc
        except ssl.SSLError as exc:
            conn.close()
            raise SslError(f"SSL error: {exc}") from exc
        except (ConnectionError, http.client.HTTPException, OSError) as exc:
            conn.close()
            raise ProtocolError(f"Recv failure: {exc}") from exc

        transferred_at = time.perf_counter()
        response_headers = [(k, v) for k, v in resp.getheaders()]

        self.verbose(f"< HTTP/1.1 {resp.status} {resp.reason}" if resp.version == 11
                     else f"< HTTP/1.0 {resp.status} {resp.reason}")
        for key, value in response_headers:
            self.verbose(f"< {key}: {value}")
        self.verbose("< ")

        response = Response(
            status=resp.status,
            reason=resp.reason,
            headers=response_headers,
            url=target.url,
            remote_ip=remote_ip,
            content_length=_content_length(resp, response_headers),
            content_type=resp.getheader("content-type"),
        )
        response.timings["dns"] = 0.0
        response.timings["connect"] = connected_at - start
        response.timings["pretransfer"] = transferred_at - start

        transport = _Transport(conn, resp)
        transport.on_first_byte = lambda: response.timings.setdefault(
            "starttransfer", time.perf_counter() - start
        )
        return response, transport

    @staticmethod
    def _apply_proxy(conn: http.client.HTTPConnection, proxy: str, target: Target) -> None:
        proxy_target = _parse(proxy if "://" in proxy else "http://" + proxy)
        conn.set_tunnel(proxy_target.host, proxy_target.port)
        # For plain HTTP the proxy address becomes the connection endpoint.
        if target.scheme == "http" and isinstance(conn, http.client.HTTPConnection):
            conn.host = proxy_target.host
            conn.port = proxy_target.port

    def _build_headers(
        self,
        target: Target,
        request: Request,
        extra: list[tuple[str, str]],
        body: bytes | None,
        method: str,
    ) -> list[tuple[str, str]]:
        headers: list[tuple[str, str]] = [
            ("Host", target.netloc),
            ("User-Agent", DEFAULT_USER_AGENT),
            ("Accept", "*/*"),
        ]

        user = target.username
        password = target.password
        if request.auth:
            user, password = request.auth

        if user is not None:
            token = _base64(f"{user}:{password or ''}")
            headers.append(("Authorization", f"Basic {token}"))

        if request.accept_encoding:
            headers.append(("Accept-Encoding", request.accept_encoding))

        if body is not None:
            headers.append(("Content-Length", str(len(body))))

        for key, value in extra:
            headers.append((key, value))

        return headers

    @staticmethod
    def _pump(
        stream: "http.client.HTTPResponse | _Transport",
        response: Response,
        sink: ChunkSink | None,
        decompress: bool = True,
    ) -> int:
        decompressor = _MaybeDecompressor(
            response.header("content-encoding", "") or "",
            enabled=bool(sink is not None) and decompress,
        )
        downloaded = 0
        try:
            while True:
                chunk = stream.read(CHUNK_SIZE)
                if not chunk:
                    break
                downloaded += len(chunk)
                if sink is not None:
                    out = decompressor.feed(chunk)
                    if out:
                        sink(out)
            tail = decompressor.flush()
            if sink is not None and tail:
                sink(tail)
        except socket.timeout as exc:
            raise TimeoutError_("Operation timed out") from exc
        except (ConnectionError, http.client.HTTPException, OSError) as exc:
            raise ProtocolError(f"Recv failure: {exc}") from exc
        finally:
            response.timings.setdefault("starttransfer", response.timings.get("pretransfer", 0.0))
            stream.close()
        return downloaded


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
class _Transport:
    """Wraps an http.client response and fires a callback on first byte."""

    def __init__(self, conn: http.client.HTTPConnection, resp: http.client.HTTPResponse):
        self._conn = conn
        self._resp = resp
        self.on_first_byte: Callable[[], None] | None = None
        self._touched = False

    def read(self, size: int) -> bytes:
        data = self._resp.read(size)
        if data and not self._touched:
            self._touched = True
            if self.on_first_byte:
                self.on_first_byte()
        return data

    def close(self) -> None:
        try:
            self._resp.close()
        finally:
            self._conn.close()


class _MaybeDecompressor:
    """Incremental gzip/deflate decoder."""

    def __init__(self, encoding: str, enabled: bool = True):
        self._obj = None
        encoding = encoding.lower().strip()
        if not enabled or not encoding or encoding == "identity":
            return
        try:
            if "gzip" in encoding or "x-gzip" in encoding:
                self._obj = zlib.decompressobj(zlib.MAX_WBITS | 16)
            elif "deflate" in encoding:
                self._obj = zlib.decompressobj()
        except zlib.error:
            self._obj = None

    def feed(self, data: bytes) -> bytes:
        if self._obj is None:
            return data
        try:
            return self._obj.decompress(data)
        except zlib.error:
            return data

    def flush(self) -> bytes:
        if self._obj is None:
            return b""
        try:
            return self._obj.flush()
        except zlib.error:
            return b""


def _base64(value: str) -> str:
    import base64

    return base64.b64encode(value.encode()).decode()


def _parse(raw: str) -> Target:
    return parse_url(raw)


def _resolve(base: Target, location: str) -> Target:
    from .urlparse import urljoin

    return urljoin(base, location)


def _dedupe(headers: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    """http.client wants a mapping; later duplicates of Host must win."""
    merged: dict[str, str] = {}
    for key, value in headers:
        merged[key] = value
    return list(merged.items())


def _content_length(resp: http.client.HTTPResponse, headers: list[tuple[str, str]]) -> int | None:
    raw = resp.getheader("content-length")
    if raw and raw.strip().isdigit():
        return int(raw)
    for key, value in headers:
        if key.lower() == "content-length" and value.strip().isdigit():
            return int(value)
    return None
