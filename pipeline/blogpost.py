"""그림에 어울리는 한국어 블로그 글(제목/본문/태그)을 Gemini로 작성한다.

네이버 블로그는 자동 글쓰기가 막혀 있어, 글과 그림을 자동 생성한 뒤
사용자가 직접 붙여넣는 방식을 돕는다. (텍스트 생성은 무료 등급에서도 동작)
"""
from __future__ import annotations

import os
from pathlib import Path


def generate_blog_text(
    topic: str,
    out_path: str | Path,
    api_key: str | None = None,
    model: str = "gemini-2.5-flash",
) -> str:
    """주제에 맞는 블로그 글을 만들어 out_path(txt)에 저장하고 본문 문자열 반환."""
    api_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("제미나이 키가 없습니다. gemini_key.txt 를 확인하세요.")

    from google import genai
    from google.genai import types

    try:
        client = genai.Client(
            api_key=api_key, http_options=types.HttpOptions(timeout=120_000)
        )
    except Exception:
        client = genai.Client(api_key=api_key)

    prompt = (
        "너는 친근한 말투의 한국어 블로그 작가야. 아래 '그림 주제'로 네이버 블로그에 "
        "올릴 글을 작성해줘.\n\n"
        f"그림 주제: {topic}\n\n"
        "다음 형식을 정확히 지켜서 한국어로 써줘:\n"
        "제목: (사람들이 클릭하고 싶은 매력적인 제목 한 줄)\n\n"
        "(본문: 6~8문장. 그림을 소개하고 감상 포인트를 친근하게. 이모지 2~3개 자연스럽게)\n\n"
        "태그: #태그1 #태그2 #태그3 #태그4 #태그5\n"
    )
    resp = client.models.generate_content(model=model, contents=prompt)
    text = (resp.text or "").strip()
    if not text:
        raise RuntimeError("블로그 글 생성 결과가 비어 있습니다.")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    return text
