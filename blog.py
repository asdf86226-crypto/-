#!/usr/bin/env python3
"""그림 1장 + 어울리는 블로그 글을 자동으로 만들어 output 폴더에 저장한다.

네이버 블로그 등 자동 글쓰기가 막힌 곳을 위해, 그림과 글만 자동 생성하고
업로드는 사용자가 직접 한다(복사/붙여넣기 + 이미지 끌어놓기).

사용법:
    python blog.py                         # config.json 의 prompt 사용
    python blog.py --prompt "귀여운 고양이 수채화"
    python blog.py --no-text               # 그림만 생성(블로그 글 생략)
"""
from __future__ import annotations

import argparse
from pathlib import Path

from pipeline.gen_image import generate_final_image
from run import load_config, load_local_key


def main() -> None:
    ap = argparse.ArgumentParser(description="그림 + 블로그 글 자동 생성")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--prompt", help="config의 prompt를 덮어씀(그림 주제)")
    ap.add_argument("--no-text", action="store_true", help="블로그 글 생성 건너뜀")
    ap.add_argument("--outdir", default="output")
    args = ap.parse_args()

    load_local_key()
    cfg = load_config(args.config)
    if args.prompt:
        cfg["prompt"] = args.prompt

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    art_path = outdir / "art.png"
    text_path = outdir / "blog.txt"

    icfg = cfg.get("image", {})

    # [1] 그림 생성
    print("[1/2] 그림 생성 중...")
    generate_final_image(
        prompt=cfg["prompt"],
        out_path=art_path,
        model=icfg.get("model", "gemini-2.5-flash-image"),
        aspect_ratio=icfg.get("aspect_ratio", "4:3"),
        prompt_suffix=icfg.get("prompt_suffix", ""),
    )
    print(f"      그림 저장: {art_path}")

    # [2] 블로그 글 생성
    if not args.no_text:
        from pipeline.blogpost import generate_blog_text

        print("[2/2] 블로그 글 작성 중...")
        topic = cfg.get("blog_topic") or cfg["prompt"]
        text = generate_blog_text(topic, text_path)
        print(f"      글 저장: {text_path}\n")
        print("─" * 40)
        print(text)
        print("─" * 40)
    else:
        print("[2/2] 블로그 글 생략.")

    print("\n완성! 네이버 블로그에 올리는 법:")
    print("  1) output 폴더의 blog.txt 내용을 복사해 블로그 글에 붙여넣기")
    print("  2) output 폴더의 art.png 그림을 글에 끌어다 넣기")
    print("  3) 발행!")


if __name__ == "__main__":
    main()
