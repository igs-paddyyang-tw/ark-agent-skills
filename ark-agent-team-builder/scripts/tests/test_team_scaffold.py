"""team-builder 端到端守門 —— 範本產出的東西，必須過得了本 skill 自己的驗證器。

## 為什麼需要這支

2026-09-11 用本 skill 第一次實建 market-team，發現 `team.yaml.tpl` **太精簡** ——
缺 `kiro_files` / `access` / `knowledge_search_order` 這些「真實部署都要」的區塊，
補完後沒有任何東西在驗「範本與 validate_team.py 還對得上」。

而 `validate_team.py` 與 `team.yaml.tpl` 是**兩份各自演化的真相**：
一邊加欄位、另一邊加檢查，沒有守門就會漂移（同型於 bot-builder 那 12 條）。

> 🔴 判準：scaffolder 的最低要求是「**它產的東西過得了它自己的驗證器**」。
> 這比逐欄位斷言更耐改 —— 範本改了、驗證器跟著改，這條測試仍然成立。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

SCRIPTS = Path(__file__).resolve().parent.parent
SKILL_ROOT = SCRIPTS.parent
TEMPLATE = SKILL_ROOT / "references" / "templates" / "team.yaml.tpl"
EXAMPLE = SKILL_ROOT / "examples" / "market-team" / "team.yaml"
SKILLS_REPO = SKILL_ROOT.parent   # 上游 skill 庫根目錄

#: 範本的兩個佔位符 —— 用最小合法內容填，只要能通過驗證器即可
INSTANCES_BLOCK = """\
  demo-agent:
    working_directory: .
    description: "總機"
    role: manager

  leader-agent:
    working_directory: agents/leader-agent
    description: "統籌"
    role: leader

  worker-agent:
    working_directory: agents/worker-agent
    description: "職人"
    role: worker
    group: leader-agent
"""
CHANNEL_BLOCK = """\
channel:
  bot_token_env: DEMO_TELEGRAM_BOT_TOKEN
