"""
Google Drive API v3 client.
Handles authentication and note file operations.
"""
import os
import io
import re
from typing import Optional
import json as _json
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

SCOPES = ["https://www.googleapis.com/auth/drive"]

SUPPORTED_MIME_TYPES = [
    "text/plain",
    "application/vnd.google-apps.document",  # Google Docs
]

TAG_PATTERN = re.compile(r"#(\w+)")

PDF_MIME_TYPE = "application/pdf"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif"}
IMAGE_MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".heif": "image/heif",
}

# 코멘트 파일명 패턴: comment_<item_id>_<날짜>.txt
COMMENT_PATTERN = re.compile(r"^comment_(.+)_(\d{4}-\d{2}-\d{2})\.txt$")

# 내 드라이브 공유 폴더 접근에 필요한 공통 파라미터
_ALL_DRIVES_PARAMS = {
    "supportsAllDrives": True,
    "includeItemsFromAllDrives": True,
}


def get_drive_service():
    """Build and return an authenticated Drive API service.

    OAuth 우선 사용. GOOGLE_REFRESH_TOKEN이 없으면 서비스 계정으로 폴백.
    """
    refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")
    client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")

    if refresh_token and client_id and client_secret:
        credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=SCOPES,
        )
        # Access Token이 없거나 만료됐으면 자동 갱신
        if not credentials.valid:
            credentials.refresh(Request())
        return build("drive", "v3", credentials=credentials)

    # 폴백: 서비스 계정
    creds_value = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "./credentials/service_account.json")
    if creds_value.strip().startswith("{"):
        info = _json.loads(creds_value)
        credentials = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        credentials = service_account.Credentials.from_service_account_file(creds_value, scopes=SCOPES)
    return build("drive", "v3", credentials=credentials)


def list_notes(folder_id: str, modified_after: Optional[str] = None) -> list[dict]:
    """
    List text note files in the specified Drive folder.

    Args:
        folder_id: Google Drive folder ID to scan.
        modified_after: ISO 8601 datetime string. If provided, only returns
                        files modified after this time (for incremental processing).

    Returns:
        List of dicts with keys: id, name, mimeType, modifiedTime.
    """
    service = get_drive_service()

    query_parts = [
        f"'{folder_id}' in parents",
        "trashed = false",
        "(mimeType = 'text/plain' or mimeType = 'application/vnd.google-apps.document' or mimeType = 'application/pdf')",
    ]
    if modified_after:
        query_parts.append(f"modifiedTime > '{modified_after}'")

    query = " and ".join(query_parts)

    results = []
    page_token = None

    while True:
        response = (
            service.files()
            .list(
                q=query,
                fields="nextPageToken, files(id, name, mimeType, modifiedTime)",
                pageToken=page_token,
                **_ALL_DRIVES_PARAMS,
            )
            .execute()
        )
        results.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return results


def read_note(file_id: str, mime_type: str = "text/plain") -> str:
    """
    Download and return the text content of a Drive file.

    Args:
        file_id: Google Drive file ID.
        mime_type: MIME type of the file.

    Returns:
        Text content of the file.
    """
    service = get_drive_service()

    if mime_type == "application/vnd.google-apps.document":
        response = (
            service.files()
            .export(fileId=file_id, mimeType="text/plain")
            .execute()
        )
        return response.decode("utf-8")
    else:
        request = service.files().get_media(fileId=file_id, **{"supportsAllDrives": True})
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buffer.getvalue().decode("utf-8")


def extract_tags(content: str) -> list[str]:
    """
    Extract manual tags from note content.
    Tags are in the format #tagname (alphanumeric + underscore).

    Args:
        content: Raw text content of the note.

    Returns:
        List of tag strings (without the # prefix), deduplicated.
    """
    return list(dict.fromkeys(TAG_PATTERN.findall(content)))


def read_notes_from_folder(
    folder_id: str, modified_after: Optional[str] = None
) -> list[dict]:
    """
    List and read all notes from a Drive folder.

    Args:
        folder_id: Google Drive folder ID.
        modified_after: Only return notes modified after this ISO 8601 datetime.

    Returns:
        List of dicts with keys: id, name, content, tags, modifiedTime.
    """
    files = list_notes(folder_id, modified_after=modified_after)
    notes = []

    for f in files:
        try:
            content = read_note(f["id"], f["mimeType"])
            tags = extract_tags(content)
            notes.append(
                {
                    "id": f["id"],
                    "name": f["name"],
                    "content": content,
                    "tags": tags,
                    "modifiedTime": f["modifiedTime"],
                }
            )
        except Exception as e:
            print(f"[WARN] Failed to read file {f['name']} ({f['id']}): {e}")

    return notes


