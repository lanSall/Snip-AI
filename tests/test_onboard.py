from io import StringIO
from pathlib import Path

from snipai.config import from_dict, load_config
from snipai.onboard import offer_setup, run_cli_setup


def test_run_cli_setup_saves_pasted_key():
    config = from_dict({"provider": "gemini", "api_key": ""})
    updated = run_cli_setup(config, stdin=StringIO("AIzaSyPASTED\n"), stdout=StringIO())
    assert updated is not None
    assert updated.api_key == "AIzaSyPASTED"
    assert updated.provider == "gemini"


def test_run_cli_setup_blank_cancels():
    config = from_dict({"provider": "gemini", "api_key": ""})
    assert run_cli_setup(config, stdin=StringIO("\n"), stdout=StringIO()) is None


def test_offer_setup_cli_writes_file(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("SNIPAI_API_KEY", raising=False)
    path = tmp_path / "config.yaml"
    config = from_dict({"provider": "gemini", "api_key": ""})
    monkeypatch.setattr("snipai.onboard.run_cli_setup", lambda cfg, **_k: from_dict({"provider": "gemini", "api_key": "AIza-cli"}))
    # Force the CLI path (no GUI).
    monkeypatch.setattr("snipai.onboard.should_show_setup_gui", lambda: False)
    monkeypatch.setattr("snipai.onboard.sys.stdin.isatty", lambda: True)
    updated = offer_setup(config, path, force_cli=True)
    assert updated is not None
    assert load_config(path).api_key == "AIza-cli"
