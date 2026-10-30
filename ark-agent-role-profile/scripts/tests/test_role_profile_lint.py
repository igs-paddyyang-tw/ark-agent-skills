"""ark-agent-role-profile 行為測試 —— profile_lint 守門與 render_profile 渲染。

## 驗什麼

- profile_lint：內建角色庫全數 P0/P1 清零；缺必填、空話立場、沒有頂回範例要被擋下；
  schema 新增的選填 `domain: general|game` 要被接受、亂填要被擋（需 jsonschema）。
- render_profile：lint 過 → 產三個 fragment（含 sha 戳記與 `inclusion: manual`）；
  lint 不過 → exit 1 且不產任何檔。

## jsonschema 兩條路徑

profile_lint 有 jsonschema 才做完整 schema 驗證，沒有時退化成「只查必填欄位」。
兩條路徑分開測：退化路徑用 monkeypatch 把 jsonschema 擋掉（不論本機有沒有裝都能跑）；
完整路徑用 `pytest.importorskip("jsonschema")`，沒裝就跳過。
"""
from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

SCRIPTS = Path(__file__).resolve().parent.parent
SKILL_ROOT = SCRIPTS.parent
ROLES = SKILL_ROOT / "assets" / "roles"
sys.path.insert(0, str(SCRIPTS))

import profile_lint  # noqa: E402


def _qa() -> dict:
    """角色庫的 qa.yaml（已知是合格的完整 profile），每次回傳新複本。"""
    return yaml.safe_load((ROLES / "qa.yaml").read_text(encoding="utf-8"))


