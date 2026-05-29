# my-idea-wiki

아이디어 노트 자동 위키화 시스템.

Google Drive에 업로드한 노트를 AI(Claude/Gemini)가 자동으로 아이템별 위키로 정리하고,  
로컬 HTML 뷰어로 Obsidian 스타일 그래프와 함께 열람하는 파이프라인입니다.

## 구조

```
src/
  drive/       # Google Drive API v3 연동 (노트 읽기, JSON 저장)
  pipeline/    # 위키화 처리 (Claude → Gemini 폴백)
  telegram/    # 봇 명령어 및 알람
  utils/       # 공통 유틸
tests/
credentials/   # 서비스 계정 JSON (gitignore됨)
```

## 설정

```bash
cp .env.example .env
# .env 파일에 각 API 키와 폴더 ID 입력
```

## 실행

```bash
pip install -r requirements.txt
uvicorn src.main:app --reload
```

## 환경변수

| 변수 | 설명 |
|------|------|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | 서비스 계정 키 경로 |
| `DRIVE_NOTES_FOLDER_ID` | 노트 업로드 폴더 ID |
| `DRIVE_WIKI_FOLDER_ID` | wiki.json 저장 폴더 ID |
| `ANTHROPIC_API_KEY` | Claude API 키 |
| `GEMINI_API_KEY` | Gemini API 키 (폴백용) |
| `TELEGRAM_BOT_TOKEN` | 텔레그램 봇 토큰 |
| `TELEGRAM_CHAT_ID` | 알람 수신 chat ID |
| `TELEGRAM_WEBHOOK_URL` | Render Web Service URL |
| `SCHEDULE_CRON` | Cron 표현식 (기본: `0 9 * * 1`) |
