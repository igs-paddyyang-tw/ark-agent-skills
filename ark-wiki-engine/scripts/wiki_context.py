"""wiki_context.py — 查詢 → 可直接注入的 context 區塊（v3）

給「注入點」用：hook / instance prompt 組裝 / agent 自行帶 context。

    python wiki_context.py --knowledge_root knowledge --domains hoyeah,shared \
        --query "$USER_MSG" --top_k 3 --budget_chars 2500
    python wiki_context.py --wiki_dir knowledge/shared/wiki --query "留存口徑" --format json

## 三條規則（都刻意）

1. **未審核的內容一定帶 ⚠** —— `approved: false` 的頁面是 llm-distilled 未經人工核對，
   注入時不標註等於把它當成已確認的事實。
2. **超過預算整筆丟棄，不截半段** —— 截斷會產生殘缺句，而模型會照著殘缺句推論。
   寧可少一筆完整的，不要多一筆斷頭的。
3. **零結果輸出空字串 exit 0** —— 注入端可以無條件串接，不必判斷有沒有結果。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent))
from _wikilib import ErrorCode, emit_error, emit_json  # noqa: E402
from wiki_query import run_query  # noqa: E402


def _query_args(top_k: int) -> SimpleNamespace:
    """組出 run_query 需要的參數物件（context 用固定設定：不取全文、不過濾）。"""
    return SimpleNamespace(
        top_k=top_k, type="", tags="", status="", trust="", approved_only=False,
        layers="", full=False, tokenizer="auto",
    )


def build_context(targets: list[tuple[str, Path]], query: str, top_k: int,
                  budget: int) -> tuple[list[dict], list[str]]:
    """回傳 (採用的頁面, 警告)。採用與否只看預算，順序照分數。"""
    args = _query_args(top_k)
    rows: list[dict] = []
    warnings: list[str] = []
    for domain, wd in targets:
        r, meta = run_query(wd, query, args, domain=domain)
        rows.extend(r)
        warnings.extend(meta["warnings"])
    rows.sort(key=lambda r: -r["score"])

    picked: list[dict] = []
    used = 0
    for r in rows[:top_k]:
        line = _render_line(r)
        if used + len(line) > budget:
            continue          # 整筆丟棄（規則 2）
        picked.append(r)
        used += len(line)
    return picked, sorted(set(warnings))


def _render_line(r: dict) -> str:
    flag = " ⚠未審核" if r.get("approved") is False else ""
    trust = r.get("trust") or "unknown"
    return f"[{r['title']}｜trust:{trust}{flag}] {r['summary']}"


def render_md(picked: list[dict]) -> str:
    if not picked:
        return ""                      # 規則 3
    lines = [_render_line(r) for r in picked]
    refs = ", ".join(r["page"] for r in picked)
    return "\n".join(lines) + f"\n---\n📚 參考：{refs}"


def main() -> None:
    p = argparse.ArgumentParser(description="Wiki Context — 查詢結果轉可注入區塊")
    p.add_argument("--wiki_dir", default="")
    p.add_argument("--knowledge_root", default="")
    p.add_argument("--domains", default="")
    p.add_argument("--query", required=True)
    p.add_argument("--top_k", type=int, default=3)
    p.add_argument("--budget_chars", type=int, default=2500)
    p.add_argument("--format", default="md", choices=["md", "json"])
    args = p.parse_args()

    if bool(args.wiki_dir) == bool(args.knowledge_root):
        emit_error(ErrorCode.BAD_ARGUMENTS, "--wiki_dir 與 --knowledge_root/--domains 二擇一")

    if args.wiki_dir:
        targets = [("", Path(args.wiki_dir))]
    else:
        root = Path(args.knowledge_root)
        doms = [d.strip() for d in args.domains.split(",") if d.strip()]
        if not doms:
            emit_error(ErrorCode.BAD_ARGUMENTS,
                       "--knowledge_root 必須搭配 --domains（D-4：不預設掃全部 domain）")
        targets = [(d, root / d / "wiki") for d in doms]

    for _d, wd in targets:
        if not wd.exists():
            emit_error(ErrorCode.WIKI_DIR_NOT_FOUND, f"目錄不存在：{wd}")

    picked, warnings = build_context(targets, args.query, args.top_k, args.budget_chars)

    if args.format == "json":
        emit_json({"ok": True, "query": args.query,
                   "context": render_md(picked),
                   "pages": [r["page"] for r in picked],
                   "meta": {"picked": len(picked), "budget_chars": args.budget_chars,
                            "unapproved": sum(1 for r in picked
                                              if r.get("approved") is False),
                            "warnings": warnings}})
    sys.stdout.write(render_md(picked))
    if picked:
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
