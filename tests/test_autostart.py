from pathlib import Path

from snipai import autostart


def test_autostart_writes_and_removes_windows_vbs(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(autostart, "_windows", lambda: True)
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(autostart, "project_root", lambda: tmp_path)
    fake_python = tmp_path / "python.exe"
    monkeypatch.setattr(autostart.sys, "executable", str(fake_python))

    path = autostart.set_enabled(True)
    assert path is not None
    assert path == tmp_path / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "snip-ai.vbs"
    body = path.read_text(encoding="utf-8")
    assert "WScript.Shell" in body
    assert "pythonw.exe" in body
    assert "-m snipai run" in body
    assert autostart.is_enabled()

    autostart.set_enabled(False)
    assert not path.exists()
    assert not autostart.is_enabled()


def test_autostart_prefers_snip_ai_exe(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(autostart, "_windows", lambda: True)
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(autostart, "project_root", lambda: tmp_path)
    (tmp_path / "snip-ai.exe").write_bytes(b"MZ")
    path = autostart.set_enabled(True)
    body = path.read_text(encoding="utf-8")
    assert "snip-ai.exe" in body
    assert "-m snipai run" not in body


def test_autostart_linux_desktop(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(autostart, "_windows", lambda: False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    path = autostart.set_enabled(True)
    assert path == tmp_path / "autostart" / "snip-ai.desktop"
    text = path.read_text(encoding="utf-8")
    assert text.startswith("[Desktop Entry]")
    assert "snip-ai" in text
    autostart.set_enabled(False)
    assert not path.exists()
