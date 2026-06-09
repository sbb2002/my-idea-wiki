"""
wiki_store 및 pipeline runner의 단위 테스트.
Drive API / AI API 호출은 mock 처리한다.
"""
import json
import pytest
from unittest.mock import patch, MagicMock

from src.pipeline.wiki_store import (
    empty_wiki, load_wiki, dump_wiki,
    upsert_item, make_version, find_item_by_title, current_week_str,
)


# ── wiki_store 테스트 ──────────────────────────────────────────

class TestEmptyWiki:
    def test_has_required_keys(self):
        wiki = empty_wiki()
        assert "items" in wiki
        assert "last_processed_at" in wiki
        assert wiki["items"] == []
        assert wiki["last_processed_at"] is None


class TestLoadDump:
    def test_roundtrip(self):
        wiki = empty_wiki()
        wiki["items"].append({"id": "item_001", "title": "테스트"})
        dumped = dump_wiki(wiki)
        loaded = load_wiki(dumped)
        assert loaded["items"][0]["title"] == "테스트"

    def test_load_empty_string_returns_empty_wiki(self):
        wiki = load_wiki("")
        assert wiki["items"] == []

    def test_load_whitespace_returns_empty_wiki(self):
        wiki = load_wiki("   ")
        assert wiki["items"] == []


class TestUpsertItem:
    def _make_version(self):
        return make_version(
            week=current_week_str(),
            content="첫 번째 업데이트",
            source_note_ids=["note_id_1"],
        )

    def test_new_item_is_created(self):
        wiki = empty_wiki()
        _, is_new, _ = upsert_item(wiki, "새 아이디어", ["AI"], "요약", self._make_version())
        assert is_new is True
        assert len(wiki["items"]) == 1
        assert wiki["items"][0]["title"] == "새 아이디어"

    def test_duplicate_title_updates_existing(self):
        wiki = empty_wiki()
        upsert_item(wiki, "기존 아이디어", ["AI"], "초기 요약", self._make_version())
        _, is_new, _ = upsert_item(wiki, "기존 아이디어", ["AI"], "업데이트 요약", self._make_version())
        assert is_new is False
        assert len(wiki["items"]) == 1  # 새 아이템이 생기지 않아야 함

    def test_update_accumulates_versions(self):
        wiki = empty_wiki()
        upsert_item(wiki, "아이디어", [], "요약1", make_version("2026-05-18", "내용1", []))
        upsert_item(wiki, "아이디어", [], "요약2", make_version("2026-05-25", "내용2", []))
        item = wiki["items"][0]
        assert len(item["versions"]) == 2
        assert item["versions"][0]["week"] == "2026-05-25"  # 최신이 앞

    def test_update_overwrites_summary(self):
        wiki = empty_wiki()
        upsert_item(wiki, "아이디어", [], "이전 요약", self._make_version())
        upsert_item(wiki, "아이디어", [], "새 요약", self._make_version())
        assert wiki["items"][0]["summary"] == "새 요약"

    def test_title_match_is_case_insensitive(self):
        wiki = empty_wiki()
        upsert_item(wiki, "AI 프로젝트", [], "요약", self._make_version())
        _, is_new, _ = upsert_item(wiki, "ai 프로젝트", [], "요약2", self._make_version())
        assert is_new is False

    def test_manual_tags_are_preserved_on_update(self):
        wiki = empty_wiki()
        upsert_item(wiki, "아이디어", ["수동태그"], "요약", self._make_version())
        upsert_item(wiki, "아이디어", ["AI자동태그"], "요약2", self._make_version())
        item = wiki["items"][0]
        assert "#수동태그" in item["tags"]
        assert "#AI자동태그" in item["tags"]

    def test_duplicate_tags_not_added(self):
        wiki = empty_wiki()
        upsert_item(wiki, "아이디어", ["태그A"], "요약", self._make_version())
        upsert_item(wiki, "아이디어", ["태그A", "태그B"], "요약2", self._make_version())
        item = wiki["items"][0]
        assert item["tags"].count("#태그A") == 1


# ── runner 테스트 (mock) ──────────────────────────────────────

class TestRunPipeline:
    def _fake_notes(self):
        return [
            {"id": "note1", "name": "아이디어1.txt", "content": "새 앱 아이디어", "tags": ["앱"], "modifiedTime": "2026-05-25T00:00:00Z"},
        ]

    def _fake_ai_items(self):
        return [
            {
                "title": "새 앱 아이디어",
                "tags": ["앱"],
                "summary": "앱 아이디어 요약",
                "content": "이번 주 업데이트 내용",
                "source_note_names": ["아이디어1.txt"],
            }
        ]

    @patch("src.pipeline.runner.find_file_in_folder", return_value=None)
    @patch("src.pipeline.runner.read_notes_from_folder")
    @patch("src.pipeline.runner.wikify_with_claude")
    @patch("src.pipeline.runner.upload_json", return_value="file_id_123")
    def test_success_flow(self, mock_upload, mock_claude, mock_read, mock_find):
        mock_read.return_value = self._fake_notes()
        mock_claude.return_value = self._fake_ai_items()

        from src.pipeline.runner import run_pipeline
        result = run_pipeline()

        assert result["status"] == "success"
        assert result["new_items"] == 1
        assert result["updated_items"] == 0
        assert result["api_used"] == "claude"

    @patch("src.pipeline.runner.find_file_in_folder", return_value=None)
    @patch("src.pipeline.runner.read_notes_from_folder")
    @patch("src.pipeline.runner.wikify_with_claude", side_effect=Exception("rate limit"))
    @patch("src.pipeline.runner.wikify_with_gemini")
    @patch("src.pipeline.runner.upload_json", return_value="file_id_123")
    def test_claude_failure_falls_back_to_gemini(self, mock_upload, mock_gemini, mock_claude, mock_read, mock_find):
        mock_read.return_value = self._fake_notes()
        mock_gemini.return_value = self._fake_ai_items()

        from src.pipeline.runner import run_pipeline
        result = run_pipeline()

        assert result["status"] == "success"
        assert result["api_used"] == "gemini"
        assert any("Claude 실패" in e for e in result["errors"])

    @patch("src.pipeline.runner.find_file_in_folder", return_value=None)
    @patch("src.pipeline.runner.read_notes_from_folder")
    @patch("src.pipeline.runner.wikify_with_claude", side_effect=Exception("rate limit"))
    @patch("src.pipeline.runner.wikify_with_gemini", side_effect=Exception("timeout"))
    def test_both_api_failure_returns_failure(self, mock_gemini, mock_claude, mock_read, mock_find):
        mock_read.return_value = self._fake_notes()

        from src.pipeline.runner import run_pipeline
        result = run_pipeline()

        assert result["status"] == "failure"
        assert result["api_used"] is None
        assert any("Claude 실패" in e for e in result["errors"])
        assert any("Gemini 실패" in e for e in result["errors"])

    @patch("src.pipeline.runner.find_file_in_folder", return_value=None)
    @patch("src.pipeline.runner.read_notes_from_folder")
    @patch("src.pipeline.runner.wikify_with_claude")
    @patch("src.pipeline.runner.upload_json", return_value="file_id_123")
    def test_no_new_notes_returns_success(self, mock_upload, mock_claude, mock_read, mock_find):
        mock_read.return_value = []  # 변경된 노트 없음

        from src.pipeline.runner import run_pipeline
        result = run_pipeline()

        assert result["status"] == "success"
        assert result["processed"] == 0
        mock_claude.assert_not_called()
