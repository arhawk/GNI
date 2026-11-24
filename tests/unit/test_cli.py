import json

from gni.cli import main


def test_cli_version(capsys):
    try:
        main(["version"])
    except SystemExit as e:
        assert e.code == 0
    assert "0.1.4" in capsys.readouterr().out


def test_cli_health(capsys):
    try:
        main(["health"])
    except SystemExit as e:
        assert e.code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert payload["llm_api_configured"] is False or isinstance(payload["llm_api_configured"], bool)
