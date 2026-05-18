"""驗證 team.yaml 結構完整性。

Usage:
    python validate_team.py [path/to/team.yaml]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]*-agent$")
_VALID_ROLES = {"admin", "manager", "leader", "worker"}


def validate(path: Path) -> list[str]:
    """回傳錯誤清單，空 = 通過。"""
    errors: list[str] = []
    if not path.exists():
        return [f"{path} not found"]

    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    if not isinstance(cfg, dict):
        return ["team.yaml is not a valid YAML mapping"]

    # 必要區塊
    for key in ("defaults", "cost_guard", "hang_detector", "instances", "health_port"):
        if key not in cfg:
            errors.append(f"missing top-level key: {key}")

    # defaults 檢查
    defaults = cfg.get("defaults", {})
    if defaults:
        if "backend" not in defaults:
            errors.append("defaults: missing 'backend'")
        if "model" not in defaults:
            errors.append("defaults: missing 'model'")

    # cost_guard 檢查
    cg = cfg.get("cost_guard", {})
    if cg:
        for field in ("daily_limit_usd", "warn_at_percentage", "timezone"):
            if field not in cg:
                errors.append(f"cost_guard: missing '{field}'")

    # hang_detector 檢查
    hd = cfg.get("hang_detector", {})
    if hd:
        if "enabled" not in hd:
            errors.append("hang_detector: missing 'enabled'")

    # instances 檢查
    instances = cfg.get("instances", {})
    if not instances:
        errors.append("no instances defined")
        return errors

    # 恰好 1 個 leader
    leaders = [n for n, v in instances.items() if v.get("role") == "leader"]
    if len(leaders) == 0:
        errors.append("no leader role found")
    elif len(leaders) > 1:
        errors.append(f"multiple leaders: {leaders}")

    # 每個 instance 必要欄位 + 命名規範
    for name, inst in instances.items():
        for field in ("working_directory", "description", "role"):
            if field not in inst:
                errors.append(f"{name}: missing '{field}'")

        # 命名規範
        if not _NAME_PATTERN.match(name):
            errors.append(f"{name}: must match pattern ^[a-z][a-z0-9-]*-agent$")

        # role 合法性
        role = inst.get("role", "")
        if role and role not in _VALID_ROLES:
            errors.append(f"{name}: invalid role '{role}' (valid: {_VALID_ROLES})")

    # health_port 檢查
    port = cfg.get("health_port")
    if port is not None and not isinstance(port, int):
        errors.append(f"health_port must be int, got {type(port).__name__}")

    return errors


def main() -> None:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("team.yaml")
    errs = validate(target)
    if errs:
        print(f"❌ {len(errs)} error(s) in {target}:")
        for e in errs:
            print(f"  - {e}")
        sys.exit(1)
    print(f"✅ {target} is valid")


if __name__ == "__main__":
    main()
