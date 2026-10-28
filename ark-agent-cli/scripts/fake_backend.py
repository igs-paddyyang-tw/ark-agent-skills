#!/usr/bin/env python3
"""fake_backend — 測試用假 CLI：讀 stdin 的 prompt，模擬一個會寫 checkpoint 的 sub-agent。

行為由 prompt 內的 `[[FAKE: ...]]` 指令或環境變數 ARK_FAKE_SCRIPT 控制：
  segments=N      第 N 段才回 done（之前回 continue）
  blocked         回 blocked
  no_checkpoint   第 1 段不寫 checkpoint（測 nudge 重試）
  crash           非零退出
每段把 prompt 裡 `checkpoint_path: <path>` 指到的檔寫成 checkpoint JSON。
"""
import json
import os
import re
import sys
import time

# Windows 預設 stdout 編碼為 cp950/cp1252，輸出非 ASCII（如 ▸、中文）會 UnicodeEncodeError，強制 UTF-8
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8")

prompt = sys.stdin.read()
m = re.search(r"checkpoint_path: (\S+)", prompt)
seg = int(re.search(r"segment: (\d+)", prompt).group(1)) if re.search(r"segment: (\d+)", prompt) else 1
fm = re.search(r"\[\[FAKE: ([^\]]+)\]\]", prompt)
script = os.getenv("ARK_FAKE_SCRIPT", "") or (fm.group(1) if fm else "segments=2")
if "crash" in script:
    print("boom", file=sys.stderr); sys.exit(1)
time.sleep(float(os.getenv("ARK_FAKE_SLEEP", "0.2")))
if "no_checkpoint" in script and seg == 1 and "⚠️ nudge" not in prompt:
    print("我做了一些事但忘了寫 checkpoint"); sys.exit(0)
want = int(re.search(r"segments=(\d+)", script).group(1)) if re.search(r"segments=(\d+)", script) else 2
status = "blocked" if "blocked" in script else ("done" if seg >= want else "continue")
cp = {"status": status, "progress": f"segment {seg}/{want} 完成", "next": "" if status != "continue" else f"繼續第 {seg + 1} 段",
      "evidence": [f"fake-evidence-{seg}.txt"], "notes": ["fake note"], "reason": "fake blocked reason" if status == "blocked" else "",
      "summary": "fake 任務完成摘要" if status == "done" else ""}
if m:
    try:
        with open(m.group(1), "w", encoding="utf-8") as f:
            json.dump(cp, f, ensure_ascii=False)
    except OSError:
        pass  # /dev/null、nul 等不可寫路徑在測試中可忽略
print(f"\x1b[32m> 第 {seg} 段完成\x1b[0m\n▸ Time: 0.2s\n" + json.dumps(cp, ensure_ascii=False))
