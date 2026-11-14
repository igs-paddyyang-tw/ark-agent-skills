"""qt_fish_run 測試：用假 fishsim（python 腳本）跑，不需 Go。

覆蓋：gate 過／不過（exit 0／3）、打法敏感度 findings（>1% P2、>1 P1、沒跑偏打法）、
命中率／附加獎勵率 95% 區間判定、路徑解析（--root 基準、絕對路徑、預設 out_dir／slug）、輸入錯誤 exit 2。
"""
from __future__ import annotations

import asyncio
import json
import pathlib
import sys

import pytest

yaml = pytest.importorskip("yaml")
SCRIPTS = pathlib.Path(__file__).resolve().parent.parent
FAKE = SCRIPTS / "tests" / "fixtures" / "fish" / "fake_fishsim.py"
sys.path.insert(0, str(SCRIPTS / "fish"))
import qt_fish_run as Q  # noqa: E402

FISH = [{"type": 1, "name": "小魚", "odds": 3, "drop_ppm": 50000, "alive": 8},
        {"type": 2, "name": "中魚", "odds": 8, "drop_ppm": 130000, "alive": 11},
        {"type": 3, "name": "大魚", "odds": 25, "drop_ppm": 410000, "alive": 16}]


def make_game(root: pathlib.Path, totals: dict, *, runs=None, seed_step=0.0, hit_skew=0.0, extra=None) -> pathlib.Path:
    """在 root/data/fish/demo 建假遊戲：設定檔＋qt-config；回傳 qt-config 路徑。"""
    g = root / "data" / "fish" / "demo"
    (g / "quicktest").mkdir(parents=True)
    (g / "configs").mkdir()
    cfg = {"_spec": "測試用", "game_rate": 0.8, "bead": {"win_mul": 20}, "fish_info": FISH,
           "_fake": {"total": totals, "seed_step": seed_step, "hit_skew": hit_skew}}
    (g / "configs" / "demo.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    qt = {"tool": "data/fish/demo/fake_fishsim.py", "config": "data/fish/demo/configs/demo.json",
          "bet": 1, "per_frame": 8,
          "runs": runs or [{"aim": "random", "seeds": [1, 2, 3], "shots": 3_000_000},
                           {"aim": "gold", "seeds": [1], "shots": 3_000_000}],
          "gate": {"total": 0.96, "tolerance": 0.005}, **(extra or {})}
    (g / "fake_fishsim.py").write_text(FAKE.read_text(encoding="utf-8"), encoding="utf-8")
    p = g / "quicktest" / "qt-config.yaml"
    p.write_text(yaml.safe_dump(qt, allow_unicode=True), encoding="utf-8")
    return p


def run(root: pathlib.Path, *extra: str) -> tuple[int, dict | None]:
    """以 root 為基準跑 qt_fish_run（--no-lint），回 (exit, stdout JSON)。"""
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = asyncio.run(Q.amain(["--qt-config", "data/fish/demo/quicktest/qt-config.yaml",
                                  "--root", str(root), "--date", "2026-11-14", "--no-lint", *extra]))
    out = buf.getvalue().strip()
    return rc, (json.loads(out) if out else None)


def report(root: pathlib.Path, out_dir: str = "data/fish/demo/quicktest/qt-report") -> dict:
    return json.loads((root / out_dir / "rtp-report.json").read_text(encoding="utf-8"))


def sev(rep: dict, fid: str) -> str:
    return next(f["sev"] for f in Q.findings(rep) if f["id"] == fid)


# ── gate ──────────────────────────────────────────────────────────────────

def test_gate_pass_writes_three_files(tmp_path):
    make_game(tmp_path, {"random": 0.958, "gold": 0.962}, seed_step=0.0005)
    rc, out = run(tmp_path)
    assert rc == 0 and out["gate"]["pass"] is True
    rep = report(tmp_path)
    assert rep["gate"]["totals"] == [0.9585, 0.959, 0.9595]       # 依 seed 排序、原樣不四捨五入
    assert rep["game"] == "demo" and rep["config"]["path"] == "data/fish/demo/configs/demo.json"
    d = tmp_path / "data/fish/demo/quicktest/qt-report"
    assert (d / "2026-11-14-quicktest-demo.md").exists() and (d / "2026-11-14-quicktest-demo.html").exists()
    md = (d / "2026-11-14-quicktest-demo.md").read_text(encoding="utf-8")
    assert "verdict: confirmed" in md and "type: data" in md
    assert (tmp_path / "output/fish/demo/qt-runs/qt3m-random-seed1.json").exists()


