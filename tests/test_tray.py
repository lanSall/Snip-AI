from snipai.tray import make_icon_image, tray_available


def test_make_icon_image():
    image = make_icon_image()
    assert image.size == (64, 64)
    assert image.mode == "RGBA"


def test_tray_available_off_linux_by_default(monkeypatch):
    monkeypatch.delenv("SNIPAI_TRAY", raising=False)
    monkeypatch.setattr("snipai.tray.os.name", "posix")
    assert tray_available() is False
