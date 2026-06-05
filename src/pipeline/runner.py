"""
위키화 파이프라인 오케스트레이터.

흐름:
  1. Drive에서 신규/변경 노트 읽기 (incremental)
  2. Claude API로 위키화 시도
  3. 실패 시 Gemini API 폴백
  4. wiki.json 업데이트
  5. gh-pages 브랜치에 wiki.json + index.html push
     (GITHUB_TOKEN 설정 시, Drive에는 wiki.json 백업만 저장)
  6. 처리 결과 집계 반환
"""
import logging
import os
import traceback
from datetime import datetime, timezone

logger = logging.getLogger("idea-wiki.runner")

from src.drive.client import (
    read_notes_from_folder, upload_json, find_file_in_folder,
    list_images, list_comment_files, download_file_bytes, IMAGE_MIME_TYPES,
    read_note, list_all_note_ids,
)
from src.pipeline.wiki_store import (
    load_wiki, dump_wiki, upsert_item, make_version, current_week_str,
    make_attachment, add_attachment_to_item, add_comment_to_item,
    find_item_by_title, archive_prd,
)
from src.pipeline.claude_processor import wikify_with_claude, ocr_image_with_claude, process_pdf_with_claude, generate_prd
from src.pipeline.gemini_processor import wikify_with_gemini

WIKI_FILENAME = "wiki.json"
VIEWER_FILENAME = "index.html"


