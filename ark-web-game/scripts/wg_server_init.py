#!/usr/bin/env python3
"""wg_server_init — 由 Server 範本產 Go Server 骨架（⑧ 抽離第 2 步），或由參考 Server 更新範本。

範本 = 參考 Server（首例 huffnpuff go-server）中「遊戲無關」的部分：
  ark-go 網路層複本、api（HTTP／WS）、round（局服務、冪等、續玩、協定協商）、result（SpinResult 信封）、
  prob（機率模組介面與註冊表）、cmd/server、tools/vendorsync。遊戲自己的機率模組另外產一個待移植的骨架。

用法:
  # 產骨架（預設輸出 data/slot/<slug>/game/go-server）
  python wg_server_init.py --slug <slug> --engine <引擎名> [--module aidev/slot/<slug>/go-server] [--out <資料夾>] [--force]
  # 由參考 Server 更新範本（P3 後、ark-go 同步後執行）
  python wg_server_init.py --sync-template --from data/slot/huffnpuff-open-house/game/go-server

exit：0 成功；1 目的地已存在（未加 --force）；2 輸入錯誤。
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import shutil
import sys

SKILL = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE = SKILL / "assets" / "go-server-template"
REF_MODULE_RE = re.compile(r"^module\s+(\S+)", re.M)

# 範本收錄的路徑（相對參考 Server）；*_test.go 只收 ark-go 自帶的（其餘測試依賴具體遊戲）
INCLUDE = [
    "go.mod", "go.sum", ".gitignore", "build.sh", "build.ps1",
    "cmd/server/main.go",
    "internal/ark-go", "internal/api/http.go", "internal/api/ws.go",
    "internal/round/service.go", "internal/round/store.go", "internal/round/devwallet.go",
    "internal/result/result.go", "internal/prob/prob.go", "internal/prob/rng.go",
    "tools/vendorsync", "tools/smoke_ws.js",
]

# 容器（0.9.0，神燈寶藏起）：odds 放 configs/，不用額外 build context；新遊戲產骨架時寫入
DOCKERFILE = """# {slug} Go Game Server 映像（ark-web-game Server 範本）
#   build context = go-server；odds 放 configs/odds.json（產生方式見 README／交付單）
#   映像內含 odds：線上機率等級參數時只放本機或公司內部 registry，不推外部（R-3）
ARG GO_IMAGE=golang:1.22-alpine
ARG RUNTIME_IMAGE=alpine:3.20

FROM ${{GO_IMAGE}} AS build
ARG GOPROXY=https://proxy.golang.org,direct
ENV GOPROXY=${{GOPROXY}} CGO_ENABLED=0
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN go build -trimpath -ldflags="-s -w" -o /out/game-server ./cmd/server

