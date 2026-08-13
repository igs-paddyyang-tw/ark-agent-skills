#!/usr/bin/env python3
"""tg_send — Telegram 發送閘道（文字／檔案／圖片）。

可當 CLI 用，也可 `from tg_send import send_text, send_file` 直接呼叫。
零第三方依賴（只用標準庫），因為它常在沒有 venv 的 agent working_directory 下執行。

## 為何不直接用 Bot API

三件事在每個專案都要重做一次，而且每次都有人漏掉其中一件：

1. **Forum topic**：群組開了 Forum 之後，`chat_id` 不足以定位，還要 `message_thread_id`。
   漏了會全部發到 General 區。
2. **失敗語意**：`urllib` 在 4xx 拋 `HTTPError`，而 Bot API 的錯誤原因在 **response body**
   的 `description` 欄位裡。只捕捉例外訊息會得到「HTTP Error 400: Bad Request」——
   完全看不出是標籤沒閉合、topic 不存在，還是被踢出群組。
3. **逸出**：`parse_mode=HTML` 時，內容裡的 `<b>` 是格式還是字面文字，取決於誰產生它。
   自動逸出會把 LLM 產出的 `<b>` 變成 `&lt;b&gt;`；完全不逸出則會讓一個 `<` 弄壞整則訊息。

## 使用

    # 文字（走 team.yaml 的 topic 對照）
    tg_send.py text --topic daily_report --file-text summary.txt --token-env TELEGRAM_BOT_TOKEN_GA

    # 檔案附件
    tg_send.py file --topic daily_report --path data/output/market-2026-08-13.html \\
        --caption "競品日報 2026-08-13"

    # 先看要送什麼，不真的送
    tg_send.py text --chat-id -1001234567890 --text "測試" --dry-run
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Literal

__all__ = ["send_text", "send_file", "send_photo", "resolve_target", "TgResult"]

#: Telegram 單則訊息上限 4096 字元。預設保守值取 4000 ——
#: TG 以 UTF-16 code unit 計長，中日文與 emoji 的計法與 Python `len()` 不同，
#: 貼著上限送會偶發 400（ninja 2026-08-13 實例）。
TEXT_LIMIT = 4000

#: Bot API 的檔案上傳上限。超過要走 local Bot API server，不是換參數能解決的。
FILE_LIMIT_BYTES = 50 * 1024 * 1024

_API = "https://api.telegram.org/bot{token}/{method}"

TgResult = dict[str, Any]

EscapeMode = Literal["auto", "always", "never"]
OverflowMode = Literal["truncate", "split", "error"]


# ── 逸出 ────────────────────────────────────────────────────────────────────

#: `parse_mode=HTML` 下 Telegram 承認的標籤。出現這些才判定「內容已是 HTML」。
_TG_TAGS = (
    "<b>", "<i>", "<u>", "<s>", "<a href=", "<code>", "<pre>",
    "<blockquote", "<tg-spoiler>", "<span class=\"tg-spoiler\">",
)


def escape_html(text: str) -> str:
    """逸出 Telegram HTML 的三個保留字元。

    只有這三個 —— 引號不必逸出（Bot API 的 HTML 子集不解析屬性以外的引號）。
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def apply_escape(text: str, mode: EscapeMode) -> str:
    """依模式決定要不要逸出。

    `auto` 的判準是「內容裡有沒有 Telegram 認得的標籤」：
      - 有 → 視為已格式化，原樣送出（渲染層已經自己逸出過使用者內容）
      - 沒有 → 視為純文字，逸出後送出

    這條規則是踩出來的：paddy-team 曾把 LLM 產出的 `<b>` 二次逸出成 `&lt;b&gt;`，
    整份日報變成滿螢幕的跳脫字元。反過來把未逸出的純文字直接送，
    一個 `<` 就會讓 Telegram 回 400。
    """
    if mode == "never":
        return text
    if mode == "always":
        return escape_html(text)
    低 = text.lower()
    return text if any(t in 低 for t in _TG_TAGS) else escape_html(text)


# ── 目標解析 ────────────────────────────────────────────────────────────────

