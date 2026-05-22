"""
Gmail OAuth 리프레시 토큰 발급 스크립트.
최초 1회만 실행. 발급된 refresh_token을 GitHub Secret에 저장.

실행:
    pip install google-auth-oauthlib
    python scripts/get_gmail_token.py
"""

import json
import os
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def main():
    env = {}
    env_path = Path(__file__).parent.parent / ".env"
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()

    client_id = env.get("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = env.get("GOOGLE_OAUTH_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("ERROR: .env에 GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET 없음")
        return

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uris": ["http://localhost"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0)

    print("\n=== 발급 완료 ===")
    print(f"refresh_token: {creds.refresh_token}")
    print("\nGitHub Secret에 아래 값을 추가하세요:")
    print(f"  GOOGLE_OAUTH_REFRESH_TOKEN = {creds.refresh_token}")

if __name__ == "__main__":
    main()
