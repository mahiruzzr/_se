"""End-to-end CLI tests against the local server (no external network)."""

import pytest

from minicurl import __version__
from minicurl.cli import main
from minicurl.errors import ExitCode


def test_version_flag(capsys):
    assert main(["--version"]) == ExitCode.OK
    assert __version__ in capsys.readouterr().out


def test_help_flag_exits_zero(capsys):
    with pytest.raises(SystemExit) as info:
        main(["--help"])
    assert info.value.code == 0
    assert "usage" in capsys.readouterr().out.lower()


def test_missing_url_exit_code_3(capsys):
    assert main([]) == ExitCode.MALFORMED_URL
    assert "no URL" in capsys.readouterr().err


def test_get_prints_body(base_url, capsys):
    assert main(["-s", base_url + "/hello"]) == ExitCode.OK
    assert "hello world" in capsys.readouterr().out


def test_post_data_implies_post(base_url, capsys):
    assert main(["-s", "-d", "a=1", base_url + "/echo"]) == ExitCode.OK
    assert '"method": "POST"' in capsys.readouterr().out


def test_explicit_method_and_header(base_url, capsys):
    code = main(["-s", "-X", "POST", "-H", "X-Cli: yes",
                 "-d", "k=v", base_url + "/echo"])
    assert code == ExitCode.OK
    assert '"x_cli": "yes"' in capsys.readouterr().out


def test_output_to_file(base_url, tmp_path, capsys):
    target = tmp_path / "out.txt"
    code = main(["-s", "-o", str(target), base_url + "/hello"])
    assert code == ExitCode.OK
    assert target.read_bytes() == b"hello world"
    assert "hello world" not in capsys.readouterr().out


def test_remote_name_saves_last_segment(base_url, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["-s", "-O", base_url + "/hello"]) == ExitCode.OK
    assert (tmp_path / "hello").read_bytes() == b"hello world"


def test_fail_flag_maps_404_to_exit_22(base_url, capsys):
    assert main(["-s", "-f", base_url + "/missing"]) == ExitCode.HTTP_ERROR
    assert "404" in capsys.readouterr().err


def test_without_fail_flag_404_still_zero(base_url, capsys):
    assert main(["-s", base_url + "/missing"]) == ExitCode.OK
    assert "not found" in capsys.readouterr().out


def test_max_time_maps_to_exit_28(base_url):
    assert main(["-s", "-m", "0.5", base_url + "/slow"]) == ExitCode.TIMEOUT


def test_malformed_header_exit_43(base_url, capsys):
    assert main(["-s", "-H", "no-colon", base_url + "/hello"]) == \
        ExitCode.BAD_FUNCTION_ARGUMENT


def test_output_and_remote_name_conflict(base_url):
    assert main(["-s", "-o", "a", "-O", base_url + "/hello"]) == \
        ExitCode.BAD_FUNCTION_ARGUMENT


def test_include_prints_headers(base_url, capsys):
    assert main(["-s", "-i", base_url + "/hello"]) == ExitCode.OK
    out = capsys.readouterr().out
    assert "200" in out and "Content-Type" in out and "hello world" in out


def test_write_out_template(base_url, capsys):
    assert main(["-s", "-w", "code=%{http_code}\\n",
                 base_url + "/hello"]) == ExitCode.OK
    assert "code=200" in capsys.readouterr().out


def test_form_upload(base_url, tmp_path, capsys):
    target = tmp_path / "up.txt"
    target.write_bytes(b"upload-bytes")
    code = main(["-s", "-F", f"f=@{target}", base_url + "/upload"])
    assert code == ExitCode.OK
    assert "multipart/form-data" in capsys.readouterr().out
