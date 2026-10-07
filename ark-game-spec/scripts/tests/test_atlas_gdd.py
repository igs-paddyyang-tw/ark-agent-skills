"""atlas v1.1：gdd-pack 入口（atlas_from_gdd）— 不需 ffmpeg，用最小 pack 走 compile → lint → build → register。"""
import json
import os
import pathlib
import subprocess
import sys

import pytest
import yaml

HERE = pathlib.Path(__file__).resolve().parent
SCRIPTS = HERE.parent
sys.path.insert(0, str(SCRIPTS.parent)); sys.path.insert(0, str(SCRIPTS / "atlas"))
import atlas_build  # noqa: E402
import atlas_lint  # noqa: E402

pytest.importorskip("PIL")


def sh(*args):
    r = subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    return r.returncode, json.loads(r.stdout.strip().splitlines()[-1])


def make_pack(d: pathlib.Path) -> pathlib.Path:
    from PIL import Image
    pack = d / "mini-pack"
    (pack / "rules").mkdir(parents=True)
    (pack / "assets" / "圖騰").mkdir(parents=True)
    (pack / "assets" / "全示意圖").mkdir(parents=True)
    Image.new("RGB", (640, 360), (40, 30, 20)).save(pack / "assets" / "全示意圖" / "main_01.png")
    Image.new("RGBA", (120, 120), (200, 160, 40, 255)).save(pack / "assets" / "圖騰" / "M1.png")
    gdd = {"contract": "1", "slug": "mini-slot", "title": "Mini Slot 素材總覽", "short_title": "Mini Slot", "domain": "slot-game",
           "status": "draft", "distribution": "internal",
           "assets": {"root": "assets", "symbols": "圖騰", "screens": "全示意圖"},
           "spec": [{"k": "盤面", "v": "主遊戲 3X5"}, {"k": "對獎方式", "v": "20 LINES"}],
           "symbol_groups": [{"id": "normal", "title": "一般圖騰"}],
           "features": [{"id": "main", "title": "MainGame", "rules": "rules/main.md"},
                        {"id": "fg", "title": "免費遊戲", "rules": "rules/fg.md"}],
           "open_questions": ["免費遊戲次數未定"]}
    (pack / "gdd.yaml").write_text(yaml.safe_dump(gdd, allow_unicode=True, sort_keys=False), encoding="utf-8")
    (pack / "symbols.yaml").write_text(yaml.safe_dump({"contract": "1", "symbols": [
        {"code": "M1", "group": "normal", "sym_id": 10, "name": "M1", "file": "M1.png", "odds": "x5 100 / x4 50 / x3 20"},
        {"code": "M2", "group": "normal", "sym_id": 11, "name": "M2", "file": None, "odds": None}]}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    (pack / "screens.yaml").write_text(yaml.safe_dump({"contract": "1", "screens": [
        {"feature": "main", "step": "1", "title": "主畫面", "file": "main_01.png", "desc": "", "lang": None}]}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    (pack / "info.yaml").write_text(yaml.safe_dump({"contract": "1", "langs": [{"id": "tw", "label": "繁中"}], "default_lang": "tw",
                                                     "placeholders": {}, "blocks": []}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    (pack / "i18n.csv").write_text("en,tw,usage\nMini Slot,迷你老虎機,\n", encoding="utf-8")
    (pack / "rules" / "main.md").write_text("### 主遊戲\n\n- 3 轉軸 5 列，20 條連線由左至右對獎。\n- `M1` 為最高倍率一般圖騰。\n\n| 連線 | 倍率 |\n|---|---|\n| x5 | 100 |\n", encoding="utf-8")
    (pack / "rules" / "fg.md").write_text("### 免費遊戲\n\n集滿 SC 進入免費遊戲。\n- 免費遊戲中可再觸發。\n", encoding="utf-8")
    return pack


def test_gdd_compile_lint_build_register(tmp_path):
    pack = make_pack(tmp_path)
    code, j = sh(SCRIPTS / "atlas" / "atlas_from_gdd.py", "--gdd", pack, "--out", tmp_path / "atlas")
    assert code == 0, j
    book = pathlib.Path(j["data"]["book"])
    assert book.name == "mini-slot" and j["data"]["features"] == ["main", "fg"]
    ay = yaml.safe_load((book / "atlas.yaml").read_text(encoding="utf-8"))
    assert ay["contract"] == "1.1" and ay["game"]["spec_source"] == "gdd-pack" and ay["distribution"] == "internal"
    figs = json.loads((book / "figures.json").read_text(encoding="utf-8"))["figures"]
    assert {f["type"] for f in figs} >= {"hero", "symbol_table"}
    assert all("source" in f for f in figs if f["type"] in ("asset", "symbol_table", "hero"))
    # 規則段：SPEC provenance、表格原樣
    fg = next(book.glob("*-fg.md")).read_text(encoding="utf-8")
    assert "- **SPEC** 集滿 SC 進入免費遊戲。" in fg and "- **SPEC** 免費遊戲中可再觸發。" in fg
    main = next(book.glob("*-main.md")).read_text(encoding="utf-8")
    assert "| x5 | 100 |" in main
    # sources 唯讀複本
    assert (book / "sources" / "gdd" / "rules" / "fg.md").exists() and (book / "sources" / "gdd" / "names.json").exists()
    rep = atlas_lint.lint(book)
    assert rep["summary"]["errors"] == 0, rep["violations"]
    code, j = sh(SCRIPTS / "atlas" / "atlas_build.py", "--book", book)
    assert code == 0 and atlas_build.check(book)["status"] == "OK"
    code, j = sh(SCRIPTS / "atlas" / "atlas_register.py", "--book", book, "--library", tmp_path / "lib")
    assert code == 0 and j["data"]["lint"] == "PASS"


def test_gdd_deterministic_and_stale(tmp_path):
    pack = make_pack(tmp_path)
    sh(SCRIPTS / "atlas" / "atlas_from_gdd.py", "--gdd", pack, "--out", tmp_path / "a1")
    sh(SCRIPTS / "atlas" / "atlas_from_gdd.py", "--gdd", pack, "--out", tmp_path / "a2")
    b1, b2 = tmp_path / "a1" / "mini-slot", tmp_path / "a2" / "mini-slot"
    for p in b1.glob("[0-9][0-9]-*.md"):
        assert p.read_bytes() == (b2 / p.name).read_bytes()
    f1 = json.loads((b1 / "figures.json").read_text(encoding="utf-8"))
    f2 = json.loads((b2 / "figures.json").read_text(encoding="utf-8"))
    assert [f["sha256"] for f in f1["figures"]] == [f["sha256"] for f in f2["figures"]]
    # 來源變了 → ATL-STALE
    os.chmod(b1 / "sources" / "gdd" / "rules" / "fg.md", 0o644)
    (b1 / "sources" / "gdd" / "rules" / "fg.md").write_text("### 免費遊戲\n\n改了。\n", encoding="utf-8")
    rep = atlas_lint.lint(b1)
    assert any(v["rule"] == "ATL-STALE" for v in rep["violations"])


def test_gdd_lint_rejects_foreign_number(tmp_path):
    pack = make_pack(tmp_path)
    _, j = sh(SCRIPTS / "atlas" / "atlas_from_gdd.py", "--gdd", pack, "--out", tmp_path / "atlas")
    book = pathlib.Path(j["data"]["book"])
    p = next(book.glob("*-fg.md"))
    p.write_text(p.read_text(encoding="utf-8") + "\n- **SPEC** 免費遊戲 7777 次。\n", encoding="utf-8")
    rep = atlas_lint.lint(book)
    assert any(v["rule"] == "ATL-NUM" for v in rep["violations"])


def test_run_gdd_entry(tmp_path):
    pack = make_pack(tmp_path)
    code, j = sh(SCRIPTS / "atlas" / "atlas_run.py", "--gdd", pack, "--out", tmp_path / "atlas", "--library", tmp_path / "lib")
    assert code == 0, j
    assert j["data"]["lint"] == "PASS" and (tmp_path / "lib" / "catalog.json").exists()
