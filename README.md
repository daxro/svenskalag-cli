# svenskalag-cli

An unofficial, read-only command-line interface for [Svenskalag.se](https://www.svenskalag.se). It uses undocumented web flows and may stop working when Svenskalag changes its website.

The CLI is designed for people, scripts, and software agents that can run commands and consume JSON.

## Installation

```bash
uv tool install git+https://github.com/daxro/svenskalag-cli.git
```

Python 3.10 or later is required.

## Secure setup

Run setup privately:

```bash
svenskalag setup
```

Enter the URL of a team or group page, your username, and your password. Association root pages are not supported in v1. Credentials are verified before an existing working profile is replaced. They are stored locally in files with `0600` permissions so the CLI can reauthenticate when the session expires.

For user-controlled automation, a secret manager can provide:

```bash
SVENSKALAG_URL=... SVENSKALAG_USERNAME=... SVENSKALAG_PASSWORD=... svenskalag setup --no-input -q
```

Never send credentials to an agent or place them directly in a command. If a command returns `not_configured`, run setup privately.

## Commands

```bash
svenskalag status --json -q
svenskalag groups -q
svenskalag people -q
svenskalag calendar --since 2026-08-01 --until 2026-08-31 --limit 10 -q
svenskalag activity 20857531 -q
svenskalag news --limit 5 -q
svenskalag news 2467511 -q
svenskalag invitations --person 3900915 -q
svenskalag reset -q
```

`--group` accepts an exact slug and otherwise uses the group configured during setup. Dates must be valid ISO dates in `YYYY-MM-DD` format. Calendar ranges may span at most 24 months.

`--fields` rejects empty and unknown fields. Data commands write JSON to stdout. Errors are written as a JSON object to stderr. Progress is written to stderr and can be suppressed with `-q`.

Example error:

```json
{"error":"not_configured","message":"The CLI is not configured. Run: svenskalag setup"}
```

## Exit codes

| Code | Meaning |
|---:|---|
| `0` | Success |
| `1` | Unexpected or general error |
| `2` | Invalid input or missing configuration |
| `3` | Authentication error |
| `4` | Resource not found |
| `5` | Network error |
| `130` | Interrupted |

## Local development

```bash
uv sync --locked --all-groups
uv run pytest
uv build
uv run svenskalag --help
```

See [SECURITY.md](SECURITY.md) for security information.
