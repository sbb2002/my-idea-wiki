"""
Render Cron Job 진입점.

Render에서 주기적으로 이 스크립트를 직접 실행한다:
  python -m src.cron_job

파이프라인 실행 → 텔레그램 알람 전송 → 종료.
"""
import sys
from dotenv import load_dotenv

load_dotenv()

from src.pipeline.runner import run_pipeline
from src.telegram.notifier import notify_result


def main() -> int:
    print("[cron] 위키화 파이프라인 시작")

    result = run_pipeline()

    print(f"[cron] 완료: {result}")

    notify_result(result)

    # 실패 시 exit code 1 (Render 로그에서 구분 가능)
    return 0 if result["status"] in ("success", "partial") else 1


if __name__ == "__main__":
    sys.exit(main())
