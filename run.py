#!/usr/bin/env python3
"""드로잉 타임랩스 자동 생성 + 유튜브 업로드 오케스트레이터.

흐름: Gemini로 완성본 1장 생성 -> 4단계 역산 -> 4분 영상 합성 -> 유튜브 업로드.

사용법:
    export GEMINI_API_KEY=...
    python run.py                      # config.json 사용
    python run.py --config myconf.json
    python run.py --prompt "..." --no-upload   # 업로드 없이 영상만
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

from pipeline.gen_image import generate_final_image
from pipeline.stages import build_stages
from pipeline.video import build_video


def load_config(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise SystemExit(
            f"설정 파일 {path} 이 없습니다. config.example.json 을 복사해 만드세요:\n"
            f"    cp config.example.json config.json"
        )
    return json.loads(p.read_text())


def main() -> None:
    ap = argparse.ArgumentParser(description="드로잉 타임랩스 자동화")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--prompt", help="config의 prompt를 덮어씀")
    ap.add_argument("--no-upload", action="store_true", help="유튜브 업로드 건너뜀")
    ap.add_argument("--outdir", default="output")
    args = ap.parse_args()

    cfg = load_config(args.config)
    if args.prompt:
        cfg["prompt"] = args.prompt

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    final_path = outdir / "final.png"
    video_path = outdir / "drawing_timelapse.mp4"

    vcfg = cfg.get("video", {})
    icfg = cfg.get("image", {})
    size = (vcfg.get("width", 1280), vcfg.get("height", 720))

    # [1] 완성본 생성
    print("[1/4] Gemini로 완성 그림 생성 중...")
    generate_final_image(
        prompt=cfg["prompt"],
        out_path=final_path,
        model=icfg.get("model", "imagen-3.0-generate-002"),
        aspect_ratio=icfg.get("aspect_ratio", "16:9"),
    )
    print(f"      저장: {final_path}")

    # [2] 4단계 역산
    print("[2/4] 스케치/색칠/묘사/완성 4단계 생성 중...")
    stages = build_stages(str(final_path), size)
    for name, img in stages.items():
        img.save(outdir / f"stage_{name}.png")

    # BGM 결정: auto=코드로 생성 / file=지정 파일 / none=무음
    total_seconds = vcfg.get("total_seconds", 240)
    bgm_cfg = vcfg.get("bgm", {})
    bgm_path = ""
    mode = bgm_cfg.get("mode", "auto")
    if mode == "auto":
        from pipeline.bgm import generate_bgm

        print("      경쾌한 BGM 생성 중...")
        bgm_path = str(generate_bgm(
            outdir / "bgm.wav",
            seconds=total_seconds,
            tempo_bpm=bgm_cfg.get("tempo_bpm", 100),
        ))
    elif mode == "file":
        bgm_path = bgm_cfg.get("file", "")

    # [3] 영상 합성
    print("[3/4] 4분 타임랩스 영상 합성 중... (수 분 소요될 수 있음)")
    build_video(
        stages,
        str(video_path),
        width=size[0],
        height=size[1],
        fps=vcfg.get("fps", 24),
        total_seconds=total_seconds,
        stage_weights=vcfg.get("stage_weights"),
        bgm_path=bgm_path,
        title=cfg.get("title", ""),
        font_path=vcfg.get("font_path", ""),
    )
    print(f"      영상: {video_path}")

    # [4] 유튜브 업로드
    ycfg = cfg.get("youtube", {})
    if args.no_upload or not ycfg.get("enabled", False):
        print("[4/4] 업로드 건너뜀. 영상 파일을 직접 확인하세요.")
        return

    print("[4/4] 유튜브 업로드 중...")
    from pipeline.upload import upload_video

    upload_video(
        str(video_path),
        title=cfg.get("title", "Drawing Timelapse"),
        description=cfg.get("description", ""),
        tags=cfg.get("tags", []),
        privacy_status=ycfg.get("privacy_status", "private"),
        category_id=ycfg.get("category_id", "24"),
        thumbnail_path=ycfg.get("thumbnail_path", ""),
        client_secret_path=ycfg.get("client_secret_path", "client_secret.json"),
        token_path=ycfg.get("token_path", "token.json"),
    )
    print("완료!")


if __name__ == "__main__":
    main()
