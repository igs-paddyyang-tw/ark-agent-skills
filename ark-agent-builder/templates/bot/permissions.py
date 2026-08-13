"""權限管理 — 白名單 + 角色分級。

泛化自 ninja-bot src/bot/permissions.py。
"""
from __future__ import annotations

import logging
from enum import IntEnum
from typing import Optional

log = logging.getLogger(__name__)


class Role(IntEnum):
    BLOCKED = 0
    GUEST = 1
    USER = 2
    ADMIN = 3
    OWNER = 4


class PermissionManager:
    """基於白名單的權限管理。"""

    def __init__(self, owner_ids: list[int], admin_ids: list[int] = None,
                 user_ids: list[int] = None, open_access: bool = False):
        self._roles: dict[int, Role] = {}
        self._open_access = open_access
        for uid in owner_ids:
            self._roles[uid] = Role.OWNER
        for uid in (admin_ids or []):
            self._roles[uid] = Role.ADMIN
        for uid in (user_ids or []):
            self._roles[uid] = Role.USER

    def check(self, user_id: int, required: Role = Role.USER) -> bool:
        """檢查用戶是否有足夠權限。"""
        role = self._roles.get(user_id, Role.GUEST if self._open_access else Role.BLOCKED)
        return role >= required

    def get_role(self, user_id: int) -> Role:
        return self._roles.get(user_id, Role.GUEST if self._open_access else Role.BLOCKED)

    def grant(self, user_id: int, role: Role) -> None:
        self._roles[user_id] = role
        log.info("Granted %s to user %d", role.name, user_id)
