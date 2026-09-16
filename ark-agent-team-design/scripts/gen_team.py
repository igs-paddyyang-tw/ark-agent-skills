#!/usr/bin/env python3
"""
gen_team.py — team-spec.yaml → team.yaml 骨架 + role-profile stub + authority-matrix + NEXT.md

用法：
  python gen_team.py team-spec.yaml --out <project_dir> [--roles-dir <ark-agent-role-profile/assets/roles>] [--force]

規則：
- team.yaml 依 ark-agent-team-builder 範本（kiro_files skills skip / team_md always / soul_md once）
- instance 名 = `{id}-agent`；entry 的 working_directory = `.`（其 profile 落專案根）
- worker 的 `group: {leader}-agent`；每個 instance 加 `profile:` 指向其 role-profile.yaml
- stub：角色庫有 base_role → 複製全部欄位並填 relationships；沒有 → 欄位留 `TODO`
- 既有檔案不覆蓋（--force 才覆蓋）；team.yaml 已存在則只印 diff 建議
"""
from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from team_spec_lint import lint, DEFAULT_ROLES_DIR  # noqa: E402

TODO = "TODO"


def inst_name(i: str) -> str:
    return f"{i}-agent"


def build_team_yaml(spec: dict) -> dict:
    d = spec.get("defaults") or {}
    entry = spec["entry"]
    instances: dict = {}
    order = {"manager": 0, "admin": 1, "leader": 2, "worker": 3}
    for i in sorted(spec["instances"], key=lambda x: order[x["tier"]]):
        name = inst_name(i["id"])
        is_entry = i["id"] == entry
        row: dict = {
            "working_directory": "." if is_entry else f"agents/{name}",
            "description": f"{i.get('emoji', '🤖')} {i['purpose']}",
            "role": i["tier"],
            "profile": "role-profile.yaml" if is_entry else f"agents/{name}/role-profile.yaml",
        }
        if i["tier"] == "worker":
            row["group"] = inst_name(i["group"])
        if i.get("persistent") is False:
            row["persistent"] = False
        if i.get("private_chat"):
            row["private_chat"] = i["private_chat"]
        row["skip_resume"] = True
        instances[name] = row

    return {
        "defaults": {"backend": "kiro-cli", "model": "auto"},
        "knowledge_search_order": d.get("knowledge_search_order", ["shared"]),
        "kiro_files": {"skills": {"policy": "skip"},
                       "steering": {"team_md": "always", "soul_md": "once"}},
        "channel": {"bot_token_env": d.get("bot_token_env", "TELEGRAM_BOT_TOKEN")},
        "access": {"mode": "group", "allowed_users": [0]},
        "cost_guard": {"daily_limit_usd": d.get("daily_limit_usd", 20.0),
                       "warn_at_percentage": 80, "timezone": "Asia/Taipei"},
        "hang_detector": {"enabled": True, "timeout_minutes": 180, "escalation_minutes": 360},
        "instances": instances,
        "health_port": d.get("health_port", 13030),
    }


def build_agents_yaml(spec: dict) -> dict:
    """hybrid/bot target：agents.yaml —— 只填 default + manager，關 team 模式。

    🔴 只放 default(entry manager)—— 不填 leader/group_members，
    這樣 bot runtime 不會啟動 team 派工（team 派工由 team daemon 那側負責）。
    """
    entry = spec["entry"]
    entry_inst = next(i for i in spec["instances"] if i["id"] == entry)
    name = inst_name(entry)
    return {
        "default": {
            "name": name,
            "description": f"{entry_inst.get('emoji', '🤖')} {entry_inst['purpose']}",
            "role": "manager",
        },
        # 🔴 刻意不填 leader / group_members —— 關掉 bot 側的 team 派工
    }


def build_bot_yaml(spec: dict) -> dict:
    """hybrid/bot target：bot.yaml —— team_leader 空（關派工）、TG 不啟、Tier 0 + Web UI。"""
    d = spec.get("defaults") or {}
    return {
        "server": {"host": "127.0.0.1", "port": d.get("health_port", 13030) + 5000},
        "modes": {
            "default": "chat",
            "team_leader": "",   # 🔴 空 = 關 team 派工（bot 側不搶派工）
        },
        "features": {"web_ui": True},   # Tier 0 + Web UI；TG 不啟（不搶 poller）
        "backend": {"type": "kiro-cli"},
    }


def build_scheduler_yaml(spec: dict) -> dict:
    """hybrid target：scheduler.yaml —— 長任務（模擬/壓測）從 scheduled_jobs 產。"""
    jobs = []
    for j in spec.get("scheduled_jobs", []):
        jobs.append({
            "id": j["id"],
            "schedule": j["schedule"],
            "task": j["task"],
            "target": inst_name(j["target"]) if j.get("target") else inst_name(spec["entry"]),
        })
    return {"jobs": jobs}


