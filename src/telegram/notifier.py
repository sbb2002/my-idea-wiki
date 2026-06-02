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
    """Drive 뷰어 index.html의 공유 URL을 반환한다. 환경변수 미설정 시 빈 문자열."""
    file_id = os.getenv("DRIVE_VIEWER_FILE_ID", "")
    if not file_id:
        return ""
    return f"https://drive.google.com/file/d/{file_id}/view"


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


def notify_result(result: dict) -> bool:
    """
    run_pipeline() 반환값을 받아 적절한 알람을 전송한다.
    노트가 없어서 처리 건수가 0인 경우는 알람 없이 스킵한다.
    """
    status = result.get("status")
    processed = result.get("processed", 0)

    if processed == 0:
        return True  # 처리할 노트 없음 — 알람 불필요

    if status == "success":
        return notify_success(
            processed=processed,
            new_items=result.get("new_items", 0),
            updated_items=result.get("updated_items", 0),
            api_used=result.get("api_used", "unknown"),
        )
    elif status == "partial":
        succeeded = result.get("new_items", 0) + result.get("updated_items", 0)
        return notify_partial(
            processed=processed,
            succeeded=succeeded,
            skipped=result.get("skipped", 0),
            errors=result.get("errors", []),
        )
    else:  # failure
        return notify_failure(errors=result.get("errors", []))
