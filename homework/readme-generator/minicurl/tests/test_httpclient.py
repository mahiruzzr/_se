"""Behaviour tests for HttpClient against the local server."""

import gzip
import json

import pytest

from minicurl.errors import (
    ConnectError,
    DnsError,
    ExitCode,
    RedirectError,
    TimeoutError_,
    UrlError,
)
from minicurl.httpclient import HttpClient, Request


def _run(url, **kwargs):
    request = Request(url=url, **kwargs)
    chunks: list[bytes] = []
    response = HttpClient().run(request, sink=chunks.append)
    return response, b"".join(chunks)


def test_get_returns_body_and_status(base_url):
    response, body = _run(base_url + "/hello")
    assert response.status == 200
    assert body == b"hello world"
    assert response.ok is True
    assert response.url == base_url + "/hello"
    assert response.redirects == []
    assert response.timings["total"] >= 0


def test_get_without_sink_still_counts_bytes(base_url):
    response = HttpClient().run(Request(url=base_url + "/hello"))
    assert response.status == 200
    assert response.bytes_downloaded == len(b"hello world")


def test_post_echoes_body_and_content_type(base_url):
    response, body = _run(
        base_url + "/echo",
        method="POST",
        headers=[("Content-Type", "text/plain")],
        body=b"a=1&b=2",
    )
    payload = json.loads(body)
    assert payload["method"] == "POST"
    assert payload["body"] == "a=1&b=2"
    assert payload["content_type"] == "text/plain"
    assert payload["content_length"] == "7"


def test_post_without_explicit_method_stays_post(base_url):
    # A body alone must not change the configured method.
    response, body = _run(base_url + "/echo", method="POST", body=b"x")
    assert json.loads(body)["method"] == "POST"


def test_404_body_and_ok_flag(base_url):
    response, body = _run(base_url + "/missing")
    assert response.status == 404
    assert response.ok is False
    assert body == b"not found"


def test_redirect_not_followed_by_default(base_url):
    response, _ = _run(base_url + "/redirect")
    assert response.status == 302
    assert response.redirects == []


def test_redirect_followed_records_chain(base_url):
    response, body = _run(base_url + "/redirect", follow_redirects=True)
    assert response.status == 200
    assert body == b"hello world"
    assert response.redirects == [base_url + "/redirect"]
    assert response.url == base_url + "/hello"


def test_redirect_loop_raises_after_limit(base_url):
    with pytest.raises(RedirectError) as info:
        _run(base_url + "/loop", follow_redirects=True, max_redirects=3)
    assert info.value.code == ExitCode.TOO_MANY_REDIRECTS


def test_slow_response_times_out(base_url):
    with pytest.raises(TimeoutError_) as info:
        _run(base_url + "/slow", timeout=0.5)
    assert info.value.code == ExitCode.TIMEOUT


def test_connection_refused_maps_to_exit_7(monkeypatch):
    # Deterministic: a refused SYN surfaces as ConnectionRefusedError
    # regardless of platform firewall behaviour (RST vs black-hole).
    import http.client

    def _refused(self):
        raise ConnectionRefusedError(10061, "No connection could be made")

    monkeypatch.setattr(http.client.HTTPConnection, "connect", _refused)
    with pytest.raises(ConnectError) as info:
        _run("http://127.0.0.1:9/", timeout=2.0)
    assert info.value.code == ExitCode.CONNECT_FAILED


def test_connect_timeout_reports_seconds(monkeypatch):
    # Regression: the message used to claim milliseconds for a
    # seconds-denominated timeout.
    import http.client
    import socket as socket_module

    def _slow(self):
        raise socket_module.timeout("timed out")

    monkeypatch.setattr(http.client.HTTPConnection, "connect", _slow)
    with pytest.raises(TimeoutError_) as info:
        _run("http://127.0.0.1:9/", timeout=2.0)
    assert info.value.code == ExitCode.TIMEOUT
    assert str(info.value).endswith("seconds")


def test_unresolvable_host_maps_to_exit_6():
    with pytest.raises(DnsError) as info:
        _run("http://no-such-host.invalid/", timeout=3.0)
    assert info.value.code == ExitCode.DNS_NOT_FOUND


def test_malformed_url_rejected_before_connect():
    with pytest.raises(UrlError):
        _run("gopher://example.com/")


def test_basic_auth_header_sent(base_url):
    response, body = _run(base_url + "/auth", auth=("user", "s3cret"))
    assert response.status == 200
    assert json.loads(body)["authorization"] == "Basic dXNlcjpzM2NyZXQ="


def test_custom_request_headers_reach_server(base_url):
    response, body = _run(
        base_url + "/headers", headers=[("X-Test-Header", "abc123")]
    )
    assert response.status == 200
    assert json.loads(body)["X-Test-Header"] == "abc123"


def test_gzip_body_decompressed_for_sink(base_url):
    response, body = _run(base_url + "/gzip")
    assert response.status == 200
    assert body == b"gzip body here"


def test_gzip_bytes_counted_raw(base_url):
    response = HttpClient().run(Request(url=base_url + "/gzip"))
    assert response.bytes_downloaded == len(gzip.compress(b"gzip body here"))


def test_on_response_fires_before_body(base_url):
    seen = []
    request = Request(url=base_url + "/hello")
    response = HttpClient().run(
        request, sink=lambda _: None, on_response=seen.append
    )
    assert len(seen) == 1
    assert seen[0] is response
    assert seen[0].status == 200


def test_request_defaults():
    request = Request()
    assert request.method == "GET"
    assert request.timeout == 300.0
    assert request.follow_redirects is False
    assert request.max_redirects == 50
