# HANDOFF.md

## Goal

아이디어 노트 자동 위키화 시스템 구축.
Google Drive에 업로드한 노트를 AI(Claude/Gemini)가 자동으로 위키화하고,
로컬 HTML 뷰어 + 그래프 뷰로 열람하는 파이프라인.

PRD: `PRD_idea-wiki-system.md` (프로젝트 파일 참고)
GitHub: https://github.com/sbb2002/my-idea-wiki
작업 브랜치: `main` (안정 버전)
롤백 브랜치: `backup/pre-gas-proxy` (GAS 작업 전 스냅샷)

---

## Current Progress

### 완료된 이슈

| 이슈 | 내용 | 상태 |
|------|------|------|
| #1 | 프로젝트 스캐폴딩 + Google Drive 노트 읽기 | ✅ |
| #2 | Claude/Gemini API 위키화 + JSON → Drive 저장 | ✅ |
| #3 | Render Cron Job 배포 + 텔레그램 알람 | ✅ |
| #4 | Render Web Service + Telegram Webhook + 봇 명령어 | ✅ |
| #5 | 로컬 HTML 뷰어 — 위키 문서 렌더링 | ✅ |
| #6 | 그래프 뷰 (force-directed, 순수 JS) | ✅ |
| #10 | 이미지 OCR 처리 (Claude Vision) | ✅ |
| #11 | 코멘트 기능 | ✅ |
| #13 | PDF 그림 영역 크롭 후 Drive pic/ 업로드 | ✅ |
| #14 | wiki.json에 크롭 이미지 참조 저장 | ✅ |
| #15 | 뷰어에서 Drive 크롭 이미지 인라인 표시 | ✅ |

### 이번 세션 완료 작업

- **#13~#15 구현** — PDF 그림 크롭 → Drive pic/ 업로드 → 뷰어 인라인 표시
- **버그 수정**
  - `read_notes_from_folder()` PDF를 텍스트로 읽으려다 스킵되는 버그
  - `renderMarkdown()` 삽입 시 `fmtDate` 함수 선언 잘린 버그
  - Render 슬립으로 파이프라인 스레드 죽는 버그 → `daemon=False` + self-ping keepalive
  - `/webhook` 응답 후 BackgroundTasks가 프로세스 종료로 죽는 버그 → `asyncio.to_thread()`
- **텔레그램 명령어 개편**
  - `/rerun` 추가 — `last_processed_at` 초기화 후 전체 재처리
  - `/cancel` 제거 — `/status`가 실행 중 상태도 표시하도록 통합
  - `/help` 추가
