from pathlib import Path

from snipai.app import SnipApp
from snipai import SnipError
from snipai.config import Config
from snipai.solver import MockSolver
from snipai.__main__ import main


class FakeUI:
    def __init__(self) -> None:
        self.toasts: list[tuple[str, str]] = []

    def schedule(self, fn) -> None:
        fn()

    def show_toast(self, title: str, body: str, *, duration_ms: int | None = None) -> None:
        self.toasts.append((title, body))


def test_app_solve_png_notifies_and_copies(tiny_png: bytes, monkeypatch):
    copied = {}

    def fake_copy(text: str) -> bool:
        copied["text"] = text
        return True

    monkeypatch.setattr("snipai.app.copy_text", fake_copy)
    ui = FakeUI()
    app = SnipApp(Config(provider="mock", clipboard=True), MockSolver("ANSWER: 408\nWHY: 17×24."), ui)
    answer = app.solve_png(tiny_png, notify=True)
    assert "408" in answer
    assert ui.toasts[0][0] == "Answer"
    assert "408" in ui.toasts[0][1]
    assert "408" in copied["text"]


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


def test_sniperror_toast_survives_except_block(monkeypatch):
    queued = []

    class QueueUI:
        def schedule(self, fn) -> None:
            queued.append(fn)

        def show_toast(self, title: str, body: str, *, duration_ms: int | None = None) -> None:
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
