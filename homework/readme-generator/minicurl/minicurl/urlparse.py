"""URL parsing helpers with curl-like defaults and error handling."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit, quote

from .errors import ExitCode, UrlError

DEFAULT_SCHEMES = ("http", "https")
DEFAULT_PORTS = {"http": 80, "https": 443, "ftp": 21}


@dataclass(frozen=True)
class Target:
    """A parsed, normalised URL target."""

    scheme: str
    host: str
    port: int
    path: str
    query: str
    username: str | None = None
    password: str | None = None
    original: str = ""

    @property
    def netloc(self) -> str:
        host = self.host
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        default = DEFAULT_PORTS.get(self.scheme)
        if self.port and self.port != default:
            return f"{host}:{self.port}"
        return host

    @property
    def request_uri(self) -> str:
        path = self.path or "/"
        if self.query:
            return f"{path}?{self.query}"
        return path

    @property
    def url(self) -> str:
        uri = self.request_uri
        return f"{self.scheme}://{self.netloc}{uri}"


def parse_url(raw: str) -> Target:
    if not raw:
        raise UrlError("no URL specified!", ExitCode.MALFORMED_URL)

    candidate = raw
    if "://" not in candidate:
        # curl assumes http:// when the scheme is omitted (for http-like tools).
        candidate = "http://" + candidate

    try:
        parts = urlsplit(candidate)
    except ValueError as exc:  # invalid port, bad ipv6, ...
        raise UrlError(f"malformed URL: {raw}\nurl.c: ({exc})", ExitCode.MALFORMED_URL)

    scheme = (parts.scheme or "").lower()
    if scheme not in DEFAULT_SCHEMES:
        raise UrlError(
            "Protocol {0} not supported or disabled in libcurl".format(scheme or "?"),
            ExitCode.UNSUPPORTED_PROTOCOL,
        )

    host = parts.hostname
    if not host:
        raise UrlError("no host specified!", ExitCode.MALFORMED_URL)

    try:
        port = parts.port or DEFAULT_PORTS[scheme]
    except ValueError:
        raise UrlError(f"port number out of range: {raw}", ExitCode.MALFORMED_URL)

    path = quote(parts.path or "", safe="/%:@!$&'()*+,;=-._~")
    query = parts.query

    # Credentials embedded in the URL: http://user:pass@host/
    username = password = None
    if parts.username:
        username = unquote(parts.username)
        password = unquote(parts.password) if parts.password else None

    return Target(
        scheme=scheme,
        host=host,
        port=port,
        path=path,
        query=query,
        username=username,
        password=password,
        original=raw,
    )


def unquote(value: str) -> str:
    from urllib.parse import unquote as _unquote

    return _unquote(value)


def urljoin(base: Target, location: str) -> Target:
    """Resolve a Location header against the current target."""
    from urllib.parse import urljoin as _urljoin

    return parse_url(_urljoin(base.url, location))