def _write(tmp_path: Path, profile: dict, name: str = "role-profile.yaml") -> Path:
    p = tmp_path / name
    p.write_text(yaml.safe_dump(profile, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return p


@pytest.fixture
def no_jsonschema(monkeypatch):
    """模擬沒裝 jsonschema：import 會 ImportError，強迫走退化路徑。"""
    monkeypatch.setitem(sys.modules, "jsonschema", None)


def _levels(fx) -> list[str]:
    return [lv for lv, _ in fx.items]


# ── 正常路徑 ─────────────────────────────────────────────────

def test_all_bundled_roles_pass_lint(no_jsonschema):
    """角色庫每一份都必須 P0/P1 清零 —— 它們是訪談的起點，自己不過就沒資格當範本。

    同時確認「掃到的數量」合理（至少 10 份），避免 glob 失效時空集合假綠。
    """
    roles = sorted(ROLES.glob("*.yaml"))
    assert len(roles) >= 10, f"角色庫只掃到 {len(roles)} 份，glob 可能失效"
    bad = {p.name: fx.items for p in roles if (fx := profile_lint.lint_file(p, None)).blocking()}
    assert not bad, f"角色庫有 P0/P1：{bad}"


def test_domain_game_accepted_in_fallback_path(tmp_path, no_jsonschema):
    """選填 `domain: game` 在退化路徑不得造成任何 P0（它不是必填欄位）。"""
    prof = _qa()
    prof["domain"] = "game"
    fx = profile_lint.lint_file(_write(tmp_path, prof), None)
    assert not fx.blocking(), fx.items


def test_render_produces_three_stamped_fragments(tmp_path):
    """lint 過的 profile → 三個 fragment，各帶 profile-sha256 戳記與 inclusion: manual；
    skills 的物件形式（schema 1.1：{name, version, tier}）要渲染出版本與 tier。"""
    prof = _qa()
    prof["skills"] = ["ark-quality-gates", {"name": "ark-test-runner", "version": "^1.0.0", "tier": "role"}]
    src = _write(tmp_path, prof)
    out = tmp_path / "rendered"
    r = subprocess.run([sys.executable, str(SCRIPTS / "render_profile.py"), str(src), "--out", str(out)],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr
    names = sorted(p.name for p in out.iterdir())
    assert names == ["AGENTS.fragment.md", "SOUL.fragment.md", "schema.fragment.md"]
    for p in out.iterdir():
        text = p.read_text(encoding="utf-8")
        assert text.startswith("---\ninclusion: manual\n---\n"), p.name
        assert "<!-- profile-sha256: " in text, p.name
    soul = (out / "SOUL.fragment.md").read_text(encoding="utf-8")
    assert prof["stance"][0] in soul and "## 🚫 Hard Stops" in soul
    agents = (out / "AGENTS.fragment.md").read_text(encoding="utf-8")
    assert "- `ark-test-runner` `^1.0.0` [role]" in agents


# ── 反例：壞輸入必須被擋 ──────────────────────────────────────

def test_missing_required_field_is_p0_in_fallback(tmp_path, no_jsonschema):
    """缺必填欄位（hard_stops）→ 退化路徑也必須報 P0，CLI exit 1。"""
    prof = _qa()
    del prof["hard_stops"]
    path = _write(tmp_path, prof)
    fx = profile_lint.lint_file(path, None)
    assert any(lv == "P0" and "hard_stops" in m for lv, m in fx.items), fx.items
    r = subprocess.run([sys.executable, str(SCRIPTS / "profile_lint.py"), str(path)],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 1


def test_mush_stance_and_no_pushback_are_p1(tmp_path, no_jsonschema):
    """空話立場（「保持專業」）與「examples 沒有任何頂回情境」都是 P1 ——
    這兩種 profile 讀起來像人格，實際上無法據以做決策。"""
    prof = _qa()
    prof["stance"][0] = "保持專業，全面協助每一位使用者完成工作"
    prof["examples"] = [{"kind": "typical", "situation": "收到驗收請求", "response": "逐條驗收並回報結果"},
                        {"kind": "typical", "situation": "收到回歸請求", "response": "跑回歸並附路徑"}]
    msgs = [m for lv, m in profile_lint.lint_file(_write(tmp_path, prof), None).items if lv == "P1"]
    assert any("保持專業" in m for m in msgs), msgs
    assert any("頂回" in m for m in msgs), msgs


def test_render_refuses_when_lint_fails(tmp_path, no_jsonschema):
    """lint 不過時 render 必須 exit 1 且一個 fragment 都不產（不能留下半套人格）。"""
    prof = _qa()
    prof["stance"] = ["很好", "很棒", "很快"]
    src = _write(tmp_path, prof)
    out = tmp_path / "rendered"
    r = subprocess.run([sys.executable, str(SCRIPTS / "render_profile.py"), str(src), "--out", str(out)],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 1
    assert not out.exists() or not any(out.iterdir())


def test_non_mapping_yaml_is_p0(tmp_path):
    """頂層不是 mapping（例如一個 list）→ 讀取失敗記 P0，而不是 crash。"""
    p = tmp_path / "bad.yaml"
    p.write_text("- a\n- b\n", encoding="utf-8")
    fx = profile_lint.lint_file(p, None)
    assert _levels(fx) == ["P0"] and "mapping" in fx.items[0][1]


# ── 邊界 ─────────────────────────────────────────────────────

def test_stance_length_boundary(tmp_path, no_jsonschema):
    """立場句 < 12 字視為形容詞（P1）；剛好 12 字且含動詞則通過 —— 守住門檻不漂移。"""
    prof = _qa()
    eleven = "先查重現步驟再回報結果"        # 11 字
    twelve = "先查重現步驟再回報測試結果"[:12]  # 12 字
    assert len(eleven) == 11 and len(twelve) == 12
    prof["stance"][0] = eleven
    assert any("太短" in m for _, m in profile_lint.lint_file(_write(tmp_path, prof), None).items)
    prof["stance"][0] = twelve
    assert not any("stance[0]" in m for _, m in profile_lint.lint_file(_write(tmp_path, prof), None).items)


def test_skills_root_flags_missing_skill(tmp_path, no_jsonschema):
    """給 --skills-root 時，列了不存在的 skill → P1；存在的不報。"""
    root = tmp_path / "skills"
    (root / "ark-quality-gates").mkdir(parents=True)
    (root / "ark-quality-gates" / "SKILL.md").write_text("x", encoding="utf-8")
    prof = _qa()
    prof["skills"] = ["ark-quality-gates", "ark-not-exist"]
    msgs = [m for lv, m in profile_lint.lint_file(_write(tmp_path, prof), root).items if lv == "P1"]
    assert any("ark-not-exist" in m for m in msgs)
    assert not any("ark-quality-gates" in m for m in msgs)


# ── 完整 schema 路徑（需 jsonschema）────────────────────────────

def test_domain_enum_with_jsonschema(tmp_path):
    """有 jsonschema 時：domain 只接受 general / game，其他值 → P0 schema 不符。"""
    pytest.importorskip("jsonschema")
    for ok in ("general", "game"):
        prof = copy.deepcopy(_qa())
        prof["domain"] = ok
        assert not profile_lint.lint_file(_write(tmp_path, prof), None).blocking()
    prof = _qa()
    prof["domain"] = "finance"
    fx = profile_lint.lint_file(_write(tmp_path, prof), None)
    assert any(lv == "P0" and "domain" in m for lv, m in fx.items), fx.items
