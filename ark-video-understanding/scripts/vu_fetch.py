#!/usr/bin/env python3
"""vu_fetch — 取得影片、建立 run 目錄與 manifest。

用法:
  python vu_fetch.py --source https://youtube.com/watch?v=... --out artifacts/cva [--domain slot-game|auto]
  python vu_fetch.py --source ./videos/x.mp4 --out artifacts/cva --domain fish-game
run_id = YYYYMMDD-<domain|auto>-<sha256[:8]>-<seq>；同一影片重跑會建立新 seq，但 video/ 以 sha256 快取。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import os
import pathlib
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vu_common as C  # noqa: E402


def download(url: str, dst_dir: pathlib.Path, timeout: int) -> pathlib.Path:
    C.which("yt-dlp")
    dst_dir.mkdir(parents=True, exist_ok=True)
    cmd = ["yt-dlp", "-f", "bv*[height<=1080]+ba/b[height<=1080]/b", "--merge-output-format", "mp4",
           "--write-subs", "--write-auto-subs", "--sub-format", "vtt", "--sub-langs", "zh.*,en.*,ja.*",
           "--no-playlist", "-o", str(dst_dir / "source.%(ext)s"), url]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        C.fail("TIMEOUT", f"yt-dlp 超過 {timeout}s", "改用本地 MP4 或提高 --timeout")
    if r.returncode != 0:
        C.fail("CONN_FAILED", f"yt-dlp 失敗: {r.stderr.strip().splitlines()[-1][:200] if r.stderr.strip() else 'unknown'}",
               "私人/地區限制影片請人工錄製後以 --source <path> 重跑")
    vids = sorted(dst_dir.glob("source.mp4")) or sorted(p for p in dst_dir.glob("source.*") if p.suffix not in (".vtt", ".srt"))
    if not vids:
        C.fail("CONN_FAILED", "yt-dlp 沒有產出影片檔", "")
    return vids[0]


def main() -> None:
    ap = argparse.ArgumentParser(description="fetch video and create run")
    ap.add_argument("--source", required=True)
    ap.add_argument("--out", default="artifacts/cva")
    ap.add_argument("--domain", default="auto", help="已註冊 pack 名或 auto（之後由 ga_detect 判定）")
    ap.add_argument("--timeout", type=int, default=int(os.getenv("ARK_VU_FETCH_TIMEOUT_S", "600")))
    a = ap.parse_args()

    if a.domain != "auto" and a.domain not in C.list_domains():
        C.fail("BAD_INPUT", f"未知 domain {a.domain!r}", f"可用: {C.list_domains()} 或 auto")

    out_root = pathlib.Path(a.out)
    out_root.mkdir(parents=True, exist_ok=True)
    with C.Timer() as t:
        is_url = a.source.startswith(("http://", "https://"))
        if is_url:
            tmp = out_root / ".fetch_tmp" / str(abs(hash(a.source)))
            src = download(a.source, tmp, a.timeout)
        else:
            src = pathlib.Path(a.source)
            if not src.is_file():
                C.fail("BAD_INPUT", f"檔案不存在: {src}", "")
        sha = C.sha256_file(src)
        day = _dt.date.today().strftime("%Y%m%d")
        base = f"{day}-{a.domain}-{sha[:8]}"
        seq = 1 + len([p for p in out_root.iterdir() if p.is_dir() and p.name.startswith(base)])
        run = out_root / f"{base}-{seq:02d}"
        (run / "video").mkdir(parents=True)
        dst = run / "video" / f"source{src.suffix.lower() or '.mp4'}"
        if is_url:
            shutil.move(str(src), dst)
            for sub in src.parent.glob("*.vtt"):
                (run / "transcript").mkdir(exist_ok=True)
                shutil.move(str(sub), run / "transcript" / sub.name)
            shutil.rmtree(src.parent, ignore_errors=True)
        else:
            shutil.copy2(src, dst)
        meta = C.ffprobe(dst)
    m = {"run_id": run.name, "contract": C.CONTRACT, "created_at": _dt.datetime.now().isoformat(timespec="seconds"),
         "source": a.source, "video": {"file": f"video/{dst.name}", "sha256": sha, **meta},
         "domain": None if a.domain == "auto" else a.domain, "domain_source": "cli" if a.domain != "auto" else "pending",
         "skill_versions": {"ark-video-understanding": C.SKILL_VERSION}, "stages": {}, "budget_used": {}}
    C.save_manifest(run, m)
    C.atomic_write(run / "video" / "meta.json", __import__("json").dumps(meta, indent=1))
    if a.domain != "auto":
        C.snapshot_pack(run, a.domain)
    C.stage_record(run, "fetch", t.elapsed_ms)
    C.emit({"run": str(run), "run_id": run.name, "video": m["video"], "domain": m["domain"]},
           {"stage": "fetch", "elapsed_ms": t.elapsed_ms})


if __name__ == "__main__":
    main()
