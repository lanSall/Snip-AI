from types import SimpleNamespace

from PIL import Image

from snipai.capture import Monitor, monitor_containing, prepare_png
from snipai.hotkeys import (
    canonical_from_button,
    format_binding,
    normalize_binding,
    parse_binding,
    to_pynput,
    validate_binding,
)


def test_to_pynput_space_and_period():
    assert to_pynput("ctrl+shift+space") == "<ctrl>+<shift>+<space>"
    assert to_pynput("ctrl+shift+period") == "<ctrl>+<shift>+."
    assert to_pynput("Ctrl-Alt-S") == "<ctrl>+<alt>+s"
    assert to_pynput("win+shift+a") == "<shift>+<cmd>+a"
    assert to_pynput("ctrl+shift+slash") == "<ctrl>+<shift>+/"
    assert to_pynput("ctrl+shift+comma") == "<ctrl>+<shift>+,"
    assert to_pynput("ctrl+shift+a") == "<ctrl>+<shift>+a"


def test_parse_mouse_and_keyboard_bindings():
    assert parse_binding("mouse4").canonical() == "mouse4"
    assert parse_binding("x1").canonical() == "mouse4"
    assert parse_binding("ctrl+mouse5").canonical() == "ctrl+mouse5"
    assert parse_binding("mouse_middle").is_mouse is True
    assert parse_binding("ctrl+shift+period").canonical() == "ctrl+shift+period"
    assert parse_binding("ctrl+left").key == "left"


def test_format_binding_labels():
    assert format_binding("ctrl+shift+space") == "Ctrl+Shift+Space"
    assert "Mouse 4" in format_binding("mouse4")
    assert format_binding("mouse_middle") == "Middle click"


def test_validate_binding_rejects_left_click_and_bare_letters():
    assert validate_binding("mouse_left")
    assert validate_binding("a")
    assert validate_binding("space")
    assert validate_binding("mouse4") is None
    assert validate_binding("ctrl+shift+a") is None
    assert validate_binding("f13") is None
    assert validate_binding("mouse_right")


def test_normalize_binding_aliases():
    assert normalize_binding("Ctrl+Shift+Period") == "ctrl+shift+period"
    assert normalize_binding("button8") == "mouse4"


def test_canonical_from_button():
    assert canonical_from_button(SimpleNamespace(name="x1")) == "mouse4"
    assert canonical_from_button(SimpleNamespace(name="button8")) == "mouse4"
    assert canonical_from_button(SimpleNamespace(name="x2")) == "mouse5"
    assert canonical_from_button(SimpleNamespace(name="middle")) == "mouse_middle"
    assert canonical_from_button(SimpleNamespace(name="left")) == "mouse_left"
    assert canonical_from_button(SimpleNamespace(name="scroll_up")) is None


def test_to_pynput_rejects_mouse():
    try:
        to_pynput("mouse4")
        assert False, "expected SnipError"
    except Exception as exc:
        assert "mouse" in str(exc).lower()


def test_start_hotkeys_splits_mouse(monkeypatch):
    from snipai.hotkeys import start_hotkeys

    created: dict[str, object] = {}

    class FakeHotKeys:
        def __init__(self, mapping):
            created["kb"] = mapping

        def start(self):
            created["kb_start"] = True

        def stop(self):
            created["kb_stop"] = True

    class FakeListener:
        def __init__(self, **kwargs):
            created.setdefault("extra", []).append(kwargs)

        def start(self):
            return None

        def stop(self):
            return None

    monkeypatch.setattr("pynput.keyboard.GlobalHotKeys", FakeHotKeys)
    monkeypatch.setattr("pynput.keyboard.Listener", FakeListener)
    monkeypatch.setattr("pynput.mouse.Listener", FakeListener)

    fired = []
    listener = start_hotkeys(
        {
            "ctrl+shift+space": lambda: fired.append("screen"),
            "mouse4": lambda: fired.append("snip"),
        }
    )
    assert "<ctrl>+<shift>+<space>" in created["kb"]
    assert any("on_click" in item for item in created["extra"])
    listener.stop()
    assert created.get("kb_stop") is True


def test_monitor_containing_picks_the_screen_under_the_point():
    monitors = [
        Monitor(1, 0, 0, 1920, 1080),
        Monitor(2, 1920, 0, 1280, 1024),
    ]
    assert monitor_containing(100, 100, monitors).index == 1
    assert monitor_containing(2000, 10, monitors).index == 2


def test_monitor_containing_falls_back_to_first():
    monitors = [Monitor(1, 0, 0, 800, 600)]
    assert monitor_containing(-20, -20, monitors).index == 1


def test_prepare_png_resizes_wide_images():
    image = Image.new("RGB", (2000, 500), color=(255, 0, 0))
    png = prepare_png(image, max_width=400)
    from snipai.capture import image_from_png

    out = image_from_png(png)
    assert out.width == 400
    assert out.height == 100
