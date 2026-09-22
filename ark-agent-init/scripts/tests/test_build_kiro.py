"""agent-init 端到端守門 —— 產出的 .kiro/ 必須落在 team.yaml 宣告的位置。

## 為什麼需要這支

2026-09-14 加 F-3 守門時實測發現：`build_kiro.py` 用 **role** 決定 `.kiro/` 放哪
（`wd == "." or role == "admin"` → 根目錄），而**套件執行期是用 `working_directory`**。
於是 `admin-agent: working_directory: agents/admin-agent` 的團隊，
admin 的人格被寫到根目錄，它自己的工作目錄一個檔案都沒有。

> 🔴 而 `validate_kiro()` **抄了同一條規則**去找檔案 → 找得到、回報通過。
> 產生器與驗證器共用同一個錯誤假設時，驗證等於互相背書。
> 這條測試刻意**直接讀 team.yaml 的 working_directory** 來斷言，不呼叫驗證器。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

SCRIPTS = Path(__file__).resolve().parent.parent
BUILD = SCRIPTS / "build_kiro.py"
GEN_MCP = SCRIPTS / "gen_mcp_json.py"

TEAM_YAML = """\
defaults:
  backend: kiro-cli
  model: auto

cost_guard:
  daily_limit_usd: 10.0
  warn_at_percentage: 80
  timezone: Asia/Taipei

hang_detector:
  enabled: true

instances:
  demo-agent:
    working_directory: .
    description: "🗺️ 總機 — 意圖路由"
    role: manager

  admin-agent:
    working_directory: agents/admin-agent
    description: "👑 維運 — 監控、費控"
    role: admin

  leader-agent:
    working_directory: agents/leader-agent
    description: "🎯 統籌 — 拆解、派工"
    role: leader

  worker-agent:
    working_directory: agents/worker-agent
    description: "🔍 職人 — 執行"
    role: worker
    group: leader-agent

