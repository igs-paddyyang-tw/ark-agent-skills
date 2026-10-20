#!/usr/bin/env python3
"""gr_query — 依 adapter 產生撈資料的 SQL；--run 時交給 ark-db-query 匯出成標準資料集 CSV。

資料集與欄位契約見 references/data-contract.md。adapter 欄位寫「TODO:」的，需要它的資料集或欄位會被略過並列在結果裡。

用法:
  python gr_query.py --config report.yaml                 # 只產 SQL 到 <data_dir>/sql/
  python gr_query.py --config report.yaml --run           # 產 SQL 並用 ark-db-query bq_export.py 匯出 CSV
  python gr_query.py --config report.yaml --run --dry-run # 只估算掃描量
  python gr_query.py --config report.yaml --bench         # 另外為 benchmark_games 產 bench/<名稱>/ 的資料集
"""
from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gr_common as C  # noqa: E402


def ok(v) -> bool:
    return bool(v) and not str(v).startswith("TODO")


def q(s: str) -> str:
    return "'" + str(s).replace("'", "''") + "'"


class SQL:
    def __init__(self, ad: dict, cfg: dict, ids: list, launch: dt.date, days: int):
        self.ad, self.cfg = ad, cfg
        c = ad["columns"]
        self.c = c
        self.T = lambda t: f"`{ad['project']}.{ad['dataset']}.{ad['tables'][t]}`"
        self.gids = ", ".join(q(ad.get("gid_format", "{id}").format(id=i)) for i in ids)
        self.launch = launch
        self.start, self.end = launch, launch + dt.timedelta(days=days - 1)
        self.skipped = []

    def seg_cols(self, alias="u", date_expr=None):
        c, out = self.c, []
        if ok(c.get("vip")):
            out.append(f"{alias}.{c['vip']} AS vip")
        if ok(c.get("market")):
            out.append(f"{alias}.{c['market']} AS market")
        if ok(c.get("reg_date")):
            out.append(f"DATE_DIFF({date_expr or alias + '.' + c['date']}, {alias}.{c['reg_date']}, DAY) AS reg_days")
        return out

    def game_user_daily(self):
        c = self.c
        sel = [f"{c['date']} AS d", f"CAST({c['uid']} AS STRING) AS uid", f"SUM({c['bet']}) AS bet", f"SUM({c['spins']}) AS spins"]
        if ok(c.get("win")):
            sel.append(f"SUM({c['win']}) AS win")
        else:
            self.skipped.append("game_user_daily.win（adapter 未設定派彩欄位 → Q5 RTP 略過）")
        for name, col in (self.ad.get("triggers") or {}).items():
            if ok(col):
                sel.append(f"SUM({col}) AS `trig_{name}`")
        seg = self.seg_cols("u")
        segsel = "".join(", u." + s.split(" AS ")[1] for s in seg)
        return f"""-- game_user_daily：本機台 × 玩家 × 日（{self.cfg['game']['name']}）
WITH g AS (
  SELECT {', '.join(sel)}
  FROM {self.T('game')}
  WHERE {c['date']} BETWEEN '{self.start}' AND '{self.end}' AND {c['gid']} IN ({self.gids})
  GROUP BY d, uid
), u AS (
  SELECT {c['date']} AS d, CAST({c['uid']} AS STRING) AS uid{(', ' + ', '.join(seg)) if seg else ''}
  FROM {self.T('user')} AS u
  WHERE {c['date']} BETWEEN '{self.start}' AND '{self.end}'
)
SELECT g.*{segsel}
FROM g LEFT JOIN u USING (d, uid)
ORDER BY d, uid
"""

    def _view_union(self, src="j"):
        parts = []
        for v in self.cfg.get("views") or [{"name": "全體"}]:
            w = ""
            if v.get("column"):
                vals = ", ".join(q(x) for x in (v.get("values") or v.get("not_values") or []))
                w = f" WHERE {v['column']} {'NOT IN' if 'not_values' in v else 'IN'} ({vals})"
            parts.append(f"SELECT {q(v['name'])} AS view, * FROM {src}{w}")
        return "\n  UNION ALL ".join(parts)

    def slot_daily(self):
        c = self.c
        seg = self.seg_cols("u")
        return f"""-- slot_daily：各切分 × 日 的全虎機押量、人數與本機台排名
WITH f AS (
  SELECT {c['date']} AS d, CAST({c['uid']} AS STRING) AS uid,
         IF({c['gid']} IN ({self.gids}), '__TARGET__', {c['gid']}) AS game, SUM({c['bet']}) AS bet
  FROM {self.T('game')}
  WHERE {c['date']} BETWEEN '{self.start}' AND '{self.end}' AND {self.ad['slot_filter']}
  GROUP BY d, uid, game
), u AS (
  SELECT {c['date']} AS d, CAST({c['uid']} AS STRING) AS uid{(', ' + ', '.join(seg)) if seg else ''}
  FROM {self.T('user')} AS u
  WHERE {c['date']} BETWEEN '{self.start}' AND '{self.end}'
), j AS (SELECT f.*{(', ' + ', '.join('u.' + s.split(' AS ')[1] for s in seg)) if seg else ''} FROM f LEFT JOIN u USING (d, uid)),
v AS (
  {self._view_union()}
), per_game AS (
  SELECT view, d, game, SUM(bet) AS bet FROM v GROUP BY view, d, game
), ranked AS (
  SELECT view, d, game, RANK() OVER (PARTITION BY view, d ORDER BY bet DESC) AS rk FROM per_game
)
SELECT t.view, t.d, t.slot_bet, t.slot_players, r.rk AS game_rank
FROM (SELECT view, d, SUM(bet) AS slot_bet, COUNT(DISTINCT uid) AS slot_players FROM v GROUP BY view, d) t
LEFT JOIN ranked r ON r.view = t.view AND r.d = t.d AND r.game = '__TARGET__'
ORDER BY t.view, t.d
"""

    def slot_users(self):
        c = self.c
        seg = self.seg_cols("u", date_expr=f"DATE '{self.end}'")
        if not seg:
            self.skipped.append("slot_users（adapter 沒有任何分層欄位 → Q2 對照組略過）")
            return None
        # 快照只有當天有上線的玩家才有列 → 取「期間內最後一筆快照」，不是只取期末那天（只取期末會讓約六成玩家分層欄位空白）
        raw = [c[k] for k in ("vip", "market", "reg_date") if ok(c.get(k))]
        return f"""-- slot_users：期間內有玩虎機的玩家與分層欄位（期間內最後一筆快照），Q2 對照組與試玩率分母用
WITH p AS (
  SELECT DISTINCT CAST({c['uid']} AS STRING) AS uid
  FROM {self.T('game')}
  WHERE {c['date']} BETWEEN '{self.start}' AND '{self.end}' AND {self.ad['slot_filter']}
), u AS (
  SELECT CAST({c['uid']} AS STRING) AS uid, {', '.join(raw)}
  FROM {self.T('user')}
  WHERE {c['date']} BETWEEN '{self.start}' AND '{self.end}'
  QUALIFY ROW_NUMBER() OVER (PARTITION BY {c['uid']} ORDER BY {c['date']} DESC) = 1
)
SELECT p.uid, {', '.join(seg)}
FROM p LEFT JOIN u ON u.uid = p.uid
"""

    def erosion(self):
        c = self.c
        w = int(self.cfg.get("erosion_window_days", 7))
        pre_s, post_e = self.launch - dt.timedelta(days=w), self.launch + dt.timedelta(days=w - 1)
        return f"""-- erosion：本機台玩家在上線前 {w} 日 vs 上線後 {w} 日，於各機台的押量（含全虎機總量）
WITH p AS (
  SELECT DISTINCT {c['uid']} AS uid FROM {self.T('game')}
  WHERE {c['date']} BETWEEN '{self.launch}' AND '{post_e}' AND {c['gid']} IN ({self.gids})
), x AS (
  SELECT IF(g.{c['gid']} IN ({self.gids}), '__TARGET__', g.{c['gid']}) AS game,
         IF(g.{c['date']} < '{self.launch}', 'pre', 'post') AS per, SUM(g.{c['bet']}) AS bet
  FROM {self.T('game')} AS g JOIN p ON g.{c['uid']} = p.uid
  WHERE g.{c['date']} BETWEEN '{pre_s}' AND '{post_e}' AND {self.ad['slot_filter']}
  GROUP BY game, per
)
SELECT game, SUM(IF(per = 'pre', bet, 0)) AS pre_bet, SUM(IF(per = 'post', bet, 0)) AS post_bet FROM x GROUP BY game
UNION ALL
SELECT '__ALL_SLOTS__', SUM(IF({c['date']} < '{self.launch}', {c['bet']}, 0)), SUM(IF({c['date']} >= '{self.launch}', {c['bet']}, 0))
FROM {self.T('game')} WHERE {c['date']} BETWEEN '{pre_s}' AND '{post_e}' AND {self.ad['slot_filter']}
"""

    def hours(self):
        hc = self.ad.get("hour_columns") or {}
        if not ok(self.ad["tables"].get("hours")) or not hc:
            self.skipped.append("hours（adapter 沒有時段表 → 健康觀察的時段圖略過）")
            return None
        c = self.c
        return f"""-- hours：本機台各時段押量
SELECT {hc['bucket']} AS bucket, SUM({hc['bet']}) AS bet
FROM {self.T('hours')}
WHERE {c['date']} BETWEEN '{self.start}' AND '{self.end}' AND {c['gid']} IN ({self.gids})
GROUP BY bucket ORDER BY bucket
"""


