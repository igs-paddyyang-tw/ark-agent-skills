"""1.4.1：指紋新鮮度改比內容 —— 模板只是 mtime 較新（git checkout）不該拒跑；內容真的變了才拒跑。"""
from __future__ import annotations

import os
import pathlib
import sys

import pytest

SCRIPTS = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))
import doc_lint as D  # noqa: E402


def _newest_template() -> pathlib.Path:
    return sorted(D.TEMPLATES_DIR.rglob("*.md"))[0]


def test_newer_mtime_same_content_is_fresh():
    md = _newest_template()
    st = md.stat()
    try:
        future = D.FINGERPRINTS.stat().st_mtime + 3600
        os.utime(md, (future, future))
        assert D.load_fingerprints()["lines"]        # 不 exit
    finally:
        os.utime(md, (st.st_atime, st.st_mtime))


def test_changed_template_content_is_stale():
    md = _newest_template()
    old = md.read_bytes()
    try:
        md.write_text(old.decode("utf-8") + "\n反證用的新模板內容行，指紋裡一定沒有這一行\n", encoding="utf-8")
        with pytest.raises(SystemExit) as e:
            D.load_fingerprints()
        assert e.value.code == 2
    finally:
        md.write_bytes(old)
