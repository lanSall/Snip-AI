from pathlib import Path


def test_committed_windows_exe_is_pe():
    path = Path(__file__).resolve().parents[1] / "snip-ai.exe"
    assert path.is_file(), "snip-ai.exe should live in the repo root for Windows users"
    data = path.read_bytes()
    assert data[:2] == b"MZ"
    # PE header offset at 0x3C
    pe_off = int.from_bytes(data[0x3C:0x40], "little")
    assert data[pe_off : pe_off + 4] == b"PE\0\0"
    # PE32+ magic 0x20B at optional header
    magic = int.from_bytes(data[pe_off + 24 : pe_off + 26], "little")
    assert magic in {0x10B, 0x20B}
    assert path.stat().st_size < 200_000
