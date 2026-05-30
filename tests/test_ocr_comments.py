"""
#10 이미지 OCR 처리 및 #11 코멘트 기능 단위 테스트.
Drive API / Claude API 호출은 mock 처리한다.
"""
import json
import pytest
from unittest.mock import patch, MagicMock

from src.pipeline.wiki_store import (
    empty_wiki, upsert_item, make_version, current_week_str,
    make_attachment, add_attachment_to_item, add_comment_to_item, find_item_by_id,
)
from src.drive.client import COMMENT_PATTERN, IMAGE_EXTENSIONS, IMAGE_MIME_TYPES


# ── wiki_store: attachment / comment 헬퍼 ─────────────────────

class TestMakeAttachment:
    def test_required_fields(self):
        att = make_attachment("drv_001", "note.jpg", "텍스트", "요약", ["태그"])
        assert att["type"] == "image"
        assert att["drive_id"] == "drv_001"
        assert att["filename"] == "note.jpg"
        assert att["ocr_text"] == "텍스트"
        assert att["summary"] == "요약"
        assert att["tags"] == ["태그"]


class TestAddAttachmentToItem:
    def _make_wiki_with_item(self):
        wiki = empty_wiki()
        version = make_version(current_week_str(), "내용", [])
        item, _ = upsert_item(wiki, "테스트 아이템", ["태그"], "요약", version)
        return wiki, item["id"]

    def test_add_attachment_to_existing_item(self):
        wiki, item_id = self._make_wiki_with_item()
        att = make_attachment("drv_001", "img.jpg", "OCR", "요약", [])
        result = add_attachment_to_item(wiki, item_id, att)
        assert result is True
        item = find_item_by_id(wiki, item_id)
        assert len(item["attachments"]) == 1
        assert item["attachments"][0]["drive_id"] == "drv_001"

    def test_returns_false_for_nonexistent_item(self):
        wiki = empty_wiki()
        att = make_attachment("drv_001", "img.jpg", "OCR", "요약", [])
        result = add_attachment_to_item(wiki, "nonexistent_id", att)
        assert result is False

    def test_duplicate_drive_id_updates_not_appends(self):
        wiki, item_id = self._make_wiki_with_item()
        att = make_attachment("drv_001", "img.jpg", "OCR 초기", "요약1", [])
        add_attachment_to_item(wiki, item_id, att)
        att2 = make_attachment("drv_001", "img.jpg", "OCR 업데이트", "요약2", [])
        result = add_attachment_to_item(wiki, item_id, att2)
        assert result is False  # 기존 업데이트
        item = find_item_by_id(wiki, item_id)
        assert len(item["attachments"]) == 1
        assert item["attachments"][0]["ocr_text"] == "OCR 업데이트"

    def test_multiple_different_attachments(self):
        wiki, item_id = self._make_wiki_with_item()
        add_attachment_to_item(wiki, item_id, make_attachment("drv_001", "a.jpg", "", "", []))
        add_attachment_to_item(wiki, item_id, make_attachment("drv_002", "b.png", "", "", []))
        item = find_item_by_id(wiki, item_id)
        assert len(item["attachments"]) == 2


