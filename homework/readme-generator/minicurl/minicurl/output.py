"""--write-out formatting and assorted output helpers."""

from __future__ import annotations

import json
import re
from typing import Any

from .httpclient import Response

_VAR_RE = re.compile(r"%\{([a-zA-Z0-9_]+)\}")
_ESCAPE_RE = re.compile(r"\\[nrtfv]")


def variables(response: Response | None) -> dict[str, Any]:
    if response is None:
        return {}
    total = response.timings.get("total", 0.0)
    return {
        "http_code": response.status,
        "response_code": response.status,
        "url_effective": response.url,
        "content_type": response.content_type or "",
        "size_download": response.bytes_downloaded,
        "size_header": len(response.all_headers.encode()),
        "num_redirects": len(response.redirects),
        "speed_download": int(response.bytes_downloaded / total) if total > 0 else 0,
        "time_total": total,
        "time_connect": response.timings.get("connect", 0.0),
        "time_pretransfer": response.timings.get("pretransfer", 0.0),
        "time_starttransfer": response.timings.get("starttransfer", 0.0),
        "remote_ip": response.remote_ip or "",
        "scheme": response.url.split("://", 1)[0] if "://" in response.url else "",
        "exitcode": 0,
        "header_json": json.dumps(
            [{"name": k, "value": v} for k, v in response.headers], separators=(",", ":")
        ),
    }


def render(template: str, response: Response | None) -> str:
    """Render a curl-style --write-out template."""
    available = variables(response)

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in available:
            return match.group(0)
        value = available[name]
        if isinstance(value, float):
            return f"{value:.6f}"
        return str(value)

    rendered = _VAR_RE.sub(replace, template)
    return _ESCAPE_RE.sub(_unescape, rendered)


def _unescape(match: re.Match[str]) -> str:
    return {
        "\\n": "\n",
        "\\r": "\r",
        "\\t": "\t",
        "\\f": "\f",
        "\\v": "\v",
    }[match.group(0)]


def format_status_line(response: Response) -> str:
    return f"HTTP/1.1 {response.status} {response.reason}\r\n"


def remote_filename(url: str) -> str:
    """Derive a local file name for -O, like curl does."""
    from urllib.parse import unquote, urlsplit

    path = urlsplit(url).path
    name = unquote(path.rstrip("/").rsplit("/", 1)[-1]) if path else ""
    return name or "index.html"
