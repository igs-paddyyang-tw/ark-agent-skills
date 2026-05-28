"""build_ai_bot.py — 一鍵建置 ai-bot（串接所有 scaffold 腳本）。

用法：python scripts/build_ai_bot.py [project_dir]
"""
import sys
from pathlib import Path

def main():
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    target.mkdir(parents=True, exist_ok=True)

    from scaffold_project import scaffold as s1
    from scaffold_bot import scaffold as s2
    from scaffold_scheduler import scaffold as s3
    from scaffold_scraper import scaffold as s5

    total = []
    total += s1(target)
    total += s2(target)
    total += s3(target)

    try:
        from scaffold_llm_cli import scaffold as s4
        total += s4(target)
    except ImportError:
        print("⚠️ scaffold_llm_cli 不存在，跳過 LLM CLI 步驟")

    total += s5(target)

    print(f"\n✅ ai-bot 建置完成！共產出 {len(total)} 個檔案")
    print("   1. 填入 .env（TELEGRAM_BOT_TOKEN）")
    print("   2. 登入 Gemini CLI：gemini")
    print("   3. 啟動：python -m src.bot.main")


if __name__ == "__main__":
    main()
