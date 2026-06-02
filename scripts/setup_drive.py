"""
공유 드라이브(Shared Drive)를 생성하는 초기 설정 스크립트.

서비스 계정은 일반 내 드라이브에 파일을 신규 생성할 수 없어서
공유 드라이브를 사용합니다. 공유 드라이브는 특정 계정 소유가 아닌
독립 공간이므로 서비스 계정이 자유롭게 파일을 생성할 수 있습니다.

실행하면:
  1. 서비스 계정 명의로 공유 드라이브 'my-idea-wiki' 생성
  2. 그 안에 pic/ 서브폴더 생성
  3. wiki.json, index.html 자동 업로드
  4. 사용자 Gmail에 편집자 권한 공유
  5. 생성된 DRIVE_WIKI_FOLDER_ID 출력

사용법:
  python scripts/setup_drive.py
"""
import os
import sys
import json
import io
import uuid

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


def create_shared_drive(service, name: str) -> str:
    """공유 드라이브 생성 후 ID 반환."""
    drive = service.drives().create(
        requestId=str(uuid.uuid4()),
        body={"name": name},
    ).execute()
    return drive["id"]


def create_folder(service, name: str, parent_id: str) -> str:
    """공유 드라이브 안에 폴더 생성 후 ID 반환."""
    folder = service.files().create(
        body={
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        },
        fields="id",
        supportsAllDrives=True,
    ).execute()
    return folder["id"]


def upload_file(service, parent_id: str, filename: str, content: str, mime_type: str) -> str:
    """공유 드라이브 안에 파일 업로드 후 ID 반환."""
    media = MediaIoBaseUpload(
        io.BytesIO(content.encode("utf-8")),
        mimetype=mime_type,
        resumable=False,
    )
    file = service.files().create(
        body={"name": filename, "parents": [parent_id]},
        media_body=media,
        fields="id",
        supportsAllDrives=True,
    ).execute()
    return file["id"]


def share_with_user(service, resource_id: str, email: str, role: str = "fileOrganizer"):
    """공유 드라이브를 사용자에게 공유."""
    service.permissions().create(
        fileId=resource_id,
        body={
            "type": "user",
            "role": role,
            "emailAddress": email,
        },
        supportsAllDrives=True,
        useDomainAdminAccess=False,
        sendNotificationEmail=False,
    ).execute()


def main():
    print("=" * 50)
    print("  아이디어 위키 드라이브 초기 설정")
    print("=" * 50)
    print("\n공유 드라이브(Shared Drive)를 생성합니다.")
    print("서비스 계정이 파일을 자유롭게 생성하려면 공유 드라이브가 필요합니다.")

    user_email = input("\n구글 드라이브 계정 이메일을 입력하세요: ").strip()
    if not user_email or "@" not in user_email:
        print("❌ 유효하지 않은 이메일입니다.")
        sys.exit(1)

    print("\n서비스 계정으로 공유 드라이브를 생성합니다...")

    try:
        service = get_service()
    except Exception as e:
        print(f"❌ 서비스 계정 인증 실패: {e}")
        sys.exit(1)

    # 1. 공유 드라이브 생성
    print("  🚗 공유 드라이브 'my-idea-wiki' 생성 중...")
    try:
        shared_drive_id = create_shared_drive(service, "my-idea-wiki")
        print(f"     완료 → ID: {shared_drive_id}")
    except Exception as e:
        print(f"❌ 공유 드라이브 생성 실패: {e}")
        print("\n  가능한 원인:")
        print("  - 일반 Gmail 계정은 공유 드라이브 생성이 제한될 수 있습니다.")
        print("  - GCP 프로젝트에서 Drive API가 활성화되어 있는지 확인하세요.")
        sys.exit(1)

    # 2. pic/ 서브폴더 생성
    print("  📁 pic/ 폴더 생성 중...")
    pic_id = create_folder(service, "pic", shared_drive_id)
    print(f"     완료 → ID: {pic_id}")

    # 3. wiki.json 업로드
    print("  📄 wiki.json 업로드 중...")
    wiki_json_id = upload_file(service, shared_drive_id, "wiki.json", INITIAL_WIKI_JSON, "application/json")
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
    index_id = upload_file(service, shared_drive_id, "index.html", html_content, "text/html")
    print(f"     완료 → ID: {index_id}")

    # 5. 사용자에게 편집자 권한 공유
    print(f"\n  🔗 {user_email}에게 편집자 권한 공유 중...")
    try:
        share_with_user(service, shared_drive_id, user_email)
        print("     완료")
    except Exception as e:
        print(f"  ⚠️  공유 실패 (수동으로 공유 설정 필요): {e}")

    # 6. 결과 출력
    print("\n" + "=" * 50)
    print("  ✅ 설정 완료!")
    print("=" * 50)
    print("\n아래 값을 .env 파일과 Render 환경변수에 업데이트하세요:\n")
    print(f"  DRIVE_WIKI_FOLDER_ID={shared_drive_id}")
    print(f"\n  (pic 폴더 ID: {pic_id}  — 자동 사용됨, 별도 설정 불필요)")
    print("\n구글 드라이브에서 확인 (좌측 메뉴 → 공유 드라이브):")
    print(f"  https://drive.google.com/drive/folders/{shared_drive_id}")
    print("\n기존 wikis 폴더와 임시 생성된 wikis/ 폴더는 삭제해도 됩니다.")


if __name__ == "__main__":
    main()
