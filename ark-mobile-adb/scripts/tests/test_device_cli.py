"""裝置層 CLI：parse_devices、envelope / exit code、crop、frame_diff、locate。"""
import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import ark_mobile_adb as m  # noqa: E402

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "ark_mobile_adb.py"


def test_parse_devices():
    rows = m.parse_devices("List of devices attached\n127.0.0.1:5555 device product:p3 model:SM_G998B transport_id:2\nemulator-5554 offline\n")
    assert rows[0]["serial"] == "127.0.0.1:5555" and rows[0]["state"] == "device" and rows[0]["model"] == "SM_G998B"
    assert rows[1]["state"] == "offline"


def test_json_envelope_on_error(monkeypatch):
    monkeypatch.setattr(m, "find_adb", lambda: None)
    r = subprocess.run([sys.executable, str(SCRIPT), "--json", "devices"], capture_output=True, text=True, env={"PATH": "/nonexistent", "PYTHONIOENCODING": "utf-8"})
    j = json.loads(r.stdout)
    assert j["success"] is False and j["error"]["code"] == "DRIVER_MISSING" and r.returncode == 8


def test_crop_diff_locate(tmp_path):
    from PIL import Image, ImageDraw
    a = Image.new("RGB", (400, 300), (10, 10, 10)); ImageDraw.Draw(a).rectangle([112, 108, 148, 132], fill=(200, 50, 50)); a.save(tmp_path / "a.png")
    b = a.copy(); ImageDraw.Draw(b).rectangle([300, 200, 380, 280], fill=(50, 200, 50)); b.save(tmp_path / "b.png")
    c = m.crop_zoom(tmp_path / "a.png", [100, 100, 60, 40], 3, tmp_path / "c.png")
    assert c["size"] == [180, 120]
    assert m.frame_diff(tmp_path / "a.png", tmp_path / "a.png") == 0.0 and m.frame_diff(tmp_path / "a.png", tmp_path / "b.png") > 0.001
    m.crop_zoom(tmp_path / "a.png", [100, 100, 60, 40], 1, tmp_path / "tpl.png")
    r = m.locate_template(tmp_path / "b.png", tmp_path / "tpl.png", 0.85)
    assert r["found"] and abs(r["center"][0] - 130) <= 2 and abs(r["center"][1] - 120) <= 2
