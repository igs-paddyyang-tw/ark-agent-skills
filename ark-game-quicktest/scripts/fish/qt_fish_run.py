"""qt_fish_run — 魚機 ④⑤ 快測：qt-config.yaml → fishsim 平行跑 → rtp-report.json＋md＋html。

由貓魚傳說專案版 `quicktest/qt_run.py` 一般化（ark-game-quicktest 2.4.0）。
技能不帶 Go 模擬器：每款魚機在自己的 go-server 寫 `cmd/fishsim`，只要吐
`references/fish-quicktest-contract.md` 定義的 JSON，就能接本程式。

用法（在專案根目錄，或以 --root 指定）：
    python qt_fish_run.py --qt-config data/fish/<slug>/quicktest/qt-config.yaml
    python qt_fish_run.py --qt-config … --shots 1000000          # 煙霧測試（覆寫發數）
    python qt_fish_run.py --qt-config … --out-dir output/fish/<slug>/qt-check

只回報數值不下結論：verdict 只看 gate（random 各種子總 RTP 在 target ± tolerance），
打法敏感度、命中率／附加獎勵率偏差列成 Findings 交人判斷。
exit 0＝gate 過、3＝gate 不過、2＝輸入錯誤或執行失敗。
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import html
import json
import math
import os
import shutil
import statistics
import sys
from datetime import date
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
SKILL_DIR = HERE.parent.parent
MD_REPORT = SKILL_DIR.parent / "ark-md-report" / "scripts"
Z95 = 1.959964
EXIT_PASS, EXIT_BAD, EXIT_GATE = 0, 2, 3

#: 設定檔 JSON 欄位名（可在 qt-config `fields` 覆寫）
DEFAULT_FIELDS = {"game_rate": "game_rate", "fish_list": "fish_info", "type": "type",
                  "name": "name", "odds": "odds", "drop_ppm": "drop_ppm"}
#: 打法敏感度：最偏打法與目標差距超過此值 → finding（P2）；總 RTP > 1 → P1
DEFAULT_AIM_DEVIATION = 0.01


class QtError(RuntimeError):
    """輸入或執行錯誤（exit 2）。"""


# ── 設定與路徑 ─────────────────────────────────────────────────────────────

def sha16(p: Path) -> str:
    """檔案 sha256 前 16 碼。"""
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def resolve(root: Path, value: str | os.PathLike) -> Path:
    """相對路徑以 root 為基準；絕對路徑原樣。"""
    p = Path(value).expanduser()
    return p if p.is_absolute() else (root / p)


def rel(root: Path, p: Path) -> str:
    """盡量以 root 為基準顯示路徑；不在 root 下就給絕對路徑。"""
    try:
        return p.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return p.resolve().as_posix()


def load_qt(qt_path: Path, root: Path) -> dict:
    """讀 qt-config.yaml、補預設值、解析路徑；缺必填欄位丟 QtError。"""
    if not qt_path.is_file():
        raise QtError(f"找不到 qt-config：{qt_path}")
    qt = yaml.safe_load(qt_path.read_text(encoding="utf-8")) or {}
    miss = [k for k in ("tool", "config", "runs", "gate") if k not in qt]
    if miss:
        raise QtError(f"qt-config 缺必填欄位：{', '.join(miss)}")
    gate = qt["gate"]
    if not isinstance(gate, dict) or "total" not in gate:
        raise QtError("gate 需為 {total, tolerance}")
    gate.setdefault("tolerance", 0.005)
    for r in qt["runs"]:
        if not {"aim", "seeds", "shots"} <= set(r):
            raise QtError(f"runs 每列需 aim／seeds／shots：{r}")
    # slug 預設：qt-config 在 <slug>/quicktest/ 下 → <slug>；否則取所在目錄名
    slug = qt.get("slug") or (qt_path.parent.parent.name if qt_path.parent.name == "quicktest"
                              else qt_path.parent.name)
    paths = {
        "qt_config": qt_path,
        "tool": resolve(root, qt["tool"]),
        "config": resolve(root, qt["config"]),
        "out_dir": resolve(root, qt["out_dir"]) if qt.get("out_dir") else qt_path.parent / "qt-report",
        "runs_dir": resolve(root, qt["runs_dir"]) if qt.get("runs_dir") else root / "output" / "fish" / slug / "qt-runs",
    }
    if not paths["tool"].exists():
        raise QtError(f"tool 不存在：{paths['tool']}")
    if not paths["config"].is_file():
        raise QtError(f"config 不存在：{paths['config']}")
    return {**qt, "slug": slug, "title": qt.get("title") or slug,
            "bonus_key": qt.get("bonus_key", "bead"),
            "fields": {**DEFAULT_FIELDS, **(qt.get("fields") or {})},
            "aim_deviation": float(qt.get("aim_deviation", DEFAULT_AIM_DEVIATION)),
            "_paths": paths}


def find_go(explicit: str | None) -> str:
    """找 go：--go > $GO_BIN > PATH > ~/.local/go/bin/go。"""
    for c in (explicit, os.environ.get("GO_BIN"), shutil.which("go"),
              str(Path.home() / ".local" / "go" / "bin" / "go")):
        if c and Path(c).exists():
            return c
    raise QtError("找不到 go（--go、$GO_BIN 或 PATH）；tool 是 Go 套件目錄時需要")


# ── 執行 ───────────────────────────────────────────────────────────────────

async def sh(*args: str, cwd: Path, env: dict | None = None) -> str:
    """跑外部指令，失敗丟 QtError（帶 stderr 尾段）。"""
    proc = await asyncio.create_subprocess_exec(
        *args, cwd=cwd, env=env or os.environ.copy(),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    out, err = await proc.communicate()
    if proc.returncode != 0:
        raise QtError(f"{' '.join(args)} → exit {proc.returncode}\n{err.decode(errors='replace')[-2000:]}")
    return out.decode()


async def prepare_tool(tool: Path, runs_dir: Path, go: str | None) -> tuple[list[str], Path]:
    """tool 是目錄 → go build 成執行檔；是 .py → 用目前 Python 跑；其他檔案 → 直接執行。

    回傳 (指令前綴, 執行時 cwd)。
    """
    if tool.is_dir():
        go_bin = find_go(go)
        exe = runs_dir / ("fishsim.exe" if os.name == "nt" else "fishsim")
        env = {**os.environ, "PATH": f"{Path(go_bin).parent}{os.pathsep}{os.environ.get('PATH', '')}"}
        await sh(go_bin, "build", "-o", str(exe), ".", cwd=tool, env=env)
        return [str(exe)], tool
    if tool.suffix == ".py":
        return [sys.executable, str(tool)], tool.parent
    return [str(tool)], tool.parent


def run_name(aim: str, seed: int, shots: int) -> str:
    """原始輸出檔名（與專案版相同慣例）。"""
    tag = f"{shots // 1_000_000}m" if shots >= 1_000_000 else str(shots)
    return f"qt{tag}-{aim}-seed{seed}.json"


async def run_all(qt: dict, shots_override: int | None, go: str | None, jobs_n: int | None) -> list[dict]:
    """依 runs 平行跑 fishsim（打法 × 種子），原始 JSON 落 runs_dir。"""
    P = qt["_paths"]
    P["runs_dir"].mkdir(parents=True, exist_ok=True)
    cmd, cwd = await prepare_tool(P["tool"], P["runs_dir"], go)
    jobs = [(str(r["aim"]), int(s), shots_override or int(r["shots"])) for r in qt["runs"] for s in r["seeds"]]
    sem = asyncio.Semaphore(jobs_n or max(1, (os.cpu_count() or 2) - 1))

    async def one(aim: str, seed: int, shots: int) -> dict:
        async with sem:
            raw = await sh(*cmd, "-config", str(P["config"]), "-shots", str(shots), "-seed", str(seed),
                           "-aim", aim, "-per", str(qt.get("per_frame", 8)), "-bet", str(qt.get("bet", 1)),
                           cwd=cwd)
        try:
            d = json.loads(raw)
        except json.JSONDecodeError as ex:
            raise QtError(f"fishsim 輸出不是 JSON（{aim} seed {seed}）：{ex}") from ex
        check_contract(d, aim, seed)
        d.setdefault("aim", aim)
        d.setdefault("seed", seed)
        d.setdefault("shots", shots)
        name = run_name(aim, seed, shots)
        (P["runs_dir"] / name).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        d["file"] = name
        print(f"  ✓ {aim:<8} seed {seed}  total {d['rtp']['total']:.6f}", file=sys.stderr)
        return d

    return list(await asyncio.gather(*(one(*j) for j in jobs)))


def check_contract(d: dict, aim: str, seed: int) -> None:
    """驗 fishsim 輸出契約最低要求：rtp.fish／rtp.total、per_fish{shots,kills,rtp}。"""
    where = f"（{aim} seed {seed}）"
    rtp = d.get("rtp")
    if not isinstance(rtp, dict) or not {"fish", "total"} <= set(rtp):
        raise QtError(f"fishsim 輸出缺 rtp.fish／rtp.total{where}")
    pf = d.get("per_fish")
    if not isinstance(pf, dict) or not pf:
        raise QtError(f"fishsim 輸出缺 per_fish{where}")
    for t, s in pf.items():
        if not {"shots", "kills", "rtp"} <= set(s):
            raise QtError(f"per_fish[{t}] 缺 shots／kills／rtp{where}")


# ── 彙整 ───────────────────────────────────────────────────────────────────

def binom_half(p: float, n: int) -> float:
    """二項 95% 區間半寬。"""
    return Z95 * math.sqrt(p * (1 - p) / n) if n else 0.0


def enrich(run: dict, cfg: dict, qt: dict) -> dict:
    """⑤ 回填：各魚種命中率／附加獎勵率實測 vs 理論（二項 95% 區間）；並標 gate 區間內外。"""
    F = qt["fields"]
    info = {str(f[F["type"]]): f for f in cfg[F["fish_list"]]}
    rate = float(cfg[F["game_rate"]])
    total_shots = run.get("shots") or sum(s["shots"] for s in run["per_fish"].values()) or 1
    for t, s in run["per_fish"].items():
        f = info.get(str(t))
        if f is None:
            raise QtError(f"per_fish 的魚種 {t} 不在設定檔 {F['fish_list']}")
        s.setdefault("name", f.get(F["name"], str(t)))
        p_hit = rate / float(f[F["odds"]])
        h = s["kills"] / s["shots"] if s["shots"] else 0.0
        half = binom_half(p_hit, s["shots"])
        s.update(odds=f[F["odds"]], hit_theory=round(p_hit, 6), hit_actual=round(h, 6),
                 hit_ci95=round(half, 6), hit_in_ci=abs(h - p_hit) <= half,
                 shot_share=round(s["shots"] / total_shots, 6))
        if "beads" in s and F["drop_ppm"] in f:
            p_drop = float(f[F["drop_ppm"]]) / 1e6
            dr = s["beads"] / s["kills"] if s["kills"] else 0.0
            dhalf = binom_half(p_drop, s["kills"])
            s.update(drop_theory=round(p_drop, 6), drop_actual=round(dr, 6), drop_ci95=round(dhalf, 6),
                     drop_in_ci=abs(dr - p_drop) <= dhalf)
    g = qt["gate"]
    run["within_gate"] = abs(run["rtp"]["total"] - g["total"]) <= g["tolerance"]
    return run


def build_report(qt: dict, cfg: dict, runs: list[dict], today: str, root: Path) -> dict:
    """彙整成 rtp-report.json（閉環回填來源）。"""
    P, F, gate = qt["_paths"], qt["fields"], qt["gate"]
    rnd = sorted((r for r in runs if r["aim"] == "random"), key=lambda r: r["seed"])
    tot = [r["rtp"]["total"] for r in rnd]
    mean = statistics.fmean(tot) if tot else 0.0
    ci = (2.0 * statistics.stdev(tot) / math.sqrt(len(tot))) if len(tot) > 1 else None
    passed = bool(rnd) and all(abs(t - gate["total"]) <= gate["tolerance"] for t in tot)
    bonus_cfg = cfg.get(qt["bonus_key"])
    keep = [k for k in (F["type"], F["name"], F["odds"], F["drop_ppm"], "alive")]
    return {
        "game": qt["slug"], "title": qt["title"], "date": today,
        "tool": f"ark-game-quicktest scripts/fish/qt_fish_run.py → {rel(root, P['tool'])}",
        "config": {"path": rel(root, P["config"]), "sha16": sha16(P["config"]), "note": cfg.get("_spec", "")},
        "qt_config": rel(root, P["qt_config"]),
        "qt_config_sha16": sha16(P["qt_config"]),
        "target": gate,
        "bonus_key": qt["bonus_key"],
        "aim_deviation": qt["aim_deviation"],
        "params": {"game_rate": cfg[F["game_rate"]],
                   **({qt["bonus_key"]: bonus_cfg} if isinstance(bonus_cfg, dict) else {}),
                   "fish": [{k: f[k] for k in keep if k in f} for f in cfg[F["fish_list"]]]},
        "analytic": next((r["analytic"] for r in runs if r.get("analytic")), {}),
        "gate": {"aim": "random", "seeds": len(rnd), "totals": tot, "mean": round(mean, 6),
                 "seed_ci95": round(ci, 6) if ci is not None else None, "pass": passed},
        "runs": sorted(runs, key=lambda r: (r["aim"] != "random", r["aim"], r["seed"])),
    }


def findings(rep: dict, aim_deviation: float | None = None) -> list[dict]:
    """自動列 Findings（只描述數值，不下設計結論）；打法門檻預設取報告的 aim_deviation。"""
    if aim_deviation is None:
        aim_deviation = float(rep.get("aim_deviation", DEFAULT_AIM_DEVIATION))
    g, t = rep["gate"], rep["target"]
    out = [{"id": "F-1", "sev": "P3" if g["pass"] else "P0",
            "what": (f"random {g['seeds']} 種子總 RTP {'／'.join(f'{x:.4f}' for x in g['totals'])}，平均 {g['mean']:.4f}"
                     if g["seeds"] else "沒有 random 打法的 run，gate 無從判定"),
            "impact": f"gate {t['total']} ±{t['tolerance']} {'通過' if g['pass'] else '不通過'}"}]
    others = [r for r in rep["runs"] if r["aim"] != "random"]
    if others:
        worst = max(others, key=lambda r: abs(r["rtp"]["total"] - t["total"]))
        hi = max(others, key=lambda r: r["rtp"]["total"])
        lo = min(others, key=lambda r: r["rtp"]["total"])
        dev = worst["rtp"]["total"] - t["total"]
        over1 = hi["rtp"]["total"] > 1
        sev = "P1" if over1 else ("P2" if abs(dev) > aim_deviation else "P3")
        out.append({"id": "F-2", "sev": sev,
                    "what": (f"打法敏感度：最高 {hi['aim']} {hi['rtp']['total']:.4f}、最低 {lo['aim']} {lo['rtp']['total']:.4f}；"
                             f"最偏 {worst['aim']} 偏離目標 {dev:+.4f}（門檻 ±{aim_deviation}）"),
                    "impact": ("專挑某魚的玩家長期回收超過 1" if over1 else
                               "最偏打法偏離超過門檻，交人判斷是否為打法漏洞" if sev == "P2" else
                               "打法差距在門檻內，交人判斷")})
    else:
        out.append({"id": "F-2", "sev": "P2", "what": "只跑了 random，沒跑偏打法（cheapest／richest／最佳比值）",
                    "impact": "打法漏洞只有多打法快測抓得到，補跑後再判"})
    cells = sum(len(r["per_fish"]) for r in rep["runs"])
    miss = [1 for r in rep["runs"] for v in r["per_fish"].values() if not v["hit_in_ci"]]
    lim = len(rep["runs"]) // 4
    out.append({"id": "F-3", "sev": "P2" if len(miss) > lim else "P3",
                "what": f"各魚種命中率落在理論 95% 區間外 {len(miss)} 格（共 {cells} 格）",
                "impact": "命中判定與 game_rate÷倍率一致" if len(miss) <= lim else "命中判定可能偏離規格，查命中鏈"})
    dcells = [v for r in rep["runs"] for v in r["per_fish"].values() if "drop_in_ci" in v]
    if dcells:
        dmiss = sum(1 for v in dcells if not v["drop_in_ci"])
        out.append({"id": "F-4", "sev": "P2" if dmiss > lim else "P3",
                    "what": f"各魚種附加獎勵率（{rep['bonus_key']}）落在理論 95% 區間外 {dmiss} 格（共 {len(dcells)} 格）",
                    "impact": "附加獎勵掉落與設定檔一致" if dmiss <= lim else "附加獎勵掉落可能偏離設定檔，查掉落判定"})
    a = rep["analytic"].get("total") if isinstance(rep["analytic"], dict) else None
    if a and g["seeds"]:
        out.append({"id": "F-5", "sev": "P3",
                    "what": f"解析近似 {a:.4f} vs 實測平均 {g['mean']:.4f}（差 {a - g['mean']:+.4f}）",
                    "impact": "解析未扣打死造成的提早離場；定版以實測為準"})
    return out


# ── 輸出 ───────────────────────────────────────────────────────────────────

def _fmt(v, spec: str, dash: str = "—") -> str:
    """數值格式化；缺值給 —。"""
    return dash if v is None else format(v, spec)


def write_md(rep: dict, fs: list[dict], md: Path, sources: list[str]) -> None:
    """Content 軌（ark-md-report data 型契約）。"""
    g, bk = rep["gate"], rep["bonus_key"]
    sev = {k: sum(1 for f in fs if f["sev"] == k.upper()) for k in ("p0", "p1", "p2", "p3")}
    fm = {
        "title": f"{rep['title']} ④⑤ 快測：random {g['seeds']} 種子平均 {g['mean']:.4f}，gate {'通過' if g['pass'] else '不通過'}",
        "type": "data", "subject": f"{rep['config']['path']}（sha {rep['config']['sha16']}）× fishsim",
        "date": rep["date"], "author": "aidev-agent（ark-game-quicktest qt_fish_run.py 自動產出）",
        "source_skill": "ark-md-report",
        "verdict": "confirmed" if g["pass"] else "rejected",
        "confidence": "high" if min((r["shots"] for r in rep["runs"]), default=0) >= 10_000_000 else "medium",
        "findings": sev, "tags": ["fish", "rtp", "quicktest", "probability"], "sources": sources,
    }
    p = rep["params"]
    L = ["---", yaml.safe_dump(fm, allow_unicode=True, sort_keys=False).strip(), "---", "",
         f"# {fm['title']}", "", "## Verdict", "",
         f"**{fm['verdict']}** —— 假設：設定檔 `{rep['config']['path']}`（sha {rep['config']['sha16']}）在 random 打法下總 RTP 落在 "
         f"{rep['target']['total']} ±{rep['target']['tolerance']}。結果：{'／'.join(f'{x:.6f}' for x in g['totals']) or '無'}，"
         f"{'全部落在區間內' if g['pass'] else '有種子落在區間外或缺 random run'}。", ""]
    if rep["config"]["note"]:
        L += [f"> 設定檔備註：{rep['config']['note']}", ""]
    L += ["## 假設與方法", "",
          f"- 工具：ark-game-quicktest `qt_fish_run.py` 讀 `{rep['qt_config']}`（sha {rep['qt_config_sha16']}），平行執行 fishsim（輸出契約見技能 `references/fish-quicktest-contract.md`）",
          f"- 參數：game_rate {p['game_rate']}；副玩法鍵 `{bk}`",
          "- 命中率理論＝game_rate ÷ 倍率；附加獎勵率理論＝設定檔 drop_ppm ÷ 1e6；區間為二項 95%",
          "- gate＝random 各種子總 RTP 都在目標 ± 容許內；其他打法只看敏感度", "",
          "## Findings", "", "| ID | 嚴重度 | 現象 | 影響 |", "|---|---|---|---|"]
    L += [f"| {f['id']} | {f['sev']} | {f['what']} | {f['impact']} |" for f in fs]
    L += ["", "## Evidence", "", "### E-1　各打法 RTP（支持 F-1、F-2）", "",
          f"| 打法 | 種子 | 發數 | 打魚 | {bk} | 總 RTP | 每千發附加獎勵 | 三同率 | 在區間 |",
          "|---|---:|---:|---:|---:|---:|---:|---:|:-:|"]
    for r in rep["runs"]:
        L.append(f"| {r['aim']} | {r['seed']} | {r['shots']:,} | {r['rtp']['fish']:.6f} | {_fmt(r['rtp'].get(bk), '.6f')} | "
                 f"**{r['rtp']['total']:.6f}** | {_fmt(r.get('beads_per_1000'), '.2f')} | {_fmt(r.get('triple_rate'), '.2%')} | "
                 f"{'✅' if r['within_gate'] else '❌'} |")
    r0 = next((r for r in rep["runs"] if r["aim"] == "random"), rep["runs"][0])
    L += ["", f"### E-2　各魚種命中率與附加獎勵率 vs 理論（{r0['aim']} 種子 {r0['seed']}，支持 F-3）", "",
          "| 魚 | 倍率 | 發數占比 | 命中率 理論 | 實測 | ±95% | 附加獎勵率 理論 | 實測 | ±95% | 單魚 RTP |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for v in r0["per_fish"].values():
        drop = (f"{v['drop_theory']:.2%} | {v['drop_actual']:.2%} | {v['drop_ci95']:.2%}{'' if v['drop_in_ci'] else ' ⚠️'}"
                if "drop_theory" in v else "— | — | —")
        L.append(f"| {v['name']} | {v['odds']} | {v['shot_share']:.1%} | {v['hit_theory']:.4%} | {v['hit_actual']:.4%} | "
                 f"{v['hit_ci95']:.4%}{'' if v['hit_in_ci'] else ' ⚠️'} | {drop} | {v['rtp']:.4f} |")
    L += ["", "## 邊界聲明", "",
          "- 打法模型簡化（每幀固定發數、不看距離）；真實玩家介於 random 與最偏打法之間",
          "- 只驗設定檔的數學；營運、錢包、活動不在範圍",
          "- 本報告只回報數值；拍板（倍率、打法漏洞處置）由人決定", ""]
    md.write_text("\n".join(L), encoding="utf-8")


def write_html(rep: dict, fs: list[dict], htm: Path) -> None:
    """View 軌：單檔、無外連；KPI＋打法長條（含目標帶）＋魚種表。"""
    e = html.escape
    g, t, bk = rep["gate"], rep["target"], rep["bonus_key"]
    runs = rep["runs"]
    lo_ax, hi_ax = 0.85, max(1.05, max(r["rtp"]["total"] for r in runs) + 0.02)
    W, bh = 640, 26
    x = lambda v: 150 + (max(lo_ax, min(v, hi_ax)) - lo_ax) / (hi_ax - lo_ax) * (W - 170)  # noqa: E731
    H = len(runs) * bh + 4
    bars = [f'<rect x="{x(t["total"] - t["tolerance"]):.1f}" y="0" width="{x(t["total"] + t["tolerance"]) - x(t["total"] - t["tolerance"]):.1f}" '
            f'height="{H}" fill="#16a34a" opacity=".12"/>',
            f'<line x1="{x(t["total"]):.1f}" x2="{x(t["total"]):.1f}" y1="0" y2="{H}" stroke="#16a34a" stroke-dasharray="4 3"/>',
            f'<line x1="{x(1):.1f}" x2="{x(1):.1f}" y1="0" y2="{H}" stroke="#dc2626" stroke-dasharray="2 3"/>']
    for i, r in enumerate(runs):
        y = i * bh + 4
        f, tot = r["rtp"]["fish"], r["rtp"]["total"]
        bars += [f'<text x="140" y="{y + 15}" text-anchor="end">{e(r["aim"])} · seed {r["seed"]}</text>',
                 f'<rect x="150" y="{y}" width="{x(tot) - 150:.1f}" height="{bh - 8}" fill="#f59e0b" opacity=".85"/>',
                 f'<rect x="150" y="{y}" width="{x(f) - 150:.1f}" height="{bh - 8}" fill="#2563eb"/>' if f > lo_ax else "",
                 f'<text x="{x(tot) + 6:.1f}" y="{y + 15}">{tot:.4f}</text>']
    svg = (f'<svg viewBox="0 0 {W + 60} {len(runs) * bh + 24}" role="img" aria-label="各打法總 RTP">' + "".join(bars)
           + f'<text x="{x(t["total"]):.1f}" y="{len(runs) * bh + 20}" text-anchor="middle" fill="#16a34a">目標 {t["total"]}</text>'
           + f'<text x="{x(1):.1f}" y="{len(runs) * bh + 20}" text-anchor="middle" fill="#dc2626">1.00</text></svg>')
    r0 = next((r for r in runs if r["aim"] == "random"), runs[0])

    def drop_cells(v: dict) -> str:
        if "drop_theory" not in v:
            return "<td>—</td><td>—</td><td>—</td>"
        return (f"<td>{v['drop_theory']:.1%}</td><td>{v['drop_actual']:.2%}</td>"
                f"<td class='{'ok' if v['drop_in_ci'] else 'bad'}'>±{v['drop_ci95']:.2%}</td>")

    fish_rows = "".join(
        f"<tr><td>{e(str(v['name']))}</td><td>{v['odds']}</td><td>{v['shot_share']:.1%}</td><td>{v['hit_theory']:.3%}</td>"
        f"<td>{v['hit_actual']:.3%}</td><td class='{'ok' if v['hit_in_ci'] else 'bad'}'>±{v['hit_ci95']:.3%}</td>"
        f"{drop_cells(v)}<td>{v['rtp']:.4f}</td></tr>" for v in r0["per_fish"].values())
    run_rows = "".join(
        f"<tr><td>{e(r['aim'])}</td><td>{r['seed']}</td><td>{r['shots']:,}</td><td>{r['rtp']['fish']:.6f}</td>"
        f"<td>{_fmt(r['rtp'].get(bk), '.6f')}</td><td><b>{r['rtp']['total']:.6f}</b></td><td>{_fmt(r.get('beads_per_1000'), '.2f')}</td>"
        f"<td>{_fmt(r.get('triple_rate'), '.2%')}</td><td class='{'ok' if r['within_gate'] else 'bad'}'>{'✅' if r['within_gate'] else '❌'}</td></tr>"
        for r in runs)
    f_rows = "".join(f"<tr><td>{f['id']}</td><td class='sev {f['sev']}'>{f['sev']}</td><td>{e(f['what'])}</td><td>{e(f['impact'])}</td></tr>" for f in fs)
    worst = max(runs, key=lambda r: r["rtp"]["total"])
    kpi = [("總 RTP（random 平均）", f"{g['mean']:.4f}", f"目標 {t['total']} ±{t['tolerance']}"),
           ("Gate", "通過" if g["pass"] else "不通過", f"{g['seeds']} 種子"),
           ("打魚 RTP", f"{r0['rtp']['fish']:.4f}", f"game_rate {rep['params']['game_rate']}"),
           (f"{bk} RTP", _fmt(r0["rtp"].get(bk), ".4f"), "副玩法"),
           ("最偏打法", f"{worst['rtp']['total']:.4f}", worst["aim"]),
           ("解析近似", _fmt(rep["analytic"].get("total") if isinstance(rep["analytic"], dict) else None, ".4f"), "守門用")]
    kpis = "".join(f"<div class='kpi'><div class='k'>{e(a)}</div><div class='v'>{e(b)}</div><div class='s'>{e(str(c))}</div></div>" for a, b, c in kpi)
    note = f"<div class='note'>設定檔備註：{e(rep['config']['note'])}</div>" if rep["config"]["note"] else ""
    doc = f"""<!DOCTYPE html>
