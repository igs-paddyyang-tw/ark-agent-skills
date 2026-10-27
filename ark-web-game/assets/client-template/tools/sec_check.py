#!/usr/bin/env python3
"""網頁遊戲資安快測（唯讀稽核器）v0.2。

定位：上線前的「設定與弱點」檢查，不是攻擊工具。
  - 只做兩類動作：(a) 讀本機設定檔／打包結果（靜態）；(b) 對 --base 指定的測試環境發唯讀 GET，讀標頭、確認敏感檔不存在（即時）。
  - 不送 POST、不連 WebSocket、不送登入／下注／強制情境、不暴力嘗試、不掃網段。
  - 需要送封包才能驗的項目（AUTH-1 等）在規格裡標「人工」，本工具不內建那類請求。

用法：
  python3 tools/sec_check.py --root <aidev 根> --game magic-lamp --base http://localhost:3031 --profile test
  python3 tools/sec_check.py --root <aidev 根> --game huffnpuff-open-house --profile prod          # 只靜態
規格：docs/designs/2026-10-23-web-game-security-quicktest-spec.md
v0.2（2026-10-27）：--profile prod 讀 deploy/<game>/compose.release.yaml（release 設定）判 DEP-1／DEP-3；DEP-6 依設定檔判（test 為 WARN）；
      沒給 --base 時 DEP-7／DEP-8 改看 nginx.conf 與 security-headers.conf（靜態）。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request

# ── 遊戲對照：gameId 與路徑 ─────────────────────────────────────────
GAMES = {
    "magic-lamp": {"slug": "magic-lamp", "server": "data/slot/magic-lamp/game/go-server"},
    "huffnpuff-open-house": {"slug": "huffnpuff", "server": "data/slot/huffnpuff-open-house/game/go-server"},
}
PGP = "data/web-game/pixi-game-platform"

SEV = {"DEP-1": "P0", "DEP-2": "P1", "DEP-3": "P0", "DEP-4": "P1", "DEP-5": "P2",
       "DEP-6": "P1", "DEP-7": "P2", "DEP-8": "P3", "DEP-9": "P1", "DEP-10": "P3",
       "AUTH-5": "P2", "AUTH-6": "P2",
       "GAME-1": "P0", "GAME-2": "P0", "GAME-3": "P0", "GAME-4": "P1", "GAME-5": "P2",
       "GAME-6": "P2", "GAME-7": "P1",
       "CLIENT-1": "P1", "CLIENT-2": "P1", "CLIENT-3": "P1", "CLIENT-4": "P2",
       "SUPPLY-1": "P1", "SUPPLY-2": "P1"}

results: list[dict] = []
PROFILE_PROD = False


def add(cid, status, detail=""):
    results.append({"id": cid, "severity": SEV.get(cid, "P3"), "status": status, "detail": detail})


def read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


# ── 即時：唯讀探測 ─────────────────────────────────────────────────
def http_get(url, timeout=3):
    """唯讀 GET，回 (status, headers, body_head)；連不上回 (None, {}, '')."""
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "sec_check/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 本機測試環境、唯讀
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read(2048).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in (e.headers or {}).items()}, ""
    except Exception:  # noqa: BLE001 連不上／逾時
        return None, {}, ""


SPA_FINGERPRINTS = ('id="app"', "<!doctype html", "<!DOCTYPE html", "manifest.json")


def looks_like_spa(body):
    low = body.lower()
    return any(fp.lower() in low for fp in SPA_FINGERPRINTS)


# ── 靜態：部署與設定 ───────────────────────────────────────────────
def server_command(compose_text):
    """compose 檔裡 server 服務的 command（字串，給 -dev／-seed 判斷用）"""
    if not compose_text:
        return None
    try:
        import yaml  # noqa: PLC0415
        d = yaml.safe_load(compose_text) or {}
        c = ((d.get("services") or {}).get("server") or {}).get("command")
        if c is not None:
            return " ".join(map(str, c)) if isinstance(c, list) else str(c)
    except Exception:  # noqa: BLE001
        pass
    m = re.search(r"command:\s*\[([^\]]*)\]", compose_text)
    return m.group(1) if m else None


def check_deploy_static(root, game, prod):
    sdir = os.path.join(root, GAMES[game]["server"])
    slug = GAMES[game]["slug"]
    compose = read(os.path.join(root, PGP, "deploy", slug, "compose.yaml"))
    release = read(os.path.join(root, PGP, "deploy", slug, "compose.release.yaml"))
    dockerfile_srv = read(os.path.join(sdir, "Dockerfile"))
    nginx = read(os.path.join(root, PGP, "deploy", slug, "nginx.conf"))

    # DEP-1/3：command 是否帶 -dev / -seed（prod 看 release 設定 compose.release.yaml；沒有就看 compose.yaml）
    src_name = "compose.release.yaml" if (prod and release) else "compose.yaml"
    cmd = server_command(release if (prod and release) else compose) or ""
    has_dev = bool(re.search(r"(^|[\s\"',])-dev($|[\s\"',])", cmd))
    has_seed = "-seed" in cmd
    if prod:
        add("DEP-1", "FAIL" if has_dev else "PASS",
            (f"{src_name} 的 server command 帶 -dev（正式設定不應帶；請建 compose.release.yaml）" if has_dev
             else f"{src_name}：server command 無 -dev" + ("，有 -redis" if "-redis" in cmd else "（⚠ 沒有 -redis，Server 會拒絕啟動）")))
        add("DEP-3", "FAIL" if has_seed else "PASS", f"{src_name}：正式不應帶 -seed" if has_seed else f"{src_name}：無 -seed")
    else:
        add("DEP-1", "INFO", f"test 環境開發模式（command dev={has_dev}）")
        add("DEP-3", "INFO", f"test 環境 seed={has_seed}")

    # DEP-2：映像預設 CMD
    if dockerfile_srv:
        cmds = re.findall(r'^CMD\s+(.+)$', dockerfile_srv, re.M)
        last = cmds[-1] if cmds else ""
        dev_default = "-dev" in last
        add("DEP-2", ("FAIL" if prod else "WARN") if dev_default else "PASS",
            f"映像預設 CMD dev={dev_default}（正式映像預設應不帶 -dev）")
    else:
        add("DEP-2", "SKIP", "找不到 Server Dockerfile")

    # DEP-4：internal 不經 nginx 對外
    if nginx is not None:
        add("DEP-4", "FAIL" if re.search(r"location\s+/internal", nginx) else "PASS",
            "nginx 把 /internal 代理出去" if "location /internal" in nginx else "nginx 未代理 /internal")
    else:
        add("DEP-4", "SKIP", "找不到 nginx.conf")

    # DEP-5：只有 web 有 ports（只看 server 服務區塊，不跨到別的服務）
    if compose:
        # 服務在 2 空白縮排（  server:、  web:…）；切出每個服務的區塊
        parts = re.split(r"\n  (\w[\w-]*):\n", "\n" + compose)
        srv_block = ""
        for i in range(1, len(parts) - 1, 2):
            if parts[i] == "server":
                srv_block = parts[i + 1]
                break
        srv_has_ports = bool(re.search(r"^\s+ports:", srv_block, re.M))
        add("DEP-5", "FAIL" if srv_has_ports else "PASS",
            "server 服務直接暴露埠" if srv_has_ports else "server 用 expose、僅 web 對外")
    else:
        add("DEP-5", "SKIP", "找不到 compose")

    # DEP-10：Server 容器非 root
    if dockerfile_srv:
        add("DEP-10", "PASS" if re.search(r"^USER\s+\S", dockerfile_srv, re.M) else "WARN",
            "Server 容器有設非 root USER" if "USER" in dockerfile_srv else "未設 USER")
    else:
        add("DEP-10", "SKIP", "找不到 Dockerfile")

    # DEP-9：tunnel 設定存在性（人工確認是否在跑）
    if compose and "trycloudflare" in compose or (compose and "cloudflared" in compose):
        add("DEP-9", "INFO", "compose 有 tunnel profile；開著時屬暫時公開，測完要停")


# ── 即時：標頭與敏感檔 ─────────────────────────────────────────────
SENSITIVE = ["/.env", "/.git/HEAD", "/package.json", "/pnpm-lock.yaml",
             "/configs/odds_live-b.json", "/odds/odds_live-b.json",
             "/deploy/magic-lamp/compose.yaml"]


def check_nginx_static(root, game):
    """沒有 --base 時：看 nginx.conf 是否關版本號、是否 include 安全標頭，以及標頭檔內容"""
    slug = GAMES[game]["slug"]
    conf = read(os.path.join(root, PGP, "deploy", slug, "nginx.conf")) or ""
    snip = read(os.path.join(root, PGP, "deploy", "_shared", "security-headers.conf")) or ""
    body = conf + "\n" + (snip if "security-headers.conf" in conf else "")
    need = ["X-Content-Type-Options", "Referrer-Policy"]
    miss = [h for h in need if h not in body]
    if "frame-ancestors" not in body and "X-Frame-Options" not in body:
        miss.append("frame-ancestors / X-Frame-Options")
    # location 內有自己的 add_header 卻沒 include → 會丟掉 server 層標頭
    lost = [ln.strip()[:60] for ln in conf.splitlines() if ln.strip().startswith("location") and "add_header" in ln and "security-headers.conf" not in ln]
    add("DEP-7", "WARN" if (miss or lost) else "PASS",
        ("缺標頭：" + ", ".join(miss) if miss else "") + (("；這些 location 有 add_header 卻沒 include 安全標頭：" + " | ".join(lost[:3])) if lost else "")
        or "nginx.conf（靜態）：安全標頭齊全、每個 add_header location 都有 include")
    add("DEP-8", "PASS" if re.search(r"server_tokens\s+off", conf) else "WARN",
        "nginx.conf（靜態）：server_tokens off" if re.search(r"server_tokens\s+off", conf) else "nginx.conf 未設 server_tokens off（會回傳版本號）")


def check_deploy_live(base, root=None, game=None):
    if not base:
        add("DEP-6", "SKIP", "未給 --base，略過即時檢查（.map 是否打包見 CLIENT-2）")
        if root and game:
            check_nginx_static(root, game)
        else:
            for cid in ("DEP-7", "DEP-8"):
                add(cid, "SKIP", "未給 --base，略過即時檢查")
        return
    # 先確認連得上；連不上就 SKIP，不要誤報成 PASS
    st0, hdr, body = http_get(base.rstrip("/") + "/")
    if st0 is None:
        for cid in ("DEP-6", "DEP-7", "DEP-8"):
            add(cid, "SKIP", f"連不上 {base}，略過即時檢查")
        return
    # DEP-6：敏感檔
    leaked = []
    for p in SENSITIVE:
        st, _, body = http_get(base.rstrip("/") + p)
        if st == 200 and not looks_like_spa(body):
            leaked.append(p)
    # 另外探 source map（沿用上面已取回的首頁 body/hdr）
    for m in re.findall(r'src="([^"]+\.js)"', body):
        mp = base.rstrip("/") + (m if m.startswith("/") else "/" + m) + ".map"
        stm, _, bm = http_get(mp)
        if stm == 200 and not looks_like_spa(bm):
            leaked.append(m + ".map")
    add("DEP-6", ("FAIL" if PROFILE_PROD else "WARN") if leaked else "PASS",
        ("可被下載：" + ", ".join(leaked)) if leaked else "未發現可下載的敏感檔")

    # DEP-7：安全標頭
    missing = []
    if "x-content-type-options" not in hdr:
        missing.append("X-Content-Type-Options")
    if "content-security-policy" not in hdr and "x-frame-options" not in hdr:
        missing.append("CSP frame-ancestors / X-Frame-Options")
    if "referrer-policy" not in hdr:
        missing.append("Referrer-Policy")
    if base.startswith("https") and "strict-transport-security" not in hdr:
        missing.append("HSTS")
    add("DEP-7", "WARN" if missing else "PASS",
        ("缺標頭：" + ", ".join(missing)) if missing else "安全標頭齊全")

    # DEP-8：伺服器版本
    srv = hdr.get("server", "")
    add("DEP-8", "WARN" if re.search(r"\d", srv) else "PASS", f"Server 標頭：{srv or '(無)'}")


# ── 靜態：Client 打包 ──────────────────────────────────────────────
WEIGHTS = ["SpecialEventWeight", "GoldenChestWeight", "SliverChestWeight", "WoodenChestWeight", "SpecialEventScore"]
SECRET = re.compile(r"(BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})")


def check_client(root, game, prod):
    slug = GAMES[game]["slug"]
    dist = os.path.join(root, PGP, "games", slug, "dist")
    srcdir = os.path.join(root, PGP, "games", slug, "src")
    if not os.path.isdir(dist):
        for cid in ("CLIENT-1", "CLIENT-2", "CLIENT-3"):
            add(cid, "SKIP", "沒有 dist（尚未 build）")
    else:
        jsblob, maps = "", []
        for dirpath, _, files in os.walk(dist):
            for fn in files:
                if fn.endswith(".map"):
                    maps.append(os.path.join(dirpath, fn))
                elif fn.endswith(".js"):
                    jsblob += read(os.path.join(dirpath, fn)) or ""
        hit = [w for w in WEIGHTS if w in jsblob]
        add("CLIENT-1", "FAIL" if hit else "PASS", ("打包含機率參數名：" + ",".join(hit)) if hit else "打包無機率參數")
        add("CLIENT-2", ("FAIL" if prod else "WARN") if maps else "PASS",
            f"dist 有 {len(maps)} 個 source map（正式站應關閉或不部署）" if maps else "無 source map")
        add("CLIENT-3", "FAIL" if SECRET.search(jsblob) else "PASS",
            "打包疑似含秘密" if SECRET.search(jsblob) else "打包無寫死秘密樣式")

    # CLIENT-4：原始碼 DOM 注入
    danger = []
    if os.path.isdir(srcdir):
        for dirpath, _, files in os.walk(srcdir):
            for fn in files:
                if fn.endswith((".ts", ".js")) and ".test." not in fn:
                    t = read(os.path.join(dirpath, fn)) or ""
                    for pat in ("innerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function"):
                        if pat in t:
                            danger.append(f"{fn}:{pat}")
        add("CLIENT-4", "WARN" if danger else "PASS", (", ".join(danger[:6])) if danger else "無危險 DOM 注入點")
    else:
        add("CLIENT-4", "SKIP", "找不到 src")


# ── 靜態：局邏輯把關機制存在性 ─────────────────────────────────────
def check_game(root, game):
    sdir = os.path.join(root, GAMES[game]["server"])
    svc = read(os.path.join(sdir, "internal/round/service.go")) or ""
    wallet = read(os.path.join(sdir, "internal/round/devwallet.go")) or ""
    http_ = read(os.path.join(sdir, "internal/api/http.go")) or ""
    conn = read(os.path.join(sdir, "internal/ark-go/ws/conn.go")) or ""
    guard = read(os.path.join(sdir, "internal/ark-go/guard/guard.go")) or ""
    checks = {
        "GAME-1": ("checkBet" in svc, "押注白名單＋餘額檢查"),
        "GAME-3": ("去重" in wallet or "seen" in wallet, "結算 roundID 去重（冪等）"),
        "GAME-4": ("balanceBefore" in http_ or "BalanceBefore" in svc, "internal 僅對帳、不做帳"),
        "GAME-5": ("MaxBytesReader" in http_ and "MaxMessage" in conn, "HTTP／WS 請求大小上限"),
        "GAME-6": ("FloodMeter" in guard, "流量封鎖"),
        "GAME-7": ("NewRoundID" in svc, "局號不含 seed"),
    }
    for cid, (ok, label) in checks.items():
        add(cid, "PASS" if ok else "WARN", f"{label}：{'機制存在' if ok else '未找到，請人工確認'}")


# ── 供應鏈（可選，呼叫外部工具）────────────────────────────────────
def check_supply(root, game):
    import shutil
    import subprocess
    sdir = os.path.join(root, GAMES[game]["server"])
    if shutil.which("govulncheck"):
        try:
            r = subprocess.run(["govulncheck", "./..."], cwd=sdir, capture_output=True, text=True, timeout=300)
            add("SUPPLY-1", "PASS" if r.returncode == 0 else "FAIL",
                "govulncheck 無發現" if r.returncode == 0 else (r.stdout[-500:] or "有發現"))
        except Exception as e:  # noqa: BLE001
            add("SUPPLY-1", "SKIP", f"govulncheck 執行失敗：{e}")
    else:
        add("SUPPLY-1", "SKIP", "未安裝 govulncheck")
    if shutil.which("pnpm"):
        try:
            r = subprocess.run(["pnpm", "audit", "--prod", "--json"], cwd=os.path.join(root, PGP),
                               capture_output=True, text=True, timeout=300)
            hi = '"high"' in r.stdout or '"critical"' in r.stdout
            add("SUPPLY-2", "FAIL" if hi else "PASS", "pnpm audit 有 high/critical" if hi else "無 high/critical")
        except Exception as e:  # noqa: BLE001
            add("SUPPLY-2", "SKIP", f"pnpm audit 執行失敗：{e}")
    else:
        add("SUPPLY-2", "SKIP", "未安裝 pnpm")


# ── 匯整 ───────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="網頁遊戲資安快測（唯讀稽核器）")
    ap.add_argument("--root", default=".", help="aidev 根目錄")
    ap.add_argument("--game", required=True, help="data/slot 的遊戲代號（slug），例 magic-lamp")
    ap.add_argument("--client", help="pixi-game-platform 的遊戲資料夾名（games/<名>、deploy/<名>）；預設＝--game（已知兩款自動對應）")
    ap.add_argument("--base", default="", help="測試環境網址（省略＝只靜態）")
    ap.add_argument("--profile", default="test", choices=["test", "prod"])
    ap.add_argument("--supply", action="store_true", help="另跑 govulncheck／pnpm audit")
    ap.add_argument("--out", default="", help="輸出 JSON 路徑")
    args = ap.parse_args()
    prod = args.profile == "prod"
    if args.game not in GAMES:                             # 新遊戲：不用改程式，照佈局慣例推路徑
        GAMES[args.game] = {"slug": args.client or args.game, "server": f"data/slot/{args.game}/game/go-server"}
    elif args.client:
        GAMES[args.game]["slug"] = args.client
    root = os.path.abspath(args.root)

    check_deploy_static(root, args.game, prod)
    global PROFILE_PROD
    PROFILE_PROD = prod
    check_deploy_live(args.base, root, args.game)
    check_game(root, args.game)
    check_client(root, args.game, prod)
    if args.supply:
        check_supply(root, args.game)

    order = {"FAIL": 0, "WARN": 1, "SKIP": 2, "INFO": 3, "PASS": 4}
    results.sort(key=lambda r: (order.get(r["status"], 9), r["severity"], r["id"]))
    n = {s: sum(1 for r in results if r["status"] == s) for s in ("PASS", "FAIL", "WARN", "SKIP", "INFO")}
    p01_fail = [r for r in results if r["status"] == "FAIL" and r["severity"] in ("P0", "P1")]
    gate = ("report-only" if not prod else ("BLOCK" if p01_fail else "PASS"))

    rep = {"schema": "web-game-sec/0.1", "game": args.game, "profile": args.profile,
           "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "base": args.base, "summary": {**n, "gate": gate}, "checks": results}

    for r in results:
        print(f"{r['status']:5} {r['severity']:3} {r['id']:9} {r['detail']}")
    print(f"\n{n['FAIL']} FAIL · {n['WARN']} WARN · {n['PASS']} PASS · {n['SKIP']} SKIP · {n['INFO']} INFO")
    print(f"放行判定（{args.profile}）：{gate}")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(rep, f, ensure_ascii=False, indent=2)
        print(f"報告：{args.out}")
    return 1 if gate == "BLOCK" else 0


if __name__ == "__main__":
    sys.exit(main())