def resolve_target(
    *,
    topic: str | None = None,
    chat_id: str | int | None = None,
    thread_id: int | None = None,
    team_yaml: Path | None = None,
) -> tuple[str | int, int | None, str | None]:
    """決定要送到哪裡。回傳 `(chat_id, thread_id, token_env)`。

    優先序：明確給的 `chat_id` > `team.yaml` 的 topic 對照 > 環境變數 `TELEGRAM_CHAT_ID`。

    `topic` 走 `team.yaml`（`channel.group_id` + `topics` 對照 + `channel.bot_token_env`），
    這樣 topic 名稱只維護一份 —— 硬編數字 ID 在頻道重整時必然漏改。

    Raises:
        ValueError: topic 不存在於對照表（連同可用清單一起回報，省得再去翻設定）
        FileNotFoundError: 指定了 topic 但找不到 team.yaml
    """
    if chat_id is not None:
        return chat_id, thread_id, None

    if topic:
        path = team_yaml or _find_team_yaml()
        if path is None:
            raise FileNotFoundError(
                "指定了 --topic 但找不到 team.yaml；改用 --chat-id 或 --team-yaml 指定路徑"
            )
        raw = _load_yaml(path)
        channel = raw.get("channel") or {}
        topics = raw.get("topics") or {}
        if topic not in topics:
            raise ValueError(f"未知 topic '{topic}'，可用: {sorted(topics)}")
        group_id = channel.get("group_id")
        if not group_id:
            raise ValueError(f"{path} 未設定 channel.group_id")
        return group_id, topics[topic], channel.get("bot_token_env") or None

    env_chat = os.environ.get("TELEGRAM_CHAT_ID")
    if env_chat:
        return env_chat, thread_id, None
    raise ValueError("未指定發送目標：需要 --topic、--chat-id 或環境變數 TELEGRAM_CHAT_ID")


def _find_team_yaml(start: Path | None = None) -> Path | None:
    """從 cwd 逐層往上找 `team.yaml`。

    不用固定層數的 `.parent` 鏈 —— 各 agent 的 working_directory 深度不同，
    數字寫死在某一個 agent 下會對、在另一個下會靜默讀到別的檔案。
    """
    cur = (start or Path.cwd()).resolve()
    for p in [cur, *cur.parents]:
        candidate = p / "team.yaml"
        if candidate.exists():
            return candidate
    return None


def _load_yaml(path: Path) -> dict:
    """讀 team.yaml。優先用 PyYAML，缺了就退回極簡解析。

    退路存在的理由：這支腳本要能在沒有裝 PyYAML 的環境跑（skill 常被複製到
    agent 目錄下獨立執行）。極簡解析只認得本檔需要的三個欄位結構。
    """
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
        return yaml.safe_load(text) or {}
    except ImportError:
        return _minimal_yaml(text)


def _minimal_yaml(text: str) -> dict:
    """只解析 `channel:` 與 `topics:` 兩個頂層區塊的 `key: value`。"""
    out: dict[str, dict] = {}
    section: str | None = None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith((" ", "\t")):
            head = line.split(":", 1)[0].strip()
            section = head if head in ("channel", "topics") else None
            if section:
                out.setdefault(section, {})
            continue
        if section and ":" in line:
            k, v = line.split(":", 1)
            v = v.split("#", 1)[0].strip().strip("\"'")
            if v:
                out[section][k.strip()] = int(v) if _is_int(v) else v
    return out


def _is_int(v: str) -> bool:
    return v.lstrip("-").isdigit()


def _get_token(token_env: str | None, fallback_env: str | None = None) -> tuple[str, str]:
    """取 Bot Token。回傳 `(token, 用到的環境變數名)`。

    候選順序：明確指定 > team.yaml 的 `channel.bot_token_env` > `TELEGRAM_BOT_TOKEN`。
    ninja 用的是 `TELEGRAM_BOT_TOKEN_GA`，寫死變數名的工具在那裡一定拿不到 token。
    """
    for name in (token_env, fallback_env, "TELEGRAM_BOT_TOKEN"):
        if name and os.environ.get(name):
            return os.environ[name], name
    tried = [n for n in (token_env, fallback_env, "TELEGRAM_BOT_TOKEN") if n]
    raise ValueError(f"Bot Token 未設定（已嘗試環境變數：{', '.join(tried)}）")


# ── API 呼叫 ────────────────────────────────────────────────────────────────

