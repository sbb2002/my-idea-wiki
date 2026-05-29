"""
Google Drive API v3 client.
Handles authentication and note file operations.
"""
import os
import io
import re
from typing import Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

SCOPES = ["https://www.googleapis.com/auth/drive"]

SUPPORTED_MIME_TYPES = [
    "text/plain",
    "application/vnd.google-apps.document",  # Google Docs
]

TAG_PATTERN = re.compile(r"#(\w+)")


def get_drive_service():
    """Build and return an authenticated Drive API service."""
    creds_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "./credentials/service_account.json")
    credentials = service_account.Credentials.from_service_account_file(
        creds_path, scopes=SCOPES
    )
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
        f"mimeType = 'text/plain'",
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
        # Export Google Docs as plain text
        response = service.files().export(fileId=file_id, mimeType="text/plain").execute()
        return response.decode("utf-8")
    else:
        request = service.files().get_media(fileId=file_id)
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
    These take priority over AI auto-classification.

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
            # Log and skip files that fail to read; don't abort entire batch
            print(f"[WARN] Failed to read file {f['name']} ({f['id']}): {e}")

    return notes


def upload_json(folder_id: str, filename: str, content: str, existing_file_id: Optional[str] = None, mime_type: str = "application/json") -> str:
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
            .update(fileId=existing_file_id, media_body=media)
            .execute()
        )
    else:
        metadata = {"name": filename, "parents": [folder_id]}
        file = (
            service.files()
            .create(body=metadata, media_body=media, fields="id")
            .execute()
        )

    return file["id"]


def find_file_in_folder(folder_id: str, filename: str) -> Optional[str]:
    """
    Find a file by name in a Drive folder.

    Returns:
        File ID if found, None otherwise.
    """
    service = get_drive_service()
    query = f"'{folder_id}' in parents and name = '{filename}' and trashed = false"
    response = service.files().list(q=query, fields="files(id)").execute()
    files = response.get("files", [])
    return files[0]["id"] if files else None
