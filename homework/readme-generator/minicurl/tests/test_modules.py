"""Unit tests for errors, multipart, output and progress helpers."""

import io

import pytest

from minicurl import __version__
from minicurl.errors import (
    CurlError,
    DnsError,
    ExitCode,
    HttpStatusError,
    TimeoutError_,
    UrlError,
)
from minicurl.httpclient import Response
from minicurl.multipart import encode_multipart, parse_form_args
from minicurl.output import format_status_line, remote_filename, render
from minicurl.progress import ProgressMeter, _eta, _hsize


def test_version_present():
    assert isinstance(__version__, str) and __version__


def test_error_codes_match_curl_conventions():
    assert ExitCode.OK == 0
    assert ExitCode.MALFORMED_URL == 3
    assert ExitCode.TIMEOUT == 28
    assert UrlError("x").code == ExitCode.MALFORMED_URL
    assert DnsError("x").code == ExitCode.DNS_NOT_FOUND
    assert TimeoutError_("x").code == ExitCode.TIMEOUT
    assert HttpStatusError("x").code == ExitCode.HTTP_ERROR
    err = CurlError("boom", 7)
    assert (err.code, str(err)) == (7, "boom")


def test_parse_form_text_and_file_fields(tmp_path):
    target = tmp_path / "note.txt"
    target.write_bytes(b"file-bytes")
    fields = parse_form_args(["msg=hi", f"doc=@{target};type=text/plain"])
    assert fields[0].is_file is False
    assert (fields[0].name, fields[0].value) == ("msg", "hi")
    assert fields[1].is_file is True
    assert fields[1].content_type == "text/plain"
    with pytest.raises(ValueError):
        parse_form_args(["noequals"])
    with pytest.raises(ValueError):
        parse_form_args(["=value"])


def test_encode_multipart_roundtrip(tmp_path):
    target = tmp_path / "a.bin"
    target.write_bytes(b"\x00\x01\x02")
    fields = parse_form_args(["k=v", f"f=@{target}"])
    body, content_type = encode_multipart(fields)
    boundary = content_type.split("boundary=")[1]
    assert body.startswith(f"--{boundary}\r\n".encode())
    assert body.endswith(f"--{boundary}--\r\n".encode())
    assert b'name="k"' in body
    assert b"\r\n\r\nv\r\n" in body and b"\x00\x01\x02" in body
    with pytest.raises(ValueError):
        encode_multipart(parse_form_args(["f=@/no/such/file-xyz"]))


def _response(**overrides):
    base = dict(
        status=200,
        reason="OK",
        headers=[("Content-Type", "text/plain")],
        url="http://example.com/x",
        timings={"total": 2.0, "connect": 0.1,
                 "pretransfer": 0.2, "starttransfer": 0.5},
        bytes_downloaded=100,
        remote_ip="127.0.0.1",
    )
    base.update(overrides)
    return Response(**base)


def test_write_out_render_basic():
    out = render("code=%{http_code} time=%{time_total}\\n", _response())
    assert out == "code=200 time=2.000000\n"


def test_write_out_unknown_vars_kept():
    assert render("%{nope}", _response()) == "%{nope}"
    assert render("x", None) == "x"


def test_format_status_line_and_remote_filename():
    assert format_status_line(_response()) == "HTTP/1.1 200 OK\r\n"
    assert remote_filename("http://h/dir/file.txt") == "file.txt"
    # Verified against real curl 8.21.0: -O on a trailing-slash URL
    # saves the last path segment ("dir"), not "index.html".
    assert remote_filename("http://h/dir/") == "dir"
    assert remote_filename("http://h/%E4%B8%AD.txt") == "中.txt"


def test_hsize_and_eta():
    assert _hsize(0) == "0B"
    assert _hsize(1023) == "1023B"
    assert _hsize(2048) == "2.0K"
    assert _eta(100, 0, 1.0) == "--:--"
    assert _eta(100, 50, 10.0) == "00:10"


def test_progress_meter_disabled_writes_nothing():
    stream = io.StringIO()
    meter = ProgressMeter(enabled=False, stream=stream)
    meter.update(100)
    meter.finish()
    assert stream.getvalue() == ""


def test_progress_meter_finish_clears_line():
    stream = io.StringIO()
    meter = ProgressMeter(enabled=True, total=10, stream=stream)
    meter._last_render = 0.0
    meter.update(10)
    meter.finish()
    assert "\r" in stream.getvalue()