NEEDS = {"game_user_daily": ["uid", "bet", "spins"], "slot_daily": ["uid", "bet"], "slot_users": ["uid"],
         "erosion": ["uid", "bet"], "hours": []}


def build_all(ad, cfg, ids, launch, days, out_dir: pathlib.Path, only=None):
    s = SQL(ad, cfg, ids, launch, days)
    files, skipped = {}, []
    for ds, need in NEEDS.items():
        if only and ds not in only:
            continue
        miss = [k for k in need if not ok(ad["columns"].get(k))]
        if miss:
            skipped.append(f"{ds}（adapter 欄位未設定：{'、'.join(miss)}）")
            continue
        sql = getattr(s, ds)()
        if sql:
            p = out_dir / "sql" / f"{ds}.sql"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(sql, encoding="utf-8")
            files[ds] = p
    return files, skipped + s.skipped


def run_export(sql_file: pathlib.Path, out_csv: pathlib.Path, dry: bool, project: str, max_bytes: int | None = None) -> dict:
    tool = C.DB_QUERY / ("bq_query.py" if dry else "bq_export.py")
    if not tool.is_file():
        C.fail("MISSING_DEP", "找不到 ark-db-query", "安裝同層 ark-db-query，或自行執行 sql/ 下的 SQL 並存成 CSV")
    cmd = [sys.executable, "-X", "utf8", str(tool), "--project", project, "--sql-file", str(sql_file)]
    cmd += ["--dry-run"] if dry else ["--out", str(out_csv), "--out-format", "csv"]
    if max_bytes:
        cmd += ["--max-bytes-billed", str(int(max_bytes))]
    # bq_export 偶發卡住不回（2026-10-19 實測 36 支裡 3 支）→ 每支逾時 300 秒、最多重試 2 次
    for attempt in range(3):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        except subprocess.TimeoutExpired:
            continue
        if r.returncode == 0 or dry:
            return {"rc": r.returncode, "tail": (r.stdout or r.stderr).strip()[-300:], "tries": attempt + 1}
    return {"rc": 124, "tail": "逾時或失敗 3 次（bq_export 卡住）", "tries": 3}


