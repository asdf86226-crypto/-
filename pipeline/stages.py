"""[2] 방법 A: 완성본 1장에서 4단계(스케치/색칠/묘사/완성)를 역산한다.

같은 그림에서 파생되므로 4단계가 100% 동일한 구도를 유지한다.
반환 순서는 그리는 순서(sketch -> color -> detail -> finish).
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps


def _to_rgb(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    # 비율이 다른 이미지를 왜곡 없이 채우도록 중앙 크롭 후 리사이즈
    return ImageOps.fit(img.convert("RGB"), size, Image.LANCZOS)


def _pencil_sketch(img: Image.Image) -> Image.Image:
    """dodge 기법으로 흰 배경 위 선화(스케치)를 만든다."""
    gray = img.convert("L")
    inv = ImageOps.invert(gray)
    blur = inv.filter(ImageFilter.GaussianBlur(radius=max(2, img.width // 200)))

    g = np.asarray(gray, dtype=np.float32)
    b = np.asarray(blur, dtype=np.float32)
    # color dodge: base*255 / (255 - blur)
    dodge = np.where(b >= 255, 255, np.minimum(255, g * 255.0 / (255.0 - b)))
    sketch = Image.fromarray(dodge.astype(np.uint8), mode="L")

    # 살짝 대비를 올려 연필선을 또렷하게
    sketch = ImageEnhance.Contrast(sketch).enhance(1.15)
    return sketch.convert("RGB")


def _flat_color(img: Image.Image) -> Image.Image:
    """색을 단순화(포스터화)해 평면 채색 단계를 만든다."""
    smooth = img.filter(ImageFilter.MedianFilter(size=5))
    poster = ImageOps.posterize(smooth, bits=3)
    # 채도를 약간 낮춰 '아직 다듬기 전' 느낌
    poster = ImageEnhance.Color(poster).enhance(0.85)
    return poster.convert("RGB")


def _detail(img: Image.Image) -> Image.Image:
    """완성 직전: 디테일은 거의 있으나 마감(채도/대비)이 덜 된 단계."""
    smooth = img.filter(ImageFilter.GaussianBlur(radius=1))
    blended = Image.blend(img, smooth, alpha=0.3)
    blended = ImageEnhance.Color(blended).enhance(0.92)
    blended = ImageEnhance.Contrast(blended).enhance(0.96)
    return blended.convert("RGB")


def build_stages(
    final_image_path: str,
    size: tuple[int, int],
) -> dict[str, Image.Image]:
    """완성본 경로에서 4단계 이미지를 만들어 dict로 반환."""
    final = _to_rgb(Image.open(final_image_path), size)
    return {
        "sketch": _pencil_sketch(final),
        "color": _flat_color(final),
        "detail": _detail(final),
        "finish": final,
    }
