"""aiqa_economy — economy 連轉核帳的 batch 轉接層（observations → ledger → item verdict）。

工作流接線點（`aiqa_run --mode batch`）：economy checklist 於 `repeat` 內逐手讀 credit 前後
（cb/ca）、bet、win → observations 得同名 list。本模組把那串讀數逐手組 `Spin` 餵進
`aiqa_ledger.classify()`，取代單轉守恆 oracle，壓外部加幣/未讀 win 誤報。

🔑 credit 為真相（真機發現 fuxing3 win ROI 大獎動畫期高估）：
- 逐手以 credit delta 為真相；win 讀數僅當**穩定（非 None）且與 credit delta 自洽**
  （`|（cb − ca） − (bet − win)| ≤ tol`）才採用，否則 `win=None`（→ ledger 判 NEEDS_HUMAN）。
- 效果：不穩 win 不會誤判 SINGLE_OFF（假陽性），退化為 NEEDS_HUMAN（穩健、不誤 FAIL）。

純函式、無 I/O：可被 aiqa_run 與離線測試共用（量測即規格）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aiqa_ledger import Spin, Verdict, classify, has_fail  # noqa: E402

# economy 讀數的預設 observation 名稱（可由 item.economy 覆寫）
DEFAULT_NAMES = {"credit_before": "cb", "bet": "bet", "win": "win", "credit_after": "ca"}


def is_economy_item(item: dict, obs: dict) -> tuple[bool, dict]:
    """判斷是否為 economy batch 項，並回解析後的讀數名稱對應。

    觸發條件（任一）：
    - item 明寫 `economy: true` 或 `economy: {...}`（可帶 names 覆寫）。
    - observations 同時含預設四名（cb/bet/win/ca）且皆為 list（逐手累積）。
    """
    spec = item.get("economy")
    names = dict(DEFAULT_NAMES)
    if isinstance(spec, dict):
        names.update(spec.get("names") or {})
        return True, names
    if spec is True:
        return True, names
    if spec is False:
        return False, names
    # 自動偵測：四個預設讀數名皆存在且為 list
    if all(isinstance(obs.get(names[k]), list) for k in names):
        return True, names
    return False, names


def _coerce_win(cb: float, ca: float, bet: float, win, *, tol: float) -> float | None:
    """credit-primary：win 僅當穩定且與 credit delta 自洽才採用，否則 None。

    自洽判準：`|（cb − ca） − (bet − win)| ≤ tol`
      （credit 實際變動 vs 由 bet/win 推得的理論變動一致）。
    """
    if win is None:
        return None
    try:
        actual_delta = float(cb) - float(ca)          # 這手扣掉的淨額（花 bet、得 win）
        implied_delta = float(bet) - float(win)        # 由讀數推得的淨額
    except (TypeError, ValueError):
        return None
    if abs(actual_delta - implied_delta) <= tol:
        return float(win)
    return None  # win 讀數與 credit 不自洽（疑大獎動畫期高估）→ 當未讀


def build_spins(obs: dict, names: dict, *, tol: float = 1.0) -> list[Spin]:
    """從 observations 逐手組 Spin（credit-primary 處理 win）。

    以四個 list 的最短長度對齊（避免某讀數少一手時越界）。
    """
    cb = obs.get(names["credit_before"]) or []
    bet = obs.get(names["bet"]) or []
    win = obs.get(names["win"]) or []
    ca = obs.get(names["credit_after"]) or []
    n = min(len(cb), len(bet), len(win), len(ca))
    spins: list[Spin] = []
    for i in range(n):
        spins.append(
            Spin(
                credit_before=float(cb[i]) if cb[i] is not None else 0.0,
                bet=float(bet[i]) if bet[i] is not None else 0.0,
                win=_coerce_win(cb[i], ca[i], bet[i], win[i], tol=tol),
                credit_after=float(ca[i]) if ca[i] is not None else 0.0,
            )
        )
    return spins


def reconcile(obs: dict, names: dict, *, tol: float = 1.0) -> dict:
    """逐手核帳 + 彙總，回 {verdict, reason, counts, rows, spins}。

    item verdict 映射：
    - 有 SINGLE_OFF / STREAK_OFF → FAIL（人為少錢/漏派彩）。
    - 否則有 NEEDS_HUMAN → NEEDS_HUMAN（win 讀不到、餘額對不上 → 人覆核）。
    - 否則 → PASS（全 OK / 外部加幣 / 基準失效）。
    """
    spins = build_spins(obs, names, tol=tol)
    if not spins:
        return {"verdict": "NEEDS_HUMAN", "reason": "economy batch：無可核帳的連轉讀數",
                "counts": {}, "rows": [], "spins": 0}
    results = classify(spins, tol=tol)
    counts: dict[str, int] = {}
    for r in results:
        counts[r.verdict.value] = counts.get(r.verdict.value, 0) + 1
    rows = [{"i": r.index, "verdict": r.verdict.value, "diff": r.diff, "detail": r.detail} for r in results]
    if has_fail(results):
        verdict, reason = "FAIL", f"連轉核帳不符（{counts}）"
    elif any(r.verdict is Verdict.NEEDS_HUMAN for r in results):
        verdict, reason = "NEEDS_HUMAN", f"連轉核帳有需覆核項（{counts}）"
    else:
        verdict, reason = "PASS", f"連轉核帳守恆（{counts}）"
    return {"verdict": verdict, "reason": reason, "counts": counts, "rows": rows, "spins": len(spins)}
