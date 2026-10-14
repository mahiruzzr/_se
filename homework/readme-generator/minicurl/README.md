# minicurl

A small, curl-like HTTP command line client written in pure Python
(standard library only: `http.client` + `ssl`, no third-party dependencies).

## Requirements

- Python 3.10 or newer
- No third-party packages needed at runtime
- `pytest` only for running the test suite

## Installation

No installation required. Run it straight from this directory:

```bash
cd minicurl
python -m minicurl --help
```

## Usage

```bash
python -m minicurl [options] URL
```

### Common examples

```bash
# Simple GET
python -m minicurl https://example.com/

# POST a form-encoded body (implies POST, like curl)
python -m minicurl -d "name=value&key=123" https://example.com/api

# Explicit method with extra headers
python -m minicurl -X POST -H "Content-Type: application/json" \
    -d '{"hello": "world"}' https://example.com/api

# Save the body to a file / use the remote file name
python -m minicurl -o page.html https://example.com/
python -m minicurl -O https://example.com/files/report.pdf

# Follow redirects, fail loudly on HTTP errors
python -m minicurl -L https://example.com/old-path
python -m minicurl -f https://example.com/missing   # exit 22 on 404

# Timeouts (seconds)
python -m minicurl -m 10 https://example.com/slow
python -m minicurl -m 30 --connect-timeout 5 https://example.com/

# Show response headers / write-out variables
python -m minicurl -i https://example.com/
python -m minicurl -s -w "code=%{http_code} time=%{time_total}\n" https://example.com/

# Multipart file upload
python -m minicurl -F "doc=@report.pdf;type=application/pdf" https://example.com/upload

# Basic auth, custom agent, insecure TLS, proxy, HTTP/1.0, verbosity
python -m minicurl -u user:password https://example.com/private
python -m minicurl -A "my-agent/1.0" https://example.com/
python -m minicurl -k https://self-signed.test/
python -m minicurl -x http://127.0.0.1:8080 https://example.com/
python -m minicurl --http1.0 https://example.com/
python -m minicurl -v https://example.com/   # trace on stderr
```

### All options

| Option | Description |
| ------ | ----------- |
| `-X, --request` | HTTP method (default GET, or POST with `-d`/`-F`) |
| `-d, --data` | Request body (repeatable, joined with `&`; implies POST) |
| `-H, --header` | `'Name: value'` request header (repeatable) |
| `-F, --form` | Multipart field `'name=value'` or `'name=@file[;type=..]'` |
| `-o, --output` | Write body to FILE instead of stdout |
| `-O, --remote-name` | Save using the remote file name |
| `-L, --location` | Follow redirects (`--max-redirs`, default 50) |
| `-f, --fail` | Exit 22 on HTTP status >= 400, suppress body |
| `-m, --max-time` | Overall timeout in seconds (default 300) |
| `--connect-timeout` | Connection phase timeout in seconds |
| `-k, --insecure` | Skip TLS certificate verification |
| `-u, --user` | Basic auth as `user:password` |
| `-A, --user-agent` | Custom User-Agent header |
| `-i, --include` | Print response headers before the body |
| `-s, --silent` | Hide the progress meter |
| `-v, --verbose` | Connection trace on stderr |
| `-w, --write-out` | Template with `%{http_code}`, `%{time_total}`, … |
| `-x, --proxy` | Proxy URL (`http://host:port`) |
| `--http1.0` | Send the request line as HTTP/1.0 |
| `--version` | Print version and exit |

## Exit codes

Exit codes follow real curl where applicable:

| Code | Meaning |
| ---- | ------- |
| 0 | OK |
| 2 | Unsupported protocol |
| 3 | Malformed URL / no URL given |
| 6 | Could not resolve host |
| 7 | Failed to connect |
| 18 | Partial file |
| 22 | HTTP error with `--fail` |
| 23 | Write error |
| 28 | Timeout |
| 35 | SSL error |
| 43 | Bad argument (e.g. malformed header or form field) |
| 47 | Too many redirects |
| 52 | Receive failure |

## Testing

Tests spin up a local HTTP server in-process, so no internet access is needed:

```bash
cd minicurl
python -m pytest tests -q
```

Expected: **55 passed**. The suite covers URL parsing, GET/POST,
redirects (including loop limits), gzip decoding, basic auth, timeouts,
connection/DNS failure mapping, multipart encoding, `--write-out`
rendering, progress helpers, and end-to-end CLI runs
(`--help`, `--version`, `-o`/`-O`, `--fail`, `--max-time`, `-F`, …).

## Project structure

```text
minicurl/
├── README.md               # this file
├── minicurl/               # the package (stdlib only)
│   ├── __init__.py         # version
│   ├── __main__.py         # `python -m minicurl` entry point
│   ├── cli.py              # argparse front-end, exit-code mapping
│   ├── httpclient.py       # HTTP engine (redirects, streaming, TLS, timings)
│   ├── urlparse.py         # URL parsing with curl-like defaults
│   ├── multipart.py        # -F/--form encoding
│   ├── output.py           # --write-out rendering, -O file names
│   ├── progress.py         # progress meter, size/ETA helpers
│   └── errors.py           # exception types + curl exit codes
└── tests/                  # pytest suite (local server, no network)
    ├── conftest.py
    ├── test_urlparse.py
    ├── test_httpclient.py
    ├── test_modules.py
    └── test_cli.py
```

## Notes and limitations

- `--connect-timeout` is accepted for compatibility but the underlying
  socket currently uses the overall `--max-time` for both the connect
  and read phases.
- `size_download` counts raw (possibly still compressed) bytes when no
  output sink is attached; bodies handed to a sink are decompressed.
- HTTP/2, cookies, and client certificates are out of scope.