def main() -> None:
    ap = argparse.ArgumentParser(description="產生／執行撈資料 SQL")
    ap.add_argument("--config", required=True)
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--bench", action="store_true", help="為 benchmark_games 產 bench/<名稱>/ 資料集")
    a = ap.parse_args()
    cfg = C.load_config(a.config)
    ap_ = C.adapter_path(cfg)
    if ap_ is None:
        C.emit({"adapter": "csv", "data_dir": str(C.data_dir(cfg)),
                "hint": "csv 模式不產 SQL：請把資料集放進 data_dir（欄位見 references/data-contract.md），然後 gr_run.py probe"},
               {"stage": "query"})
        return
    if not ap_.is_file():
        C.fail("BAD_INPUT", f"找不到 adapter {ap_}")
    ad = C.yaml_load(ap_)
    dd = C.data_dir(cfg)
    launch = C.to_date(cfg["game"]["launch_date"])
    jobs = [("target", cfg["game"].get("ids") or [cfg["game"].get("id")], launch, dd, None)]
    if a.bench:
        for b in cfg.get("benchmark_games") or []:
            jobs.append((b["name"], b["ids"], C.to_date(b["launch_date"]), dd / "bench" / b["name"], ["game_user_daily", "slot_daily", "slot_users"]))
    report = []
    for name, ids, ld, out_dir, only in jobs:
        files, skipped = build_all(ad, cfg, ids, ld, int(cfg["stage"]), out_dir, only)
        res = {"job": name, "sql": {k: str(v) for k, v in files.items()}, "skipped": skipped}
        if a.run or a.dry_run:
            res["export"] = {k: run_export(v, out_dir / f"{k}.csv", a.dry_run, ad["project"], ad.get("max_bytes_billed")) for k, v in files.items()}
        report.append(res)
    failed = [j["job"] + ":" + k for j in report for k, v in (j.get("export") or {}).items() if v["rc"] != 0]
    if failed:
        C.fail("QUERY_FAILED", f"{len(failed)} 個查詢失敗", "看 data.jobs[].export 的 tail", {"jobs": report})
    C.emit({"jobs": report, "next": f"gr_run.py probe --config {a.config}"}, {"stage": "query"})


if __name__ == "__main__":
    main()
