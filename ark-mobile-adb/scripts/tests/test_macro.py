"""v2.1：macro DSL（lint 反證 / fake replay / explain）、getevent 解析、座標換算、batch 單進程、reconnect 判斷。"""
import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import aiqa_common as C  # noqa: E402
import aiqa_macro as MC  # noqa: E402
import ark_mobile_adb as M  # noqa: E402

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
DEMO_MACRO = SCRIPTS.parent / "gamepacks" / "demo-slot" / "macros" / "enter-and-spin.yaml"


def test_macro_lint_and_replay_fake(tmp_path):
    m = MC.load_macro(DEMO_MACRO); pack = C.load_pack("demo-slot")
    assert [v for v in MC.lint(m, pack) if v["severity"] == "error"] == []
    r = MC.replay(m, "fake", None, tmp_path / "out", dry=False)
    assert r["ok"] and r["values"]["bet"] == 100 and "win" in r["values"] and r["shots"] >= 5
    assert (tmp_path / "out" / "summary.json").exists()


def test_macro_lint_counterexamples():
    pack = C.load_pack("demo-slot")
    bad = {"macro": "x", "game": "demo-slot", "resolution": {"width": 1600, "height": 900},
           "steps": [{"tap": [540, 918 * 2]}, {"tap": "btn:nope"}, {"fly": 1}, {"checkpoint": {"screen": "mars"}}]}
    rules = {v["rule"] for v in MC.lint(bad, pack) if v["severity"] == "error"}
    assert {"MC-COORD", "MC-TARGET", "MC-STEP", "MC-SCREEN"} <= rules
    blind = {"macro": "x", "game": "demo-slot", "resolution": {"width": 1600, "height": 900}, "steps": [{"tap": [1, 1]}]}
    assert any(v["rule"] == "MC-BLIND" for v in MC.lint(blind, pack))
    wrong_res = dict(bad, resolution={"width": 720, "height": 1280}, steps=[{"checkpoint": {"screen": "lobby"}}])
    assert any(v["rule"] == "MC-RES" for v in MC.lint(wrong_res, pack))


def test_macro_checkpoint_fail_stops(tmp_path):
    m = {"macro": "cp", "game": "demo-slot", "resolution": {"width": 1600, "height": 900},
         "steps": [{"checkpoint": {"screen": "info_page"}}, {"tap": "btn:spin"}]}   # fake 開機在 lobby → 第一步就該 FAIL
    r = MC.replay(m, "fake", None, tmp_path / "o", dry=False)
    assert not r["ok"] and r["fails"][0]["step"] == "checkpoint" and r["steps"] == 1


def test_explain_renders_sop():
    txt = MC.explain(MC.load_macro(DEMO_MACRO))
    assert "檢查點" in txt and "重複" in txt and txt.startswith("# SOP")


def test_getevent_parse_scales_to_wm_size():
    raw = """[   12.100000] /dev/input/event2: EV_ABS       ABS_MT_TRACKING_ID   00000001
[   12.100100] /dev/input/event2: EV_KEY       BTN_TOUCH            DOWN
[   12.100200] /dev/input/event2: EV_ABS       ABS_MT_POSITION_X    00007fff
[   12.100300] /dev/input/event2: EV_ABS       ABS_MT_POSITION_Y    00003fff
[   12.180000] /dev/input/event2: EV_KEY       BTN_TOUCH            UP
[   12.180100] /dev/input/event2: EV_ABS       ABS_MT_TRACKING_ID   ffffffff
[   15.000000] /dev/input/event2: EV_KEY       BTN_TOUCH            DOWN
[   15.000100] /dev/input/event2: EV_ABS       ABS_MT_POSITION_X    00000000
[   15.000200] /dev/input/event2: EV_ABS       ABS_MT_POSITION_Y    00007fff
[   15.050000] /dev/input/event2: EV_KEY       BTN_TOUCH            UP
"""
    taps = MC.parse_getevent(raw, (32767, 32767), (720, 1280))
    assert len(taps) == 2 and taps[0]["x"] == 720 and taps[0]["y"] == 640 and taps[1] == {"t": 15.0, "x": 0, "y": 1280, "hold_ms": 50}
    m = MC.taps_to_macro(taps, "rec", "ghy", "panda", (720, 1280))
    kinds = [next(iter(s)) for s in m["steps"]]
    assert kinds == ["tap", "wait_stable", "tap", "shot"] and m["resolution"] == {"width": 720, "height": 1280}


def test_coordinate_basis():
    assert M.to_device_xy(540, 918, (540, 960), (720, 1280)) == (720, 1224)   # 分析文件裡點空三次的那個 y
    assert M.color_close([60, 180, 90], [70, 170, 100], 10) and not M.color_close([0, 0, 0], [40, 0, 0], 30)


def test_thumb_meta(tmp_path):
    from PIL import Image
    Image.new("RGB", (720, 1280), (5, 5, 5)).save(tmp_path / "s.png")
    meta = M.make_thumb(tmp_path / "s.png", 540, tmp_path / "t.png", (720, 1280))
    assert meta["thumb_size"] == [540, 960] and abs(meta["scale"] - 1.3333) < 1e-3 and (tmp_path / "t.png.meta.json").exists()


def test_batch_single_process_runs_all_lines(tmp_path):
    f = tmp_path / "b.txt"
    f.write_text("# 註解\nto-device 1 1 --basis 540x960\ncrop --src nope.png --rect 0,0,1,1 --out x.png\n", encoding="utf-8")
    r = subprocess.run([sys.executable, str(SCRIPTS / "ark_mobile_adb.py"), "--json", "batch", "--file", str(f), "--keep-going"],
                       capture_output=True, text=True, env={"PATH": "/nonexistent", "PYTHONIOENCODING": "utf-8"})
    j = json.loads(r.stdout)
    assert j["data"]["steps"] == 2 and all("error" in x or x["rc"] != 0 for x in j["data"]["results"])  # 無 adb / 無檔案 → 兩行都失敗但都有跑
