# HANDOFF.md

## Goal

아이디어 노트 자동 위키화 시스템 구축.
Google Drive에 업로드한 노트를 AI(Claude/Gemini)가 자동으로 위키화하고,
GitHub Pages로 호스팅된 HTML 뷰어로 PC/모바일에서 열람하는 파이프라인.

PRD: `PRD_idea-wiki-system.md`
GitHub: https://github.com/sbb2002/my-idea-wiki
롤백 브랜치: `backup/pre-gas-proxy`

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

### 다음 세션 작업 (순서대로)

| 이슈 | 내용 | Type | Blocked by |
|------|------|------|------------|
| [#17](https://github.com/sbb2002/my-idea-wiki/issues/17) | gh-pages 브랜치 생성 및 GitHub Pages 활성화 | HITL | 없음 |
| [#18](https://github.com/sbb2002/my-idea-wiki/issues/18) | index.html 모바일 반응형 UI 개선 | AFK | 없음 |
| [#19](https://github.com/sbb2002/my-idea-wiki/issues/19) | /run 완료 후 gh-pages에 wiki.json + index.html 자동 push | AFK | #17 |
| [#20](https://github.com/sbb2002/my-idea-wiki/issues/20) | 문서 업데이트 | AFK | #17, #19 |

---

## 구조 변경 사항 (이번 세션 결정)

### 변경 전
```
runner.py → wiki.json → Drive wikis/
         → index.html → Drive wikis/
         → 이미지 크롭 → Drive wikis/pic/
사용자: Drive에서 index.html 다운로드 → 더블클릭
```

### 변경 후 (#19 완료 시)
```
runner.py → wiki.json → gh-pages 브랜치
         → index.html (wiki.json 인라인 포함) → gh-pages 브랜치
         → 이미지 크롭 → Drive wikis/pic/ (유지)
사용자: https://sbb2002.github.io/my-idea-wiki/ 북마크로 접근
```

### 핵심 결정 사항
- Drive wikis/ 폴더: pic/ 서브폴더만을 위해 유지 (wiki.json/index.html 더 이상 저장 안 함)
- `DRIVE_WIKI_FOLDER_ID`: 환경변수명 유지 (pic/ 상위 폴더로서 역할)
- `DRIVE_PIC_FOLDER_ID`: 유지
- `GITHUB_TOKEN`: 신규 환경변수 추가 필요
- gh-pages 브랜치: orphan 브랜치로 생성 (소스코드 없이 index.html, wiki.json만)
- Render Auto-Deploy: main 브랜치만 감지하므로 gh-pages push로 재배포 없음

---

## What Worked

- **인라인 embed 방식** — WIKI_DATA 변수 주입, file:// 완전 동작
- **daemon=False 스레드** — 파이프라인 스레드 보존
- **asyncio self-ping keepalive** — Render 슬립 방지
- **lh3.googleusercontent.com/d/** — 이미지는 CORS 없이 로드 가능

---

## What Didn't Work

- **Drive JSON fetch (브라우저)** — 모든 방법 CORS/403으로 차단
  - lh3.googleusercontent.com → 이미지 전용, JSON 404
  - drive.google.com/uc?export=download → CORS 차단
- **Render Web Service 프록시** — 750시간 경합 문제로 기각
- **GitHub Pages + JS 비밀번호** — 개발자도구로 노출, 보안 무의미

---

## Next Steps 상세

### #17 (HITL — 사용자가 직접 수행)

```bash
git checkout --orphan gh-pages
git rm -rf .
echo "# GitHub Pages" > README.md
git add README.md
git commit -m "init gh-pages"
git push origin gh-pages
git checkout main
```

이후 GitHub 레포 → Settings → Pages → Branch: `gh-pages` → Save
확인: https://sbb2002.github.io/my-idea-wiki/

### #18 (AFK — 에이전트가 구현)

viewer/index.html 반응형 개선:
- 모바일(~390px): 사이드바 숨김, 햄버거 메뉴 또는 하단 탭
- TOC 모바일에서 접힘 처리
- 그래프 뷰 터치 인터랙션 (핀치 줌, 드래그)
- 이미지 첨부 영역 레이아웃 보정

### #19 (AFK — 에이전트가 구현)

`src/pipeline/runner.py` 수정:
- Drive wiki.json/index.html 업로드 로직 제거
- GitHub API로 gh-pages 브랜치에 push
  ```
  PUT /repos/sbb2002/my-idea-wiki/contents/index.html
  PUT /repos/sbb2002/my-idea-wiki/contents/wiki.json
  (branch: gh-pages)
  ```
- 환경변수: `GITHUB_TOKEN` 추가
- 텔레그램 알람에 Pages URL 포함

### #20 (AFK — 에이전트가 구현)

README, instruction.md, dev_manual.md 업데이트

---

## Environment Variables

| 변수 | 비고 |
|------|------|
| `GOOGLE_OAUTH_CLIENT_ID` | OAuth 클라이언트 ID |
| `GOOGLE_OAUTH_CLIENT_SECRET` | OAuth 클라이언트 보안 비밀 |
| `GOOGLE_REFRESH_TOKEN` | OAuth Refresh Token |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | 서비스 계정 키 (폴백) |
| `DRIVE_NOTES_FOLDER_ID` | 노트 업로드 폴더 ID |
| `DRIVE_WIKI_FOLDER_ID` | wikis/ 폴더 ID (pic/ 상위, 유지) |
| `DRIVE_PIC_FOLDER_ID` | wikis/pic/ 폴더 ID |
| `ANTHROPIC_API_KEY` | Claude API |
| `GEMINI_API_KEY` | Gemini API (폴백) |
| `TELEGRAM_BOT_TOKEN` | 텔레그램 봇 토큰 |
| `TELEGRAM_CHAT_ID` | 알람 수신 chat ID |
| `TELEGRAM_WEBHOOK_URL` | Render Web Service URL + `/webhook` |
| `TELEGRAM_WEBHOOK_SECRET` | (선택) Webhook 보안 토큰 |
| `SCHEDULE_CRON` | 기본값: `0 9 * * 1` |
| `GITHUB_TOKEN` | **다음 세션에서 추가** — gh-pages push용 PAT |
