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
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Optional

import httpx

import atexit
import signal
import sys

from src.telegram.notifier import send_message, _bot_url, _viewer_url

log = logging.getLogger("idea-wiki.bot")

# ── 상태 저장 (메모리, 재시작 시 소멸 허용) ─────────────────────
_last_run_result: Optional[dict] = None
_schedule_cron: str = os.getenv("SCHEDULE_CRON", "0 9 * * 1")
_schedule_description: str = "매주 월요일 오전 9시 (UTC)"
_pipeline_running: bool = False
_cold_start_warned: bool = False  # 이번 프로세스 생애 첫 /run 여부

# chat_id → {"item": dict, "title": str, "reasons": list[str]}
# /prd 부실 판정 후 y/n 대기 중인 상태를 보관한다.
_prd_pending: dict[str | int, dict] = {}


def _mark_started() -> None:
    """서버가 처음 시작되면 이미 warm 상태임을 기록."""
    global _cold_start_warned
    _cold_start_warned = True


def _keepalive_start() -> None:
    """파이프라인 스레드에서 main.py의 start_keepalive()를 호출한다."""
    try:
        from src.main import start_keepalive
        start_keepalive()
    except Exception as e:
        log.warning(f"[keepalive] start 실패: {e}")


def _keepalive_stop() -> None:
    """파이프라인 스레드에서 main.py의 stop_keepalive()를 호출한다."""
    try:
        from src.main import stop_keepalive
        stop_keepalive()
    except Exception as e:
        log.warning(f"[keepalive] stop 실패: {e}")


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

    _reply(chat_id, "🚀 위키화를 시작합니다...")
    log.info("[run] 파이프라인 시작")

    def _run_in_thread():
        global _pipeline_running, _last_run_result
        _pipeline_running = True
        _keepalive_start()   # 파이프라인 시작 시 keep-alive ON
        try:
            log.info("[run] run_pipeline() 호출")
            from src.pipeline.runner import run_pipeline
            result = run_pipeline()
            log.info(f"[run] 완료: {result}")
            _last_run_result = {
                **result,
                "run_at": datetime.now(timezone.utc).isoformat(),
            }
            from src.telegram.notifier import notify_result
            notify_result(result)
            viewer = _viewer_url()
            if viewer:
                _reply(chat_id, f"📄 뷰어에서 결과를 확인하세요:\n{viewer}")
        except Exception as e:
            log.error(f"[run] 오류: {e}", exc_info=True)
            _reply(chat_id, f"❌ 위키화 실행 중 오류: {e}")
            _last_run_result = {
                "status": "failure",
                "errors": [str(e)],
                "run_at": datetime.now(timezone.utc).isoformat(),
            }
        finally:
            _keepalive_stop()    # 파이프라인 완료 시 keep-alive OFF
            _pipeline_running = False
            log.info("[run] 스레드 종료")

    thread = threading.Thread(target=_run_in_thread, daemon=False)
    thread.start()


def _handle_status(chat_id: str | int) -> None:
    if _pipeline_running:
        _reply(chat_id, "⏳ 현재 위키화가 진행 중입니다. 완료되면 결과 알람이 전송됩니다.")
        return

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


def _handle_help(chat_id: str | int) -> None:
    text = (
        "📖 <b>사용 가능한 명령어</b>\n\n"
        "/run\n"
        "  → 즉시 위키화 실행. 드라이브 노트 폴더의 새 노트를 처리합니다.\n\n"
        "/rerun\n"
        "  → 전체 재처리. last_processed_at을 초기화하고 모든 노트를 다시 위키화합니다.\n"
        "  (노트가 스킵되거나 결과가 이상할 때 사용)\n\n"
        "/list\n"
        "  → 위키 아이템 목록을 최초 생성일 순으로 표시\n\n"
        "/list --tags\n"
        "  → 아이템 목록 + 태그 표시 (최대 3개)\n\n"
        "/overview N\n"
        "  → N번 아이템의 개요를 출력합니다. 번호는 /list 에서 확인하세요.\n\n"
        "/prd N\n"
        "  → N번 아이템의 PRD를 AI로 생성해 GitHub Pages에 저장합니다.\n"
        "  번호는 /list 에서 확인하세요.\n\n"
        "/status\n"
        "  → 현재 실행 중이면 진행 중 안내, 완료됐으면 마지막 실행 결과 조회\n\n"
        "/schedule\n"
        "  → 현재 자동 실행 주기(Cron 표현식) 확인\n\n"
        "/set &lt;cron 표현식&gt;\n"
        "  → 실행 주기 메모 변경\n"
        "  예: <code>/set 0 9 * * 1</code> (매주 월요일 오전 9시 UTC)\n"
        "  ⚠️ 실제 Render Cron Job 스케줄은 Render 대시보드에서 변경하세요.\n\n"
        "/help\n"
        "  → 이 도움말 표시"
    )
    _reply(chat_id, text)


