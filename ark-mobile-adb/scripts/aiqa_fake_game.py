"""aiqa_fake_game — 合成 slot 遊戲（dry-run / 測試用的假裝置後端）。

畫面 1600x900：lobby → main_game（5x3 盤面、HUD：bet / win / credit / multiplier）→ info_page；
spin 後 4 幀轉動再停輪；賠付 = 中排同符號 ≥3 個 × 賠率 × bet/100 × 乘倍；乘倍：有贏 +1、無贏回 1。
斷網中 spin → 顯示「網路不穩」，15 秒後 6002 彈窗，按 OK 回 lobby。restart_app → 回 lobby（recover 到 main_game）。
bugs：{"payout_off_by": 10, "glitch": True, "multiplier_stuck": True, "uncertain_visual": True, "no_6002": True}
"""
from __future__ import annotations

import random

W, H = 1600, 900
SYMBOLS = ["S01", "S02", "S03", "S04", "S05", "S06"]
PAYTABLE = {"S01": {3: 50, 4: 100, 5: 300}, "S02": {3: 40, 4: 80, 5: 200}, "S03": {3: 30, 4: 60, 5: 150},
            "S04": {3: 20, 4: 40, 5: 100}, "S05": {3: 10, 4: 20, 5: 60}, "S06": {3: 5, 4: 10, 5: 30}}
COLORS = {"S01": (220, 60, 60), "S02": (60, 160, 220), "S03": (60, 200, 90), "S04": (230, 190, 60), "S05": (170, 90, 220), "S06": (200, 200, 200)}
LAYOUT = {
    "tile_demo": (650, 350, 300, 200),      # lobby 機台
    "spin": (1380, 740, 160, 90),
    "info": (40, 790, 90, 60),
    "close": (1490, 30, 70, 50),
    "ok": (720, 560, 160, 60),              # 6002 彈窗
    "roi_bet": (200, 830, 200, 50), "roi_win": (700, 830, 260, 50), "roi_credit": (1200, 830, 300, 50),
    "roi_multiplier": (740, 30, 140, 50), "roi_board": (300, 120, 1000, 600), "roi_info_paytable": (300, 150, 1000, 500),
    "roi_popup": (560, 380, 480, 260),
}