<html lang="zh-TW"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(rep['title'])} ④⑤ 快測報告 {e(rep['date'])}</title>
<style>
:root{{--bg:#f8fafc;--card:#fff;--ink:#0f172a;--mute:#64748b;--line:#e2e8f0;--acc:#2563eb}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 system-ui,"Noto Sans TC",sans-serif}}
main{{max-width:1080px;margin:0 auto;padding:28px 20px 60px}}
h1{{font-size:24px;margin:0 0 4px}} h2{{font-size:18px;margin:32px 0 10px;border-left:4px solid var(--acc);padding-left:8px}}
.sub{{color:var(--mute);font-size:13px}} .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-top:18px}}
.kpi{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}}
.kpi .k{{font-size:12px;color:var(--mute)}} .kpi .v{{font-size:22px;font-weight:700}} .kpi .s{{font-size:12px;color:var(--mute)}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;overflow-x:auto}}
table{{border-collapse:collapse;width:100%;font-size:13.5px}} th,td{{padding:6px 8px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}}
th:first-child,td:first-child{{text-align:left}} th{{background:#f1f5f9;font-weight:600}}
.ok{{color:#16a34a}} .bad{{color:#dc2626;font-weight:600}} .sev{{font-weight:700;text-align:center}}
.P0,.P1{{color:#dc2626}} .P2{{color:#d97706}} .P3{{color:#64748b}}
.f td{{white-space:normal;text-align:left}} svg{{width:100%;font-size:12px}} .legend span{{display:inline-block;width:12px;height:12px;margin:0 4px 0 12px;vertical-align:-1px}}
.note{{background:#fffbeb;border:1px solid #fde68a;border-radius:8px;padding:10px 12px;font-size:13px;margin-top:14px}}
footer{{margin-top:40px;color:var(--mute);font-size:12px}}
</style></head><body><main>
<h1>🐟 {e(rep['title'])} ④⑤ 快測報告</h1>
<div class="sub">{e(rep['date'])} · 設定檔 {e(rep['config']['path'])}（sha {e(rep['config']['sha16'])}）· qt-config sha {e(rep['qt_config_sha16'])} · 只回報數值不下結論</div>
<div class="grid">{kpis}</div>
{note}
<h2>各打法總 RTP</h2>
<div class="card">{svg}<div class="legend sub"><span style="background:#2563eb"></span>打魚<span style="background:#f59e0b"></span>{e(bk)}<span style="background:#16a34a;opacity:.3"></span>目標區間<span style="background:#dc2626"></span>1.00</div></div>
<h2>Findings</h2>
<div class="card f"><table><tr><th>ID</th><th>嚴重度</th><th>現象</th><th>影響</th></tr>{f_rows}</table></div>
<h2>各打法明細</h2>
<div class="card"><table><tr><th>打法</th><th>種子</th><th>發數</th><th>打魚</th><th>{e(bk)}</th><th>總 RTP</th><th>每千發附加獎勵</th><th>三同率</th><th>在區間</th></tr>{run_rows}</table></div>
<h2>各魚種命中率／附加獎勵率 vs 理論（{e(r0['aim'])} seed {r0['seed']}）</h2>
<div class="card"><table><tr><th>魚</th><th>倍率</th><th>發數占比</th><th>命中 理論</th><th>命中 實測</th><th>95% 區間</th><th>獎勵 理論</th><th>獎勵 實測</th><th>95% 區間</th><th>單魚 RTP</th></tr>{fish_rows}</table>
<div class="sub">命中率理論＝game_rate ÷ 倍率；附加獎勵率理論＝drop_ppm ÷ 1e6。</div></div>
<h2>邊界聲明</h2>
<div class="card f"><ul><li>打法模型簡化（每幀固定發數、不看距離）；真實玩家介於 random 與最偏打法之間</li>
<li>只驗設定檔的數學；營運、錢包、活動不在範圍</li><li>拍板（倍率、打法漏洞處置）由人決定</li></ul></div>
<footer>產出：ark-game-quicktest scripts/fish/qt_fish_run.py · {e(rep['tool'])}</footer>
</main></body></html>
"""
    htm.write_text(doc, encoding="utf-8")


async def lint_and_stamp(md: Path, htm: Path, root: Path) -> str:
    """戳記 MD↔HTML 並跑 report_lint；同層沒有 ark-md-report 就略過（SKIP）。"""
    if not (MD_REPORT / "report_lint.py").exists():
        return "SKIP（找不到同層 ark-md-report）"
    try:
        if (MD_REPORT / "report_pair.py").exists():
            await sh(sys.executable, str(MD_REPORT / "report_pair.py"), "stamp", str(md), str(htm), cwd=root)
        await sh(sys.executable, str(MD_REPORT / "report_lint.py"), str(md), cwd=root)
        return "PASS"
    except QtError as ex:
        return f"FAIL {str(ex).splitlines()[-1] if str(ex) else ''}"


# ── 入口 ───────────────────────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """命令列參數。"""
    ap = argparse.ArgumentParser(description="魚機 ④⑤ 快測（ark-game-quicktest）")
    ap.add_argument("--qt-config", required=True, help="qt-config.yaml（相對 --root）")
    ap.add_argument("--root", default=".", help="路徑基準（預設目前目錄）")
    ap.add_argument("--out-dir", help="覆寫報告輸出目錄（優先於 qt-config out_dir）")
    ap.add_argument("--runs-dir", help="覆寫原始 JSON 目錄（優先於 qt-config runs_dir）")
    ap.add_argument("--shots", type=int, help="覆寫每個 run 的發數（煙霧測試）")
    ap.add_argument("--jobs", type=int, help="平行數（預設 CPU 數 −1）")
    ap.add_argument("--go", help="go 執行檔（tool 為 Go 套件目錄時）")
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--no-lint", action="store_true", help="不跑 report_pair／report_lint")
    return ap.parse_args(argv)


async def amain(argv: list[str] | None = None) -> int:
    """入口：讀設定 → 跑 → 彙整 → 寫三檔 → lint／戳記；回傳 exit code。"""
    a = parse_args(argv)
    root = Path(a.root).expanduser().resolve()
    try:
        qt = load_qt(resolve(root, a.qt_config), root)
        P = qt["_paths"]
        if a.out_dir:
            P["out_dir"] = resolve(root, a.out_dir)
        if a.runs_dir:
            P["runs_dir"] = resolve(root, a.runs_dir)
        cfg = json.loads(P["config"].read_text(encoding="utf-8"))
        for k in ("game_rate", "fish_list"):
            if qt["fields"][k] not in cfg:
                raise QtError(f"設定檔缺欄位 {qt['fields'][k]}（可在 qt-config fields 覆寫欄位名）")
        runs = [enrich(r, cfg, qt) for r in await run_all(qt, a.shots, a.go, a.jobs)]
    except (QtError, json.JSONDecodeError, KeyError, yaml.YAMLError) as ex:
        print(f"❌ {ex}", file=sys.stderr)
        return EXIT_BAD
    rep = build_report(qt, cfg, runs, a.date, root)
    fs = findings(rep)
    out = P["out_dir"]
    out.mkdir(parents=True, exist_ok=True)
    rj = out / "rtp-report.json"
    rj.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    md = out / f"{a.date}-quicktest-{qt['slug']}.md"
    htm = md.with_suffix(".html")
    write_md(rep, fs, md, [rep["qt_config"], rel(root, rj), rep["config"]["path"]])
    write_html(rep, fs, htm)
    lint = "SKIP（--no-lint）" if a.no_lint else await lint_and_stamp(md, htm, root)
    print(json.dumps({"gate": rep["gate"], "findings": [{k: f[k] for k in ("id", "sev")} for f in fs],
                      "lint": lint, "out": [rel(root, p) for p in (rj, md, htm)]},
                     ensure_ascii=False, indent=1))
    return EXIT_PASS if rep["gate"]["pass"] else EXIT_GATE


def main() -> None:
    """同步入口。"""
    sys.exit(asyncio.run(amain()))


if __name__ == "__main__":
    main()
