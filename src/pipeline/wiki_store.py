"""
wiki.json 데이터 구조 정의 및 상태 관리.

wiki.json은 Drive에 저장되는 단일 파일이며, 모든 위키 아이템의 source of truth다.
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Optional


# ── 데이터 구조 ────────────────────────────────────────────────

def normalize_tags(tags: list[str], max_count: int = 10) -> list[str]:
    """
    태그 목록을 정규화한다.
    - '#' 없는 태그에 '#' 추가
    - 대소문자 무시 중복 제거 (먼저 나온 것 유지)
    - 최대 max_count개로 제한
    """
    seen: set[str] = set()
    result: list[str] = []
    for tag in tags:
        tag = tag.strip()
        if not tag:
            continue
        if not tag.startswith("#"):
            tag = "#" + tag
        key = tag.lower()
        if key not in seen:
            seen.add(key)
            result.append(tag)
        if len(result) >= max_count:
            break
    return result


def make_version(week: str, content: str, source_note_ids: list[str], tokens: int = 0) -> dict:
    return {
        "week": week,           # "YYYY-MM-DD" (파이프라인 실행일 또는 노트 수정일)
        "content": content,     # LLM이 작성한 이번 주 업데이트 요약
        "source_note_ids": source_note_ids,  # 이 버전을 구성한 원본 노트 Drive ID 목록
        "tokens": tokens,       # body 생성에 사용된 토큰 수 (body 미생성 시 0)
    }


def make_kickoff() -> dict:
    """빈 킥오프 필드를 반환한다. 1~5번은 파이프라인이 채우고, 6~7번은 항상 공란."""
    return {
        "core_value": "",          # 1. 핵심 가치 — AI 자동 생성
        "mvp_scope": "",           # 2. MVP 범위 — AI 자동 생성
        "ui_anchor": "",           # 3. UI 앵커 — AI 자동 생성
        "tech_rationale": "",      # 4. 기술 선택 근거 — AI 자동 생성
        "weak_points": "",         # 5. 가장 먼저 무너질 것 — AI 자동 생성
        "kill_condition": "",      # 6. Kill Condition — 사용자 작성
        "decision_log": [],        # 7. 의사결정 로그 — 사용자 작성 [{date, decision, reason, rejected_alternative}]
    }


def make_item(title: str, tags: list[str], summary: str, first_version: dict) -> dict:
    return {
        "id": f"item_{uuid.uuid4().hex[:8]}",
        "title": title,
        "tags": normalize_tags(tags),
        "summary": summary,       # 가장 최신 요약 (매 업데이트마다 덮어씀)
        "versions": [first_version],
        "related": [],            # 연관 아이템 ID 목록
        "comments": [],
        "kickoff": make_kickoff(),  # 킥오프 문서 (1~5: AI 자동, 6~7: 사용자 작성)
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
    kickoff: dict | None = None,
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
        # AI 생성 킥오프 값이 있으면 1~5번 필드만 반영 (6~7번은 항상 공란 유지)
        if kickoff:
            for key in ("core_value", "mvp_scope", "ui_anchor", "tech_rationale", "weak_points"):
                if kickoff.get(key):
                    item["kickoff"][key] = kickoff[key]
        wiki["items"].append(item)
        return item, True, False
    else:
        # 태그는 수동 태그 우선 — 기존 태그에 없는 것만 추가 후 정규화
        merged = existing["tags"] + [t for t in tags if t not in existing["tags"]]
        existing["tags"] = normalize_tags(merged)
        existing["summary"] = summary
        if body:
            existing["body"] = body
        if see_also is not None:
            existing["see_also"] = see_also
        # kickoff: 기존 아이템에 필드가 없으면 추가, 있으면 사용자 편집 보존
        # AI 생성값은 기존 킥오프의 빈 1~5번 필드에만 채움
        if "kickoff" not in existing:
            existing["kickoff"] = make_kickoff()
        if kickoff:
            for key in ("core_value", "mvp_scope", "ui_anchor", "tech_rationale", "weak_points"):
                if kickoff.get(key) and not existing["kickoff"].get(key):
                    existing["kickoff"][key] = kickoff[key]
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
    """오늘 날짜를 'YYYY-MM-DD' 형식으로 반환 (파이프라인 실행 날짜 기준)."""
    return datetime.now(timezone.utc).date().isoformat()


def note_modified_date(note: dict) -> str:
    """
    노트 dict에서 버전 날짜 문자열을 반환한다.

    - 노트에 modifiedTime(Drive API ISO 문자열)이 있으면 그 날짜(YYYY-MM-DD) 사용
    - 없으면 오늘 날짜(파이프라인 실행 날짜) 폴백
    """
    raw = note.get("modifiedTime") or note.get("modified_time") or ""
    if raw:
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            pass
    return current_week_str()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