class TestAddCommentToItem:
    def _make_wiki_with_item(self):
        wiki = empty_wiki()
        version = make_version(current_week_str(), "내용", [])
        item, _ = upsert_item(wiki, "테스트 아이템", [], "요약", version)
        return wiki, item["id"]

    def test_add_comment(self):
        wiki, item_id = self._make_wiki_with_item()
        result = add_comment_to_item(wiki, item_id, "2026-05-27", "코멘트 내용")
        assert result is True
        item = find_item_by_id(wiki, item_id)
        assert len(item["comments"]) == 1
        assert item["comments"][0]["text"] == "코멘트 내용"
        assert item["comments"][0]["date"] == "2026-05-27"

    def test_returns_false_for_nonexistent_item(self):
        wiki = empty_wiki()
        result = add_comment_to_item(wiki, "nonexistent", "2026-05-27", "내용")
        assert result is False

    def test_duplicate_date_overwrites(self):
        wiki, item_id = self._make_wiki_with_item()
        add_comment_to_item(wiki, item_id, "2026-05-27", "초기 내용")
        result = add_comment_to_item(wiki, item_id, "2026-05-27", "수정된 내용")
        assert result is False  # 덮어씀
        item = find_item_by_id(wiki, item_id)
        assert len(item["comments"]) == 1
        assert item["comments"][0]["text"] == "수정된 내용"

    def test_multiple_different_dates(self):
        wiki, item_id = self._make_wiki_with_item()
        add_comment_to_item(wiki, item_id, "2026-05-20", "첫 번째")
        add_comment_to_item(wiki, item_id, "2026-05-27", "두 번째")
        item = find_item_by_id(wiki, item_id)
        assert len(item["comments"]) == 2

    def test_comment_with_attachments(self):
        wiki, item_id = self._make_wiki_with_item()
        add_comment_to_item(wiki, item_id, "2026-05-27", "내용", attachments=[{"file": "img.jpg"}])
        item = find_item_by_id(wiki, item_id)
        assert item["comments"][0]["attachments"] == [{"file": "img.jpg"}]


# ── drive.client: 파일명 패턴 파싱 ───────────────────────────────

class TestCommentPattern:
    def test_valid_comment_filename(self):
        m = COMMENT_PATTERN.match("comment_item_abc123_2026-05-27.txt")
        assert m is not None
        assert m.group(1) == "item_abc123"
        assert m.group(2) == "2026-05-27"

    def test_valid_with_uuid_style_id(self):
        m = COMMENT_PATTERN.match("comment_item_a1b2c3d4_2026-01-01.txt")
        assert m is not None

    def test_invalid_no_comment_prefix(self):
        assert COMMENT_PATTERN.match("note_item_abc_2026-05-27.txt") is None

    def test_invalid_missing_date(self):
        assert COMMENT_PATTERN.match("comment_item_abc.txt") is None

    def test_invalid_wrong_extension(self):
        assert COMMENT_PATTERN.match("comment_item_abc_2026-05-27.md") is None

    def test_invalid_bad_date_format(self):
        assert COMMENT_PATTERN.match("comment_item_abc_20260527.txt") is None


class TestImageExtensions:
    def test_common_extensions_supported(self):
        for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif"]:
            assert ext in IMAGE_EXTENSIONS

    def test_mime_type_mapping(self):
        assert IMAGE_MIME_TYPES[".jpg"] == "image/jpeg"
        assert IMAGE_MIME_TYPES[".png"] == "image/png"
        assert IMAGE_MIME_TYPES[".heic"] == "image/heic"


# ── claude_processor: OCR mock 테스트 ───────────────────────────

class TestOcrImageWithClaude:
    def test_ocr_returns_parsed_dict(self):
        from src.pipeline.claude_processor import ocr_image_with_claude

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps({
            "ocr_text": "추출된 텍스트",
            "summary": "이미지 요약",
            "tags": ["메모", "아이디어"],
        }))]

        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = mock_response
            result = ocr_image_with_claude(b"fake_image_bytes", "image/jpeg", "test.jpg")

        assert result["ocr_text"] == "추출된 텍스트"
        assert result["summary"] == "이미지 요약"
        assert "메모" in result["tags"]

    def test_ocr_strips_json_fence(self):
        from src.pipeline.claude_processor import ocr_image_with_claude

        raw = '```json\n{"ocr_text": "텍스트", "summary": "요약", "tags": []}\n```'
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=raw)]

        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = mock_response
            result = ocr_image_with_claude(b"fake_image_bytes", "image/png", "img.png")

        assert result["ocr_text"] == "텍스트"

    def test_ocr_raises_on_api_error(self):
        from src.pipeline.claude_processor import ocr_image_with_claude

        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.side_effect = Exception("API 오류")
            with pytest.raises(Exception, match="API 오류"):
                ocr_image_with_claude(b"bytes", "image/jpeg", "fail.jpg")

    def test_ocr_heic_conversion_failure_raises(self):
        """HEIC 변환 실패 시 RuntimeError가 발생해야 한다."""
        from src.pipeline.claude_processor import ocr_image_with_claude

        with patch("anthropic.Anthropic"):
            with patch("PIL.Image.open", side_effect=Exception("변환 불가")):
                with pytest.raises(RuntimeError, match="HEIC 변환 실패"):
                    ocr_image_with_claude(b"heic_bytes", "image/heic", "photo.heic")


