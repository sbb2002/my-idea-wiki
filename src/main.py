"""
FastAPI 앱 — Render Web Service 진입점.

엔드포인트:
  GET  /health    — 헬스 체크 (Render keep-alive용으로도 사용)
  POST /webhook   — 텔레그램 Webhook 수신

슬립 방지 전략:
  파이프라인 실행 중에는 asyncio로 self-ping을 30초마다 보내
  Render가 idle로 판단해 프로세스를 죽이지 않도록 한다.
"""
import asyncio
import hmac
import logging
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("idea-wiki")

from src.telegram.bot import handle_update, _mark_started

app = FastAPI(title="Idea Wiki System")
_mark_started()

# CORS — gh-pages 뷰어(브라우저)에서 호출 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://sbb2002.github.io", "http://localhost", "http://127.0.0.1", "null"],
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type"],
)

# 파이프라인 실행 중 self-ping 태스크 핸들
_keepalive_task: asyncio.Task | None = None


async def _self_ping_loop():
    """파이프라인 실행 중 30초마다 /health를 self-ping해 슬립 방지."""
    import aiohttp
    port = os.getenv("PORT", "10000")
    url = f"http://localhost:{port}/health"
    log.info("[keep-alive] self-ping 시작")
    try:
        async with aiohttp.ClientSession() as session:
            while True:
                await asyncio.sleep(30)
                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
                        log.info(f"[keep-alive] ping {r.status}")
                except Exception as e:
                    log.warning(f"[keep-alive] ping 실패: {e}")
    except asyncio.CancelledError:
        log.info("[keep-alive] self-ping 종료")


def start_keepalive():
    global _keepalive_task
    if _keepalive_task is None or _keepalive_task.done():
        try:
            loop = asyncio.get_event_loop()
            _keepalive_task = loop.create_task(_self_ping_loop())
        except RuntimeError:
            pass


def stop_keepalive():
    global _keepalive_task
    if _keepalive_task and not _keepalive_task.done():
        _keepalive_task.cancel()
        _keepalive_task = None


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/webhook")
async def telegram_webhook(request: Request):
    """
    텔레그램 Update를 수신해 asyncio 태스크로 처리한다.
    파이프라인 실행 중에는 self-ping으로 슬립을 방지한다.
    """
    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET")
    if secret:
        token_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not hmac.compare_digest(token_header, secret):
            raise HTTPException(status_code=403, detail="Invalid secret token")

    try:
        update = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    log.info(f"[webhook] update 수신: {list(update.keys())}")

    async def _run():
        try:
            await asyncio.to_thread(handle_update, update)
        except Exception as e:
            log.error(f"[webhook] handle_update 오류: {e}", exc_info=True)
        finally:
            log.info("[webhook] 처리 완료")

    asyncio.create_task(_run())
    return {"ok": True}


# ── PRD 생성 엔드포인트 ────────────────────────────────────────
_PRD_SYSTEM_PROMPT = """\
You are a precise technical writer that produces Product Requirements Documents (PRDs) \
for LLM-based autonomous implementation agents.

Rules:
- Write in the same language as the idea content (Korean if Korean, English if English).
- Be exhaustive and unambiguous — the implementing LLM has no other context.

Capture what makes THIS idea unique:
- Identify the distinctive value of this specific idea: the exact problem it solves, \
for whom, and the design choices that differentiate it from a generic product in the \
same category. A PRD that could describe any similar product is a failed PRD.
- Infer the following directly from the idea content and state them explicitly:
  * Core value — the single most important thing this idea must deliver.
  * MVP scope — the minimal feature set that proves the core value, AND what is \
deliberately excluded from the first version.
  * Constraints & risks — technical or UX constraints implied by the content, and \
the weakest assumption that would break this idea first.
- Do NOT invent features that contradict the idea content. Where the content is \
silent, choose the simplest option that serves the core value and mark it clearly \
as an assumption.

Output constraints:
- Do NOT include version history, attachment metadata, or changelog.
- Include related items ONLY if they are architecturally inseparable from this item.
- Output raw Markdown only. No preamble, no explanation, no code fences around the document.
"""


class PrdRequest(BaseModel):
    item_id: str
    title: str
    tags: list[str] = []
    summary: str = ""
    body: str = ""
    related_items: list[dict] = []   # [{title, summary}]