def _call(
    token: str,
    method: str,
    payload: dict[str, Any],
    *,
    files: dict[str, Path] | None = None,
    retries: int = 3,
    timeout: int = 60,
) -> TgResult:
    """呼叫 Bot API，一律回傳 result dict，不拋例外。

    **錯誤描述取自 response body 而非例外字串** —— `urllib` 在 4xx 拋 `HTTPError`，
    只讀 `str(e)` 得到的是「HTTP Error 400: Bad Request」，看不出原因；
    body 裡的 `description` 才會說「can't parse entities: Unclosed start tag」。
    這個差別決定了值班的人要查五分鐘還是五十分鐘。

    重試只對「重試有意義」的情況：逾時、5xx、429（依 `retry_after` 等待）。
    400 是內容本身有問題，重試幾次都一樣。
    """
    url = _API.format(token=token, method=method)
    last: TgResult = {"status": "error", "message": "未執行"}

    for attempt in range(1, retries + 1):
        try:
            if files:
                body, content_type = _encode_multipart(payload, files)
                req = urllib.request.Request(url, data=body, headers={"Content-Type": content_type})
            else:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read())
            if data.get("ok"):
                return {
                    "status": "success",
                    "message_id": (data.get("result") or {}).get("message_id"),
                    "method": method,
                }
            last = {"status": "error", "message": data.get("description", "unknown"), "method": method}
            return last  # ok=false 代表請求送達但被拒，重試無意義

        except urllib.error.HTTPError as e:
            描述, retry_after = _read_api_error(e)
            last = {
                "status": "error",
                "message": 描述,
                "http_status": e.code,
                "method": method,
            }
            if e.code == 429:
                time.sleep(retry_after or 3)
                continue
            if 500 <= e.code < 600 and attempt < retries:
                time.sleep(2 ** attempt)
                continue
            return last  # 4xx（400 最常見）：內容問題，重試沒用

        except Exception as e:  # 逾時、連線中斷等
            last = {"status": "error", "message": f"{type(e).__name__}: {e}", "method": method}
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue

    return last


def _read_api_error(e: urllib.error.HTTPError) -> tuple[str, int | None]:
    """從 HTTPError 的 body 取出 Bot API 的 `description` 與 `retry_after`。"""
    try:
        payload = json.loads(e.read().decode("utf-8", "replace"))
    except Exception:
        return f"HTTP {e.code}: {e.reason}", None
    描述 = payload.get("description") or f"HTTP {e.code}: {e.reason}"
    retry_after = (payload.get("parameters") or {}).get("retry_after")
    return f"HTTP {e.code}: {描述}", retry_after


def _encode_multipart(fields: dict[str, Any], files: dict[str, Path]) -> tuple[bytes, str]:
    """手工組 multipart/form-data（避免為了上傳檔案而多一個第三方依賴）。"""
    boundary = f"----tgsend{uuid.uuid4().hex}"
    out = bytearray()
    for k, v in fields.items():
        if v is None:
            continue
        out += f"--{boundary}\r\n".encode()
        out += f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode()
        out += (json.dumps(v) if isinstance(v, (dict, list)) else str(v)).encode("utf-8")
        out += b"\r\n"
    for k, path in files.items():
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        out += f"--{boundary}\r\n".encode()
        out += (
            f'Content-Disposition: form-data; name="{k}"; filename="{path.name}"\r\n'
            f"Content-Type: {ctype}\r\n\r\n"
        ).encode()
        out += path.read_bytes()
        out += b"\r\n"
    out += f"--{boundary}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={boundary}"


# ── 對外 API ────────────────────────────────────────────────────────────────