def _handle_list(chat_id: str | int, args: str) -> None:
    """wiki.json에서 아이템 목록을 최초 생성일 오름차순으로 출력한다."""
    show_tags = "--tags" in args

    try:
        from src.drive.client import find_file_in_folder, read_note
        from src.pipeline.wiki_store import load_wiki

        wiki_folder_id = os.getenv("DRIVE_WIKI_FOLDER_ID")
        wiki_file_id = find_file_in_folder(wiki_folder_id, "wiki.json")
        if not wiki_file_id:
            _reply(chat_id, "ℹ️ 아직 위키 데이터가 없습니다.\n/run 으로 위키화를 먼저 실행하세요.")
            return

        wiki = load_wiki(read_note(wiki_file_id))
        items = wiki.get("items", [])

        if not items:
            _reply(chat_id, "ℹ️ 등록된 아이템이 없습니다.\n/run 으로 위키화를 먼저 실행하세요.")
            return

        def _first_created(item: dict) -> str:
            versions = item.get("versions", [])
            if versions:
                return versions[-1].get("week", "9999-99-99")
            return "9999-99-99"

        sorted_items = sorted(items, key=_first_created)

        lines = [f"📋 <b>위키 아이템 목록</b> ({len(sorted_items)}개)\n"]

        for i, item in enumerate(sorted_items, 1):
            title = item.get("title", "(제목 없음)")
            date = _first_created(item)

            if show_tags:
                tags = item.get("tags", [])
                if len(tags) <= 3:
                    tag_str = "  " + " ".join(tags) if tags else ""
                else:
                    tag_str = "  " + " ".join(tags[:3]) + " [#...]"
                lines.append(f"{i:2}. {title}\n    📅 {date}{tag_str}")
            else:
                lines.append(f"{i:2}. {title}  ·  {date}")

        _reply(chat_id, "\n".join(lines))

    except Exception as e:
        log.error(f"[list] 오류: {e}", exc_info=True)
        _reply(chat_id, f"❌ 목록 조회 중 오류: {e}")


def _handle_overview(chat_id: str | int, args: str) -> None:
    """N번 아이템의 개요를 출력한다."""
    n_str = args.strip()

    # 숫자 유효성 검사
    try:
        n = int(n_str)
        if n <= 0:
            raise ValueError
    except ValueError:
        _reply(chat_id, "해당 아이템이 없습니다. 먼저 /list 로 확인해주세요.")
        return

    try:
        from src.drive.client import find_file_in_folder, read_note
        from src.pipeline.wiki_store import load_wiki

        wiki_folder_id = os.getenv("DRIVE_WIKI_FOLDER_ID")
        wiki_file_id = find_file_in_folder(wiki_folder_id, "wiki.json")
        if not wiki_file_id:
            _reply(chat_id, "ℹ️ 아직 위키 데이터가 없습니다.\n/run 으로 위키화를 먼저 실행하세요.")
            return

        wiki = load_wiki(read_note(wiki_file_id))
        items = wiki.get("items", [])

        if not items:
            _reply(chat_id, "ℹ️ 등록된 아이템이 없습니다.\n/run 으로 위키화를 먼저 실행하세요.")
            return

        def _first_created(item: dict) -> str:
            versions = item.get("versions", [])
            if versions:
                return versions[-1].get("week", "9999-99-99")
            return "9999-99-99"

        sorted_items = sorted(items, key=_first_created)

        if n > len(sorted_items):
            _reply(chat_id, "해당 아이템이 없습니다. 먼저 /list 로 확인해주세요.")
            return

        item = sorted_items[n - 1]
        title = item.get("title", "(제목 없음)")
        tags = item.get("tags", [])
        summary = item.get("summary", "(요약 없음)")
        versions = item.get("versions", [])
        latest = versions[0] if versions else None

        tag_str = " ".join(tags) if tags else "(없음)"
        date = _first_created(item)

        lines = [
            f"📄 <b>{n}. {title}</b>",
            f"📅 최초 등록: {date}",
            f"🏷 태그: {tag_str}",
            "",
            f"<b>요약</b>",
            summary,
        ]

        if latest:
            lines += [
                "",
                f"<b>최신 업데이트</b> ({latest.get('week', '')})",
                latest.get("content", "(내용 없음)"),
            ]

        _reply(chat_id, "\n".join(lines))

    except Exception as e:
        log.error(f"[overview] 오류: {e}", exc_info=True)
        _reply(chat_id, f"❌ 개요 조회 중 오류: {e}")


