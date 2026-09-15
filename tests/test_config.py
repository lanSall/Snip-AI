from pathlib import Path

from snipai.config import (
    DEFAULT_GEMINI_MODEL,
    apply_setup,
    from_dict,
    infer_provider,
    load_config,
    looks_like_gemini_key,
    models_for_provider,
    needs_setup,
    prepare_config,
    resolve_config_path,
    save_config,
    write_example_config,
)


def test_defaults():
    config = from_dict({})
    assert config.provider == "gemini"
    assert config.model == "gemini-3.8-flash"
    assert config.model == DEFAULT_GEMINI_MODEL
    assert config.hotkey == "ctrl+shift+space"
    assert config.settings_hotkey == "ctrl+shift+slash"
    assert config.ask_hotkey == "ctrl+shift+a"
    assert config.notify.position == "bottom-right"
    assert config.notify.sound is False


def test_models_for_provider_lists_flash_first():
    ids = [mid for mid, _label in models_for_provider("gemini")]
    assert ids[0] == "gemini-3.8-flash"
    assert "gemini-3.1-flash-lite" in ids
    assert "gemini-3.1-pro-preview" in ids


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
    assert config.model == "gemini-3.8-flash"


def test_looks_like_gemini_key():
    assert looks_like_gemini_key("AIzaSyABC")
    assert looks_like_gemini_key("AQ.abc")
    assert not looks_like_gemini_key("sk-openai")


def test_load_missing_file_uses_defaults(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SNIPAI_CONFIG", str(tmp_path / "missing.yaml"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    config = load_config()
    assert config.model == "gemini-3.8-flash"


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


def test_infer_provider():
    assert infer_provider("AIzaSyABC") == "gemini"
    assert infer_provider("sk-ant-abc") == "anthropic"
    assert infer_provider("sk-or-v1-abc") == "openrouter"
    assert infer_provider("sk-proj-abc") == "openai"
    assert infer_provider("", fallback="ollama") == "ollama"


def test_needs_setup(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("SNIPAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert needs_setup(from_dict({"provider": "gemini", "api_key": ""}))
    assert not needs_setup(from_dict({"provider": "mock"}))
    assert not needs_setup(from_dict({"provider": "ollama"}))
    assert not needs_setup(from_dict({"provider": "gemini", "api_key": "AIza-test"}))


def test_apply_setup_infers_openai_from_key():
    config = apply_setup(from_dict({}), api_key="sk-proj-abc")
    assert config.provider == "openai"
    assert config.model == "gpt-4o"
    assert config.api_key == "sk-proj-abc"


def test_apply_setup_respects_explicit_provider():
    config = apply_setup(from_dict({}), api_key="sk-proj-abc", provider="openrouter")
    assert config.provider == "openrouter"


def test_save_config_roundtrip(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    path = tmp_path / "config.yaml"
    saved = apply_setup(from_dict({}), api_key="AIzaSyTESTKEY")
    save_config(saved, path)
    loaded = load_config(path)
    assert loaded.api_key == "AIzaSyTESTKEY"
    assert loaded.provider == "gemini"
    assert loaded.model == "gemini-3.8-flash"
    assert loaded.settings_hotkey == "ctrl+shift+slash"
    assert loaded.ask_hotkey == "ctrl+shift+a"
    text = path.read_text(encoding="utf-8")
    assert "api_key:" in text
    assert "settings_hotkey:" in text
    assert "ask_hotkey:" in text


def test_example_files_do_not_contain_live_keys():
    import re

    repo = Path(__file__).resolve().parents[1]
    blob = (repo / "config.example.yaml").read_text(encoding="utf-8")
    blob += "\n" + (repo / "snipai" / "config.py").read_text(encoding="utf-8")
    assert not re.search(r"AIzaSy[A-Za-z0-9_-]{20,}", blob)


def test_prepare_config_upgrades_retired_gemini_default():
    config = prepare_config(from_dict({"provider": "gemini", "model": "gemini-2.5-pro", "api_key": "AIza-test"}))
    assert config.model == "gemini-3.8-flash"


def test_prepare_config_keeps_gemini_31_pro():
    config = prepare_config(
        from_dict({"provider": "gemini", "model": "gemini-3.1-pro-preview", "api_key": "AIza-test"})
    )
    assert config.model == "gemini-3.1-pro-preview"


def test_load_config_rewrites_retired_gemini_model(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("SNIPAI_MODEL", raising=False)
    path = tmp_path / "config.yaml"
    path.write_text("provider: gemini\nmodel: gemini-2.5-pro\napi_key: AIza-test\n", encoding="utf-8")
    config = load_config(path)
    assert config.model == "gemini-3.8-flash"
    assert "gemini-3.8-flash" in path.read_text(encoding="utf-8")
    assert "gemini-2.5-pro" not in path.read_text(encoding="utf-8")


def test_load_config_does_not_rewrite_gemini_31_pro(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("SNIPAI_MODEL", raising=False)
    path = tmp_path / "config.yaml"
    path.write_text(
        "provider: gemini\nmodel: gemini-3.1-pro-preview\napi_key: AIza-test\n",
        encoding="utf-8",
    )
    config = load_config(path)
    assert config.model == "gemini-3.1-pro-preview"
    assert "gemini-3.1-pro-preview" in path.read_text(encoding="utf-8")


def test_apply_setup_keeps_explicit_model():
    config = apply_setup(
        from_dict({"provider": "gemini"}),
        api_key="AIzaSyTESTKEY",
        provider="gemini",
        model="gemini-3.1-flash-lite",
    )
    assert config.model == "gemini-3.1-flash-lite"


def test_apply_setup_keeps_existing_pro_when_model_omitted():
    config = apply_setup(
        from_dict({"provider": "gemini", "model": "gemini-3.1-pro-preview"}),
        api_key="AIzaSyTESTKEY",
        provider="gemini",
    )
    assert config.model == "gemini-3.1-pro-preview"
