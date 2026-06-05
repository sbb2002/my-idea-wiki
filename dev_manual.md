# 아이디어 위키 — 개발자 매뉴얼

---

## 1. 시스템 구성 개요

```
[Render Cron Job]          [Render Web Service]
idea-wiki-cron             idea-wiki-web
python -m src.cron_job     uvicorn src.main:app
       │                          │
       └──────────┬───────────────┘
                  ▼
         Google Drive API
         (notes 폴더 읽기 / wiki.json 백업 / pic 폴더 이미지 저장)
                  │
         Claude API (Vision 포함) → Gemini API (폴백)
                  │
         GitHub Contents API
         (gh-pages 브랜치에 wiki.json + index.html push)
                  │
         GitHub Pages  →  사용자 브라우저 (PC/모바일)
                  │
         Telegram Bot API (알람/명령)
```

| 서비스 | 역할 | 슬립 여부 |
|--------|------|-----------| 
| `idea-wiki-cron` | 주기적 위키화 실행 | 실행 시에만 켜짐 (750h 제한 무관) |
| `idea-wiki-web` | 텔레그램 Webhook 수신 | 15분 미사용 시 슬립 |

---

## 2. Render 서버 시작 및 배포

### 최초 배포
```bash
# 레포 루트에 render.yaml이 있으므로 Render 대시보드에서:
# New → Blueprint → GitHub 레포 연결
# render.yaml을 자동으로 읽어 cron + web 서비스를 동시 생성
```

### 재배포 (코드 변경 후)
- GitHub `main` 브랜치에 push하면 Render가 자동으로 재배포
- 수동 재배포: Render 대시보드 → 해당 서비스 → **Manual Deploy** → **Deploy latest commit**

### Webhook 등록
서버 URL이 바뀌면 텔레그램 Webhook을 재등록해야 합니다:
```bash
python scripts/register_webhook.py
```

또는 브라우저에서 직접:
```
https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=<RENDER_WEB_URL>/webhook
```

---

## 3. 환경변수 설정

Render 대시보드 → 서비스 선택 → **Environment** 탭에서 설정합니다.

### idea-wiki-cron 환경변수

| 변수명 | 설명 | 예시 |
|--------|------|------|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | 서비스 계정 JSON **전체 내용** (파일 경로 아님) | `{"type":"service_account",...}` |
| `GOOGLE_OAUTH_CLIENT_ID` | OAuth 클라이언트 ID | `123456-abc.apps.googleusercontent.com` |
| `GOOGLE_OAUTH_CLIENT_SECRET` | OAuth 클라이언트 보안 비밀 | `GOCSPX-...` |
| `GOOGLE_REFRESH_TOKEN` | OAuth Refresh Token (`get_oauth_token.py`로 발급) | `1//0e...` |
| `DRIVE_NOTES_FOLDER_ID` | 노트 업로드 폴더 ID | `1ABC123...` |
| `DRIVE_WIKI_FOLDER_ID` | wikis/ 폴더 ID (wiki.json 백업 및 pic/ 상위) | `1DEF456...` |
| `DRIVE_PIC_FOLDER_ID` | PDF 그림 크롭 저장 폴더 ID (`wikis/pic/`) | `1GHI789...` |
| `ANTHROPIC_API_KEY` | Claude API 키 | `sk-ant-...` |
| `GEMINI_API_KEY` | Gemini API 키 (폴백) | `AIza...` |
| `TELEGRAM_BOT_TOKEN` | 텔레그램 봇 토큰 | `123456:ABC...` |
| `TELEGRAM_CHAT_ID` | 알람 수신 Chat ID | `987654321` |
| `GITHUB_TOKEN` | gh-pages push용 PAT (`repo` 스코프 필요) | `github_pat_...` |
| `GITHUB_REPO` | 레포 경로 (선택, 기본값 `sbb2002/my-idea-wiki`) | `owner/repo` |
| `GITHUB_BRANCH` | 배포 대상 브랜치 (선택, 기본값 `gh-pages`) | `gh-pages` |

### idea-wiki-web 환경변수

위 cron 변수 전부 + 아래 추가:

| 변수명 | 설명 | 예시 |
|--------|------|------|
| `TELEGRAM_WEBHOOK_URL` | Render Web Service URL + `/webhook` | `https://idea-wiki-web.onrender.com/webhook` |
| `TELEGRAM_WEBHOOK_SECRET` | Webhook 보안 토큰 (선택) | 임의 문자열 |
| `SCHEDULE_CRON` | 기본 실행 주기 cron 표현식 | `0 9 * * 1` (매주 월 오전 9시 UTC) |
| `APP_ENV` | 실행 환경 | `production` |

> **Drive 인증 우선순위:** OAuth (`GOOGLE_REFRESH_TOKEN`) → 서비스 계정 (`GOOGLE_SERVICE_ACCOUNT_JSON`) 순으로 폴백됩니다.
> OAuth가 있으면 서비스 계정 없이도 동작하며, 파일 신규 생성도 가능합니다.

