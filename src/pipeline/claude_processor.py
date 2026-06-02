"""
Claude API를 사용해 노트를 위키 아이템으로 변환한다.
"""
import os
import json
import base64
import anthropic

# 한 번에 처리할 최대 노트 수 (토큰 절약)
BATCH_SIZE = 10

# 기존 아이템을 전체 상세로 넘길 최대 개수
# 초과 시 id+title+tags 요약본만 전달
EXISTING_ITEMS_FULL_THRESHOLD = 20

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
    """기존 위키 아이템을 프롬프트용 컨텍스트 문자열로 변환한다.

    아이템 수가 EXISTING_ITEMS_FULL_THRESHOLD 이하면 title+tags+summary 전체,
    초과하면 title+tags 요약본만 반환한다.
    """
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

    lines.append("")  # 빈 줄로 구분
    return "\n".join(lines)


def _build_user_prompt(notes: list[dict], existing_items: list[dict]) -> str:
    parts = []

    # 기존 아이템 컨텍스트를 맨 앞에 삽입
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


def wikify_with_claude(notes: list[dict], existing_items: list[dict] | None = None) -> list[dict]:
    """
    Claude API로 노트 목록을 위키 아이템 목록으로 변환한다.

    Args:
        notes: drive.client.read_notes_from_folder() 반환값
        existing_items: 기존 wiki["items"] 목록. 제공 시 병합 정확도 향상.

    Returns:
        위키 아이템 dict 목록 (title, tags, summary, content, source_note_names)

    Raises:
        Exception: API 호출 실패 시 (폴백 처리는 호출자가 담당)
    """
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    existing_items = existing_items or []
    all_items = []

    for i in range(0, len(notes), BATCH_SIZE):
        batch = notes[i: i + BATCH_SIZE]
        prompt = _build_user_prompt(batch, existing_items)

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = message.content[0].text.strip()
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


PDF_SYSTEM_PROMPT = """당신은 아이디어 노트 PDF를 분석하는 어시스턴트입니다.

PDF의 각 페이지 이미지를 보고 다음을 추출하세요:
- 타이핑된 텍스트
- 손글씨 텍스트
- 이미지/스크린샷 내의 텍스트
- 도형, 화살표, 선이 나타내는 관계나 구조
- 그림/스케치가 표현하는 내용 (묘사)
- 체크박스 상태 (체크됨/미체크)

그림/스케치/다이어그램/이미지 영역이 있으면 해당 영역의 바운딩 박스 좌표를 반드시 포함하세요.
좌표는 페이지 이미지 기준 픽셀 단위입니다 (좌상단 원점).

반드시 JSON 형식으로만 응답하세요.
{
  "pages": [
    {
      "page": 1,
      "text_content": "추출한 모든 텍스트 (타이핑+손글씨 포함)",
      "visual_description": "그림, 스크린샷, 도형 등 시각 요소 묘사",
      "summary": "이 페이지의 핵심 내용 요약 (2-3문장)",
      "drawings": [
        {
          "bbox": [x1, y1, x2, y2],
          "description": "이 그림/스케치/다이어그램이 표현하는 내용 설명"
        }
      ]
    }
  ],
  "overall_summary": "전체 PDF의 핵심 아이디어 요약 (3-5문장)",
  "tags": ["관련 태그1", "태그2"]
}

drawings 배열은 그림이 없는 페이지에서는 빈 배열([])로 두세요."""


