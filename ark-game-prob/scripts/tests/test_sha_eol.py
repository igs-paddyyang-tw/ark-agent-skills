"""sha16 跨作業系統：文字檔 CRLF／LF 同一個 sha；舊版（原始位元組）戳記照樣接受；二進位不正規化（2026-11-19）。"""
from __future__ import annotations

import hashlib
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import ps_common as C  # noqa: E402


def test_crlf_and_lf_same_sha(tmp_path: pathlib.Path):
    lf, crlf = tmp_path / "a.md", tmp_path / "b.md"
    lf.write_bytes("# 標題\n內容\n".encode())
    crlf.write_bytes("# 標題\r\n內容\r\n".encode())
    assert C.sha16(lf) == C.sha16(crlf)


def test_legacy_crlf_stamp_accepted_on_lf_checkout(tmp_path: pathlib.Path):
    p = tmp_path / "x.md"
    p.write_bytes(b"a\nb\n")
    legacy = hashlib.sha256(b"a\r\nb\r\n").hexdigest()[:16]  # Windows 算出的舊戳記
    assert C.sha16_ok(p, legacy)
    assert C.sha16_ok(p, C.sha16(p))
    assert not C.sha16_ok(p, "0" * 16)
    assert not C.sha16_ok(p, None)


def test_binary_untouched(tmp_path: pathlib.Path):
    p = tmp_path / "x.bin"
    raw = b"\x00\x01\r\n\x02"
    p.write_bytes(raw)
    assert C.sha16(p) == hashlib.sha256(raw).hexdigest()[:16]