FROM ${{RUNTIME_IMAGE}}
RUN adduser -D -u 10001 app
COPY --from=build /out/game-server /app/game-server
COPY configs/odds.json /app/odds/odds.json
USER app
EXPOSE 8787
HEALTHCHECK --interval=10s --timeout=3s --retries=6 CMD wget -qO- http://127.0.0.1:8787/healthz >/dev/null || exit 1
ENTRYPOINT ["/app/game-server"]
# 預設不帶 -dev（fail closed：沒有 -redis 會拒絕啟動）；測試環境由 compose command 明確帶 -dev
CMD ["-addr", ":8787", "-engine", "{engine}", "-odds", "/app/odds/odds.json"]
"""
DOCKERIGNORE = "*.exe\nbin/\nout/\nreports/\n**/*_test.go\n**/testdata/\n"

STUB = '''// Package {engine} 是 {slug} 的機率模組（⑧ 抽離第 3 步：逐函式移植 ⑦ game.js 的數學）。
//
// 依 ark-web-game references/extraction-sop.md：
//   1. 照 game/trace-map.md 一列一列移植，抽值順序與 game.js 相同（只在條件成立時才抽）。
//   2. Body 換算整數 credit 只用 result.Credits；feature.script 欄位與 game.js record 完全相同。
//   3. 逐局對帳（整份 SpinResult）0 不一致才算完成。
package {engine}

import (
	"encoding/json"
	"errors"
	"os"

	"{module}/internal/prob"
	"{module}/internal/result"
)

// EngineName 是註冊表名稱（server -engine {engine}）。
const EngineName = "{engine}"

func init() {{
	prob.Register(EngineName, func(oddsPath string) (prob.Game, error) {{
		b, err := os.ReadFile(oddsPath)
		if err != nil {{
			return nil, err
		}}
		var odds map[string]any
		if err := json.Unmarshal(b, &odds); err != nil {{
			return nil, err
		}}
		return &Game{{odds: odds}}, nil
	}})
}}

// ErrNotPorted 表示數學尚未移植。
var ErrNotPorted = errors.New("{engine}：機率模組尚未移植（見 references/extraction-sop.md）")

// Game 實作 prob.Game。
type Game struct{{ odds map[string]any }}

// Outcome 是一局的數學結果（倍數）；移植時依 game.js 的結果結構補欄位。
type Outcome struct{{ X float64 }}

// TotalX 實作 prob.Outcome。
func (o *Outcome) TotalX() float64 {{ return o.X }}

// Info 實作 prob.Game（移植時由 odds 讀盤面、押注表、符號碼）。
func (g *Game) Info() prob.Info {{ return prob.Info{{Bets: []int{{1}}, DefaultBet: 1, BetBase: 1}} }}

// Play 實作 prob.Game。
func (g *Game) Play(rng prob.Rand, fx func() uint32) prob.Outcome {{ panic(ErrNotPorted) }}

// Body 實作 prob.Game。
func (g *Game) Body(o prob.Outcome, bet int) result.Body {{ panic(ErrNotPorted) }}

// ParseScene 實作 prob.Game。
func (g *Game) ParseScene(raw json.RawMessage) (prob.Scene, bool, error) {{ return nil, false, ErrNotPorted }}

// Match 實作 prob.Game。
func (g *Game) Match(sc prob.Scene, o prob.Outcome) bool {{ return false }}
'''


def out(obj: dict, code: int) -> None:
    print(json.dumps(obj, ensure_ascii=False))
    sys.exit(code)


def iter_files(root: pathlib.Path):
    for rel in INCLUDE:
        p = root / rel
        if p.is_file():
            yield p
        elif p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file() and "__pycache__" not in f.parts:
                    yield f


def sync_template(src: pathlib.Path) -> None:
    gomod = src / "go.mod"
    if not gomod.is_file():
        out({"ok": False, "fatal": f"{src} 不是 Go module"}, 2)
    module = REF_MODULE_RE.search(gomod.read_text(encoding="utf-8")).group(1)
    eng_imp = re.compile(r'_ "' + re.escape(module) + r'/internal/prob/(\w+)"[^\n]*')
    if TEMPLATE.exists():
        shutil.rmtree(TEMPLATE)
    n = 0
    for f in iter_files(src):
        rel = f.relative_to(src).as_posix()
        dst = TEMPLATE / (rel + ".tmpl" if rel.endswith(".go") or rel == "go.mod" else rel)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if rel.endswith((".go", ".mod", ".json", ".sh", ".ps1", ".md")):
            t = f.read_text(encoding="utf-8")
            if rel == "cmd/server/main.go":
                t = eng_imp.sub('_ "__MODULE__/internal/prob/__ENGINE__" // 註冊機率模組', t)
                t = re.sub(r'flag\.String\("engine", "\w+"', 'flag.String("engine", "__ENGINE__"', t)
                t = re.sub(r'flag\.String\("game", "[^"]+"', 'flag.String("game", "__GAME__"', t)
            t = t.replace(module, "__MODULE__")
            dst.write_text(t, encoding="utf-8")
        else:
            shutil.copy2(f, dst)
        n += 1
    (TEMPLATE / "TEMPLATE.json").write_text(json.dumps({
        "from": src.as_posix(), "module": module, "synced": dt.date.today().isoformat(), "files": n,
        "note": "由 wg_server_init.py --sync-template 產生，勿手改；ark-go 同步後重跑"}, ensure_ascii=False, indent=1), encoding="utf-8")
    out({"ok": True, "template": str(TEMPLATE), "files": n, "module": module}, 0)


def rehash_vendored(dest: pathlib.Path, today: str) -> None:
    vj = dest / "internal" / "ark-go" / "VENDORED.json"
    if not vj.is_file():
        return
    m = json.loads(vj.read_text(encoding="utf-8"))
    base = vj.parent
    for rel in list(m.get("files", {})):
        p = base / rel
        if p.is_file():
            m["files"][rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    m.setdefault("sync_chain", []).append({"from": "ark-web-game assets/go-server-template", "synced": today,
                                           "note": "wg_server_init 只改匯入路徑（module），內容未改"})
    vj.write_text(json.dumps(m, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def init(a) -> None:
    if not (TEMPLATE / "TEMPLATE.json").is_file():
        out({"ok": False, "fatal": "範本不存在，先跑 --sync-template --from <參考 go-server>"}, 2)
    if not re.fullmatch(r"[a-z][a-z0-9]*", a.engine):
        out({"ok": False, "fatal": "--engine 只能小寫英數、字母開頭（Go 套件名）"}, 2)
    dest = pathlib.Path(a.out or f"data/slot/{a.slug}/game/go-server")
    if dest.exists() and any(dest.iterdir()) and not a.force:
        out({"ok": False, "fatal": f"{dest} 已存在，加 --force 覆寫"}, 1)
    module = a.module or f"aidev/slot/{a.slug}/go-server"
    game_id = a.game_id or a.slug
    n = 0
    for f in sorted(TEMPLATE.rglob("*")):
        if not f.is_file() or f.name == "TEMPLATE.json":
            continue
        rel = f.relative_to(TEMPLATE).as_posix()
        if rel.endswith(".tmpl"):
            rel = rel[:-5]
        dst = dest / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if rel.endswith((".go", ".mod", ".json", ".sh", ".ps1", ".md")) or rel == "go.mod":
            t = f.read_text(encoding="utf-8")
            t = t.replace("__MODULE__", module).replace("__ENGINE__", a.engine).replace("__GAME__", game_id)
            dst.write_text(t, encoding="utf-8")
        else:
            shutil.copy2(f, dst)
        n += 1
    (dest / "Dockerfile").write_text(DOCKERFILE.format(slug=a.slug, engine=a.engine), encoding="utf-8")
    (dest / ".dockerignore").write_text(DOCKERIGNORE, encoding="utf-8")
    stub = dest / "internal" / "prob" / a.engine / "game.go"
    stub.parent.mkdir(parents=True, exist_ok=True)
    stub.write_text(STUB.format(engine=a.engine, slug=a.slug, module=module), encoding="utf-8")
    today = dt.date.today().isoformat()
    rehash_vendored(dest, today)
    (dest / "README.md").write_text(
        f"# {a.slug} Go Server（由 ark-web-game wg_server_init 產生，{today}）\n\n"
        f"- 機率模組：`internal/prob/{a.engine}/`（待移植；依 ark-web-game references/extraction-sop.md）\n"
        f"- 局服務、網路層、SpinResult 信封來自範本，請勿就地修改；`internal/ark-go` 為原封複本\n"
        f"- 啟動：`go run ./cmd/server -dev -engine {a.engine} -odds <odds.json>`\n", encoding="utf-8")
    out({"ok": True, "dest": str(dest), "files": n + 2, "module": module, "engine": a.engine,
         "next": f"移植 internal/prob/{a.engine}/game.go → go build ./... → 逐局對帳"}, 0)


def main() -> None:
    ap = argparse.ArgumentParser(description="Go Server 範本：產骨架或更新範本")
    ap.add_argument("--sync-template", action="store_true")
    ap.add_argument("--from", dest="src")
    ap.add_argument("--slug")
    ap.add_argument("--engine")
    ap.add_argument("--module")
    ap.add_argument("--game-id")
    ap.add_argument("--out")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if a.sync_template:
        if not a.src:
            out({"ok": False, "fatal": "--sync-template 需要 --from"}, 2)
        sync_template(pathlib.Path(a.src))
    if not a.slug or not a.engine:
        out({"ok": False, "fatal": "需要 --slug 與 --engine"}, 2)
    init(a)


if __name__ == "__main__":
    main()