health_port: 23040
"""


@pytest.fixture()
def project(tmp_path):
    (tmp_path / "team.yaml").write_text(TEAM_YAML, encoding="utf-8")
    r = subprocess.run([sys.executable, str(BUILD), str(tmp_path / "team.yaml"),
                        str(tmp_path)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return tmp_path


def _kiro_dir(base: Path, wd: str) -> Path:
    return base / ".kiro" if wd == "." else base / wd / ".kiro"


def _instances() -> dict:
    return yaml.safe_load(TEAM_YAML)["instances"]


# ── 端到端：產出 → 立刻用自己的驗證器驗 ─────────────────────────

def test_build_passes_its_own_validate(project):
    r = subprocess.run([sys.executable, str(BUILD), "--validate", str(project)],
                       capture_output=True, text=True)
    assert r.returncode == 0, f"產出過不了自己的 validate：\n{r.stdout}"


# ── 落點：以 team.yaml 為準，不看 role ──────────────────────────

@pytest.mark.parametrize("name,inst", sorted(_instances().items()))
def test_kiro_lands_at_declared_working_directory(project, name, inst):
    """每個 instance 的 .kiro/ 必須在它宣告的 working_directory 底下。

    🔴 admin-agent 是這條的重點：它的 role 是 admin，但 wd 是 agents/admin-agent
    —— 落點由 wd 決定，不由 role 決定（套件執行期就是這樣讀的）。
    """
    kiro = _kiro_dir(project, inst["working_directory"])
    assert (kiro / "steering" / "SOUL.md").is_file(), f"{name}: 缺 {kiro}/steering/SOUL.md"
    assert (kiro / "agents" / f"{name}.json").is_file(), f"{name}: 缺 agent.json"
    assert (kiro / "settings" / "mcp.json").is_file(), f"{name}: 缺 mcp.json"


def test_no_two_instances_share_one_kiro(project):
    """兩個 instance 落在同一個 .kiro/ = 後者靜默共用/覆寫前者的人格"""
    dirs = [str(_kiro_dir(project, i["working_directory"]))
            for i in _instances().values()]
    assert len(dirs) == len(set(dirs)), f"落點重複：{dirs}"


# ── 內容：不得殘留佔位符、mcp.json 要能解析且授權正確 ─────────────

def test_no_placeholder_residue(project):
    pattern = re.compile(r"\{\{?[a-z_]+\}?\}|TODO_|XXX_")
    hits = [f"{p}: {pattern.search(p.read_text(encoding='utf-8')).group()}"
            for p in project.rglob(".kiro/**/*.md")
            if pattern.search(p.read_text(encoding="utf-8"))]
    assert not hits, f"殘留佔位符：{hits}"


@pytest.mark.parametrize("name,inst", sorted(_instances().items()))
def test_mcp_json_declares_instance_and_role(project, name, inst):
    mcp = json.loads((_kiro_dir(project, inst["working_directory"])
                      / "settings" / "mcp.json").read_text(encoding="utf-8"))
    args = mcp["mcpServers"]["team"]["args"]
    assert args[args.index("--instance") + 1] == name
    assert args[args.index("--role") + 1] == inst["role"]


def test_admin_is_the_only_one_with_an_empty_target_whitelist(project):
    """admin 的白名單是空字串（＝不限制）；其他角色帶實際清單。

    ⚠️ 授權邊界要看 `--allowed-targets` 的**值**，不能看它在不在 ——
    每個角色都有這個旗標，空與非空才是差別。
    """
    def targets_of(inst):
        mcp = json.loads((_kiro_dir(project, inst["working_directory"])
                          / "settings" / "mcp.json").read_text(encoding="utf-8"))
        args = mcp["mcpServers"]["team"]["args"]
        return args[args.index("--allowed-targets") + 1]

    insts = _instances()
    assert targets_of(insts["admin-agent"]) == ""
    for name in ("demo-agent", "leader-agent", "worker-agent"):
        assert "admin-agent" not in targets_of(insts[name]).split(","), \
            f"{name} 不該能直接指派 admin"
        assert targets_of(insts[name]), name


@pytest.mark.parametrize("wd,expected_home", [(".", "."), ("agents/admin-agent", "../..")])
def test_home_is_derived_from_directory_depth(project, wd, expected_home):
    """--home 由實際深度算出，不是照 role 寫死（admin 搬家也要指得對）"""
    mcp = json.loads((_kiro_dir(project, wd) / "settings" / "mcp.json")
                     .read_text(encoding="utf-8"))
    args = mcp["mcpServers"]["team"]["args"]
    assert args[args.index("--home") + 1] == expected_home


def test_mcp_entrypoint_matches_the_installed_package(project):
    """進入點必須是現行套件 —— 舊值 `py src/ark_team_core/team_mcp.py` 兩層都錯了

    （`py` 是 Windows 啟動器、`ark_team_core` 是三代前的套件名）。
    """
    mcp = json.loads((project / ".kiro" / "settings" / "mcp.json")
                     .read_text(encoding="utf-8"))
    team = mcp["mcpServers"]["team"]
    assert team["command"] != "py", "py 是 Windows 啟動器，Linux 上不存在"
    assert team["args"][:2] == ["-m", "ark_team_agent.team_mcp"], team["args"]


# ── 冪等：重跑不得覆寫手寫人格 ──────────────────────────────────

def test_rerun_does_not_overwrite_handwritten_soul(project):
    soul = project / "agents" / "leader-agent" / ".kiro" / "steering" / "SOUL.md"
    soul.write_text("# 我手寫的人格\n", encoding="utf-8")
    subprocess.run([sys.executable, str(BUILD), str(project / "team.yaml"),
                    str(project)], check=True, capture_output=True)
    assert soul.read_text(encoding="utf-8") == "# 我手寫的人格\n"


# ── gen_mcp_json 與 build_kiro 必須產出同一份 mcp.json ───────────

def test_gen_mcp_json_agrees_with_build_kiro(project):
    """兩支腳本各自實作 _make_*_mcp —— 兩份真相，必須對得上"""
    before = {p: p.read_text(encoding="utf-8")
              for p in project.rglob(".kiro/settings/mcp.json")}
    for p in before:
        p.unlink()

    r = subprocess.run([sys.executable, str(GEN_MCP), str(project / "team.yaml"),
                        str(project)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    for p, content in before.items():
        assert p.is_file(), f"gen_mcp_json 沒產出 {p}"
        assert json.loads(p.read_text(encoding="utf-8")) == json.loads(content), \
            f"{p}: gen_mcp_json 與 build_kiro 產出不一致"


# ── 反證：驗證器要真的會紅 ──────────────────────────────────────

@pytest.mark.parametrize("victim", [
    ".kiro/steering/SOUL.md",
    "agents/leader-agent/.kiro/settings/mcp.json",
    "agents/admin-agent/.kiro/steering/TEAM.md",
])
def test_validate_actually_catches_a_missing_file(project, victim):
    (project / victim).unlink()
    r = subprocess.run([sys.executable, str(BUILD), "--validate", str(project)],
                       capture_output=True, text=True)
    assert r.returncode == 1, f"刪了 {victim} 卻仍然通過：\n{r.stdout}"


# ── v2.1：根目錄即 manager 的目錄佈局 ──────────────────────────

def test_root_has_no_steering_agents_md(project):
    """根目錄（wd="."）不產 steering/AGENTS.md —— 它用專案根那份（SSOT），
    否則兩份都被 Kiro 載入造成漂移。子 agent 仍各有一份複本。"""
    root_agents = project / ".kiro" / "steering" / "AGENTS.md"
    assert not root_agents.exists(), "根 steering/ 不該產 AGENTS.md（用專案根那份）"
    # 子 agent 仍需要複本
    worker_agents = project / "agents" / "worker-agent" / ".kiro" / "steering" / "AGENTS.md"
    assert worker_agents.exists(), "子 agent steering/ 應有 AGENTS.md 複本"


@pytest.mark.parametrize("name,inst", sorted(_instances().items()))
def test_agent_json_points_at_its_own_steering_with_dotdot(project, name, inst):
    """`file://` 的基準是**放這個 json 的目錄**，也就是 `<X>/.kiro/agents/`。

    所以指向「自己那層的 steering」必須是 `../../.kiro/steering/...`：

    | agent 在哪 | `file://../../.kiro/steering/SOUL.md` 解析成 |
    |---|---|
    | 根目錄（wd="."） | `<專案根>/.kiro/steering/SOUL.md` ✅ |
    | `agents/worker-agent`（任何深度） | `agents/worker-agent/.kiro/steering/SOUL.md` ✅ |

    🔴 `../../` **不是「假設兩層深」** —— 它是從 `.kiro/agents/` 回到
    **這個 agent 自己的 workspace 根**，與 agent 位在幾層無關。
    寫成 `file://.kiro/steering/SOUL.md` 會解析成
    `<X>/.kiro/agents/.kiro/steering/SOUL.md`（多一層 `.kiro/agents/`）。

    2026-09-15 曾被改成無 `../..` 的版本（`92646c3`），2026-09-16 revert。
    證據（不是推論）：兩個**實際在跑**的部署（`nana-team-agent`、`paddy-bot`）
    都用 `file://../../.kiro/steering/SOUL.md`，且專案 CLAUDE.md 的
    「`file://` 相對路徑陷阱」明寫基準是 `.kiro/agents/`。

    ⚠️ 本測試**實際解析路徑**並確認檔案存在 —— 只比對字串會讓下一個人再翻一次。
    """
    kiro = _kiro_dir(project, inst["working_directory"])
    d = json.loads((kiro / "agents" / f"{name}.json").read_text(encoding="utf-8"))

    assert d["prompt"] == "file://../../.kiro/steering/SOUL.md", d["prompt"]
    resolved = (kiro / "agents" / d["prompt"].removeprefix("file://")).resolve()
    assert resolved == (kiro / "steering" / "SOUL.md").resolve(), resolved
    assert resolved.is_file(), f"{name}: prompt 指到的檔案不存在 {resolved}"


# ── B1b / B2 / B4：五類知識來源 + knowledge_search_order ──────────

_SOURCES_TEAM_YAML = """\
team: { name: aibi-demo }
knowledge_sources: [private, hoyeah, github, shared, weknora]
instances:
  aibi-manager: { role: manager, base_role: aibi-manager, working_directory: . }
  query-analyst: { role: worker, base_role: query-analyst, working_directory: agents/query-analyst }
