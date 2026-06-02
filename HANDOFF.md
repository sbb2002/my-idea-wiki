# HANDOFF.md

## Goal

아이디어 노트 자동 위키화 시스템 구축.
Google Drive에 업로드한 노트를 AI(Claude/Gemini)가 자동으로 위키화하고,
로컬 HTML 뷰어 + 그래프 뷰로 열람하는 파이프라인.

PRD: `PRD_idea-wiki-system.md` (프로젝트 파일 참고)
GitHub: https://github.com/sbb2002/my-idea-wiki
작업 브랜치: `feature/oauth-drive` (main에서 분기)

---

## Current Progress

### 완료된 이슈

| 이슈 | 내용 | 상태 |
|------|------|------|
| #1 | 프로젝트 스캐폴딩 + Google Drive 노트 읽기 | ✅ |
| #2 | Claude/Gemini API 위키화 + JSON → Drive 저장 | ✅ |
| #3 | Render Cron Job 배포 + 텔레그램 알람 | ✅ |
| #4 | Render Web Service + Telegram Webhook + 봇 명령어 5개 | ✅ |
| #5 | 로컬 HTML 뷰어 — 위키 문서 렌더링 | ✅ |
| #6 | 그래프 뷰 (force-directed, 순수 JS) | ✅ |
| #10 | 이미지 OCR 처리 (Claude Vision) | ✅ |
| #11 | 코멘트 기능 | ✅ |

### 이번 세션 완료 작업

- **로컬 테스트 환경 구축** (`run_local.py`)
- **Google Drive API 활성화** (GCP 프로젝트 887817282671)
- **Drive 클라이언트 버그 수정**: `supportsAllDrives`, `includeItemsFromAllDrives` 추가
- **구글 독스(Google Docs) mimeType 지원** 추가
- **위키피디아 스타일 뷰어** 전면 개편 (Linux Libertine 폰트, 인포박스, TOC, 타임라인)
- **라이트/다크 테마 전환** 기능 추가 (localStorage 유지)
- **storageQuotaExceeded 에러 메시지** 개선 (해결 방법 안내 포함)
- **기존 아이템 컨텍스트 주입** — 위키화 병합 정확도 향상
  - 아이템 ≤ 20개: title+tags+summary 전체 전달
  - 아이템 > 20개: title+tags 요약본만 전달
- **PDF 노트 지원** (방법 A — 전체 Vision)
  - PyMuPDF로 페이지별 PNG 변환 → Claude Vision 분석
  - 6가지 요소 처리: 타이핑 텍스트, 손글씨, 이미지, 이미지 내 텍스트, 선, 화살표
  - 빈 페이지 자동 스킵
- **OAuth Drive 인증 전환** (`feature/oauth-drive` 브랜치)
  - `scripts/get_oauth_token.py`: Refresh Token 최초 발급
  - `scripts/setup_drive.py`: OAuth로 wikis 폴더 구조 생성
  - `src/drive/client.py`: OAuth 우선, 서비스 계정 폴백
- **문서화**: `instruction.md`, `dev_manual.md`, `README.md` 재작성

### 미완료 이슈 (다음 세션에서 진행)

