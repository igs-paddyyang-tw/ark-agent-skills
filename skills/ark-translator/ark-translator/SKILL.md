---
name: ark-translator
description: |
  產出 translator.py 多語言翻譯 Skill，搭配 Gemini LLM 進行高品質翻譯，
  支援繁體中文、簡體中文、英文、日文互譯。
  保留 Markdown 格式與程式碼區塊不翻譯，支援批次翻譯。
  使用此 Skill 當使用者提及翻譯、translate、多語言、i18n、
  中翻英、英翻中、日翻中、或任何需要語言轉換的場景。
---

# ark-translator

產出 `src/skills/llm_skills/translator.py`，搭配 Gemini LLM 進行多語言翻譯，可獨立運作。

## 觸發條件

使用者提及以下關鍵字時觸發：
- 「翻譯」、「translate」、「多語言」
- 「中翻英」、「英翻中」、「日翻中」
- 「i18n」、「語言轉換」
- 「翻成日文」、「翻成英文」

## 核心概念

```
原文 → translator（Gemini LLM）→ 譯文（保留格式）
```

支援語言：

| 代碼 | 語言 |
|------|------|
| `zh-TW` | 繁體中文 |
| `zh-CN` | 簡體中文 |
| `en` | 英文 |
| `ja` | 日文 |

## 輸入參數

| 參數 | 型別 | 必要 | 預設值 | 說明 |
|------|------|------|--------|------|
| `text` | `str` | ✅ | — | 待翻譯文字（支援 Markdown） |
| `source_lang` | `str` | ❌ | `"auto"` | 來源語言代碼（auto 自動偵測） |
| `target_lang` | `str` | ✅ | — | 目標語言代碼（`zh-TW` / `zh-CN` / `en` / `ja`） |
| `preserve_format` | `bool` | ❌ | `True` | 是否保留 Markdown 格式與程式碼區塊 |

## 產出檔案

- `src/skills/llm_skills/translator.py`

---

## 產出指引

### 步驟 1：建立參數模型

```python
from src.skills.base import SkillParam

class TranslatorParams(SkillParam):
    """translator 輸入參數。"""
    text: str
    source_lang: str = "auto"
    target_lang: str
    preserve_format: bool = True
```

### 步驟 2：實作 Skill 類別

```python
class TranslatorSkill(BaseSkill):
    skill_id = "translator"
    skill_type = SkillType.LLM
    description = "多語言翻譯（搭配 Gemini），支援繁中/簡中/英/日互譯"
    version = "1.0.0"
    input_schema = TranslatorParams

    LANG_NAMES: dict[str, str] = {
        "zh-TW": "繁體中文",
        "zh-CN": "簡體中文",
        "en": "English",
        "ja": "日本語",
    }
```

### 步驟 3：實作 execute 方法

```python
async def execute(self, params: dict) -> SkillResult:
    try:
        p = TranslatorParams(**params)

        if p.target_lang not in self.LANG_NAMES:
            return SkillResult(
                success=False,
                error=f"不支援的目標語言: {p.target_lang}，支援: {list(self.LANG_NAMES.keys())}",
            )

        # 保留格式：提取程式碼區塊，翻譯後還原
        if p.preserve_format:
            text_to_translate, code_blocks = self._extract_code_blocks(p.text)
        else:
            text_to_translate = p.text
            code_blocks = []

        # 組裝 prompt
        prompt = self._build_prompt(text_to_translate, p.source_lang, p.target_lang)

        # 呼叫 LLM（透過 LLMAdapter，使用 CLOUD tier = Gemini）
        translated = await self.llm_adapter.generate(
            prompt=prompt,
            tier="CLOUD",
        )

        # 還原程式碼區塊
        if p.preserve_format and code_blocks:
            translated = self._restore_code_blocks(translated, code_blocks)

        return SkillResult(success=True, data={
            "translated_text": translated,
            "source_lang": p.source_lang,
            "target_lang": p.target_lang,
            "char_count": len(p.text),
        })
    except Exception as e:
        return SkillResult(success=False, error=f"翻譯失敗: {e}")
```

### 步驟 4：實作輔助方法

#### _build_prompt — 組裝翻譯 prompt

```python
def _build_prompt(self, text: str, source_lang: str, target_lang: str) -> str:
    """組裝翻譯用 prompt。"""
    target_name = self.LANG_NAMES[target_lang]
    source_hint = ""
    if source_lang != "auto":
        source_name = self.LANG_NAMES.get(source_lang, source_lang)
        source_hint = f"來源語言為 {source_name}。"

    return (
        f"你是專業翻譯員。{source_hint}"
        f"請將以下文字翻譯為 {target_name}。\n"
        f"規則：\n"
        f"- 保持原文的語氣與風格\n"
        f"- 保留 Markdown 格式（標題、列表、粗體等）\n"
        f"- 專有名詞保留原文或附註原文\n"
        f"- 只輸出譯文，不要加任何解釋\n\n"
        f"原文：\n{text}"
    )
```

#### _extract_code_blocks — 提取程式碼區塊

```python
def _extract_code_blocks(self, text: str) -> tuple[str, list[str]]:
    """提取 Markdown 程式碼區塊，以佔位符替代。"""
    import re
    code_blocks: list[str] = []
    pattern = r"```[\s\S]*?```|`[^`\n]+`"

    def replacer(match: re.Match) -> str:
        code_blocks.append(match.group(0))
        return f"__CODE_BLOCK_{len(code_blocks) - 1}__"

    cleaned = re.sub(pattern, replacer, text)
    return cleaned, code_blocks
```

#### _restore_code_blocks — 還原程式碼區塊

```python
def _restore_code_blocks(self, text: str, code_blocks: list[str]) -> str:
    """將佔位符還原為原始程式碼區塊。"""
    import re
    def replacer(match: re.Match) -> str:
        idx = int(match.group(1))
        return code_blocks[idx] if idx < len(code_blocks) else match.group(0)

    return re.sub(r"__CODE_BLOCK_(\d+)__", replacer, text)
```

---

## 輸出格式

```json
{
  "success": true,
  "data": {
    "translated_text": "This is the translated content.",
    "source_lang": "auto",
    "target_lang": "en",
    "char_count": 42
  }
}
```

Workflow YAML 串接範例：

```yaml
- id: translate_doc
  type: skill
  skill: translator
  params:
    text: "{{ outputs.fetch_content }}"
    target_lang: "en"
    preserve_format: true
  output: translated

- id: export
  type: skill
  skill: file_export
  params:
    content: "{{ outputs.translated.translated_text }}"
    filename: "README_en.md"
  output: file
```

## 注意事項

- LLM 呼叫必須透過 `LLMAdapter`，使用 CLOUD tier（Gemini）以確保翻譯品質
- `preserve_format=True` 時，程式碼區塊（`` ` `` 與 ` ``` `）會被提取後原封不動還原
- `source_lang="auto"` 時由 LLM 自動判斷來源語言
- 長文本建議分段翻譯（每段 < 3000 字元），避免 LLM token 上限
- 批次翻譯可在 Workflow 中搭配迴圈步驟實現
- 專有名詞（品牌名、技術術語）可能需要人工校對