def _handle_prd(chat_id: str | int, args: str) -> None:
    """/prd N — N번 아이템의 PRD를 생성해 gh-pages에 push한다."""
    n_str = args.strip()

    try:
        n = int(n_str)
        if n <= 0:
            raise ValueError
    except ValueError:
        _reply(chat_id, "❗ 사용법: /prd &lt;번호&gt;\n예: <code>/prd 3</code>\n번호는 /list 에서 확인하세요.")
        return

    try:
        from src.drive.client import find_file_in_folder, read_note
        from src.pipeline.wiki_store import load_wiki

        wiki_folder_id = os.getenv("DRIVE_WIKI_FOLDER_ID")
        wiki_file_id = find_file_in_folder(wiki_folder_id, "wiki.json")
        if not wiki_file_id:
            _reply(chat_id, "ℹ️ 아직 위키 데이터가 없습니다.\n/run 으로 위키화를 먼저 실행하세요.")
            return

        wiki = load_wiki(read_note(wiki_file_id))
        items = wiki.get("items", [])

        if not items:
            _reply(chat_id, "ℹ️ 등록된 아이템이 없습니다.\n/run 으로 위키화를 먼저 실행하세요.")
            return

        def _first_created(item: dict) -> str:
            versions = item.get("versions", [])
            if versions:
                return versions[-1].get("week", "9999-99-99")
            return "9999-99-99"

        sorted_items = sorted(items, key=_first_created)

        if n > len(sorted_items):
            _reply(chat_id, f"해당 아이템이 없습니다. 먼저 /list 로 확인해주세요.")
            return

        item = sorted_items[n - 1]

    except Exception as e:
        log.error(f"[prd] wiki 로드 오류: {e}", exc_info=True)
        _reply(chat_id, f"❌ 위키 데이터 로드 중 오류: {e}")
        return

    title = item.get("title", "(제목 없음)")

    # ── viability check ──────────────────────────────────────────
    body = item.get("versions", [{}])[0].get("content", "") if item.get("versions") else ""
    try:
        from src.main import check_prd_viability, ViabilityRequest
        import asyncio as _asyncio
        v_req = ViabilityRequest(
            title=title,
            tags=item.get("tags", []),
            summary=item.get("summary", ""),
            body=body,
        )
        result = _asyncio.run(check_prd_viability(v_req))
        if not result.get("sufficient", True):
            reasons = result.get("reasons", [])
            reason_text = "\n".join(f"  • {r}" for r in reasons)
            warning = (
                f"⚠️ <b>{title}</b> 아이템의 내용이 PRD로 만들기에 부실합니다.\n\n"
                f"부실 이유:\n{reason_text}\n\n"
                f"바이브 코딩이 불가능할 수 있습니다.\n"
                f"그래도 PRD로 만드시겠습니까? (y/N)"
            )
            _prd_pending[chat_id] = {"item": item, "title": title}
            _reply(chat_id, warning)
            return
    except Exception as e:
        log.warning(f"[prd] viability check 실패, 그냥 진행: {e}")
    # ────────────────────────────────────────────────────────────

    _execute_prd(chat_id, item, title)


