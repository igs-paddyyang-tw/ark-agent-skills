"""report_pair.py — 雙軌漂移檢查器（Content 軌 MD ↔ View 軌 HTML）。

原理：ark-html-report 渲染時在 HTML 內嵌戳記註解
    <!-- content-src: {md相對路徑} sha256:{md檔案雜湊前16碼} -->
本工具驗證配對狀態，防止「只改 HTML」或「改了 MD 沒重渲染」的兩軌漂移。

用法：
    python report_pair.py check docs/reports/review/2026-08-11-xxx.md
        → OK / STALE（MD 已改、HTML 未重渲染）/ NO-HTML / NO-STAMP
    python report_pair.py stamp report.md report.html
        → 將正確戳記寫入（或更新）HTML，渲染流程最後一步呼叫
    python report_pair.py scan docs/reports/
        → 掃描整個目錄的配對狀態總表

Exit code：check/scan 發現 STALE 或 NO-STAMP 時回 1。
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

STAMP_RE = re.compile(r"<!--\s*content-src:\s*(\S+)\s+sha256:([0-9a-f]{16})\s*-->")


def md_hash(md_path: Path) -> str:
    return hashlib.sha256(md_path.read_bytes()).hexdigest()[:16]


def html_candidates(md_path: Path) -> list[Path]:
    """依 ark-html-report 路徑約定尋找配對 HTML：同目錄同名優先，其次 docs/reports/html/。"""
    cands = [md_path.with_suffix(".html")]
    parts = md_path.parts
    if "reports" in parts:
        root = Path(*parts[: parts.index("reports") + 1])
        cands.append(root / "html" / md_path.with_suffix(".html").name)
    return [c for c in cands if c.exists()]


def check(md_path: Path, quiet: bool = False) -> str:
    """回傳狀態：OK / STALE / NO-HTML / NO-STAMP / BAD-REF"""
    htmls = html_candidates(md_path)
    if not htmls:
        status = "NO-HTML"
        if not quiet:
            print(f"ℹ NO-HTML  {md_path}（尚未渲染 View 軌，若無人類受眾屬正常）")
        return status

    html_path = htmls[0]
    m = STAMP_RE.search(html_path.read_text(encoding="utf-8"))
    if not m:
        if not quiet:
            print(f"❌ NO-STAMP {html_path}（HTML 無戳記，無法驗證來源，請重渲染並 stamp）")
        return "NO-STAMP"

    ref_path, ref_hash = m.group(1), m.group(2)
    if Path(ref_path).name != md_path.name:
        if not quiet:
            print(f"❌ BAD-REF  {html_path} 戳記指向 {ref_path}，非 {md_path.name}")
        return "BAD-REF"

    if ref_hash != md_hash(md_path):
        if not quiet:
            print(f"❌ STALE    {html_path}（MD 已更動，HTML 未重渲染）")
        return "STALE"

    if not quiet:
        print(f"✅ OK       {md_path.name} ↔ {html_path.name}")
    return "OK"


def stamp(md_path: Path, html_path: Path) -> None:
    h = md_hash(md_path)
    new_stamp = f"<!-- content-src: {md_path.as_posix()} sha256:{h} -->"
    html = html_path.read_text(encoding="utf-8")
    if STAMP_RE.search(html):
        html = STAMP_RE.sub(new_stamp, html, count=1)
    elif "</body>" in html:
        html = html.replace("</body>", f"{new_stamp}\n</body>", 1)
    else:
        html += f"\n{new_stamp}\n"
    html_path.write_text(html, encoding="utf-8")
    print(f"✅ 已寫入戳記：{html_path}（sha256:{h}）")


def scan(root: Path) -> int:
    stats: dict[str, int] = {}
    bad = 0
    for md in sorted(root.rglob("*.md")):
        if md.name.startswith("_") or "/html/" in md.as_posix():
            continue
        status = check(md)
        stats[status] = stats.get(status, 0) + 1
        if status in ("STALE", "NO-STAMP", "BAD-REF"):
            bad += 1
    print(f"\n總計：{stats}")
    return 1 if bad else 0


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    cmd = sys.argv[1]
    if cmd == "check":
        status = check(Path(sys.argv[2]))
        return 1 if status in ("STALE", "NO-STAMP", "BAD-REF") else 0
    if cmd == "stamp":
        stamp(Path(sys.argv[2]), Path(sys.argv[3]))
        return 0
    if cmd == "scan":
        return scan(Path(sys.argv[2]))
    print(f"未知指令：{cmd}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
