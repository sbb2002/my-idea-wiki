# 💡 아이디어 위키 (my-idea-wiki)

구글 드라이브에 아이디어 노트를 올리면 AI가 자동으로 위키 문서로 정리해주는 파이프라인입니다.

노트가 흩어지고 맥락을 잃어버리는 문제를 해결하기 위해,  
Claude(폴백: Gemini)가 노트를 아이템별로 묶고 버전을 누적하며,  
로컬 HTML 뷰어와 그래프 뷰로 아이디어의 전체 지형을 한눈에 파악할 수 있습니다.

---

## 시스템 흐름

```
[1] 구글 드라이브 notes 폴더에 노트 업로드
    (텍스트, 구글 독스, 이미지, PDF 지원)

[2] 자동 위키화 (Render Cron Job, 기본 매주 월요일)
    노트 읽기 → Claude API (폴백: Gemini) → wiki.json 생성/업데이트
    → 구글 드라이브 wikis 폴더에 저장 → 텔레그램 결과 알람 + wikis 폴더 링크

[3] 결과 확인
    wikis 폴더의 index.html 다운로드 또는 동기화 → 브라우저에서 열기
    위키 문서 + 그래프 뷰로 아이디어 탐색
```

또는 텔레그램에서 `/run`으로 즉시 실행할 수 있습니다.

---

## 주요 기능

- **자동 위키화** — 노트를 아이템별로 분류하고, 같은 주제의 노트는 버전으로 누적
- **다양한 파일 형식 지원** — 텍스트, 구글 독스, 이미지(JPG/PNG/HEIC), PDF
- **이미지 OCR** — 손글씨 메모 사진을 Claude Vision으로 텍스트 추출 후 위키화
- **PDF 분석** — 페이지별 Vision 분석으로 타이핑/손글씨/그림 모두 추출. 그림 영역은 크롭 후 Drive pic/ 폴더에 저장하고 뷰어에 인라인 표시
- **태그 시스템** — `#태그명` 형식으로 수동 태그 지정 (AI 자동 분류보다 우선)
- **병합 지능** — 기존 위키 아이템을 컨텍스트로 활용해 중복 생성 방지
- **Claude → Gemini 폴백** — API 실패 시 자동 전환, 이중 실패 시 텔레그램 알람
- **텔레그램 봇** — `/run` `/rerun` `/status` `/schedule` `/set` `/help` 명령으로 원격 제어
- **완료 알람에 wikis 폴더 링크 포함** — 결과 확인 위치를 바로 안내
- **로컬 HTML 뷰어** — 위키 문서 + Obsidian 스타일 그래프 뷰, 라이트/다크 테마

---

## 빠른 시작 (사용자)

1. **텔레그램 봇 생성** — @BotFather에서 봇 토큰과 Chat ID 발급
2. **구글 드라이브 폴더 설정** — `scripts/setup_drive.py` 실행으로 폴더 구조 자동 생성
3. **`wikis` 폴더에 빈 파일 업로드** — `wiki.json`과 `index.html` 미리 업로드 필수  
   *(구글 드라이브 설정에서 "Google 문서 자동변환" 옵션 해제 후 업로드)*
4. **텔레그램에서 `/run`** — 노트를 `notes` 폴더에 올리고 명령 전송
5. **결과 확인** — 완료 알람의 wikis 폴더 링크 클릭 → `index.html` 다운로드 후 브라우저에서 열기

> 자세한 내용은 **[instruction.md](./instruction.md)** 참고

---

## 기술 스택

| 구분 | 기술 |
|------|------|
| 서버 | Python, FastAPI, Render (Cron Job + Web Service) |
| AI | Anthropic Claude API (Vision 포함), Google Gemini API |
| 저장 | Google Drive API v3, OAuth 2.0 인증 |
| 알람/제어 | Telegram Bot API (Webhook) |
| 뷰어 | Vanilla JS, D3-like Canvas 그래프 (단일 HTML 파일) |

---

## 문서

| 문서 | 대상 | 내용 |
|------|------|------|
| [instruction.md](./instruction.md) | 사용자 | 봇 설정, 노트 작성법, 뷰어 사용법 |
| [dev_manual.md](./dev_manual.md) | 개발자 | Render 배포, 환경변수, API 목록, 코드 구조 |