def build_stub(i: dict, spec: dict, roles_dir: Path | None) -> tuple[dict, bool]:
    """回傳 (profile, has_todo)。"""
    by_id = {x["id"]: x for x in spec["instances"]}
    base = None
    if roles_dir and i["base_role"] != "custom":
        p = roles_dir / f"{i['base_role']}.yaml"
        if p.exists():
            base = yaml.safe_load(p.read_text(encoding="utf-8"))
    has_todo = base is None

    prof: dict = copy.deepcopy(base) if base else {
        "schema_version": 1,
        "identity": {"name": None, "emoji": i.get("emoji", "🤖"), "one_liner": TODO, "language": "zh-TW"},
        "stance": [TODO, TODO, TODO],
        "tradeoffs": {"ambiguity": "ask", "speed_vs_quality": "quality", "risk": "conservative"},
        "scope": {"does": [TODO, TODO], "does_not": [TODO], "escalates_to": None},
        "hard_stops": [TODO],
        "anti_patterns": [],
        "voice": {"tone": TODO, "max_chars": 150, "banned_openers": [], "format": "結論先行"},
        "metrics": [],
        "knowledge_domains": [TODO],
        "skills": [],
        "examples": [{"situation": TODO, "response": TODO, "kind": "typical"},
                     {"situation": TODO, "response": TODO, "kind": "pushback"}],
    }
    prof["role_id"] = i["id"]
    prof["base_role"] = i["base_role"]
    prof.setdefault("identity", {})["emoji"] = i.get("emoji", prof["identity"].get("emoji", "🤖"))
    if base is None:
        prof["identity"]["one_liner"] = i["purpose"][:60]

    # relationships / escalation 由 spec 決定（instance 層，永遠覆蓋角色庫）
    esc_to = next((e["to"] for e in spec.get("escalation", []) if e["from"] == i["id"]), None)
    delegates = [inst_name(x["id"]) for x in spec["instances"] if x.get("group") == i["id"]]
    consults = [inst_name(x["id"]) for x in spec["instances"]
                if x["id"] != i["id"] and x.get("tier") == "worker" and x.get("group") == i.get("group") and i["tier"] == "worker"]
    prof["relationships"] = {
        "reports_to": inst_name(i["group"]) if i.get("group") else (inst_name(esc_to) if esc_to else None),
        "delegates_to": delegates,
        "consults": consults,
    }
    prof.setdefault("scope", {})["escalates_to"] = inst_name(esc_to) if esc_to else None
    # 決策鎖 → hard_stops 提示（不自動寫進 hard_stops，只放註解欄位供 role-profile 訪談參考）
    locks = [l["decision"] for l in spec.get("decision_locks", [])
             if l.get("approver") != i["id"] and i["id"] not in (l.get("allowed") or [])
             and l.get("proposer") != i["id"]]
    prof["_hint_locks"] = locks  # 只用於產 stub 檔頭註解，dump 前移除
    _ = by_id
    return prof, has_todo


def build_authority(spec: dict) -> dict:
    return {
        "version": 1,
        "team_id": spec["team_id"],
        "decisions": [
            {
                "decision": l["decision"],
                "approver": l["approver"] if l["approver"] == "human" else inst_name(l["approver"]),
                "proposer": inst_name(l["proposer"]) if l.get("proposer") else None,
                "allowed": [inst_name(x) for x in (l.get("allowed") or [])],
            }
            for l in spec.get("decision_locks", [])
        ],
    }


def build_next(spec: dict, todo_ids: list[str]) -> str:
    lines = [f"# NEXT — {spec['name']}（{spec['team_id']}）建置順序\n",
             "> 每步的產出是下一步的唯一輸入；順序錯（尤其先 start）會讓套件用通用人格產 SOUL 且 `once` 永不覆蓋。\n",
             "| # | 步驟 | skill / 指令 | Gate |", "|---|---|---|---|",
             "| 1 | 裝 wheel + start.py | `ark-agent-team-builder` 步驟 1–2 | import 版號正確 |",
             "| 2 | 檢查 team.yaml | `python validate_team.py team.yaml` | 0 errors |"]
    if todo_ids:
        lines.append(f"| 3 | 補 TODO stub（{len(todo_ids)} 個：{', '.join(todo_ids)}） | `ark-agent-role-profile` standard 訪談 | `profile_lint` P0/P1 = 0 |")
    else:
        lines.append("| 3 | 確認 stub | `profile_lint --all` | P0/P1 = 0 |")
    lines += [
        "| 4 | 渲染人格 | `render_profile.py agents/*/role-profile.yaml` | 每個 SOUL fragment 有 sha 戳記 |",
        "| 5 | 產 .kiro/ | `ark-agent-init --profile` | 品質檢查清單全過 |",
        "| 6 | 裝技能 | `sync_skills.py`（MATRIX 由 profile.skills 生成） | `--check` 零差異 |",
        "| 7 | 行為驗收 | `ark-prompt-spec-validator` L2 × `ark-agent-cli`，跑 profile.examples | pushback 100% |",
        "| 8 | 首次 start | `.venv/bin/python start.py` | health 兩階段就緒 |",
        "\n## 決策鎖（config/authority-matrix.yml）\n",
    ]
    for l in spec.get("decision_locks", []):
        lines.append(f"- **{l['decision']}** → 批准：`{l['approver']}`" +
                     (f"，提案：`{l['proposer']}`" if l.get("proposer") else "") +
                     (f"，可執行：{', '.join(l['allowed'])}" if l.get("allowed") else ""))
    return "\n".join(lines) + "\n"


