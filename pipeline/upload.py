"""[4] 완성된 mp4를 YouTube Data API v3로 업로드한다.

- OAuth 2.0(설치형 앱) 인증 필요. API 키만으로는 업로드 불가.
- 최초 1회 브라우저 승인 후 token_path에 토큰을 저장, 이후 자동 갱신.
- 새 GCP 프로젝트는 기본 '테스트' 상태라 privacy_status는 private 권장
  (public 자동 게시는 앱 심사가 필요할 수 있음).

준비물: Google Cloud Console에서 YouTube Data API v3 사용 설정 후
'데스크톱 앱' OAuth 클라이언트를 만들어 client_secret.json 다운로드.
"""
from __future__ import annotations

from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _get_credentials(client_secret_path: str, token_path: str):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None
    token_file = Path(token_path)
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not Path(client_secret_path).exists():
                raise RuntimeError(
                    f"{client_secret_path} 가 없습니다. Google Cloud Console에서 "
                    "'데스크톱 앱' OAuth 클라이언트를 만들어 내려받으세요."
                )
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
            # 헤드리스 환경이면 run_console(구버전) 대신 run_local_server(open_browser=False)
            creds = flow.run_local_server(port=0, open_browser=False)
        token_file.write_text(creds.to_json())
    return creds


def upload_video(
    video_path: str,
    title: str,
    description: str = "",
    tags: list[str] | None = None,
    *,
    privacy_status: str = "private",
    category_id: str = "24",
    thumbnail_path: str = "",
    client_secret_path: str = "client_secret.json",
    token_path: str = "token.json",
) -> str:
    """영상을 업로드하고 videoId를 반환. thumbnail_path가 있으면 썸네일도 설정."""
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    creds = _get_credentials(client_secret_path, token_path)
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags or [],
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  업로드 진행률: {int(status.progress() * 100)}%")

    video_id = response["id"]
    print(f"  업로드 완료: https://youtu.be/{video_id}  (상태: {privacy_status})")

    # 사용자가 지정한 썸네일 설정 (있을 때만)
    if thumbnail_path and Path(thumbnail_path).exists():
        try:
            ext = Path(thumbnail_path).suffix.lower()
            mime = "image/png" if ext == ".png" else "image/jpeg"
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_path, mimetype=mime),
            ).execute()
            print(f"  썸네일 설정 완료: {thumbnail_path}")
        except Exception as e:  # 채널 미인증 등
            print(
                f"  ⚠️ 썸네일 설정 실패: {e}\n"
                "     맞춤 썸네일은 전화번호로 인증된 채널에서만 가능합니다 "
                "(youtube.com/verify)."
            )
    elif thumbnail_path:
        print(f"  ⚠️ 썸네일 파일을 찾을 수 없음: {thumbnail_path}")

    return video_id
