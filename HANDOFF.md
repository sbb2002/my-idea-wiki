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
| PRD 기능 | 파이프라인에서 LLM 친화적 PRD 생성 + 뷰어 다운로드 버튼 | ✅ |
| 뷰어 리팩토링 | index.html → _template.html + css/×6 + js/×6 분리 | ✅ |

### 이번 세션 주요 결정사항

#### PRD 기능 재설계
기존: 파이프라인(runner.py)이 위키화 시 모든 아이템에 대해 PRD 자동 생성
→ 문제: 구체화되지 않은 아이디어도 PRD로 만들어 토큰 낭비 심함

변경 후:
- **파이프라인에서 PRD 자동 생성 제거** (#47)
- **index.html에서 사용자가 원하는 아이템만 선택해 PRD 생성** (#48)
- **생성된 PRD를 gh-pages/prd/ 에 저장 + 다운로드** (#49)
- **아이템 선택 시 기존 PRD 자동 로드** (#50)

#### 보안 설계
기존: gh-pages public → wiki.json/PRD 누구나 접근 가능
→ 문제: 개인 아이디어 노출

검토한 방안:
- GitHub Pages Private (유료, 기각)
- JS 비밀번호 (개발자도구 노출, 기각, 이전 세션에서도 기각된 바 있음)
- Cloudflare Pages + Access (무료, OTP 이메일 인증)
- **GitHub Token을 비밀번호로 활용** → 채택 (#46)

채택 이유: 이미 킥오프 저장 시 localStorage GitHub Token 구조가 있어 추가 인프라 없이 구현 가능.
개인 기기에서만 사용하므로 localStorage 토큰 노출 위험 낮음.

---

## 다음 세션 작업 (우선순위 순)

| 이슈 | 제목 | Type | Blocked by |
|------|------|------|------------|
| [#46](https://github.com/sbb2002/my-idea-wiki/issues/46) | 보안 — wiki.json/PRD 로딩을 GitHub Token 인증으로 보호 | AFK | 없음 |
| [#47](https://github.com/sbb2002/my-idea-wiki/issues/47) | 파이프라인에서 PRD 자동 생성 제거 | AFK | 없음 |
| [#48](https://github.com/sbb2002/my-idea-wiki/issues/48) | PRD 생성 — index.html에서 선택한 아이템으로 Claude API 호출 | AFK | #46 |
| [#49](https://github.com/sbb2002/my-idea-wiki/issues/49) | PRD 저장 — 생성된 PRD를 gh-pages/prd/에 GitHub API로 push 및 다운로드 | AFK | #48 |
| [#50](https://github.com/sbb2002/my-idea-wiki/issues/50) | PRD 열람 — 아이템 선택 시 gh-pages/prd/에서 해당 PRD 로드 및 렌더링 | AFK | #49 |

### #46 구현 상세 (보안)

`viewer/js/data.js`의 `loadWiki()` 함수를 수정:
```javascript
// 변경 전
async function loadWiki() {
  if (typeof WIKI_DATA !== 'undefined') return WIKI_DATA;
  try {
    const resp = await fetch('./wiki.json');
    if (resp.ok) return await resp.json();
  } catch(e) {}
  return null;
}

// 변경 후: GitHub Contents API + Token 인증
async function loadWiki() {
  if (typeof WIKI_DATA !== 'undefined') return WIKI_DATA;
  const token = getGhToken(); // 기존 함수 재사용
  if (!token) { /* 🔑 입력 안내 */ return null; }
  const resp = await fetch(
    'https://api.github.com/repos/sbb2002/my-idea-wiki/contents/wiki.json?ref=gh-pages',
    { headers: { Authorization: `Bearer ${token}`, Accept: 'application/vnd.github+json' } }
  );
  if (!resp.ok) { /* 인증 실패 안내 */ return null; }
  const meta = await resp.json();
  return JSON.parse(atob(meta.content.replace(/\n/g, '')));
}
```

PRD 로딩도 동일한 패턴으로 GitHub Contents API 사용.

### #47 구현 상세 (파이프라인 PRD 제거)

`src/pipeline/runner.py`에서 제거할 것:
- 6-B 섹션 전체 (약 383~421번 줄, PRD 생성 루프)
- `generate_prd` import
- `result["prd_generated"]`, `result["prd_failed"]` 카운터

`src/pipeline/claude_processor.py`에서 제거할 것:
- `generate_prd()` 함수
- `PRD_SYSTEM_PROMPT` 상수
- `_build_prd_prompt()` 함수

`src/pipeline/wiki_store.py`에서 제거할 것:
- `archive_prd()` 함수 (뷰어에서 직접 prd_history 관리)

`src/telegram/notifier.py`:
- 완료 알람에서 PRD 관련 통계 항목 제거

**단, `item.prd` / `item.prd_history` wiki.json 필드는 유지** (뷰어에서 계속 사용).

### #48 구현 상세 (PRD 생성 UI)

`viewer/js/wiki.js`에 추가:
- "PRD 만들기" 버튼 — 기존 `prd-download-btn` 근처 배치
- 클릭 시 Anthropic API(`claude-sonnet-4-20250514`) 직접 호출 (브라우저에서)
- 프롬프트 재료: `item.title`, `item.summary`, `item.versions`, `item.kickoff`
- 기존 PRD 있으면 덮어쓰기 확인 모달
- 로딩 중 스피너, 완료 후 PRD 섹션 즉시 렌더링

---

## 파일 구조 (현재)

```
src/
├── pipeline/
│   ├── runner.py           # 파이프라인 오케스트레이터 (6-B PRD 생성 섹션 제거 예정)
│   ├── wiki_store.py       # wiki.json 데이터 구조 (archive_prd 제거 예정)
│   ├── claude_processor.py # 위키화/OCR/PDF (generate_prd 제거 예정)
│   └── gemini_processor.py # Gemini 폴백
├── drive/client.py
├── telegram/
│   ├── bot.py
│   └── notifier.py
├── github/gh_pages.py
└── viewer/builder.py       # css/*.css + js/*.js + _template.html → index.html 조합

viewer/
├── _template.html
├── css/ (variables, layout, wiki, graph, layout_shell, responsive)
└── js/
    ├── data.js     ← #46: loadWiki() GitHub API 방식으로 교체
    ├── render.js
    ├── ui.js
    ├── wiki.js     ← #48: PRD 만들기 버튼 + Claude API 호출 추가
    ├── graph.js
    └── init.js
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
