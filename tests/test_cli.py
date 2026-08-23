import json

from svenskalag_cli import cli


def test_help_and_version_are_available(capsys):
    try:
        cli.build_parser().parse_args(["--version"])
    except SystemExit as exc:
        assert exc.code == 0
    assert "svenskalag 0.1.0" in capsys.readouterr().out


def test_help_uses_english_headings(capsys):
    with __import__("pytest").raises(SystemExit) as stopped:
        cli.build_parser().parse_args(["--help"])
    assert stopped.value.code == 0
    output = capsys.readouterr().out
    assert "usage:" in output
    assert "positional arguments:" in output
    assert "options:" in output


def test_unknown_fields_fail_before_configuration(capsys):
    assert cli.main(["groups", "--fields", "secret"]) == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"] == "invalid_input"
    assert "Unknown fields" in payload["message"]


def test_invalid_date_and_limit_fail_locally(capsys):
    assert cli.main(["calendar", "--since", "2026-02-30"]) == 2
    assert json.loads(capsys.readouterr().err)["error"] == "invalid_input"


def test_invitations_reject_inverted_range(capsys):
    assert cli.main(["invitations", "--since", "2026-08-25", "--until", "2026-08-24"]) == 2
    assert json.loads(capsys.readouterr().err)["error"] == "invalid_input"


def test_unconfigured_status_is_success(monkeypatch, capsys):
    monkeypatch.setattr(cli, "load_config", lambda required=False: {"url": None, "username": None, "password": None})
    assert cli.main(["status", "--json", "-q"]) == 0
    assert json.loads(capsys.readouterr().out)["configured"] is False


def test_status_fields_require_json(capsys):
    assert cli.main(["status", "--fields", "configured"]) == 2
    assert json.loads(capsys.readouterr().err)["error"] == "invalid_input"
    assert cli.main(["calendar", "--limit", "0"]) == 2
    assert json.loads(capsys.readouterr().err)["error"] == "invalid_input"


def test_noninteractive_setup_requires_namespaced_environment(monkeypatch, capsys):
    for name in ("SVENSKALAG_URL", "SVENSKALAG_USERNAME", "SVENSKALAG_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    assert cli.main(["setup", "--no-input"]) == 2
    assert json.loads(capsys.readouterr().err)["error"] == "invalid_input"


def test_setup_rejects_association_root_without_replacing_config(monkeypatch, capsys):
    monkeypatch.setenv("SVENSKALAG_URL", "https://www.svenskalag.se/demo-forening")
    monkeypatch.setenv("SVENSKALAG_USERNAME", "demo")
    monkeypatch.setenv("SVENSKALAG_PASSWORD", "secret")
    monkeypatch.setattr(cli, "authenticate", lambda *args: object())
    monkeypatch.setattr(cli, "fetch_context", lambda *args: {
        "organization": {"name": "Demo IF", "slug": "demo-forening", "url": "https://www.svenskalag.se/demo-forening"},
        "group": {"name": "En slogan", "slug": "demo-forening", "url": "https://www.svenskalag.se/demo-forening"},
    })
    saved = []
    monkeypatch.setattr(cli, "save_config", lambda *args: saved.append(args))
    assert cli.main(["setup", "--no-input", "-q"]) == 2
    assert not saved
    assert json.loads(capsys.readouterr().err)["error"] == "invalid_input"


def test_reset_is_idempotent(tmp_path, monkeypatch, capsys):
    paths = [tmp_path / name for name in ("config", "session", "state")]
    for path in paths[:2]:
        path.write_text("x")
    monkeypatch.setattr(cli, "CONFIG_FILE", paths[0])
    monkeypatch.setattr(cli, "SESSION_FILE", paths[1])
    monkeypatch.setattr(cli, "STATE_FILE", paths[2])
    assert cli.main(["reset", "-q"]) == 0
    assert json.loads(capsys.readouterr().out)["reset"] is True
    assert cli.main(["reset", "-q"]) == 0
    assert json.loads(capsys.readouterr().out)["deleted"] == []
