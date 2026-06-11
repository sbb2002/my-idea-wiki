# HANDOFF.md

## Goal

아이디어 노트 자동 위키화 시스템 구축.
Google Drive에 업로드한 노트를 AI(Claude/Gemini)가 자동으로 위키화하고,
GitHub Pages로 호스팅된 HTML 뷰어로 PC/모바일에서 열람하는 파이프라인.

PRD: `PRD_idea-wiki-system.md`
GitHub: https://github.com/sbb2002/my-idea-wiki
뷰어: https://sbb2002.github.io/my-idea-wiki/
백업 브랜치: `backup/pre-prd-auth` (PRD 인증 작업 직전 스냅샷)

---

## Current Progress

### 완료된 이슈 (전체)

| 이슈/작업 | 내용 | 상태 |
|-----------|------|------|
| #1~#6 | 스캐폴딩, 위키화, Cron, Webhook, 뷰어, 그래프 | ✅ |
| #10~#20 | OCR, 코멘트, PDF 크롭, gh-pages, 모바일 반응형 등 | ✅ |
| #21~#38 | 버전 중복 방지, 고아 감지/삭제, 섹션 접기, 모바일 UX 등 | ✅ |
| keepalive 버그 | stop_keepalive()가 파이프라인 완료 전 호출되던 타이밍 버그 수정 | ✅ |
| 중단 알람 | SIGTERM/atexit 시 파이프라인 실행 중이면 텔레그램 알람 | ✅ |
| 모바일 접기 버그 | click 단일 리스너로 교체 | ✅ |
| 그래프 범례 | 우측 하단 드래그 가능 범례 | ✅ |
| 뷰어 리팩토링 | index.html → _template.html + css/×6 + js/×6 분리 | ✅ |
| **#46** | 보안 — loadWiki() → GitHub Contents API + Token 인증 | ✅ |
| **#47** | 파이프라인 PRD 자동 생성 제거 (runner.py, claude_processor.py) | ✅ |
| **#48** | PRD 만들기 버튼 — 브라우저에서 Claude API 직접 호출 | ✅ |
| **#49** | 생성된 PRD → gh-pages/prd/{itemId}.md GitHub API push + 다운로드 | ✅ |
| **#50** | 아이템 선택 시 gh-pages/prd/{itemId}.md 자동 로드 및 렌더링 | ✅ |

### 이번 세션 주요 변경사항

#### #46 보안
- `viewer/js/data.js` `loadWiki()` → GitHub Contents API + Token 방식
- Token 없으면 에러를 throw, `init.js`에서 catch → 샘플 데이터 + 에러 배너 표시
- `init.js` try/catch로 loadWiki() 예외 처리 추가

#### #47 파이프라인 PRD 제거
- `runner.py`: 6-B 섹션 전체 제거, `generate_prd`/`archive_prd` import 제거, `prd_generated`/`prd_failed` 카운터 제거
- `claude_processor.py`: `generate_prd()`, `_build_prd_prompt()`, `PRD_SYSTEM_PROMPT` 제거
- `wiki.json`의 `item.prd` / `item.prd_history` 필드는 유지 (뷰어에서 계속 사용)

#### #48/#49/#50 PRD 생성/저장/열람
- `wiki.js` PRD 섹션 전면 재설계:
  - `generatePrd()`: 브라우저에서 Claude API 직접 호출 → 스피너 → 완료 시 즉시 렌더링
  - `_savePrdToGithub()`: gh-pages/prd/{itemId}.md PUT (SHA 조회 → 신규/업데이트)
  - `_loadPrdFromGithub()`: 아이템 선택 시 백그라운드 로드 시도
  - `_renderPrdSection()`: PRD 섹션 DOM 독립 렌더링 (id="prd-section-container")
  - 기존 PRD 덮어쓰기 시 confirm 모달 + prd_history 보관
- `_template.html`: "📄 PRD 만들기" 버튼 추가 (데스크탑 TOC 박스, 모바일 상단)
- `graph.css`: `#prd-generate-btn` 스타일 추가 (accent 배경 filled 버튼)
- TOC에서 PRD 섹션 항상 표시 (기존엔 item.prd 있을 때만)

---

## 파일 구조 (현재)

```
src/
├── pipeline/
│   ├── runner.py           # 파이프라인 오케스트레이터 (PRD 섹션 제거됨)
│   ├── wiki_store.py       # wiki.json 데이터 구조 (archive_prd 유지, 뷰어에서 직접 관리)
│   ├── claude_processor.py # 위키화/OCR/PDF (generate_prd 제거됨)
│   └── gemini_processor.py # Gemini 폴백
├── drive/client.py
├── telegram/
│   ├── bot.py
│   └── notifier.py
├── github/gh_pages.py
└── viewer/builder.py       # css/*.css + js/*.js + _template.html → index.html 조합

viewer/
├── _template.html          ← 📄 PRD 만들기 버튼 추가
├── css/
│   ├── variables.css
│   ├── layout.css
│   ├── wiki.css
│   ├── graph.css           ← #prd-generate-btn CSS 추가
│   ├── layout_shell.css
│   └── responsive.css
└── js/
    ├── data.js     ← loadWiki() GitHub API + Token 인증
    ├── render.js
    ├── ui.js
    ├── wiki.js     ← PRD 생성/저장/열람 전면 재설계
    ├── graph.js
    └── init.js     ← loadWiki() try/catch 예외 처리
```

