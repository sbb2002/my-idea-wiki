"""
서비스 계정 명의로 wikis 폴더 구조를 생성하는 초기 설정 스크립트.

실행하면:
  1. 서비스 계정이 소유한 wikis/ 폴더 생성
  2. 그 안에 pic/ 서브폴더 생성
  3. 빈 wiki.json, index.html 자동 업로드
  4. 사용자 Gmail에 편집자 권한 공유
  5. 생성된 폴더 ID 출력 → .env / Render 환경변수에 업데이트 필요

사용법:
  python scripts/setup_drive.py

사전 준비:
  - .env 파일에 GOOGLE_SERVICE_ACCOUNT_JSON, DRIVE_NOTES_FOLDER_ID 설정
  - credentials/service_account.json 배치
"""
import os
import sys
import json
import io

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dotenv
dotenv.load_dotenv()

from google.oauth2 import service_account
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
    creds_value = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "./credentials/service_account.json")
    if creds_value.strip().startswith("{"):
        info = json.loads(creds_value)
        credentials = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        credentials = service_account.Credentials.from_service_account_file(creds_value, scopes=SCOPES)
    return build("drive", "v3", credentials=credentials)


def create_folder(service, name: str, parent_id: str = None) -> str:
    """서비스 계정 명의로 폴더 생성 후 ID 반환."""
    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_id:
        metadata["parents"] = [parent_id]

    folder = service.files().create(
        body=metadata,
        fields="id",
        supportsAllDrives=True,
    ).execute()
    return folder["id"]


def upload_file(service, folder_id: str, filename: str, content: str, mime_type: str) -> str:
    """서비스 계정 명의로 파일 생성 후 ID 반환."""
    media = MediaIoBaseUpload(
        io.BytesIO(content.encode("utf-8")),
        mimetype=mime_type,
        resumable=False,
    )
    file = service.files().create(
        body={"name": filename, "parents": [folder_id]},
        media_body=media,
        fields="id",
        supportsAllDrives=True,
    ).execute()
    return file["id"]


def share_with_user(service, file_id: str, email: str, role: str = "writer"):
    """파일/폴더를 사용자 이메일에 공유."""
    service.permissions().create(
        fileId=file_id,
        body={
            "type": "user",
            "role": role,
            "emailAddress": email,
        },
        supportsAllDrives=True,
        sendNotificationEmail=False,
    ).execute()


def main():
    print("=" * 50)
    print("  아이디어 위키 드라이브 초기 설정")
    print("=" * 50)

    # 사용자 Gmail 입력
    user_email = input("\n구글 드라이브 계정 이메일을 입력하세요: ").strip()
    if not user_email or "@" not in user_email:
        print("❌ 유효하지 않은 이메일입니다.")
        sys.exit(1)

    # 선택: 상위 폴더 ID (my-idea-wiki 폴더 등)
    parent_input = input(
        "\n상위 폴더 ID를 입력하세요 (없으면 Enter — 내 드라이브 최상단에 생성): "
    ).strip()
    parent_id = parent_input if parent_input else None

    print("\n서비스 계정으로 폴더를 생성합니다...")

    try:
        service = get_service()
    except Exception as e:
        print(f"❌ 서비스 계정 인증 실패: {e}")
        sys.exit(1)

    # 1. wikis/ 폴더 생성
    print("  📁 wikis/ 폴더 생성 중...")
    wikis_id = create_folder(service, "wikis", parent_id)
    print(f"     완료 → ID: {wikis_id}")

    # 2. pic/ 서브폴더 생성
    print("  📁 wikis/pic/ 폴더 생성 중...")
    pic_id = create_folder(service, "pic", wikis_id)
    print(f"     완료 → ID: {pic_id}")

    # 3. 빈 wiki.json 업로드
    print("  📄 wiki.json 업로드 중...")
    wiki_json_id = upload_file(service, wikis_id, "wiki.json", INITIAL_WIKI_JSON, "application/json")
    print(f"     완료 → ID: {wiki_json_id}")

    # 4. 빈 index.html 업로드
    print("  📄 index.html 업로드 중...")
    # viewer/index.html이 있으면 사용, 없으면 초기 버전
    viewer_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "viewer", "index.html")
    if os.path.exists(viewer_path):
        with open(viewer_path, encoding="utf-8") as f:
            html_content = f.read()
        print("     (viewer/index.html 사용)")
    else:
        html_content = INITIAL_INDEX_HTML
    index_id = upload_file(service, wikis_id, "index.html", html_content, "text/html")
    print(f"     완료 → ID: {index_id}")

    # 5. 사용자에게 편집자 권한 공유
    print(f"\n  🔗 {user_email}에게 편집자 권한 공유 중...")
    share_with_user(service, wikis_id, user_email, role="writer")
    print("     완료")

    # 6. 결과 출력
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
