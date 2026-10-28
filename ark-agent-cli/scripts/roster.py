#!/usr/bin/env python3
"""roster — 讀 agents.yaml（agent 編制的唯一來源），做「選角路由」的確定性那一半。

職責（只做確定性、可測的事；語意選角交給 LLM / manager）：
  - list_candidates()：列出可派工的 agent（dispatchable=true），供 manager 看著挑
  - resolve()：給一個 agent name → 驗證存在且 dispatchable、補出工作目錄 cwd（從 yaml 的 dir 相對 agents.yaml 解析）

分區規則（對齊 agents.yaml 的 role 欄位）：
  - worker：預設選角池（阿智 / 碼哥 / 品管 / 數據 / 情報 / 筆記 …）
  - leader：可被派工；派給它之後要不要再開第二層是 leader 自己的事，本 skill 不管
  - admin：維運 agent，不進預設 worker 池，但 manager/人可明確指定（--route agent:admin）
  - manager / default：互動入口本體（persistent / dispatchable=false），不列入選角

本模組不呼叫 LLM、不 spawn，只回純資料。agent_spawn.py 的 route 子命令與 spawn --route 使用它。
"""
from __future__ import annotations

import os
import pathlib

import agent_common as C

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

# 不列入選角的角色（互動入口本體，非被派工對象）
_NON_DISPATCH_ROLES = {"manager", "default"}


class RosterError(Exception):
    """roster 專用錯誤（找不到 yaml / 缺 PyYAML / name 不合法）。"""


def _yaml_path(yaml_path: str | pathlib.Path | None) -> pathlib.Path:
    if yaml_path:
        p = pathlib.Path(yaml_path)
        if not p.exists():
            raise RosterError(f"指定的 agents.yaml 不存在: {p}")
        return p
    p = C.find_agents_yaml()
    if not p:
        raise RosterError("找不到 agents.yaml（設 env ARK_AGENTS_YAML 或在 workspace 根放一份）")
    return p


def load_roster(yaml_path: str | pathlib.Path | None = None) -> tuple[dict, pathlib.Path]:
    """讀 agents.yaml → (agents dict, yaml 所在目錄)。目錄用來把相對 dir 解成絕對 cwd。"""
    if yaml is None:
        raise RosterError("需要 PyYAML：pip install pyyaml")
    p = _yaml_path(yaml_path)
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise RosterError(f"agents.yaml 格式不對（應為 mapping）: {p}")
    return data, p.parent


def _entry_view(name: str, e: dict, root: pathlib.Path) -> dict:
    """把一筆 agent 定義整理成路由要用的視圖（含解好的絕對 cwd）。"""
    rel = e.get("dir") or "."
    cwd = str((root / rel).resolve())
    return {
        "name": name,
        "codename": e.get("codename") or e.get("name") or name,
        "desc": e.get("desc", ""),
        "role": e.get("role", ""),
        "emoji": e.get("emoji", ""),
        "dispatchable": bool(e.get("dispatchable", False)),
        "dir": rel,
        "cwd": cwd,
    }


def list_candidates(role: str | None = None, yaml_path: str | pathlib.Path | None = None) -> dict:
    """列可派工名單，分兩區：
      workers：dispatchable 且 role 不是 admin/manager/default（leader 也在這區，可被派）
      ops    ：dispatchable 的 admin（維運，需明確指定）
    role 參數可再縮小 workers 區（例如只要 role=worker）。
    回 {"workers":[...], "ops":[...], "source": <yaml 路徑>}。
    """
    data, root = load_roster(yaml_path)
    workers, ops = [], []
    for name, e in data.items():
        if not isinstance(e, dict):
            continue
        v = _entry_view(name, e, root)
        if not v["dispatchable"]:
            continue
        if v["role"] in _NON_DISPATCH_ROLES:
            continue
        if v["role"] == "admin":
            ops.append(v)
            continue
        if role and v["role"] != role:
            continue
        workers.append(v)
    return {"workers": workers, "ops": ops, "source": str(root / "agents.yaml")}


def resolve(name: str, yaml_path: str | pathlib.Path | None = None, allow_admin: bool = True) -> dict:
    """給 agent name → 驗證並回路由視圖（含 cwd）。
    不存在 / 不可派工 → RosterError。manager/default 一律不可派。
    admin 需 allow_admin=True（預設允許，因為是「明確指定」才會走到這）。
    """
    data, root = load_roster(yaml_path)
    e = data.get(name)
    if not isinstance(e, dict):
        avail = [n for n, x in data.items() if isinstance(x, dict) and x.get("dispatchable")]
        raise RosterError(f"agents.yaml 沒有這個 agent: {name}（可派工: {avail}）")
    v = _entry_view(name, e, root)
    if v["role"] in _NON_DISPATCH_ROLES:
        raise RosterError(f"{name} 是互動入口（role={v['role']}），不可被派工")
    if not v["dispatchable"]:
        raise RosterError(f"{name} 的 dispatchable=false，不可被派工")
    if v["role"] == "admin" and not allow_admin:
        raise RosterError(f"{name} 是維運 agent，需明確指定才可派工")
    return v
