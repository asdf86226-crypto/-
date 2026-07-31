"""[1] Gemini로 완성 그림 1장을 생성한다.

방법 A: 완성본 1장만 AI로 생성하고, 이후 stages.py 에서
스케치/색칠/묘사 단계를 역산한다. 그래서 여기서는 딱 1장만 만든다.

여러 이미지 모델을 후보로 시도해, 현재 API 키에서 사용 가능한 첫 모델을
자동으로 사용한다(키/요금제마다 열려있는 모델이 다르기 때문).

필요 환경변수: GEMINI_API_KEY  (Google AI Studio에서 발급)
"""
from __future__ import annotations

import io
import os
from pathlib import Path

from PIL import Image

# 우선순위대로 시도할 이미지 생성 모델. 앞의 것이 먼저 시도된다.
_FALLBACK_MODELS = [
    "gemini-2.5-flash-image",                    # 최신 네이티브 이미지 모델
    "gemini-2.0-flash-preview-image-generation",  # 대체(무료 티어에서 흔히 가능)
    "imagen-3.0-generate-002",                    # 최후: Imagen(요금제 필요할 수 있음)
]


def _via_generate_content(client, types, model: str, prompt: str) -> Image.Image | None:
    """gemini-* 이미지 모델용: generate_content로 이미지를 받는다."""
    resp = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
    )
    for cand in (resp.candidates or []):
        content = getattr(cand, "content", None)
        for part in (getattr(content, "parts", None) or []):
            inline = getattr(part, "inline_data", None)
            if inline and getattr(inline, "data", None):
                return Image.open(io.BytesIO(inline.data)).convert("RGB")
    return None


def _via_imagen(client, types, model: str, prompt: str, aspect_ratio: str) -> Image.Image | None:
    """imagen-* 모델용: generate_images 사용."""
    resp = client.models.generate_images(
        model=model,
        prompt=prompt,
        config=types.GenerateImagesConfig(number_of_images=1, aspect_ratio=aspect_ratio),
    )
    if not resp.generated_images:
        return None
    gen = resp.generated_images[0].image
    raw = getattr(gen, "image_bytes", None)
    if raw is not None:
        return Image.open(io.BytesIO(raw)).convert("RGB")
    return gen._pil_image.convert("RGB")  # type: ignore[attr-defined]


def generate_final_image(
    prompt: str,
    out_path: str | Path,
    model: str | None = None,
    aspect_ratio: str = "16:9",
    api_key: str | None = None,
) -> Path:
    """프롬프트로 완성 그림 1장을 생성해 out_path 에 저장하고 경로를 반환."""
    api_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "제미나이 키를 찾을 수 없습니다. 프로젝트 폴더에 gemini_key.txt 파일을 만들고 "
            "그 안에 키만 붙여넣어 저장하세요. (또는 환경변수 GEMINI_API_KEY 설정)"
        )

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    # config에서 지정한 모델을 맨 앞에 두고, 나머지 후보를 뒤에 붙인다.
    candidates: list[str] = []
    if model:
        candidates.append(model)
    for m in _FALLBACK_MODELS:
        if m not in candidates:
            candidates.append(m)

    full_prompt = f"{prompt}. Wide 16:9 landscape composition, highly detailed."

    last_err: Exception | None = None
    for m in candidates:
        try:
            if m.startswith("imagen"):
                img = _via_imagen(client, types, m, full_prompt, aspect_ratio)
            else:
                img = _via_generate_content(client, types, m, full_prompt)
            if img is not None:
                out_path = Path(out_path)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                img.save(out_path)
                print(f"      (사용한 이미지 모델: {m})")
                return out_path
        except Exception as e:  # 이 모델이 안 되면 다음 후보로
            last_err = e
            continue

    raise RuntimeError(
        "사용 가능한 이미지 생성 모델을 찾지 못했습니다. 제미나이 키가 유효한지, "
        "이미지 생성이 지원되는 키인지 확인하세요.\n"
        f"마지막 오류: {last_err}"
    )
