"""scaffolder 契約守門 —— 把「模板與產生腳本必須一致」變成測試。

## 為什麼需要這支

2026-09-11 用本 skill 實建 `slot-server`，從 scaffold 到能跑**手動修正了 12 處**。
沒有任何一處是「東西不見了」—— 全部是**兩份各自演化的真相對不上**：

| 一邊說 | 另一邊說 |
|---|---|
| `assets/bot.yaml`：報告寫 `output/reports` | `build_agent.py`：建的是 `artifacts/reports` |
| `assets/agents.yaml`：`group_members` 有 `worker-b` | 該檔從未定義 `worker-b` |
| `assets/agents.yaml`：`worker-a.dir = agents/worker-a-agent` | `build_agent.py` 一個 `agents/` 都不建 |
| `SKILL.md`：`assets/steering/AGENTS.md` | 實際檔名是 `BRAIN.md` |

而舊版 `validate_agent.py` 只驗「檔案存在 + 佔位符」，**12 條全部通過**。

> 🔴 判準：**模板與它的產生器是兩份真相時，必須有守門在比對它們。**
> 這些缺陷都曾經是對的，是後來一邊改了另一邊沒跟上。修症狀不加守門，它會漂移回去。
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

SCRIPTS = Path(__file__).resolve().parent.parent
SKILL_ROOT = SCRIPTS.parent
ASSETS = SKILL_ROOT / "assets"
SKILLS_REPO = SKILL_ROOT.parent


# ── 端到端：產完立刻驗 ────────────────────────────────────────

def test_scaffold_passes_its_own_validate(tmp_path):
    """跑 scaffold → 立刻跑 validate，必須 0 問題

    這是最重要的一條：它不預設任何細節，只要求
    **這個 skill 產出的東西，能通過這個 skill 自己的驗證器**。
    """
    out = tmp_path / "demo"
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "build_agent.py"), str(out),
         "--name", "demo-bot", "--codename", "小虎", "--admin-chat-id", "123"],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stderr

    v = subprocess.run([sys.executable, str(SCRIPTS / "validate_agent.py"), str(out)],
                       capture_output=True, text=True)
    assert v.returncode == 0, f"scaffold 過不了自己的 validate：\n{v.stdout}"


def test_validate_actually_catches_a_broken_scaffold(tmp_path):
    """反證：把產出弄壞，validate 必須變紅（否則上一條是空轉）"""
    out = tmp_path / "demo"
    subprocess.run([sys.executable, str(SCRIPTS / "build_agent.py"), str(out)],
                   check=True, capture_output=True)
    (out / "knowledge" / "shared" / "schema.md").unlink()
    v = subprocess.run([sys.executable, str(SCRIPTS / "validate_agent.py"), str(out)],
                       capture_output=True, text=True)
    assert v.returncode == 1 and "schema.md" in v.stdout


# ── 來源契約：模板 vs 產生腳本 ────────────────────────────────

def _generator_src() -> str:
    return (SCRIPTS / "build_agent.py").read_text(encoding="utf-8")


def test_bot_yaml_md_dir_is_created_by_generator():
    """assets/bot.yaml 的 report.md_dir 必須在 build_agent.py 的 DIRS 裡

    實例：md_dir 寫 `output/reports`、DIRS 建 `artifacts/reports`
    → 報告寫不出去，而且啟動時不會報錯。
    """
    bot = yaml.safe_load((ASSETS / "bot.yaml").read_text(encoding="utf-8"))
    md_dir = (bot.get("report") or {}).get("md_dir")
    assert md_dir, "bot.yaml 缺 report.md_dir"
    assert f'"{md_dir}"' in _generator_src(), (
        f"bot.yaml 的 md_dir='{md_dir}' 不在 build_agent.py 的 DIRS 裡")


def test_agents_yaml_dirs_are_created_by_generator():
    """assets/agents.yaml 每個 dir（除了 "."）都要在 build_agent.py 的 AGENT_DIRS 裡"""
    ag = yaml.safe_load((ASSETS / "agents.yaml").read_text(encoding="utf-8"))
    src = _generator_src()
    for key, val in ag.items():
        d = (val or {}).get("dir")
        if not d or d == ".":
            continue
        leaf = d.rstrip("/").split("/")[-1]
        assert f'"{leaf}"' in src, (
            f"agents.yaml 的 {key}.dir='{d}' 不會被 build_agent.py 建出來")


def test_agents_yaml_group_members_all_defined():
    """group_members 不得指向未定義的成員（實例：worker-b 從未定義）"""
    ag = yaml.safe_load((ASSETS / "agents.yaml").read_text(encoding="utf-8"))
    for key, val in ag.items():
        for m in ((val or {}).get("group_members") or []):
            assert m in ag, f"{key}.group_members 含 '{m}'，但 agents.yaml 沒定義它"


@pytest.mark.parametrize("rel", ["SKILL.md", "assets/requirements.txt", "scripts/build_agent.py"])
def test_install_commands_carry_extras(rel):
    """三處安裝指令都必須帶 [search,skills]

    只裝 base wheel 會少兩組能力且**不報錯**：
    [search] 缺 → 四層搜尋靜默降級成 purepy + CJK bigram
    [skills] 缺 → schedule_engine 只印一行 WARNING 就跳過
    """
    text = (SKILL_ROOT / rel).read_text(encoding="utf-8")
    if "pip install" not in text:
        pytest.skip(f"{rel} 沒有安裝指令")
    for line in text.splitlines():
        if "pip install" in line and "ark_bot_agent" in line:
            assert "[search,skills]" in line, f"{rel} 的安裝指令沒帶 extras：{line.strip()}"


def test_start_py_skeleton_does_not_inject_empty_skills():
    """start.py 骨架不得寫 run_bot(skills=[...]) —— scaffold 建的 skills/ 是空的

    指向空目錄會讓啟動橫幅永遠印「⚠️ 注入了 skills 但一個都沒載到」，
    而常駐假警報的代價是維運開始習慣性忽略整個橫幅。
    """
    src = (ASSETS / "start.py").read_text(encoding="utf-8")
    code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    assert "skills=[" not in code.replace(" ", ""), (
        "start.py 骨架注入了 skills=[...]，但 scaffold 建的 skills/ 是空的")
    assert "run_bot()" in code


# ── 衛生：跨 skill ────────────────────────────────────────────

@pytest.mark.parametrize("skill", ["ark-agent-bot-builder", "ark-agent-init"])
def test_no_bom_in_assets(skill):
    """asset 不得有 BOM —— frontmatter 的 `\\A---` 會整段解析失敗，且失敗表現是
    「tags 讀成空」而不是報錯。"""
    bad = [str(f) for f in (SKILLS_REPO / skill / "assets").rglob("*")
           if f.is_file() and f.read_bytes()[:3] == b"\xef\xbb\xbf"]
    assert not bad, f"這些 asset 帶 BOM：{bad}"


@pytest.mark.parametrize("name", ["agent.json", "admin-agent.json"])
def test_agent_json_template_contract(name):
    """agent.json 模板：file:// 基準是 .kiro/agents/（要往上兩層），且不得用 allowedTools:['*']"""
    import json
    p = SKILLS_REPO / "ark-agent-init" / "assets" / "agents" / name
    d = json.loads(p.read_text(encoding="utf-8"))
    assert d.get("allowedTools") != ["*"], f"{name} 的 allowedTools 用了 ['*']"
    assert d["prompt"].startswith("file://../../"), (
        f"{name} 的 prompt='{d['prompt']}' —— file:// 基準是 .kiro/agents/，"
        "指向專案根資源要用 ../../")
    for r in d.get("resources", []):
        if isinstance(r, str) and r.startswith("file://") and ".kiro/steering" in r:
            assert r.startswith("file://../../"), f"{name} 的 resource 基準錯：{r}"


def test_skill_md_asset_table_matches_reality():
    """SKILL.md 附帶資源表列的 assets/steering/*.md 必須真的存在

    實例：表上列 AGENTS.md / USER.md / SOUL.md / MEMORY.md，實際檔名是
    BRAIN.md / SOUL-{root,admin,leader,worker}.md / MEMORY-template.md
    → 照著 skill 走的人會發現「說要 copy 的檔案不在」。
    """
    init = SKILLS_REPO / "ark-agent-init"
    text = (init / "SKILL.md").read_text(encoding="utf-8")
    m = re.search(r"### assets/steering/.*?\n(.*?)(?=\n### |\n## |\Z)", text, re.S)
    if not m:
        pytest.skip("SKILL.md 沒有 assets/steering 資源表")
    claimed = set(re.findall(r"\|\s*`([A-Za-z0-9_-]+\.md)`\s*\|", m.group(1)))
    actual = {f.name for f in (init / "assets" / "steering").glob("*.md")}
    missing = sorted(claimed - actual)
    assert not missing, f"SKILL.md 聲稱有但實際不存在的 asset：{missing}（實際有：{sorted(actual)}）"
