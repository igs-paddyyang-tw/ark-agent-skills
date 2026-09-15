"""build_kiro.py — 依 team.yaml 一鍵產出所有 agent 的 .kiro/ 配置。

Usage:
    python build_kiro.py [team.yaml] [output_base_dir]
    python build_kiro.py --validate [project_dir]

產出：
    {base}/
    ├── .kiro/                        # working_directory: "." 的 agent（通常是總機/manager）
    │   ├── agents/{admin}.json
    │   ├── prompts/route-message.md
    │   ├── prompts/service-check.md
    │   ├── settings/mcp.json
    │   ├── skills/                   # 空目錄（由 clone_skills.py 填充）
    │   └── steering/
    │       ├── AGENTS.md
    │       ├── CODE.md
    │       ├── MEMORY.md
    │       ├── SOUL.md
    │       ├── TEAM.md
    │       └── USER.md
    └── agents/{name}-agent/
        └── .kiro/
            ├── agents/{name}.json
            ├── prompts/daily-report.md
            ├── prompts/team-check.md
            ├── settings/mcp.json
            ├── skills/               # 空目錄（由 clone_skills.py 填充）
            └── steering/
                ├── AGENTS.md
                ├── CODE.md
                ├── MEMORY.md
                ├── SOUL.md
                ├── TEAM.md
                └── USER.md

v1.0 — 對齊 game-analytics-team 參考實作
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

import yaml

# ── 常數 ─────────────────────────────────────────────────────

SKILL_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = SKILL_ROOT / "assets"
STEERING_ASSETS = ASSETS_DIR / "steering"
AGENTS_ASSETS = ASSETS_DIR / "agents"

#: team MCP 的現行進入點（套件 ark_team_agent）。
#: 🔴 舊值是 `src/ark_team_core/team_mcp.py` + `command: "py"` —— 前者是三代前的
#: 套件名（現在裝的是 ark_team_agent，且以 `-m` 呼叫），後者是 Windows 啟動器，
#: 在 Linux 上根本不存在。對照組：套件自己在啟動時寫的 mcp.json。
TEAM_MCP_MODULE = "ark_team_agent.team_mcp"
PROMPTS_ASSETS = ASSETS_DIR / "prompts"

TODAY = date.today().isoformat()


# ── 主函式 ────────────────────────────────────────────────────

def build_kiro(team_path: Path, output_base: Path | None = None,
               profile: str | None = None) -> list[str]:
    """產出所有 agent 的 .kiro/ 配置。回傳已建立的路徑清單。

    profile 給定時：根目錄（working_directory="."）的 manager SOUL 改由
    ark-agent-role-profile 渲染指定角色（非預設 admin/worker 模板）。
    """
    with open(team_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    base = output_base or team_path.parent
    instances = cfg.get("instances", {})
    all_names = list(instances.keys())
    non_admin_names = [n for n, v in instances.items()
                       if (v or {}).get("role") != "admin"]
    port = cfg.get("health_port", 13030)
    team_name = base.name

    created: list[str] = []

    for name, inst in instances.items():
        inst = inst or {}
        role = inst.get("role", "worker")
        wd = inst.get("working_directory", f"agents/{name}")
        description = inst.get("description", f"{name}")

        # 🔴 落點與授權是兩件事，別綁在一起（2026-09-14 修）：
        #   落點 = working_directory —— 套件執行期就是照這個欄位去讀 .kiro/
        #   授權 = role —— admin 才拿得到「可發訊給所有人」的 MCP
        # 舊碼寫成 `wd == "." or role == "admin"` 同時決定兩者，造成兩個錯：
        #   ① admin 宣告了 agents/admin-agent 卻被寫到根目錄 → 它的工作目錄空的
        #   ② wd="." 的 manager 被當成 admin → 拿到 admin 人格與無白名單的 MCP
        kiro_dir = base / ".kiro" if wd == "." else base / wd / ".kiro"
        is_admin = role == "admin"
        # profile 只作用於根目錄（wd="."）的 manager —— 其餘 instance 走原模板
        inst_profile = profile if wd == "." else None
        is_root = wd == "."

        agent_created = _build_agent_kiro(
            kiro_dir=kiro_dir,
            name=name,
            role=role,
            description=description,
            is_admin=is_admin,
            team_name=team_name,
            all_instances=instances,
            non_admin_names=non_admin_names,
            port=port,
            base=base,
            profile=inst_profile,
            is_root=is_root,
        )
        created.extend(agent_created)

    return created


def _build_agent_kiro(
    kiro_dir: Path,
    name: str,
    role: str,
    description: str,
    is_admin: bool,
    team_name: str,
    all_instances: dict,
    non_admin_names: list[str],
    port: int,
    base: Path,
    profile: str | None = None,
    is_root: bool = False,
) -> list[str]:
    """產出單一 agent 的 .kiro/ 目錄。"""
    created: list[str] = []

    # 建立目錄結構
    for sub in ("agents", "prompts", "settings", "skills", "steering"):
        (kiro_dir / sub).mkdir(parents=True, exist_ok=True)

    # 1. steering/
    steering_created = _build_steering(
        kiro_dir / "steering", name, role, description,
        team_name, all_instances, is_admin, profile, is_root,
    )
    created.extend(steering_created)

    # 2. agents/{name}.json
    agent_json = kiro_dir / "agents" / f"{name}.json"
    if not agent_json.exists():
        _write_agent_json(agent_json, name, description, is_admin)
        created.append(str(agent_json.relative_to(base)))

    # 3. settings/mcp.json
    mcp_json = kiro_dir / "settings" / "mcp.json"
    # admin mcp.json 強制覆蓋（build_team.py 可能先產出空 {}）
    needs_write = not mcp_json.exists()
    if not needs_write and is_admin:
        try:
            existing = json.loads(mcp_json.read_text(encoding="utf-8"))
            if not existing.get("mcpServers") or existing["mcpServers"] == {}:
                needs_write = True  # 空 mcpServers → 覆蓋
        except Exception:
            needs_write = True
    if needs_write:
        allowed = ",".join(non_admin_names)
        # --home 是「從這個 agent 的工作目錄回到團隊根」的相對路徑。
        # 🔴 舊碼把它寫死成 admin=`.`／其他=`../..`，等於假設 admin 一定住根目錄；
        #    改成由實際深度算，admin 搬到 agents/ 底下也不會指錯。
        home = _relative_home(kiro_dir.parent, base)
        if is_admin:
            mcp_content = _make_admin_mcp(name, port, home)
        else:
            mcp_content = _make_agent_mcp(name, role, port, allowed, home)
        mcp_json.write_text(
            json.dumps(mcp_content, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        created.append(str(mcp_json.relative_to(base)))

    # 4. prompts/
    prompts_created = _build_prompts(kiro_dir / "prompts", role, is_admin, base)
    created.extend(prompts_created)

    return created


# ── steering/ ─────────────────────────────────────────────────

def _build_steering(
    steering_dir: Path,
    name: str,
    role: str,
    description: str,
    team_name: str,
    all_instances: dict,
    is_admin: bool,
    profile: str | None = None,
    is_root: bool = False,
) -> list[str]:
    """產出 steering/ 下的所有檔案。"""
    created: list[str] = []
    base = steering_dir.parent.parent.parent  # kiro_dir -> base

    # SOUL.md
    soul = steering_dir / "SOUL.md"
    if not soul.exists():
        _write_soul(soul, name, role, description, team_name, len(all_instances), profile)
        created.append(str(soul.relative_to(base)))

    # AGENTS.md（從 assets 複製）
    # 🔴 根目錄（is_root）不在 steering/ 產 AGENTS.md —— 根目錄的 .kiro/steering/AGENTS.md
    #    與專案根 AGENTS.md 會「兩份都被 Kiro 載入」造成漂移。根目錄用專案根那份（SSOT）。
    #    子 agent 仍在自己的 steering/ 放一份（複本，供該 agent 載入）。
    agents_md = steering_dir / "AGENTS.md"
    if not is_root and not agents_md.exists():
        src = STEERING_ASSETS / "AGENTS.md"
        if src.exists():
            shutil.copy2(src, agents_md)
        else:
            agents_md.write_text(_default_agents_md(), encoding="utf-8")
        created.append(str(agents_md.relative_to(base)))

    # CODE.md（從 assets 複製）
    code_md = steering_dir / "CODE.md"
    if not code_md.exists():
        src = STEERING_ASSETS / "CODE.md"
        if src.exists():
            shutil.copy2(src, code_md)
        created.append(str(code_md.relative_to(base)))

    # MEMORY.md
    memory_md = steering_dir / "MEMORY.md"
    if not memory_md.exists():
        memory_md.write_text(_default_memory_md(name, team_name), encoding="utf-8")
        created.append(str(memory_md.relative_to(base)))

    # USER.md（從 assets 複製）
    user_md = steering_dir / "USER.md"
    if not user_md.exists():
        src = STEERING_ASSETS / "USER.md"
        if src.exists():
            shutil.copy2(src, user_md)
        else:
            user_md.write_text(_default_user_md(), encoding="utf-8")
        created.append(str(user_md.relative_to(base)))

    # TEAM.md（動態產出，含成員表）
    team_md = steering_dir / "TEAM.md"
    if not team_md.exists():
        _write_team_md(team_md, name, role, all_instances)
        created.append(str(team_md.relative_to(base)))

    return created


def _render_profile_soul(profile: str) -> str | None:
    """呼叫 ark-agent-role-profile 的 render_profile 渲染指定角色的 SOUL。

    profile 可以是角色 id（如 qa-manager）或 role-profile.yaml 路徑。
    成功回傳渲染後的 SOUL 內容（含 profile-sha256 戳記），
    失敗（角色不存在、render 腳本缺、非零退出）回傳 None。
    """
    rp_root = SKILL_ROOT.parent / "ark-agent-role-profile"
    render = rp_root / "scripts" / "render_profile.py"
    if not render.exists():
        return None
    # profile 是路徑就直接用，否則當角色 id 到角色庫找
    prof_path = Path(profile)
    if not prof_path.exists():
        prof_path = rp_root / "assets" / "roles" / f"{profile}.yaml"
    if not prof_path.exists():
        return None
    with tempfile.TemporaryDirectory() as tmp:
        try:
            subprocess.run(
                [sys.executable, str(render), str(prof_path), "--out", tmp],
                check=True, capture_output=True, text=True,
            )
        except (subprocess.CalledProcessError, OSError):
            return None
        frag = Path(tmp) / "SOUL.fragment.md"
        if not frag.exists():
            return None
        return frag.read_text(encoding="utf-8")


def _write_soul(
    path: Path,
    name: str,
    role: str,
    description: str,
    team_name: str,
    agent_count: int,
    profile: str | None = None,
) -> None:
    """產出 SOUL.md，依角色選擇模板。

    profile 給定時（僅根目錄 manager）：改由 ark-agent-role-profile 的
    render_profile 渲染指定角色的 SOUL（含 profile-sha256 戳記），
    不使用內建 admin/leader/worker 模板。未給時行為完全不變（向後相容）。
    """
    if profile:
        rendered = _render_profile_soul(profile)
        if rendered is not None:
            path.write_text(rendered, encoding="utf-8")
            return
        # 渲染失敗（角色不存在等）→ 印警告後退回模板路徑，不中斷
        print(f"  ⚠️  --profile {profile} 渲染失敗，退回內建模板", file=sys.stderr)

    if role == "admin":
        tpl_file = STEERING_ASSETS / "SOUL-admin.md"
    elif role == "leader":
        tpl_file = STEERING_ASSETS / "SOUL-leader.md"
    else:
        tpl_file = STEERING_ASSETS / "SOUL-worker.md"

    if tpl_file.exists():
        content = tpl_file.read_text(encoding="utf-8")
        # 替換佔位符
        short = name.replace("-agent", "")
        emoji = _role_emoji(role, description)
        content = (content
            .replace("{AGENT_NAME}", name)
            .replace("{AGENT_SHORT}", short)
            .replace("{TEAM_NAME}", team_name)
            .replace("{AGENT_COUNT}", str(agent_count))
            .replace("{DESCRIPTION}", description)
            .replace("{ROLE_DESCRIPTION}", description)
            .replace("{SPECIALTY}", description)
            .replace("{EMOJI}", emoji))
    else:
        content = _fallback_soul(name, role, description)

    path.write_text(content, encoding="utf-8")


def _write_team_md(
    path: Path,
    instance_name: str,
    role: str,
    all_instances: dict,
) -> None:
    """產出 TEAM.md（含動態成員表）。"""
    tpl_file = STEERING_ASSETS / "TEAM.md"
    if tpl_file.exists():
        content = tpl_file.read_text(encoding="utf-8")
    else:
        content = _default_team_md_template()

    # 產出成員表
    rows = []
    for n, inst in all_instances.items():
        inst = inst or {}
        r = inst.get("role", "worker")
        desc = inst.get("description", "")
        rows.append(f"| {n} | {r} | {desc} |")
    members_table = "\n".join(rows)

    # 權限說明
    perms = {
        "admin": "可發訊給所有人",
        "leader": "可發訊給所有人（除 admin）",
        "worker": "可發訊給 leader + 其他 worker",
    }.get(role, "標準權限")

    content = (content
        .replace("{MEMBERS_TABLE}", members_table)
        .replace("{INSTANCE_NAME}", instance_name)
        .replace("{ROLE}", role)
        .replace("{PERMISSIONS}", perms))

    path.write_text(content, encoding="utf-8")


# ── agents/{name}.json ────────────────────────────────────────

def _write_agent_json(path: Path, name: str, description: str, is_admin: bool) -> None:
    """產出 agent.json。"""
    if is_admin:
        tpl_file = AGENTS_ASSETS / "admin-agent.json"
    else:
        tpl_file = AGENTS_ASSETS / "agent.json"

    if tpl_file.exists():
        content = tpl_file.read_text(encoding="utf-8")
        short = name.replace("-agent", "")
        content = (content
            .replace("{AGENT_NAME}", name)
            .replace("{AGENT_SHORT}", short)
            .replace("{DESCRIPTION}", description))
        path.write_text(content, encoding="utf-8")
    else:
        # Fallback
        data = {
            "name": name,
            "description": description,
            "prompt": "file://.kiro/steering/SOUL.md",
            "model": "auto",
            "tools": ["*"],
            "allowedTools": ["*"],
            "resources": [
                "file://.kiro/steering/**/*.md",
                "skill://.kiro/skills/**/SKILL.md",
            ],
        }
        if is_admin:
            data["resources"].append({
                "type": "knowledgeBase",
                "source": "file://./knowledge",
                "name": "AdminKnowledge",
                "description": "團隊規範、運維紀錄",
            })
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ── mcp.json ──────────────────────────────────────────────────

def _relative_home(agent_dir: Path, base: Path) -> str:
    """從 agent 工作目錄回到團隊根的相對路徑（根目錄回 "."）。"""
    depth = len(agent_dir.resolve().relative_to(base.resolve()).parts)
    return "." if depth == 0 else "/".join([".."] * depth)

def _make_admin_mcp(instance: str, port: int, home: str = ".") -> dict:
    return {
        "mcpServers": {
            "team": {
                "command": "python3",
                "args": [
                    "-m", TEAM_MCP_MODULE,
                    "--port", str(port),
                    "--instance", instance,
                    "--role", "admin",
                    "--allowed-targets", "",   # 空 = 不限制（admin 可發訊給所有人）
                    "--home", home,
                ],
            }
        }
    }


def _make_agent_mcp(instance: str, role: str, port: int, allowed_targets: str,
                    home: str = "../..") -> dict:
    return {
        "mcpServers": {
            "team": {
                "command": "python3",
                "args": [
                    "-m", TEAM_MCP_MODULE,
                    "--port", str(port),
                    "--instance", instance,
                    "--role", role,
                    "--allowed-targets", allowed_targets,
                    "--home", home,
                ],
            }
        }
    }


# ── prompts/ ──────────────────────────────────────────────────

def _build_prompts(prompts_dir: Path, role: str, is_admin: bool, base: Path) -> list[str]:
    """產出 prompts/ 下的提詞模板。"""
    created: list[str] = []

    if is_admin or role == "admin":
        files = ["route-message.md", "service-check.md"]
    elif role == "leader":
        files = ["daily-report.md", "team-check.md"]
    else:
        files = ["daily-report.md"]

    for fname in files:
        dst = prompts_dir / fname
        if not dst.exists():
            src = PROMPTS_ASSETS / fname
            if src.exists():
                shutil.copy2(src, dst)
                created.append(str(dst.relative_to(base)))

    return created


# ── 工具函式 ──────────────────────────────────────────────────

def _role_emoji(role: str, description: str) -> str:
    """從 description 或 role 推斷 emoji。"""
    desc_lower = description.lower()
    for emoji, keywords in [
        ("👑", ["admin", "管理"]),
        ("🧠", ["pm", "leader", "專案", "project"]),
        ("💻", ["coder", "dev", "engineer", "工程"]),
        ("🧪", ["qa", "test", "測試"]),
        ("📊", ["data", "analyst", "數據"]),
        ("📰", ["market", "research", "市場"]),
        ("📋", ["report", "報告"]),
        ("🤖", ["ai", "llm", "ml"]),
        ("⚙️", ["devops", "ops", "維運"]),
    ]:
        if any(kw in desc_lower for kw in keywords):
            return emoji
    return {"admin": "👑", "leader": "🧠", "worker": "💻"}.get(role, "🤖")


def _default_memory_md(name: str, team_name: str) -> str:
    return (
        f"# 🧠 {name} 專案記憶\n\n"
        f"> 每完成一個段落必須更新。\n\n---\n\n"
        f"## 專案快照\n\n"
        f"- **團隊：** {team_name}\n"
        f"- **建立日期：** {TODAY}\n"
        f"- **狀態：** 初始化\n\n"
        "## 待辦\n\n- [ ] 確認任務\n\n"
        "## 近期進度\n\n（待填充）\n"
    )


def _default_user_md() -> str:
    return (
        "# USER.md — 使用者百科\n\n"
        "## 個人特徵與偏好\n\n"
        "- **稱呼：** （填入）\n"
        "- **偏好語言：** 繁體中文\n\n"
        "## 溝通風格\n\n"
        "- **回答風格：** 簡短直接\n"
        "- **字數限制：** ≤ 150 字\n"
    )


def _default_agents_md() -> str:
    return (
        "# 團隊共用行為準則\n\n"
        "> 所有 agent 必須遵守。**所有回覆使用繁體中文。**\n\n"
        "## 工具使用規則\n\n"
        "- reply(text, kind) — 回覆使用者\n"
        "- send_to_instance — 跨 agent 通訊\n"
        "- log_to_leader — 錯誤/過程私下回報\n\n"
        "## 回覆風格\n\n"
        "- 結論先行\n- 不貼 raw stdout\n- ≤ 150 字\n"
    )


def _default_team_md_template() -> str:
    return (
        "# 團隊運作規範\n\n"
        "## 團隊成員\n\n"
        "| Instance | 角色 | 職責 |\n|----------|------|------|\n"
        "{MEMBERS_TABLE}\n\n"
        "## 你的身份\n\n"
        "- **Instance**: {INSTANCE_NAME}\n"
        "- **Role**: {ROLE}\n"
        "- **權限**: {PERMISSIONS}\n"
    )


def _fallback_soul(name: str, role: str, description: str) -> str:
    emoji = _role_emoji(role, description)
    return (
        f"# {emoji} {name} — {description}\n\n"
        "> **所有回覆使用繁體中文。**\n\n"
        "## 🧠 Your Identity & Memory\n\n"
        f"- **Role**：{role}\n"
        f"- **Description**：{description}\n\n"
        "## 🎯 Your Core Mission\n\n"
        "1. 接收任務並執行\n"
        "2. 回報結果給 leader\n\n"
        "## ⚙️ Tool Settings\n\n"
        "- All tools are trusted\n"
    )


# ── validate ──────────────────────────────────────────────────

def validate_kiro(project_dir: Path) -> list[str]:
    """驗證 .kiro/ 結構完整性。"""
    errors: list[str] = []
    team_yaml = project_dir / "team.yaml"
    if not team_yaml.exists():
        return ["❌ team.yaml not found"]

    with open(team_yaml, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    seen: dict[str, str] = {}
    for name, inst in cfg.get("instances", {}).items():
        inst = inst or {}
        wd = inst.get("working_directory", f"agents/{name}")

        # 落點只看 working_directory —— 與 build_kiro() 同一條規則。
        # 🔴 這裡曾經抄了「role == 'admin' → 根目錄」那條錯規則，
        #    於是產生器把檔案放錯地方、驗證器也去錯地方找 → 互相背書、永遠綠。
        kiro_dir = project_dir / ".kiro" if wd == "." else project_dir / wd / ".kiro"

        # 兩個 instance 落在同一個 .kiro/ = 後者靜默共用前者的人格與授權
        if str(kiro_dir) in seen:
            errors.append(f"❌ {name} 與 {seen[str(kiro_dir)]} 共用同一個 .kiro/（{wd}）")
        seen[str(kiro_dir)] = name

        prefix = f"{name}/.kiro"

        # 必要目錄
        for sub in ("agents", "prompts", "settings", "steering"):
            if not (kiro_dir / sub).exists():
                errors.append(f"❌ {prefix}/{sub}/ 缺少")

        # agent.json
        agent_json = kiro_dir / "agents" / f"{name}.json"
        if not agent_json.exists():
            errors.append(f"❌ {prefix}/agents/{name}.json 缺少")

        # mcp.json
        mcp_json = kiro_dir / "settings" / "mcp.json"
        if not mcp_json.exists():
            errors.append(f"❌ {prefix}/settings/mcp.json 缺少")
        else:
            try:
                mcp = json.loads(mcp_json.read_text(encoding="utf-8"))
                if "mcpServers" not in mcp:
                    errors.append(f"⚠️ {prefix}/settings/mcp.json 缺少 mcpServers")
                else:
                    team_server = mcp["mcpServers"].get("team", {})
                    args = team_server.get("args", [])
                    if "--instance" not in args:
                        errors.append(f"⚠️ {prefix}/settings/mcp.json 缺少 --instance 參數")
                    if "--role" not in args:
                        errors.append(f"⚠️ {prefix}/settings/mcp.json 缺少 --role 參數")
            except (json.JSONDecodeError, Exception) as e:
                errors.append(f"⚠️ {prefix}/settings/mcp.json 格式錯誤: {e}")

        # steering 必要檔案
        # 🔴 根目錄（wd="."）不要求 steering/AGENTS.md —— 它用專案根 AGENTS.md（SSOT），
        #    build_kiro 也刻意不在根 steering/ 產 AGENTS.md（避免兩份都被載入）。
        required_steering = ("SOUL.md", "AGENTS.md", "MEMORY.md", "USER.md", "TEAM.md")
        if wd == ".":
            required_steering = ("SOUL.md", "MEMORY.md", "USER.md", "TEAM.md")
        for fname in required_steering:
            if not (kiro_dir / "steering" / fname).exists():
                errors.append(f"❌ {prefix}/steering/{fname} 缺少")

        # prompts 至少 1 個
        prompts = list((kiro_dir / "prompts").glob("*.md")) if (kiro_dir / "prompts").exists() else []
        if not prompts:
            errors.append(f"⚠️ {prefix}/prompts/ 無提詞模板")

    return errors


# ── clone_skills ──────────────────────────────────────────────

def clone_skills(project_dir: Path) -> str:
    """Clone 或更新 skills/ 倉庫。"""
    import subprocess
    skills_dir = project_dir / "skills"
    repo_url = "https://github.com/igs-paddyyang-tw/ark-kiro-skills.git"

    if skills_dir.exists() and (skills_dir / ".git").exists():
        result = subprocess.run(
            ["git", "pull", "origin", "main"],
            cwd=skills_dir, capture_output=True, text=True,
        )
        return f"✅ skills/ 已更新\n{result.stdout.strip()}"
    else:
        result = subprocess.run(
            ["git", "clone", repo_url, str(skills_dir)],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            count = len(list(skills_dir.glob("ark-*/SKILL.md")))
            return f"✅ skills/ 已 clone（{count} 個 Skills）"
        return f"❌ clone 失敗: {result.stderr.strip()}"


# ── CLI ──────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 1:
        print("Usage:")
        print("  python build_kiro.py [team.yaml] [output_dir]  # 產出 .kiro/")
        print("  python build_kiro.py --validate [project_dir]  # 驗證結構")
        print("  python build_kiro.py --clone-skills [project_dir]  # clone skills/")
        sys.exit(1)

    if len(sys.argv) > 1 and sys.argv[1] == "--validate":
        target = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")
        errors = validate_kiro(target)
        if errors:
            print(f"\n❌ {len(errors)} 項問題（{target}）:\n")
            for e in errors:
                print(f"  {e}")
            sys.exit(1)
        else:
            print(f"\n✅ .kiro/ 結構完整（{target}）")
        return

    if len(sys.argv) > 1 and sys.argv[1] == "--clone-skills":
        target = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")
        print(clone_skills(target))
        return

    # --profile <role>：抽出後不進位置參數（向後相容：不給則 None）
    argv = sys.argv[1:]
    profile: str | None = None
    if "--profile" in argv:
        i = argv.index("--profile")
        if i + 1 < len(argv):
            profile = argv[i + 1]
            del argv[i:i + 2]
        else:
            print("❌ --profile 需要一個角色 id 或 yaml 路徑")
            sys.exit(1)

    team_path = Path(argv[0]) if len(argv) > 0 else Path("team.yaml")
    output_base = Path(argv[1]) if len(argv) > 1 else None

    if not team_path.exists():
        print(f"❌ {team_path} not found")
        sys.exit(1)

    created = build_kiro(team_path, output_base, profile)
    base = output_base or team_path.parent

    print(f"\n✅ .kiro/ 配置已產出（{base}）\n")
    print(f"📁 產出 {len(created)} 項:")
    for f in created:
        print(f"  • {f}")
    print(f"\n📋 下一步:")
    print(f"  1. python build_kiro.py --clone-skills {base}  # clone skills/")
    print(f"  2. python build_kiro.py --validate {base}      # 驗證結構")
    print(f"  3. python start.py                              # 啟動團隊")


if __name__ == "__main__":
    # 🔴 在讀位置參數之前攔截 —— 否則 `--help` 會被當成路徑，
    #    輕則 exit≠0，重則在 cwd 產出整包骨架（scripts/tests/test_cli_contract.py 在驗）。
    if {"-h", "--help"} & set(sys.argv[1:]):
        print(__doc__ or "")
        raise SystemExit(0)
    main()
