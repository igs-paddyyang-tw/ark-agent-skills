"""產生端到端測試用的合成資料集（數字皆虛構）。

用法：python make_fixture.py <data_dir> [--days 30] [--no-win]
"""
from __future__ import annotations

import csv
import datetime as dt
import math
import pathlib
import random
import sys

LAUNCH = dt.date(2026, 10, 1)
VIEWS = {"全體": lambda u: True, "CN": lambda u: u["market"] == "CN", "非CN": lambda u: u["market"] != "CN"}


def users(n, seed):
    r = random.Random(seed)
    return [{"uid": f"u{seed}_{i}", "vip": min(9, int(r.expovariate(0.45))), "market": r.choice(["CN", "CN", "JP", "TW", "VN"]),
             "reg_days": int(r.expovariate(1 / 200))} for i in range(n)]


def write(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def game(dd: pathlib.Path, days: int, seed: int, n_users: int, win=True, triggers=True, heat=1.0):
    r = random.Random(seed)
    us = users(n_users, seed)
    gud, active = [], {}
    for i in range(days):
        d = LAUNCH + dt.timedelta(days=i)
        p_new = 0.09 * math.exp(-i / 5) * heat + 0.004
        for u in us:
            uid = u["uid"]
            if uid in active:
                age = (d - active[uid]).days
                play = r.random() < 0.42 * (age + 1) ** -0.35
            else:
                play = r.random() < p_new
                if play:
                    active[uid] = d
            if not play:
                continue
            spins = int(r.lognormvariate(4.6 + u["vip"] * 0.08, 0.9)) + 1
            bet_per = 100 * (1.6 ** u["vip"])
            bet = spins * bet_per
            row = [d.isoformat(), uid, round(bet, 2), spins]
            if win:
                row.append(round(bet * (0.965 + r.gauss(0, 12 / math.sqrt(spins))), 2))
            if triggers:
                row += [sum(1 for _ in range(spins) if r.random() < 1 / 180), sum(1 for _ in range(spins) if r.random() < 1 / 95)]
            row += [u["vip"], u["market"], u["reg_days"]]
            gud.append(row)
    head = ["d", "uid", "bet", "spins"] + (["win"] if win else []) + (["trig_Free Game", "trig_Hold & Spin"] if triggers else []) + ["vip", "market", "reg_days"]
    write(dd / "game_user_daily.csv", head, gud)
    # slot_daily：全虎機（合成：本機約佔 3%～9%）
    sd = []
    for vn, f in VIEWS.items():
        for i in range(days):
            d = (LAUNCH + dt.timedelta(days=i)).isoformat()
            rows = [x for x in gud if x[0] == d and f({"market": x[-2]})]
            gb = sum(x[2] for x in rows)
            share = 0.028 + 0.055 * math.exp(-i / 6) * heat
            sd.append([vn, d, round(gb / share, 2) if gb else 1e9, int(len(rows) / (0.18 + r.random() * 0.05)) or 1000, 3 + i // 6])
    write(dd / "slot_daily.csv", ["view", "d", "slot_bet", "slot_players", "game_rank"], sd)
    pool = users(n_users * 4, seed + 1000) + us
    write(dd / "slot_users.csv", ["uid", "vip", "market", "reg_days"], [[u["uid"], max(0, u["vip"] - (1 if r.random() < 0.3 else 0)), u["market"], u["reg_days"]] for u in pool])
    return gud


def main():
    dd = pathlib.Path(sys.argv[1])
    days = int(sys.argv[sys.argv.index("--days") + 1]) if "--days" in sys.argv else 30
    win = "--no-win" not in sys.argv
    game(dd, days, 7, 2500, win=win)
    write(dd / "erosion.csv", ["game", "pre_bet", "post_bet"],
          [["__TARGET__", 0, 9.0e9], ["Slot_101", 6.0e9, 2.4e9], ["Slot_102", 3.0e9, 1.9e9], ["Slot_103", 2.0e9, 2.2e9], ["__ALL_SLOTS__", 4.0e11, 4.05e11]])
    write(dd / "hours.csv", ["bucket", "bet"], [["0–6 時", 14], ["6–12 時", 21], ["12–18 時", 29], ["18–24 時", 36]])
    for k, heat in enumerate([0.7, 0.9, 1.0, 1.1, 1.3]):
        game(dd / "bench" / f"bench{k}", days, 100 + k, 1200, win=False, triggers=False, heat=heat)
    print(dd)


if __name__ == "__main__":
    main()
