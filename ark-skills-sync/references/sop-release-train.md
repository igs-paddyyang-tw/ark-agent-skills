# SOP —— 發列車與對齊通知

1. 內容 commit 都推上去、工作樹乾淨，`audit_skills.py --repo .` P0／P1＝0
2. 產 manifest（**另開一個 commit**，不要 amend 進內容 commit —— manifest 記的 commit 會變孤兒）：
   ```bash
   python3 ark-skills-sync/scripts/gen_manifest.py --repo . --release skills-YYYY.MM-rN --out ark-skills-sync/release
   git commit -m "chore(release): 列車 skills-YYYY.MM-rN manifest" -- ark-skills-sync/release/index.json ark-skills-sync/release/manifest.json
   ```
   ⚠️ 不帶 `--out` 會寫到 repo 根 `release/`（錯位置）。r40 以前的 manifest 在 `ark-skills-align/release/`，查歷史的腳本兩個路徑都認。
3. 有改名／刪除／併入（major 或契約變更）：
   ```bash
   python3 scripts/check_consumers.py --impact --json impact.json
   python3 ark-skills-sync/scripts/notice_build.py impact.json --out docs/reports/review/<date>-align-notice.md
   ```
4. pre-push hook 只在「這次推送刪掉 skill」時檢查消費端矩陣（擋）與已部署複本（警告）
