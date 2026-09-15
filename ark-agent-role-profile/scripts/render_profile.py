#!/usr/bin/env python3
"""
render_profile.py — role-profile.yaml → IDENTITY.md + SOUL/AGENTS/schema fragment。

用法：
  python render_profile.py role-profile.yaml --out ./rendered [--skip-lint]

渲染前預設先跑 profile_lint（P0/P1 不為零即中止）。
每個輸出檔頭嵌 `<!-- profile-sha256: … -->`，供偵測 yaml 已改但 md 未重渲染。
刻意不渲染 MCP Tools / Tool Settings：那屬 AGENTS.md / TEAM.md（operating rules）。
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from profile_lint import lint_file  # noqa: E402

TRADEOFF_TEXT = {
    "ambiguity": {"ask": "需求模糊時先問，不猜", "minimal_then_confirm": "需求模糊時先做最小版本再確認",
                  "conservative": "需求模糊時照最保守解讀執行"},
    "speed_vs_quality": {"speed": "速度與品質衝突時，先交付再補", "quality": "速度與品質衝突時，品質優先"},
    "risk": {"conservative": "風險偏好：保守", "balanced": "風險偏好：平衡", "aggressive": "風險偏好：積極"},
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def stamp(digest: str, source: str) -> str:
    return f"<!-- profile-sha256: {digest} · source: {source} · rendered by ark-agent-role-profile -->\n"


def render_identity(p: dict, hdr: str) -> str:
    idn = p["identity"]
    name = idn.get("name") or p["role_id"]
    return (hdr + "---\ninclusion: always\n---\n"
            f"# IDENTITY — {idn['emoji']} {name}\n\n"
            f"- **Name**：{name}\n- **Emoji**：{idn['emoji']}\n"
            f"- **Role**：{p['role_id']}（base: {p['base_role']}）\n"
            f"- **One-liner**：{idn['one_liner']}\n- **Language**：{idn['language']}\n")


def render_soul(p: dict, hdr: str) -> str:
    idn = p["identity"]
    name = idn.get("name") or p["role_id"]
    out = [hdr, f"# {idn['emoji']} {name} — {idn['one_liner']}\n",
           f"> 所有回覆使用{'繁體中文' if idn['language'] == 'zh-TW' else idn['language']}。\n"]
    out.append("## 📌 Your Stance（據此做決策）\n")
    out += [f"{i}. {s}" for i, s in enumerate(p["stance"], 1)]
    out.append("\n## ⚖️ Default Tradeoffs\n")
    out += [f"- {TRADEOFF_TEXT[k][v]}" for k, v in p["tradeoffs"].items()]
    out.append("\n## 🎯 Your Core Mission\n")
    out += [f"{i}. {d}" for i, d in enumerate(p["scope"]["does"], 1)]
    out.append("\n**不歸你管（轉出）**：" + "、".join(p["scope"]["does_not"]))
    if p["scope"].get("escalates_to"):
        out.append(f"**超出範圍時升報**：`{p['scope']['escalates_to']}`")
    out.append("\n## 🚫 Hard Stops（誰要求都不做）\n")
    out += [f"- {h}" for h in p["hard_stops"]]
    if p.get("anti_patterns"):
        out.append("\n## 🪞 Anti-patterns（發現自己在做時）\n")
        out += [f"- **{a['pattern']}** → {a['correction']}" for a in p["anti_patterns"]]
    v = p["voice"]
    out.append("\n## 💭 Your Communication Style\n")
    out.append(f"- 語氣：{v['tone']}\n- 字數：≤ {v['max_chars']} 字\n- 格式：{v['format']}")
    if v.get("banned_openers"):
        out.append("- 禁用開場白：" + "／".join(v["banned_openers"]))
    if p.get("metrics"):
        out.append("\n## 📏 Your Success Metrics\n\n| 指標 | 目標 |\n|------|------|")
        out += [f"| {m['name']} | {m['target']} |" for m in p["metrics"]]
    out.append("\n## 🎭 Examples\n")
    for ex in p["examples"]:
        tag = "頂回" if ex.get("kind") == "pushback" else "典型"
        out.append(f"**[{tag}] {ex['situation']}**\n→ {ex['response']}\n")
    return "\n".join(out) + "\n"


def render_agents(p: dict, hdr: str) -> str:
    r = p.get("relationships") or {}
    name = p["identity"].get("name") or p["role_id"]
    rows = [f"| 回報對象 | `{r.get('reports_to') or '—'}` |",
            f"| 可派工 | {', '.join(f'`{x}`' for x in r.get('delegates_to') or []) or '—'} |",
            f"| 會諮詢 | {', '.join(f'`{x}`' for x in r.get('consults') or []) or '—'} |",
            f"| 升報 | `{p['scope'].get('escalates_to') or '—'}` |"]
    return (hdr + f"## {name} 協作關係\n\n| 關係 | 對象 |\n|------|------|\n" + "\n".join(rows) + "\n\n"
            "職責：" + "、".join(p["scope"]["does"]) + "\n轉出：" + "、".join(p["scope"]["does_not"]) + "\n")


def render_schema(p: dict, hdr: str) -> str:
    return (hdr + "## 適合存放的知識\n\n" + "\n".join(f"- {k}" for k in p["knowledge_domains"]) +
            "\n\n> 對話記錄只進 memory/，不進 knowledge/；wiki 只有使用者明確要求才寫。\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("profile", type=Path)
    ap.add_argument("--out", type=Path, default=Path("."))
    ap.add_argument("--skip-lint", action="store_true")
    ap.add_argument("--skills-root", type=Path, default=None)
    a = ap.parse_args()

    if not a.skip_lint:
        fx = lint_file(a.profile, a.skills_root)
        if fx.blocking():
            for lv, m in fx.items:
                print(f"[{lv}] {m}")
            print("❌ lint 未過，中止渲染")
            return 1

    p = yaml.safe_load(a.profile.read_text(encoding="utf-8"))
    hdr = stamp(sha(a.profile), a.profile.name)
    a.out.mkdir(parents=True, exist_ok=True)
    files = {
        "IDENTITY.md": render_identity(p, hdr),
        "SOUL.fragment.md": render_soul(p, hdr),
        "AGENTS.fragment.md": render_agents(p, hdr),
        "schema.fragment.md": render_schema(p, hdr),
    }
    for fn, body in files.items():
        (a.out / fn).write_text(body, encoding="utf-8")
        print(f"✅ {a.out / fn}  ({len(body.encode()) / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
