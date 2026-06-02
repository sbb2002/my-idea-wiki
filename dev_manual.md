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
         (notes 폴더 읽기 / wikis 폴더 쓰기)
                  │
         Claude API → Gemini API (폴백)
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
# TELEGRAM_WEBHOOK_URL 환경변수가 설정된 상태에서
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
| `DRIVE_NOTES_FOLDER_ID` | 노트 업로드 폴더 ID | `1ABC123...` |
| `DRIVE_WIKI_FOLDER_ID` | 위키 결과물 저장 폴더 ID | `1DEF456...` |
| `ANTHROPIC_API_KEY` | Claude API 키 | `sk-ant-...` |
| `GEMINI_API_KEY` | Gemini API 키 (폴백) | `AIza...` |
| `TELEGRAM_BOT_TOKEN` | 텔레그램 봇 토큰 | `123456:ABC...` |
| `TELEGRAM_CHAT_ID` | 알람 수신 Chat ID | `987654321` |

### idea-wiki-web 환경변수

위 cron 변수 전부 + 아래 추가:

| 변수명 | 설명 | 예시 |
|--------|------|------|
| `TELEGRAM_WEBHOOK_URL` | Render Web Service URL + `/webhook` | `https://idea-wiki-web.onrender.com/webhook` |
| `TELEGRAM_WEBHOOK_SECRET` | Webhook 보안 토큰 (선택) | 임의 문자열 |
| `SCHEDULE_CRON` | 기본 실행 주기 cron 표현식 | `0 9 * * 1` (매주 월 오전 9시 UTC) |
| `APP_ENV` | 실행 환경 | `production` |

> **`GOOGLE_SERVICE_ACCOUNT_JSON` 주의:** Render는 파일 시스템이 휘발성이므로
> JSON 파일 경로가 아닌 **JSON 내용 전체를 문자열로** 환경변수에 붙여넣어야 합니다.

---

## 4. 사용 중인 외부 API 목록

서비스 종료 시 비활성화해야 할 API키/서비스 목록입니다.

### AI API
| API | 용도 | 키 변수명 | 비활성화 위치 |
|-----|------|-----------|---------------|
| **Anthropic Claude API** | 노트 위키화 (기본) | `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) → API Keys |
| **Google Gemini API** | 노트 위키화 (Claude 실패 시 폴백) | `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) → API Keys |

### Google Cloud
| API | 용도 | 비활성화 위치 |
|-----|------|---------------|
| **Google Drive API v3** | 노트 읽기, wiki.json/index.html 저장 | [GCP Console](https://console.cloud.google.com) → APIs & Services → Enabled APIs → Drive API → Disable |
| **서비스 계정** | Drive API 인증 | GCP Console → IAM & Admin → Service Accounts → 해당 계정 → Disable |

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

# credentials/ 폴더에 서비스 계정 JSON 파일 배치
mkdir -p credentials
# credentials/service_account.json 복사

# 파이프라인 직접 실행
python run_local.py

# Web 서버 로컬 실행
uvicorn src.main:app --reload
```

### 로컬 실행 전 Google Drive 사전 준비
`wikis` 폴더에 빈 `wiki.json`과 `index.html`이 없으면 저장 시 403 에러가 발생합니다.
(서비스 계정은 파일 신규 생성 불가 — 업데이트만 가능)

```
에러:
  - wiki.json 저장 실패: <HttpError 403...>
  도움말: 지정한 공유 wiki 폴더에 비어있는 index.html과 wiki.json을 업로드하십시오...
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
│   ├── pipeline/
│   │   ├── runner.py        # 위키화 파이프라인 오케스트레이터
│   │   ├── claude_processor.py   # Claude API 호출
│   │   ├── gemini_processor.py   # Gemini API 호출 (폴백)
│   │   └── wiki_store.py    # wiki.json 로드/저장/업서트
│   ├── telegram/
│   │   ├── bot.py           # Webhook 핸들러 및 명령어 처리
│   │   └── notifier.py      # 알람 전송
│   └── utils/
│       └── time_utils.py    # 주차 계산 등 공통 유틸
├── viewer/
│   └── index.html           # 로컬 HTML 뷰어 (위키 + 그래프 뷰)
└── scripts/
    └── register_webhook.py  # 텔레그램 Webhook URL 등록 스크립트
```

---

## 7. 주요 로직 흐름

### 위키화 파이프라인 (`runner.py`)
```
1. wiki.json 로드 (Drive)
2. last_processed_at 이후 수정된 노트만 읽기 (incremental)
3. 기존 아이템 목록을 컨텍스트로 Claude에게 전달
   ├─ 아이템 ≤ 20개: title + tags + summary 전체 전달
   └─ 아이템 > 20개: title + tags 요약본만 전달 (토큰 절약)
4. Claude → 실패 시 Gemini 폴백
5. 반환된 아이템을 기존 wiki에 upsert (제목 일치 → 버전 누적 / 불일치 → 신규)
6. wiki.json 저장, index.html 업데이트 (Drive)
7. 텔레그램으로 결과 알람 전송
```

### 텔레그램 Webhook 흐름
```
사용자 /run 전송
→ Telegram → Render Web Service (슬립 중이면 콜드 스타트 30초~1분)
→ bot.py: 즉시 "시작합니다" 응답 (timeout 방지)
→ 백그라운드 스레드에서 run_pipeline() 실행
→ 완료 후 결과 알람 전송
```
