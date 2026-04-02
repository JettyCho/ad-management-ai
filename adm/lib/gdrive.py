"""Google Drive 파일 업로드 유틸리티.

.docx 등의 파일을 Google Docs 형식으로 변환 업로드한다.
인증은 gsheet.py와 동일한 .google_token.json을 공유한다.

사용법:
    from adm.lib.gdrive import upload_as_google_doc

    url = upload_as_google_doc(
        "보고서.docx",
        title="분석 보고서",          # Drive에 표시될 이름
        share_email="user@buzzvil.com",  # (선택) 공유할 이메일
    )
    print(url)  # https://docs.google.com/document/d/.../edit
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
]
TOKEN_PATH = Path(__file__).resolve().parent.parent.parent / ".google_token.json"


def _get_credentials() -> Credentials:
    """OAuth2 인증 후 Credentials 반환. gsheet.py와 동일한 토큰 파일 공유."""
    creds: Credentials | None = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
        client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
        if not client_id or not client_secret:
            raise RuntimeError(
                "GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET 환경변수가 필요합니다."
            )
        client_config = {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        }
        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
        creds = flow.run_local_server(port=0)

    TOKEN_PATH.write_text(
        json.dumps(
            {
                "token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_uri": creds.token_uri,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "scopes": creds.scopes,
            }
        )
    )
    return creds


def upload_as_google_doc(
    file_path: str | Path,
    title: str | None = None,
    share_email: str | None = None,
    folder_id: str | None = None,
) -> str:
    """.docx 파일을 Google Docs 형식으로 변환 업로드.

    Args:
        file_path: 업로드할 .docx 파일 경로.
        title: Drive에 표시될 문서 이름. None이면 파일명 사용.
        share_email: 편집 권한을 부여할 이메일. None이면 공유 안 함.
        folder_id: 업로드할 Drive 폴더 ID. None이면 루트.

    Returns:
        Google Docs 웹 링크 URL.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")

    creds = _get_credentials()
    service = build("drive", "v3", credentials=creds)

    file_metadata: dict = {
        "name": title or file_path.stem,
        "mimeType": "application/vnd.google-apps.document",
    }
    if folder_id:
        file_metadata["parents"] = [folder_id]

    media = MediaFileUpload(
        str(file_path),
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    file = (
        service.files()
        .create(body=file_metadata, media_body=media, fields="id, webViewLink")
        .execute()
    )

    web_link = file["webViewLink"]
    print(f"[OK] Google Docs 업로드 완료: {web_link}")

    if share_email:
        service.permissions().create(
            fileId=file["id"],
            body={"type": "user", "role": "writer", "emailAddress": share_email},
        ).execute()
        print(f"[OK] 공유 완료: {share_email}")

    return web_link