def send_text(
    text: str,
    *,
    topic: str | None = None,
    chat_id: str | int | None = None,
    thread_id: int | None = None,
    token_env: str | None = None,
    parse_mode: str = "HTML",
    escape: EscapeMode = "auto",
    on_overflow: OverflowMode = "truncate",
    disable_preview: bool = True,
    reply_markup: dict | None = None,
    team_yaml: Path | None = None,
    dry_run: bool = False,
) -> TgResult:
    """發送文字訊息。失敗回傳 `{"status": "error", ...}`，不拋例外。

    Args:
        on_overflow: 超過 `TEXT_LIMIT` 時的處置。
            `truncate`（預設）— 截到上限並附註「內容過長已截斷」。日報的正確做法是
                摘要截斷、完整版走附件；硬切成多則會洗版，讀者也拼不回來。
            `split` — 依段落切成多則（僅適合本來就是流水訊息的場景）。
            `error` — 直接回錯誤，讓呼叫端自己決定。

    Note:
        截斷一律在**段落邊界**，不切字串中間 —— 切在 HTML 標籤裡會留下未閉合結構，
        Telegram 直接回 400（ninja 2026-08-13 實例）。
    """
    chat, thread, yaml_token_env = resolve_target(
        topic=topic, chat_id=chat_id, thread_id=thread_id, team_yaml=team_yaml
    )
    內容 = apply_escape(text, escape) if parse_mode.upper() == "HTML" else text

    chunks, overflow_note = _fit(內容, on_overflow)
    if overflow_note == "__error__":
        return {
            "status": "error",
            "message": f"訊息長度 {len(內容)} 超過上限 {TEXT_LIMIT}（on_overflow=error）",
        }

    base = {
        "chat_id": chat,
        "message_thread_id": thread,
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_preview,
    }
    if dry_run:
        return {
            "status": "dry_run", "chat_id": chat, "message_thread_id": thread,
            "parts": len(chunks), "chars": [len(c) for c in chunks],
            "token_env": token_env or yaml_token_env or "TELEGRAM_BOT_TOKEN",
            "preview": chunks[0][:300],
        }

    token, _ = _get_token(token_env, yaml_token_env)
    結果: list[TgResult] = []
    for i, chunk in enumerate(chunks):
        payload = {**base, "text": chunk}
        if reply_markup and i == len(chunks) - 1:
            payload["reply_markup"] = reply_markup  # 按鈕掛最後一則，否則會被後續訊息推走
        r = _call(token, "sendMessage", payload)
        結果.append(r)
        if r["status"] != "success":
            return {**r, "sent_parts": i}
        if i < len(chunks) - 1:
            time.sleep(0.5)  # 避免 429
    return {**結果[-1], "parts": len(chunks)}


def send_file(
    path: str | Path,
    *,
    caption: str | None = None,
    topic: str | None = None,
    chat_id: str | int | None = None,
    thread_id: int | None = None,
    token_env: str | None = None,
    parse_mode: str = "HTML",
    escape: EscapeMode = "auto",
    team_yaml: Path | None = None,
    dry_run: bool = False,
) -> TgResult:
    """發送檔案附件。"""
    p = Path(path)
    if not p.exists():
        return {"status": "error", "message": f"檔案不存在: {p}"}
    size = p.stat().st_size
    if size > FILE_LIMIT_BYTES:
        return {
            "status": "error",
            "message": f"檔案 {size / 1048576:.1f} MB 超過 Bot API 上限 50 MB",
        }

    chat, thread, yaml_token_env = resolve_target(
        topic=topic, chat_id=chat_id, thread_id=thread_id, team_yaml=team_yaml
    )
    說明 = apply_escape(caption, escape) if caption and parse_mode.upper() == "HTML" else caption
    if 說明 and len(說明) > 1024:
        說明 = 說明[:1020] + " …"  # caption 上限 1024，超過整則會被拒

    if dry_run:
        return {
            "status": "dry_run", "chat_id": chat, "message_thread_id": thread,
            "file": str(p), "size_bytes": size, "caption": 說明,
            "token_env": token_env or yaml_token_env or "TELEGRAM_BOT_TOKEN",
        }

    token, _ = _get_token(token_env, yaml_token_env)
    return _call(
        token, "sendDocument",
        {"chat_id": chat, "message_thread_id": thread, "caption": 說明, "parse_mode": parse_mode},
        files={"document": p},
    )


def send_photo(
    path: str | Path,
    *,
    caption: str | None = None,
    topic: str | None = None,
    chat_id: str | int | None = None,
    thread_id: int | None = None,
    token_env: str | None = None,
    team_yaml: Path | None = None,
    dry_run: bool = False,
) -> TgResult:
    """發送圖片。"""
    p = Path(path)
    if not p.exists():
        return {"status": "error", "message": f"檔案不存在: {p}"}
    chat, thread, yaml_token_env = resolve_target(
        topic=topic, chat_id=chat_id, thread_id=thread_id, team_yaml=team_yaml
    )
    if dry_run:
        return {"status": "dry_run", "chat_id": chat, "message_thread_id": thread,
                "photo": str(p), "caption": caption}
    token, _ = _get_token(token_env, yaml_token_env)
    return _call(
        token, "sendPhoto",
        {"chat_id": chat, "message_thread_id": thread, "caption": caption},
        files={"photo": p},
    )


