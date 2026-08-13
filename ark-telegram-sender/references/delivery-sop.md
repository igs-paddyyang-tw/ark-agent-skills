# Telegram 送達 SOP

> 適用：日報／報告／告警等「有附件的長內容」推送。
> 實作見 `scripts/tg_send.py`。本文記錄的是**為什麼這樣送**，照抄參數不看理由會再踩一次。

---

## 1. 兩段式送達

長內容一律拆成兩則：

```
① 文字摘要（人在手機上就能讀完的長度）
② HTML 附件（完整版）
```

**不要把長內容硬切成多則文字訊息。** 一份日報切成三則會洗版，讀者也拼不回來 ——
而且中間任一則失敗，剩下的就是殘篇。摘要截斷 + 附件補完，失敗時至少摘要是完整的一則。

摘要要標明「其餘 N 則見附件」。靜默少講幾則，讀者不會知道自己漏看了。

| 段 | 失敗的意義 | 是否算出刊失敗 |
|----|-----------|:---:|
| 文字摘要 | 讀者完全沒收到通知 | ✅ 是 |
| HTML 附件 | 讀者收到通知但看不到完整版 | ❌ 否（加值，不是必要） |

---

## 2. 失敗語意：一律回傳，不拋例外

```python
r = send_text(...)
if r["status"] != "success":     # ← 這行不能省
    ...
```

**只用 `try/except` 判定會把失敗當成功。** 這是 ninja 的 D27 缺陷：
`push_to_topic()` 以回傳值表示失敗、不拋例外，呼叫端只包了 try/except，
於是連續三天回報「出刊成功」而實際上一則都沒送出去。

需要例外語意時用 CLI 的 `--raise-on-error`（非 0 結束碼）或自行檢查後 raise。

### 錯誤描述要取自 response body

`urllib` 在 4xx 拋 `HTTPError`，`str(e)` 只會給「HTTP Error 400: Bad Request」。
真正的原因在 body 的 `description`：

```
HTTP 400: Bad Request: can't parse entities: Can't find end tag corresponding to start tag "b"
```

差別是值班的人要查五分鐘還是五十分鐘。`tg_send.py` 已內建，自行實作時別漏。

---

## 3. 逸出決策

`parse_mode=HTML` 時，內容裡的 `<b>` 是**格式**還是**字面文字**，取決於誰產生它：

```
內容由渲染層產生（已自己逸出過使用者內容）→ escape=never  或 auto
內容是純文字（使用者輸入、log、LLM 純文字輸出）→ escape=always 或 auto
不確定 → auto
```

`auto` 的判準是「內容裡有沒有 Telegram 認得的標籤」（`<b>` `<i>` `<a href=` `<code>` …）。

兩種踩法都出現過：

| 做法 | 症狀 |
|------|------|
| 一律逸出 | LLM 產出的 `<b>` 變成 `&lt;b&gt;`，滿螢幕跳脫字元（paddy-team 實例，靠 prompt 加 `style="report"` 繞過） |
| 一律不逸出 | 內容裡一個 `<` 就讓整則訊息回 400 |

---

## 4. 長度與大小

| 限制 | 值 | 超過的行為 |
|------|---:|-----------|
| 文字訊息 | 4096 字元 | 整則 400 |
| caption（附件說明） | 1024 字元 | 整則 400 |
| 檔案 | 50 MB | 上傳失敗（要更大得自架 local Bot API server） |

**實作用 4000 而非 4096**：Telegram 以 UTF-16 code unit 計長，中日文與 emoji 的
計法與 Python `len()` 不同，貼著上限送會偶發 400。

### 截斷一定要在邊界

```python
text[:3900]          # ❌ 會切在 HTML 標籤中間 → 400
_cut_at_boundary()   # ✅ 段落 → 換行 → 最後一個 `>`，逐級退讓
```

ninja 2026-08-13 的競品刊就是死在第一種寫法：24 則的摘要超長，硬切留下
`<b><a href="https://…` 未閉合結構，Telegram 直接拒收。**更好的做法是在組裝時
就以「則」為單位控制預算**，字串永遠在標籤邊界結束，不需要事後修補。

---

## 5. Forum topic

群組開了 Forum（`is_forum: true`）之後，`chat_id` 不足以定位訊息位置，
還要 `message_thread_id`。漏了會全部發到 General 區。

topic 名稱只維護一份，放在 `team.yaml`：

```yaml
channel:
  group_id: -100xxxxxxxxxx
  bot_token_env: TELEGRAM_BOT_TOKEN_GA   # ← 不是每個專案都叫 TELEGRAM_BOT_TOKEN
topics:
  daily_report: 2
  assistant_chat: 1
  ops_alert: 1447
```

解析優先序：`--chat-id` > `--topic`（查 team.yaml） > 環境變數 `TELEGRAM_CHAT_ID`。

**不要在程式裡硬編 topic 數字**：頻道重整時必然漏改，而且錯了不會報錯 ——
訊息會安靜地發到別區。

---

## 6. 常見 400 與對策

| description 片段 | 原因 | 對策 |
|------------------|------|------|
| `can't parse entities: Can't find end tag` | 標籤未閉合（多半是截斷造成） | 見 §4 |
| `can't parse entities: Unsupported start tag` | 用了 Telegram 不支援的標籤（`<div>`／`<p>`／`<br>`） | 只用 `b i u s a code pre blockquote tg-spoiler` |
| `message thread not found` | topic 被刪或 ID 過期 | 重新取得 topic ID，更新 team.yaml |
| `message is too long` | 超過 4096 | 見 §4 |
| `chat not found` | Bot 未加入群組／被踢 | 重新邀請並給發言權限 |
| `Too Many Requests` (429) | 觸發速率限制 | 依 `parameters.retry_after` 等待後重試（`tg_send.py` 已內建） |

---

## 7. 測試守則

**測試絕不真送。** 一律 `--dry-run` 或注入假的發送函式。

ninja 曾因為把未審的 importlib fallback 順手 commit，讓測試真的往正式頻道送訊息
（`885ea60`）。現在 conftest 有 autouse 防護擋住對外送出與知識庫寫入 ——
新增任何發送管道時，記得一併納入防護，否則防護只擋得住舊路徑。

驗收真送時，送到 **通報區（ops_alert）而非日報區**，並在內容標明是測試。
