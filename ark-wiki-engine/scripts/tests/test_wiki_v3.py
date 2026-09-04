"""ark-wiki-engine v3 — W0 驗收測試（deterministic）

對應 plan `docs/plans/2026-09-04-ark-wiki-engine-v3-executor-plan.md` 的
AC-001 ~ AC-012。每個測試的 docstring 標 `AC: AC-XXX` 建立追蹤鏈
（ark-code-spec-validator 依此判定 AC 是否有測試覆蓋）。

執行：
    python3 -m pytest scripts/tests -q          # 系統 python（bigram 路徑）
    .venv/bin/python -m pytest scripts/tests -q # venv（jieba 路徑）
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
FIXTURE = SCRIPTS / "tests" / "fixtures" / "wiki"
sys.path.insert(0, str(SCRIPTS))

from _wikilib import ErrorCode, content_hash, parse_frontmatter, tokenize  # noqa: E402


def run(script: str, *args: str) -> tuple[int, dict | str]:
    """跑腳本並解析 stdout JSON。回 (exit_code, payload)。"""
    proc = subprocess.run([sys.executable, str(SCRIPTS / script), *args],
                          capture_output=True, text=True)
    try:
        return proc.returncode, json.loads(proc.stdout)
    except json.JSONDecodeError:
        return proc.returncode, proc.stdout


@pytest.fixture(scope="module", autouse=True)
def built_index():
    """每次測試前重建索引（tokenizer 依當前解譯器能力）。"""
    run("wiki_index.py", "build", "--wiki_dir", str(FIXTURE))
    yield


def q(*args: str) -> dict:
    code, payload = run("wiki_query.py", "--wiki_dir", str(FIXTURE), *args)
    assert isinstance(payload, dict), payload
    return payload


# ── AC-001 _wikilib ──────────────────────────────────────────

def test_wikilib_frontmatter_and_hash(tmp_path):
    """AC: AC-001 — frontmatter 支援 inline 與 block list；content_hash 穩定且對變更敏感"""
    fm = parse_frontmatter(
        '---\ntitle: "T"\ntags: [a, b]\naliases:\n  - x\n  - y\napproved: false\n---\nbody')
    assert fm["tags"] == ["a", "b"] and fm["aliases"] == ["x", "y"]
    assert fm["approved"] is False          # 不可被讀成字串 "false"

    h1 = content_hash(FIXTURE)
    assert h1 == content_hash(FIXTURE)      # 同一狀態兩次相同
    p = FIXTURE / "misc" / "orphan.md"
    original = p.read_text(encoding="utf-8")
    try:
        p.write_text(original + "\n變更\n", encoding="utf-8")
        assert content_hash(FIXTURE) != h1  # 內容改變 → hash 改變
    finally:
        p.write_text(original, encoding="utf-8")


def test_error_codes_declared():
    """AC: AC-001 — 七個設計錯誤碼皆已宣告"""
    for code in ("WIKI_DIR_NOT_FOUND", "INDEX_MISSING", "INDEX_STALE", "TOKENIZER_MISMATCH",
                 "GUARD_BLOCKED", "TAG_NOT_IN_WHITELIST", "SCHEMA_NOT_FOUND"):
        assert getattr(ErrorCode, code) in ErrorCode.ALL


# ── AC-002 F-1 迴歸 ─────────────────────────────────────────

def test_missing_wiki_dir_is_friendly_error():
    """AC: AC-002 — 目錄不存在回 WIKI_DIR_NOT_FOUND + exit 2，不是 NameError（F-1 迴歸）"""
    code, payload = run("wiki_query.py", "--wiki_dir", "/nonexistent-wiki", "--query", "x")
    assert code == 2
    assert payload["ok"] is False
    assert payload["error"]["code"] == ErrorCode.WIKI_DIR_NOT_FOUND
    assert "NameError" not in json.dumps(payload)


def test_bad_arguments_mutually_exclusive():
    """AC: AC-002 — --wiki_dir 與 --knowledge_root 二擇一；缺 --domains 亦擋（D-4）"""
    code, payload = run("wiki_query.py", "--wiki_dir", str(FIXTURE),
                        "--knowledge_root", "x", "--query", "a")
    assert code == 2 and payload["error"]["code"] == ErrorCode.BAD_ARGUMENTS
    code, payload = run("wiki_query.py", "--knowledge_root",
                        str(FIXTURE.parent.parent), "--query", "a")
    assert code == 2 and payload["error"]["code"] == ErrorCode.BAD_ARGUMENTS


# ── AC-003 單一事實來源 ─────────────────────────────────────

def test_single_frontmatter_implementation():
    """AC: AC-003 — 全 scripts 只有一個 parse_frontmatter 定義（用 ast，不用字串比對）"""
    import ast
    defs = [(f.name, node.name)
            for f in SCRIPTS.glob("*.py")
            for node in ast.walk(ast.parse(f.read_text(encoding="utf-8")))
            if isinstance(node, ast.FunctionDef)
            and node.name in ("parse_frontmatter", "extract_wikilinks", "tokenize")]
    for name in ("parse_frontmatter", "extract_wikilinks", "tokenize"):
        owners = [f for f, d in defs if d == name]
        assert owners == ["_wikilib.py"], f"{name} 定義於 {owners}，應只在 _wikilib.py"


# ── AC-004 / AC-005 索引 ────────────────────────────────────

def test_build_manifest_fields():
    """AC: AC-004 — manifest 含 index_version/tokenizer/bm25_backend/content_hash"""
    code, payload = run("wiki_index.py", "build", "--wiki_dir", str(FIXTURE))
    assert code == 0 and payload["ok"] is True
    mf = payload["manifest"]
    for key in ("index_version", "built_at", "page_count", "tokenizer",
                "bm25_backend", "content_hash"):
        assert key in mf, key
    assert mf["page_count"] == 12
    assert mf["tokenizer"] in ("jieba", "bigram")
    assert (FIXTURE / ".index" / "bm25" / "postings.json").exists()


def test_concurrent_build_one_locked():
    """AC: AC-005 — 兩個 build 併發 → 一個 BUILD_LOCKED，且 .index/ 完整"""
    procs = [subprocess.Popen([sys.executable, str(SCRIPTS / "wiki_index.py"), "build",
                               "--wiki_dir", str(FIXTURE)],
                              stdout=subprocess.PIPE, text=True) for _ in range(2)]
    outs = [json.loads(p.communicate()[0]) for p in procs]
    codes = [o.get("error", {}).get("code") for o in outs if not o["ok"]]
    assert ErrorCode.BUILD_LOCKED in codes, outs
    assert any(o["ok"] for o in outs)
    for rel in ("manifest.json", "metadata.json", "graph.json", "bm25/postings.json"):
        assert (FIXTURE / ".index" / rel).exists(), rel


def test_freshness_stale_but_still_answers():
    """AC: AC-004 — touch 一頁 → index_fresh:false + INDEX_STALE warning，但仍回結果（D-5）"""
    run("wiki_index.py", "build", "--wiki_dir", str(FIXTURE))
    p = FIXTURE / "kpi" / "dau-definition.md"
    p.touch()
    code, payload = run("wiki_index.py", "freshness", "--wiki_dir", str(FIXTURE))
    assert code == 1 and payload["fresh"] is False
    assert payload["reason"] == ErrorCode.INDEX_STALE

    out = q("--query", "DAU")
    assert out["ok"] is True
    assert out["meta"]["index_fresh"] is False
    assert ErrorCode.INDEX_STALE in out["meta"]["warnings"]
    assert out["results"], "索引過期時仍必須回答（不可掛零）"


def test_legacy_md_subcommand_compat():
    """AC: AC-004 — 無子命令 = md（v2 相容），--dry_run 不寫檔"""
    code, payload = run("wiki_index.py", "--wiki_dir", str(FIXTURE), "--dry_run")
    assert code == 0
    assert "知識庫索引" in (payload if isinstance(payload, str) else json.dumps(payload))


# ── AC-006 圖譜 ─────────────────────────────────────────────

def test_graph_export_has_both_directions(tmp_path):
    """AC: AC-006 — --export 的鄰接表對 fixture 的 [[link]] 正確且含反向邊"""
    out = tmp_path / "adj.json"
    code, _ = run("wiki_graph.py", "--wiki_dir", str(FIXTURE), "--export", str(out))
    assert code == 0
    adj = json.loads(out.read_text(encoding="utf-8"))
    assert "arch/graph-only-page" in adj["out"]["arch/five-layer"]
    assert "arch/five-layer" in adj["in"]["arch/graph-only-page"]
    assert adj["out"]["misc/orphan"] == []


# ── AC-007 ~ AC-010 四層與契約 ──────────────────────────────

def test_l0_alias_ranks_first():
    """AC: AC-007 — query 等於 alias → 該頁 rank 1 且 layers 含 L0"""
    out = q("--query", "留存口徑", "--top_k", "3")
    assert out["results"], out
    top = out["results"][0]
    assert top["slug"] == "retention-definition"
    assert "L0" in top["layers"]


def test_l3_graph_only_page_surfaces():
    """AC: AC-008 — 只被 wikilink 指到、無關鍵字的頁在 top_k 內且 layers == ['L3']"""
    out = q("--query", "五層架構", "--top_k", "5")
    hit = [r for r in out["results"] if r["slug"] == "graph-only-page"]
    assert hit, [r["slug"] for r in out["results"]]
    assert hit[0]["layers"] == ["L3"]


def test_garbage_query_does_not_crash():
    """AC: AC-009 — 亂碼 query 回 ok:true 不 crash；有子字串命中時兜底層必回結果"""
    out = q("--query", "zzqqxx9999")
    assert out["ok"] is True and isinstance(out["results"], list)

    out2 = q("--query", "ylopho")     # 詞中片段：L0/L1 皆不命中，只有子字串
    assert out2["results"], "兜底層應命中"
    assert out2["results"][0]["layers"] == ["fallback"]


def test_meta_contract_fields():
    """AC: AC-010 — meta 含 index_used/index_fresh/layers_used/layers_skipped/tokenizer/backend/elapsed_ms"""
    out = q("--query", "留存")
    meta = out["meta"]
    for key in ("index_used", "index_fresh", "layers_used", "layers_skipped",
                "tokenizer", "bm25_backend", "elapsed_ms", "warnings", "total"):
        assert key in meta, key
    assert meta["layers_skipped"].get("L2") == "no_embeddings"   # 語意層未啟用要講明


def test_filters_and_trust():
    """AC: AC-010 — type/status/tags/trust/approved-only 過濾生效"""
    assert [r["slug"] for r in q("--query", "留存", "--trust", "llm-distilled")["results"]] \
        == ["pending-review"]
    assert all(r["approved"] is True
               for r in q("--query", "留存", "--approved-only")["results"])
    assert all(r["type"] == "concept"
               for r in q("--query", "定義", "--type", "concept")["results"])
    assert all("ops" in r["tags"] for r in q("--query", "部署", "--tags", "ops")["results"])


def test_full_budget_and_out_file(tmp_path):
    """AC: AC-010 — --full 超 max_chars 標 truncated；--out 落盤且不回傳 content"""
    out = q("--query", "留存", "--full", "--max_chars", "80")
    assert out["meta"]["truncated"] is True
    total = sum(len(r.get("content", "")) for r in out["results"])
    assert total <= 80

    dest = tmp_path / "ctx.md"
    out2 = q("--query", "留存", "--full", "--out", str(dest))
    assert out2["meta"]["out_file"] == str(dest)
    assert dest.exists() and dest.read_text(encoding="utf-8").strip()
    assert all("content" not in r for r in out2["results"])


def test_text_format_still_human_readable():
    """AC: AC-010 — --format text 保留 v2 人類輸出（相容）"""
    code, payload = run("wiki_query.py", "--wiki_dir", str(FIXTURE),
                        "--query", "留存口徑", "--format", "text")
    assert code == 0
    assert isinstance(payload, str) and "🔍 查詢" in payload


def test_multi_domain_requires_explicit_domains():
    """AC: AC-010 — 多 domain 需顯式 --domains（D-4），page 帶 domain 前綴"""
    root = FIXTURE.parent          # tests/fixtures/ 底下把 wiki 當成一個 domain 用
    code, payload = run("wiki_query.py", "--knowledge_root", str(root.parent),
                        "--domains", "fixtures", "--query", "留存口徑")
    # fixtures/wiki 存在 → 應成功且 page 前綴 domain
    assert code == 0, payload
    assert payload["meta"]["domains"] == ["fixtures"]
    assert payload["results"][0]["page"].startswith("fixtures/")


# ── AC-011 JSON Schema ─────────────────────────────────────

def test_outputs_conform_to_contract_schema():
    """AC: AC-011 — 成功/空結果/錯誤三種輸出皆通過 query-contract.schema.json"""
    jsonschema = pytest.importorskip(
        "jsonschema", reason="需要 jsonschema 才能驗契約；用系統 python3 跑（venv 未安裝）")
    schema = json.loads((SCRIPTS.parent / "references" /
                         "query-contract.schema.json").read_text(encoding="utf-8"))
    payloads = [
        q("--query", "留存口徑"),
        q("--query", "zzqqxx9999"),                       # 空結果
        run("wiki_query.py", "--wiki_dir", "/nope", "--query", "x")[1],   # 錯誤
    ]
    for p in payloads:
        jsonschema.validate(instance=p, schema=schema)