"""


def _render(tmp_path: Path) -> Path:
    out = tmp_path / "team.yaml"
    out.write_text(
        TEMPLATE.read_text(encoding="utf-8")
        .replace("{instances_block}", INSTANCES_BLOCK)
        .replace("{channel_block}", CHANNEL_BLOCK),
        encoding="utf-8",
    )
    return out


def _validate(target: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "validate_team.py"), str(target)],
        capture_output=True, text=True)


# ── 端到端：範本 → 立刻驗 ──────────────────────────────────────

def test_template_renders_and_passes_its_own_validate(tmp_path):
    """把 team.yaml.tpl 填完 → validate_team.py 必須 0 錯誤"""
    r = _validate(_render(tmp_path))
    assert r.returncode == 0, f"範本過不了自己的 validate：\n{r.stdout}"


def test_each_placeholder_appears_exactly_once_in_the_template():
    """🔴 回歸：範本的說明註解曾經**自己寫出**帶大括號的佔位符字面。

    於是「照 SKILL 說的做字串替換」會連註解一起換掉，
    產出的 YAML 在第 2 行就 parse 失敗。註解要描述佔位符，不能長得像佔位符。
    """
    raw = TEMPLATE.read_text(encoding="utf-8")
    for token in ("{instances_block}", "{channel_block}"):
        assert raw.count(token) == 1, \
            f"{token} 在範本裡出現 {raw.count(token)} 次（應為 1 —— 註解別寫字面）"


def test_template_has_no_placeholder_left_after_render(tmp_path):
    """渲染後不得殘留 `{...}` 佔位符（漏填一個就會產出壞設定）"""
    text = _render(tmp_path).read_text(encoding="utf-8")
    leftovers = [ln for ln in text.splitlines()
                 if "{" in ln and "}" in ln and not ln.lstrip().startswith("#")]
    assert not leftovers, f"殘留佔位符：{leftovers}"


def test_template_keeps_the_blocks_real_deployment_needs(tmp_path):
    """kiro_files / access / knowledge_search_order 是實建 market-team 補上的。

    🔴 它們不是選配：缺 `kiro_files.skills.policy: skip`，套件每次啟動都會
    用內建 skill 推翻角色矩陣（本 repo 在 slot 踩過）。掉了就要有人知道。
    """
    cfg = yaml.safe_load(_render(tmp_path).read_text(encoding="utf-8"))
    assert cfg["kiro_files"]["skills"]["policy"] == "skip"
    assert cfg["kiro_files"]["steering"]["team_md"] == "always"
    assert "access" in cfg
    assert "knowledge_search_order" in cfg


def test_shipped_example_is_valid():
    """隨 skill 出貨的範例本身必須合法（別人會照抄）。

    ⚠️ 2026-09-16 `examples/market-team` 已被移除（建 team 標準流程已涵蓋）。
    這條改成「**有就驗、沒有就跳過**」而不是刪掉 —— 哪天再放範例回來，
    它會自動重新受守（刪掉的話就得有人記得再加一次）。
    """
    if not EXAMPLE.is_file():
        pytest.skip("目前沒有出貨範例包（examples/market-team 已於 2026-09-16 移除）")
    r = _validate(EXAMPLE)
    assert r.returncode == 0, f"範例包過不了 validate：\n{r.stdout}"


# ── scaffold_dirs：宣告了 working_directory 就要真的建出來 ────────

def test_scaffold_dirs_creates_every_relative_working_directory(tmp_path):
    team = _render(tmp_path)
    r = subprocess.run([sys.executable, str(SCRIPTS / "scaffold_dirs.py"), str(team)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr

    cfg = yaml.safe_load(team.read_text(encoding="utf-8"))
    for name, inst in cfg["instances"].items():
        wd = inst.get("working_directory", f"agents/{name}")
        if wd == ".":
            # 總機住在專案根目錄，不另外建（套件讀根層 .kiro/）
            assert not (tmp_path / "agents" / name).exists()
            continue
        for sub in ("knowledge", "docs"):
            assert (tmp_path / wd / sub).is_dir(), f"{name}: 缺 {wd}/{sub}"


def test_scaffold_dirs_is_idempotent(tmp_path):
    """第二次跑必須 0 新增 —— 否則重跑會覆寫既有內容"""
    team = _render(tmp_path)
    cmd = [sys.executable, str(SCRIPTS / "scaffold_dirs.py"), str(team)]
    subprocess.run(cmd, check=True, capture_output=True)
    second = subprocess.run(cmd, capture_output=True, text=True)
    assert second.returncode == 0
    assert "already exist" in second.stdout, second.stdout


# ── 反證：驗證器要真的會紅（否則上面全是空轉）────────────────────

@pytest.mark.parametrize("mutate,expect", [
    (lambda c: c["instances"].pop("leader-agent"), "no leader"),
    (lambda c: c["instances"].update({"BadName": {"working_directory": "a",
                                                  "description": "x",
                                                  "role": "worker"}}), "pattern"),
    (lambda c: c["instances"]["worker-agent"].update({"role": "boss"}), "invalid role"),
    (lambda c: c.pop("cost_guard"), "cost_guard"),
])
def test_validate_actually_catches_broken_config(tmp_path, mutate, expect):
    cfg = yaml.safe_load(_render(tmp_path).read_text(encoding="utf-8"))
    mutate(cfg)
    broken = tmp_path / "broken.yaml"
    broken.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")

    r = _validate(broken)
    assert r.returncode == 1, f"弄壞了卻仍然通過（{expect}）：\n{r.stdout}"
    assert expect in r.stdout, r.stdout


# ── 出貨的範例包不得指向上游已移除的 skill ──────────────────────

def test_shipped_example_references_only_existing_skills():
    """🔴 範例包是新專案照抄的東西 —— 它指到已移除的 skill，等於量產斷鏈。

    2026-09-15 實測漏掉過一次：`ark-ingest-guard` 併入 `ark-wiki-engine` 時，
    三個真實消費端的矩陣都改了，**唯獨這份範例沒改**，
    而它還被複製進 nana-team-agent 的 skill 複本裡（靠掃消費端才反向發現）。

    上游自己的範例不在 `check_consumers.py` 的掃描範圍（它掃 `projects/`），
    所以這條由本 skill 自己守。
    """
    import ast
    ex = SKILL_ROOT / "examples" / "market-team" / "scripts" / "sync_skills.py"
    if not ex.is_file():
        pytest.skip("範例包沒有 sync_skills.py")

    names: set[str] = set()
    for node in ast.walk(ast.parse(ex.read_text(encoding="utf-8"))):
        tgt = (getattr(node.targets[0], "id", "") if isinstance(node, ast.Assign)
               else getattr(node.target, "id", "") if isinstance(node, ast.AnnAssign) else None)
        if tgt in ("MATRIX", "COMMON"):
            v = ast.literal_eval(node.value)
            names |= set(v) if isinstance(v, list) else {s for lst in v.values() for s in lst}

    assert names, "沒解析到任何 skill 名字 —— MATRIX 是 AnnAssign，別只判 ast.Assign"
    upstream = {d.name for d in SKILLS_REPO.glob("ark-*") if (d / "SKILL.md").is_file()}
    missing = sorted(n for n in names if n.startswith("ark-") and n not in upstream)
    assert not missing, f"範例包指向上游已不存在的 skill：{missing}"
