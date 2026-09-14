import os

import pytest

from snipai.capture import prepare_png, snapshot_current
from snipai.config import NotifyConfig
from snipai.ui import ToastUI


pytestmark = pytest.mark.skipif(not os.environ.get("DISPLAY") and os.name != "nt", reason="needs a display")


def test_list_and_grab_current_monitor():
    monitor, image = snapshot_current()
    assert monitor.width > 0 and monitor.height > 0
    assert image.size[0] > 0 and image.size[1] > 0
    png = prepare_png(image, max_width=800)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_toast_does_not_crash():
    ui = ToastUI(NotifyConfig(duration_ms=50, position="bottom-right"))
    try:
        ui.show_toast("Answer", "408")
        ui.root.update()
        assert ui._toast is not None
        ui._close_toast()
        ui.root.update()
        assert ui._toast is None
    finally:
        ui.destroy()
