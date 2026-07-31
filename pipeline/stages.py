"""[2] 방법 A: 완성본 1장에서 4단계(스케치/색칠/묘사/완성)를 역산한다.

같은 그림에서 파생되므로 4단계가 100% 동일한 구도를 유지한다.
반환 순서는 그리는 순서(sketch -> color -> detail -> finish).
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps


def _to_rgb(img: Image.Image, size: tuple[int, int], fit: str = "contain") -> Image.Image:
    """이미지를 목표 크기로 맞춘다.

    fit="contain": 전체가 다 보이도록 비율 유지 후 여백(배경색)으로 채움(잘림 없음).
    fit="cover":   화면을 꽉 채우되 넘치는 부분은 크롭(잘릴 수 있음).
    """
    img = img.convert("RGB")
    if fit == "cover":
        return ImageOps.fit(img, size, Image.LANCZOS)
    # contain: 비율 유지로 안에 맞추고, 남는 여백은 그림의 모서리색으로 채움
    fitted = ImageOps.contain(img, size, Image.LANCZOS)
    bg = img.getpixel((2, 2)) if img.width > 4 and img.height > 4 else (255, 255, 255)
    canvas = Image.new("RGB", size, bg)
    x = (size[0] - fitted.width) // 2
    y = (size[1] - fitted.height) // 2
    canvas.paste(fitted, (x, y))
    return canvas


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


def _base_color(img: Image.Image) -> Image.Image:
    """기본색(밑색): 색을 크게 단순화하고 채도를 낮춰 '밑색 깐' 느낌."""
    smooth = img.filter(ImageFilter.MedianFilter(size=7))
    poster = ImageOps.posterize(smooth, bits=2)      # 색을 더 크게 뭉갬
    poster = ImageEnhance.Color(poster).enhance(0.6)  # 채도 낮게
    poster = ImageEnhance.Brightness(poster).enhance(1.06)
    return poster.convert("RGB")


def _detail(img: Image.Image) -> Image.Image:
    """명암/묘사 단계: 명암은 들어갔으나 하이라이트 마감 전(약간 눌린 하이라이트)."""
    smooth = img.filter(ImageFilter.GaussianBlur(radius=1))
    blended = Image.blend(img, smooth, alpha=0.25)
    blended = ImageEnhance.Color(blended).enhance(0.95)
    # 하이라이트를 살짝 눌러 '아직 마감 전'
    arr = np.asarray(blended, dtype=np.float32)
    arr = np.where(arr > 200, 200 + (arr - 200) * 0.6, arr)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def build_stages(
    final_image_path: str,
    size: tuple[int, int],
    fit: str = "contain",
) -> dict[str, Image.Image]:
    """완성본 경로에서 그리기 단계 이미지들을 만들어 dict로 반환.

    순서: lineart(선화) -> base(기본색) -> color(색상 확정) -> shade(명암/묘사)
          -> finish(하이라이트/완성)
    """
    final = _to_rgb(Image.open(final_image_path), size, fit)
    return {
        "lineart": _pencil_sketch(final),
        "base": _base_color(final),
        "color": _flat_color(final),
        "shade": _detail(final),
        "finish": final,
    }