def _execute_prd(chat_id: str | int, item: dict, title: str) -> None:
    """PRD 생성을 스레드로 실행한다. viability check 통과 후 호출된다."""
    _reply(chat_id, f"🤖 <b>{title}</b>의 PRD를 생성 중입니다…")
    log.info(f"[prd] 생성 시작: {item.get('id')} — {title}")

    def _run_in_thread():
        try:
            import anthropic as _anthropic
            from src.main import _build_prd_prompt, _PRD_SYSTEM_PROMPT, PrdRequest
            from src.github.gh_pages import push_file

            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                _reply(chat_id, "❌ ANTHROPIC_API_KEY가 서버에 설정되지 않았습니다.")
                return

            # 연관 아이템 summary 수집
            all_items = {i.get("id"): i for i in item.get("_wiki_items", [])}
            related_items = [
                {"title": all_items[r].get("title", r), "summary": all_items[r].get("summary", "")}
                for r in item.get("related", [])
                if r in all_items
            ]

            # 기존 PRD가 있으면 prd_history로 보관
            if item.get("prd"):
                if not isinstance(item.get("prd_history"), list):
                    item["prd_history"] = []
                item["prd_history"].insert(0, {
                    "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    "content": item["prd"],
                })
                item["prd"] = None

            req = PrdRequest(
                item_id=item.get("id", ""),
                title=title,
                tags=item.get("tags", []),
                summary=item.get("summary", ""),
                body=item.get("versions", [{}])[0].get("content", "") if item.get("versions") else "",
                related_items=related_items,
            )

            client = _anthropic.Anthropic(api_key=api_key)
            prompt = _build_prd_prompt(req)
            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=_PRD_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            prd_text = message.content[0].text.strip()

            if not prd_text:
                _reply(chat_id, "❌ Claude 응답이 비어있습니다.")
                return

            prd_path = f"prd/{req.item_id}.md"
            push_file(prd_path, prd_text, f'prd: generate PRD for "{title}"')

            repo = os.getenv("GITHUB_REPO", "sbb2002/my-idea-wiki")
            branch = os.getenv("GITHUB_BRANCH", "gh-pages")
            raw_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{prd_path}"

            lines = [
                f"✅ <b>{title}</b> PRD 생성 완료!",
                f"📄 {raw_url}",
            ]
            _reply(chat_id, "\n".join(lines))
            log.info(f"[prd] 완료: {prd_path}")

        except Exception as e:
            log.error(f"[prd] 오류: {e}", exc_info=True)
            _reply(chat_id, f"❌ PRD 생성 중 오류: {e}")

    thread = threading.Thread(target=_run_in_thread, daemon=False)
    thread.start()


def _handle_rerun(chat_id: str | int) -> None:
    """last_processed_at을 초기화하고 전체 노트를 재처리한다."""
    global _pipeline_running, _last_run_result

    if _pipeline_running:
        _reply(chat_id, "⏳ 이미 위키화 작업이 진행 중입니다.")
        return

    _reply(chat_id, "🔄 전체 재처리를 시작합니다... (last_processed_at 초기화)")
    log.info("[rerun] 전체 재처리 시작")

    def _run_in_thread():
        global _pipeline_running, _last_run_result
        _pipeline_running = True
        _keepalive_start()   # 파이프라인 시작 시 keep-alive ON
        try:
            from src.pipeline.runner import run_pipeline
            from src.drive.client import find_file_in_folder, upload_json, read_note
            from src.pipeline.wiki_store import load_wiki, dump_wiki

            wiki_folder_id = os.getenv("DRIVE_WIKI_FOLDER_ID")
            log.info(f"[rerun] wiki.json last_processed_at 초기화 (폴더: {wiki_folder_id})")
            wiki_file_id = find_file_in_folder(wiki_folder_id, "wiki.json")
            if wiki_file_id:
                wiki = load_wiki(read_note(wiki_file_id))
                wiki["last_processed_at"] = None
                upload_json(wiki_folder_id, "wiki.json", dump_wiki(wiki), existing_file_id=wiki_file_id)
                log.info("[rerun] last_processed_at 초기화 완료")

            log.info("[rerun] run_pipeline(is_rerun=True) 호출")
            result = run_pipeline(is_rerun=True)  # #30: rerun 여부 전달
            log.info(f"[rerun] 완료: {result}")
            _last_run_result = {
                **result,
                "run_at": datetime.now(timezone.utc).isoformat(),
            }
            from src.telegram.notifier import notify_result
            notify_result(result)
            viewer = _viewer_url()
            if viewer:
                _reply(chat_id, f"📄 뷰어에서 결과를 확인하세요:\n{viewer}")
        except Exception as e:
            log.error(f"[rerun] 오류: {e}", exc_info=True)
            _reply(chat_id, f"❌ 재처리 중 오류: {e}")
            _last_run_result = {
                "status": "failure",
                "errors": [str(e)],
                "run_at": datetime.now(timezone.utc).isoformat(),
            }
        finally:
            _keepalive_stop()    # 파이프라인 완료 시 keep-alive OFF
            _pipeline_running = False
            log.info("[rerun] 스레드 종료")

    thread = threading.Thread(target=_run_in_thread, daemon=False)
    thread.start()


