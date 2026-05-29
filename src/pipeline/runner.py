"""
위키화 파이프라인 오케스트레이터.

흐름:
  1. Drive에서 신규/변경 노트 읽기 (incremental)
  2. Claude API로 위키화 시도
  3. 실패 시 Gemini API 폴백
  4. wiki.json 업데이트 후 Drive에 저장
  5. HTML 뷰어 생성 후 Drive에 저장
  6. 처리 결과 집계 반환
"""
import os
import traceback
from datetime import datetime, timezone

from src.drive.client import read_notes_from_folder, upload_json, find_file_in_folder
from src.pipeline.wiki_store import (
    load_wiki, dump_wiki, upsert_item, make_version, current_week_str,
)
from src.pipeline.claude_processor import wikify_with_claude
from src.pipeline.gemini_processor import wikify_with_gemini

WIKI_FILENAME = "wiki.json"
VIEWER_FILENAME = "index.html"


def run_pipeline() -> dict:
    """
    위키화 파이프라인을 실행하고 결과를 반환한다.

    Returns:
        {
            "status": "success" | "partial" | "failure",
            "processed": int,       # 처리 시도한 노트 수
            "new_items": int,
            "updated_items": int,
            "skipped": int,         # 처리 실패한 노트 수
            "api_used": "claude" | "gemini" | None,
            "errors": list[str],    # 에러 메시지 목록
        }
    """
    notes_folder_id = os.getenv("DRIVE_NOTES_FOLDER_ID")
    wiki_folder_id = os.getenv("DRIVE_WIKI_FOLDER_ID")

    result = {
        "status": "success",
        "processed": 0,
        "new_items": 0,
        "updated_items": 0,
        "skipped": 0,
        "api_used": None,
        "errors": [],
    }

    # ── 1. 기존 wiki.json 로드 ──────────────────────────────────
    wiki_file_id = find_file_in_folder(wiki_folder_id, WIKI_FILENAME)
    if wiki_file_id:
        from src.drive.client import read_note
        wiki_json_str = read_note(wiki_file_id)
    else:
        wiki_json_str = ""

    wiki = load_wiki(wiki_json_str)
    last_processed_at = wiki.get("last_processed_at")

    # ── 2. 신규/변경 노트 읽기 (incremental) ───────────────────
    try:
        notes = read_notes_from_folder(notes_folder_id, modified_after=last_processed_at)
    except Exception as e:
        result["status"] = "failure"
        result["errors"].append(f"Drive 읽기 실패: {e}")
        return result

    if not notes:
        result["status"] = "success"
        return result  # 처리할 노트 없음

    result["processed"] = len(notes)

    # ── 3. AI 위키화 (Claude → Gemini 폴백) ────────────────────
    ai_items = None
    claude_error = None
    gemini_error = None

    try:
        ai_items = wikify_with_claude(notes)
        result["api_used"] = "claude"
    except Exception as e:
        claude_error = str(e)
        result["errors"].append(f"Claude 실패: {claude_error}")

    if ai_items is None:
        try:
            ai_items = wikify_with_gemini(notes)
            result["api_used"] = "gemini"
        except Exception as e:
            gemini_error = str(e)
            result["errors"].append(f"Gemini 실패: {gemini_error}")

    if ai_items is None:
        result["status"] = "failure"
        return result

    # ── 4. wiki.json 업데이트 ───────────────────────────────────
    week = current_week_str()
    skipped = 0

    for ai_item in ai_items:
        try:
            # source_note_ids: 이름으로 매핑
            source_names = ai_item.get("source_note_names", [])
            source_ids = [
                n["id"] for n in notes if n["name"] in source_names
            ]

            version = make_version(
                week=week,
                content=ai_item.get("content", ""),
                source_note_ids=source_ids,
            )
            _, is_new = upsert_item(
                wiki=wiki,
                title=ai_item["title"],
                tags=ai_item.get("tags", []),
                summary=ai_item.get("summary", ""),
                version=version,
            )
            if is_new:
                result["new_items"] += 1
            else:
                result["updated_items"] += 1
        except Exception as e:
            skipped += 1
            result["errors"].append(f"아이템 처리 실패 ({ai_item.get('title', '?')}): {e}")

    result["skipped"] = skipped

    # ── 5. wiki.json Drive 저장 ─────────────────────────────────
    wiki["last_processed_at"] = datetime.now(timezone.utc).isoformat()

    try:
        upload_json(
            folder_id=wiki_folder_id,
            filename=WIKI_FILENAME,
            content=dump_wiki(wiki),
            existing_file_id=wiki_file_id,
        )
    except Exception as e:
        result["status"] = "failure"
        result["errors"].append(f"wiki.json 저장 실패: {e}")
        return result

    # ── 6. HTML 뷰어 생성 후 Drive 저장 ────────────────────────
    try:
        from src.viewer.builder import build_viewer_html
        viewer_html = build_viewer_html(dump_wiki(wiki))
        viewer_file_id = find_file_in_folder(wiki_folder_id, VIEWER_FILENAME)
        upload_json(
            folder_id=wiki_folder_id,
            filename=VIEWER_FILENAME,
            content=viewer_html,
            existing_file_id=viewer_file_id,
            mime_type="text/html",
        )
    except Exception as e:
        # 뷰어 생성 실패는 경고로만 처리 — 위키화 결과에는 영향 없음
        print(f"[WARN] HTML 뷰어 생성 실패 (무시): {e}")
        result["errors"].append(f"뷰어 생성 실패 (무시됨): {e}")

    # ── 7. 최종 상태 결정 ──────────────────────────────────────
    if skipped > 0 and (result["new_items"] + result["updated_items"]) > 0:
        result["status"] = "partial"
    elif skipped == result["processed"]:
        result["status"] = "failure"

    return result
