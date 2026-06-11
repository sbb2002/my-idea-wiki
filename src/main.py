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
        "Write for an LLM agent that will autonomously implement this from scratch."
    )

    return "\n\n".join(parts)


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
