"""意圖路由器 — LLM 分類 + keyword fallback 雙軌策略。

多層規則判斷訊息該走哪個 agent：
1. 前置 keyword 快速命中（零 LLM 消耗）
2. LLM 路由（分類 + confidence 評分）
3. keyword fallback（LLM 不可用時降級）
4. confidence 門檻規則（低信心強制升級為 TASK）

輸出契約：
  {"route": "CHAT|DIRECT|TASK", "agent": "str|null", "confidence": 0.0, "reason": "str",
   "is_write_operation": bool, "estimated_steps": int, "target_agent": "str|null"}

降級規則：
  - LLM 不可用 / 超時 / JSON 解析失敗 → keyword fallback
  - confidence < CONFIDENCE_MIN → 強制 TASK

環境變數：
  ARK_ROUTER_TIMEOUT_SEC  — LLM 呼叫超時（預設 3s）
  ARK_ROUTER_CONFIDENCE_MIN — 信心門檻（預設 0.6）
  ARK_ROUTER_ENABLED — 功能開關（預設 true）
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time

log = logging.getLogger(__name__)

# ── 設定 ──────────────────────────────────────────────────
ROUTER_TIMEOUT = float(os.getenv("ARK_ROUTER_TIMEOUT_SEC", "3"))
CONFIDENCE_MIN = float(os.getenv("ARK_ROUTER_CONFIDENCE_MIN", "0.6"))

ROUTER_PROMPT = """你是訊息路由器。分析使用者訊息，只回傳純 JSON（禁止 markdown code block 或其他文字）。

路由定義（只有三種）：
- CHAT：不需要 agent 動手的一切 — 問答、翻譯、解釋、摘要、確認、閒聊、問候、語義模糊需澄清
- DIRECT：單一 agent 可獨立完成的明確執行任務（寫 code、查數據、產報告、改檔案）
- TASK：需要拆解、跨領域、多步驟、含驗收要求、目標模糊、**或涉及破壞性/高風險操作（部署 production、刪除資料、重啟服務）**

判斷邏輯：
1. 需要 agent 動手做事？
   → 1 步搞定 → DIRECT
   → 多步/需規劃/高風險 → TASK
2. 不需要動手（純問答/翻譯/確認/閒聊）→ CHAT

特別規則：
- 語義極度模糊（「那個東西怎麼了」「繼續做」）→ CHAT（讓 LLM 追問澄清）
- 涉及 production 部署、批量刪除、重大變更 → 強制 TASK
- 確認型問句（「這樣對嗎」「對不對」）→ CHAT

可指派的 agent（DIRECT / target_agent 時填入）：
{agents}

