"""ps_diff 1.5.2 裁定（ruling + pin）：pin 對得上 → ruled 不擋；值變了 → pin 失效回 mismatch。不需 xlsx。"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

SCRIPTS = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))
import ps_diff  # noqa: E402


def _run(tmp, cfg_val, pin):
    data = {"game": "t", "source": {"name": "t.xlsx", "sha256_16": "0" * 16}, "known": {"board": {"線數": 1}, "reelsets": {"sets": [{"weight": 1}, {"weight": 2}, {"weight": 3}]}}}
    (tmp / "prob-data.json").write_text(json.dumps(data), encoding="utf-8")
    (tmp / "cfg.json").write_text(json.dumps({"W": cfg_val}), encoding="utf-8")
    (tmp / "map.yaml").write_text(
        'rules:\n  - {id: rs, xlsx: "reelsets.weight", config: W, ruling: {id: R-9, winner: config, by: t, date: "2026-10-21", pin: %s}}\n' % json.dumps(pin),
        encoding="utf-8")
    p = subprocess.run([sys.executable, str(SCRIPTS / "ps_diff.py"), "--data", str(tmp / "prob-data.json"), "--config", str(tmp / "cfg.json"),
                        "--map", str(tmp / "map.yaml"), "--out", str(tmp)], capture_output=True, text=True)
    return p.returncode, json.loads((tmp / "config-diff.json").read_text(encoding="utf-8"))


def test_ruled_when_pin_matches(tmp_path):
    pin = {"xlsx": ps_diff.vsha([1, 2, 3]), "config": ps_diff.vsha([1, 2, 4])}
    rc, rep = _run(tmp_path, [1, 2, 4], pin)
    assert rc == 0 and rep["summary"]["ruled"] == 1 and rep["summary"]["mismatch"] == 0
    assert "已裁定" in (tmp_path / "config-diff.md").read_text(encoding="utf-8")


def test_pin_stale_falls_back_to_mismatch(tmp_path):
    pin = {"xlsx": ps_diff.vsha([1, 2, 3]), "config": ps_diff.vsha([1, 2, 4])}
    rc, rep = _run(tmp_path, [1, 2, 5], pin)
    assert rc == 3 and rep["summary"]["mismatch"] == 1 and rep["summary"]["ruled"] == 0
    assert "pin 失效" in rep["rows"][0]["note"]