"""


@pytest.fixture()
def sources_project(tmp_path):
    (tmp_path / "team.yaml").write_text(_SOURCES_TEAM_YAML, encoding="utf-8")
    r = subprocess.run([sys.executable, str(BUILD), str(tmp_path / "team.yaml"),
                        str(tmp_path)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return tmp_path


def test_b1b_builds_five_source_shelves(sources_project):
    """B1b：所選來源層各建 knowledge 櫃骨架；weknora 不建櫃。"""
    k = sources_project / "knowledge"
    # shared / 產品(hoyeah) / private(各 instance)
    assert (k / "shared" / "wiki").is_dir()
    assert (k / "hoyeah" / "wiki").is_dir()
    assert (k / "aibi-manager" / "wiki").is_dir()            # dir="." 的 manager → knowledge/<name>/
    assert (sources_project / "agents" / "query-analyst" / "knowledge" / "wiki").is_dir()
    # weknora 不建櫃（外部 RAG）
    assert not (k / "weknora").exists()
    # github → github-sources.yaml 骨架
    assert (sources_project / "github-sources.yaml").is_file()


def test_b2_writes_search_order_trust_descending(sources_project):
    """B2：team.yaml 自動寫 knowledge_search_order，信任度遞減，weknora 排除。"""
    cfg = yaml.safe_load((sources_project / "team.yaml").read_text(encoding="utf-8"))
    order = cfg.get("knowledge_search_order")
    assert order == ["private", "hoyeah", "github", "shared"], order
    assert "weknora" not in order


def test_b2_default_when_no_sources(tmp_path):
    """B2：未宣告 knowledge_sources → 預設 [private, shared]。"""
    (tmp_path / "team.yaml").write_text(
        "team: { name: d }\ninstances:\n  m: { role: manager, working_directory: . }\n",
        encoding="utf-8")
    subprocess.run([sys.executable, str(BUILD), str(tmp_path / "team.yaml"), str(tmp_path)],
                   capture_output=True, text=True)
    cfg = yaml.safe_load((tmp_path / "team.yaml").read_text(encoding="utf-8"))
    assert cfg["knowledge_search_order"] == ["private", "shared"]
    assert not (tmp_path / "github-sources.yaml").exists()


def test_b2_idempotent_does_not_overwrite(tmp_path):
    """B2：已有 knowledge_search_order 不覆蓋（冪等）。"""
    (tmp_path / "team.yaml").write_text(
        "team: { name: d }\nknowledge_sources: [private, shared]\n"
        "knowledge_search_order: [private, custom, shared]\n"
        "instances:\n  m: { role: manager, working_directory: . }\n",
        encoding="utf-8")
    subprocess.run([sys.executable, str(BUILD), str(tmp_path / "team.yaml"), str(tmp_path)],
                   capture_output=True, text=True)
    cfg = yaml.safe_load((tmp_path / "team.yaml").read_text(encoding="utf-8"))
    assert cfg["knowledge_search_order"] == ["private", "custom", "shared"]


def test_b4_validate_passes_on_wellformed(sources_project):
    """B4：正常產出通過 validate 的 knowledge 檢查。"""
    sys.path.insert(0, str(SCRIPTS))
    from build_kiro import _validate_knowledge_sources
    cfg = yaml.safe_load((sources_project / "team.yaml").read_text(encoding="utf-8"))
    errs = _validate_knowledge_sources(cfg, sources_project)
    assert errs == [], errs


def test_b4_validate_catches_missing_shelf_and_weknora_in_order(sources_project):
    """B4 反證：缺 shared 目錄 → 報錯；weknora 進 search_order → 報錯。"""
    sys.path.insert(0, str(SCRIPTS))
    from build_kiro import _validate_knowledge_sources
    import shutil
    # 反證① 移走 shared
    shutil.rmtree(sources_project / "knowledge" / "shared")
    cfg = yaml.safe_load((sources_project / "team.yaml").read_text(encoding="utf-8"))
    errs = _validate_knowledge_sources(cfg, sources_project)
    assert any("shared" in e and "不存在" in e for e in errs), errs
    # 反證② weknora 混進 order
    cfg["knowledge_search_order"] = ["private", "hoyeah", "github", "shared", "weknora"]
    errs2 = _validate_knowledge_sources(cfg, sources_project)
    assert any("weknora" in e for e in errs2), errs2