---

## What Worked

- **인라인 embed 방식** — WIKI_DATA 변수 주입, file:// 완전 동작
- **gh-pages orphan 브랜치** — main과 분리, Render Auto-Deploy 미영향
- **lh3.googleusercontent.com/d/** — Drive 이미지 CORS 없이 로드 가능
- **keepalive를 스레드 안으로** — `_run_in_thread` 진입 시 start, finally에서 stop
- **renderMarkdown 이스케이프 순서** — 이스케이프 → MD변환 → 테이블파싱 → 이미지치환 → p래핑
- **A안 빌드 조합** — builder.py로 단일 index.html 생성, 배포 구조 변경 없음
- **GitHub Token을 비밀번호로** — 기존 localStorage Token 구조 재활용, 추가 인프라 불필요
- **prd-section-container 패턴** — PRD를 인라인 HTML 대신 독립 컨테이너로 관리, 비동기 로드/재렌더링 용이
- **loadWiki throw/catch 패턴** — data.js에서 showError 의존 제거, init.js에서 일괄 처리

## What Didn't Work

- **Drive JSON fetch (브라우저)** — 모든 방법 CORS/403으로 차단 (lh3는 이미지 전용)
- **Render Web Service 프록시** — 750시간 경합 문제로 기각
- **GitHub Pages + JS 비밀번호** — 개발자도구로 노출, 보안 무의미
- **Cloudflare Pages + Access** — 가능하나 설정 복잡, GitHub Token 방식으로 대체
- **parseTables 후 HTML 이스케이프** — `<table>` 태그가 `&lt;`로 깨짐
- **`_lastTouch` 350ms 가드** — passive touchend로 e.preventDefault() 무시 → click 단일 리스너로 대체
- **main.py에서 keepalive 관리** — thread.start() 후 즉시 반환으로 타이밍 버그

---

## Environment Variables

| 변수 | 비고 |
|------|------|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | 서비스 계정 키 |
| `DRIVE_NOTES_FOLDER_ID` | 노트 업로드 폴더 ID |
| `DRIVE_WIKI_FOLDER_ID` | wikis/ 폴더 ID |
| `DRIVE_PIC_FOLDER_ID` | wikis/pic/ 폴더 ID |
| `ANTHROPIC_API_KEY` | Claude API |
| `GEMINI_API_KEY` | Gemini API (폴백) |
| `TELEGRAM_BOT_TOKEN` | 텔레그램 봇 토큰 |
| `TELEGRAM_CHAT_ID` | 알람 수신 chat ID |
| `TELEGRAM_WEBHOOK_URL` | Render Web Service URL + `/webhook` |
| `TELEGRAM_WEBHOOK_SECRET` | (선택) Webhook 보안 토큰 |
| `SCHEDULE_CRON` | 기본값: `0 9 * * 1` |
| `GITHUB_TOKEN` | gh-pages push용 PAT ✅ Render 등록 완료 |
| `GITHUB_REPO` | 기본값: `sbb2002/my-idea-wiki` |
| `GITHUB_BRANCH` | 기본값: `gh-pages` |

## 의사결정 로그

[2026-06-11] 이슈 #58 — 패스스루를 check_error y/N 확인 경로로 대체 / 검증 실패 시 무단 PRD 생성 방지 / "경고 없이 그냥 진행" 방식 포기
[2026-06-11] 이슈 #58 — 근본 원인을 _VIABILITY_PROMPT의 비이스케이프 중괄호(format KeyError '"q1"')로 확정하고 함께 수정 / 이슈 진단(_parse 예외)만으로는 관측된 로그 재현 불가 / 프롬프트 수정 없이 예외 분리만 하는 방안 포기

---

## 이번 세션 (2026-06-11)

### 완료
| 이슈 | 내용 | 커밋 |
|------|------|------|
| #58 | bug: viability check 파싱 실패 시 check_error 반환 | `8175a3a` |

### 남은 오픈 이슈
| 이슈 | 분류 | 내용 |
|------|------|------|
| #59 | bug | 텔레그램 /prd 생성 후 뷰어 다운로드 버튼 비활성화 |
| #56 | improve | /prd 명령어 PRD 퀄리티 개선 |
| #39 | data | 기존 wiki.json 버전 날짜(week) 6월 1일 고정 문제 |

### 다음 세션 시작 방법
```
HANDOFF.md 를 읽고 작업을 이어주세요.
/combo-run --list  또는  /combo-run 59
```
