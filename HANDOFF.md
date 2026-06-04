# HANDOFF.md

## Goal

아이디어 노트 자동 위키화 시스템 구축.
Google Drive에 업로드한 노트를 AI(Claude/Gemini)가 자동으로 위키화하고,
GitHub Pages로 호스팅된 HTML 뷰어로 PC/모바일에서 열람하는 파이프라인.

PRD: `PRD_idea-wiki-system.md`
GitHub: https://github.com/sbb2002/my-idea-wiki
뷰어: https://sbb2002.github.io/my-idea-wiki/

---

## Current Progress

### 완료된 이슈

| 이슈 | 내용 | 상태 |
|------|------|------|
| #1~#6 | 스캐폴딩, 위키화, Cron, Webhook, 뷰어, 그래프 | ✅ |
| #10 | 이미지 OCR | ✅ |
| #11 | 코멘트 기능 | ✅ |
| #13 | PDF 그림 크롭 → Drive pic/ 업로드 | ✅ |
| #14 | wiki.json에 크롭 이미지 참조 저장 | ✅ |
| #15 | 뷰어에서 Drive 크롭 이미지 인라인 표시 | ✅ |
| #17 | gh-pages 브랜치 생성 및 GitHub Pages 활성화 | ✅ (HITL 완료) |
| #18 | index.html 모바일 반응형 UI 개선 | ✅ |
| #19 | /run 완료 후 gh-pages에 wiki.json + index.html 자동 push | ✅ |
| #20 | 문서 업데이트 (README, instruction.md, dev_manual.md) | ✅ |
| #21 | 동일 week 버전 히스토리 중복 적재 방지 | ✅ |
| #22 | Drive 삭제 노트의 위키 아이템 잔류 감지 및 알람 | ✅ |
| #23 | 모바일 인포박스 접기/펼치기 | ✅ |
| #24 | 문서 상단 메타 정보와 인포박스 중복 제거 | ✅ |
| #25 | 마크다운 표 렌더링 | ✅ |
| #26 | 첨부 이미지를 상세 내용 본문에 인라인 표시 | ✅ (파이프 버그 추가 수정됨) |
| #27 | 섹션 헤딩 클릭으로 접기/펼치기 (PC+모바일) | ✅ |

### 다음 세션 작업 — 버그 수정 (우선순위 순)

> ⚠️ #13~#20은 GitHub에서 닫히지 않은 상태이나 실제로는 완료됨. 무시할 것.

#### 🔴 즉시 수정 (심각 / 레이아웃 붕괴)

