"""假 fishsim（測試用）：照 fish-quicktest-contract 吐固定 JSON，不跑 Go。

總 RTP 取設定檔 `_fake.total[aim]`（可再加 `_fake.seed_step × seed`）；
命中數照理論命中率產生，`_fake.hit_skew` 可讓命中率故意偏離理論。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ap = argparse.ArgumentParser()
for k in ("config", "aim"):
    ap.add_argument(f"-{k}")
for k in ("shots", "seed", "per", "bet"):
    ap.add_argument(f"-{k}", type=int)
a, rest = ap.parse_known_args()  # 契約 v2：其餘旗標（-seats 4 -skill cycle…）原樣回吐
flags = dict(zip(rest[0::2], rest[1::2]))
cfg = json.loads(Path(a.config).read_text(encoding="utf-8"))
fake = cfg["_fake"]
total = fake["total"][a.aim] + fake.get("seed_step", 0) * a.seed + fake.get("seats_step", 0) * int(flags.get("-seats", 0))
skew = fake.get("hit_skew", 0.0)
fish = cfg["fish_info"]
per = a.shots // len(fish)
per_fish = {}
for f in fish:
    p = cfg["game_rate"] / f["odds"] * (1 + skew)
    kills = round(per * p)
    beads = round(kills * f["drop_ppm"] / 1e6)
    per_fish[str(f["type"])] = {"name": f["name"], "shots": per, "kills": kills, "beads": beads,
                                "rtp": round(kills * f["odds"] / per, 6)}
out = {"aim": a.aim, "seed": a.seed, "shots": per * len(fish), "bet": a.bet,
       "rtp": {"fish": round(total - 0.15, 6), "bead": 0.15, "total": round(total, 6)},
       "per_fish": per_fish, "analytic": {"fish": 0.8, "bead": 0.16, "total": 0.96},
       "beads_per_1000": 13.0, "triple_rate": 0.12, "echo_flags": flags}
if fake.get("no_per_fish"):
    del out["per_fish"]
print(json.dumps(out, ensure_ascii=False))
