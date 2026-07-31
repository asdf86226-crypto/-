#!/usr/bin/env python3
"""그림 1장을 자동으로 만들어 output 폴더에 저장한다.

만든 그림(output/art.png)을 블로그에 직접 올리면 된다.

사용법:
    python blog.py                         # config.json 의 prompt 사용
    python blog.py --prompt "귀여운 고양이 수채화"
"""
from __future__ import annotations

import argparse
from pathlib import Path

from pipeline.gen_image import generate_final_image
from run import load_config, load_local_key


def main() -> None:
    ap = argparse.ArgumentParser(description="그림 자동 생성")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--prompt", help="config의 prompt를 덮어씀(그림 주제)")
    ap.add_argument("--outdir", default="output")
    args = ap.parse_args()

    load_local_key()
    cfg = load_config(args.config)
    if args.prompt:
        cfg["prompt"] = args.prompt

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    art_path = outdir / "art.png"

    icfg = cfg.get("image", {})

    print("그림 생성 중...")
    generate_final_image(
        prompt=cfg["prompt"],
        out_path=art_path,
        model=icfg.get("model", "gemini-2.5-flash-image"),
        aspect_ratio=icfg.get("aspect_ratio", "4:3"),
        prompt_suffix=icfg.get("prompt_suffix", ""),
    )
    print(f"완성! 그림 저장: {art_path}")
    print("\n블로그에 올리는 법: output 폴더의 art.png 그림을 글에 끌어다 넣고 발행!")


if __name__ == "__main__":
    main()
