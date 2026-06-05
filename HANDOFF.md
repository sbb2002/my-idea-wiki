# HANDOFF.md

## Goal

아이디어 노트 자동 위키화 시스템 구축.
Google Drive에 업로드한 노트를 AI(Claude/Gemini)가 자동으로 위키화하고,
GitHub Pages로 호스팅된 HTML 뷰어로 PC/모바일에서 열람하는 파이프라인.

PRD: `PRD_idea-wiki-system.md`
GitHub: https://github.com/sbb2002/my-idea-wiki
뷰어: https://sbb2002.github.io/my-idea-wiki/
백업 브랜치: `backup/pre-refactor-20260605` (뷰어 리팩토링 직전 스냅샷)

---

## Current Progress

### 완료된 이슈 (전체)

| 이슈/작업 | 내용 | 상태 |
|-----------|------|------|
| #1~#6 | 스캐폴딩, 위키화, Cron, Webhook, 뷰어, 그래프 | ✅ |
| #10~#20 | OCR, 코멘트, PDF 크롭, gh-pages, 모바일 반응형 등 | ✅ |
| #21~#38 | 버전 중복 방지, 고아 감지/삭제, 섹션 접기, 모바일 UX 등 | ✅ |
| #30 | /rerun vs /run 동작 명확화 (overwrite_count + 알람 표시) | ✅ |
| keepalive 버그 | stop_keepalive()가 파이프라인 완료 전 호출되던 타이밍 버그 수정 | ✅ |
| 중단 알람 | SIGTERM/atexit 시 파이프라인 실행 중이면 텔레그램 알람 | ✅ |
| 모바일 접기 버그 v1 | touchend+click 이중 발화 → _lastTouch 350ms 가드로 수정 | ✅ |
| 모바일 접기 버그 v2 | `#main` overflow 스크롤 컨테이너에서 passive 처리로 e.preventDefault() 무시 → touchend+click 이중 구조 전체 제거, click 단일 리스너로 교체 | ✅ |
| 섹션 기본 상태 | 이미지 첨부 기본 접힘 / 인포박스 기본 펼침 | ✅ |
| 그래프 범례 | 우측 하단 드래그 가능 범례 (태그 색상 + 엣지 종류) | ✅ |
| PRD 기능 | 파이프라인에서 LLM 친화적 PRD 생성 + 뷰어 다운로드 버튼 | ✅ |
| PRD 조건부 생성 | run=있으면 스킵, rerun=아카이브 후 재생성 | ✅ |
| 뷰어 리팩토링 | index.html(2470줄) → _template.html + css/×6 + js/×6 분리 | ✅ |

### 이번 세션 주요 작업

#### 1. keepalive 타이밍 버그 수정 (`src/main.py`, `src/telegram/bot.py`)
- **문제**: `main.py _run()`이 `handle_update` 반환(=`thread.start()` 직후) 즉시 `stop_keepalive()` 호출 → 파이프라인이 돌기도 전에 keep-alive 꺼짐
- **수정**: `main.py`에서 keepalive 호출 제거, `bot.py` 파이프라인 스레드(`_run_in_thread`) 진입 시 `_keepalive_start()`, `finally`에서 `_keepalive_stop()` 호출
- **추가**: SIGTERM/atexit 핸들러 → 파이프라인 실행 중 서버 종료 시 텔레그램 알람

#### 2. 모바일 UX 버그 수정 + 그래프 범례 (`viewer/`)
- **접기 버그**: `touchend` 후 합성 `click`이 350ms 내 발화 → `_lastTouch` 타임스탬프로 무시
- **섹션 기본 상태**: 이미지 첨부(`sec-attachments`) 기본 접힘 / 인포박스 기본 펼침
- **그래프 범례**: 우측 하단 고정, 접기/펼치기 버튼, 헤더 드래그 이동 (마우스+터치), `renderGraph._legendInited` 플래그로 리스너 중복 방지

#### 3. PRD 기능 (`src/pipeline/claude_processor.py`, `runner.py`, `wiki_store.py`, `viewer/`)
- **파이프라인**: `generate_prd()` — summary + body + OCR + 연관 아이템 title/summary → LLM 친화적 Markdown PRD
- **조건부 생성**: run 시 PRD 있으면 스킵(토큰 절약), rerun 시 기존 PRD → `prd_history` 보관 후 재생성
- **뷰어**: PRD 섹션(sec-prd) + 이전 버전 히스토리, TOC 연동, 다운로드 버튼(`PRD_제목.md`)
- **wiki.json**: `prd`, `prd_history` 필드 추가

#### 4. 뷰어 소스 분리 리팩토링 (`viewer/`)
- **A안(빌드 조합)**: `_template.html` + `css/` + `js/` → `builder.py`가 조합해 단일 `index.html` 생성
- `index.html`, `style.css`, `app.js` → `.gitignore` (빌드 산출물)
- 빌드 결과 기존 index.html과 byte-for-byte 동일 확인

