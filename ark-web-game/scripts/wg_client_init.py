#!/usr/bin/env python3
"""wg_client_init — 由 Client 範本產正式網頁遊戲 Client monorepo（ark-web-game 計畫 P5 任務 5.1），或由參考 Client 更新範本。

範本 = 參考 Client（首例 pixi-game-platform／games/huffnpuff）中「遊戲無關」的部分：
  根目錄（pnpm workspace、tsconfig、schemas、schema 同步檢查）、
  packages/shared-types（契約型別）、packages/ark-wire（wire 編解碼＋ArkConn＋mock Server）、packages/game-service（Ws／Http／Replay／Recorder）、
  games/<game> 的 runtime（Boot、Clock、Tween、Emitter）、GameController（一局流程＋present-events）、轉輪、通用 Presenter、進入點。
  遊戲專屬（game.config.ts、presenters/index.ts、專屬 Presenter、e2e）由範本給起始版，再依遊戲改。

用法:
  # 產 monorepo（新 repo）或在既有 monorepo 加一款遊戲
  python wg_client_init.py --out <資料夾> --game <遊戲資料夾名> --key <game key> --name "<顯示名>" [--add-game] [--force]
  # 由參考 Client 更新範本（P5 後、參考 Client 改了共用部分後執行）
  python wg_client_init.py --sync-template --from <pixi-game-platform 根> [--ref-game huffnpuff]

exit：0 成功；1 目的地已存在（未加 --force）；2 輸入錯誤。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import shutil
import sys

SKILL = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE = SKILL / "assets" / "client-template"
GAME_DIR = "games/__GAME__"

# 範本收錄（相對參考 Client 根）；目錄整個收（排除 node_modules、dist、reports）
ROOT_FILES = [".gitignore", "tsconfig.base.json", "tools/schema-sync-check.mjs", "schemas"]
PACKAGES = ["packages/shared-types", "packages/ark-wire", "packages/game-service"]
# 參考遊戲中遊戲無關的檔案（相對 games/<ref>）
GAME_FILES = [
    "tsconfig.json", "vite.config.ts",
    "src/main.ts", "src/runtime", "src/game/controller.ts", "src/game/present-events.ts",
    "src/scenes/ui.ts", "src/scenes/reels.ts", "src/scenes/main.ts", "src/scenes/art.ts", "src/presenters/generic.ts",
    "test/runtime.test.ts", "test/controller.test.ts", "test/assets.test.ts", "test/fixtures/trace.json",
    "e2e/e2e.mjs",
]
SKIP_DIRS = {"node_modules", "dist", "reports", "__pycache__", ".vite"}

# 範本自帶（遊戲專屬起始版；sync 不覆蓋）
OWN = {
    "package.json.tmpl": """{
  "name": "__REPO__",
  "private": true,
  "version": "0.1.0",
  "description": "正式網頁遊戲 Client（PixiJS 8＋TypeScript＋Vite；由 ark-web-game wg_client_init 產生）",
  "packageManager": "pnpm@10.28.0",
  "scripts": {
    "build": "pnpm -r build",
    "test": "pnpm -r test",
    "typecheck": "pnpm -r typecheck",
    "gen:types": "pnpm --filter @pgp/shared-types gen",
    "schema:sync-check": "node tools/schema-sync-check.mjs"
  },
  "devDependencies": { "typescript": "5.9.3", "vite": "6.4.5", "vitest": "3.2.7", "@types/node": "22.20.5" },
  "pnpm": { "onlyBuiltDependencies": ["esbuild"] }
}
""",
    "pnpm-workspace.yaml": "packages:\n  - packages/*\n  - games/*\n",
    f"{GAME_DIR}/package.json.tmpl": """{
  "name": "__GAME__",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -p . --noEmit && vite build",
    "typecheck": "tsc -p . --noEmit",
    "test": "vitest run",
    "e2e": "node e2e/e2e.mjs"
  },
  "dependencies": { "@pgp/game-service": "workspace:*", "@pgp/shared-types": "workspace:*", "pixi.js": "8.6.6" },
  "devDependencies": { "@types/node": "22.20.5", "typescript": "5.9.3", "vite": "6.4.5", "vitest": "3.2.7" }
}
""",
    f"{GAME_DIR}/index.html.tmpl": """<!doctype html>
