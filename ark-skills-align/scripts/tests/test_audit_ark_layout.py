"""AL-034／035：.ark 工具中立佈局稽核規則（S2 T2.3）—— 必須能紅、雙讀後必須綠。"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import audit_skills as AU  # noqa: E402

SKILL = ('---\nname: ark-demo\ndescription: demo\nmetadata:\n  version: "1.0.0"\n'
         '  category: tool\n  form: executor\n  domain: general\n  outputs: []\n---\n# demo\n{body}\n')


def _repo(tmp: Path, script: str, body: str = "", extra: dict[str, str] | None = None) -> Path:
    sk = tmp / "ark-demo"
    (sk / "scripts").mkdir(parents=True)
    (sk / "SKILL.md").write_text(SKILL.format(body=body), encoding="utf-8")
    (sk / "scripts" / "run.py").write_text(script, encoding="utf-8")
    for rel, text in (extra or {}).items():
        (sk / rel).parent.mkdir(parents=True, exist_ok=True)
        (sk / rel).write_text(text, encoding="utf-8")
    return tmp


def _rules(repo: Path) -> dict[str, dict]:
    findings = AU.audit(repo, {})["findings"]
    return {f["rule"]: f for f in findings if f["skill"] == "ark-demo"}


def test_hardcoded_kiro_path_is_flagged(tmp_path: Path):
    got = _rules(_repo(tmp_path, 'p = root / ".kiro" / "skills"\n'))
    assert got["kiro-path-in-script"]["severity"] == "P2"
    assert "scripts/run.py" in got["kiro-path-in-script"]["message"]


def test_dual_read_passes(tmp_path: Path):
    src = 'base = root / ".ark" if (root / ".ark" / "ark.yaml").is_file() else root / ".kiro"\n'
    assert "kiro-path-in-script" not in _rules(_repo(tmp_path, src))


def test_attribute_named_ark_does_not_count_as_dual_read(tmp_path: Path):
    src = 'x = CFG.arkIdPrefix\np = root / ".kiro" / "skills"\n'
    assert "kiro-path-in-script" in _rules(_repo(tmp_path, src))


def test_url_and_tests_are_ignored(tmp_path: Path):
    repo = _repo(tmp_path, 'fix = "curl -fsSL https://cli.kiro.dev/install | bash"\n',
                 extra={"scripts/tests/test_x.py": 'p = tmp / ".kiro" / "skills"\n'})
    assert "kiro-path-in-script" not in _rules(repo)


def test_doc_only_kiro_layout_is_p3(tmp_path: Path):
    got = _rules(_repo(tmp_path, "", body="人格放 `.kiro/steering/SOUL.md`"))
    assert got["doc-kiro-layout-only"]["severity"] == "P3"
    ok = _rules(_repo(tmp_path / "b", "", body="人格放 `.ark/brain/SOUL.md`（舊佈局 `.kiro/steering/`）"))
    assert "doc-kiro-layout-only" not in ok
