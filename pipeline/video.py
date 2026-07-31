"""[3] 4단계 이미지를 약 4분짜리 타임랩스 영상으로 합성한다.

- 스케치: 흰 캔버스에서 선화가 좌->우로 그려지는 wipe 효과
- 색칠/묘사/완성: 이전 단계에서 다음 단계로 디졸브(dissolve)
- 전 구간 켄번즈(느린 줌)로 정적인 느낌 제거
- 인트로(완성본 티저)/아웃트로 카드 포함
- BGM 파일이 있으면 ffmpeg로 합성

의존성: imageio(+imageio-ffmpeg), numpy, pillow. moviepy는 쓰지 않는다.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont

Size = tuple[int, int]


# ---------- 프레임 유틸 ----------

def _kenburns(base: Image.Image, size: Size, zoom: float) -> Image.Image:
    """중앙 기준으로 zoom(>=1)만큼 확대한 프레임을 반환."""
    w, h = size
    zoom = max(1.0, zoom)
    cw, ch = int(w / zoom), int(h / zoom)
    left, top = (w - cw) // 2, (h - ch) // 2
    return base.crop((left, top, left + cw, top + ch)).resize(size, Image.LANCZOS)


def _arr(img: Image.Image) -> np.ndarray:
    return np.asarray(img.convert("RGB"), dtype=np.float32)


def _dissolve(a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray:
    return a * (1.0 - t) + b * t


def _fade(a: np.ndarray, factor: float) -> np.ndarray:
    return a * max(0.0, min(1.0, factor))


def _u8(a: np.ndarray) -> np.ndarray:
    return np.clip(a, 0, 255).astype(np.uint8)


# ---------- 세그먼트 렌더러 (numpy 프레임 제너레이터) ----------

def _seg_reveal(prev: Image.Image, cur: Image.Image, n: int, size: Size,
                fps: int, reveal_seconds: float = 2.0, direction: str = "h",
                label: str = "", label_font: ImageFont.FreeTypeFont | None = None):
    """prev 위에 cur를 direction 방향으로 '빠르게 덧그리며' 채우고, 나머지는 홀드.

    디졸브(뭉개짐)가 아니라 각 단계가 또렷하게 얹히는 느낌을 준다.
    reveal_seconds 동안만 전환하고 그 뒤로는 완성된 현재 단계를 유지한다.
    label 이 있으면(폰트 있을 때) 하단에 단계 자막을 표시한다.
    """
    w, h = size
    reveal_frames = max(1, min(n, int(reveal_seconds * fps)))
    lab_rgb, lab_a = (None, None)
    if label and label_font is not None:
        lab_rgb, lab_a = _render_label(label, label_font, size)
    for i in range(n):
        z = 1.0 + 0.02 * (i / max(1, n - 1))   # 아주 옅은 줌(정지 화면 방지)
        base_prev = _arr(_kenburns(prev, size, z))
        base_cur = _arr(_kenburns(cur, size, z))
        if i < reveal_frames:
            p = (i + 1) / reveal_frames
            frame = base_prev.copy()
            if direction == "v":
                row = int(h * p)
                frame[:row, :, :] = base_cur[:row, :, :]
            else:
                col = int(w * p)
                frame[:, :col, :] = base_cur[:, :col, :]
        else:
            frame = base_cur
        if lab_rgb is not None:
            frame = frame * (1.0 - lab_a) + lab_rgb * lab_a
        yield _u8(frame)


def _render_label(text: str, font: ImageFont.FreeTypeFont, size: Size):
    """하단 중앙에 둥근 반투명 밴드 + 흰 글자 자막을 만들어 (rgb, alpha) 반환."""
    w, h = size
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    cx, y = w // 2, int(h * 0.86)
    px, py = int(th * 0.9), int(th * 0.45)
    band = [cx - tw // 2 - px, y - py, cx + tw // 2 + px, y + th + py]
    d.rounded_rectangle(band, radius=(th + 2 * py) // 2, fill=(0, 0, 0, 140))
    d.text((cx - tw // 2 - bbox[0], y - bbox[1]), text, font=font, fill=(255, 255, 255, 255))
    arr = np.asarray(overlay).astype(np.float32)
    return arr[:, :, :3], arr[:, :, 3:4] / 255.0


def _seg_intro(finish: Image.Image, n: int, size: Size, title: str, font: ImageFont.FreeTypeFont | None):
    """완성본을 어둡게 깔고 검정에서 페이드인 하는 티저."""
    for i in range(n):
        p = i / max(1, n - 1)
        z = 1.10 - 0.10 * p                      # 살짝 줌아웃
        base = _kenburns(finish, size, z)
        if font and title:
            base = _draw_caption(base.copy(), title, font, size)
        frame = _arr(base) * (0.25 + 0.35 * p)   # 어둡게 티저
        frame = _fade(frame, min(1.0, i / max(1, int(n * 0.3))))  # 검정->티저 페이드인
        yield _u8(frame)


def _seg_outro(finish: Image.Image, n: int, size: Size, text: str, font: ImageFont.FreeTypeFont | None):
    """완성본 홀드 후 끝에서 살짝 페이드아웃, 구독 문구(폰트 있을 때)."""
    for i in range(n):
        p = i / max(1, n - 1)
        z = 1.0 + 0.06 * p
        base = _kenburns(finish, size, z)
        if font and text:
            base = _draw_caption(base.copy(), text, font, size, bottom=True)
        frame = _arr(base)
        fade_out = 1.0 - max(0.0, (p - 0.8) / 0.2) * 0.7   # 마지막 20% 페이드아웃
        yield _u8(_fade(frame, fade_out))


def _draw_caption(img: Image.Image, text: str, font: ImageFont.FreeTypeFont, size: Size, bottom: bool = False) -> Image.Image:
    """반투명 밴드 위에 텍스트를 그린다(폰트가 있을 때만 호출)."""
    w, h = size
    draw = ImageDraw.Draw(img, "RGBA")
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    y = int(h * 0.82) if bottom else int(h * 0.10)
    pad = int(th * 0.6)
    draw.rectangle([0, y - pad, w, y + th + pad], fill=(0, 0, 0, 140))
    draw.text(((w - tw) / 2, y - bbox[1]), text, font=font, fill=(255, 255, 255, 255))
    return img


# 한글 지원 폰트 자동 탐색 후보(윈도우/맥/리눅스). 지정 폰트가 없을 때 사용.
_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\malgunbd.ttf",   # 맑은 고딕 Bold (윈도우)
    r"C:\Windows\Fonts\malgun.ttf",     # 맑은 고딕 (윈도우)
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",          # 맥
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",  # 맥
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",  # 리눅스
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
]


def _load_font(font_path: str, px: int) -> ImageFont.FreeTypeFont | None:
    """지정 폰트(px 크기)를 로드. 없으면 시스템 한글 폰트를 자동 탐색."""
    candidates = ([font_path] if font_path else []) + _FONT_CANDIDATES
    for path in candidates:
        try:
            return ImageFont.truetype(path, px)
        except Exception:
            continue
    return None


# ---------- 메인 빌더 ----------

def build_video(
    stages: dict[str, Image.Image],
    out_path: str,
    *,
    width: int = 1280,
    height: int = 720,
    fps: int = 24,
    total_seconds: int = 240,
    stage_weights: dict[str, float] | None = None,
    transition_seconds: float = 2.0,
    bgm_path: str = "",
    title: str = "",
    outro_text: str = "구독과 좋아요 부탁드려요!",
    font_path: str = "",
) -> Path:
    """4단계 이미지 dict -> mp4 파일 생성. 최종 경로 반환.

    transition_seconds: 각 단계가 '덧그려지며' 바뀌는 데 걸리는 시간(초). 작을수록 빠릿.
    """
    size: Size = (width, height)
    weights = stage_weights or {
        "intro": 0.05, "sketch": 0.20, "color": 0.25,
        "detail": 0.30, "finish": 0.15, "outro": 0.05,
    }
    order = ["intro", "sketch", "color", "detail", "finish", "outro"]
    total = sum(weights.get(k, 0) for k in order)
    frames_for = {k: max(1, int(total_seconds * fps * weights.get(k, 0) / total)) for k in order}

    font = _load_font(font_path, int(height * 0.05))         # 인트로/아웃트로 큰 자막
    label_font = _load_font(font_path, int(height * 0.042))  # 단계 자막(스케치/채색…)
    stage_labels = {
        "sketch": "스케치", "color": "채색", "detail": "묘사", "finish": "완성",
    }
    white = Image.new("RGB", size, (250, 250, 248))  # 스케치 시작용 캔버스

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # 오디오 유무와 무관하게 먼저 무음 영상을 임시로 렌더.
    # mkstemp가 연 파일 핸들을 닫아야 윈도우에서 나중에 삭제/이동이 된다.
    _fd, _tmp_name = tempfile.mkstemp(suffix=".mp4")
    os.close(_fd)
    tmp_video = Path(_tmp_name)
    writer = imageio.get_writer(
        tmp_video, fps=fps, codec="libx264",
        macro_block_size=1, pixelformat="yuv420p",
        ffmpeg_log_level="error",
    )
    try:
        for frame in _seg_intro(stages["finish"], frames_for["intro"], size, title, font):
            writer.append_data(frame)
        # 각 단계를 이전 단계 위에 '빠르게 덧그리며' 채운다(방향은 번갈아).
        prev_img = white
        for cur_key, direction in [
            ("sketch", "h"), ("color", "v"), ("detail", "h"), ("finish", "v"),
        ]:
            for frame in _seg_reveal(prev_img, stages[cur_key], frames_for[cur_key],
                                     size, fps, transition_seconds, direction,
                                     label=stage_labels.get(cur_key, ""),
                                     label_font=label_font):
                writer.append_data(frame)
            prev_img = stages[cur_key]
        for frame in _seg_outro(stages["finish"], frames_for["outro"], size, outro_text, font):
            writer.append_data(frame)
    finally:
        writer.close()

    # BGM 합성 (있을 때만). ffmpeg 바이너리는 imageio-ffmpeg 것을 사용.
    if bgm_path and Path(bgm_path).exists():
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [
            ffmpeg, "-y",
            "-i", str(tmp_video),
            "-stream_loop", "-1", "-i", str(bgm_path),
            "-shortest",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-af", "afade=t=out:st=%d:d=2" % max(0, total_seconds - 2),
            str(out_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        # 임시파일 삭제 실패는 치명적이지 않으니 무시(윈도우 잠금 대비)
        try:
            tmp_video.unlink()
        except OSError:
            pass
    else:
        try:
            tmp_video.replace(out_path)
        except OSError:
            # 이동 실패 시 복사로 대체
            import shutil
            shutil.copyfile(tmp_video, out_path)

    return out_path