輸出格式（只回傳 JSON，所有欄位必填）：
{{"route": "CHAT|DIRECT|TASK", "agent": "agent名稱或null", "confidence": 0.0, "reason": "一句話理由", "is_write_operation": false, "estimated_steps": 1, "target_agent": "agent名稱或null"}}"""

# ── keyword 分類表（可自訂） ────────────────────────────────
CHAT_KEYWORDS: list[str] = [
    "嗨", "你好", "哈囉", "hi", "hello", "早安", "晚安", "謝謝", "感謝", "哈哈",
    "什麼是", "解釋", "翻譯", "幫我看", "怎麼說", "意思是", "定義", "天氣",
]
DIRECT_KEYWORDS: list[str] = [
    "寫", "改", "建", "做", "修", "部署", "安裝", "新增", "刪除", "查", "找", "列出",
    "搜尋", "search", "查一下", "找一下", "重啟", "restart",
]
TASK_KEYWORDS: list[str] = [
    "分析", "規劃", "設計", "架構", "spec", "plan", "research", "研究", "評估", "比較", "深入",
]
WRITE_KEYWORDS: list[str] = [
    "部署", "刪除", "重啟", "改", "修", "建", "新增", "安裝", "寫", "deploy", "delete", "write",
]


def _keyword_fallback(text: str, agents: list[str]) -> dict:
    """keyword 兜底，confidence 固定 0.5。"""
    lower = text.lower()
    is_write = any(k in lower for k in WRITE_KEYWORDS)

    if any(k in lower for k in TASK_KEYWORDS):
        return {"route": "TASK", "agent": None, "confidence": 0.5, "reason": "keyword:task",
                "is_write_operation": is_write, "estimated_steps": 3, "target_agent": None}
    if any(k in lower for k in DIRECT_KEYWORDS):
        return {"route": "DIRECT", "agent": None, "confidence": 0.5, "reason": "keyword:direct",
                "is_write_operation": is_write, "estimated_steps": 1, "target_agent": None}
    if any(k in lower for k in CHAT_KEYWORDS):
        return {"route": "CHAT", "agent": None, "confidence": 0.8, "reason": "keyword:chat",
                "is_write_operation": False, "estimated_steps": 1, "target_agent": None}
    # 預設 CHAT（不確定的問題讓 LLM 回答比送 agent 安全）
    return {"route": "CHAT", "agent": None, "confidence": 0.4, "reason": "keyword:default→chat",
            "is_write_operation": False, "estimated_steps": 1, "target_agent": None}


def _apply_confidence_rule(result: dict) -> dict:
    """confidence < CONFIDENCE_MIN 時強制升級為 TASK（寧可慢，不可錯）。"""
    if result.get("confidence", 0) < CONFIDENCE_MIN and result.get("route") != "TASK":
        log.debug("Router confidence %.2f < %.2f，強制 TASK", result["confidence"], CONFIDENCE_MIN)
        result["route"] = "TASK"
        result["agent"] = None
    return result


def _extract_json(text: str) -> dict | None:
    """從 LLM 回應中提取 JSON（容忍 markdown code block）。"""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return None


async def route(
    message: str,
    history: str = "",
    agents: list[str] | None = None,
    *,
    llm_fn=None,
    llm_available_fn=None,
) -> dict:
    """分析訊息，回傳路由決策。

    參數：
      message — 使用者訊息
      history — 對話歷史（可選）
      agents — 可指派的 agent 名稱列表
      llm_fn — async LLM 呼叫函式，簽名 (prompt, system_prompt) -> str
      llm_available_fn — 判斷 LLM 是否可用的函式，回傳 bool

    回傳格式：{route, agent, confidence, reason, is_write_operation, estimated_steps, target_agent}
    任何失敗都降級到 keyword fallback，不拋出 exception。
    """
    agent_list = agents or []
    t0 = time.monotonic()

    # LLM 不可用 → 直接 fallback
    if llm_available_fn and not llm_available_fn():
        log.warning("Router: LLM 不可用，fallback keyword")
        result = _keyword_fallback(message, agent_list)
        return _apply_confidence_rule(result)

    if not llm_fn:
        log.warning("Router: 無 LLM 函式，fallback keyword")
        result = _keyword_fallback(message, agent_list)
        return _apply_confidence_rule(result)

    # 組合 prompt
    agent_desc = "\n".join(f"- {a}" for a in agent_list)
    system = ROUTER_PROMPT.format(agents=agent_desc)
    prompt = message
    if history:
        prompt = f"對話歷史：\n{history}\n\n使用者訊息：{message}"

    try:
        result_raw = await asyncio.wait_for(
            llm_fn(prompt, system),
            timeout=ROUTER_TIMEOUT,
        )
        text = result_raw[0] if isinstance(result_raw, tuple) else result_raw
        if not text:
            result = _keyword_fallback(message, agent_list)
        else:
            parsed = _extract_json(text)
            if not parsed or "route" not in parsed:
                log.warning("Router: JSON 解析失敗，fallback keyword")
                result = _keyword_fallback(message, agent_list)
            else:
                if parsed["route"] not in ("CHAT", "DIRECT", "TASK"):
                    parsed["route"] = "CHAT"
                parsed.setdefault("agent", None)
                parsed.setdefault("confidence", 0.5)
                parsed.setdefault("reason", "")
                parsed.setdefault("is_write_operation", False)
                parsed.setdefault("estimated_steps", 1)
                parsed.setdefault("target_agent", None)
                result = _apply_confidence_rule(parsed)

    except asyncio.TimeoutError:
        log.warning("Router: 超時（%.1fs），fallback keyword", ROUTER_TIMEOUT)
        result = _keyword_fallback(message, agent_list)
    except Exception as e:
        log.warning("Router: 失敗 %s，fallback keyword", e)
        result = _keyword_fallback(message, agent_list)

    latency_ms = (time.monotonic() - t0) * 1000
    log.debug("Router: %s (%.0fms)", result.get("route"), latency_ms)
    return result