- **위키 구조 확장**
  - `body` 필드 추가 — 개요를 마크다운 소제목(##)으로 상세 설명 (필수)
  - `see_also` 필드 추가 — 관련 개념/기술 추천 (선택)
  - 뷰어에 `renderMarkdown()`, 상세 내용/같이 보기 섹션 추가
- **로그 모니터링** — `logging` 모듈로 단계별 로그 추가
- **Drive fetch 시도 후 롤백**
  - `lh3.googleusercontent.com/d/` → JSON 404 (이미지 전용)
  - `drive.google.com/uc?export=download` → CORS 차단
  - 인라인 주입(A안)으로 복구
- **문서 최신화** — README, instruction.md, dev_manual.md

### 다음 세션 작업

| 이슈 | 내용 | 브랜치 |
|------|------|--------|
| [#16](https://github.com/sbb2002/my-idea-wiki/issues/16) | GAS 프록시로 wiki.json fetch — index.html 고정 파일화 | main에서 분기 |

---

## What Worked

- **인라인 embed 방식** — `WIKI_DATA` 변수 주입, `file://` 프로토콜 완전 동작
- **daemon=False 스레드** — 메인 스레드 종료 시 파이프라인 스레드 보존
- **asyncio self-ping keepalive** — 파이프라인 실행 중 Render 슬립 방지
- **lh3.googleusercontent.com/d/** — 이미지(`<img src>`)는 CORS 없이 로드 가능
- **incremental 처리** — `last_processed_at` 필드로 신규/변경 노트만 처리
- **기존 아이템 컨텍스트 주입** — 위키화 병합 정확도 향상
- **OAuth 인증** — 사용자 계정으로 Drive 파일 신규 생성 가능

---

## What Didn't Work

- **Drive JSON fetch (브라우저)** — 모든 방법 CORS/403으로 차단
  - `lh3.googleusercontent.com/d/{id}` → 이미지 전용, JSON 404
  - `drive.google.com/uc?export=download` → CORS 차단 + 403
  - `file://` 프로토콜에서 로컬 fetch → 보안 정책 차단
- **Render Web Service 프록시** — 다른 앱과 750시간 경합 문제로 기각
- **BackgroundTasks** — Render가 응답 후 즉시 슬립하면 같이 종료됨
- **daemon=True 스레드** — 메인 스레드 종료 시 강제 종료

---

## Next Steps: #16 GAS 프록시 구현

### 구현 방향

1. **Google Apps Script 작성**
   ```javascript
   function doGet(e) {
     var fileId = 'WIKI_JSON_FILE_ID';
     var file = DriveApp.getFileById(fileId);
     var content = file.getBlob().getDataAsString();
     return ContentService
       .createTextOutput(content)
       .setMimeType(ContentService.MimeType.JSON);
   }
   ```
   - GAS 웹 앱으로 배포: "나 포함 모든 사용자" 또는 "익명" 접근 허용
   - GAS는 자동으로 CORS 헤더를 붙여줌

2. **`viewer/index.html`의 `loadWiki()` 수정**
   ```javascript
   async function loadWiki() {
     if (typeof WIKI_DATA !== 'undefined') return WIKI_DATA; // 레거시 호환
     if (typeof GAS_URL !== 'undefined' && GAS_URL) {
       const resp = await fetch(GAS_URL);
       if (resp.ok) return await resp.json();
     }
     return null;
   }
   ```

3. **`builder.py` 수정** — `GAS_URL`만 `<head>`에 주입

4. **`runner.py` 수정** — `index.html`은 GAS URL이 바뀔 때만 재생성
   - 환경변수 `GAS_WIKI_URL` 추가

5. **`.env.example`에 `GAS_WIKI_URL` 추가**

6. **문서 업데이트** — GAS 설정 방법 instruction.md, dev_manual.md에 추가

### 주의사항
- GAS 웹 앱 배포 시 "액세스 권한: 모든 사용자(익명 포함)" 설정 필수
- GAS URL은 배포 후 고정됨 (재배포해도 URL 유지)
- `wiki.json`이 공유 설정("링크 있는 모든 사용자 보기")이어야 GAS에서 읽기 가능
- 롤백 필요 시 `backup/pre-gas-proxy` 브랜치 사용

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
| `DRIVE_WIKI_FOLDER_ID` | wikis 폴더 ID |
| `DRIVE_PIC_FOLDER_ID` | wikis/pic/ 폴더 ID |
| `ANTHROPIC_API_KEY` | Claude API |
| `GEMINI_API_KEY` | Gemini API (폴백) |
| `TELEGRAM_BOT_TOKEN` | 텔레그램 봇 토큰 |
| `TELEGRAM_CHAT_ID` | 알람 수신 chat ID |
| `TELEGRAM_WEBHOOK_URL` | Render Web Service URL + `/webhook` |
| `TELEGRAM_WEBHOOK_SECRET` | (선택) Webhook 보안 토큰 |
| `SCHEDULE_CRON` | (선택) 기본값: `0 9 * * 1` |
| `GAS_WIKI_URL` | **다음 세션에서 추가** — GAS 웹 앱 배포 후 발급되는 URL |

## 현재 브랜치 상태

- `main`: 현재 안정 버전 (이번 세션 작업 모두 포함)
- `backup/pre-gas-proxy`: GAS 작업 시작 전 스냅샷 (롤백용)
