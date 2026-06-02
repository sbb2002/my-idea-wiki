"""
OAuth 인증으로 구글 드라이브에 wikis 폴더 구조를 생성하는 초기 설정 스크립트.

사전 준비:
  - scripts/get_oauth_token.py 실행 완료
  - .env에 GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN 설정

실행하면:
  1. OAuth 사용자 계정으로 wikis/ 폴더 생성
  2. 그 안에 pic/ 서브폴더 생성
  3. wiki.json, index.html 자동 업로드
  4. 생성된 DRIVE_WIKI_FOLDER_ID 출력

사용법:
  python scripts/setup_drive.py
"""
import os
import sys
import json
import io

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dotenv
dotenv.load_dotenv()

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

SCOPES = ["https://www.googleapis.com/auth/drive"]

INITIAL_WIKI_JSON = json.dumps({
    "schema_version": "1",
    "updated_at": None,
    "last_processed_at": None,
    "items": []
}, ensure_ascii=False, indent=2)

INITIAL_INDEX_HTML = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>아이디어 위키</title></head>
<body><p>위키화가 완료되면 이 파일이 자동으로 업데이트됩니다.</p></body>
</html>"""


def get_service():
    refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")
    client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")

    if not all([refresh_token, client_id, client_secret]):
        print("❌ OAuth 환경변수가 설정되지 않았습니다.")
        print("   먼저 scripts/get_oauth_token.py를 실행하세요.")
        sys.exit(1)

    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )
    if not credentials.valid:
        credentials.refresh(Request())
    return build("drive", "v3", credentials=credentials)


def create_folder(service, name: str, parent_id: str = None) -> str:
    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_id:
        metadata["parents"] = [parent_id]
    folder = service.files().create(body=metadata, fields="id").execute()
    return folder["id"]


def upload_file(service, parent_id: str, filename: str, content: str, mime_type: str) -> str:
    media = MediaIoBaseUpload(
        io.BytesIO(content.encode("utf-8")),
        mimetype=mime_type,
        resumable=False,
    )
    file = service.files().create(
        body={"name": filename, "parents": [parent_id]},
        media_body=media,
        fields="id",
    ).execute()
    return file["id"]


def main():
    print("=" * 50)
    print("  아이디어 위키 드라이브 초기 설정")
    print("=" * 50)

    parent_input = input(
        "\n상위 폴더 ID를 입력하세요 (없으면 Enter — 내 드라이브 최상단에 생성): "
    ).strip()
    parent_id = parent_input if parent_input else None

    print("\nOAuth 사용자 계정으로 폴더를 생성합니다...")

    try:
        service = get_service()
    except Exception as e:
        print(f"❌ OAuth 인증 실패: {e}")
        sys.exit(1)

    # 1. wikis/ 폴더 생성
    print("  📁 wikis/ 폴더 생성 중...")
    wikis_id = create_folder(service, "wikis", parent_id)
    print(f"     완료 → ID: {wikis_id}")

    # 2. pic/ 서브폴더 생성
    print("  📁 wikis/pic/ 폴더 생성 중...")
    pic_id = create_folder(service, "pic", wikis_id)
    print(f"     완료 → ID: {pic_id}")

    # 3. wiki.json 업로드
    print("  📄 wiki.json 업로드 중...")
    wiki_json_id = upload_file(service, wikis_id, "wiki.json", INITIAL_WIKI_JSON, "application/json")
    print(f"     완료 → ID: {wiki_json_id}")

    # 4. index.html 업로드
    print("  📄 index.html 업로드 중...")
    viewer_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "viewer", "index.html"
    )
    if os.path.exists(viewer_path):
        with open(viewer_path, encoding="utf-8") as f:
            html_content = f.read()
        print("     (viewer/index.html 사용)")
    else:
        html_content = INITIAL_INDEX_HTML
    index_id = upload_file(service, wikis_id, "index.html", html_content, "text/html")
    print(f"     완료 → ID: {index_id}")

    # 5. 결과 출력
    print("\n" + "=" * 50)
    print("  ✅ 설정 완료!")
    print("=" * 50)
    print("\n아래 값을 .env 파일과 Render 환경변수에 업데이트하세요:\n")
    print(f"  DRIVE_WIKI_FOLDER_ID={wikis_id}")
    print(f"\n  (pic 폴더 ID: {pic_id}  — 자동 사용됨, 별도 설정 불필요)")
    print("\n구글 드라이브에서 확인:")
    print(f"  https://drive.google.com/drive/folders/{wikis_id}")
    print("\n기존 wikis 폴더는 삭제해도 됩니다.")


if __name__ == "__main__":
    main()