class FakeGame:
    def __init__(self, seed: int = 7, bugs: dict | None = None):
        self.rng = random.Random(seed)
        self.bugs = bugs or {}
        self.t = 0.0
        self.screen = "lobby"
        self.bet, self.credit, self.win, self.mult = 100, 20000, 0, 1
        self.reels = [[self.rng.choice(SYMBOLS) for _ in range(3)] for _ in range(5)]
        self.spinning_frames = 0
        self.net = True
        self.net_lost_at = None
        self.popup = None
        self.log: list[str] = []
        self.foreground = True
        self.last_highlight: list[str] = []

    # ------------------------------------------------------------ 時間與狀態
    def tick(self, dt: float = 0.5):
        self.t += dt
        if self.spinning_frames > 0:
            self.spinning_frames -= 1
            if self.spinning_frames == 0:
                if not self.net:
                    self.spinning_frames = 1  # 轉不停
                else:
                    self._settle()
        if not self.net and self.net_lost_at is not None and self.screen == "main_game" and self.popup is None:
            if self.t - self.net_lost_at >= 15 and not self.bugs.get("no_6002"):
                self.popup = "6002"

    def _settle(self):
        self.reels = [[self.rng.choice(SYMBOLS) for _ in range(3)] for _ in range(5)]
        if self.rng.random() < 0.45:  # 提高中獎率方便測試
            sym = self.rng.choice(SYMBOLS); n = self.rng.choice([3, 3, 4, 5])
            for c in range(n):
                self.reels[c][1] = sym
        row = [self.reels[c][1] for c in range(5)]
        sym = row[0]; n = 1
        while n < 5 and row[n] == sym:
            n += 1
        pay = PAYTABLE[sym].get(n, 0) if n >= 3 else 0
        win = pay * self.bet // 100 * self.mult
        if pay and self.bugs.get("payout_off_by"):
            win += int(self.bugs["payout_off_by"])
        self.win = win
        self.credit += win
        self.last_highlight = [sym] * n if pay else []
        if not self.bugs.get("multiplier_stuck"):
            self.mult = self.mult + 1 if win > 0 else 1
        self.log.append(f"settle t={self.t} win={win} mult={self.mult}")

    # ------------------------------------------------------------ 輸入
    def tap(self, x: int, y: int):
        def hit(name):
            bx, by, bw, bh = LAYOUT[name]
            return bx <= x <= bx + bw and by <= y <= by + bh
        if self.popup == "6002":
            if hit("ok"):
                self.popup = None; self.screen = "lobby"; self.spinning_frames = 0
            return
        if self.screen == "lobby" and hit("tile_demo"):
            self.screen = "main_game"
        elif self.screen == "main_game":
            if hit("spin") and self.spinning_frames == 0 and self.credit >= self.bet:
                self.credit -= self.bet; self.win = 0; self.spinning_frames = 4; self.last_highlight = []
            elif hit("info"):
                self.screen = "info_page"
        elif self.screen == "info_page" and hit("close"):
            self.screen = "main_game"

    def key(self, name: str):
        if name == "BACK":
            if self.screen in ("info_page", "main_game"):
                self.screen = "lobby" if self.screen == "main_game" else "main_game"

    def restart_app(self):
        self.log.append("restart")
        self.spinning_frames = 0; self.popup = None
        self.screen = "lobby"  # 重登後回 lobby；recover 由玩家重新進入

    def set_net(self, on: bool):
        self.net = on
        self.net_lost_at = None if on else self.t

    # ------------------------------------------------------------ 讀值（fake reader 的 ground truth）
    def truth(self, roi: str):
        return {"bet": self.bet, "win": self.win, "credit": self.credit, "multiplier": self.mult,
                "board": [[s for s in col] for col in self.reels], "highlight": list(self.last_highlight),
                "info_paytable": [{"symbol": s, "count": c, "pay": p} for s, t in PAYTABLE.items() for c, p in t.items()],
                "popup": self.popup, "screen": self.screen, "spinning": self.spinning_frames > 0}.get(roi)

    def visual(self, question: str) -> dict:
        q = question.lower()
        conf = 0.5 if self.bugs.get("uncertain_visual") else 0.95
        if "破圖" in q or "glitch" in q or "錯位" in q:
            return {"answer": bool(self.bugs.get("glitch")), "confidence": conf, "detail": "fake visual: glitch flag"}
        if "亮框" in q or "highlight" in q:
            return {"answer": bool(self.last_highlight), "confidence": conf, "detail": "fake visual: highlight"}
        if "網路" in q or "network" in q:
            return {"answer": (not self.net) and self.spinning_frames > 0, "confidence": conf, "detail": "fake visual: net icon"}
        return {"answer": None, "confidence": 0.3, "detail": "fake visual: unknown question"}

    # ------------------------------------------------------------ 渲染
    def render(self, path):
        from PIL import Image, ImageDraw
        im = Image.new("RGB", (W, H), (18, 22, 40) if self.screen != "info_page" else (30, 30, 30))
        d = ImageDraw.Draw(im)
        def box(name, fill, label=None):
            x, y, w, h = LAYOUT[name]; d.rectangle([x, y, x + w, y + h], fill=fill, outline=(255, 255, 255))
            if label:
                d.text((x + 8, y + 8), label, fill=(0, 0, 0))
        if self.screen == "lobby":
            d.text((60, 40), "LOBBY", fill=(255, 220, 120))
            box("tile_demo", (200, 160, 60), "DEMO SLOT")
        elif self.screen == "info_page":
            d.text((60, 40), "INFO  PAYTABLE", fill=(255, 220, 120))
            box("close", (200, 80, 80), "X")
            y = 160
            for s, t in PAYTABLE.items():
                d.rectangle([320, y, 360, y + 30], fill=COLORS[s]); d.text((380, y + 8), f"{s}  x3={t[3]}  x4={t[4]}  x5={t[5]}", fill=(255, 255, 255)); y += 60
        else:
            d.text((60, 40), "DEMO SLOT", fill=(255, 220, 120))
            for c in range(5):
                for r in range(3):
                    x, y = 300 + c * 200, 120 + r * 200
                    if self.spinning_frames > 0:
                        d.rectangle([x, y, x + 180, y + 180], fill=tuple(self.rng.randint(0, 255) for _ in range(3)))
                    else:
                        sym = self.reels[c][r]; d.rectangle([x, y, x + 180, y + 180], fill=COLORS[sym]); d.text((x + 70, y + 80), sym, fill=(0, 0, 0))
                        if r == 1 and self.last_highlight and c < len(self.last_highlight):
                            d.rectangle([x - 4, y - 4, x + 184, y + 184], outline=(255, 255, 0), width=6)
            if self.bugs.get("glitch") and self.spinning_frames == 0:
                d.rectangle([300, 120, 390, 210], fill=(255, 0, 255))  # 破圖
            box("spin", (60, 180, 90), "SPIN"); box("info", (90, 90, 200), "i")
            for name, val in (("roi_bet", f"BET {self.bet}"), ("roi_win", f"WIN {self.win}"), ("roi_credit", f"CREDIT {self.credit}"), ("roi_multiplier", f"x{self.mult}")):
                x, y, w, h = LAYOUT[name]; d.rectangle([x, y, x + w, y + h], fill=(0, 0, 0)); d.text((x + 10, y + 16), val, fill=(255, 255, 0))
            if not self.net and self.spinning_frames > 0:
                d.ellipse([760, 380, 840, 460], outline=(255, 80, 80), width=6); d.text((770, 470), "NETWORK", fill=(255, 80, 80))
            if self.popup == "6002":
                x, y, w, h = LAYOUT["roi_popup"]; d.rectangle([x, y, x + w, y + h], fill=(240, 240, 240)); d.text((x + 40, y + 40), "ERROR 6002", fill=(200, 0, 0)); box("ok", (80, 160, 80), "OK")
        im.save(path)
        return path
