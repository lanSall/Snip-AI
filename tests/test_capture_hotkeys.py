from PIL import Image

from snipai.capture import Monitor, monitor_containing, prepare_png
from snipai.hotkeys import to_pynput


def test_to_pynput_space_and_period():
    assert to_pynput("ctrl+shift+space") == "<ctrl>+<shift>+<space>"
    assert to_pynput("ctrl+shift+period") == "<ctrl>+<shift>+."
    assert to_pynput("Ctrl-Alt-S") == "<ctrl>+<alt>+s"
    assert to_pynput("win+shift+a") == "<cmd>+<shift>+a"
    assert to_pynput("ctrl+shift+slash") == "<ctrl>+<shift>+/"
    assert to_pynput("ctrl+shift+comma") == "<ctrl>+<shift>+,"
    assert to_pynput("ctrl+shift+a") == "<ctrl>+<shift>+a"


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
