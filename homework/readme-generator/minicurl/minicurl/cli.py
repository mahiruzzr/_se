"""Minimal curl-like command line front-end over HttpClient."""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .errors import CurlError, ExitCode, HttpStatusError
from .httpclient import HttpClient, Request, Response
from .multipart import encode_multipart, parse_form_args
from .output import format_status_line, remote_filename, render
from .progress import ProgressMeter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="minicurl",
        description="A small, curl-like HTTP command line client.",
    )
    parser.add_argument("url", nargs="?", help="URL to request")
    parser.add_argument("--version", action="store_true",
                        help="Show version and exit")
    parser.add_argument("-X", "--request", default=None,
                        help="HTTP method (default GET, or POST with -d/-F)")
    parser.add_argument("-d", "--data", action="append", default=[],
                        help="Request body (repeatable, joined with &; implies POST)")
    parser.add_argument("-H", "--header", action="append", default=[],
                        help="'Name: value' request header (repeatable)")
    parser.add_argument("-F", "--form", action="append", default=[],
                        help="multipart form field 'name=value' or 'name=@file[;type=..]'")
    parser.add_argument("-o", "--output", default=None,
                        help="Write body to FILE instead of stdout")
    parser.add_argument("-O", "--remote-name", action="store_true",
                        help="Write body to a file named like the remote file")
    parser.add_argument("-L", "--location", action="store_true",
                        help="Follow redirects")
    parser.add_argument("--max-redirs", type=int, default=50,
                        help="Maximum redirects to follow (default 50)")
    parser.add_argument("-f", "--fail", action="store_true",
                        help="Fail with exit 22 on HTTP >= 400 (no body output)")
    parser.add_argument("-m", "--max-time", type=float, default=300.0,
                        help="Overall operation timeout in seconds")
    parser.add_argument("--connect-timeout", type=float, default=None,
                        help="Connection phase timeout in seconds")
    parser.add_argument("-k", "--insecure", action="store_true",
                        help="Skip TLS certificate verification")
    parser.add_argument("-u", "--user", default=None,
                        help="Basic auth 'user:password'")
    parser.add_argument("-A", "--user-agent", default=None,
                        help="Custom User-Agent header")
    parser.add_argument("-i", "--include", action="store_true",
                        help="Include response headers in the output")
    parser.add_argument("-s", "--silent", action="store_true",
                        help="Silent mode (no progress meter)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Verbose connection trace on stderr")
    parser.add_argument("-w", "--write-out", default=None,
                        help="Write-out template, e.g. '%%{http_code}\\n'")
    parser.add_argument("-x", "--proxy", default=None,
                        help="Proxy URL (http://host:port)")
    parser.add_argument("--http1.0", dest="http10", action="store_true",
                        help="Use HTTP/1.0 for the request line")
    return parser


def _split_header(raw: str) -> tuple[str, str]:
    if ":" not in raw:
        raise CurlError(f"malformed header: {raw!r} (expected 'Name: value')",
                        ExitCode.BAD_FUNCTION_ARGUMENT)
    name, value = raw.split(":", 1)
    name = name.strip()
    if not name:
        raise CurlError(f"malformed header: {raw!r} (empty name)",
                        ExitCode.BAD_FUNCTION_ARGUMENT)
    return name, value.strip()


def _build_request(args: argparse.Namespace) -> Request:
    if not args.url:
        raise CurlError("no URL specified!", ExitCode.MALFORMED_URL)
    headers = [_split_header(item) for item in args.header]
    if args.user_agent:
        headers.append(("User-Agent", args.user_agent))
    auth = None
    if args.user:
        user, _, password = args.user.partition(":")
        auth = (user, password)
    body: bytes | None = None
    if args.form:
        try:
            fields = parse_form_args(args.form)
            body, content_type = encode_multipart(fields)
        except ValueError as exc:
            raise CurlError(str(exc), ExitCode.BAD_FUNCTION_ARGUMENT) from exc
        headers.append(("Content-Type", content_type))
    elif args.data:
        body = "&".join(args.data).encode()
    method = args.request or ("POST" if body is not None else "GET")
    return Request(
        method=method,
        url=args.url,
        headers=headers,
        body=body,
        timeout=args.max_time,
        connect_timeout=args.connect_timeout,
        follow_redirects=args.location,
        max_redirects=args.max_redirs,
        insecure=args.insecure,
        proxy=args.proxy,
        auth=auth,
        http_version="1.0" if args.http10 else "1.1",
    )


def main(argv: list[str] | None = None) -> int:
    """Run minicurl; return the process exit code (no sys.exit inside)."""
    args = build_parser().parse_args(argv)
    if args.version:
        print(f"minicurl {__version__}")
        return ExitCode.OK
    if not args.url:
        build_parser().print_usage(sys.stderr)
        print("minicurl: no URL specified!", file=sys.stderr)
        return ExitCode.MALFORMED_URL

    verbose = (lambda msg: print(msg, file=sys.stderr)) if args.verbose else None
    client = HttpClient(verbose=verbose)
    try:
        request = _build_request(args)
    except CurlError as exc:
        print(f"minicurl: {exc.message}", file=sys.stderr)
        return exc.code

    if args.output and args.remote_name:
        print("minicurl: --output and --remote-name are mutually exclusive",
              file=sys.stderr)
        return ExitCode.BAD_FUNCTION_ARGUMENT

    out_file = None
    if args.output:
        try:
            out_file = open(args.output, "wb")
        except OSError as exc:
            print(f"minicurl: cannot write to {args.output!r}: {exc}",
                  file=sys.stderr)
            return ExitCode.WRITE_ERROR

    meter = ProgressMeter(enabled=not args.silent)
    chunks: list[bytes] = []

    def sink(data: bytes) -> None:
        meter.update(len(data))
        if out_file is not None:
            out_file.write(data)
        else:
            chunks.append(data)

    def on_response(response: Response) -> None:
        meter.total = response.content_length
        if args.fail and response.status >= 400:
            raise HttpStatusError(
                f"The requested URL returned error: {response.status}")

    try:
        response = client.run(request, sink=sink, on_response=on_response)
    except CurlError as exc:
        print(f"minicurl: {exc.message}", file=sys.stderr)
        return exc.code
    finally:
        meter.finish()
        if out_file is not None:
            out_file.close()

    body = b"".join(chunks)
    if args.remote_name:
        filename = remote_filename(response.url)
        try:
            with open(filename, "wb") as handle:
                handle.write(body)
        except OSError as exc:
            print(f"minicurl: cannot write to {filename!r}: {exc}",
                  file=sys.stderr)
            return ExitCode.WRITE_ERROR

    if out_file is None:
        if args.include:
            sys.stdout.write(format_status_line(response))
            sys.stdout.write(response.all_headers)
            sys.stdout.write("\r\n")
        try:
            sys.stdout.buffer.write(body)
            sys.stdout.buffer.flush()
        except (OSError, ValueError) as exc:
            print(f"minicurl: failed writing output: {exc}", file=sys.stderr)
            return ExitCode.WRITE_ERROR

    if args.write_out:
        sys.stdout.write(render(args.write_out, response))
        sys.stdout.flush()
    return ExitCode.OK
