"""book_lint.py — ark-book Content 軌契約與教學結構驗證器。

Deterministic 守門：寫完章節 / 整本書後必須跑過此 lint 才能 build 與登錄。
驗證 book.yaml 契約、章節 frontmatter、目錄一致性、七段結構、教學元件、
chunk 自足禁詞、placeholder 殘留、sources 與內部連結存在。

用法：
    python book_lint.py books/first-personal-agent/            # 整本
    python book_lint.py books/first-personal-agent/03-xxx.md   # 單章（仍會讀同目錄 book.yaml）
    python book_lint.py books/xxx/ --wiki-schema knowledge/proj/schema.md   # 加驗 tags 白名單
    python book_lint.py books/xxx/ --json                      # 機器可讀輸出（book_register 消費）

Exit code：0 全過 / 1 有 FAIL（WARN 不影響 exit code）
只依賴標準庫 + PyYAML（缺 PyYAML 時退回極簡 frontmatter 解析）。
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ── 契約定義（與 references/book-contract.md 同步）─────────────────────────

BOOK_REQUIRED = ["title", "slug", "author", "version", "status", "language",
                 "level", "audience", "outcomes", "prerequisites", "scope_out",
                 "tags", "chapters", "shelf", "created", "updated"]
CH_REQUIRED = ["book", "chapter", "slug", "title", "type", "level", "est_minutes",
               "punchline", "objectives", "tags", "sources", "trust", "confidence", "status"]

STATUS_ENUM = {"draft", "review", "published"}
LEVEL_ENUM = {"beginner", "intermediate", "advanced"}
TYPE_ENUM = {"preface", "chapter", "appendix", "exercise"}
TRUST_ENUM = {"deterministic", "llm-distilled"}
CONF_ENUM = {"high", "medium", "low"}
SPINE_ENUM = {"green", "wine", "navy", "brown", "brass"}

SECTIONS = ["這章要解決的問題", "路線圖", "內文", "常見誤解", "動手做", "重點回顧", "下一章"]
PREFACE_SECTIONS = ["為什麼有這本書", "這本書給誰", "讀完你會", "全書路線圖"]
OPTIONAL_FOR_APPENDIX = {"動手做", "下一章"}

FORBIDDEN_PHRASES = ["如上所述", "如前所述", "上文提到", "詳見上文", "（見上）", "前述問題"]
WARN_PHRASES = ["前者", "後者", "該問題", "此問題"]
PLACEHOLDER_RE = re.compile(r"\bTODO\b|\bTBD\b|lorem ipsum|\bxxx\b|<[^>\n]{1,40}>", re.I)
# 允許的 <> 用法：html 標籤與泛型；這裡只抓像 <填空提示> 的中文/空格內容
PLACEHOLDER_ANGLE_RE = re.compile(r"<[^>/\n]*[\u4e00-\u9fff][^>\n]*>")
FILENAME_RE = re.compile(r"^(\d{2})-([a-z0-9][a-z0-9-]*)\.md$")
ALERT_RE = re.compile(r"^>\s*\[!(ASK|TIP|MYTH|TRY|NOTE|WARNING)\]", re.M)
PUNCH_MAX = 40


@dataclass
class Result:
    path: str
    fails: list[str] = field(default_factory=list)
    warns: list[str] = field(default_factory=list)

    def fail(self, msg: str) -> None:
        self.fails.append(msg)

    def warn(self, msg: str) -> None:
        self.warns.append(msg)


# ── 解析工具 ───────────────────────────────────────────────────────────────

def load_yaml_text(text: str) -> dict:
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(text)
        return data if isinstance(data, dict) else {}
    except ImportError:
        return _mini_yaml(text)


def _mini_yaml(text: str) -> dict:
    """極簡 fallback：key: value / key: [a, b] / key:\n  - item。"""
    out: dict = {}
    key = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.strip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if m and not line.startswith(" "):
            key, val = m.group(1), m.group(2).strip()
            if val == "":
                out[key] = []
            elif val.startswith("[") and val.endswith("]"):
                out[key] = [v.strip().strip("'\"") for v in val[1:-1].split(",") if v.strip()]
            else:
                v = val.strip().strip("'\"")
                out[key] = int(v) if re.fullmatch(r"-?\d+", v) else v
        elif key and line.strip().startswith("- "):
            if not isinstance(out.get(key), list):
                out[key] = []
            out[key].append(line.strip()[2:].strip().strip("'\""))
    return out


def split_frontmatter(text: str) -> tuple[dict, str]:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.DOTALL)
    if not m:
        return {}, text
    return load_yaml_text(m.group(1)), text[m.end():]


def h2_sections(body: str) -> list[tuple[str, str]]:
    """回傳 [(標題, 內容)]，標題去掉 '## ' 與可能的副標（以 '：' 或 ' — ' 分隔前半）。"""
    parts = re.split(r"^##\s+(.+?)\s*$", body, flags=re.M)
    out = []
    for i in range(1, len(parts), 2):
        title = parts[i].strip()
        content = parts[i + 1] if i + 1 < len(parts) else ""
        out.append((title, content))
    return out


def norm_title(t: str) -> str:
    t = re.sub(r"[：:—\-–].*$", "", t).strip()
    return t


def count_list_items(content: str) -> int:
    return len(re.findall(r"^\s*(?:[-*]|\d+\.)\s+\S", content, re.M))


# ── book.yaml 檢查 ─────────────────────────────────────────────────────────

def lint_book_yaml(book_dir: Path, wiki_tags: set[str] | None) -> tuple[Result, dict]:
    path = book_dir / "book.yaml"
    r = Result(str(path))
    if not path.exists():
        r.fail("缺 book.yaml")
        return r, {}
    meta = load_yaml_text(path.read_text(encoding="utf-8"))
    for k in BOOK_REQUIRED:
        if k not in meta or meta[k] in (None, ""):
            r.fail(f"book.yaml 缺必要欄位 `{k}`")
    if not r.fails:
        if meta["slug"] != book_dir.name:
            r.fail(f"slug `{meta['slug']}` 與目錄名 `{book_dir.name}` 不一致")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", str(meta["slug"])):
            r.fail("slug 必須是 kebab-case")
        if meta["status"] not in STATUS_ENUM:
            r.fail(f"status `{meta['status']}` 不在 {sorted(STATUS_ENUM)}")
        if meta["level"] not in LEVEL_ENUM:
            r.fail(f"level `{meta['level']}` 不在 {sorted(LEVEL_ENUM)}")
        if not isinstance(meta["version"], int) or meta["version"] < 1:
            r.fail("version 必須是 ≥1 的整數")
        outs = meta["outcomes"] if isinstance(meta["outcomes"], list) else []
        if not 2 <= len(outs) <= 5:
            r.fail(f"outcomes 需 2–5 條（現 {len(outs)}）；超過 5 條請拆兩本書")
        for o in outs:
            if re.match(r"^(理解|知道|了解|熟悉|認識)", str(o)):
                r.warn(f"outcome「{o}」以不可驗證的動詞開頭，改成「用 X 產出 Y」類")
        if not isinstance(meta["chapters"], list) or not meta["chapters"]:
            r.fail("chapters 目錄為空")
        if not isinstance(meta.get("scope_out"), list):
            r.fail("scope_out 必須是清單（可為空 []）")
        cover = meta.get("cover") or {}
        if isinstance(cover, dict) and cover.get("spine_color") and cover["spine_color"] not in SPINE_ENUM:
            r.fail(f"cover.spine_color `{cover['spine_color']}` 不在 {sorted(SPINE_ENUM)}")
        if meta.get("style"):
            mf = Path(__file__).resolve().parent.parent / "assets" / "styles" / "_manifest.json"
            if mf.exists():
                names = [s["name"] for s in json.loads(mf.read_text(encoding="utf-8")).get("styles", [])]
                if meta["style"] not in names:
                    r.fail(f"style `{meta['style']}` 不在 assets/styles/_manifest.json：{names}")
        if wiki_tags is not None:
            bad = [t for t in meta["tags"] if t not in wiki_tags]
            if bad:
                r.fail(f"tags 不在 wiki 受控詞彙表：{bad}")
    return r, meta


# ── 章節檔檢查 ─────────────────────────────────────────────────────────────

def lint_chapter(path: Path, book_meta: dict, book_dir: Path, wiki_tags: set[str] | None,
                 calibration: list[str]) -> tuple[Result, dict]:
    r = Result(str(path))
    text = path.read_text(encoding="utf-8")
    fm, body = split_frontmatter(text)
    if not fm:
        r.fail("缺 frontmatter")
        return r, {}

    m = FILENAME_RE.match(path.name)
    if not m:
        r.fail("檔名需為 `NN-kebab-slug.md`")
    for k in CH_REQUIRED:
        if k not in fm or fm[k] in (None, ""):
            r.fail(f"frontmatter 缺必要欄位 `{k}`")
    if r.fails:
        return r, fm

    # 一致性
    if m:
        if int(m.group(1)) != int(fm["chapter"]):
            r.fail(f"檔名章號 {m.group(1)} ≠ frontmatter chapter {fm['chapter']}")
        if m.group(2) != fm["slug"]:
            r.fail(f"檔名 slug `{m.group(2)}` ≠ frontmatter slug `{fm['slug']}`")
    if book_meta and fm["book"] != book_meta.get("slug"):
        r.fail(f"book `{fm['book']}` ≠ book.yaml slug `{book_meta.get('slug')}`")
    for k, enum in (("type", TYPE_ENUM), ("level", LEVEL_ENUM), ("trust", TRUST_ENUM),
                    ("confidence", CONF_ENUM), ("status", STATUS_ENUM)):
        if fm[k] not in enum:
            r.fail(f"{k} `{fm[k]}` 不在 {sorted(enum)}")
    if not isinstance(fm["est_minutes"], int) or fm["est_minutes"] <= 0:
        r.fail("est_minutes 必須是正整數")
    elif fm["type"] == "chapter" and not 5 <= fm["est_minutes"] <= 40:
        r.warn(f"est_minutes={fm['est_minutes']}：一章建議 10–25 分鐘，超過 40 請拆章")
    punch = str(fm["punchline"]).strip()
    if len(punch) > PUNCH_MAX:
        r.fail(f"punchline 超過 {PUNCH_MAX} 字（{len(punch)}）：一句話寫不出來代表章還沒想清楚")
    objs = fm["objectives"] if isinstance(fm["objectives"], list) else []
    if not 1 <= len(objs) <= 3:
        r.fail(f"objectives 需 1–3 條（現 {len(objs)}）")
    if wiki_tags is not None:
        bad = [t for t in fm["tags"] if t not in wiki_tags]
        if bad:
            r.fail(f"tags 不在 wiki 受控詞彙表：{bad}")

    # sources 路徑存在（相對 book_dir 或 repo 根；含 # 錨點者取前半；外部 repo 路徑只 WARN）
    for s in fm["sources"] or []:
        p = str(s).split("#")[0]
        if not p:
            continue
        if (book_dir / p).exists() or (book_dir.parent.parent / p).exists() or Path(p).exists():
            continue
        if p.startswith("sources/"):
            r.fail(f"sources 路徑不存在：{p}")
        else:
            r.warn(f"sources 路徑在本 repo 找不到（外部引用？）：{p}")

    # ── 內文結構 ──
    secs = h2_sections(body)
    titles = [norm_title(t) for t, _ in secs]
    sec_map = {norm_title(t): c for t, c in secs}

    if fm["type"] == "preface":
        for s in PREFACE_SECTIONS:
            if s not in titles:
                r.fail(f"序缺章節 `## {s}`")
    else:
        required = [s for s in SECTIONS if not (fm["type"] in ("appendix", "exercise") and s in OPTIONAL_FOR_APPENDIX)]
        missing = [s for s in required if s not in titles]
        for s in missing:
            r.fail(f"缺章節 `## {s}`")
        present = [s for s in SECTIONS if s in titles]
        order = [titles.index(s) for s in present]
        if order != sorted(order):
            r.fail(f"七段順序錯誤：現為 {present}")

        prob = sec_map.get("這章要解決的問題", "")
        if prob and not re.search(r"[？?]|怎麼辦", prob):
            r.fail("「這章要解決的問題」需以問題收尾（含問號或「怎麼辦」）——先讓問題痛再給方法")
        road = sec_map.get("路線圖", "")
        if road and not 2 <= count_list_items(road) <= 5:
            r.fail(f"路線圖需 2–5 個項目（現 {count_list_items(road)}）")
        content = sec_map.get("內文", "")
        if content:
            if not re.search(r"^>\s*\[!ASK\]", content, re.M):
                r.fail("內文缺 `> [!ASK]`（你可能會想說…）——至少主動說出讀者一個疑問")
            for term in fm.get("key_terms") or []:
                if str(term) not in content:
                    r.warn(f"key_terms `{term}` 未在內文出現：命名儀式沒做？")
        myths = sec_map.get("常見誤解", "")
        if myths and not re.search(r"^>\s*\[!MYTH\]", myths, re.M):
            r.fail("常見誤解缺 `> [!MYTH]`（大家通常會以為…但其實…）")
        prac = sec_map.get("動手做", "")
        if prac and not (re.search(r"```", prac) or re.search(r"^\s*\d+\.\s+\S", prac, re.M)):
            r.fail("動手做需含 fenced code 或編號步驟——讀者要能立刻執行")
        if prac and not re.search(r"你應該看到|預期輸出|成功時|會看到", prac):
            r.warn("動手做沒有寫「你應該看到什麼」")
        recap = sec_map.get("重點回顧", "")
        if recap:
            n = count_list_items(recap)
            if not 1 <= n <= 3:
                r.fail(f"重點回顧需 1–3 條（現 {n}）——超過三句就不是回顧")
            first = re.search(r"^\s*(?:[-*]|\d+\.)\s+(.+)$", recap, re.M)
            if first and not _shares_keywords(first.group(1), punch):
                r.warn("重點回顧第一句與 punchline 看起來不是同一句")
        nxt = sec_map.get("下一章", "")
        if nxt and len(re.findall(r"[。！？!?]", nxt)) > 2:
            r.warn("「下一章」超過兩句，橋接一句就好")

    # ── AI 可讀性 ──
    for ph in FORBIDDEN_PHRASES:
        if ph in body:
            r.fail(f"chunk 自足禁詞「{ph}」：章節會被切塊檢索，寫全名或用章節 slug 指涉")
    for ph in WARN_PHRASES:
        if ph in body:
            r.warn(f"跨段指涉風險詞「{ph}」，確認是否同句即時對比")
    prose = re.sub(r"```.*?```", "", body, flags=re.S)          # 去 fenced code
    prose = re.sub(r"`[^`\n]*`", "", prose)                       # 去 inline code
    for mm in PLACEHOLDER_ANGLE_RE.finditer(prose):
        r.fail(f"placeholder 殘留：{mm.group(0)!r}（模板填空未填）")
    for mm in re.finditer(r"^\s*(?:[-*]\s*)?(TODO|TBD)\b.*$|\b(TODO|TBD):", prose, re.M | re.I):
        r.fail(f"placeholder 殘留：{mm.group(0).strip()[:40]!r}")
    if re.search(r"lorem ipsum", prose, re.I):
        r.fail("placeholder 殘留：lorem ipsum")
    for mm in re.finditer(r"\b(TODO|TBD|xxx)\b", prose, re.I):
        r.warn(f"內文出現 `{mm.group(0)}`：若是在講 lint 規則可忽略，若是待填請補上")
    if len(body.strip()) < 600 and fm["type"] == "chapter":
        r.warn("章節內文少於 600 字，確認不是大綱殘留")

    # 內部連結 [[slug]] / (NN-slug.md)
    for link in re.findall(r"\]\(([^)]+\.md)(?:#[^)]*)?\)", body):
        if link.startswith("http"):
            continue
        if not (path.parent / link).exists():
            r.fail(f"內部連結不存在：{link}")

    # calibration 引用
    for line in calibration:
        key = re.split(r"[；。，、（(：:]", line, 1)[0].strip()
        key = key if len(key) >= 6 else line[:12]
        if key and key in body:
            calibration_hit.add(line)

    return r, fm


calibration_hit: set[str] = set()


def _shares_keywords(a: str, b: str) -> bool:
    ka = set(re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z_]{3,}", a))
    kb = set(re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z_]{3,}", b))
    return bool(ka & kb) or b.strip("。 ") in a


# ── 整本書檢查 ─────────────────────────────────────────────────────────────

def load_wiki_tags(schema: Path | None) -> set[str] | None:
    if not schema:
        return None
    if not schema.exists():
        print(f"WARN  wiki schema 不存在：{schema}（略過 tags 白名單驗證）")
        return None
    text = schema.read_text(encoding="utf-8")
    tags = set(re.findall(r"`([a-z0-9][a-z0-9-]*)`", text))
    return tags or None


def load_calibration(book_dir: Path) -> list[str]:
    p = book_dir / "_calibration.md"
    if not p.exists():
        return []
    return [ln.strip()[2:].strip() for ln in p.read_text(encoding="utf-8").splitlines()
            if ln.strip().startswith("- ")]


def lint_book(book_dir: Path, wiki_schema: Path | None, only: Path | None = None) -> list[Result]:
    results: list[Result] = []
    wiki_tags = load_wiki_tags(wiki_schema)
    br, meta = lint_book_yaml(book_dir, wiki_tags)
    results.append(br)
    calibration = load_calibration(book_dir)

    files = sorted(p for p in book_dir.glob("*.md") if FILENAME_RE.match(p.name))
    if only:
        files = [only]
    ch_metas: list[dict] = []
    for f in files:
        cr, fm = lint_chapter(f, meta, book_dir, wiki_tags, calibration)
        results.append(cr)
        if fm:
            ch_metas.append(fm)

    if meta and not only:
        toc = [str(c) for c in meta.get("chapters", [])]
        names = [f.stem for f in files]
        for c in toc:
            if c not in names:
                br.fail(f"book.yaml chapters 有 `{c}` 但檔案不存在")
        for n in names:
            if n not in toc:
                br.fail(f"檔案 `{n}.md` 未列入 book.yaml chapters")
        nums = sorted(int(FILENAME_RE.match(f.name).group(1)) for f in files)
        main = [n for n in nums if n < 90]
        if main and main != list(range(main[0], main[0] + len(main))):
            br.fail(f"章號不連續：{main}")
        if meta.get("status") == "published":
            for fm in ch_metas:
                if fm.get("status") != "published":
                    br.fail(f"書為 published 但章節 `{fm.get('slug')}` status={fm.get('status')}")
        # outcomes 覆蓋
        all_obj = " ".join(str(o) for fm in ch_metas for o in (fm.get("objectives") or []))
        for o in meta.get("outcomes", []):
            if not _shares_keywords(all_obj, str(o)):
                br.warn(f"outcome「{o}」沒有任何一章的 objectives 覆蓋")
        for line in calibration:
            if line not in calibration_hit:
                br.warn(f"_calibration.md 條目未在任何章節反映：「{line[:30]}…」")
    return results


# ── 輸出 ───────────────────────────────────────────────────────────────────

def main(argv: list[str]) -> int:
    if "-h" in argv or "--help" in argv:
        print(__doc__)
        return 0
    args = [a for a in argv if not a.startswith("--")]
    wiki_schema = None
    if "--wiki-schema" in argv:
        wiki_schema = Path(argv[argv.index("--wiki-schema") + 1])
        args = [a for a in args if str(wiki_schema) != a]
    as_json = "--json" in argv
    if not args:
        print(__doc__)
        return 2
    target = Path(args[0])
    if target.is_dir():
        book_dir, only = target, None
    else:
        book_dir, only = target.parent, target
    results = lint_book(book_dir, wiki_schema, only)

    total_fail = sum(len(r.fails) for r in results)
    total_warn = sum(len(r.warns) for r in results)
    if as_json:
        print(json.dumps({
            "book_dir": str(book_dir), "status": "PASS" if total_fail == 0 else "FAIL",
            "fails": total_fail, "warns": total_warn,
            "files": [{"path": r.path, "fails": r.fails, "warns": r.warns} for r in results],
        }, ensure_ascii=False, indent=2))
    else:
        for r in results:
            tag = "FAIL" if r.fails else ("WARN" if r.warns else "PASS")
            print(f"{tag:4}  {r.path}")
            for f in r.fails:
                print(f"      ✗ {f}")
            for w in r.warns:
                print(f"      ! {w}")
        print(f"\n{'PASS' if total_fail == 0 else 'FAIL'}  {len(results)} files · {total_fail} FAIL · {total_warn} WARN")
    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
