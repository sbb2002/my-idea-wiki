"""
FastAPI 앱 — Render Web Service 진입점.

엔드포인트:
  GET  /health    — 헬스 체크
  POST /webhook   — 텔레그램 Webhook 수신
"""
import hashlib
import hmac
import os

from fastapi import FastAPI, HTTPException, Request
from dotenv import load_dotenv

load_dotenv()

from src.telegram.bot import handle_update, _mark_started

app = FastAPI(title="Idea Wiki System")

# 서버 시작 시 warm 상태로 표시 (다음 /run은 콜드 스타트 안내 없음)
_mark_started()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/webhook")
async def telegram_webhook(request: Request):
    """
    텔레그램이 POST하는 Update JSON을 수신한다.

    선택적 보안: TELEGRAM_WEBHOOK_SECRET 환경변수가 설정된 경우
    X-Telegram-Bot-Api-Secret-Token 헤더를 검증한다.
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

    # 비동기 컨텍스트에서 동기 핸들러 호출 (블로킹 최소화)
    handle_update(update)

    return {"ok": True}
