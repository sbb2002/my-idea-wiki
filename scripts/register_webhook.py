"""
텔레그램 봇 Webhook URL 등록 스크립트.

Render Web Service 배포 후 한 번만 실행하면 된다:
  python -m scripts.register_webhook

환경변수:
  TELEGRAM_BOT_TOKEN     — 봇 토큰
  TELEGRAM_WEBHOOK_URL   — Render Web Service URL (예: https://idea-wiki-web.onrender.com/webhook)
  TELEGRAM_WEBHOOK_SECRET — (선택) 시크릿 토큰
"""
import os
import sys
import httpx
from dotenv import load_dotenv

load_dotenv()


def register_webhook() -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    webhook_url = os.getenv("TELEGRAM_WEBHOOK_URL")

    if not token:
        print("[ERROR] TELEGRAM_BOT_TOKEN 환경변수가 설정되지 않았습니다.")
        return False

    if not webhook_url:
        print("[ERROR] TELEGRAM_WEBHOOK_URL 환경변수가 설정되지 않았습니다.")
        print("예: TELEGRAM_WEBHOOK_URL=https://idea-wiki-web.onrender.com/webhook")
        return False

    payload: dict = {"url": webhook_url}

    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET")
    if secret:
        payload["secret_token"] = secret

    api_url = f"https://api.telegram.org/bot{token}/setWebhook"
    print(f"[INFO] Webhook 등록 중: {webhook_url}")

    try:
        resp = httpx.post(api_url, json=payload, timeout=15)
        data = resp.json()
    except Exception as e:
        print(f"[ERROR] 요청 실패: {e}")
        return False

    if data.get("ok"):
        print(f"[OK] Webhook 등록 성공: {data.get('description', '')}")
        return True
    else:
        print(f"[ERROR] Webhook 등록 실패: {data}")
        return False


def get_webhook_info() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("[ERROR] TELEGRAM_BOT_TOKEN이 없습니다.")
        return

    api_url = f"https://api.telegram.org/bot{token}/getWebhookInfo"
    try:
        resp = httpx.get(api_url, timeout=10)
        data = resp.json()
        info = data.get("result", {})
        print(f"[INFO] 현재 Webhook 정보:")
        print(f"  URL: {info.get('url', '(없음)')}")
        print(f"  pending_update_count: {info.get('pending_update_count', 0)}")
        print(f"  last_error: {info.get('last_error_message', '없음')}")
    except Exception as e:
        print(f"[ERROR] 조회 실패: {e}")


if __name__ == "__main__":
    if "--info" in sys.argv:
        get_webhook_info()
    else:
        ok = register_webhook()
        sys.exit(0 if ok else 1)
