"""
wiki.json 데이터 구조 정의 및 상태 관리.

wiki.json은 Drive에 저장되는 단일 파일이며, 모든 위키 아이템의 source of truth다.
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Optional


# ── 데이터 구조 ────────────────────────────────────────────────

def make_version(week: str, content: str, source_note_ids: list[str]) -> dict:
    return {
        "week": week,           # "YYYY-MM-DD" (해당 주 월요일)
        "content": content,     # LLM이 작성한 이번 주 업데이트 요약
        "source_note_ids": source_note_ids,  # 이 버전을 구성한 원본 노트 Drive ID 목록
    }


def make_item(title: str, tags: list[str], summary: str, first_version: dict) -> dict:
    return {
        "id": f"item_{uuid.uuid4().hex[:8]}",
        "title": title,
        "tags": tags,
        "summary": summary,       # 가장 최신 요약 (매 업데이트마다 덮어씀)
        "versions": [first_version],
        "related": [],            # 연관 아이템 ID 목록
        "comments": [],
        "prd": None,               # LLM 친화적 PRD (Markdown, 파이프라인 생성)
        "prd_history": [],         # 이전 PRD 버전 목록 [{date, content}]
    }


def empty_wiki() -> dict:
    return {
        "schema_version": "1",
        "updated_at": _now_iso(),
        "last_processed_at": None,  # 마지막 위키화 실행 시각 (incremental 기준점)
        "items": [],
    }


# ── 로드 / 저장 헬퍼 ───────────────────────────────────────────

def load_wiki(json_str: str) -> dict:
    """JSON 문자열 → wiki dict. 빈 문자열이면 빈 위키 반환."""
    if not json_str or not json_str.strip():
        return empty_wiki()
    return json.loads(json_str)


def dump_wiki(wiki: dict) -> str:
    """wiki dict → JSON 문자열 (pretty-print)."""
    wiki["updated_at"] = _now_iso()
    return json.dumps(wiki, ensure_ascii=False, indent=2)


# ── 아이템 조회 / 조작 ─────────────────────────────────────────

def find_item_by_id(wiki: dict, item_id: str) -> Optional[dict]:
    for item in wiki["items"]:
        if item["id"] == item_id:
            return item
    return None


def find_item_by_title(wiki: dict, title: str) -> Optional[dict]:
    """대소문자 무시 제목 검색."""
    title_lower = title.lower()
    for item in wiki["items"]:
        if item["title"].lower() == title_lower:
            return item
    return None


def upsert_item(
    wiki: dict,
    title: str,
    tags: list[str],
    summary: str,
    version: dict,
    body: str = "",
    see_also: list[dict] | None = None,
) -> tuple[dict, bool, bool]:
    """
    아이템을 추가하거나 업데이트한다.

    - 동일 제목 아이템이 없으면 신규 생성
    - 있으면 summary/body/see_also 갱신 + versions 앞에 추가 (최신순)

    Returns:
        (item, is_new, is_overwrite):
            item        — 아이템 dict
            is_new      — True이면 신규 생성
            is_overwrite — True이면 동일 week content를 덮어씀 (#30)
    """
    existing = find_item_by_title(wiki, title)
    if existing is None:
        item = make_item(title, tags, summary, version)
        item["body"] = body
        item["see_also"] = see_also or []
        wiki["items"].append(item)
        return item, True, False
    else:
        # 태그는 수동 태그 우선 — 기존 태그에 없는 것만 추가
        for tag in tags:
            if tag not in existing["tags"]:
                existing["tags"].append(tag)
        existing["summary"] = summary
        if body:
            existing["body"] = body
        if see_also is not None:
            existing["see_also"] = see_also
        # 동일 week 버전이 이미 있으면 content만 업데이트 (중복 삽입 방지)
        same_week = next((v for v in existing["versions"] if v.get("week") == version.get("week")), None)
        if same_week:
            same_week["content"] = version["content"]
            same_week["source_note_ids"] = list(set(same_week.get("source_note_ids", []) + version.get("source_note_ids", [])))
            return existing, False, True   # is_overwrite=True (#30)
        else:
            existing["versions"].insert(0, version)  # 최신이 앞
            return existing, False, False


# ── 유틸 ───────────────────────────────────────────────────────

def make_attachment(
    drive_id: str,
    filename: str,
    ocr_text: str,
    summary: str,
    tags: list[str],
    pic_drive_id: str | None = None,
    description: str | None = None,
) -> dict:
    """이미지 첨부 파일 dict를 생성한다."""
    att = {
        "type": "image",
        "drive_id": drive_id,
        "filename": filename,
        "ocr_text": ocr_text,
        "summary": summary,
        "tags": tags,
    }
    if pic_drive_id:
        att["pic_drive_id"] = pic_drive_id
    if description:
        att["description"] = description
    return att


def add_attachment_to_item(wiki: dict, item_id: str, attachment: dict) -> bool:
    """
    아이템에 첨부 파일을 추가한다. drive_id가 이미 존재하면 업데이트(중복 방지).

    Returns:
        True if added, False if updated existing.
    """
    item = find_item_by_id(wiki, item_id)
    if item is None:
        return False
    if "attachments" not in item:
        item["attachments"] = []
    for att in item["attachments"]:
        # drive_id 또는 filename이 동일하면 중복으로 판단 (#34)
        same_id = att.get("drive_id") == attachment["drive_id"]
        same_filename = (
            attachment.get("filename")
            and att.get("filename") == attachment["filename"]
        )
        if same_id or same_filename:
            att.update(attachment)
            return False
    item["attachments"].append(attachment)
    return True


def archive_prd(item: dict, archived_at: str) -> bool:
    """
    현재 PRD를 prd_history로 이동한다. rerun 시 기존 PRD 보존용.

    Args:
        item: wiki 아이템 dict (직접 수정)
        archived_at: 보관 날짜 문자열 (YYYY-MM-DD)

    Returns:
        True if archived, False if prd was None (nothing to archive)
    """
    current_prd = item.get("prd")
    if not current_prd:
        return False

    if "prd_history" not in item:
        item["prd_history"] = []

    item["prd_history"].insert(0, {   # 최신이 앞
        "date": archived_at,
        "content": current_prd,
    })
    item["prd"] = None
    return True


def add_comment_to_item(wiki: dict, item_id: str, date: str, text: str, attachments: Optional[list] = None) -> bool:
    """
    아이템에 코멘트를 추가한다. 같은 날짜 코멘트는 중복 방지.

    Returns:
        True if added, False if already exists.
    """
    item = find_item_by_id(wiki, item_id)
    if item is None:
        return False
    for c in item.get("comments", []):
        if c.get("date") == date:
            c["text"] = text  # 재업로드 시 덮어씀
            return False
    item["comments"].append({
        "date": date,
        "text": text,
        "attachments": attachments or [],
    })
    return True



def current_week_str() -> str:
    """이번 주 월요일 날짜를 'YYYY-MM-DD' 형식으로 반환."""
    today = datetime.now(timezone.utc).date()
    monday = today - __import__("datetime").timedelta(days=today.weekday())
    return monday.isoformat()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
