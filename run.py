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
import os
from pathlib import Path

from PIL import Image

from pipeline.gen_image import generate_final_image
from pipeline.stages import build_stages
from pipeline.video import build_video


def load_local_key() -> None:
    """gemini_key.txt 파일이 있으면 GEMINI_API_KEY 환경변수로 로드(초보자 편의).

    환경변수가 이미 설정돼 있으면 그대로 둔다.
    """
    if os.environ.get("GEMINI_API_KEY"):
        return
    # 현재 폴더 -> 홈 폴더 순으로 gemini_key.txt 를 찾는다.
    # 홈 폴더(예: C:\Users\<나>)에 한 번 두면 매번 새로 만들 필요가 없다.
    for key_file in (Path("gemini_key.txt"), Path.home() / "gemini_key.txt"):
        if key_file.exists():
            key = key_file.read_text(encoding="utf-8").strip()
            if key:
                os.environ["GEMINI_API_KEY"] = key
                return


def find_user_track() -> str:
    """폴더(및 홈)에서 내가 넣은 음원 파일을 찾는다. 있으면 경로 문자열, 없으면 "".

    bgm/music 이름 + 흔한 오디오 확장자를 찾는다. (합성 결과 output/bgm.wav 는 제외)
    """
    exts = (".mp3", ".m4a", ".wav", ".ogg", ".aac", ".flac")
    # 1) 정해진 이름(bgm/music 등)을 우선 찾고
    names = ("bgm", "music", "song", "배경음악")
    for folder in (Path("."), Path.home()):
        for name in names:
            for ext in exts:
                cand = folder / f"{name}{ext}"
                if cand.exists():
                    return str(cand)
    # 2) 없으면 프로젝트 폴더에 있는 아무 음악 파일이나 사용(이름 상관없이)
    audio = sorted(p for p in Path(".").iterdir()
                   if p.is_file() and p.suffix.lower() in exts)
    if audio:
        return str(audio[0])
    return ""


def load_config(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        # config.json이 없으면 예시 파일로 대체(첫 실행 편의)
        example = Path("config.example.json")
        if example.exists():
            print(f"※ {path} 이 없어 config.example.json 설정으로 실행합니다.")
            return json.loads(example.read_text(encoding="utf-8"))
        raise SystemExit(
            f"설정 파일 {path} 이 없습니다. config.example.json 을 복사해 만드세요."
        )
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser(description="드로잉 타임랩스 자동화")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--prompt", help="config의 prompt를 덮어씀")
    ap.add_argument("--no-upload", action="store_true", help="유튜브 업로드 건너뜀")
    ap.add_argument("--outdir", default="output")
    args = ap.parse_args()

    load_local_key()
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
        model=icfg.get("model", "gemini-2.5-flash-image"),
        aspect_ratio=icfg.get("aspect_ratio", "16:9"),
        prompt_suffix=icfg.get("prompt_suffix", ""),
    )
    print(f"      저장: {final_path}")

    # [2] 4단계 역산
    print("[2/4] 스케치/색칠/묘사/완성 4단계 생성 중...")
    stages = build_stages(str(final_path), size, fit=vcfg.get("fit", "contain"))
    for name, img in stages.items():
        img.save(outdir / f"stage_{name}.png")

    # BGM 결정
    #  - 폴더에 내 음원 파일(bgm.mp3 등)이 있으면 그걸 최우선으로 사용
    #  - 없으면 mode 에 따라 auto(코드 생성) / file(지정) / none(무음)
    total_seconds = vcfg.get("total_seconds", 240)
    bgm_cfg = vcfg.get("bgm", {})
    bgm_path = ""
    mode = bgm_cfg.get("mode", "auto")

    user_track = find_user_track()
    if bgm_cfg.get("file"):
        bgm_path = bgm_cfg["file"]
    elif user_track:
        print(f"      내 음원 사용: {user_track}")
        bgm_path = user_track
    elif mode == "auto":
        from pipeline.bgm import generate_bgm

        print("      경쾌한 BGM 생성 중...")
        bgm_path = str(generate_bgm(
            outdir / "bgm.wav",
            seconds=total_seconds,
            tempo_bpm=bgm_cfg.get("tempo_bpm", 104),
        ))

    # [3] 영상 합성
    print(f"[3/4] {total_seconds}초 타임랩스 영상 합성 중... (수 분 소요될 수 있음)")
    build_video(
        stages,
        str(video_path),
        width=size[0],
        height=size[1],
        fps=vcfg.get("fps", 24),
        total_seconds=total_seconds,
        stage_weights=vcfg.get("stage_weights"),
        transition_seconds=vcfg.get("transition_seconds", 2.0),
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
