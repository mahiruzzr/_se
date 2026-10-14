"""Tests for URL parsing helpers."""

import pytest

from minicurl.errors import ExitCode
from minicurl.urlparse import Target, parse_url, urljoin


def test_bare_host_defaults_to_http():
    target = parse_url("example.com/path?q=1")
    assert target.scheme == "http"
    assert target.host == "example.com"
    assert target.port == 80
    assert target.request_uri == "/path?q=1"


def test_explicit_port_and_userinfo():
    target = parse_url("http://user:pass@example.com:8080/a")
    assert (target.host, target.port) == ("example.com", 8080)
    assert (target.username, target.password) == ("user", "pass")


def test_https_default_port_and_netloc():
    target = parse_url("https://example.com/")
    assert target.port == 443
    assert target.netloc == "example.com"
    assert parse_url("http://example.com:80/").netloc == "example.com"
    assert parse_url("http://example.com:8080/").netloc == "example.com:8080"


def test_missing_scheme_or_host_rejected():
    with pytest.raises(Exception) as info:
        parse_url("")
    assert info.value.code == ExitCode.MALFORMED_URL
    with pytest.raises(Exception):
        parse_url("http://")


def test_unsupported_scheme_exit_code_2():
    with pytest.raises(Exception) as info:
        parse_url("ftp://example.com/file")
    assert info.value.code == ExitCode.UNSUPPORTED_PROTOCOL


def test_bad_port_rejected():
    with pytest.raises(Exception) as info:
        parse_url("http://example.com:99999/")
    assert info.value.code == ExitCode.MALFORMED_URL


def test_ipv6_host():
    target = parse_url("http://[::1]:8000/x")
    assert target.host == "::1"
    assert target.netloc == "[::1]:8000"


def test_urljoin_resolves_relative_location():
    base = parse_url("http://example.com/a/b")
    assert urljoin(base, "/c").request_uri == "/c"
    assert urljoin(base, "http://other.test/z").host == "other.test"


def test_target_url_roundtrip():
    target = parse_url("https://example.com:8443/p?q=2")
    assert target.url == "https://example.com:8443/p?q=2"


def test_dataclass_defaults():
    target = Target(scheme="http", host="h", port=80, path="", query="")
    assert target.request_uri == "/"
    assert target.username is None
