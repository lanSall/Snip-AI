"""Load and save snip-ai settings."""

from __future__ import annotations

import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from snipai import SnipError


DEFAULT_SYSTEM_PROMPT = """You are a screenshot problem-solver.

Look at the image. Identify the question, error, puzzle, or task on screen.
Solve it. Be correct and concise.

Format your reply EXACTLY like this:
ANSWER: <the final answer, as short as possible>
WHY: <one or two sentences>

If the screenshot is an error message, ANSWER is the fix.
If it is multiple choice, ANSWER is the letter and the choice text.
If there is no problem to solve, ANSWER is a one-line description of what you see.
Do not use markdown."""


def user_config_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "snip-ai"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "snip-ai"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "snip-ai"
    return Path.home() / ".config" / "snip-ai"


def user_data_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "snip-ai"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / "snip-ai"
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "snip-ai"
    return Path.home() / ".local" / "share" / "snip-ai"


def package_config_path() -> Path:
    """``config.yaml`` next to the snip-ai project folder (where this package lives)."""
    return Path(__file__).resolve().parent.parent / "config.yaml"


def resolve_config_path(explicit: Path | None = None) -> Path:
    """Pick the config file: ``--config``, ``$SNIPAI_CONFIG``, cwd, project folder, then the user config dir."""
    if explicit is not None:
        return explicit.expanduser()
    override = os.environ.get("SNIPAI_CONFIG")
    if override:
        return Path(override).expanduser()
    cwd_config = Path.cwd() / "config.yaml"
    if cwd_config.is_file():
        return cwd_config
    packaged = package_config_path()
    if packaged.is_file():
        return packaged
    return user_config_dir() / "config.yaml"


def default_config_path() -> Path:
    return resolve_config_path()


@dataclass
class NotifyConfig:
    enabled: bool = True
    duration_ms: int = 8000
    max_chars: int = 180
    position: str = "bottom-right"
    sound: bool = False


DEFAULT_GEMINI_MODEL = "gemini-3.1-pro-preview"
# Old defaults Google now rejects for new API keys ("no longer available to new users").
LEGACY_GEMINI_MODELS = frozenset(
    {
        "gemini-2.5-pro",
        "gemini-2.5-pro-preview-03-25",
        "gemini-2.5-pro-preview-05-06",
        "gemini-2.5-pro-preview-06-05",
        "gemini-pro",
        "gemini-pro-vision",
    }
)

DEFAULT_MODELS = {
    "gemini": DEFAULT_GEMINI_MODEL,
    "google": DEFAULT_GEMINI_MODEL,
    "openai": "gpt-4o",
    "openai_compatible": "gpt-4o",
    "anthropic": "claude-sonnet-4-5",
    "openrouter": "openai/gpt-4o",
    "ollama": "llama3.2-vision",
    "mock": "mock",
}

KEY_SIGNUP_URLS = {
    "gemini": "https://aistudio.google.com/api-keys",
    "google": "https://aistudio.google.com/api-keys",
    "openai": "https://platform.openai.com/api-keys",
    "anthropic": "https://console.anthropic.com/settings/keys",
    "openrouter": "https://openrouter.ai/keys",
    "ollama": "https://ollama.com/",
}


@dataclass
class Config:
    provider: str = "gemini"
    model: str = DEFAULT_GEMINI_MODEL
    api_key: str = ""
    base_url: str = ""
    hotkey: str = "ctrl+shift+space"
    region_hotkey: str = "ctrl+shift+period"
    capture_mode: str = "screen"
    clipboard: bool = True
    save_shots: bool = False
    shots_dir: str = ""
    max_image_width: int = 1600
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    mock_reply: str = ""
    notify: NotifyConfig = field(default_factory=NotifyConfig)

    def resolved_api_key(self) -> str:
        if self.api_key.strip():
            return self.api_key.strip()
        provider = self.provider.lower().strip()
        names = ["SNIPAI_API_KEY"]
        if provider in {"gemini", "google"}:
            names += ["GEMINI_API_KEY", "GOOGLE_API_KEY"]
        elif provider == "anthropic":
            names += ["ANTHROPIC_API_KEY"]
        elif provider == "openrouter":
            names += ["OPENROUTER_API_KEY", "OPENAI_API_KEY"]
        else:
            names += [
                "OPENAI_API_KEY",
                "OPENROUTER_API_KEY",
                "GEMINI_API_KEY",
                "GOOGLE_API_KEY",
            ]
        for name in names:
            value = os.environ.get(name, "").strip()
            if value:
                return value
        return ""

    def resolved_shots_dir(self) -> Path:
        if self.shots_dir.strip():
            return Path(self.shots_dir).expanduser()
        return user_data_dir() / "shots"

    def resolved_base_url(self) -> str:
        if self.base_url.strip():
            return self.base_url.rstrip("/")
        provider = self.provider.lower().strip()
        if provider == "openai":
            return "https://api.openai.com/v1"
        if provider in {"gemini", "google"}:
            return "https://generativelanguage.googleapis.com/v1beta/openai"
        if provider == "openrouter":
            return "https://openrouter.ai/api/v1"
        if provider == "anthropic":
            return "https://api.anthropic.com"
        if provider == "ollama":
            return "http://127.0.0.1:11434"
        return os.environ.get("SNIPAI_BASE_URL", "").rstrip("/")


