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

### 미완료 이슈

| 이슈 | 내용 | Blocked by |
|------|------|------------|
| #4 | Render Web Service + Telegram Webhook + 봇 명령어 5개 | #3 (완료됨 → 바로 시작 가능) |
| #5 | 로컬 HTML 뷰어 — 위키 문서 렌더링 | #2 (완료됨 → 바로 시작 가능) |
| #6 | 그래프 뷰 (D3/Vis.js 인라인) | #5 |

### 현재 프로젝트 구조

```
my-idea-wiki/
├── render.yaml                  # Cron Job 설정 (Web Service 섹션 주석으로 예약)
├── requirements.txt
├── .env.example
├── src/
│   ├── main.py                  # FastAPI 앱 (현재 /health 엔드포인트만)
│   ├── cron_job.py              # Render Cron Job 진입점
│   ├── drive/
│   │   └── client.py            # Drive API v3: 노트 읽기, JSON 저장
│   ├── pipeline/
│   │   ├── runner.py            # 파이프라인 오케스트레이터
│   │   ├── wiki_store.py        # wiki.json 스키마 및 상태 관리
│   │   ├── claude_processor.py  # Claude API 위키화
│   │   └── gemini_processor.py  # Gemini API 폴백
│   └── telegram/
│       └── notifier.py          # 텔레그램 알람 (3종)
└── tests/                       # 26개 단위 테스트 (전부 통과)
```

---

## What Worked

- **google-genai 최신 SDK** 사용 (`google.generativeai` deprecated → `google.genai`로 교체)
- **mock 기반 단위 테스트**: Drive API / AI API 호출 없이 파이프라인 로직 검증
- **incremental 처리**: `last_processed_at` 필드로 신규/변경 노트만 처리
- **수동 태그 우선**: `#태그` 파싱 후 업데이트 시에도 기존 태그 보존

---

## What Didn't Work

- `google-generativeai==0.8.1` — deprecated, FutureWarning 발생. `google-genai`로 교체함
- GitHub fine-grained PAT는 `X-OAuth-Scopes` 헤더를 노출하지 않음 — 권한 확인은 실제 API 호출로 테스트해야 함

---

## Next Steps

### 다음 세션에서 바로 시작할 것: #4

**#4 — Render Web Service + Telegram Webhook + 봇 명령어**

구현할 파일:
- `src/telegram/bot.py` — Webhook 핸들러 + 5개 명령어 (`/run`, `/status`, `/schedule`, `/set`, `/cancel`)
- `src/main.py` — `POST /webhook` 엔드포인트 추가
- `render.yaml` — Web Service 섹션 주석 해제 및 작성

주의사항:
- Web Service는 15분 비활성 시 슬립, 콜드 스타트(30초~1분) 허용
- `/run` 수신 시 콜드 스타트 안내 메시지(`잠시만 기다려주세요~`) 즉시 응답 후 파이프라인 실행
- `/status`용으로 마지막 실행 결과를 어딘가에 저장해야 함 → Drive의 `status.json` 또는 메모리(재시작 시 소멸 허용)
- Webhook URL은 Render 배포 후 등록 (배포 전에는 ngrok으로 로컬 테스트 가능)

그 다음: **#5 — 로컬 HTML 뷰어** (#4와 병렬 가능, #2만 완료되면 됨)

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
| `TELEGRAM_WEBHOOK_URL` | Render Web Service URL (#4 배포 후) |
