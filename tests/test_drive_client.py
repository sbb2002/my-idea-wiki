"""
Unit tests for drive.client — covers logic that doesn't require
a real Drive API connection.
"""
import pytest
from src.drive.client import extract_tags


class TestExtractTags:
    def test_single_tag(self):
        assert extract_tags("아이디어 #앱개발") == ["앱개발"]

    def test_multiple_tags(self):
        assert extract_tags("#AI #머신러닝 메모") == ["AI", "머신러닝"]

    def test_deduplication(self):
        assert extract_tags("#태그 #태그 #다른태그") == ["태그", "다른태그"]

    def test_no_tags(self):
        assert extract_tags("태그 없는 노트입니다.") == []

    def test_tags_mixed_in_text(self):
        content = "오늘 아이디어:\n- 새로운 앱 #앱개발\n- AI 활용 방안 #AI #머신러닝"
        assert extract_tags(content) == ["앱개발", "AI", "머신러닝"]

    def test_preserves_insertion_order(self):
        tags = extract_tags("#c #a #b")
        assert tags == ["c", "a", "b"]
