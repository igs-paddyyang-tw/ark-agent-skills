"""gs_restore（還原模式 config-spec）：全鍵枚舉、value 一律 $ref 可解析、mode 分流自檢；反證必紅。"""
import json
import os
import pathlib
import subprocess
import sys

import yaml

HERE = pathlib.Path(__file__).resolve().parent
SCRIPTS = HERE.parent
RESTORE = SCRIPTS / "spec" / "gs_restore.py"
GS = SCRIPTS / "gs_run.py"
CONF = {"Bet_Cost": 50, "RTP": 0.965, "MainGameReelSetWeight": [10, 20, 70], "FreeSpin": {"Times": [8, 10]},
        "Line/Odds": [[0, 5]], "Tilde~Key": True}


def sh(*args):
    r = subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    line = next((ln for ln in reversed(r.stdout.strip().splitlines()) if ln.startswith("{")), "{}")
    return r.returncode, json.loads(line)


def make(tmp):
    c = tmp / "config" / "a-standard.json"
    c.parent.mkdir(parents=True)
    c.write_text(json.dumps(CONF), encoding="utf-8")
    return c


def test_restore_all_keys_ref_resolvable(tmp_path):
    c = make(tmp_path)
    out = tmp_path / "games" / "demo" / "spec"
    code, j = sh(RESTORE, "--config", c, "--out", out, "--slug", "demo")
    assert code == 0, j
    cfg = yaml.safe_load((out / "config-spec.yaml").read_text(encoding="utf-8"))
    assert cfg["mode"] == "restore-live" and cfg["slug"] == "demo"
    assert [p["name"] for p in cfg["parameters"]] == list(CONF)                    # 全鍵、順序同設定檔
    assert all(set(p["value"]) == {"$ref"} for p in cfg["parameters"])            # 不抄值
    types = {p["name"]: p["type"] for p in cfg["parameters"]}
    assert types == {"Bet_Cost": "integer", "RTP": "number", "MainGameReelSetWeight": "array", "FreeSpin": "object",
                     "Line/Odds": "array", "Tilde~Key": "boolean"}
    refs = {p["name"]: p["value"]["$ref"] for p in cfg["parameters"]}
    assert refs["Line/Odds"].endswith("#/Line~1Odds") and refs["Tilde~Key"].endswith("#/Tilde~0Key")  # RFC 6901 跳脫
    assert all(p["decision"].startswith("restore-live: ") for p in cfg["parameters"])
    assert sh(RESTORE, "--check", out / "config-spec.yaml")[0] == 0


def test_restore_xlsx_sha_in_decision(tmp_path):
    c = make(tmp_path)
    x = tmp_path / "表.xlsx"; x.write_bytes(b"fake-xlsx")
    code, j = sh(RESTORE, "--config", c, "--xlsx", x, "--out", tmp_path / "spec")
    assert code == 0, j
    cfg = yaml.safe_load((tmp_path / "spec" / "config-spec.yaml").read_text(encoding="utf-8"))
    assert cfg["source_xlsx"]["sha256_16"] in cfg["parameters"][0]["decision"]


def _break(tmp_path, fn):
    c = make(tmp_path)
    out = tmp_path / "spec"
    assert sh(RESTORE, "--config", c, "--out", out)[0] == 0
    p = out / "config-spec.yaml"
    cfg = yaml.safe_load(p.read_text(encoding="utf-8")); fn(cfg)
    p.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    return sh(RESTORE, "--check", p)


def test_check_blocks_wrong_ref(tmp_path):
    code, j = _break(tmp_path, lambda c: c["parameters"][0]["value"].update({"$ref": "../config/a-standard.json#/NoSuchKey"}))
    assert code == 3 and j["error"]["code"] == "GATE_BLOCKED" and "NoSuchKey" in j["data"]["errors"][0]["msg"]


def test_check_blocks_bare_value_and_description_string(tmp_path):
    """F5 原病灶：value 填描述字串／裸值 → 形式過 null 但無約束力，還原模式必須擋。"""
    def f(c):
        c["parameters"][0]["value"] = 50
        c["parameters"][1]["value"] = "10 組 SC 密度分層權重"
    code, j = _break(tmp_path, f)
    assert code == 3 and len(j["data"]["errors"]) == 2


def test_check_blocks_wrong_mode_and_decision(tmp_path):
    def f(c):
        c["mode"] = "design"
        c["parameters"][0]["decision"] = "D-001"
    code, j = _break(tmp_path, f)
    assert code == 3 and {e["param"] for e in j["data"]["errors"]} == {None, "Bet_Cost"}


def test_bad_input(tmp_path):
    assert sh(RESTORE)[0] == 2
    bad = tmp_path / "x.json"; bad.write_text("[]", encoding="utf-8")
    assert sh(RESTORE, "--config", bad)[0] == 2


def test_gs_run_restore_stage(tmp_path):
    c = make(tmp_path)
    code, j = sh(GS, "--stage", "restore", "--config", c, "--out", tmp_path / "spec", "--slug", "demo")
    assert code == 0, j
    assert j["meta"]["stage"] == "restore" and j["data"]["params"] == len(CONF)
    code, j = sh(GS, "--stage", "restore", "--check", tmp_path / "spec" / "config-spec.yaml")
    assert code == 0 and j["data"]["verdict"] == "OK"