def run_pipeline(is_rerun: bool = False) -> dict:
    """
    위키화 파이프라인을 실행하고 결과를 반환한다.

    Args:
        is_rerun: True이면 /rerun 호출 (전체 재처리). 알람 문구에 재처리 여부 표시. (#30)

    Returns:
        {
            "status": "success" | "partial" | "failure",
            "processed": int,        # 처리 시도한 노트 수
            "new_items": int,
            "updated_items": int,
            "overwrite_count": int,  # 동일 week content 덮어쓴 수 (rerun 시 양수) (#30)
            "skipped": int,          # 처리 실패한 노트 수
            "api_used": "claude" | "gemini" | None,
            "errors": list[str],     # 에러 메시지 목록
            "is_rerun": bool,        # rerun 여부 (#30)
        }
    """
    notes_folder_id = os.getenv("DRIVE_NOTES_FOLDER_ID")
    wiki_folder_id = os.getenv("DRIVE_WIKI_FOLDER_ID")

    result = {
        "status": "success",
        "processed": 0,
        "new_items": 0,
        "updated_items": 0,
        "overwrite_count": 0,   # 동일 week content 덮어쓴 수 (#30)
        "skipped": 0,
        "api_used": None,
        "errors": [],
        "ocr_processed": 0,
        "ocr_skipped": 0,
        "comments_processed": 0,
        "is_rerun": is_rerun,   # rerun 여부 (#30)
        "prd_generated": 0,     # PRD 생성 성공 수
        "prd_failed": 0,        # PRD 생성 실패 수
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

    # ── 2-B. PDF 노트 전처리 (Vision 분석 → 텍스트 노트로 변환) ───
    pic_folder_id = os.getenv("DRIVE_PIC_FOLDER_ID")
    pdf_notes = [n for n in notes if n.get("mimeType") == "application/pdf"]
    text_notes = [n for n in notes if n.get("mimeType") != "application/pdf"]

    for pdf_note in pdf_notes:
        try:
            pdf_bytes = download_file_bytes(pdf_note["id"])
            pdf_result = process_pdf_with_claude(pdf_bytes, pdf_note["name"], pic_folder_id=pic_folder_id)

            # drawings 수집 — 위키화 후 첨부로 연결하기 위해 보관
            pdf_note["_drawings"] = [
                d
                for page in pdf_result.get("pages", [])
                for d in page.get("drawings", [])
                if d.get("pic_drive_id")
            ]

            # PDF 분석 결과를 텍스트 노트로 변환해 파이프라인에 합류
            text_notes.append({
                "id": pdf_note["id"],
                "name": pdf_note["name"],
                "mimeType": "text/plain",
                "modifiedTime": pdf_note["modifiedTime"],
                "content": (
                    "[PDF 분석 결과: " + pdf_note["name"] + "]\n\n"
                    + pdf_result.get("full_text", "") + "\n\n"
                    + "전체 요약: " + pdf_result.get("overall_summary", "")
                ),
                "tags": pdf_result.get("tags", []),
                "_drawings": pdf_note["_drawings"],  # drawings 전달
            })
            result["ocr_processed"] += 1
        except Exception as e:
            result["ocr_skipped"] += 1
            result["errors"].append(f"PDF 처리 실패 ({pdf_note.get('name', '?')}): {e}")

    notes = text_notes

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

        existing_items = wiki.get("items", [])

        try:
            ai_items = wikify_with_claude(notes, existing_items=existing_items)
            result["api_used"] = "claude"
        except Exception as e:
            claude_error = str(e)
            result["errors"].append(f"Claude 실패: {claude_error}")

        if ai_items is None:
            try:
                ai_items = wikify_with_gemini(notes, existing_items=existing_items)
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
                _, is_new, is_overwrite = upsert_item(
                    wiki=wiki,
                    title=ai_item["title"],
                    tags=ai_item.get("tags", []),
                    summary=ai_item.get("summary", ""),
                    version=version,
                    body=ai_item.get("body", ""),
                    see_also=ai_item.get("see_also", []),
                )
                if is_new:
                    result["new_items"] += 1
                else:
                    result["updated_items"] += 1
                if is_overwrite:
                    result["overwrite_count"] += 1  # rerun 시 같은 week content 덮어씀 (#30)

                # PDF drawings → 해당 아이템에 첨부로 연결 (#14)
                item_obj = find_item_by_title(wiki, ai_item["title"])
                if item_obj:
                    for note_name in source_names:
                        note_entry = next((n for n in notes if n["name"] == note_name), None)
                        if note_entry and note_entry.get("_drawings"):
                            for drawing in note_entry["_drawings"]:
                                # #33: claude_processor가 저장한 filename 사용 (뷰어 attByFilename 매핑 일치)
                                drawing_filename = drawing.get("filename") or f"{note_name}_drawing"
                                att = make_attachment(
                                    drive_id=drawing["pic_drive_id"],
                                    filename=drawing_filename,
                                    ocr_text="",
                                    summary=drawing.get("description", ""),
                                    tags=[],
                                    pic_drive_id=drawing["pic_drive_id"],
                                    description=drawing.get("description", ""),
                                )
                                add_attachment_to_item(wiki, item_obj["id"], att)
            except Exception as e:
                skipped += 1
                result["errors"].append(f"아이템 처리 실패 ({ai_item.get('title', '?')}): {e}")

    result["skipped"] = skipped

    # ── 5. 위키 데이터 저장 및 gh-pages 배포 ──────────────────────
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
                item, is_new, is_overwrite = upsert_item(
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
                if is_overwrite:
                    result["overwrite_count"] += 1  # (#30)

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

    wiki_json_str = dump_wiki(wiki)

    # ── 5-A. gh-pages 브랜치에 wiki.json + index.html push ──────
    github_token = os.getenv("GITHUB_TOKEN", "")
    if github_token:
        try:
            from src.github.gh_pages import push_wiki_to_gh_pages
            push_wiki_to_gh_pages(wiki_json_str)
            print("[INFO] gh-pages push 완료")
        except Exception as e:
            # push 실패는 치명적이지 않음 — 경고만 남기고 계속
            print(f"[WARN] gh-pages push 실패: {e}")
            result["errors"].append(f"gh-pages push 실패 (무시됨): {e}")
    else:
        print("[WARN] GITHUB_TOKEN 미설정 — gh-pages push 건너뜀")

    # ── 5-B. Drive wiki.json 백업 저장 (pic/ 폴더 상위 유지 목적) ──
    try:
        upload_json(
            folder_id=wiki_folder_id,
            filename=WIKI_FILENAME,
            content=wiki_json_str,
            existing_file_id=wiki_file_id,
        )
    except Exception as e:
        result["status"] = "failure"
        err_str = str(e)
        if "storageQuotaExceeded" in err_str or "storage quota" in err_str.lower():
            result["errors"].append(
                f"wiki.json Drive 저장 실패: {e}\n"
                "도움말: wiki 폴더에 비어있는 wiki.json을 업로드하십시오. "
                "구글독스로 변환되지 않도록 설정하여 주십시오."
            )
        else:
            result["errors"].append(f"wiki.json Drive 저장 실패: {e}")
        return result

    # ── 6. 최종 상태 결정 ──────────────────────────────────────
    if skipped > 0 and (result["new_items"] + result["updated_items"]) > 0:
        result["status"] = "partial"
    elif result["processed"] > 0 and skipped == result["processed"]:
        result["status"] = "failure"

    # ── 6-B. PRD 생성 ─────────────────────────────────────────
    # 생성 조건:
    #   - run:   prd가 None인 아이템만 생성 (이미 있으면 토큰 절약을 위해 스킵)
    #   - rerun: 기존 prd를 prd_history로 보관 후 항상 재생성
    # 이번 실행에서 신규/업데이트된 아이템에만 적용
    processed_titles = {ai_item.get("title") for ai_item in (ai_items or [])}
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for item in wiki["items"]:
        if item.get("title") not in processed_titles:
            continue  # 이번 실행에서 처리되지 않은 아이템은 스킵

        has_prd = bool(item.get("prd"))

        # run 모드: 이미 PRD가 있으면 스킵
        if not is_rerun and has_prd:
            logger.info(f"PRD 스킵 (이미 존재): {item['title']}")
            continue

        # rerun 모드: 기존 PRD를 history로 보관
        if is_rerun and has_prd:
            archive_prd(item, today_str)
            logger.info(f"PRD 아카이브 완료: {item['title']} ({today_str})")

        try:
            related_ids = item.get("related", [])
            related_items_ctx = [
                {"title": r["title"], "summary": r.get("summary", "")}
                for r in wiki["items"]
                if r["id"] in related_ids and r.get("title")
            ]
            prd_md = generate_prd(item, related_items_ctx)
            item["prd"] = prd_md
            result["prd_generated"] += 1
            logger.info(f"PRD 생성 완료: {item['title']}")
        except Exception as e:
            result["prd_failed"] += 1
            result["errors"].append(f"PRD 생성 실패 ({item.get('title', '?')}): {e}")
            logger.warning(f"PRD 생성 실패 ({item.get('title', '?')}): {e}")

    # ── 7. 고아 아이템 감지 및 자동 제거 (#31, #36) ──────────
    # Drive에 존재하지 않는 source_note_ids만 가진 아이템을 wiki.json에서 직접 삭제
    try:
        live_ids = list_all_note_ids(notes_folder_id)
        orphan_ids = []
        orphan_titles = []
        for item in wiki["items"]:
            all_ids = []
            for v in item.get("versions", []):
                all_ids.extend(v.get("source_note_ids", []))
            # 이미지 첨부 ID도 포함 (이미지가 source_note_id인 경우 오탐 방지 위해 #31 선행 필수)
            for att in item.get("attachments", []):
                if att.get("drive_id"):
                    all_ids.append(att["drive_id"])
            if all_ids and not any(nid in live_ids for nid in all_ids):
                orphan_ids.append(item["id"])
                orphan_titles.append(item["title"])

        if orphan_ids:
            before_count = len(wiki["items"])
            wiki["items"] = [it for it in wiki["items"] if it["id"] not in set(orphan_ids)]
            after_count = len(wiki["items"])
            logger.info(f"고아 아이템 {before_count - after_count}개 자동 제거: {orphan_titles}")

        result["orphan_items"] = orphan_titles
    except Exception as e:
        result["orphan_items"] = []
        result["errors"].append(f"고아 아이템 감지 실패 (무시됨): {e}")

    return result
