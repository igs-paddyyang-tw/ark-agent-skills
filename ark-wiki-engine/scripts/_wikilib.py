"""_wikilib.py — ark-wiki-engine v3 共用模組（單一事實來源）

所有腳本以下列方式引用：

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from _wikilib import parse_frontmatter, emit_json, emit_error, ErrorCode

## 為什麼要有這支

v2 時 `parse_frontmatter` 在 `wiki_query.py` / `wiki_index.py` / `wiki_lint.py`
各有一份（另有一份在 `build_wiki.py` 的模板字串裡），各版對 list 值的解析
行為略有差異 —— 同一頁在查詢與 lint 眼中的 tags 可能不同。

**判準：同一事實只能有一個出口。** 四層搜尋的 tokenizer 更是如此 ——
build 與 query 用不同分詞就等於索引白建，所以 mode 會寫進 manifest 供比對。
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterator

INDEX_VERSION = "3.0"
INDEX_DIRNAME = ".index"


# ── 錯誤碼 ───────────────────────────────────────────────────

class ErrorCode:
    """統一錯誤碼。新增時同步更新 references/query-contract.schema.json。"""

    WIKI_DIR_NOT_FOUND = "WIKI_DIR_NOT_FOUND"
    INDEX_MISSING = "INDEX_MISSING"
    INDEX_STALE = "INDEX_STALE"
    TOKENIZER_MISMATCH = "TOKENIZER_MISMATCH"
    GUARD_BLOCKED = "GUARD_BLOCKED"
    TAG_NOT_IN_WHITELIST = "TAG_NOT_IN_WHITELIST"
    SCHEMA_NOT_FOUND = "SCHEMA_NOT_FOUND"
    BUILD_LOCKED = "BUILD_LOCKED"
    BAD_ARGUMENTS = "BAD_ARGUMENTS"

    ALL = (
        WIKI_DIR_NOT_FOUND, INDEX_MISSING, INDEX_STALE, TOKENIZER_MISMATCH,
        GUARD_BLOCKED, TAG_NOT_IN_WHITELIST, SCHEMA_NOT_FOUND, BUILD_LOCKED,
        BAD_ARGUMENTS,
    )


# ── stdout 契約 ──────────────────────────────────────────────

def emit_json(payload: dict[str, Any], exit_code: int = 0) -> None:
    """把 payload 印到 stdout 並結束。agent 端固定解析這個形狀。"""
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    sys.stdout.flush()
    sys.exit(exit_code)


def emit_error(code: str, msg: str, exit_code: int = 2, **extra: Any) -> None:
    """錯誤一律走這裡 —— 不 raise 到 traceback。

    v2 的 `wiki_query.py` 在 `--wiki_dir` 不存在時用了 `sys.stderr` 卻沒
    `import sys`（F-1）→ 使用者看到的是 NameError 而不是「目錄不存在」。
    """
    emit_json({"ok": False, "error": {"code": code, "msg": msg, **extra}}, exit_code)


# ── frontmatter ──────────────────────────────────────────────

_FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


def _coerce(value: str) -> Any:
    """把 frontmatter 的字串值轉成 list / bool / str。"""
    v = value.strip()
    if v.startswith("[") and v.endswith("]"):
        return [x.strip().strip('"').strip("'") for x in v[1:-1].split(",") if x.strip()]
    v = v.strip('"').strip("'")
    low = v.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    return v


def parse_frontmatter(content: str) -> dict[str, Any]:
    """解析 YAML frontmatter（不引入 PyYAML —— 零依賴是設計約束）。

    支援兩種 list 寫法：inline `[a, b]` 與 block（`-` 開頭的續行）。
    v2 三份實作只支援 inline，block 寫法會被讀成空字串。
    """
    m = _FM_RE.match(content)
    if not m:
        return {}
    result: dict[str, Any] = {}
    pending_key: str | None = None
    for raw in m.group(1).splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        stripped = line.strip()
        if stripped.startswith("- ") and pending_key:
            result.setdefault(pending_key, [])
            if isinstance(result[pending_key], list):
                result[pending_key].append(stripped[2:].strip().strip('"').strip("'"))
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        # 巢狀鍵（縮排）不進頂層，避免 metadata 子鍵污染
        if key != key.lstrip():
            continue
        key = key.strip()
        if not value.strip():
            pending_key = key
            result[key] = []
            continue
        pending_key = None
        result[key] = _coerce(value)
    # 空 list（宣告了 key 但沒有項目）視為未設定，避免下游把 [] 當成「有這個欄位」
    return {k: v for k, v in result.items() if v != []}


def strip_frontmatter(content: str) -> str:
    """取 frontmatter 之後的本文。"""
    m = _FM_RE.match(content)
    return content[m.end():] if m else content


# ── 分詞 ─────────────────────────────────────────────────────

STOPWORDS = {
    "the", "a", "an", "of", "and", "or", "to", "in", "is", "are", "was", "were",
    "for", "on", "at", "by", "with", "as", "it", "this", "that", "be", "from",
    "的", "了", "是", "在", "和", "與", "或", "有", "為", "會", "要", "把", "被",
}

_WORD_RE = re.compile(r"[a-zA-Z0-9_\-.]+")
_CJK_RE = re.compile(r"[一-鿿]+")


def jieba_available() -> bool:
    """jieba 是否可用。獨立成函式方便測試 monkeypatch（見 test_degrade.py）。"""
    try:
        import jieba  # noqa: F401
        return True
    except Exception:
        return False


def resolve_tokenizer(mode: str = "auto") -> str:
    """把 auto 解析成實際 mode。回傳 'jieba' 或 'bigram'。"""
    if mode in ("jieba", "bigram"):
        return mode
    return "jieba" if jieba_available() else "bigram"


def tokenize(text: str, mode: str = "auto", userdict: Path | None = None) -> list[str]:
    """分詞。

    - `jieba`：`cut_for_search` + 選配 userdict（aliases/title 進詞典，
      讓「留存口徑」這類複合詞不被切散）
    - `bigram`：ASCII 詞 + CJK **bigram**（v2 是 CJK 逐字，
      單字 token 的 df 幾乎等於文件數 → IDF 趨近 0，等於沒有區分力）

    **build 與 query 必須用同一 mode**，否則索引查不到東西。
    """
    resolved = resolve_tokenizer(mode)
    lowered = text.lower()
    if resolved == "jieba":
        try:
            import jieba
            if userdict and Path(userdict).exists():
                jieba.load_userdict(str(userdict))
            toks = [t.strip() for t in jieba.cut_for_search(lowered)]
            return [t for t in toks if t and not t.isspace() and t not in STOPWORDS]
        except Exception:
            resolved = "bigram"  # jieba 中途壞掉也要能回答
    tokens: list[str] = []
    for w in _WORD_RE.findall(lowered):
        if w not in STOPWORDS:
            tokens.append(w)
    for run in _CJK_RE.findall(lowered):
        if len(run) == 1:
            tokens.append(run)
            continue
        for i in range(len(run) - 1):
            tokens.append(run[i:i + 2])
    return [t for t in tokens if t not in STOPWORDS]


# ── 頁面掃描與雜湊 ───────────────────────────────────────────

def iter_pages(wiki_dir: Path) -> Iterator[Path]:
    """依相對路徑排序列出 wiki 頁面（排序讓 content_hash 穩定）。"""
    yield from sorted(wiki_dir.rglob("*.md"), key=lambda p: str(p.relative_to(wiki_dir)))


def content_hash(wiki_dir: Path) -> str:
    """以 (relpath, size, mtime_ns) 算 sha256，供 freshness 判斷。

    不讀檔內容 —— 300 頁的 wiki 每次查詢都全量讀檔會拖垮 P95。
    """
    h = hashlib.sha256()
    for p in iter_pages(wiki_dir):
        st = p.stat()
        h.update(str(p.relative_to(wiki_dir)).encode("utf-8"))
        h.update(str(st.st_size).encode("ascii"))
        h.update(str(st.st_mtime_ns).encode("ascii"))
    return h.hexdigest()


def page_id(wiki_dir: Path, path: Path) -> str:
    """頁面識別：相對 wiki_dir 的路徑去掉 .md（如 `kpi/retention-definition`）。"""
    return str(path.relative_to(wiki_dir).with_suffix("")).replace("\\", "/")


def index_dir(wiki_dir: Path) -> Path:
    return wiki_dir / INDEX_DIRNAME


def load_manifest(wiki_dir: Path) -> dict[str, Any] | None:
    mf = index_dir(wiki_dir) / "manifest.json"
    if not mf.exists():
        return None
    try:
        return json.loads(mf.read_text(encoding="utf-8"))
    except Exception:
        return None


def extract_wikilinks(content: str) -> list[str]:
    """提取 [[wikilink]]（支援 [[target|顯示文字]]）。"""
    return [m.split("|")[0].strip() for m in re.findall(r"\[\[([^\]]+)\]\]", content)]
