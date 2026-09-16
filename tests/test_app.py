from pathlib import Path

from snipai.app import SnipApp
from snipai import SnipError
from snipai.config import Config
from snipai.solver import MockSolver
from snipai.__main__ import main


class FakeUI:
    def __init__(self) -> None:
        self.toasts: list[tuple[str, str]] = []
        self.last_on_click = None

    def schedule(self, fn) -> None:
        fn()

    def show_toast(
        self, title: str, body: str, *, duration_ms: int | None = None, on_click=None, actions=None
    ) -> None:
        self.toasts.append((title, body))
        self.last_on_click = on_click
        self.last_actions = actions


def test_app_solve_png_notifies_and_copies(tiny_png: bytes, monkeypatch):
    copied = {}

    def fake_copy(text: str) -> bool:
        copied["text"] = text
        return True

    monkeypatch.setattr("snipai.app.copy_text", fake_copy)
    ui = FakeUI()
    from snipai.history import AnswerHistory

    hist = AnswerHistory()
    app = SnipApp(
        Config(provider="mock", clipboard=True),
        MockSolver("ANSWER: 408\nWHY: 17×24."),
        ui,
        history=hist,
    )
    answer = app.solve_png(tiny_png, notify=True)
    assert "408" in answer
    assert ui.toasts[0][0] == "Answer"
    assert "408" in ui.toasts[0][1]
    assert "408" in copied["text"]
    assert hist.entries[0].headline == "408"
    assert "17×24" in hist.entries[0].full
    assert callable(ui.last_on_click)
    labels = [label for label, _cb in ui.last_actions]
    assert labels == ["Retry", "Follow up"]


