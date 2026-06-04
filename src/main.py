"""
FastAPI 앱 — Render Web Service 진입점.

엔드포인트:
  GET  /health    — 헬스 체크 (Render keep-alive용으로도 사용)
  POST /webhook   — 텔레그램 Webhook 수신

슬립 방지 전략:
  파이프라인 실행 중에는 asyncio로 self-ping을 30초마다 보내
  Render가 idle로 판단해 프로세스를 죽이지 않도록 한다.
"""
import asyncio
import hmac
import logging
import os

from fastapi import FastAPI, HTTPException, Request
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("idea-wiki")

from src.telegram.bot import handle_update, _mark_started

app = FastAPI(title="Idea Wiki System")
_mark_started()

# 파이프라인 실행 중 self-ping 태스크 핸들
_keepalive_task: asyncio.Task | None = None


async def _self_ping_loop():
    """파이프라인 실행 중 30초마다 /health를 self-ping해 슬립 방지."""
    import aiohttp
    port = os.getenv("PORT", "10000")
    url = f"http://localhost:{port}/health"
    log.info("[keep-alive] self-ping 시작")
    try:
        async with aiohttp.ClientSession() as session:
            while True:
                await asyncio.sleep(30)
                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
                        log.info(f"[keep-alive] ping {r.status}")
                except Exception as e:
                    log.warning(f"[keep-alive] ping 실패: {e}")
    except asyncio.CancelledError:
        log.info("[keep-alive] self-ping 종료")


def start_keepalive():
    global _keepalive_task
    if _keepalive_task is None or _keepalive_task.done():
        try:
            loop = asyncio.get_event_loop()
            _keepalive_task = loop.create_task(_self_ping_loop())
        except RuntimeError:
            pass


def stop_keepalive():
    global _keepalive_task
    if _keepalive_task and not _keepalive_task.done():
        _keepalive_task.cancel()
        _keepalive_task = None


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/webhook")
async def telegram_webhook(request: Request):
    """
    텔레그램 Update를 수신해 asyncio 태스크로 처리한다.
    파이프라인 실행 중에는 self-ping으로 슬립을 방지한다.
    """
    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET")
    if secret:
        token_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not hmac.compare_digest(token_header, secret):
            raise HTTPException(status_code=403, detail="Invalid secret token")

    try:
        update = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    log.info(f"[webhook] update 수신: {list(update.keys())}")

    async def _run():
        start_keepalive()
        try:
            await asyncio.to_thread(handle_update, update)
        except Exception as e:
            log.error(f"[webhook] handle_update 오류: {e}", exc_info=True)
        finally:
            stop_keepalive()
            log.info("[webhook] 처리 완료")

    asyncio.create_task(_run())
    return {"ok": True}
