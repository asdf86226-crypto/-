"""[1] Gemini로 완성 그림 1장을 생성한다.

방법 A: 완성본 1장만 AI로 생성하고, 이후 stages.py 에서
스케치/색칠/묘사 단계를 역산한다. 그래서 여기서는 딱 1장만 만든다.

여러 이미지 모델을 후보로 시도해, 현재 API 키에서 사용 가능한 첫 모델을
자동으로 사용한다(키/요금제마다 열려있는 모델이 다르기 때문).
모두 실패하면 각 모델의 실패 이유를 모아서 알려준다.

필요 환경변수: GEMINI_API_KEY  (Google AI Studio에서 발급)

내 키에 어떤 모델이 있는지 확인하려면:
    python -c "from pathlib import Path;from google import genai;c=genai.Client(api_key=Path('gemini_key.txt').read_text().strip());[print(m.name,'->',m.supported_actions) for m in c.models.list()]"
"""
from __future__ import annotations

import io
import os
from pathlib import Path

from PIL import Image

# 우선순위대로 시도할 이미지 생성 모델(앞의 것 먼저).
# gemini-* 는 generate_content, imagen-* 는 generate_images(predict)로 호출한다.
_FALLBACK_MODELS = [
    "gemini-2.5-flash-image",       # 무료 티어에서 잘 되는 네이티브 이미지 모델
    "gemini-3.1-flash-image",
    "nano-banana-pro-preview",
    "imagen-4.0-generate-001",      # Imagen 4 (predict)
    "imagen-4.0-fast-generate-001",
]


def _extract_image(resp) -> Image.Image | None:
    """generate_content 응답에서 첫 이미지 파트를 꺼낸다."""
    for cand in (getattr(resp, "candidates", None) or []):
        content = getattr(cand, "content", None)
        for part in (getattr(content, "parts", None) or []):
            inline = getattr(part, "inline_data", None)
            if inline and getattr(inline, "data", None):
                return Image.open(io.BytesIO(inline.data)).convert("RGB")
    return None


def _via_generate_content(client, types, model: str, prompt: str) -> Image.Image:
    """gemini-* 이미지 모델용. response_modalities 조합을 바꿔가며 시도."""
    errors = []
    for modalities in (["IMAGE"], ["TEXT", "IMAGE"]):
        try:
            resp = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(response_modalities=modalities),
            )
            img = _extract_image(resp)
            if img is not None:
                return img
            errors.append(f"modalities={modalities}: 응답에 이미지 파트 없음")
        except Exception as e:
            errors.append(f"modalities={modalities}: {e}")
    raise RuntimeError("; ".join(errors))


def _via_imagen(client, types, model: str, prompt: str, aspect_ratio: str) -> Image.Image:
    """imagen-* 모델용. generate_images(predict) 사용."""
    resp = client.models.generate_images(
        model=model,
        prompt=prompt,
        config=types.GenerateImagesConfig(number_of_images=1, aspect_ratio=aspect_ratio),
    )
    if not resp.generated_images:
        raise RuntimeError("generated_images 비어 있음")
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
    prompt_suffix: str = "",
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

    # 응답이 없을 때 무한정 멈추지 않도록 타임아웃(약 120초)을 건다.
    try:
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=120_000),  # 밀리초
        )
    except Exception:
        client = genai.Client(api_key=api_key)

    # config에서 지정한 모델을 맨 앞에 두고, 나머지 후보를 뒤에 붙인다.
    candidates: list[str] = []
    if model:
        candidates.append(model)
    for m in _FALLBACK_MODELS:
        if m not in candidates:
            candidates.append(m)

    # 스타일 지시는 config의 prompt_suffix로 제어(없으면 프롬프트 그대로).
    full_prompt = f"{prompt}. {prompt_suffix}".strip() if prompt_suffix else prompt

    report: list[str] = []
    for m in candidates:
        try:
            if m.startswith("imagen"):
                img = _via_imagen(client, types, m, full_prompt, aspect_ratio)
            else:
                img = _via_generate_content(client, types, m, full_prompt)
            out_path = Path(out_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(out_path)
            print(f"      (사용한 이미지 모델: {m})")
            return out_path
        except Exception as e:
            report.append(f"  - {m}: {e}")
            continue

    raise RuntimeError(
        "모든 이미지 모델이 실패했습니다. 아래 이유를 확인하세요:\n"
        + "\n".join(report)
    )