#### 5. runner.py logging NameError 수정
- `#36` 고아 삭제 코드에서 `logger` 미정의 → `import logging` + `logger = getLogger(...)` 추가

---

## 파일 구조 (현재)

```
src/
├── pipeline/
│   ├── runner.py           # 파이프라인 오케스트레이터
│   ├── wiki_store.py       # wiki.json 데이터 구조 (prd, prd_history 필드 포함)
│   ├── claude_processor.py # 위키화/OCR/PDF/PRD 생성
│   └── gemini_processor.py # Gemini 폴백
├── drive/client.py         # Google Drive API 래퍼
├── telegram/
│   ├── bot.py              # 봇 명령 핸들러 (keepalive 스레드 연동)
│   └── notifier.py         # 알람 전송 (PRD/고아/중단 알람 포함)
├── github/gh_pages.py      # gh-pages push
└── viewer/builder.py       # css/*.css + js/*.js + _template.html → index.html 조합

viewer/
├── _template.html          # HTML 뼈대 (151줄)
├── css/
│   ├── variables.css       # CSS 변수 + 테마 (78줄)
│   ├── layout.css          # 헤더/사이드바/메인 (241줄)
│   ├── wiki.css            # 위키 본문 + PRD 섹션 (589줄)
│   ├── graph.css           # 그래프 + 범례 (216줄)
│   ├── layout_shell.css    # 로딩/탭바/첨부카드 (138줄)
│   └── responsive.css      # @media (132줄)
└── js/
    ├── data.js             # SAMPLE_WIKI, 전역 상태, loadWiki (49줄)
    ├── render.js           # renderMarkdown, fmtDate, fmtWeek (96줄)
    ├── ui.js               # 사이드바, 탭바, TOC 네비 (88줄)
    ├── wiki.js             # selectItem, PRD 섹션, filterItems (338줄)
    ├── graph.js            # switchView, renderGraph, 범례 (399줄)
    └── init.js             # applyTheme, toggleTheme, init() (61줄)
```

---

## 다음 세션 작업

현재 열린 이슈 없음. 아래는 발견된 잠재 개선 사항:

### 🔧 선택적 개선
- `scripts/dedup_versions.py --dry-run` → 실제 wiki.json 중복 버전 확인 후 적용
- PRD 다운로드 버튼 — 모바일에서 위치/디자인 개선 여지 있음
- `wiki.css`(589줄) — PRD 스타일 추가로 증가했으므로 추후 분리 가능
- 뷰어 수정 시 `viewer/index.html` 직접 편집 금지 — 반드시 `css/`, `js/` 수정 후 `builder.py`로 빌드

---

## What Worked

- **인라인 embed 방식** — WIKI_DATA 변수 주입, file:// 완전 동작
- **gh-pages orphan 브랜치** — main과 분리, Render Auto-Deploy 미영향
- **lh3.googleusercontent.com/d/** — Drive 이미지 CORS 없이 로드 가능
- **daemon=False 스레드** — 파이프라인 스레드 보존
- **keepalive를 스레드 안으로** — `_run_in_thread` 진입 시 start, finally에서 stop이 올바른 구조
- **renderMarkdown 이스케이프 순서** — 이스케이프 → MD변환 → 테이블파싱 → 이미지치환 → p래핑
- **renderGraph._legendInited 플래그** — 그래프 탭 전환 시 리스너 중복 방지
- **_lastTouch 타임스탬프** — touchend/click 이중 발화 방지 (350ms 가드)
- **A안 빌드 조합** — 소스 분리 후 builder.py로 합치는 방식이 배포 구조 변경 없이 깔끔

## What Didn't Work

- **Drive JSON fetch (브라우저)** — 모든 방법 CORS/403으로 차단
- **Render Web Service 프록시** — 750시간 경합 문제로 기각
- **parseTables 후 HTML 이스케이프** — `<table>` 태그가 `&lt;`로 깨짐. 반드시 이스케이프 먼저
- **clearfix div 안에 wiki-h2 혼재** — 섹션 래핑 JS DOM 분리 → 레이아웃 붕괴
- **`_lastTouch` 350ms 가드 방식** — `#main`(overflow-y:auto) 내 touchend passive 처리로 e.preventDefault() 무시 → click 즉시 발화 → toggle 2회 실행으로 원상복구. click 단일 리스너로 대체
- **`#sidebar-overlay` pointer-events 누락** — 모바일에서 overlay가 display:block+inset:0으로 화면 전체를 덮고 있었고, 닫혀도 opacity:0일 뿐 pointer-events 미설정으로 모든 터치를 흡수. → 닫힌 상태 pointer-events:none 추가
- **main.py에서 keepalive 관리** — handle_update가 thread.start() 후 즉시 반환하므로 파이프라인 완료 전에 stop됨
- **`_initGraphLegend` 매 renderGraph 호출** — document 이벤트 리스너 누적 → 드래그 오작동

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
