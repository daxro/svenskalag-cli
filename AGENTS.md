# Project instructions

Read `README.md` in full before changing the CLI contract or other user-visible behavior.

## Purpose

`svenskalag-cli` is an unofficial, read-only CLI for Svenskalag.se. Keep it small, predictable, secure, and useful to people, scripts, and software agents.

## Rules

- Write data JSON to stdout. Write structured errors and optional progress to stderr.
- Never expose credentials, cookies, or access codes in output, errors, logs, fixtures, or documentation.
- Verify new credentials in a separate session before replacing a working profile.
- Write configuration, session, and state files atomically with `0600` permissions.
- Bound calendar reads and stop once `--limit` has been reached.
- Add focused tests for behavior changes and run the complete test suite.
- Write documentation, help text, comments, and docstrings in English. Keep the machine API and code symbols in English.

## Development

```bash
uv sync --locked --all-groups
uv run pytest
uv build
uv run svenskalag --help
```
