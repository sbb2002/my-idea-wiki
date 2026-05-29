"""
텔레그램 notifier 단위 테스트.
실제 HTTP 요청은 mock 처리한다.
"""
import pytest
from unittest.mock import patch, MagicMock

from src.telegram.notifier import notify_result


def _mock_send(monkeypatch, success=True):
    mock = MagicMock(return_value=success)
    monkeypatch.setattr("src.telegram.notifier.send_message", mock)
    return mock


class TestNotifyResult:
    def test_success_sends_message(self, monkeypatch):
        mock = _mock_send(monkeypatch)
        result = {
            "status": "success", "processed": 5,
            "new_items": 2, "updated_items": 3,
            "skipped": 0, "api_used": "claude", "errors": [],
        }
        notify_result(result)
        mock.assert_called_once()
        assert "✅" in mock.call_args[0][0]
        assert "신규: 2개" in mock.call_args[0][0]

    def test_partial_sends_warning(self, monkeypatch):
        mock = _mock_send(monkeypatch)
        result = {
            "status": "partial", "processed": 5,
            "new_items": 2, "updated_items": 1,
            "skipped": 2, "api_used": "gemini",
            "errors": ["아이템 처리 실패 (테스트): 오류"],
        }
        notify_result(result)
        mock.assert_called_once()
        assert "⚠️" in mock.call_args[0][0]

    def test_failure_sends_error(self, monkeypatch):
        mock = _mock_send(monkeypatch)
        result = {
            "status": "failure", "processed": 3,
            "new_items": 0, "updated_items": 0,
            "skipped": 3, "api_used": None,
            "errors": ["Claude 실패: rate limit", "Gemini 실패: timeout"],
        }
        notify_result(result)
        mock.assert_called_once()
        assert "❌" in mock.call_args[0][0]
        assert "Claude 실패" in mock.call_args[0][0]

    def test_no_notes_skips_notification(self, monkeypatch):
        mock = _mock_send(monkeypatch)
        result = {
            "status": "success", "processed": 0,
            "new_items": 0, "updated_items": 0,
            "skipped": 0, "api_used": None, "errors": [],
        }
        notify_result(result)
        mock.assert_not_called()

    def test_partial_error_list_capped_at_3(self, monkeypatch):
        mock = _mock_send(monkeypatch)
        result = {
            "status": "partial", "processed": 10,
            "new_items": 5, "updated_items": 0, "skipped": 5,
            "api_used": "claude",
            "errors": [f"오류 {i}" for i in range(10)],
        }
        notify_result(result)
        msg = mock.call_args[0][0]
        # 최대 3개만 표시되므로 "오류 3" 이상은 없어야 함
        assert "오류 0" in msg
        assert "오류 2" in msg
        assert "오류 3" not in msg