def _build_prd_prompt(req: PrdRequest) -> str:
    parts: list[str] = []

    parts.append(f"# Idea Title\n{req.title}")

    if req.tags:
        parts.append(f"# Tags\n{', '.join(req.tags)}")

    if req.summary:
        parts.append(f"# Summary\n{req.summary}")

    if req.body:
        parts.append(f"# Detailed Content\n{req.body}")

    # 연관 아이템
    if req.related_items:
        rel_lines = "\n".join(f"- **{r['title']}**: {r.get('summary', '')}" for r in req.related_items)
        parts.append(f"# Related Items\n{rel_lines}")

    parts.append(
        "---\n"
        "Generate a comprehensive PRD for THIS specific idea. Structure it with: "
        "Overview, Core Value, MVP Scope (including explicit exclusions), Requirements, "
        "Technical Considerations, and Risks & Assumptions.\n"
        "Write for an LLM agent that will autonomously implement this from scratch.\n\n"
        "IMPORTANT: The very first lines of the PRD output must be the following blockquote "
        "exactly as written (translate field labels to match the document language, "
        "but preserve the instruction meaning precisely):\n\n"
        "> **[구현 에이전트에게]**\n"
        "> 이 PRD를 받은 즉시 구현을 시작하지 말 것.\n"
        ">\n"
        "> 먼저 PRD 전체를 읽고 명시되지 않은 결정, 엣지 케이스, 모호한 요구사항을\n"
        "> 결정 트리로 정리하라. 그 후 아래 규칙에 따라 사용자를 인터뷰하라:\n"
        ">\n"
        "> - 질문은 **한 번에 하나씩**\n"
        "> - 각 질문마다 **권장 답변을 함께 제시**하고 사용자가 동의/수정하도록 유도\n"
        "> - 상위 결정(아키텍처, 데이터 모델)을 먼저 해소하고, 하위 결정(UX 세부사항,\n"
        ">   에러 처리)은 나중에 다룰 것\n"
        "> - 답변이 새로운 불확실성을 드러내면 그 가지를 끝까지 파고들 것\n"
        "> - 모든 주요 분기가 해소되면 인터뷰를 종료하고 확정된 결정 요약을 제공\n"
        ">\n"
        "> 인터뷰 완료 후 사용자의 확인을 받은 다음 구현을 시작하라.\n\n"
        "After this blockquote, write the PRD body."
    )

    return "\n\n".join(parts)


_VIABILITY_PROMPT = """\
아래 아이디어 노트 내용을 읽고, 이것이 PRD(제품 요구사항 문서)로 만들기에 충분한 내용인지 판단하라.

판단 기준 — 아래 중 2개 이상 해당하면 부실(insufficient)로 판정:
1. summary가 3문장 미만이거나 없음
2. body가 없거나 200자 미만
3. "무엇을 만드는가"(결과물의 형태: 앱/시스템/도구 등)가 불명확
4. MVP 범위나 제외 사항을 전혀 추론할 수 없음

반드시 아래 JSON 형식으로만 응답하라. 다른 텍스트 없이:
{"sufficient": true} 또는 {"sufficient": false, "reasons": ["이유1", "이유2"]}

---
제목: {title}
태그: {tags}
요약: {summary}
본문: {body}
"""


class ViabilityRequest(BaseModel):
    title: str
    tags: list[str] = []
    summary: str = ""
    body: str = ""


@app.post("/api/check-prd-viability")
async def check_prd_viability(req: ViabilityRequest):
    """
    PRD 생성 전 내용 충분성 사전 검사.
    Haiku로 판단, 실패 시 Gemini Flash로 폴백.
    """
    import anthropic as _anthropic

    prompt = _VIABILITY_PROMPT.format(
        title=req.title,
        tags=", ".join(req.tags) if req.tags else "(없음)",
        summary=req.summary or "(없음)",
        body=req.body or "(없음)",
    )

    def _parse(text: str) -> dict:
        import json as _json
        text = text.strip()
        # 코드 펜스 제거
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return _json.loads(text.strip())

    # 1차: Claude Haiku
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        try:
            client = _anthropic.Anthropic(api_key=api_key)
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            )
            return _parse(msg.content[0].text)
        except Exception as e:
            log.warning(f"[viability] Haiku 실패, Gemini 폴백: {e}")

    # 2차: Gemini Flash
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        try:
            from google import genai as _genai
            client = _genai.Client(api_key=gemini_key)
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            return _parse(resp.text)
        except Exception as e:
            log.warning(f"[viability] Gemini 폴백도 실패: {e}")

    # 양쪽 실패 시 sufficient로 간주 (생성 막지 않음)
    log.error("[viability] 모든 모델 실패 — sufficient=true로 패스스루")
    return {"sufficient": True}


@app.post("/api/generate-prd")
async def generate_prd_endpoint(req: PrdRequest):
    """
    브라우저에서 PRD 생성 요청을 받아:
    1. Claude API로 PRD Markdown 생성
    2. gh-pages/prd/{item_id}.md 에 push
    3. {prd_url} 반환
    """
    import anthropic as _anthropic
    from src.github.gh_pages import push_file

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY가 서버에 설정되지 않았습니다.")

    log.info(f"[generate-prd] 요청: {req.item_id} — {req.title}")

    # 1. Claude API 호출
    try:
        client = _anthropic.Anthropic(api_key=api_key)
        prompt = _build_prd_prompt(req)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=_PRD_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        prd_text = message.content[0].text.strip()
    except Exception as e:
        log.error(f"[generate-prd] Claude API 실패: {e}")
        raise HTTPException(status_code=502, detail=f"Claude API 오류: {e}")

    if not prd_text:
        raise HTTPException(status_code=502, detail="Claude 응답이 비어있습니다.")

    # 2. gh-pages/prd/{item_id}.md push
    prd_path = f"prd/{req.item_id}.md"
    try:
        await asyncio.to_thread(
            push_file,
            prd_path,
            prd_text,
            f'prd: generate PRD for "{req.title}"',
        )
    except Exception as e:
        log.error(f"[generate-prd] GitHub push 실패: {e}")
        raise HTTPException(status_code=502, detail=f"GitHub 저장 실패: {e}")

    repo = os.getenv("GITHUB_REPO", "sbb2002/my-idea-wiki")
    owner, repo_name = repo.split("/", 1)
    prd_url = f"https://raw.githubusercontent.com/{owner}/{repo_name}/gh-pages/{prd_path}"

    log.info(f"[generate-prd] 완료: {prd_path}")
    return {"ok": True, "prd_url": prd_url, "prd": prd_text}