| 순서 | 이슈 | 내용 | Blocked by |
|------|------|------|-----------|
| 1 | [#28](https://github.com/sbb2002/my-idea-wiki/issues/28) | 섹션 접기 — clearfix 내부 wiki-h2 래핑 오작동 (인포박스 DOM 분리) | 없음 |
| 2 | [#32](https://github.com/sbb2002/my-idea-wiki/issues/32) | 모바일 wiki-h2 섹션 접기 클릭 미동작 (touch-action 누락) | #28 선행 권장 |
| 3 | [#29](https://github.com/sbb2002/my-idea-wiki/issues/29) | TOC 클릭 시 접힌 섹션 자동 펼침 없음 | #28 선행 권장 |

#### 🟡 데이터/파이프라인 버그

| 순서 | 이슈 | 내용 | Blocked by |
|------|------|------|-----------|
| 4 | [#35](https://github.com/sbb2002/my-idea-wiki/issues/35) | 기존 중복 week 버전 데이터 정리 (일회성 마이그레이션) | 없음 |
| 5 | [#31](https://github.com/sbb2002/my-idea-wiki/issues/31) | 고아 감지 오탐 — list_all_note_ids에 이미지 mimeType 누락 | 없음 |
| 6 | [#36](https://github.com/sbb2002/my-idea-wiki/issues/36) | 고아 아이템 자동 제거 (알람만 발송 → wiki.json에서 직접 삭제) | #31 선행 필수 |
| 7 | [#33](https://github.com/sbb2002/my-idea-wiki/issues/33) | 상세 내용 이미지 인라인 미렌더링 — drawing filename 불일치 | 없음 |
| 8 | [#34](https://github.com/sbb2002/my-idea-wiki/issues/34) | rerun 시 PDF drawing 이미지 중복 첨부 | #33 선행 권장 |

#### 🟢 UX 개선 (모바일)

| 순서 | 이슈 | 내용 | Blocked by |
|------|------|------|-----------|
| 9 | [#37](https://github.com/sbb2002/my-idea-wiki/issues/37) | 하단 탭바 재설계 — 위키 탭 제거 + 목록/그래프 ON-OFF 토글 | 없음 |
| 10 | [#38](https://github.com/sbb2002/my-idea-wiki/issues/38) | 다크모드 미감지 + 테마 버튼 라벨 반전 수정 | 없음 |

#### ⚪ 동작 명확화 (낮은 우선순위)

| 순서 | 이슈 | 내용 |
|------|------|------|
| 11 | [#30](https://github.com/sbb2002/my-idea-wiki/issues/30) | rerun 시 week content 덮어쓰기 동작 명확화 |

---

## 구조 현황

```
runner.py → wiki.json → gh-pages 브랜치 (wiki.json + index.html)
         → wiki.json 백업 → Drive wikis/
         → 이미지 크롭 → Drive wikis/pic/ (유지)
사용자: https://sbb2002.github.io/my-idea-wiki/ 북마크로 접근
```

### 주요 파일

| 파일 | 역할 |
|------|------|
| `src/pipeline/runner.py` | 파이프라인 오케스트레이터 |
| `src/pipeline/wiki_store.py` | wiki.json 데이터 구조 및 upsert 로직 |
| `src/pipeline/claude_processor.py` | Claude API 위키화 / OCR / PDF 처리 |
| `src/drive/client.py` | Google Drive API 래퍼 |
| `src/telegram/bot.py` | 텔레그램 봇 명령 핸들러 |
| `src/telegram/notifier.py` | 알람 전송 유틸리티 |
| `viewer/index.html` | HTML 뷰어 (단일 파일, JS/CSS 인라인) |

---

## What Worked

- **인라인 embed 방식** — WIKI_DATA 변수 주입, file:// 완전 동작
- **gh-pages orphan 브랜치** — main과 분리, Render Auto-Deploy 미영향
- **lh3.googleusercontent.com/d/** — Drive 이미지 CORS 없이 로드 가능
- **daemon=False 스레드** — 파이프라인 스레드 보존
- **asyncio self-ping keepalive** — Render 슬립 방지
- **renderMarkdown 이스케이프 순서** — 이스케이프 → MD변환 → 테이블파싱 → 이미지치환 → p래핑 순서가 정답

---

## What Didn't Work

- **Drive JSON fetch (브라우저)** — 모든 방법 CORS/403으로 차단
- **Render Web Service 프록시** — 750시간 경합 문제로 기각
- **GitHub Pages + JS 비밀번호** — 개발자도구로 노출, 보안 무의미
- **parseTables 후 HTML 이스케이프** — `<table>` 태그가 `&lt;`로 깨짐. 반드시 이스케이프를 먼저 하고 HTML 삽입해야 함
- **clearfix div 안에 wiki-h2 혼재** — 섹션 래핑 JS가 clearfix를 넘어 DOM을 분리시켜 레이아웃 붕괴

---

## Environment Variables

| 변수 | 비고 |
|------|------|
| `GOOGLE_OAUTH_CLIENT_ID` | OAuth 클라이언트 ID |
| `GOOGLE_OAUTH_CLIENT_SECRET` | OAuth 클라이언트 보안 비밀 |
| `GOOGLE_REFRESH_TOKEN` | OAuth Refresh Token |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | 서비스 계정 키 (폴백) |
| `DRIVE_NOTES_FOLDER_ID` | 노트 업로드 폴더 ID |
| `DRIVE_WIKI_FOLDER_ID` | wikis/ 폴더 ID (pic/ 상위, wiki.json 백업) |
| `DRIVE_PIC_FOLDER_ID` | wikis/pic/ 폴더 ID |
| `ANTHROPIC_API_KEY` | Claude API |
| `GEMINI_API_KEY` | Gemini API (폴백) |
| `TELEGRAM_BOT_TOKEN` | 텔레그램 봇 토큰 |
| `TELEGRAM_CHAT_ID` | 알람 수신 chat ID |
| `TELEGRAM_WEBHOOK_URL` | Render Web Service URL + `/webhook` |
| `TELEGRAM_WEBHOOK_SECRET` | (선택) Webhook 보안 토큰 |
| `SCHEDULE_CRON` | 기본값: `0 9 * * 1` |
| `GITHUB_TOKEN` | gh-pages push용 PAT (repo 스코프) ✅ Render 등록 완료 |
| `GITHUB_REPO` | 기본값: `sbb2002/my-idea-wiki` |
| `GITHUB_BRANCH` | 기본값: `gh-pages` |