def upload_json(
    folder_id: str,
    filename: str,
    content: str,
    existing_file_id: Optional[str] = None,
    mime_type: str = "application/json",
) -> str:
    """
    Upload or update a file in the specified Drive folder.

    Args:
        folder_id: Google Drive folder ID.
        filename: Name of the file to create/update.
        content: File content as string.
        existing_file_id: If provided, update this file instead of creating a new one.
        mime_type: MIME type of the file (default: application/json).

    Returns:
        File ID of the created/updated file.
    """
    service = get_drive_service()
    media = MediaIoBaseUpload(
        io.BytesIO(content.encode("utf-8")),
        mimetype=mime_type,
        resumable=False,
    )

    if existing_file_id:
        file = (
            service.files()
            .update(
                fileId=existing_file_id,
                media_body=media,
                supportsAllDrives=True,
            )
            .execute()
        )
    else:
        metadata = {"name": filename, "parents": [folder_id]}
        file = (
            service.files()
            .create(
                body=metadata,
                media_body=media,
                fields="id",
                supportsAllDrives=True,
            )
            .execute()
        )

    return file["id"]


def download_file_bytes(file_id: str) -> bytes:
    """
    Drive 파일의 raw bytes를 다운로드해 반환한다.

    Args:
        file_id: Google Drive file ID.

    Returns:
        File content as bytes.
    """
    service = get_drive_service()
    request = service.files().get_media(fileId=file_id, **{"supportsAllDrives": True})
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buffer.getvalue()


def list_images(folder_id: str, modified_after: Optional[str] = None) -> list[dict]:
    """
    Drive 폴더에서 이미지 파일 목록을 반환한다.

    Args:
        folder_id: Google Drive folder ID.
        modified_after: ISO 8601 datetime. 이후 수정된 파일만 반환.

    Returns:
        List of dicts: id, name, mimeType, modifiedTime, extension
    """
    service = get_drive_service()

    mime_conditions = " or ".join(
        f"mimeType = '{m}'" for m in set(IMAGE_MIME_TYPES.values())
    )
    query_parts = [
        f"'{folder_id}' in parents",
        "trashed = false",
        f"({mime_conditions})",
    ]
    if modified_after:
        query_parts.append(f"modifiedTime > '{modified_after}'")

    query = " and ".join(query_parts)
    results = []
    page_token = None

    while True:
        response = (
            service.files()
            .list(
                q=query,
                fields="nextPageToken, files(id, name, mimeType, modifiedTime)",
                pageToken=page_token,
                **_ALL_DRIVES_PARAMS,
            )
            .execute()
        )
        for f in response.get("files", []):
            ext = os.path.splitext(f["name"])[1].lower()
            if ext in IMAGE_EXTENSIONS:
                f["extension"] = ext
                results.append(f)
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return results


def list_comment_files(folder_id: str, modified_after: Optional[str] = None) -> list[dict]:
    """
    Drive 폴더에서 코멘트 파일(comment_<item_id>_<날짜>.txt) 목록을 반환한다.

    Returns:
        List of dicts: id, name, item_id, date, modifiedTime
    """
    files = list_notes(folder_id, modified_after=modified_after)
    comment_files = []
    for f in files:
        match = COMMENT_PATTERN.match(f["name"])
        if match:
            f["item_id"] = match.group(1)
            f["date"] = match.group(2)
            comment_files.append(f)
    return comment_files


def find_file_in_folder(folder_id: str, filename: str) -> Optional[str]:
    """
    Find a file by name in a Drive folder.

    Returns:
        File ID if found, None otherwise.
    """
    service = get_drive_service()
    query = f"'{folder_id}' in parents and name = '{filename}' and trashed = false"
    response = (
        service.files()
        .list(q=query, fields="files(id)", **_ALL_DRIVES_PARAMS)
        .execute()
    )
    files = response.get("files", [])
    return files[0]["id"] if files else None
