"""Error types and curl-compatible exit codes."""

from __future__ import annotations


class ExitCode:
    """Exit codes roughly matching the real curl."""

    OK = 0
    UNSUPPORTED_PROTOCOL = 2
    MALFORMED_URL = 3
    DNS_NOT_FOUND = 6
    CONNECT_FAILED = 7
    TOO_MANY_REDIRECTS = 47
    BAD_FUNCTION_ARGUMENT = 43
    HTTP_ERROR = 22  # -f / --fail
    TIMEOUT = 28
    SSL_ERROR = 35
    PARTIAL_FILE = 18
    WRITE_ERROR = 23
    RECV_ERROR = 52
    UNKNOWN = 1


class CurlError(Exception):
    """Base error carrying a curl-style exit code and message."""

    def __init__(self, message: str, code: int = ExitCode.UNKNOWN):
        super().__init__(message)
        self.message = message
        self.code = code


class UrlError(CurlError):
    def __init__(self, message: str, code: int = ExitCode.MALFORMED_URL):
        super().__init__(message, code)


class DnsError(CurlError):
    def __init__(self, message: str):
        super().__init__(message, ExitCode.DNS_NOT_FOUND)


class ConnectError(CurlError):
    def __init__(self, message: str):
        super().__init__(message, ExitCode.CONNECT_FAILED)


class TimeoutError_(CurlError):
    def __init__(self, message: str):
        super().__init__(message, ExitCode.TIMEOUT)


class SslError(CurlError):
    def __init__(self, message: str):
        super().__init__(message, ExitCode.SSL_ERROR)


class RedirectError(CurlError):
    def __init__(self, message: str):
        super().__init__(message, ExitCode.TOO_MANY_REDIRECTS)


class HttpStatusError(CurlError):
    """Raised by --fail when the server answers with >= 400."""

    def __init__(self, message: str):
        super().__init__(message, ExitCode.HTTP_ERROR)


class ProtocolError(CurlError):
    def __init__(self, message: str, code: int = ExitCode.RECV_ERROR):
        super().__init__(message, code)
