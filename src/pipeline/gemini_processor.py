"""
Gemini API 폴백 프로세서.
Claude API 실패 시 자동으로 호출된다.
"""
import os
import json
from google import genai
from google.genai import types

BATCH_SIZE = 10
EXISTING_ITEMS_FULL_THRESHOLD = 20

SYSTEM_PROMPT = """당신은 아이디어 노트를 위키 아이템으로 정리하는 어시스턴트입니다.

주어진 노트들을 분석해서 아이템별로 묶고, 각 아이템에 대해 다음을 생성하세요:
- title: 아이템의 핵심 주제를 나타내는 간결한 제목 (한국어 또는 영어)
- tags: 분류 태그 목록. 노트에 #태그 형식으로 명시된 수동 태그가 있으면 반드시 포함하고, 없으면 내용 기반으로 자동 생성
- summary: 이 아이디어의 현재 상태를 나타내는 요약 (3-5문장)
- content: 이번 주 업데이트 내용 — 노트의 핵심 아이디어, 인사이트, 발전 방향을 서술형으로 정리

여러 노트가 같은 주제를 다루면 하나의 아이템으로 묶으세요.

[기존 아이템과의 병합 규칙]
- 아래에 기존 위키 아이템 목록이 제공됩니다.
- 새 노트의 내용이 기존 아이템과 같은 주제라면, 반드시 기존 아이템의 title을 그대로 사용하세요.
- 새로운 주제라면 새 title을 만드세요.
- 애매한 경우 기존 아이템 쪽으로 병합하는 것을 우선시하세요.

반드시 JSON 형식으로만 응답하세요. 다른 텍스트는 절대 포함하지 마세요.
응답 형식:
{
  "items": [
    {
      "title": "아이템 제목",
      "tags": ["태그1", "태그2"],
      "summary": "최신 요약...",
      "content": "이번 주 업데이트 내용...",
      "source_note_names": ["노트파일명1.txt"]
    }
  ]
}"""


def _build_existing_context(existing_items: list[dict]) -> str:
    """기존 위키 아이템을 프롬프트용 컨텍스트 문자열로 변환한다."""
    if not existing_items:
        return ""

    lines = ["=== 기존 위키 아이템 목록 ==="]

    if len(existing_items) <= EXISTING_ITEMS_FULL_THRESHOLD:
        for item in existing_items:
            tags = ", ".join(f"#{t}" for t in item.get("tags", []))
            summary = item.get("summary", "")
            lines.append(f'- "{item["title"]}" [{tags}]\n  요약: {summary}')
    else:
        lines.append("(아이템이 많아 제목+태그 요약본만 제공합니다)")
        for item in existing_items:
            tags = ", ".join(f"#{t}" for t in item.get("tags", []))
            lines.append(f'- "{item["title"]}" [{tags}]')

    lines.append("")
    return "\n".join(lines)


def _build_user_prompt(notes: list[dict], existing_items: list[dict]) -> str:
    parts = []

    existing_ctx = _build_existing_context(existing_items)
    if existing_ctx:
        parts.append(existing_ctx)

    for i, note in enumerate(notes, 1):
        manual_tags = ", ".join(f"#{t}" for t in note.get("tags", []))
        tag_hint = f"\n수동 태그: {manual_tags}" if manual_tags else ""
        parts.append(
            f"=== 노트 {i}: {note['name']} ==={tag_hint}\n{note['content']}"
        )
    return "\n\n".join(parts)


def wikify_with_gemini(notes: list[dict], existing_items: list[dict] | None = None) -> list[dict]:
    """
    Gemini API로 노트 목록을 위키 아이템 목록으로 변환한다.

    Args:
        notes: drive.client.read_notes_from_folder() 반환값
        existing_items: 기존 wiki["items"] 목록. 제공 시 병합 정확도 향상.

    Returns:
        위키 아이템 dict 목록

    Raises:
        Exception: API 호출 실패 시
    """
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    existing_items = existing_items or []
    all_items = []

    for i in range(0, len(notes), BATCH_SIZE):
        batch = notes[i: i + BATCH_SIZE]
        user_prompt = _build_user_prompt(batch, existing_items)

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
            ),
        )

        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        parsed = json.loads(raw)
        all_items.extend(parsed.get("items", []))

    return all_items
