#!/usr/bin/env python3
"""test_registry_path.py — _registry_path() 三層查找回歸測試（p1）。

不需要 WeKnora 服務：純函式行為測試。
三層查找語意（先命中先用）：
  1. ARK_WEKNORA_KB_REGISTRY 環境變數（最高優先）
  2. knowledge/shared/weknora/kb_registry.json（W1 共用單一來源，沿 __file__ 往上找）
  3. <skill>/kb_registry.json（fallback，repo 自足）

每一層都正反各驗一次，避免「規則沒作用」的假綠燈。

執行：pytest .kiro/skills/ark-weknora-cli/tests/test_registry_path.py
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parent.parent
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _weknora_chat as wc  # noqa: E402

SKILL_FALLBACK = (SCRIPTS / "..").resolve() / "kb_registry.json"


# ── 第 1 層：環境變數覆蓋 ────────────────────────────────────────────────

def test_layer1_env_override_wins(monkeypatch, tmp_path):
    """AC-W1-1：設了 ARK_WEKNORA_KB_REGISTRY → 用它，壓過其他兩層。"""
    custom = tmp_path / "my_reg.json"
    custom.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("ARK_WEKNORA_KB_REGISTRY", str(custom))
    assert wc._registry_path() == Path(str(custom))


def test_layer1_env_not_set_falls_through(monkeypatch):
    """反證：未設環境變數 → 絕不回傳環境變數路徑（落到第 2/3 層）。"""
    monkeypatch.delenv("ARK_WEKNORA_KB_REGISTRY", raising=False)
    got = wc._registry_path()
    # 落點必為 shared 單一來源或 skill fallback，兩者都以 kb_registry.json 結尾
    assert got.name == "kb_registry.json"


# ── 第 2 層：knowledge/shared/weknora 單一來源 ───────────────────────────

def test_layer2_shared_source_found(monkeypatch):
    """AC-W1-2：未設環境變數但 shared 來源存在 → 命中 shared（往上逐層找到）。"""
    monkeypatch.delenv("ARK_WEKNORA_KB_REGISTRY", raising=False)
    # 偽造一個「存在的」shared 路徑：攔截 Path.exists，只讓目標 shared 路徑回 True
    target = None
    for base in Path(wc.__file__).resolve().parents:
        cand = base / "knowledge" / "shared" / "weknora" / "kb_registry.json"
        target = cand  # 取最靠近 __file__ 的候選（迴圈第一個 base 即最深層）
        break
    real_exists = Path.exists

    def fake_exists(self):
        if self == target:
            return True
        return real_exists(self)

    monkeypatch.setattr(Path, "exists", fake_exists)
    got = wc._registry_path()
    assert got == target, f"shared 來源存在時應命中它，實際 {got}"


def test_layer2_shared_absent_falls_to_skill(monkeypatch):
    """反證：shared 來源都不存在 → 落到第 3 層 skill fallback。"""
    monkeypatch.delenv("ARK_WEKNORA_KB_REGISTRY", raising=False)
    real_exists = Path.exists

    def fake_exists(self):
        # 任何 shared 候選一律不存在，其餘照舊
        if self.parent.name == "weknora" and self.name == "kb_registry.json":
            return False
        return real_exists(self)

    monkeypatch.setattr(Path, "exists", fake_exists)
    got = wc._registry_path()
    assert got == SKILL_FALLBACK, f"shared 不存在時應落到 skill fallback，實際 {got}"


# ── 第 3 層：skill 內建佔位 fallback ─────────────────────────────────────

def test_layer3_skill_fallback_path(monkeypatch):
    """AC-W1-3：fallback 路徑就是 <skill>/kb_registry.json。"""
    monkeypatch.delenv("ARK_WEKNORA_KB_REGISTRY", raising=False)
    real_exists = Path.exists

    def fake_exists(self):
        if self.parent.name == "weknora" and self.name == "kb_registry.json":
            return False
        return real_exists(self)

    monkeypatch.setattr(Path, "exists", fake_exists)
    assert wc._registry_path() == SKILL_FALLBACK


# ── load_kb_registry 透過 _registry_path 讀到真值 ───────────────────────

def test_load_reads_from_env_override(monkeypatch, tmp_path):
    """整合：環境變數指到一份有真 UUID 的表 → load_kb_registry 讀得到、過濾註解鍵。"""
    reg = tmp_path / "reg.json"
    reg.write_text(json.dumps({
        "_note": "comment",
        "game-dev": "uuid-1234",
    }, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("ARK_WEKNORA_KB_REGISTRY", str(reg))
    loaded = wc.load_kb_registry()
    assert loaded == {"game-dev": "uuid-1234"}, f"應讀到並過濾 _note：{loaded}"
    assert wc.resolve_kb("game-dev") == "uuid-1234"
    assert wc.resolve_kb("unknown-alias") == "unknown-alias"  # fallback 原樣


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