def test_gate_fail_exit3(tmp_path):
    make_game(tmp_path, {"random": 0.950, "gold": 0.951})
    rc, out = run(tmp_path)
    assert rc == 3 and out["gate"]["pass"] is False
    rep = report(tmp_path)
    assert sev(rep, "F-1") == "P0"
    assert all(not r["within_gate"] for r in rep["runs"])
    assert "verdict: rejected" in (tmp_path / "data/fish/demo/quicktest/qt-report/2026-11-14-quicktest-demo.md").read_text(encoding="utf-8")


def test_gate_fail_when_one_seed_out(tmp_path):
    make_game(tmp_path, {"random": 0.958, "gold": 0.96}, seed_step=0.003)   # 0.961／0.964／0.967 → seed3 出界
    rc, _ = run(tmp_path)
    assert rc == 3


# ── findings ─────────────────────────────────────────────────────────────

def test_aim_sensitivity_within_threshold_p3(tmp_path):
    make_game(tmp_path, {"random": 0.96, "gold": 0.965})
    run(tmp_path)
    assert sev(report(tmp_path), "F-2") == "P3"


def test_aim_sensitivity_over_1pct_p2(tmp_path):
    make_game(tmp_path, {"random": 0.96, "gold": 0.975})
    run(tmp_path)
    assert sev(report(tmp_path), "F-2") == "P2"


def test_aim_sensitivity_low_side_also_counts(tmp_path):
    make_game(tmp_path, {"random": 0.96, "gold": 0.94})              # 偏低也算最偏
    run(tmp_path)
    assert sev(report(tmp_path), "F-2") == "P2"


def test_aim_over_one_is_p1(tmp_path):
    make_game(tmp_path, {"random": 0.96, "gold": 1.0144})
    rc, out = run(tmp_path)
    assert rc == 0                                                     # gate 只看 random
    assert sev(report(tmp_path), "F-2") == "P1"
    assert {"id": "F-2", "sev": "P1"} in out["findings"]


def test_aim_deviation_configurable(tmp_path):
    make_game(tmp_path, {"random": 0.96, "gold": 0.975}, extra={"aim_deviation": 0.02})
    run(tmp_path)
    assert sev(report(tmp_path), "F-2") == "P3"


def test_random_only_flags_missing_biased_aims(tmp_path):
    make_game(tmp_path, {"random": 0.96}, runs=[{"aim": "random", "seeds": [1, 2], "shots": 3_000_000}])
    run(tmp_path)
    f2 = next(f for f in Q.findings(report(tmp_path)) if f["id"] == "F-2")
    assert f2["sev"] == "P2" and "沒跑偏打法" in f2["what"]


# ── 區間判定 ─────────────────────────────────────────────────────────────

def test_hit_and_drop_in_ci_when_exact(tmp_path):
    make_game(tmp_path, {"random": 0.96, "gold": 0.96})
    run(tmp_path)
    rep = report(tmp_path)
    cells = [v for r in rep["runs"] for v in r["per_fish"].values()]
    assert all(v["hit_in_ci"] and v["drop_in_ci"] for v in cells)
    v = rep["runs"][0]["per_fish"]["1"]
    assert v["hit_theory"] == round(0.8 / 3, 6) and v["drop_theory"] == 0.05
    assert sev(rep, "F-3") == "P3" and sev(rep, "F-4") == "P3"


def test_hit_out_of_ci_flags_p2(tmp_path):
    make_game(tmp_path, {"random": 0.96, "gold": 0.96}, hit_skew=0.05)   # 命中率高 5%，1M 發早出界
    run(tmp_path)
    rep = report(tmp_path)
    assert not any(v["hit_in_ci"] for r in rep["runs"] for v in r["per_fish"].values())
    assert sev(rep, "F-3") == "P2"


def test_enrich_ci_boundary():
    qt = {"fields": Q.DEFAULT_FIELDS, "gate": {"total": 0.96, "tolerance": 0.005}}
    cfg = {"game_rate": 0.5, "fish_info": [{"type": 1, "name": "x", "odds": 2, "drop_ppm": 0}]}
    n = 10_000
    half = Q.binom_half(0.25, n)
    inside = {"shots": n, "rtp": {"fish": 0.9, "total": 0.96},
              "per_fish": {"1": {"shots": n, "kills": int(n * (0.25 + half * 0.9)), "rtp": 0.5}}}
    outside = {"shots": n, "rtp": {"fish": 0.9, "total": 0.97},
               "per_fish": {"1": {"shots": n, "kills": int(n * (0.25 + half * 1.2)) + 1, "rtp": 0.5}}}
    assert Q.enrich(inside, cfg, qt)["per_fish"]["1"]["hit_in_ci"] is True
    assert Q.enrich(outside, cfg, qt)["per_fish"]["1"]["hit_in_ci"] is False
    assert inside["within_gate"] is True and outside["within_gate"] is False


