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

from src.drive.client import (
    read_notes_from_folder, upload_json, find_file_in_folder,
    list_images, list_comment_files, download_file_bytes, IMAGE_MIME_TYPES,
    read_note,
)
from src.pipeline.wiki_store import (
    load_wiki, dump_wiki, upsert_item, make_version, current_week_str,
    make_attachment, add_attachment_to_item, add_comment_to_item,
)
from src.pipeline.claude_processor import wikify_with_claude, ocr_image_with_claude
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
        "ocr_processed": 0,
        "ocr_skipped": 0,
        "comments_processed": 0,
    }

    # ── 1. 기존 wiki.json 로드 ──────────────────────────────────
    wiki_file_id = find_file_in_folder(wiki_folder_id, WIKI_FILENAME)
    if wiki_file_id:
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
        # 노트가 없어도 OCR / 코멘트 처리는 계속 진행
        week = current_week_str()
        skipped = 0
    else:
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

    # ── 5-B. 이미지 OCR 처리 ────────────────────────────────────
    try:
        image_files = list_images(notes_folder_id, modified_after=last_processed_at)
    except Exception as e:
        image_files = []
        result["errors"].append(f"이미지 목록 조회 실패: {e}")

    for img in image_files:
        try:
            img_bytes = download_file_bytes(img["id"])
            ext = img.get("extension", ".jpg")
            mime = IMAGE_MIME_TYPES.get(ext, "image/jpeg")
            ocr_result = ocr_image_with_claude(img_bytes, mime, img["name"])

            # OCR 결과를 독립 아이템으로도 위키화 (summary를 제목 기반으로)
            att = make_attachment(
                drive_id=img["id"],
                filename=img["name"],
                ocr_text=ocr_result.get("ocr_text", ""),
                summary=ocr_result.get("summary", ""),
                tags=ocr_result.get("tags", []),
            )

            # 기존 아이템 중 태그가 겹치는 것에 첨부, 없으면 신규 아이템 생성
            matched = False
            for tag in att["tags"]:
                for item in wiki["items"]:
                    if tag in item.get("tags", []):
                        add_attachment_to_item(wiki, item["id"], att)
                        matched = True
                        break
                if matched:
                    break

            if not matched:
                # 독립 아이템으로 신규 생성
                stem = os.path.splitext(img["name"])[0]
                version = make_version(
                    week=week,
                    content=ocr_result.get("summary", "이미지 첨부"),
                    source_note_ids=[img["id"]],
                )
                item, is_new = upsert_item(
                    wiki=wiki,
                    title=stem,
                    tags=att["tags"],
                    summary=ocr_result.get("summary", ""),
                    version=version,
                )
                if "attachments" not in item:
                    item["attachments"] = []
                item["attachments"].append(att)
                if is_new:
                    result["new_items"] += 1
                else:
                    result["updated_items"] += 1

            result["ocr_processed"] += 1
        except Exception as e:
            result["ocr_skipped"] += 1
            result["errors"].append(f"OCR 실패 ({img.get('name', '?')}): {e}")

    # ── 5-C. 코멘트 파일 처리 ────────────────────────────────────
    try:
        comment_files = list_comment_files(notes_folder_id, modified_after=last_processed_at)
    except Exception as e:
        comment_files = []
        result["errors"].append(f"코멘트 목록 조회 실패: {e}")

    for cf in comment_files:
        try:
            text = read_note(cf["id"])
            added = add_comment_to_item(wiki, cf["item_id"], cf["date"], text)
            if added:
                result["comments_processed"] += 1
        except Exception as e:
            result["errors"].append(f"코멘트 처리 실패 ({cf.get('name', '?')}): {e}")

    try:
        upload_json(
            folder_id=wiki_folder_id,
            filename=WIKI_FILENAME,
            content=dump_wiki(wiki),
            existing_file_id=wiki_file_id,
        )
    except Exception as e:
        result["status"] = "failure"
        err_str = str(e)
        if "storageQuotaExceeded" in err_str or "storage quota" in err_str.lower():
            result["errors"].append(
                f"wiki.json 저장 실패: {e}\n도움말: 지정한 공유 wiki 폴더에 비어있는 index.html과 wiki.json을 업로드하십시오. 업로드 시 구글독스로 변환되지 않도록 설정하여 주십시오."
            )
        else:
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
        err_str = str(e)
        if "storageQuotaExceeded" in err_str or "storage quota" in err_str.lower():
            msg = f"index.html 저장 실패: {e}\n도움말: 지정한 공유 wiki 폴더에 비어있는 index.html과 wiki.json을 업로드하십시오. 업로드 시 구글독스로 변환되지 않도록 설정하여 주십시오."
        else:
            msg = f"뷰어 생성 실패 (무시됨): {e}"
        print(f"[WARN] HTML 뷰어 생성 실패 (무시): {e}")
        result["errors"].append(msg)

    # ── 7. 최종 상태 결정 ──────────────────────────────────────
    if skipped > 0 and (result["new_items"] + result["updated_items"]) > 0:
        result["status"] = "partial"
    elif result["processed"] > 0 and skipped == result["processed"]:
        result["status"] = "failure"

    return result
