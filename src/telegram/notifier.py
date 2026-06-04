"""
텔레그램 알람 전송 유틸리티.
위키화 파이프라인 결과를 3종 메시지 포맷으로 전송한다.
"""
import os
import httpx
from datetime import datetime, timezone


def _bot_url(method: str) -> str:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    return f"https://api.telegram.org/bot{token}/{method}"


def _chat_id() -> str:
    return os.getenv("TELEGRAM_CHAT_ID", "")


def send_message(text: str) -> bool:
    """
    텔레그램 메시지를 전송한다.

    Returns:
        True if sent successfully, False otherwise.
    """
    try:
        resp = httpx.post(
            _bot_url("sendMessage"),
            json={"chat_id": _chat_id(), "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        return resp.status_code == 200
    except Exception as e:
        print(f"[WARN] 텔레그램 전송 실패: {e}")
        return False


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _viewer_url() -> str:
    """
    GitHub Pages 뷰어 URL을 반환한다.
    GITHUB_TOKEN 이 설정된 경우 gh-pages URL을 우선 사용하고,
    미설정이면 Drive wikis 폴더 URL을 폴백으로 반환한다.
    """
    if os.getenv("GITHUB_TOKEN"):
        try:
            from src.github.gh_pages import gh_pages_url
            url = gh_pages_url()
            if url:
                return url
        except Exception:
            pass
    # 폴백: Drive 폴더
    folder_id = os.getenv("DRIVE_WIKI_FOLDER_ID", "")
    if not folder_id:
        return ""
    return f"https://drive.google.com/drive/folders/{folder_id}"


def notify_success(processed: int, new_items: int, updated_items: int, api_used: str) -> bool:
    """✅ 성공 알람."""
    viewer = _viewer_url()
    viewer_line = f"\n• 뷰어: {viewer}" if viewer else ""
    text = (
        f"✅ [{_today()}] 위키화 완료\n"
        f"• 처리: {processed}개 노트\n"
        f"• 신규: {new_items}개 / 업데이트: {updated_items}개\n"
        f"• 사용 API: {api_used}"
        f"{viewer_line}"
    )
    return send_message(text)


def notify_partial(processed: int, succeeded: int, skipped: int, errors: list[str]) -> bool:
    """⚠️ 부분 성공 알람."""
    error_summary = "\n".join(f"  - {e}" for e in errors[:3])  # 최대 3개만 표시
    viewer = _viewer_url()
    viewer_line = f"\n• 뷰어: {viewer}" if viewer else ""
    text = (
        f"⚠️ [{_today()}] 일부 실패\n"
        f"• {processed}개 중 {succeeded}개 처리, {skipped}개 스킵\n"
        f"• 오류:\n{error_summary}"
        f"{viewer_line}"
    )
    return send_message(text)


def notify_failure(errors: list[str]) -> bool:
    """❌ 전체 실패 알람."""
    error_summary = "\n".join(f"  - {e}" for e in errors)
    text = (
        f"❌ [{_today()}] 위키화 실패\n"
        f"• 오류:\n{error_summary}"
    )
    return send_message(text)


def notify_orphans(titles: list[str]) -> bool:
    """🔍 고아 아이템 감지 알람 — Drive에서 원본 노트가 삭제된 아이템."""
    items_str = "\n".join(f"  • {t}" for t in titles[:10])
    suffix = f"\n  … 외 {len(titles) - 10}개" if len(titles) > 10 else ""
    text = (
        f"🔍 [{_today()}] 고아 아이템 감지\n"
        f"Drive에서 원본 노트가 삭제된 아이템이 wiki.json에 잔류 중입니다.\n"
        f"{items_str}{suffix}\n"
        f"필요 시 wiki.json에서 수동으로 삭제하세요."
    )
    return send_message(text)


def notify_result(result: dict) -> bool:
    """
    run_pipeline() 반환값을 받아 적절한 알람을 전송한다.
    노트가 없어서 처리 건수가 0인 경우는 알람 없이 스킵한다.
    """
    status = result.get("status")
    processed = result.get("processed", 0)

    if processed == 0:
        # 처리할 노트 없어도 고아 아이템이 있으면 알람
        orphans = result.get("orphan_items", [])
        if orphans:
            notify_orphans(orphans)
        return True

    if status == "success":
        ok = notify_success(
            processed=processed,
            new_items=result.get("new_items", 0),
            updated_items=result.get("updated_items", 0),
            api_used=result.get("api_used", "unknown"),
        )
    elif status == "partial":
        succeeded = result.get("new_items", 0) + result.get("updated_items", 0)
        ok = notify_partial(
            processed=processed,
            succeeded=succeeded,
            skipped=result.get("skipped", 0),
            errors=result.get("errors", []),
        )
    else:  # failure
        ok = notify_failure(errors=result.get("errors", []))

    # 고아 아이템 알람 (status와 무관하게 별도 전송)
    orphans = result.get("orphan_items", [])
    if orphans:
        notify_orphans(orphans)

    return ok