| 이슈 | 내용 | Blocked by |
|------|------|------------|
| [#13](https://github.com/sbb2002/my-idea-wiki/issues/13) | PDF 그림 영역 크롭 후 Drive pic/ 업로드 | 없음 |
| [#14](https://github.com/sbb2002/my-idea-wiki/issues/14) | wiki.json에 크롭 이미지 참조 저장 | #13 |
| [#15](https://github.com/sbb2002/my-idea-wiki/issues/15) | 뷰어에서 Drive 크롭 이미지 인라인 표시 | #14 |

---

## What Worked

- **google-genai 최신 SDK** 사용
- **mock 기반 단위 테스트**
- **incremental 처리**: `last_processed_at` 필드
- **수동 태그 우선**
- **백그라운드 스레드**: /run 파이프라인 비블로킹 실행
- **인라인 embed 방식**: file:// 프로토콜 fetch 차단 우회 — builder.py로 WIKI_DATA 변수 주입
- **순수 JS force-directed graph**: 외부 의존성 없음, 오프라인 완전 동작
- **supportsAllDrives + includeItemsFromAllDrives**: 서비스 계정의 내 드라이브 공유 폴더 접근
- **OAuth 인증**: 사용자 계정으로 Drive 파일 신규 생성 가능

---

## What Didn't Work

- `google-generativeai==0.8.1` → `google-genai`로 교체
- 서비스 계정의 Drive 파일 신규 생성 → 저장 공간 없음 (403) → OAuth로 해결
- 서비스 계정의 공유 드라이브 생성 → 일반 Gmail 계정 제한 (403) → OAuth로 우회
- 폴더 소유권 이전 → 구글 정책상 개인→서비스계정 불가

---

## Next Steps: #13부터 순서대로

### #13 — PDF 그림 영역 크롭 후 Drive pic/ 업로드

**현재 상태**:
- `src/pipeline/claude_processor.py`의 `process_pdf_with_claude()`가 텍스트 분석은 하지만 그림 좌표 반환 안 함
- `wikis/pic/` 폴더는 `setup_drive.py`로 생성 완료, OAuth로 파일 신규 생성 가능
- `pic/` 폴더는 링크 공유(뷰어 권한) 상태로 사용자가 수동 설정 필요

**구현 방향**:
1. `PDF_SYSTEM_PROMPT`에 그림 영역 좌표 반환 지시 추가
   ```json
   "drawings": [
     {"page": 1, "bbox": [x1, y1, x2, y2], "description": "스케치 설명"}
   ]
   ```
2. 반환된 좌표로 PyMuPDF 크롭 (`page.get_pixmap(clip=rect)`)
3. JPEG 압축 (품질 75) 후 Drive `pic/` 폴더에 업로드
4. `DRIVE_PIC_FOLDER_ID` 환경변수 추가 필요 (setup_drive.py 출력값)
5. 그림 없는 페이지는 스킵

**주의사항**:
- 좌표는 PDF 포인트 단위 → 이미지 변환 시 1.5x 스케일 적용했으므로 좌표도 1.5배 적용
- Drive `pic/` 폴더 ID는 `.env`의 `DRIVE_PIC_FOLDER_ID`로 관리
- OAuth 클라이언트는 `get_drive_service()`가 자동 처리

### #14 — wiki.json에 크롭 이미지 참조 저장

`wiki_store.py`의 attachment 구조:
```python
{
    "drive_id": "...",      # 기존
    "filename": "...",      # 기존
    "ocr_text": "...",      # 기존
    "summary": "...",       # 기존
    "tags": [...],          # 기존
    "pic_drive_id": "...",  # 신규: 크롭 이미지 Drive 파일 ID
    "description": "...",   # 신규: Claude의 그림 설명
}
```

### #15 — 뷰어에서 Drive 크롭 이미지 인라인 표시

Drive 직접 링크:
```
https://drive.google.com/uc?id=<pic_drive_id>
```
`index.html`에서 `pic_drive_id`가 있으면 해석 텍스트(description) 옆에 `<img>` 태그로 표시.
이미지 로드 실패 시 fallback 텍스트 표시.

---

## Environment Variables

`.env.example` 참고.

| 변수 | 비고 |
|------|------|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | 서비스 계정 키 (폴백용) |
| `GOOGLE_OAUTH_CLIENT_ID` | OAuth 클라이언트 ID |
| `GOOGLE_OAUTH_CLIENT_SECRET` | OAuth 클라이언트 보안 비밀 |
| `GOOGLE_REFRESH_TOKEN` | OAuth Refresh Token |
| `DRIVE_NOTES_FOLDER_ID` | 노트 업로드 폴더 ID |
| `DRIVE_WIKI_FOLDER_ID` | wikis 폴더 ID (OAuth로 생성한 것) |
| `DRIVE_PIC_FOLDER_ID` | wikis/pic/ 폴더 ID (**다음 세션에서 추가 필요**) |
| `ANTHROPIC_API_KEY` | Claude API |
| `GEMINI_API_KEY` | Gemini API (폴백) |
| `TELEGRAM_BOT_TOKEN` | 텔레그램 봇 토큰 |
| `TELEGRAM_CHAT_ID` | 알람 수신 chat ID |
| `TELEGRAM_WEBHOOK_URL` | Render Web Service URL + `/webhook` |
| `TELEGRAM_WEBHOOK_SECRET` | (선택) Webhook 보안 토큰 |
| `SCHEDULE_CRON` | (선택) 기본값: `0 9 * * 1` |

## 현재 브랜치 상태

- `main`: OAuth 전환 이전 안정 버전
- `feature/oauth-drive`: OAuth 전환 완료, #13~#15 미구현
  - 다음 세션에서 `feature/oauth-drive` 브랜치에서 작업 계속
  - #13~#15 완료 후 main에 머지