def _notify_from_dict(raw: Any) -> NotifyConfig:
    data = raw if isinstance(raw, dict) else {}
    defaults = NotifyConfig()
    return NotifyConfig(
        enabled=bool(data.get("enabled", defaults.enabled)),
        duration_ms=int(data.get("duration_ms", defaults.duration_ms)),
        max_chars=int(data.get("max_chars", defaults.max_chars)),
        position=str(data.get("position", defaults.position)),
        sound=bool(data.get("sound", defaults.sound)),
    )


def from_dict(raw: dict[str, Any] | None) -> Config:
    data = raw or {}
    defaults = Config()
    provider = str(os.environ.get("SNIPAI_PROVIDER") or data.get("provider", defaults.provider))
    model = str(os.environ.get("SNIPAI_MODEL") or data.get("model", defaults.model))
    hotkey = str(os.environ.get("SNIPAI_HOTKEY") or data.get("hotkey", defaults.hotkey))
    return Config(
        provider=provider,
        model=model,
        api_key=str(data.get("api_key", defaults.api_key)),
        base_url=str(data.get("base_url", defaults.base_url)),
        hotkey=hotkey,
        region_hotkey=str(data.get("region_hotkey", defaults.region_hotkey)),
        capture_mode=str(data.get("capture_mode", defaults.capture_mode)),
        clipboard=bool(data.get("clipboard", defaults.clipboard)),
        save_shots=bool(data.get("save_shots", defaults.save_shots)),
        shots_dir=str(data.get("shots_dir", defaults.shots_dir)),
        max_image_width=int(data.get("max_image_width", defaults.max_image_width)),
        system_prompt=str(data.get("system_prompt", defaults.system_prompt)),
        mock_reply=str(data.get("mock_reply", defaults.mock_reply)),
        notify=_notify_from_dict(data.get("notify")),
    )


def looks_like_gemini_key(key: str) -> bool:
    stripped = (key or "").strip()
    return stripped.startswith("AIza") or stripped.startswith("AQ.")


def infer_provider(api_key: str, fallback: str = "gemini") -> str:
    """Guess the provider from a pasted key so the user does not have to pick one."""
    stripped = (api_key or "").strip()
    if looks_like_gemini_key(stripped):
        return "gemini"
    if stripped.startswith("sk-ant"):
        return "anthropic"
    if stripped.startswith("sk-or-"):
        return "openrouter"
    if stripped.startswith("sk-"):
        return "openai"
    chosen = (fallback or "gemini").strip().lower() or "gemini"
    return chosen


def needs_setup(config: Config) -> bool:
    """True when the app cannot call a model until the user pastes a key."""
    provider = config.provider.lower().strip()
    if provider in {"mock", "ollama"}:
        return False
    return not bool(config.resolved_api_key())


def apply_setup(
    config: Config,
    *,
    api_key: str,
    provider: str | None = None,
    model: str | None = None,
) -> Config:
    """Fill provider, model, and api_key from the setup window or ``snip-ai init --key``."""
    key = (api_key or "").strip()
    chosen = (provider or "").strip().lower() or None
    inferred = infer_provider(key, fallback=chosen or config.provider or "gemini")
    # Honor an explicit non-default provider. If they left Gemini (the default)
    # and pasted an OpenAI/Anthropic key, switch automatically.
    if chosen and chosen != "gemini":
        provider_out = chosen
    elif key:
        provider_out = inferred
    else:
        provider_out = chosen or config.provider or "gemini"

    stock = set(DEFAULT_MODELS.values()) | set(LEGACY_GEMINI_MODELS)
    model_out = (model or "").strip() or config.model
    if not model_out or model_out in stock:
        model_out = DEFAULT_MODELS.get(provider_out, model_out or DEFAULT_GEMINI_MODEL)

    config.provider = provider_out
    config.model = model_out
    config.api_key = key
    return prepare_config(config)


