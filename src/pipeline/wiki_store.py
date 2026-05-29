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


def upsert_item(wiki: dict, title: str, tags: list[str], summary: str, version: dict) -> tuple[dict, bool]:
    """
    아이템을 추가하거나 업데이트한다.

    - 동일 제목 아이템이 없으면 신규 생성
    - 있으면 summary 갱신 + versions 앞에 추가 (최신순)

    Returns:
        (item, is_new): 아이템 dict와 신규 여부
    """
    existing = find_item_by_title(wiki, title)
    if existing is None:
        item = make_item(title, tags, summary, version)
        wiki["items"].append(item)
        return item, True
    else:
        # 태그는 수동 태그 우선 — 기존 태그에 없는 것만 추가
        for tag in tags:
            if tag not in existing["tags"]:
                existing["tags"].append(tag)
        existing["summary"] = summary
        existing["versions"].insert(0, version)  # 최신이 앞
        return existing, False


# ── 유틸 ───────────────────────────────────────────────────────

def current_week_str() -> str:
    """이번 주 월요일 날짜를 'YYYY-MM-DD' 형식으로 반환."""
    today = datetime.now(timezone.utc).date()
    monday = today - __import__("datetime").timedelta(days=today.weekday())
    return monday.isoformat()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
