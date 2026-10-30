"""ark-community-cli 行為測試：假名化／PII 守門、分類規則、normalize→classify→digest→handoff 整條管線。

全部用 tmp_path 與手造的 raw JSONL，不打 Discord／X API（pull 腳本不在測試範圍）。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import common  # noqa: E402
import classify  # noqa: E402
import normalize  # noqa: E402

CLI = SCRIPTS / "community_cli.py"
WEEK = "2026-W40"  # 2026-09-28（一）～ 10-04
BASE = "アプデ後にログインできないバグが続いて最悪、早く直して"
SUFFIXES = ["iPhoneです", "三日目です", "Androidでも同じ", "今朝からずっと", "課金したのに"]


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(CLI), *args], capture_output=True, text=True, timeout=60)


def init_ws(tmp_path: Path, act: int = 3, watch: int = 2) -> Path:
    """用 init 建 workspace，並把 verdict 門檻調低，讓小 fixture 就能觸發 act。"""
    ws = tmp_path / "community"
    r = run("init", "--out", str(ws))
    assert r.returncode == 0, r.stdout + r.stderr
    cfg_p = ws / "config.yaml"
    cfg = yaml.safe_load(cfg_p.read_text(encoding="utf-8"))
    cfg["classify"]["verdict_thresholds"] = {"act": act, "watch": watch}
    cfg["discord"]["channels"] = [{"id": "1", "name": "feedback", "feedback_hint": None}]
    cfg_p.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    return cfg_p


def discord_msg(i: int, text: str, author: str, ts: str = "2026-09-29T10:00:00+00:00") -> dict:
    return {"id": f"9000000000000000{i:02d}", "timestamp": ts, "content": text,
            "author": {"id": author, "username": f"nick_{author[-4:]}"},
            "reactions": [{"count": i}], "attachments": [], "_channel_name": "feedback"}


# ── 純函式 ────────────────────────────────────────────────


def test_ctx_refuses_placeholder_salt(tmp_path):
    """範本鹽值（REPLACE_…）沒換就必須拒絕執行 —— 否則所有部署共用同一把鹽，假名可被反推。"""
    cfg = tmp_path / "config.yaml"
    cfg.write_text("root: .\npseudonym_salt: REPLACE_WITH_RANDOM_32_BYTES_HEX\n", encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        common.Ctx(cfg)
    assert "pseudonym_salt" in str(e.value.code)


def test_pseudonym_is_stable_and_salt_dependent(tmp_path):
    """同鹽同 id → 同 author_key（跨週可追蹤）；換鹽 → 不同（假名不可跨部署對照）。"""
    a, b = tmp_path / "a.yaml", tmp_path / "b.yaml"
    a.write_text("root: .\npseudonym_salt: aaaa\n", encoding="utf-8")
    b.write_text("root: .\npseudonym_salt: bbbb\n", encoding="utf-8")
    ca, cb = common.Ctx(a), common.Ctx(b)
    k = ca.pseudonym("123456789012345678")
    assert k == ca.pseudonym("123456789012345678")
    assert len(k) == 16 and "123456789012345678" not in k
    assert k != cb.pseudonym("123456789012345678")


def test_pii_scan_flags_snowflake_handle_and_username(tmp_path):
    """PII 自掃要抓到 17–19 位 snowflake、@handle、已知 username；16 位 hex 假名不算。"""
    p = tmp_path / "x.md"
    p.write_text("author 1234567890123456789 說 @someone_jp 很爛，player_ab12 也是；key=0123456789abcdef", encoding="utf-8")
    hits = common.pii_scan(p, ["player_ab12"])
    kinds = sorted(h.split(":")[0] for h in hits)
    assert kinds == ["handle", "snowflake", "username"]
    p.write_text("author_key 0123456789abcdef 無個資", encoding="utf-8")
    assert common.pii_scan(p) == []


def test_parse_since_and_week_range_boundaries():
    """週界是 ISO 週一 00:00 UTC 起算 7 天；'36h' 相對時間要能解析。"""
    lo, hi = common.week_range(WEEK)
    assert lo.isoformat() == "2026-09-28T00:00:00+00:00"
    assert (hi - lo).days == 7
    assert common.parse_since("2026-10-01T00:00:00+00:00").isoformat() == "2026-10-01T00:00:00+00:00"
    delta = common.parse_since("1d") - common.parse_since("36h")
    assert round(delta.total_seconds() / 3600) == 12


def test_strip_discord_ids_removes_embedded_snowflakes():
    """mention／channel／role／custom emoji 內嵌的 snowflake 必須在落 records 前脫敏（hard_stop）。"""
    t = "<@123456789012345678> <@!123456789012345679> <@&123456789012345670> <#123456789012345671> <:pepe:123456789012345672>"
    out = normalize.strip_discord_ids(t)
    assert common.SNOWFLAKE_RE.search(out) is None
    assert out == "[uid] [uid] [uid] [ch] :pepe:"


def test_classify_type_hint_breaks_tie_and_zero_hit_is_uncategorized():
    """命中數平手時頻道 hint 決勝；完全沒命中 → uncategorized（進 llm-queue），不可亂猜。"""
    lex = {"feedback_type": {"bug": {"en": ["crash"]}, "ux": {"en": ["laggy"]}}}
    assert classify.classify_type("crash and laggy", lex, None)[0] == "uncategorized"
    assert classify.classify_type("crash and laggy", lex, "ux")[0] == "ux"
    assert classify.classify_type("hello world", lex, None)[0] == "uncategorized"
    assert classify.classify_type("game crash again", lex, None)[0] == "bug"


# ── 整條管線（子行程跑 CLI，看 exit code 與產物）─────────────────


def build_pipeline(tmp_path: Path) -> tuple[Path, Path]:
    cfg_p = init_ws(tmp_path)
    ws = cfg_p.parent
    msgs = [discord_msg(i, f"<@12345678901234567{i}> {BASE}{s}", f"55500000000000000{i}")
            for i, s in enumerate(SUFFIXES)]
    # 與第 0 則脫敏後全文相同（mention 對象不同，脫敏後都是 [uid]）→ 應被標 duplicate_of
    msgs.append(discord_msg(9, f"<@111111111111111111> {BASE}{SUFFIXES[0]}", "555000000000000009"))
    raw = ws / "raw" / "discord" / "2026-09-29.jsonl"
    raw.write_text("\n".join(json.dumps(m, ensure_ascii=False) for m in msgs), encoding="utf-8")
    for step in (["normalize"], ["classify", "--week", WEEK], ["digest", "--week", WEEK]):
        r = run(*step, "--config", str(cfg_p))
        assert r.returncode == 0, f"{step}: {r.stdout}{r.stderr}"
    return cfg_p, ws


def test_pipeline_end_to_end_produces_pii_clean_digest(tmp_path):
    """正常路徑：6 則 raw → records 無 snowflake／username、全文重複被標 duplicate_of，
    5 位作者同一負面 cluster ≥ act 門檻 → 週摘 verdict=act／severity=P1，案件卡 F-{week}-1 產出。"""
    cfg_p, ws = build_pipeline(tmp_path)
    recs = [json.loads(line) for line in (ws / "records" / "2026-09-29.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(recs) == 6
    assert sum(1 for r in recs if r["duplicate_of"]) == 1
    blob = (ws / "records" / "2026-09-29.jsonl").read_text(encoding="utf-8")
    assert common.SNOWFLAKE_RE.search(blob) is None
    assert "nick_" not in blob and "username" not in blob

    digest = (ws / "reports" / "weekly" / f"{WEEK}-community-digest.md").read_text(encoding="utf-8")
    fm = yaml.safe_load(digest.split("---")[1])
    assert fm["verdict"] == "act" and fm["severity"] == "P1"
    assert fm["findings"] == [f"F-{WEEK}-1"]
    case = (ws / "cases" / WEEK / f"F-{WEEK}-1.md").read_text(encoding="utf-8")
    assert "feedback_type: bug" in case and "distinct_authors: 5" in case

    r = run("loop", "handoff", "--config", str(cfg_p), "--week", WEEK)
    assert r.returncode == 0, r.stdout + r.stderr
    manifest = json.loads((ws / "reports" / "weekly" / f"{WEEK}-handoff.json").read_text(encoding="utf-8"))
    assert manifest["pii_scan"] == "PASS"
    assert [i["target"] for i in manifest["items"]] == ["events/", "pain-points/"]


def test_normalize_rerun_is_incremental(tmp_path):
    """邊界：同一 raw 檔重跑 normalize 不得重複寫入 records（state/normalized.json 記已處理）。"""
    cfg_p, ws = build_pipeline(tmp_path)
    before = (ws / "records" / "2026-09-29.jsonl").read_text(encoding="utf-8")
    r = run("normalize", "--config", str(cfg_p))
    assert r.returncode == 0 and "0 raw 檔" in r.stdout
    assert (ws / "records" / "2026-09-29.jsonl").read_text(encoding="utf-8") == before


def test_digest_empty_week_fails(tmp_path):
    """反例：該週沒有 classify 資料 → digest 必須非 0 結束並指路「先跑 classify」，不能產空報告。"""
    cfg_p = init_ws(tmp_path)
    r = run("digest", "--config", str(cfg_p), "--week", WEEK)
    assert r.returncode != 0
    assert "classify" in (r.stdout + r.stderr)
    assert not (cfg_p.parent / "reports" / "weekly" / f"{WEEK}-community-digest.md").exists()


def test_digest_fails_when_pii_leaks_into_cases(tmp_path):
    """反例：records 文字含 @handle（mask 漏網）→ digest PII 自掃要 FAIL 並回 exit 1。"""
    cfg_p = init_ws(tmp_path)
    ws = cfg_p.parent
    msgs = [discord_msg(i, f"@leaker_jp {BASE}{s}", f"55500000000000000{i}") for i, s in enumerate(SUFFIXES)]
    (ws / "raw" / "discord" / "2026-09-29.jsonl").write_text(
        "\n".join(json.dumps(m, ensure_ascii=False) for m in msgs), encoding="utf-8")
    assert run("normalize", "--config", str(cfg_p)).returncode == 0
    assert run("classify", "--config", str(cfg_p), "--week", WEEK).returncode == 0
    r = run("digest", "--config", str(cfg_p), "--week", WEEK)
    assert r.returncode == 1
    assert "PII scan FAIL" in r.stdout


def test_init_refuses_overwrite_without_force(tmp_path):
    """反例：config 已存在時 init 不可覆寫（鹽值一換，所有歷史 author_key 失聯）。"""
    cfg_p = init_ws(tmp_path)
    salt = yaml.safe_load(cfg_p.read_text(encoding="utf-8"))["pseudonym_salt"]
    r = run("init", "--out", str(cfg_p.parent))
    assert r.returncode == 1
    assert yaml.safe_load(cfg_p.read_text(encoding="utf-8"))["pseudonym_salt"] == salt
    assert len(salt) == 64
