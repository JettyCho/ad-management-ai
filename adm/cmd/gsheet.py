"""Google Sheets 유틸리티.

사용법:
    from adm.cmd.gsheet import GoogleSheet

    gs = GoogleSheet()  # 최초 실행 시 브라우저 OAuth 인증
    sid = gs.create("제목", ["시트1", "시트2"], "user@gmail.com")
    gs.write(sid, "시트1!A1", [["a", "b"], ["1", "2"]])
    gs.add_sheet(sid, "시트3")
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]
TOKEN_PATH = Path(__file__).resolve().parent.parent.parent / ".google_token.json"


def _get_credentials() -> Credentials:
    """OAuth2 인증 후 Credentials 반환. 토큰은 프로젝트 루트에 캐시."""
    creds: Optional[Credentials] = None

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

    TOKEN_PATH.write_text(json.dumps({
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes,
    }))
    return creds


class GoogleSheet:
    """Google Sheets API 래퍼."""

    def __init__(self) -> None:
        creds = _get_credentials()
        self.service = build("sheets", "v4", credentials=creds)
        self.sheets = self.service.spreadsheets()

    def create(
        self,
        title: str,
        sheet_names: list[str] | None = None,
        share_email: str | None = None,
    ) -> str:
        """스프레드시트 생성 후 spreadsheet_id 반환."""
        body: dict = {"properties": {"title": title}}
        if sheet_names:
            body["sheets"] = [
                {"properties": {"title": name}} for name in sheet_names
            ]
        result = self.sheets.create(body=body).execute()
        spreadsheet_id = result["spreadsheetId"]
        url = result["spreadsheetUrl"]
        print(f"생성 완료: {url}")

        if share_email:
            drive = build("drive", "v3", credentials=_get_credentials())
            drive.permissions().create(
                fileId=spreadsheet_id,
                body={"type": "user", "role": "writer", "emailAddress": share_email},
            ).execute()
            print(f"공유 완료: {share_email}")

        return spreadsheet_id

    def add_sheet(self, spreadsheet_id: str, sheet_name: str) -> None:
        """기존 스프레드시트에 시트 추가."""
        self.sheets.batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                "requests": [
                    {"addSheet": {"properties": {"title": sheet_name}}}
                ]
            },
        ).execute()
        print(f"시트 추가: {sheet_name}")

    def write(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: list[list[str]],
        batch_size: int = 500,
    ) -> None:
        """데이터를 시트에 입력. batch_size 행씩 나눠서 전송."""
        for i in range(0, len(values), batch_size):
            chunk = values[i : i + batch_size]
            # 범위의 시작 행 계산
            if "!" in range_name:
                sheet_prefix = range_name.split("!")[0]
            else:
                sheet_prefix = range_name
            start_row = i + 1
            end_row = i + len(chunk)
            max_col = max(len(row) for row in chunk)
            col_letter = chr(ord("A") + max_col - 1) if max_col <= 26 else "Z"
            chunk_range = f"{sheet_prefix}!A{start_row}:{col_letter}{end_row}"

            self.sheets.values().update(
                spreadsheetId=spreadsheet_id,
                range=chunk_range,
                valueInputOption="RAW",
                body={"values": chunk},
            ).execute()
            print(f"  입력: {chunk_range} ({len(chunk)}행)")

        print(f"입력 완료: 총 {len(values)}행")