def process_pdf_with_claude(pdf_bytes: bytes, filename: str, pic_folder_id: str | None = None) -> dict:
    """
    PDF를 페이지별 이미지로 변환해 Claude Vision으로 분석한다.
    그림 영역이 감지되면 크롭 후 Drive pic/ 폴더에 업로드한다.

    Args:
        pdf_bytes: PDF raw bytes
        filename: 파일명 (로그용)
        pic_folder_id: Drive pic/ 폴더 ID. None이면 이미지 업로드 스킵.

    Returns:
        {
            "overall_summary": str,
            "tags": list[str],
            "pages": list[{"page": int, "text_content": str,
                           "visual_description": str, "summary": str,
                           "drawings": list[{"bbox": [...], "description": str,
                                            "pic_drive_id": str}]}],
            "full_text": str,  # 모든 페이지 text_content 합본
        }

    Raises:
        Exception: API 호출 또는 변환 실패 시
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise RuntimeError("PyMuPDF가 설치되지 않았습니다. pip install pymupdf 실행 후 재시도하세요.")

    import io as _io

    # ── PDF → 페이지별 PNG 변환 ──
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    SCALE = 1.5  # 품질과 토큰의 균형
    mat = fitz.Matrix(SCALE, SCALE)
    page_images = []  # list of (page_index, png_bytes, fitz_page)

    for page in doc:
        pix = page.get_pixmap(matrix=mat)
        png_bytes = pix.tobytes("png")
        # 빈 페이지 스킵 (평균 밝기 253 이상이면 빈 페이지)
        if pix.width * pix.height > 0:
            samples = pix.samples
            avg = sum(samples[::100]) / (len(samples[::100]) or 1)
            if avg < 253:
                page_images.append((page.number, png_bytes, page))

    if not page_images:
        return {
            "overall_summary": "빈 PDF",
            "tags": [],
            "pages": [],
            "full_text": "",
        }

    # ── Claude Vision 호출 ──
    import base64
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    content_blocks = []
    for i, (page_no, png, _) in enumerate(page_images):
        b64 = base64.standard_b64encode(png).decode("utf-8")
        content_blocks.append({
            "type": "text",
            "text": f"=== 페이지 {page_no + 1} ==="
        })
        content_blocks.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": b64,
            }
        })

    content_blocks.append({
        "type": "text",
        "text": f"파일명: {filename}\n위 PDF 페이지들을 분석해서 JSON으로 응답해주세요."
    })

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=PDF_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content_blocks}],
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    parsed = json.loads(raw)

    # ── 그림 크롭 & Drive 업로드 ──
    # page_images 인덱스: 실제 페이지 번호(1-based) → (page_no, png_bytes, fitz_page) 매핑
    page_map = {page_no + 1: (png, fitz_page) for page_no, png, fitz_page in page_images}
    stem = os.path.splitext(filename)[0]

    for page_data in parsed.get("pages", []):
        drawings = page_data.get("drawings", [])
        if not drawings:
            page_data["drawings"] = []
            continue

        page_no = page_data.get("page", 0)
        page_entry = page_map.get(page_no)

        for d_idx, drawing in enumerate(drawings):
            drawing["pic_drive_id"] = None  # 기본값

            bbox = drawing.get("bbox")
            if not bbox or len(bbox) != 4:
                continue

            # 크롭 & 업로드 (pic_folder_id가 있을 때만)
            if pic_folder_id and page_entry:
                try:
                    _, fitz_page = page_entry
                    x1, y1, x2, y2 = [float(c) / SCALE for c in bbox]
                    rect = fitz.Rect(x1, y1, x2, y2)
                    pix_crop = fitz_page.get_pixmap(matrix=mat, clip=rect)
                    jpeg_bytes = _compress_to_jpeg(pix_crop.tobytes("png"), quality=75)

                    pic_filename = f"{stem}_p{page_no}_d{d_idx + 1}.jpg"
                    from src.drive.client import upload_image_bytes
                    drive_id = upload_image_bytes(
                        folder_id=pic_folder_id,
                        filename=pic_filename,
                        image_bytes=jpeg_bytes,
                        mime_type="image/jpeg",
                    )
                    drawing["pic_drive_id"] = drive_id
                except Exception as e:
                    print(f"[WARN] 그림 크롭/업로드 실패 (page {page_no}, drawing {d_idx}): {e}")

    # full_text: 모든 페이지 텍스트 합본
    pages = parsed.get("pages", [])
    full_text = "\n\n".join(
        f"[페이지 {p['page']}]\n{p.get('text_content', '')}\n{p.get('visual_description', '')}"
        for p in pages
    ).strip()

    parsed["full_text"] = full_text
    return parsed


def _compress_to_jpeg(png_bytes: bytes, quality: int = 75) -> bytes:
    """PNG bytes를 JPEG로 압축한다."""
    try:
        from PIL import Image
        import io as _io
        img = Image.open(_io.BytesIO(png_bytes)).convert("RGB")
        buf = _io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        return buf.getvalue()
    except ImportError:
        # Pillow 없으면 PNG 그대로 반환
        return png_bytes
