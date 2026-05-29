"""
텔레그램 봇 Webhook 핸들러.

FastAPI의 POST /webhook 요청을 처리하고 5개 명령어를 구현한다.

명령어:
  /run      — 즉시 위키화 실행
  /status   — 마지막 실행 결과 조회
  /schedule — 현재 실행 주기 확인
  /set <주기> — 실행 주기 변경
  /cancel   — 예약된 실행 취소
"""
import asyncio
import os
import threading
from datetime import datetime, timezone
from typing import Optional

import httpx

from src.telegram.notifier import send_message, _bot_url, _chat_id

# ── 상태 저장 (메모리, 재시작 시 소멸 허용) ─────────────────────
_last_run_result: Optional[dict] = None
_schedule_cron: str = os.getenv("SCHEDULE_CRON", "0 9 * * 1")
_schedule_description: str = "매주 월요일 오전 9시 (UTC)"
_pipeline_running: bool = False
_cold_start_warned: bool = False  # 이번 프로세스 생애 첫 /run 여부


def _mark_started() -> None:
    """서버가 처음 시작되면 이미 warm 상태임을 기록."""
    global _cold_start_warned
    _cold_start_warned = True


def _reply(chat_id: str | int, text: str) -> None:
    """동기 방식으로 텔레그램 메시지 전송."""
    try:
        httpx.post(
            _bot_url("sendMessage"),
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        print(f"[WARN] reply 실패: {e}")


# ── 명령어 핸들러 ───────────────────────────────────────────────

def _handle_run(chat_id: str | int) -> None:
    global _pipeline_running, _last_run_result

    if _pipeline_running:
        _reply(chat_id, "⏳ 이미 위키화 작업이 진행 중입니다.")
        return

    # 콜드 스타트 직후 첫 요청이 아니라면 warm 상태이므로 안내 불필요
    # 어쨌든 즉시 응답 후 백그라운드 실행
    _reply(chat_id, "🚀 위키화를 시작합니다...")

    def _run_in_thread():
        global _pipeline_running, _last_run_result
        _pipeline_running = True
        try:
            from src.pipeline.runner import run_pipeline
            result = run_pipeline()
            _last_run_result = {
                **result,
                "run_at": datetime.now(timezone.utc).isoformat(),
            }
            from src.telegram.notifier import notify_result
            notify_result(result)
        except Exception as e:
            error_msg = f"❌ 위키화 실행 중 오류: {e}"
            _reply(chat_id, error_msg)
            _last_run_result = {
                "status": "failure",
                "errors": [str(e)],
                "run_at": datetime.now(timezone.utc).isoformat(),
            }
        finally:
            _pipeline_running = False

    thread = threading.Thread(target=_run_in_thread, daemon=True)
    thread.start()


def _handle_status(chat_id: str | int) -> None:
    if _last_run_result is None:
        _reply(chat_id, "ℹ️ 아직 실행된 기록이 없습니다.\n/run 으로 위키화를 시작하세요.")
        return

    r = _last_run_result
    run_at = r.get("run_at", "알 수 없음")
    status = r.get("status", "unknown")
    emoji = {"success": "✅", "partial": "⚠️", "failure": "❌"}.get(status, "❓")

    lines = [
        f"{emoji} <b>마지막 실행 결과</b>",
        f"• 실행 시각: {run_at}",
        f"• 상태: {status}",
        f"• 처리: {r.get('processed', 0)}개 노트",
        f"• 신규: {r.get('new_items', 0)}개 / 업데이트: {r.get('updated_items', 0)}개",
    ]
    if r.get("errors"):
        lines.append(f"• 오류: {', '.join(r['errors'][:2])}")

    _reply(chat_id, "\n".join(lines))


def _handle_schedule(chat_id: str | int) -> None:
    text = (
        f"📅 <b>현재 실행 주기</b>\n"
        f"• Cron: <code>{_schedule_cron}</code>\n"
        f"• 설명: {_schedule_description}\n\n"
        f"변경하려면: /set &lt;cron 표현식&gt;\n"
        f"예시: <code>/set 0 9 * * 1</code> (매주 월요일 오전 9시 UTC)"
    )
    _reply(chat_id, text)


def _handle_set(chat_id: str | int, args: str) -> None:
    global _schedule_cron, _schedule_description

    cron_expr = args.strip()
    if not cron_expr:
        _reply(chat_id, "❗ 사용법: /set &lt;cron 표현식&gt;\n예: /set 0 9 * * 1")
        return

    parts = cron_expr.split()
    if len(parts) != 5:
        _reply(
            chat_id,
            "❗ Cron 표현식은 5개 필드여야 합니다.\n"
            "예: <code>0 9 * * 1</code> (분 시 일 월 요일)\n\n"
            "<b>참고</b>: Render Cron Job의 실제 스케줄은 Render 대시보드에서 변경해야 합니다.\n"
            "이 명령어는 메모 목적으로만 저장됩니다."
        )
        return

    old_cron = _schedule_cron
    _schedule_cron = cron_expr
    _schedule_description = f"사용자 설정 ({cron_expr})"

    text = (
        f"✅ 실행 주기가 업데이트되었습니다.\n"
        f"• 이전: <code>{old_cron}</code>\n"
        f"• 변경: <code>{cron_expr}</code>\n\n"
        f"⚠️ Render Cron Job의 실제 스케줄은 Render 대시보드에서 별도로 변경해야 합니다."
    )
    _reply(chat_id, text)


def _handle_cancel(chat_id: str | int) -> None:
    global _pipeline_running

    if _pipeline_running:
        # 실행 중인 스레드를 강제 종료할 수는 없으므로 안내만
        _reply(
            chat_id,
            "⚠️ 현재 위키화가 진행 중입니다. 강제 중단은 지원되지 않습니다.\n"
            "잠시 후 자동으로 완료됩니다.",
        )
    else:
        _reply(
            chat_id,
            "ℹ️ 현재 예약된 실행이 없습니다.\n"
            "Render Cron Job 스케줄을 취소하려면 Render 대시보드에서 직접 중지해주세요.",
        )


# ── Webhook 진입점 ───────────────────────────────────────────────

def handle_update(update: dict) -> None:
    """
    텔레그램 Update 객체를 파싱하고 적절한 핸들러를 호출한다.
    """
    global _cold_start_warned

    message = update.get("message") or update.get("edited_message")
    if not message:
        return  # callback_query 등 무시

    chat_id = message.get("chat", {}).get("id")
    text: str = message.get("text", "")

    if not text.startswith("/"):
        return  # 명령어가 아닌 메시지 무시

    # "@botname" suffix 제거 (그룹 채팅 대응)
    command_part = text.split()[0].split("@")[0]
    args = text[len(command_part):].strip()

    # 콜드 스타트 감지: /run 수신 시 서버가 막 깨어난 경우 안내
    if command_part == "/run" and not _cold_start_warned:
        _reply(chat_id, "⏳ 잠시만 기다려주세요~ 서버를 깨우는 중입니다.")
        _cold_start_warned = True

    if command_part == "/run":
        _handle_run(chat_id)
    elif command_part == "/status":
        _handle_status(chat_id)
    elif command_part == "/schedule":
        _handle_schedule(chat_id)
    elif command_part == "/set":
        _handle_set(chat_id, args)
    elif command_part == "/cancel":
        _handle_cancel(chat_id)
    else:
        _reply(
            chat_id,
            "❓ 알 수 없는 명령어입니다.\n\n"
            "사용 가능한 명령어:\n"
            "/run — 즉시 위키화 실행\n"
            "/status — 마지막 실행 결과\n"
            "/schedule — 현재 실행 주기\n"
            "/set &lt;cron&gt; — 주기 변경\n"
            "/cancel — 예약 취소",
        )