<html lang="zh-TW">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <title>__NAME__</title>
  <style>
    html, body { margin: 0; height: 100%; background: #10131c; color: #eef; font-family: system-ui, "Noto Sans TC", sans-serif; overflow: hidden; }
    #app { position: fixed; inset: 0; }
    #boot { position: fixed; inset: 0; display: grid; place-items: center; pointer-events: none; font-size: 15px; }
    #boot[data-state="playable"] { display: none; }
    #boot[data-state="error"] { color: #ff8a80; pointer-events: auto; }
  </style>
</head>
<body>
  <div id="app"></div>
  <div id="boot" data-state="idle">載入中…</div>
  <script type="module" src="/src/main.ts"></script>
</body>
</html>
""",
    f"{GAME_DIR}/src/game.config.ts.tmpl": """// __NAME__ 遊戲設定（演出層；數值只來自 Server 的 GameInfo／SpinResult，這裡不放機率）
export const GAME = {
  key: '__KEY__',
  name: __NAME_JSON__,
  design: { w: 720, h: 1280 },
  reels: { cols: 5, rows: 3, cellW: 126, cellH: 126, gap: 8, x: 36, y: 300 },
  timing: { spinMin: 0.55, reelGap: 0.14, land: 0.18, winShow: 0.6, countUp: 0.5, featureStep: 0.45, featureIntro: 0.8 },
  /** 符號：顯示名＋佔位色（未列的符號用名稱與雜湊色；正式美術到位前） */
  symbols: {} as Record<string, [string, number]>,
  /** 聽牌：這些符號在前面各軸累計 ≥ need 時，後面各軸延長 sec 秒（只在 base.trigger 局） */
  tease: { symbols: [], need: 2, sec: 0.6 } as { symbols: string[]; need: number; sec: number },
  /** 贏分等級門檻（倍數）→ 大獎演出 */
  winTiers: [[15, 'BIG'], [40, 'MEGA'], [100, 'SUPER']] as [number, string][],
  /** 素材清單：'none' = 佔位模式（還沒打包素材時）；打包後改 './assets/manifest.json'（wg_pack_assets，見 assets.yaml） */
  assets: 'none',
  /** 玩法要用的素材別名（抽到玩法時先確保所在 bundle） */
  featureArt: [] as string[],
};
export type GameConfig = typeof GAME;
""",
    f"{GAME_DIR}/src/presenters/index.ts": """// 玩法 Presenter 對照：依 feature.script 選 Presenter（遊戲專屬；沒對到用通用版）
//   新增專屬 Presenter：寫 presenters/<玩法>.ts（只讀 feature.script，不重算），在這裡依 script.type 對應
import type { SpinResult } from '@pgp/shared-types';
import { playGeneric, type Presenter } from './generic.js';

export function pickPresenter(_r: SpinResult): Presenter {
  return playGeneric;
}
""",
    f"{GAME_DIR}/e2e/e2e.config.json.tmpl": """{
  "schema": "pgp-e2e-config/1",
  "game": "__GAME__",
  "arkIdPrefix": "e2e-__KEY__",
  "serverDir": "data/slot/<slug>/game/go-server",
  "serverArgs": ["-dev", "-seed", "7", "-flood-limit", "100000", "-balance", "50000000", "-ws-max-inline", "2000"],
  "scenes": [{ "scene": "feature" }],
  "expectChunked": false,
  "stage": { "game": "data/slot/<slug>/game/pixi-client/game.js" }
}
""",
    f"{GAME_DIR}/assets.yaml.tmpl": """# __NAME__ 素材設定（ark-web-game wg_pack_assets；格式 pgp-assets/1）
#   python <aidev>/.kiro/skills/ark-web-game/scripts/wg_pack_assets.py --config games/__GAME__/assets.yaml --out <output 資料夾> [--set 來源=資料夾]
#   打包後：game.config.ts 的 assets 改 './assets/manifest.json'，建置時 PGP_ASSETS_DIR=<output 資料夾>
#   畫面認得的別名：bg_main、logo、reel_frame、reel_bg、ui_panel、ui_spin、ui_auto、ui_plus、ui_minus、sym_<符號代號>、win_big／mega／super；音效 sfx_spin、sfx_stop、sfx_prewin、sfx_alarm、sfx_board_start、sfx_board_end、sfx_fast_on、sfx_fast_off、sfx_info
schema: pgp-assets/1
game_key: __KEY__
version: 0.1.0
sources:
  art: { dir: art }                     # 圖檔資料夾（svg／png／webp）；原創美術或美術組交件
  # sfx: { env: GAME_SFX_DIR }          # 音效資料夾（原檔不進 repo）
image: { format: webp, quality: 86 }
audio: { formats: [ogg, m4a] }
bundles:
  __KEY__-core:
    required: true
    images: {}
""",
    "README.md.tmpl": """# __REPO__

由 ark-web-game `wg_client_init.py` 產生（範本來源見 `.wg-client.json`）。

```bash
pnpm install
pnpm -r typecheck && pnpm -r test && pnpm -r build
pnpm --filter __GAME__ dev        # ?service=ws&url=ws://127.0.0.1:8787/ws&dev  連 Go Server（-dev）
```

| 位置 | 內容 |
|---|---|
| `packages/shared-types` | 契約型別（由 `schemas/` 產生；`pnpm schema:sync-check`） |
| `packages/ark-wire` | ark-go wire 編解碼、ArkConn、`test/mock-ark.mjs`（測試用 Server） |
| `packages/game-service` | GameService：WsService、HttpService、ReplayService、Recorder |
| `games/__GAME__` | 遊戲：runtime（Boot／Clock／Tween）、GameController（present-events/1）、轉輪、Presenter |

下一步（ark-web-game references/client-vertical-slice.md）：
1. `src/game.config.ts` 填符號與聽牌規則；
2. 依 `feature.script` 寫專屬 Presenter，登記到 `src/presenters/index.ts`；
3. 填 `e2e/e2e.config.json`（Go Server 路徑、強制情境、Stage 遊戲包），建置後 `pnpm --filter __GAME__ e2e --aidev <aidev 根>`（含 trace-parity）。
""",
}


def die(msg: str, code: int = 2) -> None:
    print(json.dumps({"ok": False, "fatal": msg}, ensure_ascii=False))
    sys.exit(code)


def copy_tree(src: pathlib.Path, dst: pathlib.Path) -> int:
    n = 0
    if src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return 1
    for p in sorted(src.rglob("*")):
        rel = p.relative_to(src)
        if any(part in SKIP_DIRS for part in rel.parts) or not p.is_file():
            continue
        q = dst / rel
        q.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, q)
        n += 1
    return n


def sync_template(src: pathlib.Path, ref_game: str) -> dict:
    if not (src / "pnpm-workspace.yaml").is_file():
        die(f"{src} 不是 pnpm monorepo（缺 pnpm-workspace.yaml）")
    gsrc = src / "games" / ref_game
    if not gsrc.is_dir():
        die(f"找不到參考遊戲 {gsrc}")
    if TEMPLATE.exists():
        shutil.rmtree(TEMPLATE)
    TEMPLATE.mkdir(parents=True)
    n = 0
    for rel in ROOT_FILES + PACKAGES:
        if not (src / rel).exists():
            die(f"參考 Client 缺 {rel}")
        n += copy_tree(src / rel, TEMPLATE / rel)
    for rel in GAME_FILES:
        if not (gsrc / rel).exists():
            die(f"參考遊戲缺 {rel}")
        n += copy_tree(gsrc / rel, TEMPLATE / GAME_DIR / rel)
    for rel, body in OWN.items():
        p = TEMPLATE / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
        n += 1
    meta = {"from": str(src.name), "refGame": ref_game, "synced": dt.date.today().isoformat(), "files": n,
            "note": "由 wg_client_init.py --sync-template 產生，勿手改（遊戲專屬起始版寫在 wg_client_init.py OWN）"}
    (TEMPLATE / "TEMPLATE.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"ok": True, "template": str(TEMPLATE), **meta}


def render(text: str, v: dict) -> str:
    for k, val in v.items():
        text = text.replace(k, val)
    return text


def scaffold(out: pathlib.Path, game: str, key: str, name: str, add_game: bool, force: bool) -> dict:
    if not (TEMPLATE / "TEMPLATE.json").is_file():
        die("範本不存在：先跑 --sync-template")
    if not re.fullmatch(r"[a-z][a-z0-9-]{1,40}", game):
        die("--game 只能小寫英數與 -（npm 套件名）")
    gdir = out / "games" / game
    if add_game:
        if not (out / "pnpm-workspace.yaml").is_file():
            die(f"--add-game 需要既有 monorepo：{out}")
        if gdir.exists() and not force:
            die(f"{gdir} 已存在（加 --force 覆寫）", 1)
    elif out.exists() and any(out.iterdir()) and not force:
        die(f"{out} 已存在且非空（加 --force 覆寫）", 1)
    v = {"__GAME__": game, "__KEY__": key, "__NAME_JSON__": json.dumps(name, ensure_ascii=False), "__NAME__": name, "__REPO__": out.name}
    written = []
    for p in sorted(TEMPLATE.rglob("*")):
        if not p.is_file() or p.name == "TEMPLATE.json":
            continue
        rel = p.relative_to(TEMPLATE).as_posix()
        if add_game and not rel.startswith(GAME_DIR + "/"):
            continue
        rel = render(rel, {"__GAME__": game})
        if rel.endswith(".tmpl"):
            rel = rel[:-5]
            body = render(p.read_text(encoding="utf-8"), v)
            q = out / rel
            q.parent.mkdir(parents=True, exist_ok=True)
            q.write_text(body, encoding="utf-8")
        else:
            q = out / rel
            q.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, q)
        written.append(rel)
    meta = json.loads((TEMPLATE / "TEMPLATE.json").read_text(encoding="utf-8"))
    (gdir / ".wg-client.json").write_text(json.dumps({"game": game, "key": key, "name": name, "template": meta, "created": dt.date.today().isoformat()}, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"ok": True, "out": str(out), "game": game, "files": len(written) + 1,
            "next": ["pnpm install", "pnpm -r typecheck && pnpm -r test && pnpm -r build", f"編輯 games/{game}/src/game.config.ts 與 presenters/index.ts"]}


def main() -> None:
    ap = argparse.ArgumentParser(description="正式 Client 骨架產生／範本同步")
    ap.add_argument("--sync-template", action="store_true")
    ap.add_argument("--from", dest="src")
    ap.add_argument("--ref-game", default="huffnpuff")
    ap.add_argument("--out")
    ap.add_argument("--game")
    ap.add_argument("--key")
    ap.add_argument("--name")
    ap.add_argument("--add-game", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if a.sync_template:
        if not a.src:
            die("--sync-template 需要 --from <參考 Client 根>")
        res = sync_template(pathlib.Path(a.src).resolve(), a.ref_game)
    else:
        if not (a.out and a.game):
            die("需要 --out 與 --game（或 --sync-template）")
        res = scaffold(pathlib.Path(a.out).resolve(), a.game, a.key or a.game, a.name or a.game, a.add_game, a.force)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