> **`GOOGLE_SERVICE_ACCOUNT_JSON` 주의:** Render는 파일 시스템이 휘발성이므로
> JSON 파일 경로가 아닌 **JSON 내용 전체를 문자열로** 환경변수에 붙여넣어야 합니다.

> **`DRIVE_PIC_FOLDER_ID`:** `scripts/setup_drive.py` 실행 결과에서 확인하거나,
> 드라이브에서 `wikis/pic/` 폴더 URL의 ID 부분을 복사합니다.

---

## 4. 사용 중인 외부 API 목록

서비스 종료 시 비활성화해야 할 API키/서비스 목록입니다.

### AI API
| API | 용도 | 키 변수명 | 비활성화 위치 |
|-----|------|-----------|---------------|
| **Anthropic Claude API** | 노트 위키화 + Vision OCR (기본) | `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) → API Keys |
| **Google Gemini API** | 노트 위키화 (Claude 실패 시 폴백) | `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) → API Keys |

### Google Cloud
| API | 용도 | 비활성화 위치 |
|-----|------|---------------|
| **Google Drive API v3** | 노트 읽기, wiki.json 백업, 이미지 저장 | [GCP Console](https://console.cloud.google.com) → APIs & Services → Enabled APIs → Drive API → Disable |
| **서비스 계정** | Drive API 인증 (폴백) | GCP Console → IAM & Admin → Service Accounts → 해당 계정 → Disable |
| **OAuth 2.0 클라이언트** | Drive API 인증 (우선) | GCP Console → APIs & Services → Credentials → OAuth 클라이언트 → Delete |

### GitHub
| 항목 | 용도 | 비활성화 위치 |
|------|------|---------------|
| **Personal Access Token** | gh-pages 브랜치에 wiki.json + index.html push | [github.com/settings/tokens](https://github.com/settings/tokens) → 해당 토큰 → Delete |

### Telegram
| 항목 | 용도 | 비활성화 위치 |
|------|------|---------------|
| **Bot Token** | 명령 수신 및 알람 전송 | @BotFather → `/mybots` → 해당 봇 → **Revoke token** |

---

## 5. 로컬 개발 환경

```bash
git clone https://github.com/sbb2002/my-idea-wiki.git
cd my-idea-wiki

python -m venv miw-env
source miw-env/bin/activate  # Windows: miw-env\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# .env 파일 편집 — API 키, 폴더 ID 입력

# credentials/ 폴더에 서비스 계정 JSON 파일 배치 (OAuth 사용 시 불필요)
mkdir -p credentials
# credentials/service_account.json 복사

# OAuth 토큰 최초 발급 (최초 1회)
python scripts/get_oauth_token.py

# Drive 폴더 구조 생성 (최초 1회)
python scripts/setup_drive.py

# 파이프라인 직접 실행
python run_local.py

# Web 서버 로컬 실행
uvicorn src.main:app --reload
```

### 로컬 실행 전 Google Drive 사전 준비
`wikis` 폴더에 빈 `wiki.json`이 없으면 저장 시 에러가 발생합니다.
(서비스 계정 인증 사용 시 파일 신규 생성 불가 — 업데이트만 가능. OAuth 사용 시 자동 생성 가능.)
`index.html`은 더 이상 Drive에 저장하지 않으므로 사전 업로드 불필요합니다.

```
에러:
  - wiki.json Drive 저장 실패: <HttpError 403...>
  도움말: wikis 폴더에 비어있는 wiki.json을 업로드하십시오...
```

위 에러가 나오면 `instruction.md` 1-2절의 파일 업로드 절차를 따르세요.

---

## 6. 프로젝트 구조

```
my-idea-wiki/
├── render.yaml              # Render 배포 설정 (cron + web)
├── requirements.txt
├── run_local.py             # 로컬 파이프라인 실행 스크립트
├── src/
│   ├── main.py              # FastAPI 앱 진입점 (Web Service)
│   ├── cron_job.py          # Cron 진입점 (Cron Job)
│   ├── drive/
│   │   └── client.py        # Google Drive API v3 래퍼
│   │                        # (OAuth 우선 / 서비스 계정 폴백, upload_image_bytes 포함)
│   ├── github/
│   │   └── gh_pages.py      # GitHub Contents API 래퍼
│   │                        # (push_file, push_wiki_to_gh_pages, gh_pages_url)
│   ├── pipeline/
│   │   ├── runner.py        # 위키화 파이프라인 오케스트레이터
│   │   │                    # (gh-pages push 포함, Drive는 wiki.json 백업만)
│   │   ├── claude_processor.py   # Claude API 호출
│   │   │                         # (wikify / OCR / PDF Vision + 그림 크롭 업로드)
│   │   ├── gemini_processor.py   # Gemini API 호출 (폴백)
│   │   └── wiki_store.py    # wiki.json 로드/저장/업서트
│   │                        # (make_attachment: pic_drive_id, description 지원)
│   ├── telegram/
│   │   ├── bot.py           # Webhook 핸들러 및 명령어 처리 (/help 포함)
│   │   └── notifier.py      # 알람 전송 (GitHub Pages URL 우선, Drive 폴더 폴백)
│   ├── viewer/
│   │   └── builder.py       # _template.html + style.css + app.js 조합 → 단일 HTML 빌드
│   └── utils/
│       └── time_utils.py    # 주차 계산 등 공통 유틸
├── viewer/                  # 뷰어 소스 (개발용 분리 구조)
│   ├── _template.html       # HTML 뼈대 ({{CSS}}, {{JS}} 플레이스홀더 포함)
│   ├── style.css            # 전체 CSS
│   └── app.js               # 전체 JS
│   ✱ viewer/index.html 은 빌드 산출물(.gitignore) — 직접 편집 금지
│     gh-pages push 시 builder.py가 조합+WIKI_DATA 주입 후 배포
└── scripts/
    ├── get_oauth_token.py   # OAuth Refresh Token 최초 발급
    ├── setup_drive.py       # Drive 폴더 구조 생성 (wikis/, wikis/pic/)
    └── register_webhook.py  # 텔레그램 Webhook URL 등록
```

---

## 7. 주요 로직 흐름

### 위키화 파이프라인 (`runner.py`)
```
1. wiki.json 로드 (Drive 백업에서)
2. last_processed_at 이후 수정된 노트만 읽기 (incremental)
3. PDF 노트 전처리
   ├─ PyMuPDF로 페이지별 PNG 변환 (1.5x 스케일)
   ├─ Claude Vision으로 텍스트 + 그림 영역(bbox) 분석
   ├─ 그림 영역 크롭 → JPEG 75% 압축 → Drive pic/ 업로드
   └─ 텍스트 노트로 변환해 파이프라인 합류
4. 기존 아이템 목록을 컨텍스트로 Claude에게 전달
   ├─ 아이템 ≤ 20개: title + tags + summary 전체 전달
   └─ 아이템 > 20개: title + tags 요약본만 전달 (토큰 절약)
5. Claude → 실패 시 Gemini 폴백
6. 반환된 아이템을 기존 wiki에 upsert (제목 일치 → 버전 누적 / 불일치 → 신규)
7. PDF에서 크롭된 그림을 해당 아이템 attachments에 pic_drive_id와 함께 저장
8. 이미지 파일 OCR 처리 (Claude Vision)
9. 코멘트 파일 처리
10. gh-pages 브랜치에 wiki.json + index.html(WIKI_DATA 인라인 주입) push

> **뷰어 수정 시**: `viewer/index.html` 직접 편집 금지.
> `viewer/style.css`, `viewer/app.js`, `viewer/_template.html` 을 수정하세요.
> `index.html`은 builder.py가 빌드 시 자동 생성합니다.
    (GITHUB_TOKEN 설정 시. 실패해도 치명적이지 않음)
11. Drive에 wiki.json 백업 저장
12. 텔레그램으로 결과 알람 전송 (GitHub Pages URL 포함)
```

### 텔레그램 Webhook 흐름
```
사용자 /run 전송
→ Telegram → Render Web Service (슬립 중이면 콜드 스타트 30초~1분)
→ bot.py: 즉시 "시작합니다" 응답 (timeout 방지)
→ 백그라운드 스레드에서 run_pipeline() 실행
→ 완료 후 결과 알람 + GitHub Pages URL 전송
```

### Drive 인증 흐름 (`client.py`)
```
get_drive_service() 호출 시:
1. GOOGLE_REFRESH_TOKEN 있으면 → OAuth 2.0으로 인증 (파일 신규 생성 가능)
2. 없으면 → GOOGLE_SERVICE_ACCOUNT_JSON으로 서비스 계정 인증 (파일 업데이트만 가능)
```

### 뷰어 배포 흐름 (`builder.py` + `gh_pages.py`)
```
build_viewer_html(wiki_json_str) 호출 시:
1. viewer/_template.html + style.css + app.js 읽어 단일 HTML 조합
2. wiki.json 데이터를 WIKI_DATA 전역변수로 <head> 직전에 주입
3. WIKI_DATA 인라인 포함 단일 HTML 반환

push_wiki_to_gh_pages(wiki_json_str) 호출 시:
1. build_viewer_html()로 index.html 생성
2. GitHub Contents API PUT /repos/{repo}/contents/wiki.json (branch: gh-pages)
3. GitHub Contents API PUT /repos/{repo}/contents/index.html (branch: gh-pages)
4. GitHub Pages가 자동으로 https://{owner}.github.io/{repo}/ 에 서빙
```

### Drive 인증 흐름 (`client.py`)
```
get_drive_service() 호출 시:
1. GOOGLE_REFRESH_TOKEN 있으면 → OAuth 2.0으로 인증 (파일 신규 생성 가능)
2. 없으면 → GOOGLE_SERVICE_ACCOUNT_JSON으로 서비스 계정 인증 (파일 업데이트만 가능)
```
