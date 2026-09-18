"""pack 契約測試：三個預設 pack lint 綠、resolve deterministic、template 必須被擋、core tag 衝突必須被擋。"""
import json
import pathlib
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
SCRIPTS = HERE.parent
sys.path.insert(0, str(SCRIPTS))
import pack_common as P  # noqa: E402
import pack_lint  # noqa: E402

ROOT = P.DEFAULT_DOMAINS_DIR


def run(*args):
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True, encoding="utf-8")
    return r.returncode, json.loads(r.stdout.strip().splitlines()[-1])


def test_default_packs_lint_green():
    code, j = run(SCRIPTS / "pack_lint.py", "--all")
    assert code == 0, j
    assert set(j["data"]["packs"]) == {"slot-game", "fish-game", "fast-game"}


def test_resolve_deterministic_and_ten_items():
    for d in P.list_packs(ROOT):
        a = P.resolve(d, ROOT)
        b = P.resolve(d, ROOT)
        assert json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)
        assert len(a["analysis"]["items"]) == 10
        assert a["analysis"]["item_ids"][:4] == ["C01", "C02", "C03", "C04"]
        assert a["spec"]["sections"][-1]["id"] == "open_questions"
        assert not any(s.get("anchor") for s in a["spec"]["sections"])
        assert a["extraction"]["budget"]["hard_max"]


def test_template_is_blocked(tmp_path):
    shutil.copytree(ROOT, tmp_path / "domains")
    shutil.copytree(ROOT / "_template", tmp_path / "domains" / "x-game")
    v = pack_lint.lint_domain("x-game", tmp_path / "domains")
    rules = {x["rule"] for x in v if x["severity"] == "error"}
    assert "PACK-PLACEHOLDER" in rules and "PACK-ITEMS" in rules


def test_core_tag_clash_blocked(tmp_path):
    shutil.copytree(ROOT, tmp_path / "domains")
    sch = tmp_path / "domains" / "slot-game" / "kb" / "schema.md"
    sch.write_text(sch.read_text(encoding="utf-8") + "\n| bonus | 重定義 core tag |\n", encoding="utf-8")
    v = pack_lint.lint_domain("slot-game", tmp_path / "domains")
    assert any(x["rule"] == "PACK-KB-TAGS" and "bonus" in x["message"] for x in v)


def test_budget_over_hard_max_blocked(tmp_path):
    shutil.copytree(ROOT, tmp_path / "domains")
    ext = tmp_path / "domains" / "fish-game" / "extraction.yaml"
    ext.write_text(ext.read_text(encoding="utf-8").replace("max_keyframes: 200", "max_keyframes: 9999"), encoding="utf-8")
    v = pack_lint.lint_domain("fish-game", tmp_path / "domains")
    assert any(x["rule"] == "PACK-BUDGET" for x in v)


def test_unknown_detector_blocked(tmp_path):
    shutil.copytree(ROOT, tmp_path / "domains")
    ext = tmp_path / "domains" / "fast-game" / "extraction.yaml"
    ext.write_text(ext.read_text(encoding="utf-8").replace("use: still_hold", "use: mahjong_discard"), encoding="utf-8")
    v = pack_lint.lint_domain("fast-game", tmp_path / "domains")
    assert any(x["rule"] == "PACK-DETECTOR" for x in v)
