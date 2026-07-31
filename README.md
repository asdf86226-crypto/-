# 드로잉 타임랩스 자동화 (Gemini → 4분 영상 → 유튜브)

AI로 그림을 생성하고, **스케치 → 색칠 → 묘사 → 완성** 4단계로 그려지는
약 4분짜리 타임랩스 영상을 만들어 **유튜브에 자동 업로드**하는 파이프라인입니다.

## 동작 방식

```
[1] Gemini(Imagen)로 완성본 1장 생성
        ↓
[2] 완성본에서 4단계를 역산 (방법 A)
      - 스케치: 윤곽선 검출(연필 선화)
      - 색칠  : 색 단순화(평면 채색)
      - 묘사  : 채도/대비를 낮춘 완성 직전본
      - 완성  : 원본
        ↓
[3] 4단계를 타임랩스 영상으로 합성 (wipe + 디졸브 + 켄번즈 + BGM)
        ↓
[4] YouTube Data API v3로 업로드 (기본 비공개, 지정 썸네일 설정)
```

> **왜 방법 A인가?** AI로 "스케치/색칠/완성"을 각각 따로 생성하면 매번
> 구도·색이 달라져 하나의 그림이 그려지는 과정처럼 보이지 않습니다.
> 완성본 1장에서 이전 단계를 역산하면 4단계가 100% 같은 그림이 됩니다.

## 설치

```bash
pip install -r requirements.txt
```

## 준비물 (직접 발급 필요)

### 1. Gemini API 키
[Google AI Studio](https://aistudio.google.com/apikey)에서 발급 후:
```bash
export GEMINI_API_KEY="your-key"
```

### 2. YouTube 업로드 OAuth (자동 업로드 쓸 때만)
1. [Google Cloud Console](https://console.cloud.google.com)에서 프로젝트 생성
2. **YouTube Data API v3** 사용 설정
3. OAuth 동의 화면 구성 → **데스크톱 앱** OAuth 클라이언트 생성
4. `client_secret.json` 다운로드하여 프로젝트 루트에 저장
5. 첫 실행 시 브라우저(또는 콘솔) 승인 → `token.json` 자동 저장

> ⚠️ 새 GCP 프로젝트는 '테스트' 상태라 업로드 영상이 **비공개(private)** 로만
> 올라갑니다. 확인 후 유튜브에서 수동으로 공개 전환하거나, 앱 심사를 받으세요.

## 사용법

```bash
cp config.example.json config.json   # 프롬프트/제목/설정 수정
python run.py                        # 생성→영상→업로드

python run.py --prompt "밤하늘 아래 고양이, 수채화" --no-upload   # 업로드 없이 영상만
python run.py --config other.json
```

결과물은 `output/` 에 저장됩니다 (`final.png`, `stage_*.png`, `drawing_timelapse.mp4`).

## 설정 (config.json) 주요 항목

| 키 | 설명 |
|----|------|
| `prompt` | 그릴 그림의 영어 프롬프트 |
| `title` / `description` / `tags` | 유튜브 메타데이터 |
| `image.model` | Gemini 이미지 모델 (예: `imagen-3.0-generate-002`) |
| `video.total_seconds` | 영상 길이(기본 240 = 4분) |
| `video.stage_weights` | 구간별 길이 비율 |
| `video.bgm.mode` | `auto`(코드로 무료 BGM 생성) / `file`(직접 파일) / `none`(무음) |
| `video.bgm.file` | `mode:"file"`일 때 사용할 음원 경로 |
| `video.bgm.tempo_bpm` | 자동 BGM 빠르기(기본 100, 클수록 경쾌) |
| `video.font_path` | 인트로/아웃트로 자막 폰트(한글이면 한글 폰트 .ttf 지정) |
| `youtube.privacy_status` | `private` / `unlisted` / `public` |
| `youtube.thumbnail_path` | 직접 준비한 썸네일 이미지 경로(예: `my_thumb.png`) |

## BGM (배경음악)
기본값 `mode: "auto"` 는 **코드로 경쾌하고 아름다운 곡을 직접 생성**합니다
(I–V–vi–IV 코드 진행 + 오르골 멜로디). 우리가 만든 음원이라 **저작권·저작자
표시 의무가 없어** 유튜브 상업적 사용이 자유롭습니다. `tempo_bpm` 으로 빠르기를
조절하세요. 직접 준비한 음원을 쓰려면 `mode: "file"`, `file: "경로.mp3"` 로 바꾸면
됩니다.

## 썸네일
`youtube.thumbnail_path` 에 **직접 만든 이미지 경로**를 넣으면 업로드 시 자동으로
썸네일로 설정됩니다(1280×720 권장). 비워두면 유튜브가 자동 선택합니다.
> ⚠️ 맞춤 썸네일은 **전화번호로 인증된 채널**에서만 가능합니다
> (youtube.com/verify). 미인증 시 영상은 올라가되 썸네일만 건너뜁니다.

## 자막 폰트에 대해
인트로 제목·아웃트로 문구는 `video.font_path` 에 폰트를 지정할 때만 표시됩니다.
한글을 넣으려면 한글 지원 `.ttf`(예: 나눔고딕)를 지정하세요. 미지정 시
텍스트 없이 이미지 티저/홀드만 나옵니다.

## 주의
- `client_secret.json`, `token.json`, `.env`, `output/` 은 `.gitignore`로 제외됩니다.
  비밀 키를 커밋하지 마세요.
- 모델명(`imagen-3.0-*`)이나 SDK 버전은 시간이 지나면 바뀔 수 있으니 오류 시
  최신 모델명으로 업데이트하세요.
