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

### 다음 세션 작업 (순서대로)

| 순서 | 이슈 | 내용 | Type | Blocked by |
|------|------|------|------|------------|
| 1 | [#21](https://github.com/sbb2002/my-idea-wiki/issues/21) | 동일 week 버전 히스토리 중복 적재 방지 | AFK | 없음 |
| 2 | [#22](https://github.com/sbb2002/my-idea-wiki/issues/22) | Drive 삭제 노트의 위키 아이템 잔류 감지 및 알람 | AFK | 없음 |
| 3 | [#24](https://github.com/sbb2002/my-idea-wiki/issues/24) | 문서 상단 메타 정보와 인포박스 중복 제거 | AFK | 없음 |
| 4 | [#23](https://github.com/sbb2002/my-idea-wiki/issues/23) | 모바일 인포박스 접기/펼치기 | AFK | #24 |
| 5 | [#27](https://github.com/sbb2002/my-idea-wiki/issues/27) | 섹션 헤딩 클릭으로 접기/펼치기 (PC+모바일) | AFK | 없음 |
| 6 | [#25](https://github.com/sbb2002/my-idea-wiki/issues/25) | 마크다운 표 렌더링 + HTML 파일 분리 계획 | AFK | 없음 |
| 7 | [#26](https://github.com/sbb2002/my-idea-wiki/issues/26) | 첨부 이미지를 상세 내용 본문에 인라인 표시 | AFK | #25 |

---

## 구조 현황

```
runner.py → wiki.json → gh-pages 브랜치 (wiki.json + index.html)
         → wiki.json 백업 → Drive wikis/
         → 이미지 크롭 → Drive wikis/pic/ (유지)
사용자: https://sbb2002.github.io/my-idea-wiki/ 북마크로 접근
```

---

## What Worked

- **인라인 embed 방식** — WIKI_DATA 변수 주입, file:// 완전 동작
- **gh-pages orphan 브랜치** — main과 분리, Render Auto-Deploy 미영향
- **lh3.googleusercontent.com/d/** — Drive 이미지 CORS 없이 로드 가능
- **daemon=False 스레드** — 파이프라인 스레드 보존
- **asyncio self-ping keepalive** — Render 슬립 방지

---

## What Didn't Work

- **Drive JSON fetch (브라우저)** — 모든 방법 CORS/403으로 차단
- **Render Web Service 프록시** — 750시간 경합 문제로 기각
- **GitHub Pages + JS 비밀번호** — 개발자도구로 노출, 보안 무의미

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
