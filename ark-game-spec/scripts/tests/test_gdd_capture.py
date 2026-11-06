"""gdd_capture（2.10.0）：實機取素材 → gdd-pack → 交付夾 → 單檔 → zip；守門：未遮蔽截圖、未知 code、同碼兩筆 symbol。"""
from __future__ import annotations
import json, pathlib, subprocess, sys, zipfile

import yaml

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
def png(path: pathlib.Path, color=(200, 40, 40)) -> None:
    from PIL import Image
    Image.new("RGB", (64, 64), color).save(path)


def make(tmp: pathlib.Path, **tweak) -> tuple[pathlib.Path, pathlib.Path]:
    cap = tmp / "cap"
    (cap / "圖騰").mkdir(parents=True)
    (cap / "截圖").mkdir()
    for n in ("HH_WW", "HH_M1", "HH_A", "HH_SS"):
        png(cap / "圖騰" / f"{n}.png")
    png(cap / "截圖" / "board_masked.png", (20, 60, 120))
    png(cap / "截圖" / "board_raw.png", (20, 60, 120))
    amap = {
        "contract": "1", "slug": "demo", "game": "測試機", "title_en": "Demo", "game_id": 1, "unlock_level": 45,
        "symbols": tweak.get("symbols", [
            {"code": "WW", "name": "WILD", "file": "圖騰/HH_WW.png", "group": "special"},
            {"code": "M1", "name": "高分一", "file": "圖騰/HH_M1.png", "group": "normal", "evidence": "贏分 ÷ 線注"},
            {"code": "A", "name": "A", "file": "圖騰/HH_A.png", "group": "normal"},
            {"code": "SS", "name": "SCATTER", "file": "圖騰/HH_SS.png", "group": "special"},
        ]),
        "screens": tweak.get("screens", [{"feature": "main", "step": "1", "title": "主盤面", "file": "截圖/board_masked.png"}]),
        "features": [{"id": "main", "title": "主遊戲", "rules": "### 規則\n\n- 5 × 3、50 線\n"}],
    }
    (cap / "asset-map.yaml").write_text(yaml.safe_dump(amap, allow_unicode=True), encoding="utf-8")
    (cap / "analysis.md").write_text("---\ntitle: 測試分析\n---\n\n# 測試分析\n\n結論一句。\n\n![M1](symbols/HH_M1.png)\n", encoding="utf-8")
    live = tmp / "live.json"
    live.write_text(json.dumps({"display_codes": [1, 11, 21, 2],
                                "odds": [[0, 10, 50, 200, 1000], [0, 10, 50, 200, 1000], [0, 0, 20, 75, 300], [0, 0, 0, 0, 0]]}), encoding="utf-8")
    return cap, live


def detail(d: dict) -> dict:
    """經 gs_run 派發時，runner 的錯誤細節包在 data.envelope。"""
    return ((d.get("data") or {}).get("envelope") or {}).get("data") or {}


def run(*args) -> dict:
    r = subprocess.run([sys.executable, "-X", "utf8", str(SCRIPTS / "gs_run.py"), "--stage", "capture", *map(str, args)],
                       capture_output=True, text=True, encoding="utf-8")
    return json.loads(r.stdout.strip().splitlines()[-1]) | {"rc": r.returncode}


def test_capture_full_chain(tmp_path):
    cap, live = make(tmp_path)
    out = tmp_path / "pack"
    d = run("--capture", cap, "--odds-json", live, "--out", out)
    assert d["rc"] == 0 and d["success"], d
    syms = {s["code"]: s for s in yaml.safe_load((out / "symbols.yaml").read_text(encoding="utf-8"))["symbols"]}
    assert syms["M1"]["odds"] == [1000, 200, 50] and syms["A"]["odds"] == [300, 75, 20]   # odds[符號][連線數−1] → [5,4,3]
    assert syms["M1"]["sym_id"] == 11 and syms["WW"]["odds"] is None                     # special 組不帶賠率
    assert (out / "export" / "測試機_素材總覽.html").is_file() and (out / "export" / "symbols" / "HH_M1.png").is_file()
    html = (out / "測試機_競品分析素材.html").read_text(encoding="utf-8")
    assert "測試分析" in html and 'src="symbols/' not in html                          # 單檔：圖已內嵌
    names = zipfile.ZipFile(d["data"]["zip"]).namelist()
    assert any(n.endswith("測試機_競品分析素材.html") for n in names) and any("/素材總覽/symbols/" in n for n in names)


def test_capture_blocks_unmasked_and_unknown(tmp_path):
    cap, live = make(tmp_path, screens=[{"feature": "main", "step": "1", "title": "未遮蔽", "file": "截圖/board_raw.png"}])
    d = run("--capture", cap, "--odds-json", live, "--out", tmp_path / "p1", "--no-zip")
    assert d["rc"] == 2 and detail(d)["unmasked"] == ["截圖/board_raw.png"]
    cap2, live2 = make(tmp_path / "b", symbols=[{"code": "M9", "name": "不存在", "file": "圖騰/HH_M1.png", "group": "normal"}])
    d = run("--capture", cap2, "--odds-json", live2, "--out", tmp_path / "p2", "--no-zip")
    assert d["rc"] == 2 and detail(d)["unknown_codes"] == ["M9"]


def test_capture_same_code_two_symbols_blocked(tmp_path):
    cap, live = make(tmp_path, symbols=[{"code": "WW", "name": "甲", "file": "圖騰/HH_WW.png", "group": "special"},
                                        {"code": "WW", "name": "乙", "file": "圖騰/HH_M1.png", "group": "special"}])
    d = run("--capture", cap, "--odds-json", live, "--out", tmp_path / "p", "--no-zip")
    assert d["rc"] == 2 and "role=symbol" in json.dumps(d, ensure_ascii=False)
