"""[1] Gemini(Imagen)로 완성 그림 1장을 생성한다.

방법 A: 완성본 1장만 AI로 생성하고, 이후 stages.py 에서
스케치/색칠/묘사 단계를 역산한다. 그래서 여기서는 딱 1장만 만든다.

필요 환경변수: GEMINI_API_KEY  (Google AI Studio에서 발급)
"""
from __future__ import annotations

import io
import os
from pathlib import Path

from PIL import Image


def generate_final_image(
    prompt: str,
    out_path: str | Path,
    model: str = "imagen-3.0-generate-002",
    aspect_ratio: str = "16:9",
    api_key: str | None = None,
) -> Path:
    """프롬프트로 완성 그림 1장을 생성해 out_path 에 저장하고 경로를 반환."""
    api_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY 환경변수가 없습니다. "
            "Google AI Studio(https://aistudio.google.com/apikey)에서 키를 발급받아 "
            "`export GEMINI_API_KEY=...` 로 설정하세요."
        )

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    resp = client.models.generate_images(
        model=model,
        prompt=prompt,
        config=types.GenerateImagesConfig(
            number_of_images=1,
            aspect_ratio=aspect_ratio,
        ),
    )

    if not resp.generated_images:
        raise RuntimeError(
            "이미지가 생성되지 않았습니다. 프롬프트가 안전정책에 걸렸거나 "
            "모델명이 올바른지 확인하세요."
        )

    # SDK 버전에 따라 image.image_bytes 또는 PIL 객체로 올 수 있어 방어적으로 처리.
    gen = resp.generated_images[0].image
    raw = getattr(gen, "image_bytes", None)
    if raw is not None:
        img = Image.open(io.BytesIO(raw)).convert("RGB")
    else:  # 일부 SDK는 PIL 이미지를 직접 노출
        img = gen._pil_image.convert("RGB")  # type: ignore[attr-defined]

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return out_path
