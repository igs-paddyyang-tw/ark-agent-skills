"""wiki_index build 在沒有刪除權限的資料夾也要成功（aidev 2026-10-22 階段報告 F-10）

修前：舊 .index／殘留 .index.tmp 用 shutil.rmtree 刪除，PermissionError 直接中斷 build。
修後：刪不掉就改名成 .index.old-<時間>，build 照常完成並在輸出帶 warnings。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

pytest.importorskip("fcntl", reason="wiki_index 用 fcntl 取 .index.lock，只在 POSIX（Linux／WSL／macOS）可跑")
import wiki_index  # noqa: E402


def _wiki(tmp: Path) -> Path:
    w = tmp / "wiki"
    (w / "a").mkdir(parents=True)
    (w / "a" / "p1.md").write_text("---\ntitle: p1\ntype: concept\ntags: [x]\n---\n\n# p1\n內容 [[p2]]\n", encoding="utf-8")
    (w / "a" / "p2.md").write_text("---\ntitle: p2\ntype: concept\ntags: [x]\n---\n\n# p2\n內容\n", encoding="utf-8")
    return w


def _build(w: Path) -> dict:
    r = subprocess.run([sys.executable, str(SCRIPTS / "wiki_index.py"), "build", "--wiki_dir", str(w)], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads(r.stdout)


def test_discard_falls_back_to_rename(tmp_path, monkeypatch):
    d = tmp_path / ".index"
    d.mkdir()
    (d / ".gitignore").write_text("*\n", encoding="utf-8")

    def deny(*_a, **_k):
        raise PermissionError("Operation not permitted")
    monkeypatch.setattr(shutil, "rmtree", deny)
    w = wiki_index._discard(d)
    assert w and ".index.old-" in w
    assert not d.exists()
    assert len(list(tmp_path.glob(".index.old-*"))) == 1


def test_build_twice_and_with_leftover_tmp(tmp_path):
    w = _wiki(tmp_path)
    assert _build(w)["manifest"]["page_count"] == 2
    (w / ".index.tmp").mkdir()
    (w / ".index.tmp" / "junk").write_text("x", encoding="utf-8")
    out = _build(w)
    assert out["ok"] and out["warnings"] == []
    assert (w / ".index" / "manifest.json").is_file() and not (w / ".index.tmp").exists()