# ── runner: OCR + 코멘트 파이프라인 통합 mock 테스트 ──────────────

class TestRunnerWithOcrAndComments:
    def _base_mocks(self):
        """공통 mock 설정을 반환한다."""
        return {
            "read_notes_from_folder": [],  # 노트 없음
            "list_images": [],
            "list_comment_files": [],
        }

    def test_pipeline_with_no_new_content(self):
        from src.pipeline.runner import run_pipeline

        with patch("src.pipeline.runner.find_file_in_folder", return_value=None), \
             patch("src.pipeline.runner.read_notes_from_folder", return_value=[]), \
             patch("src.pipeline.runner.list_images", return_value=[]), \
             patch("src.pipeline.runner.list_comment_files", return_value=[]), \
             patch("src.pipeline.runner.upload_json", return_value="file_id"), \
             patch("os.getenv", side_effect=lambda k, d=None: "test_folder" if "FOLDER" in k else d):
            result = run_pipeline()
        assert result["status"] == "success"
        assert result["processed"] == 0

    def test_pipeline_ocr_skip_on_failure(self):
        """OCR 실패 시 해당 파일만 스킵, 전체 파이프라인은 계속 진행."""
        from src.pipeline.runner import run_pipeline

        mock_image = {"id": "img_001", "name": "test.jpg", "extension": ".jpg", "modifiedTime": "2026-05-27T00:00:00Z"}

        with patch("src.pipeline.runner.find_file_in_folder", return_value=None), \
             patch("src.pipeline.runner.read_notes_from_folder", return_value=[]), \
             patch("src.pipeline.runner.list_images", return_value=[mock_image]), \
             patch("src.pipeline.runner.list_comment_files", return_value=[]), \
             patch("src.pipeline.runner.download_file_bytes", return_value=b"bytes"), \
             patch("src.pipeline.runner.ocr_image_with_claude", side_effect=Exception("Vision API 오류")), \
             patch("src.pipeline.runner.upload_json", return_value="file_id"), \
             patch("os.getenv", side_effect=lambda k, d=None: "test_folder" if "FOLDER" in k else d):
            result = run_pipeline()

        assert result["ocr_skipped"] == 1
        assert any("OCR 실패" in e for e in result["errors"])

    def test_pipeline_comment_processed(self):
        """코멘트 파일이 올바르게 처리된다."""
        from src.pipeline.runner import run_pipeline

        mock_comment = {
            "id": "cf_001", "name": "comment_item_abc_2026-05-27.txt",
            "item_id": "item_abc", "date": "2026-05-27", "modifiedTime": "2026-05-27T00:00:00Z"
        }

        wiki_with_item = json.dumps({
            "schema_version": "1",
            "updated_at": "2026-05-01T00:00:00Z",
            "last_processed_at": None,
            "items": [{
                "id": "item_abc",
                "title": "테스트 아이템",
                "tags": [], "summary": "", "versions": [],
                "related": [], "comments": [],
            }]
        })

        with patch("src.pipeline.runner.find_file_in_folder", return_value="wiki_file_id"), \
             patch("src.pipeline.runner.read_note", return_value=wiki_with_item), \
             patch("src.pipeline.runner.read_notes_from_folder", return_value=[]), \
             patch("src.pipeline.runner.list_images", return_value=[]), \
             patch("src.pipeline.runner.list_comment_files", return_value=[mock_comment]), \
             patch("src.pipeline.runner.upload_json", return_value="file_id"), \
             patch("src.pipeline.runner.read_note", side_effect=[wiki_with_item, "코멘트 내용"]), \
             patch("os.getenv", side_effect=lambda k, d=None: "test_folder" if "FOLDER" in k else d):
            result = run_pipeline()

        assert result["comments_processed"] == 1
