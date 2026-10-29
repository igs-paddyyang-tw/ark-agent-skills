"""ark-quality-gates 驗收測試（規格 AC-1～AC-6）：合成專案，證明每道關會紅也不會亂紅。"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))
import quality_gates as qg  # noqa: E402

HAS_PYTEST = qg._has_module(sys.executable, "pytest")


def _proj(tmp_path: Path, files: dict[str, str]) -> Path:
    root = tmp_path / "proj"
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return root


CLEAN = {"app.py": "def add(a, b):\n    return a + b\n",
         "tests/test_app.py": "from app import add\n\ndef test_add():\n    assert add(1, 2) == 3\n",
         "tests/conftest.py": "import sys, pathlib\nsys.path.insert(0, str(pathlib.Path(__file__).parent.parent))\n"}


# ── AC-1／AC-2 tests 關 ─────────────────────────────────────────

@pytest.mark.skipif(not HAS_PYTEST, reason="本環境沒有 pytest")
def test_tests_pass_and_fail(tmp_path):
    ok = qg.gate_tests(_proj(tmp_path / "a", CLEAN), sys.executable, None, 120)
    assert ok.status == "pass" and "1 passed" in ok.summary
    bad = dict(CLEAN, **{"tests/test_bad.py": "def test_bad():\n    assert 1 == 2\n"})
    g = qg.gate_tests(_proj(tmp_path / "b", bad), sys.executable, None, 120)
    assert g.status == "fail" and "1 failed" in g.summary
    assert any("test_bad" in f.message for f in g.findings)


@pytest.mark.skipif(not HAS_PYTEST, reason="本環境沒有 pytest")
def test_no_tests_collected_is_skip_not_pass(tmp_path):
    g = qg.gate_tests(_proj(tmp_path, {"app.py": "x = 1\n"}), sys.executable, None, 120)
    assert g.status == "skip" and "0 個" in g.summary


def test_missing_pytest_is_skip_with_hint(tmp_path, monkeypatch):
    monkeypatch.setattr(qg, "_has_module", lambda py, mod: False)
    g = qg.gate_tests(_proj(tmp_path, CLEAN), "/opt/fake/python", None, 120)
    assert g.status == "skip" and "pip install pytest" in g.hint


# ── AC-3 lint 關 ────────────────────────────────────────────────

def test_syntax_error_fails_with_location(tmp_path):
    root = _proj(tmp_path, {"ok.py": "x = 1\n", "pkg/broken.py": "def f(:\n    pass\n"})
    g = qg.gate_lint(root, which=lambda _: None)
    assert g.status == "fail"
    assert [(f.file, f.line, f.rule) for f in g.findings] == [("pkg/broken.py", 1, "syntax-error")]
    assert "pip install ruff" in g.hint


def test_lint_clean_passes_and_excludes_venv(tmp_path):
    root = _proj(tmp_path, {"ok.py": "x = 1\n", ".venv/lib/bad.py": "def f(:\n"})
    assert qg.gate_lint(root, which=lambda _: None).status == "pass"


# ── AC-4 security 關 ────────────────────────────────────────────

def test_security_catches_secret_and_shell_true(tmp_path):
    root = _proj(tmp_path, {"svc.py": (
        "import subprocess\n"
        "API_KEY = 'sk-live-0123456789abcdef'\n"  # nosec — 測試夾具
        "subprocess.run('ls ' + name, shell=True)\n"
        "cur.execute(f\"SELECT * FROM users WHERE id = {uid}\")\n")})
    g = qg.gate_security(root, which=lambda _: None)
    assert g.status == "fail"
    assert {f.rule for f in g.findings} >= {"hardcoded-secret", "shell-true", "sql-concat"}


def test_security_no_false_positives_on_common_safe_code(tmp_path):
    root = _proj(tmp_path, {"safe.py": (
        "import os, ast\n"
        "API_KEY = os.environ['API_KEY']\n"
        "password = '<your-password>'\n"
        "model.eval()\n"
        "ast.literal_eval('[1]')\n"
        "# token = 'abcdefghijklmnop'  註解不算\n"  # nosec — 測試夾具
        "cur.execute('SELECT * FROM t WHERE id = ?', (uid,))\n")})
    g = qg.gate_security(root, which=lambda _: None)
    assert g.status == "pass", [(f.rule, f.line) for f in g.findings]
    assert "bandit" in g.hint and "pip-audit" in g.hint


def test_nosec_suppresses_but_is_counted(tmp_path):
    root = _proj(tmp_path, {"run.py": "import subprocess\nsubprocess.run(cmd, shell=True)  # nosec 使用者設定的指令\n"})
    g = qg.gate_security(root, which=lambda _: None)
    assert g.status == "pass" and g.suppressed == 1 and "nosec 略過 1" in g.summary


# ── AC-5／AC-6 CLI ─────────────────────────────────────────────

def _cli(*args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPTS / "quality_gates.py"), *args],
                          capture_output=True, text=True)


def test_strict_turns_skip_into_failure(tmp_path):
    root = _proj(tmp_path, {"app.py": "x = 1\n"})   # 0 個測試 → tests 關 skip
    assert _cli("--path", str(root), "--only", "tests,lint").returncode == 0
    assert _cli("--path", str(root), "--only", "tests,lint", "--strict").returncode == 1


def test_cli_exit_code_matches_verdict_and_writes_reports(tmp_path):
    root = _proj(tmp_path, {"svc.py": "eval(input())\n"})
    out_j, out_m = tmp_path / "r.json", tmp_path / "r.md"
    r = _cli("--path", str(root), "--only", "lint,security", "--json", str(out_j), "--md", str(out_m))
    data = json.loads(out_j.read_text(encoding="utf-8"))
    assert r.returncode == 1 and data["verdict"] == "fail"
    assert {g["name"]: g["status"] for g in data["gates"]} == {"lint": "pass", "security": "fail"}
    assert "dangerous-eval" in out_m.read_text(encoding="utf-8")


def test_unknown_gate_is_usage_error(tmp_path):
    assert _cli("--path", str(tmp_path), "--only", "lint,typo").returncode == 2
