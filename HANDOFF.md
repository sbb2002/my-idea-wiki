# HANDOFF.md

## Goal

아이디어 노트 자동 위키화 시스템 구축.
Google Drive에 업로드한 노트를 AI(Claude/Gemini)가 자동으로 위키화하고,
로컬 HTML 뷰어 + 그래프 뷰로 열람하는 파이프라인.

PRD: `PRD_idea-wiki-system.md` (프로젝트 파일 참고)
GitHub: https://github.com/sbb2002/my-idea-wiki

---

## Current Progress

### 완료된 이슈

| 이슈 | 내용 | 상태 |
|------|------|------|
| #1 | 프로젝트 스캐폴딩 + Google Drive 노트 읽기 | ✅ closed |
| #2 | Claude/Gemini API 위키화 + JSON → Drive 저장 | ✅ closed |
| #3 | Render Cron Job 배포 + 텔레그램 알람 | ✅ closed |
| #4 | Render Web Service + Telegram Webhook + 봇 명령어 5개 | ✅ 구현 완료 (브랜치: `issue-4-telegram-webhook`) |

### 미완료 이슈

| 이슈 | 내용 | Blocked by |
|------|------|------------|
| #5 | 로컬 HTML 뷰어 — 위키 문서 렌더링 | #2 (완료됨 → 바로 시작 가능) |
| #6 | 그래프 뷰 (D3/Vis.js 인라인) | #5 |

### 현재 프로젝트 구조

```
my-idea-wiki/
├── render.yaml                  # Cron Job + Web Service 설정
├── requirements.txt
├── .env.example                 # TELEGRAM_WEBHOOK_SECRET 추가됨
├── scripts/
│   └── register_webhook.py     # Webhook URL 등록 유틸리티 (배포 후 1회 실행)
├── src/
│   ├── main.py                  # FastAPI: GET /health, POST /webhook
│   ├── cron_job.py              # Render Cron Job 진입점
│   ├── drive/
│   │   └── client.py
│   ├── pipeline/
│   │   ├── runner.py
│   │   ├── wiki_store.py
│   │   ├── claude_processor.py
│   │   └── gemini_processor.py
│   └── telegram/
│       ├── notifier.py          # 텔레그램 알람 (3종)
│       └── bot.py               # ✨ NEW: Webhook 핸들러 + 5개 명령어
└── tests/
    ├── test_drive_client.py
    ├── test_notifier.py
    ├── test_pipeline.py
    └── test_bot.py              # ✨ NEW: 19개 단위 테스트
```

---

## What Worked

- **google-genai 최신 SDK** 사용 (`google.generativeai` deprecated → `google.genai`로 교체)
- **mock 기반 단위 테스트**: Drive API / AI API 호출 없이 파이프라인 로직 검증
- **incremental 처리**: `last_processed_at` 필드로 신규/변경 노트만 처리
- **수동 태그 우선**: `#태그` 파싱 후 업데이트 시에도 기존 태그 보존
- **백그라운드 스레드**: /run 수신 시 파이프라인을 threading.Thread로 실행해 응답 블로킹 없음
- **콜드 스타트 감지**: `_cold_start_warned` 플래그로 프로세스 첫 /run 시에만 안내 메시지 발송

---

## What Didn't Work

- `google-generativeai==0.8.1` — deprecated, FutureWarning 발생. `google-genai`로 교체함
- GitHub fine-grained PAT는 PR 생성 API 권한 없음 (`Resource not accessible by personal access token`). 브랜치 push만 가능.

---

## Next Steps

### 다음 세션에서 바로 시작할 것: #5

**#5 — 로컬 HTML 뷰어 (위키 문서 렌더링)**

구현할 파일:
- `viewer/index.html` — 단일 파일(모든 JS/CSS 인라인), wiki.json 읽어 렌더링
- `src/pipeline/runner.py` 수정 — 위키화 후 HTML 뷰어도 Drive에 업로드

기능:
- 아이템 목록 사이드바 + 상세 뷰
- 위키 문서 구조: 개요 → AI 작성 내용 → 버전 히스토리 (타임라인)
- 로컬 파일에서 JSON fetch (`fetch()` API, `file://` 프로토콜 주의)
  - `file://` 프로토콜에서는 fetch()가 차단될 수 있음 → JSON을 JS 변수로 인라인하거나 별도 로컬 서버 필요

그 다음: **#6 — 그래프 뷰** (#5 완료 후)

---

### #4 배포 절차 (참고용)

1. Render 대시보드에서 `idea-wiki-web` Web Service 생성 및 배포
2. 배포 완료 후 URL 확인 (예: `https://idea-wiki-web.onrender.com`)
3. `.env`에 `TELEGRAM_WEBHOOK_URL=https://idea-wiki-web.onrender.com/webhook` 설정
4. `python -m scripts.register_webhook` 실행 (1회)

---

## Environment Variables (필요한 것들)

`.env.example` 참고. 실제 값은 Render 대시보드 환경변수에 등록.

| 변수 | 비고 |
|------|------|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | 서비스 계정 키 경로 |
| `DRIVE_NOTES_FOLDER_ID` | 노트 업로드 폴더 ID |
| `DRIVE_WIKI_FOLDER_ID` | wiki.json 저장 폴더 ID |
| `ANTHROPIC_API_KEY` | Claude API |
| `GEMINI_API_KEY` | Gemini API (폴백) |
| `TELEGRAM_BOT_TOKEN` | 텔레그램 봇 토큰 |
| `TELEGRAM_CHAT_ID` | 알람 수신 chat ID |
| `TELEGRAM_WEBHOOK_URL` | Render Web Service URL + `/webhook` |
| `TELEGRAM_WEBHOOK_SECRET` | (선택) Webhook 보안 토큰 |
| `SCHEDULE_CRON` | (선택) 기본값: `0 9 * * 1` |
