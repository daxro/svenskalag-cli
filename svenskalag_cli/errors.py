"""Structured errors and exit codes for the CLI."""

import json
import sys

EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_AUTH = 3
EXIT_NOT_FOUND = 4
EXIT_NETWORK = 5


class SvenskalagError(Exception):
    """Base error with a stable machine-readable name."""

    code = "error"
    exit_code = EXIT_ERROR

    def __init__(self, message):
        super().__init__(message)
        self.message = message


class InputError(SvenskalagError):
    code = "invalid_input"
    exit_code = EXIT_USAGE


class NotConfiguredError(SvenskalagError):
    code = "not_configured"
    exit_code = EXIT_USAGE


class AuthError(SvenskalagError):
    code = "authentication_error"
    exit_code = EXIT_AUTH


class NotFoundError(SvenskalagError):
    code = "not_found"
    exit_code = EXIT_NOT_FOUND


class NetworkError(SvenskalagError):
    code = "network_error"
    exit_code = EXIT_NETWORK


class ParseError(SvenskalagError):
    code = "parse_error"
    exit_code = EXIT_ERROR


def emit_error(error):
    """Write a stable JSON error and return its exit code."""
    payload = {"error": error.code, "message": error.message}
    print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
    return error.exit_code