def _fit(text: str, mode: OverflowMode) -> tuple[list[str], str | None]:
    """把內容裁成符合長度上限的段落串列。"""
    if len(text) <= TEXT_LIMIT:
        return [text], None
    if mode == "error":
        return [text], "__error__"
    if mode == "truncate":
        註記 = "\n\n<i>…內容過長已截斷</i>"
        return [_cut_at_boundary(text, TEXT_LIMIT - len(註記)) + 註記], "truncated"

    # split：依空行 → 換行 → 硬切，逐級退讓
    chunks: list[str] = []
    剩餘 = text
    while len(剩餘) > TEXT_LIMIT:
        切點 = _cut_at_boundary(剩餘, TEXT_LIMIT)
        chunks.append(切點)
        剩餘 = 剩餘[len(切點):].lstrip("\n")
    if 剩餘:
        chunks.append(剩餘)
    return chunks, "split"


def _cut_at_boundary(text: str, limit: int) -> str:
    """在段落或行邊界切，不切在標籤中間。

    找不到邊界時退回硬切，但會退到最後一個 `>` 之後 —— 寧可少送一段文字，
    也不要送出未閉合的標籤（Telegram 會整則拒收）。
    """
    片段 = text[:limit]
    for 分隔 in ("\n\n", "\n"):
        idx = 片段.rfind(分隔)
        if idx > limit // 2:
            return 片段[:idx]
    idx = 片段.rfind(">")
    return 片段[: idx + 1] if idx > 0 else 片段


# ── CLI ─────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tg_send.py",
        description="Telegram 發送閘道（文字／檔案／圖片）",
    )
    sub = p.add_subparsers(dest="mode", required=True)

    def 共用(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--topic", help="team.yaml 的 topics key，如 daily_report")
        sp.add_argument("--chat-id", help="直接指定 chat_id（優先於 --topic）")
        sp.add_argument("--thread-id", type=int, help="Forum topic 的 message_thread_id")
        sp.add_argument("--token-env", help="Bot Token 的環境變數名（ninja 用 TELEGRAM_BOT_TOKEN_GA）")
        sp.add_argument("--team-yaml", type=Path, help="team.yaml 路徑（預設由 cwd 往上找）")
        sp.add_argument("--dry-run", action="store_true", help="只印出將送出的內容，不真送")
        sp.add_argument("--raise-on-error", action="store_true", help="失敗時以非 0 結束碼退出")

    t = sub.add_parser("text", help="發送文字訊息")
    共用(t)
    來源 = t.add_mutually_exclusive_group(required=True)
    來源.add_argument("--text", help="訊息內容")
    來源.add_argument("--file-text", type=Path, help="從檔案讀取訊息內容")
    來源.add_argument("--stdin", action="store_true", help="從 stdin 讀取訊息內容")
    t.add_argument("--parse-mode", default="HTML", choices=["HTML", "Markdown", "MarkdownV2", "plain"])
    t.add_argument("--escape", default="auto", choices=["auto", "always", "never"])
    t.add_argument("--on-overflow", default="truncate", choices=["truncate", "split", "error"])
    t.add_argument("--preview", action="store_true", help="允許展開連結預覽（預設關閉）")

    f = sub.add_parser("file", help="發送檔案附件")
    共用(f)
    f.add_argument("--path", type=Path, required=True)
    f.add_argument("--caption")

    ph = sub.add_parser("photo", help="發送圖片")
    共用(ph)
    ph.add_argument("--path", type=Path, required=True)
    ph.add_argument("--caption")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    共用參數 = dict(
        topic=args.topic, chat_id=args.chat_id, thread_id=args.thread_id,
        token_env=args.token_env, team_yaml=args.team_yaml, dry_run=args.dry_run,
    )
    try:
        if args.mode == "text":
            if args.stdin:
                內容 = sys.stdin.read()
            elif args.file_text:
                內容 = args.file_text.read_text(encoding="utf-8")
            else:
                內容 = args.text
            result = send_text(
                內容, parse_mode=args.parse_mode, escape=args.escape,
                on_overflow=args.on_overflow, disable_preview=not args.preview, **共用參數,
            )
        elif args.mode == "file":
            result = send_file(args.path, caption=args.caption, **共用參數)
        else:
            result = send_photo(args.path, caption=args.caption, **共用參數)
    except (ValueError, FileNotFoundError) as e:
        result = {"status": "error", "message": str(e)}

    print(json.dumps(result, ensure_ascii=False, indent=2))
    失敗 = result.get("status") == "error"
    return 1 if (失敗 and args.raise_on_error) else 0


if __name__ == "__main__":
    raise SystemExit(main())