def test_field_override_and_bonus_key():
    qt = {"fields": {**Q.DEFAULT_FIELDS, "fish_list": "fishes", "odds": "mul", "drop_ppm": "gem_ppm"},
          "gate": {"total": 0.96, "tolerance": 0.005}}
    cfg = {"game_rate": 0.9, "fishes": [{"type": 7, "name": "龍", "mul": 90, "gem_ppm": 100000}]}
    r = {"shots": 900, "rtp": {"fish": 0.9, "gem": 0.06, "total": 0.96},
         "per_fish": {"7": {"shots": 900, "kills": 9, "beads": 1, "rtp": 0.9}}}
    v = Q.enrich(r, cfg, qt)["per_fish"]["7"]
    assert v["hit_theory"] == 0.01 and v["drop_theory"] == 0.1 and v["odds"] == 90


# ── 路徑與輸入 ───────────────────────────────────────────────────────────

def test_paths_resolve_against_root_and_out_dir_override(tmp_path):
    make_game(tmp_path, {"random": 0.96, "gold": 0.96})
    rc, out = run(tmp_path, "--out-dir", "output/fish/demo/check", "--runs-dir", "output/raw")
    assert rc == 0
    assert out["out"][0] == "output/fish/demo/check/rtp-report.json"
    assert (tmp_path / "output/raw/qt3m-gold-seed1.json").exists()
    assert not (tmp_path / "data/fish/demo/quicktest/qt-report").exists()


def test_load_qt_defaults_and_absolute(tmp_path):
    p = make_game(tmp_path, {"random": 0.96}, extra={"slug": "x-fish", "out_dir": str(tmp_path / "abs-out")})
    qt = Q.load_qt(p, tmp_path)
    assert qt["slug"] == "x-fish" and qt["bonus_key"] == "bead"
    assert qt["_paths"]["out_dir"] == tmp_path / "abs-out"
    assert qt["_paths"]["runs_dir"] == tmp_path / "output/fish/x-fish/qt-runs"
    assert qt["_paths"]["tool"] == tmp_path / "data/fish/demo/fake_fishsim.py"


def test_default_slug_from_quicktest_parent(tmp_path):
    p = make_game(tmp_path, {"random": 0.96})
    qt = Q.load_qt(p, tmp_path)
    assert qt["slug"] == "demo" and qt["_paths"]["out_dir"] == p.parent / "qt-report"


def test_bad_input_exit2(tmp_path):
    p = make_game(tmp_path, {"random": 0.96})
    d = yaml.safe_load(p.read_text(encoding="utf-8"))
    d["tool"] = "data/fish/demo/nope"
    p.write_text(yaml.safe_dump(d), encoding="utf-8")
    rc, out = run(tmp_path)
    assert rc == 2 and out is None


def test_missing_required_field(tmp_path):
    p = make_game(tmp_path, {"random": 0.96})
    d = yaml.safe_load(p.read_text(encoding="utf-8"))
    del d["gate"]
    p.write_text(yaml.safe_dump(d), encoding="utf-8")
    with pytest.raises(Q.QtError, match="gate"):
        Q.load_qt(p, tmp_path)


def test_contract_violation_exit2(tmp_path):
    with pytest.raises(Q.QtError, match="rtp"):
        Q.check_contract({"per_fish": {"1": {}}}, "random", 1)
    with pytest.raises(Q.QtError, match="per_fish"):
        Q.check_contract({"rtp": {"fish": 0.8, "total": 0.9}, "per_fish": {"1": {"shots": 1}}}, "random", 1)


def test_md_passes_report_lint(tmp_path):
    lint = Q.MD_REPORT / "report_lint.py"
    if not lint.exists():
        pytest.skip("同層沒有 ark-md-report")
    make_game(tmp_path, {"random": 0.96, "gold": 1.02})
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = asyncio.run(Q.amain(["--qt-config", "data/fish/demo/quicktest/qt-config.yaml",
                                  "--root", str(tmp_path), "--date", "2026-11-14"]))
    assert rc == 0 and json.loads(buf.getvalue())["lint"] == "PASS"
