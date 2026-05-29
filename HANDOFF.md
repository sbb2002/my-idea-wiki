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
| #4 | Render Web Service + Telegram Webhook + 봇 명령어 5개 | ✅ closed |
| #5 | 로컬 HTML 뷰어 — 위키 문서 렌더링 | ✅ PR #8 오픈 (머지 대기) |

### 미완료 이슈

| 이슈 | 내용 | Blocked by |
|------|------|------------|
| #6 | 그래프 뷰 (D3/Vis.js 인라인) | #5 (머지 후 시작 가능) |

### 현재 프로젝트 구조

```
my-idea-wiki/
├── render.yaml
├── requirements.txt
├── .env.example
├── scripts/
│   └── register_webhook.py
├── viewer/
│   └── index.html               # ✨ NEW: 단일 파일 HTML 뷰어
├── src/
│   ├── main.py
│   ├── cron_job.py
│   ├── drive/
│   │   └── client.py            # upload_json에 mime_type 파라미터 추가됨
│   ├── pipeline/
│   │   ├── runner.py            # step 6: HTML 뷰어 자동 생성 추가됨
│   │   ├── wiki_store.py
│   │   ├── claude_processor.py
│   │   └── gemini_processor.py
│   ├── viewer/
│   │   ├── __init__.py
│   │   └── builder.py           # ✨ NEW: wiki.json 인라인 embed 유틸
│   └── telegram/
│       ├── notifier.py
│       └── bot.py
└── tests/                       # 53개 단위 테스트 (전부 통과)
    ├── test_drive_client.py
    ├── test_notifier.py
    ├── test_pipeline.py
    ├── test_bot.py
    └── test_viewer.py           # ✨ NEW: 8개 테스트
```

---

## What Worked

- **google-genai 최신 SDK** 사용
- **mock 기반 단위 테스트**
- **incremental 처리**: `last_processed_at` 필드
- **수동 태그 우선**
- **백그라운드 스레드**: /run 파이프라인 비블로킹 실행
- **인라인 embed 방식**: file:// 프로토콜 fetch 차단 우회 — builder.py로 WIKI_DATA 변수 주입
- **단계적 폴백**: fetch → 인라인 WIKI_DATA → 샘플 데이터

---

## What Didn't Work

- `google-generativeai==0.8.1` → `google-genai`로 교체
- GitHub fine-grained PAT는 PR 생성 권한 별도 설정 필요 (현재 해결됨)

---

## Next Steps

### 다음 세션에서 바로 시작할 것: #6

**#6 — 그래프 뷰 (D3/Vis.js 인라인)**

#5가 머지되면 `viewer/index.html`에 그래프 뷰 탭을 추가한다.

구현 방향:
- `viewer/index.html`에 "그래프" 탭 추가 (위키 문서 뷰와 토글)
- D3.js CDN 사용 불가 (오프라인) → D3 force simulation 코드를 인라인으로 포함
  - 또는 순수 JS로 간단한 force-directed graph 직접 구현 (의존성 없음)
- 노드: 각 아이템 (제목 표시)
- 엣지: `related` 배열 기반 자동 연결
- 인터랙션: 노드 클릭 → 해당 아이템 위키 문서로 이동
- 태그 기반 노드 색상 구분
- 줌/패닝 지원

주의사항:
- D3를 인라인으로 넣으면 HTML 파일이 매우 커짐 → 경량 force simulation 직접 구현 검토
- PRD: "AI 의미 유사도 + 태그 공유로 자동 연결"은 #6 범위, 명시적 `related` 필드 연결이 핵심

---

## Environment Variables

`.env.example` 참고.

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
