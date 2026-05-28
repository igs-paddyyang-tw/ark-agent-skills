"""gen_mcp_json.py — 依 team.yaml 產出每個 agent 的 settings/mcp.json。

Usage:
    python gen_mcp_json.py [team.yaml] [output_base_dir]

產出：
    {output_base}/                    # admin（working_directory: .）
        .kiro/settings/mcp.json
    {output_base}/agents/{name}-agent/
        .kiro/settings/mcp.json

mcp.json 格式（對齊 game-analytics-team 參考實作）：
    admin  → src/ark_team_core/team_mcp.py  --role admin  --home .
    others → ../../src/ark_team_core/team_mcp.py  --role {role}  --home ../..
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml


def gen_mcp_json(team_path: Path, output_base: Path | None = None) -> list[str]:
    """產出所有 agent 的 mcp.json。回傳已建立的路徑清單。"""
    with open(team_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    base = output_base or team_path.parent
    port = cfg.get("health_port", 13030)
    instances = cfg.get("instances", {})

    # 所有非 admin instance 名稱（用於 allowed-targets）
    all_names = list(instances.keys())
    non_admin_names = [n for n, v in instances.items()
                       if (v or {}).get("role") != "admin"]

    created: list[str] = []

    for name, inst in instances.items():
        inst = inst or {}
        role = inst.get("role", "worker")
        wd = inst.get("working_directory", f"agents/{name}")

        if wd == "." or role == "admin":
            # Admin：在根目錄 .kiro/
            settings_dir = base / ".kiro" / "settings"
            mcp_path = settings_dir / "mcp.json"
            mcp_content = _make_admin_mcp(name, port)
        else:
            # 其他 agent：在 agents/{name}/.kiro/
            agent_dir = base / wd
            settings_dir = agent_dir / ".kiro" / "settings"
            mcp_path = settings_dir / "mcp.json"
            # allowed-targets = 所有 non-admin instance（含自己）
            allowed = ",".join(non_admin_names)
            mcp_content = _make_agent_mcp(name, role, port, allowed)

        settings_dir.mkdir(parents=True, exist_ok=True)
        if not mcp_path.exists():
            mcp_path.write_text(
                json.dumps(mcp_content, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            created.append(str(mcp_path.relative_to(base)))

    return created


def _make_admin_mcp(instance: str, port: int) -> dict:
    """Admin 的 mcp.json（cwd = 根目錄）。"""
    return {
        "mcpServers": {
            "team": {
                "command": "py",
                "args": [
                    "src/ark_team_core/team_mcp.py",
                    "--port", str(port),
                    "--instance", instance,
                    "--role", "admin",
                    "--allowed-targets", "",
                    "--home", ".",
                ],
            }
        }
    }


def _make_agent_mcp(instance: str, role: str, port: int, allowed_targets: str) -> dict:
    """非 admin agent 的 mcp.json（cwd = agents/{name}-agent/）。"""
    return {
        "mcpServers": {
            "team": {
                "command": "py",
                "args": [
                    "../../src/ark_team_core/team_mcp.py",
                    "--port", str(port),
                    "--instance", instance,
                    "--role", role,
                    "--allowed-targets", allowed_targets,
                    "--home", "../..",
                ],
            }
        }
    }


def main() -> None:
    team_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("team.yaml")
    output_base = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    if not team_path.exists():
        print(f"❌ {team_path} not found")
        sys.exit(1)

    created = gen_mcp_json(team_path, output_base)
    if created:
        print(f"✅ 產出 {len(created)} 個 mcp.json:")
        for p in created:
            print(f"  • {p}")
    else:
        print("ℹ️ 所有 mcp.json 已存在，無需更新")


if __name__ == "__main__":
    main()
