"""md_to_image — 從 Markdown 文案產出 16:9 圖片（OpenAI DALL-E）。"""
from __future__ import annotations

import os
from pathlib import Path

from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType


class MdToImageParams(SkillParam):
    """md_to_image 輸入參數。"""
    markdown: str = ""
    style: str = "modern"  # modern / minimalist / vibrant / dark
    output_name: str = "slide"


class MdToImageSkill(BaseSkill):
    skill_id = "md_to_image"
    skill_type = SkillType.PYTHON
    description = "從 Markdown 文案產出 16:9 圖片（OpenAI DALL-E 3）"
    version = "1.0.0"
    input_schema = MdToImageParams

    async def execute(self, params: dict) -> SkillResult:
        try:
            p = MdToImageParams(**params)
            if not p.markdown:
                return SkillResult(success=False, error="需提供 markdown 文案")

            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                return SkillResult(success=False, error="OPENAI_API_KEY 未設定")

            prompt = self._build_prompt(p.markdown, p.style)

            # 呼叫 OpenAI Image API
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            resp = client.images.generate(
                model="gpt-image-1",
                prompt=prompt,
                size="1536x1024",
                n=1,
            )

            image_b64 = resp.data[0].b64_json

            # 存圖片
            import base64
            out_dir = Path("output/images")
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"{p.output_name}.png"
            out_path.write_bytes(base64.b64decode(image_b64))

            return SkillResult(success=True, data={
                "image_path": str(out_path),
                "style": p.style,
            })
        except Exception as e:
            return SkillResult(success=False, error=str(e))

    def _build_prompt(self, markdown: str, style: str) -> str:
        """從 MD 文案組裝 DALL-E prompt。"""
        style_hints = {
            "modern": "modern, clean, professional design with bold typography",
            "minimalist": "minimalist, lots of whitespace, elegant and simple",
            "vibrant": "vibrant colors, energetic, eye-catching gradient background",
            "dark": "dark background, neon accents, tech-inspired aesthetic",
        }
        hint = style_hints.get(style, style_hints["modern"])

        return (
            f"Create a presentation-style visual graphic (16:9 landscape ratio). "
            f"Style: {hint}. "
            f"The image should visually communicate the following content as an infographic or key visual, "
            f"NOT as a screenshot of text. Use icons, illustrations, and minimal text labels. "
            f"Content:\n{markdown[:500]}"
        )
