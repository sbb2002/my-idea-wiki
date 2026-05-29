"""
Claude API를 사용해 노트를 위키 아이템으로 변환한다.
"""
import os
import json
import anthropic

# 한 번에 처리할 최대 노트 수 (토큰 절약)
BATCH_SIZE = 10

SYSTEM_PROMPT = """당신은 아이디어 노트를 위키 아이템으로 정리하는 어시스턴트입니다.

주어진 노트들을 분석해서 아이템별로 묶고, 각 아이템에 대해 다음을 생성하세요:
- title: 아이템의 핵심 주제를 나타내는 간결한 제목 (한국어 또는 영어)
- tags: 분류 태그 목록. 노트에 #태그 형식으로 명시된 수동 태그가 있으면 반드시 포함하고, 없으면 내용 기반으로 자동 생성
- summary: 이 아이디어의 현재 상태를 나타내는 요약 (3-5문장)
- content: 이번 주 업데이트 내용 — 노트의 핵심 아이디어, 인사이트, 발전 방향을 서술형으로 정리

여러 노트가 같은 주제를 다루면 하나의 아이템으로 묶으세요.

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


def _build_user_prompt(notes: list[dict]) -> str:
    parts = []
    for i, note in enumerate(notes, 1):
        manual_tags = ", ".join(f"#{t}" for t in note.get("tags", []))
        tag_hint = f"\n수동 태그: {manual_tags}" if manual_tags else ""
        parts.append(
            f"=== 노트 {i}: {note['name']} ==={tag_hint}\n{note['content']}"
        )
    return "\n\n".join(parts)


def wikify_with_claude(notes: list[dict]) -> list[dict]:
    """
    Claude API로 노트 목록을 위키 아이템 목록으로 변환한다.

    Args:
        notes: drive.client.read_notes_from_folder() 반환값

    Returns:
        위키 아이템 dict 목록 (title, tags, summary, content, source_note_names)

    Raises:
        Exception: API 호출 실패 시 (폴백 처리는 호출자가 담당)
    """
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    all_items = []

    for i in range(0, len(notes), BATCH_SIZE):
        batch = notes[i: i + BATCH_SIZE]
        prompt = _build_user_prompt(batch)

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = message.content[0].text.strip()
        # JSON fence 제거 (모델이 가끔 ```json ... ``` 로 감쌀 수 있음)
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        parsed = json.loads(raw)
        all_items.extend(parsed.get("items", []))

    return all_items
