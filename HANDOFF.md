# HANDOFF.md

## Goal

아이디어 노트 자동 위키화 시스템 구축.
Google Drive에 업로드한 노트를 AI(Claude/Gemini)가 자동으로 위키화하고,
로컬 HTML 뷰어 + 그래프 뷰로 열람하는 파이프라인.

PRD: `PRD_idea-wiki-system.md` (프로젝트 파일 참고)
GitHub: https://github.com/sbb2002/my-idea-wiki

---

## Current Progress

### 완료된 이슈 (1차 개발 전체 완료)

| 이슈 | 내용 | 상태 |
|------|------|------|
| #1 | 프로젝트 스캐폴딩 + Google Drive 노트 읽기 | ✅ closed |
| #2 | Claude/Gemini API 위키화 + JSON → Drive 저장 | ✅ closed |
| #3 | Render Cron Job 배포 + 텔레그램 알람 | ✅ closed |
| #4 | Render Web Service + Telegram Webhook + 봇 명령어 5개 | ✅ closed |
| #5 | 로컬 HTML 뷰어 — 위키 문서 렌더링 | ✅ closed |
| #6 | 그래프 뷰 (force-directed, 순수 JS) | ✅ closed (PR #9 머지) |

### 미완료 이슈 (2차 개발)

| 이슈 | 내용 | Blocked by |
|------|------|------------|
| #10 | 이미지 OCR 처리 (Claude Vision) | 없음 |
| #11 | 코멘트 기능 | 없음 (#10 완료 후 첨부 연계 가능) |

### 현재 프로젝트 구조

```
my-idea-wiki/
├── render.yaml
├── requirements.txt
├── .env.example
├── scripts/
│   └── register_webhook.py
├── viewer/
│   └── index.html               # 단일 파일 HTML 뷰어 (위키 + 그래프 탭)
├── src/
│   ├── main.py
│   ├── cron_job.py
│   ├── drive/
│   │   └── client.py
│   ├── pipeline/
│   │   ├── runner.py
│   │   ├── wiki_store.py
│   │   ├── claude_processor.py
│   │   └── gemini_processor.py
│   ├── viewer/
│   │   ├── __init__.py
│   │   └── builder.py           # wiki.json 인라인 embed 유틸
│   └── telegram/
│       ├── notifier.py
│       └── bot.py
└── tests/                       # 56개 단위 테스트 (전부 통과)
    ├── test_drive_client.py
    ├── test_notifier.py
    ├── test_pipeline.py
    ├── test_bot.py
    └── test_viewer.py           # 11개 테스트 (그래프 뷰 포함)
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
- **순수 JS force-directed graph**: D3 없이 직접 구현, 외부 의존성 없음, 오프라인 완전 동작
- **그래프 엣지 3종**: related(회색), explicit_related(파란 굵은 선), 태그 공유(반투명 얇은 선)

---

## What Didn't Work

- `google-generativeai==0.8.1` → `google-genai`로 교체
- GitHub fine-grained PAT는 PR 생성 권한 별도 설정 필요 (현재 해결됨)

---

## Next Steps

### 다음 세션에서 시작할 것: #10 (이미지 OCR)

**#10 — 이미지 OCR 처리**

구현 방향:
- `src/drive/client.py`: Drive 폴더에서 이미지 파일(jpg, png, heic 등) 감지
- `src/pipeline/claude_processor.py`: 이미지를 base64로 인코딩 후 Claude Vision API에 전달, OCR + 요약
- `src/pipeline/wiki_store.py`: 아이템에 `attachments` 필드 추가 (`{ "type": "image", "drive_id": "...", "ocr_text": "...", "thumbnail_url": "..." }`)
- `viewer/index.html`: 위키 문서에 OCR 텍스트 + 원본 이미지 나란히 표시하는 섹션 추가

주의사항:
- Claude Vision 실패 시 해당 파일만 스킵, 부분 실패 알람 기존 로직 재활용
- HEIC 포맷은 변환 필요할 수 있음 (pillow 등)

**#11 — 코멘트 기능** (#10 완료 후 또는 병행 가능)

구현 방향:
- 파일명 규칙: `comment_<item_id>_<날짜>.txt`
- Drive 폴더에서 코멘트 파일 감지 → 파싱 → wiki.json `comments` 배열에 추가
- `viewer/index.html`: 위키 문서 하단에 코멘트 섹션 추가

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