# ── 프로세스 종료 알람 ──────────────────────────────────────────

def _notify_shutdown(reason: str) -> None:
    """파이프라인 실행 중 프로세스가 예기치 않게 종료될 때 텔레그램 알람."""
    if not _pipeline_running:
        return  # 파이프라인이 안 돌고 있으면 알람 불필요 (정상 슬립 등)
    try:
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        send_message(
            f"⚠️ [{ts}] 파이프라인 중단 감지\n"
            f"• 원인: {reason}\n"
            f"• 파이프라인이 완료되지 않았을 수 있습니다.\n"
            f"• /status 로 상태를 확인하고 필요 시 /run 또는 /rerun 으로 재실행하세요."
        )
    except Exception as e:
        log.warning(f"[shutdown] 알람 전송 실패: {e}")


def _handle_sigterm(signum, frame) -> None:
    """Render 배포 교체 시 SIGTERM 수신 → 알람 후 종료."""
    log.warning("[shutdown] SIGTERM 수신 — 프로세스 종료 예정")
    _notify_shutdown("SIGTERM (Render 배포 교체 또는 수동 재시작)")
    sys.exit(0)


def _atexit_handler() -> None:
    """atexit: 정상/비정상 종료 시 파이프라인 실행 중이면 알람."""
    _notify_shutdown("프로세스 종료 (서버 슬립 또는 예외)")


# 핸들러 등록
signal.signal(signal.SIGTERM, _handle_sigterm)
atexit.register(_atexit_handler)


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
        # PRD 부실 경고에 대한 y/n 응답 처리
        if chat_id in _prd_pending:
            answer = text.strip().lower()
            if answer in ("y", "yes"):
                pending = _prd_pending.pop(chat_id)
                _execute_prd(chat_id, pending["item"], pending["title"])
            elif answer in ("n", "no", ""):
                _prd_pending.pop(chat_id)
                _reply(chat_id, "🚫 PRD 생성을 취소했습니다.")
            else:
                _reply(chat_id, "❓ y 또는 n 으로 답해주세요. 그래도 PRD로 만드시겠습니까? (y/N)")
        return

    # "@botname" suffix 제거 (그룹 채팅 대응)
    command_part = text.split()[0].split("@")[0]
    args = text[len(command_part):].strip()

    # 콜드 스타트 감지: /run 수신 시 서버가 막 깨어난 경우 안내
    if command_part == "/run" and not _cold_start_warned:
        _reply(chat_id, "⏳ 잠시만 기다려주세요~ 서버를 깨우는 중입니다.")
        _cold_start_warned = True

    if command_part == "/run":
        _handle_run(chat_id)
    elif command_part == "/rerun":
        _handle_rerun(chat_id)
    elif command_part == "/list":
        _handle_list(chat_id, args)
    elif command_part == "/overview":
        _handle_overview(chat_id, args)
    elif command_part == "/prd":
        _handle_prd(chat_id, args)
    elif command_part == "/status":
        _handle_status(chat_id)
    elif command_part == "/schedule":
        _handle_schedule(chat_id)
    elif command_part == "/set":
        _handle_set(chat_id, args)
    elif command_part == "/cancel":
        _handle_help(chat_id)  # /cancel 제거 — /help로 안내
    elif command_part == "/help":
        _handle_help(chat_id)
    else:
        _reply(
            chat_id,
            "❓ 알 수 없는 명령어입니다.\n/help 로 사용법을 확인하세요.",
        )
