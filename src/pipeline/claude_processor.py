"""
Claude API를 사용해 노트를 위키 아이템으로 변환한다.
"""
import os
import json
import base64
import anthropic

# 한 번에 처리할 최대 노트 수 (토큰 절약)
BATCH_SIZE = 10

OCR_SYSTEM_PROMPT = """당신은 손글씨 메모나 사진 속 텍스트를 정확하게 추출하는 OCR 어시스턴트입니다.

이미지에서 텍스트를 추출하고 다음 JSON 형식으로만 응답하세요. 다른 텍스트는 절대 포함하지 마세요.
{
  "ocr_text": "추출한 텍스트 전문",
  "summary": "이미지 내용 요약 (2-3문장)",
  "tags": ["관련 태그1", "태그2"]
}

텍스트가 없는 이미지(사진, 도표 등)의 경우:
{
  "ocr_text": "",
  "summary": "이미지 내용 설명",
  "tags": []
}"""

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


def ocr_image_with_claude(image_bytes: bytes, mime_type: str, filename: str) -> dict:
    """
    Claude Vision API로 이미지에서 텍스트를 추출하고 요약한다.

    Args:
        image_bytes: 이미지 raw bytes
        mime_type: 이미지 MIME type (예: "image/jpeg")
        filename: 파일명 (로그용)

    Returns:
        {
            "ocr_text": "추출 텍스트",
            "summary": "요약",
            "tags": ["태그1", ...],
        }

    Raises:
        Exception: API 호출 실패 시
    """
    # HEIC/HEIF는 JPEG로 변환 (Claude Vision 미지원)
    if mime_type in ("image/heic", "image/heif"):
        try:
            from PIL import Image
            import io as _io
            img = Image.open(_io.BytesIO(image_bytes))
            buf = _io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG")
            image_bytes = buf.getvalue()
            mime_type = "image/jpeg"
        except Exception as e:
            raise RuntimeError(f"HEIC 변환 실패 ({filename}): {e}") from e

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    b64_data = base64.standard_b64encode(image_bytes).decode("utf-8")

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=OCR_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime_type,
                            "data": b64_data,
                        },
                    },
                    {"type": "text", "text": f"파일명: {filename}\n위 이미지에서 텍스트를 추출하고 요약해주세요."},
                ],
            }
        ],
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    return json.loads(raw)
