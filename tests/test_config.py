from pathlib import Path

from snipai.config import (
    from_dict,
    load_config,
    looks_like_gemini_key,
    prepare_config,
    resolve_config_path,
    write_example_config,
)


def test_defaults():
    config = from_dict({})
    assert config.provider == "openai"
    assert config.hotkey == "ctrl+shift+space"
    assert config.notify.position == "bottom-right"
    assert config.notify.sound is False


def test_env_overrides_provider_and_key(monkeypatch):
    monkeypatch.setenv("SNIPAI_PROVIDER", "anthropic")
    monkeypatch.setenv("SNIPAI_MODEL", "claude-sonnet-4-5")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    config = from_dict({"provider": "openai", "model": "gpt-4o"})
    assert config.provider == "anthropic"
    assert config.model == "claude-sonnet-4-5"
    assert config.resolved_api_key() == "sk-ant-test"


def test_file_api_key_wins(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "from-env")
    config = from_dict({"api_key": "from-file"})
    assert config.resolved_api_key() == "from-file"


def test_gemini_env_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("SNIPAI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-from-env")
    config = prepare_config(from_dict({"provider": "gemini", "api_key": ""}))
    assert config.resolved_api_key() == "AIza-from-env"
    assert config.resolved_base_url().endswith("/openai")


def test_gemini_key_switches_openai_defaults(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    config = prepare_config(
        from_dict({"provider": "openai", "api_key": "AIzaSyTestKey", "model": "gpt-4o"})
    )
    assert config.provider == "gemini"
    assert config.model == "gemini-2.5-pro"


def test_looks_like_gemini_key():
    assert looks_like_gemini_key("AIzaSyABC")
    assert looks_like_gemini_key("AQ.abc")
    assert not looks_like_gemini_key("sk-openai")


def test_load_missing_file_uses_defaults(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SNIPAI_CONFIG", str(tmp_path / "missing.yaml"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    config = load_config()
    assert config.model == "gpt-4o"


def test_cwd_config_is_discovered(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("SNIPAI_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text("provider: mock\n", encoding="utf-8")
    assert resolve_config_path().resolve() == (tmp_path / "config.yaml").resolve()
    assert load_config().provider == "mock"


def test_load_yaml(tmp_path: Path):
    path = tmp_path / "config.yaml"
    path.write_text("provider: mock\nnotify:\n  max_chars: 40\n", encoding="utf-8")
    config = load_config(path)
    assert config.provider == "mock"
    assert config.notify.max_chars == 40


def test_write_example_does_not_overwrite(tmp_path: Path):
    path = tmp_path / "config.yaml"
    path.write_text("provider: mock\n", encoding="utf-8")
    write_example_config(path)
    assert "mock" in path.read_text(encoding="utf-8")
