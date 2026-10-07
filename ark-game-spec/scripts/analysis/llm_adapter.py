"""多模態 LLM adapter（ADR-007）：腳本呼叫、模型釘版、快取、structured JSON。

provider（環境變數 ARK_LLM_PROVIDER）:
  anthropic  ANTHROPIC_API_KEY（可選 ANTHROPIC_BASE_URL），模型 ARK_LLM_MODEL
  gemini     GEMINI_API_KEY，模型 ARK_LLM_MODEL
  module     ARK_LLM_ADAPTER_MODULE=path/to/adapter.py，需提供 complete(prompt, images, system) -> str
             （接 ark-llm-tools 的 LLMAdapter / GeminiAdapter 用這條）
  fake       離線 deterministic 假回覆（測試 / 無憑證）；ARK_FAKE_ANSWERS=<json> 可指定固定回覆

快取 key = sha256(provider, model, system, prompt, images sha, pack_sha)；同輸入重跑零費用。
stdout 保持乾淨：本模組永不 print。
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import pathlib
import re
import time
import urllib.error
import urllib.request

DEFAULT_MODEL = {"anthropic": "claude-sonnet-4-6", "gemini": "gemini-2.5-flash"}
MAX_RETRY = 2


class LLMError(Exception):
    def __init__(self, code: str, msg: str, hint: str = ""):
        super().__init__(msg)
        self.code, self.hint = code, hint


def provider() -> str:
    return os.getenv("ARK_LLM_PROVIDER", "fake").lower()


def model_name() -> str:
    return os.getenv("ARK_LLM_MODEL", DEFAULT_MODEL.get(provider(), "fake"))


def _cache_dir(run: pathlib.Path | None) -> pathlib.Path:
    d = pathlib.Path(os.getenv("ARK_LLM_CACHE_DIR", str((run or pathlib.Path(".")) / ".cache" / "llm")))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _img_b64(path: pathlib.Path) -> tuple[str, str]:
    data = path.read_bytes()
    mt = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return base64.b64encode(data).decode(), mt


def _strip_json(text: str) -> str:
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    m = re.search(r"\{.*\}", t, re.S)
    return m.group(0) if m else t


class Adapter:
    def __init__(self, run: pathlib.Path | None = None, pack_sha: str = "", budget: dict | None = None):
        self.run, self.pack_sha = run, pack_sha
        self.calls = 0
        self.cache_hits = 0
        self.budget = budget or {}
        self.max_calls = int(os.getenv("ARK_LLM_MAX_CALLS", self.budget.get("max_llm_calls", 40)))
        self.hard_max = int(self.budget.get("hard_max", {}).get("max_llm_calls", 120))
        self.fake_answers = None
        if os.getenv("ARK_FAKE_ANSWERS"):
            self.fake_answers = json.loads(pathlib.Path(os.environ["ARK_FAKE_ANSWERS"]).read_text(encoding="utf-8"))

    # ------------------------------------------------------------ public
    def complete_json(self, system: str, prompt: str, images: list[pathlib.Path] | None = None,
                      fake_key: str | None = None, fake_fn=None) -> dict:
        """回傳 dict（已解析 JSON）。schema 違規由呼叫端處理；解析失敗重試 ≤ MAX_RETRY。"""
        images = images or []
        key = hashlib.sha256(json.dumps([provider(), model_name(), system, prompt, self.pack_sha,
                                         [hashlib.sha256(p.read_bytes()).hexdigest() for p in images]]).encode()).hexdigest()
        cp = _cache_dir(self.run) / f"{key}.json"
        if cp.exists() and provider() != "fake":  # fake 不走快取（測試要能換 ARK_FAKE_*）
            self.cache_hits += 1
            return json.loads(cp.read_text(encoding="utf-8"))
        if self.calls >= self.max_calls:
            raise LLMError("BUDGET_EXCEEDED", f"LLM 呼叫數達上限 {self.max_calls}",
                           "縮小 --t-range、提高 --max-llm-calls（不可超過 pack hard_max）")
        if self.max_calls > self.hard_max:
            raise LLMError("BUDGET_EXCEEDED", f"--max-llm-calls {self.max_calls} 超過 pack hard_max {self.hard_max}", "")
        last_err = None
        for attempt in range(MAX_RETRY + 1):
            self.calls += 1
            raw = self._call(system, prompt if attempt == 0 else prompt + "\n\n（上一輪不是合法 JSON，只輸出 JSON object，不要任何說明或 code fence）",
                             images, fake_key, fake_fn)
            try:
                obj = json.loads(_strip_json(raw))
                if not isinstance(obj, dict):
                    raise ValueError("not an object")
                cp.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
                return obj
            except ValueError as e:  # noqa: PERF203
                last_err = e
        raise LLMError("QUERY_FAILED", f"模型回覆無法解析為 JSON（重試 {MAX_RETRY} 次）: {last_err}", "檢查 prompt 是否要求純 JSON")

    # ------------------------------------------------------------ providers
    def _call(self, system, prompt, images, fake_key, fake_fn) -> str:
        p = provider()
        if p == "fake":
            return self._fake(system, prompt, images, fake_key, fake_fn)
        if p == "anthropic":
            return self._anthropic(system, prompt, images)
        if p == "gemini":
            return self._gemini(system, prompt, images)
        if p == "module":
            return self._module(system, prompt, images)
        raise LLMError("BAD_INPUT", f"未知 ARK_LLM_PROVIDER={p}", "anthropic | gemini | module | fake")

    def _fake(self, system, prompt, images, fake_key, fake_fn) -> str:
        if self.fake_answers and fake_key in self.fake_answers:
            return json.dumps(self.fake_answers[fake_key], ensure_ascii=False)
        if fake_fn:
            return json.dumps(fake_fn(), ensure_ascii=False)
        return "{}"

    def _http(self, url: str, headers: dict, body: dict, timeout: int = 120) -> dict:
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return json.loads(r.read().decode())
            except urllib.error.HTTPError as e:
                detail = e.read().decode(errors="replace")[:300]
                if e.code in (429, 500, 502, 503, 529) and attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                if e.code in (401, 403):
                    raise LLMError("CONN_FAILED", f"認證失敗 {e.code}: {detail}", "檢查 API key 環境變數") from None
                raise LLMError("QUERY_FAILED", f"HTTP {e.code}: {detail}", "") from None
            except urllib.error.URLError as e:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                raise LLMError("CONN_FAILED", f"連線失敗: {e}", "檢查網路 / proxy allowlist") from None
        raise LLMError("CONN_FAILED", "重試耗盡", "")

    def _anthropic(self, system, prompt, images) -> str:
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise LLMError("CONN_FAILED", "未設 ANTHROPIC_API_KEY", "export ANTHROPIC_API_KEY=... 或改用 ARK_LLM_PROVIDER=module")
        content = []
        for p in images:
            b64, mt = _img_b64(p)
            content.append({"type": "image", "source": {"type": "base64", "media_type": mt, "data": b64}})
        content.append({"type": "text", "text": prompt})
        body = {"model": model_name(), "max_tokens": int(os.getenv("ARK_LLM_MAX_TOKENS", "4000")), "temperature": 0,
                "system": system, "messages": [{"role": "user", "content": content}]}
        base = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")
        j = self._http(f"{base}/v1/messages", {"x-api-key": key, "anthropic-version": "2023-06-01"}, body)
        return "".join(b.get("text", "") for b in j.get("content", []) if b.get("type") == "text")

    def _gemini(self, system, prompt, images) -> str:
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise LLMError("CONN_FAILED", "未設 GEMINI_API_KEY", "")
        parts = [{"text": system + "\n\n" + prompt}]
        for p in images:
            b64, mt = _img_b64(p)
            parts.append({"inline_data": {"mime_type": mt, "data": b64}})
        body = {"contents": [{"parts": parts}], "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}}
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name()}:generateContent?key={key}"
        j = self._http(url, {}, body)
        try:
            return j["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            raise LLMError("QUERY_FAILED", f"Gemini 回覆結構異常: {str(j)[:200]}", "") from None

    def _module(self, system, prompt, images) -> str:
        path = os.getenv("ARK_LLM_ADAPTER_MODULE")
        if not path or not pathlib.Path(path).exists():
            raise LLMError("DRIVER_MISSING", "ARK_LLM_ADAPTER_MODULE 未設或不存在", "指向提供 complete(prompt, images, system) 的 .py")
        import importlib.util
        spec = importlib.util.spec_from_file_location("ark_llm_ext", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod.complete(prompt=prompt, images=[str(p) for p in images], system=system)

    def meta(self) -> dict:
        return {"provider": provider(), "model": model_name(), "llm_calls": self.calls, "cache_hits": self.cache_hits}