def should_replace_gemini_model(model: str) -> bool:
    name = (model or "").strip()
    if not name or name.startswith("gpt-"):
        return True
    lower = name.lower()
    if lower in LEGACY_GEMINI_MODELS or lower.startswith("gemini-2.5-pro"):
        return True
    return False


def prepare_config(config: Config) -> Config:
    """Fill Gemini provider/model when the key or provider says Gemini."""
    provider = config.provider.lower().strip()
    key = config.resolved_api_key()
    if provider in {"gemini", "google"} or (
        provider in {"openai", "openai_compatible"} and looks_like_gemini_key(key)
    ):
        config.provider = "gemini"
        if should_replace_gemini_model(config.model):
            config.model = DEFAULT_GEMINI_MODEL
    return config


def load_config(path: Path | None = None) -> Config:
    config_path = resolve_config_path(path)
    if not config_path.exists():
        return prepare_config(from_dict({}))
    loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if loaded is None:
        return prepare_config(from_dict({}))
    if not isinstance(loaded, dict):
        raise SnipError(f"Config file must be a YAML mapping: {config_path}")
    file_model = str(loaded.get("model", "")).strip()
    config = prepare_config(from_dict(loaded))
    if file_model and file_model != config.model and should_replace_gemini_model(file_model):
        save_config(config, config_path)
    return config


def config_to_dict(config: Config) -> dict[str, Any]:
    data = asdict(config)
    return data


EXAMPLE_YAML = """# snip-ai config
# This is the live config (not config.example.yaml in the repo).
# Get a Gemini key at https://aistudio.google.com/api-keys

provider: gemini          # gemini | openai | anthropic | openrouter | openai_compatible | ollama | mock
model: gemini-3.1-pro-preview
api_key: ""               # paste your Gemini/OpenAI/Anthropic key here
base_url: ""              # optional override, e.g. http://127.0.0.1:11434/v1

# Global hotkeys. Use ctrl, alt, shift, cmd (Windows key / Command).
hotkey: ctrl+shift+space          # capture the monitor under the cursor
region_hotkey: ctrl+shift+period  # drag a rectangle, then solve that snip
capture_mode: screen              # screen | region  (used by `snip-ai once`)

clipboard: true           # copy the full answer so you can paste it
save_shots: false
shots_dir: ""
max_image_width: 1600

notify:
  enabled: true
  duration_ms: 8000
  max_chars: 180
  position: bottom-right  # bottom-right | bottom-left | top-right | top-left
  sound: false
"""


def _protect_config_file(path: Path) -> None:
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def write_example_config(path: Path | None = None) -> Path:
    config_path = path or default_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if config_path.exists():
        return config_path
    config_path.write_text(EXAMPLE_YAML, encoding="utf-8")
    _protect_config_file(config_path)
    return config_path


def save_config(config: Config, path: Path | None = None) -> Path:
    """Write the live settings file (used by the setup window)."""
    config_path = path or default_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {
        "provider": config.provider,
        "model": config.model,
        "api_key": config.api_key,
        "base_url": config.base_url,
        "hotkey": config.hotkey,
        "region_hotkey": config.region_hotkey,
        "capture_mode": config.capture_mode,
        "clipboard": config.clipboard,
        "save_shots": config.save_shots,
        "shots_dir": config.shots_dir,
        "max_image_width": config.max_image_width,
        "notify": asdict(config.notify),
    }
    if config.system_prompt != DEFAULT_SYSTEM_PROMPT:
        data["system_prompt"] = config.system_prompt
    if config.mock_reply:
        data["mock_reply"] = config.mock_reply
    header = (
        "# snip-ai settings\n"
        "# You can change the API key from the setup window (run snip-ai, or snip-ai init).\n"
    )
    config_path.write_text(header + yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    _protect_config_file(config_path)
    return config_path