def test_cli_solve_no_notify(math_problem_png: Path, tmp_path: Path, capsys, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    config = tmp_path / "config.yaml"
    config.write_text("provider: mock\nclipboard: false\n", encoding="utf-8")
    code = main(["--config", str(config), "solve", str(math_problem_png), "--no-notify"])
    captured = capsys.readouterr()
    assert code == 0
    assert "ANSWER:" in captured.out or "42" in captured.out


def test_cli_init(tmp_path: Path, capsys):
    path = tmp_path / "config.yaml"
    code = main(["--config", str(path), "init"])
    assert code == 0
    assert path.exists()
    assert "provider:" in path.read_text(encoding="utf-8")


def test_cli_init_with_key(tmp_path: Path, capsys):
    path = tmp_path / "config.yaml"
    code = main(["--config", str(path), "init", "--key", "AIzaSyTESTKEY"])
    assert code == 0
    text = path.read_text(encoding="utf-8")
    assert "AIzaSyTESTKEY" in text
    assert "gemini-3.8-flash" in text
    captured = capsys.readouterr()
    assert "Saved" in captured.out


def test_cli_init_openai_key_infers_provider(tmp_path: Path):
    path = tmp_path / "config.yaml"
    assert main(["--config", str(path), "init", "--key", "sk-proj-abc"]) == 0
    text = path.read_text(encoding="utf-8")
    assert "provider: openai" in text
    assert "sk-proj-abc" in text


def test_cli_solve_without_key_asks_for_setup(tmp_path: Path, math_problem_png: Path, monkeypatch, capsys):
    for name in (
        "OPENAI_API_KEY",
        "SNIPAI_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "ANTHROPIC_API_KEY",
        "OPENROUTER_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    config = tmp_path / "empty.yaml"
    config.write_text("provider: gemini\napi_key: ''\n", encoding="utf-8")
    code = main(["--config", str(config), "solve", str(math_problem_png), "--no-notify"])
    captured = capsys.readouterr()
    assert code == 1
    assert "setup" in captured.err.lower() or "API key" in captured.err


def test_open_settings_reloads_key_and_model(tmp_path: Path, monkeypatch):
    from snipai.config import apply_setup, from_dict, save_config

    path = tmp_path / "config.yaml"
    cfg = apply_setup(
        from_dict({}),
        api_key="AIza-old",
        provider="gemini",
        model="gemini-3.8-flash",
    )
    save_config(cfg, path)

    def fake_wizard(config, **kwargs):
        assert kwargs.get("running") is True
        return apply_setup(
            config,
            api_key="AIza-new",
            provider="gemini",
            model="gemini-3.1-flash-lite",
        )

    monkeypatch.setattr("snipai.setup_ui.run_setup_wizard", fake_wizard)
    ui = FakeUI()
    app = SnipApp(cfg, MockSolver("ANSWER: 1\nWHY: x"), ui, config_path=path)
    app.open_settings()
    assert app.config.api_key == "AIza-new"
    assert app.config.model == "gemini-3.1-flash-lite"
    saved = path.read_text(encoding="utf-8")
    assert "AIza-new" in saved
    assert "gemini-3.1-flash-lite" in saved
    assert any("gemini-3.1-flash-lite" in body for _title, body in ui.toasts)


def test_open_settings_restarts_hotkeys_with_mouse_bind(tmp_path: Path, monkeypatch):
    from snipai.config import apply_setup, from_dict, save_config

    path = tmp_path / "config.yaml"
    cfg = apply_setup(from_dict({}), api_key="AIza-old", provider="gemini")
    save_config(cfg, path)
    seen: list[set[str]] = []

    def fake_start(bindings):
        seen.append(set(bindings))

        class Listener:
            def stop(self) -> None:
                return None

        return Listener()

    def fake_wizard(config, **kwargs):
        updated = apply_setup(
            config,
            api_key="AIza-old",
            provider="gemini",
            model=config.model,
        )
        updated.region_hotkey = "mouse4"
        return updated

    monkeypatch.setattr("snipai.app.start_hotkeys", fake_start)
    monkeypatch.setattr("snipai.setup_ui.run_setup_wizard", fake_wizard)
    ui = FakeUI()
    app = SnipApp(cfg, MockSolver("ANSWER: 1\nWHY: x"), ui, config_path=path)
    app._hotkeys_running = True
    app.open_settings()
    assert app.config.region_hotkey == "mouse4"
    assert any("mouse4" in keys for keys in seen)


def test_open_settings_cancel_leaves_config(tmp_path: Path, monkeypatch):
    from snipai.config import apply_setup, from_dict, save_config

    path = tmp_path / "config.yaml"
    cfg = apply_setup(from_dict({}), api_key="AIza-keep", provider="gemini")
    save_config(cfg, path)
    monkeypatch.setattr("snipai.setup_ui.run_setup_wizard", lambda *a, **k: None)
    ui = FakeUI()
    app = SnipApp(cfg, MockSolver(), ui, config_path=path)
    app.open_settings()
    assert app.config.api_key == "AIza-keep"


def test_open_settings_without_path_toasts():
    ui = FakeUI()
    app = SnipApp(Config(provider="mock"), MockSolver(), ui)
    app.open_settings()
    assert any("settings file" in body.lower() for _title, body in ui.toasts)


def test_open_history_without_root_does_not_crash():
    ui = FakeUI()
    app = SnipApp(Config(provider="mock"), MockSolver(), ui)
    app.open_history()
    assert ui.toasts == []


def test_run_hotkeys_binds_settings(monkeypatch):
    seen: dict[str, set[str]] = {}

    class LoopUI(FakeUI):
        def mainloop(self) -> None:
            return

    def fake_start(bindings):
        seen["keys"] = set(bindings)

        class Listener:
            def stop(self) -> None:
                return None

        return Listener()

    monkeypatch.setattr("snipai.app.start_hotkeys", fake_start)
    ui = LoopUI()
    app = SnipApp(Config(), MockSolver(), ui)
    app.run_hotkeys()
    assert "ctrl+shift+space" in seen["keys"]
    assert "ctrl+shift+period" in seen["keys"]
    assert "ctrl+shift+slash" in seen["keys"]
    assert "ctrl+shift+a" in seen["keys"]


def test_open_ask_without_root_does_not_crash():
    ui = FakeUI()
    app = SnipApp(Config(provider="mock"), MockSolver(), ui)
    app.open_ask()
    assert ui.toasts == []


def test_app_solve_question_notifies_and_copies(monkeypatch):
    copied = {}

    def fake_copy(text: str) -> bool:
        copied["text"] = text
        return True

    monkeypatch.setattr("snipai.app.copy_text", fake_copy)
    ui = FakeUI()
    from snipai.history import AnswerHistory

    hist = AnswerHistory()
    app = SnipApp(
        Config(provider="mock", clipboard=True),
        MockSolver("ANSWER: 4\nWHY: 2+2."),
        ui,
        history=hist,
    )
    answer = app.solve_question("What is 2+2?", notify=True)
    assert "4" in answer
    assert ui.toasts[0][0] == "Answer"
    assert "4" in copied["text"]
    assert hist.entries[0].headline == "4"
    assert ui.last_actions is None


def test_ask_job_sniperror_toast(monkeypatch):
    queued = []

    class QueueUI:
        def schedule(self, fn) -> None:
            queued.append(fn)

        def show_toast(
            self, title: str, body: str, *, duration_ms: int | None = None, on_click=None, actions=None
        ) -> None:
            self.seen = (title, body)

    ui = QueueUI()
    app = SnipApp(Config(provider="mock", clipboard=False), MockSolver(), ui)
    app._ask_job("   ")
    assert queued, "toast callback should be queued"
    for fn in queued:
        fn()
    assert ui.seen[0] == "snip-ai"
    assert "Type a question" in ui.seen[1]


def test_sniperror_toast_survives_except_block(monkeypatch):
    queued = []

    class QueueUI:
        def schedule(self, fn) -> None:
            queued.append(fn)

        def show_toast(
            self, title: str, body: str, *, duration_ms: int | None = None, on_click=None, actions=None
        ) -> None:
            self.seen = (title, body)

    ui = QueueUI()
    app = SnipApp(Config(provider="mock", clipboard=False), MockSolver(), ui)
    monkeypatch.setattr(app, "_capture", lambda mode: (_ for _ in ()).throw(SnipError("No API key. demo")))
    app._job("screen")
    assert queued, "toast callback should be queued"
    for fn in queued:
        fn()
    assert ui.seen[0] == "snip-ai"
    assert "No API key" in ui.seen[1]


def test_retry_last_without_snip_toasts():
    ui = FakeUI()
    app = SnipApp(Config(provider="mock", clipboard=False), MockSolver(), ui)
    app.retry_last()
    assert any("Snip something first" in body for _title, body in ui.toasts)


def test_open_follow_up_without_snip_toasts():
    ui = FakeUI()
    app = SnipApp(Config(provider="mock", clipboard=False), MockSolver(), ui)
    app.open_follow_up()
    assert any("Snip something first" in body for _title, body in ui.toasts)


def test_retry_job_reuses_last_png(tiny_png: bytes, monkeypatch):
    monkeypatch.setattr("snipai.app.copy_text", lambda text: True)
    ui = FakeUI()
    solver = MockSolver("ANSWER: 1\nWHY: first.")
    seen: list[bytes] = []
    original = solver.solve

    def wrap(png: bytes) -> str:
        seen.append(png)
        return original(png)

    solver.solve = wrap  # type: ignore[method-assign]
    app = SnipApp(Config(provider="mock", clipboard=False), solver, ui)
    app.solve_png(tiny_png, notify=False)
    solver.reply = "ANSWER: 2\nWHY: retry."
    app._retry_job()
    assert seen == [tiny_png, tiny_png]
    assert app._last_answer.startswith("ANSWER: 2")


def test_solve_follow_up_uses_last_snip(tiny_png: bytes, monkeypatch):
    monkeypatch.setattr("snipai.app.copy_text", lambda text: True)
    ui = FakeUI()
    solver = MockSolver("ANSWER: 9\nWHY: follow.")
    app = SnipApp(Config(provider="mock", clipboard=False), solver, ui)
    app.solve_png(tiny_png, notify=False)
    answer = app.solve_follow_up("Why 9?", notify=True)
    assert "9" in answer
    assert solver.last_follow_up == "Why 9?"
    labels = [label for label, _cb in ui.last_actions]
    assert "Retry" in labels and "Follow up" in labels


def test_on_ask_submit_routes_follow_up():
    ui = FakeUI()
    app = SnipApp(Config(provider="mock", clipboard=False), MockSolver(), ui)
    seen: list[tuple[str, str]] = []
    app._start_follow_up_job = lambda q: seen.append(("fu", q))  # type: ignore[method-assign]
    app._start_ask_job = lambda q: seen.append(("ask", q))  # type: ignore[method-assign]
    app._on_ask_submit("about the snip", use_last_snip=True)
    app._on_ask_submit("plain ask", use_last_snip=False)
    assert seen == [("fu", "about the snip"), ("ask", "plain ask")]


def test_pause_unbinds_capture_keeps_settings(monkeypatch):
    seen: list[set[str]] = []

    def fake_start(bindings):
        seen.append(set(bindings))

        class Listener:
            def stop(self) -> None:
                return None

        return Listener()

    monkeypatch.setattr("snipai.app.start_hotkeys", fake_start)
    ui = FakeUI()
    app = SnipApp(Config(), MockSolver(), ui)
    app._hotkeys_running = True
    app._start_hotkey_listener()
    assert "ctrl+shift+space" in seen[-1]
    assert "ctrl+shift+a" in seen[-1]
    assert "ctrl+shift+slash" in seen[-1]
    app.toggle_pause()
    assert app.is_paused() is True
    assert seen[-1] == {"ctrl+shift+slash"}
    assert any("paused" in body.lower() for _title, body in ui.toasts)
    app.toggle_pause()
    assert app.is_paused() is False
    assert "ctrl+shift+space" in seen[-1]
    assert "ctrl+shift+a" in seen[-1]
    assert any("Shortcuts on" in body for _title, body in ui.toasts)


def test_open_settings_copies_toast_duration(tmp_path: Path, monkeypatch):
    from snipai.config import NotifyConfig, apply_setup, from_dict, save_config

    path = tmp_path / "config.yaml"
    cfg = apply_setup(from_dict({}), api_key="AIza-old", provider="gemini")
    save_config(cfg, path)

    def fake_wizard(config, **kwargs):
        updated = apply_setup(config, api_key="AIza-old", provider="gemini", model=config.model)
        updated.notify = NotifyConfig(duration_ms=0)
        updated.prompt_style = "explain"
        return updated

    monkeypatch.setattr("snipai.setup_ui.run_setup_wizard", fake_wizard)
    ui = FakeUI()
    ui.notify = cfg.notify
    app = SnipApp(cfg, MockSolver(), ui, config_path=path)
    app.open_settings()
    assert app.config.notify.duration_ms == 0
    assert app.config.prompt_style == "explain"
    assert ui.notify.duration_ms == 0
