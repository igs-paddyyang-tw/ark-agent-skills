#!/usr/bin/env python3
"""fake_backend — 測試用假 CLI：讀 stdin 的 prompt，模擬一個會寫 checkpoint 的 sub-agent。

行為由 prompt 內的 `[[FAKE: ...]]` 指令或環境變數 ARK_FAKE_SCRIPT 控制：
  segments=N      第 N 段才回 done（之前回 continue）
  blocked         回 blocked
  no_checkpoint   第 1 段不寫 checkpoint（測 nudge 重試）
  crash           非零退出
  idle_from=K     第 K 段起 actions=0、evidence_new=0、progress / metrics 不變（測空轉熔斷）
  linger=S        寫完 checkpoint 後再睡 S 秒才退出（測 handoff grace kill）
  usage           輸出含 usage 的 JSON 行（測用量統計）
  list_actions    actions／evidence_new 寫成清單（測 2.4.2 U-1 容錯）
  stdout_only     不寫 checkpoint 檔，只把 JSON 印在輸出最後（測 read-only 退路，U-5）
每段把 prompt 裡 `checkpoint_path: <path>` 指到的檔寫成 checkpoint JSON。
"""
import json
import os
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
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
idle_from = int(re.search(r"idle_from=(\d+)", script).group(1)) if re.search(r"idle_from=(\d+)", script) else 10**9
status = "blocked" if "blocked" in script else ("done" if seg >= want else "continue")
idle = seg >= idle_from
cp = {"status": status, "progress": "沒有新進展" if idle else f"segment {seg}/{want} 完成", "next": "" if status != "continue" else f"繼續第 {seg + 1} 段",
      "evidence": [] if idle else [f"fake-evidence-{seg}.txt"], "notes": ["fake note"], "actions": 0 if idle else 3, "evidence_new": 0 if idle else 1,
      "metrics": {"spins": 0 if idle else seg * 10}, "reason": "fake blocked reason" if status == "blocked" else "", "summary": "fake 任務完成摘要" if status == "done" else ""}
if "list_actions" in script:
    cp["actions"] = ["讀檔", "跑測試", "寫報告"]; cp["evidence_new"] = ["fake-evidence.txt"]
if m and "stdout_only" not in script:
    with open(m.group(1), "w", encoding="utf-8") as f:
        json.dump(cp, f, ensure_ascii=False)
print(f"\x1b[32m> 第 {seg} 段完成\x1b[0m\n▸ Time: 0.2s\n" + json.dumps(cp, ensure_ascii=False))
if "usage" in script:
    print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 1000 * seg, "output_tokens": 50}}))
lm = re.search(r"linger=([\d.]+)", script)
if lm:
    time.sleep(float(lm.group(1)))