def write(path: Path, text: str, force: bool) -> str:
    if path.exists() and not force:
        return f"⏭️  {path}（已存在，略過）"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return f"✅ {path}"


def dump(obj: dict) -> str:
    return yaml.safe_dump(obj, allow_unicode=True, sort_keys=False, width=100)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("spec", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--roles-dir", type=Path, default=DEFAULT_ROLES_DIR if DEFAULT_ROLES_DIR.exists() else None)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--skip-lint", action="store_true")
    ap.add_argument("--target", choices=["team", "bot", "hybrid"], default="team",
                    help="team(預設,team.yaml)｜bot(agents.yaml+bot.yaml)｜hybrid(全部+scheduler.yaml)")
    a = ap.parse_args()

    if not a.skip_lint:
        fx = lint(a.spec, a.roles_dir)
        if fx.blocking():
            for lv, m in fx.items:
                print(f"[{lv}] {m}")
            print("❌ team-spec lint 未過，中止")
            return 1

    spec = yaml.safe_load(a.spec.read_text(encoding="utf-8"))
    out = a.out
    header = f"# {spec['name']}（{spec['team_id']}）— 由 ark-agent-team-design 生成，來源 {a.spec.name}\n# 啟動前先讀 NEXT.md。access.allowed_users 換成實際 TG user_id。\n\n"
    # target 決定產哪些設定檔（team.yaml 一律產；bot/hybrid 加 agents.yaml + bot.yaml）
    if a.target in ("team", "hybrid"):
        print(write(out / "team.yaml", header + dump(build_team_yaml(spec)), a.force))
    if a.target in ("bot", "hybrid"):
        bot_hdr = f"# {spec['name']}（{spec['team_id']}）bot runtime — team_leader 空（關派工）、TG 不啟\n\n"
        print(write(out / "agents.yaml", bot_hdr + dump(build_agents_yaml(spec)), a.force))
        print(write(out / "bot.yaml", bot_hdr + dump(build_bot_yaml(spec)), a.force))
    if a.target == "hybrid":
        sched_hdr = "# 長任務（模擬/壓測）—— 由 scheduler 觸發，移出 instances\n\n"
        print(write(out / "scheduler.yaml", sched_hdr + dump(build_scheduler_yaml(spec)), a.force))
    print(write(out / "team-spec.yaml", a.spec.read_text(encoding="utf-8"), a.force))

    todo_ids: list[str] = []
    for i in spec["instances"]:
        prof, has_todo = build_stub(i, spec, a.roles_dir)
        if has_todo:
            todo_ids.append(i["id"])
        dest = out / ("role-profile.yaml" if i["id"] == spec["entry"] else f"agents/{inst_name(i['id'])}/role-profile.yaml")
        tag = "（含 TODO，交 role-profile 訪談）" if has_todo else ""
        locks = prof.pop("_hint_locks", [])
        hint = (f"# role-profile stub — 由 ark-agent-team-design 生成（team-spec: {spec['team_id']}）\n"
                f"# base_role: {i['base_role']} · tier: {i['tier']}\n"
                + (f"# 團隊決策鎖中此角色無權批准/執行：{'；'.join(locks)}（訪談 hard_stops 時參考）\n" if locks else "")
                + ("# ⚠️ 含 TODO：跑 ark-agent-role-profile standard 訪談補完後才可 render\n" if has_todo else "")
                + "\n")
        print(write(dest, hint + dump(prof), a.force) + tag)
        (out / f"agents/{inst_name(i['id'])}" if i["id"] != spec["entry"] else out).mkdir(parents=True, exist_ok=True)
        for sub in ("knowledge/wiki", "knowledge/raw", "memory/daily", "artifacts/reports"):
            base = out if i["id"] == spec["entry"] else out / f"agents/{inst_name(i['id'])}"
            (base / sub).mkdir(parents=True, exist_ok=True)
            (base / sub / ".gitkeep").touch()

    for sub in ("knowledge/shared/wiki", "knowledge/shared/raw", "memory/daily", "memory/archive", "config"):
        (out / sub).mkdir(parents=True, exist_ok=True)
        (out / sub / ".gitkeep").touch()
    print(write(out / "config/authority-matrix.yml", dump(build_authority(spec)), a.force))
    print(write(out / "NEXT.md", build_next(spec, todo_ids), a.force))
    print(f"\n📊 {len(spec['instances'])} instances · {len(todo_ids)} 個 stub 含 TODO · {len(spec.get('decision_locks', []))} 條決策鎖")
    return 0


if __name__ == "__main__":
    sys.exit(main())
