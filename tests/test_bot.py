"""
텔레그램 봇 핸들러 단위 테스트.

실제 텔레그램 API 호출 없이 명령어 라우팅과 상태 로직을 검증한다.
"""
import importlib
import sys
from unittest.mock import MagicMock, patch


def _reload_bot():
    """테스트 간 모듈 상태 초기화를 위해 bot 모듈을 리로드한다."""
    if "src.telegram.bot" in sys.modules:
        del sys.modules["src.telegram.bot"]
    import src.telegram.bot as bot
    return bot


class TestBotRouting:
    """명령어 라우팅 테스트."""

    def _make_update(self, text: str, chat_id: int = 42) -> dict:
        return {
            "message": {
                "chat": {"id": chat_id},
                "text": text,
            }
        }

    def test_run_command_sends_start_message(self):
        bot = _reload_bot()
        bot._cold_start_warned = True  # warm 상태로 설정

        with patch("src.telegram.bot._reply") as mock_reply, \
             patch("src.telegram.bot.threading.Thread") as mock_thread:
            mock_thread.return_value.start = MagicMock()
            bot.handle_update(self._make_update("/run"))
            assert mock_reply.called
            text = mock_reply.call_args[0][1]
            assert "위키화" in text

    def test_run_cold_start_sends_warning(self):
        bot = _reload_bot()
        bot._cold_start_warned = False  # 콜드 스타트 상태

        replies = []
        with patch("src.telegram.bot._reply", side_effect=lambda c, t: replies.append(t)), \
             patch("src.telegram.bot.threading.Thread") as mock_thread:
            mock_thread.return_value.start = MagicMock()
            bot.handle_update(self._make_update("/run"))

        # 첫 번째 메시지가 콜드 스타트 안내여야 함
        assert any("잠시만" in r or "서버를 깨우는" in r for r in replies)
        assert bot._cold_start_warned is True

    def test_status_no_history(self):
        bot = _reload_bot()
        bot._last_run_result = None

        with patch("src.telegram.bot._reply") as mock_reply:
            bot.handle_update(self._make_update("/status"))
            text = mock_reply.call_args[0][1]
            assert "기록" in text or "없" in text

    def test_status_with_history(self):
        bot = _reload_bot()
        bot._last_run_result = {
            "status": "success",
            "processed": 5,
            "new_items": 2,
            "updated_items": 3,
            "run_at": "2026-05-30T09:00:00+00:00",
        }
        bot._cold_start_warned = True

        with patch("src.telegram.bot._reply") as mock_reply:
            bot.handle_update(self._make_update("/status"))
            text = mock_reply.call_args[0][1]
            assert "success" in text or "✅" in text
            assert "5" in text  # processed

    def test_schedule_returns_cron(self):
        bot = _reload_bot()
        bot._schedule_cron = "0 9 * * 1"
        bot._cold_start_warned = True

        with patch("src.telegram.bot._reply") as mock_reply:
            bot.handle_update(self._make_update("/schedule"))
            text = mock_reply.call_args[0][1]
            assert "0 9 * * 1" in text

    def test_set_valid_cron(self):
        bot = _reload_bot()
        bot._cold_start_warned = True

        with patch("src.telegram.bot._reply") as mock_reply:
            bot.handle_update(self._make_update("/set 0 12 * * 5"))
            assert bot._schedule_cron == "0 12 * * 5"
            text = mock_reply.call_args[0][1]
            assert "✅" in text

    def test_set_invalid_cron(self):
        bot = _reload_bot()
        bot._cold_start_warned = True
        original = bot._schedule_cron

        with patch("src.telegram.bot._reply") as mock_reply:
            bot.handle_update(self._make_update("/set invalid"))
            # cron이 변경되지 않아야 함
            assert bot._schedule_cron == original
            text = mock_reply.call_args[0][1]
            assert "❗" in text or "5개" in text

    def test_set_empty_args(self):
        bot = _reload_bot()
        bot._cold_start_warned = True

        with patch("src.telegram.bot._reply") as mock_reply:
            bot.handle_update(self._make_update("/set"))
            text = mock_reply.call_args[0][1]
            assert "❗" in text or "사용법" in text

    def test_cancel_not_running(self):
        bot = _reload_bot()
        bot._pipeline_running = False
        bot._cold_start_warned = True

        with patch("src.telegram.bot._reply") as mock_reply:
            bot.handle_update(self._make_update("/cancel"))
            text = mock_reply.call_args[0][1]
            assert "없" in text or "ℹ️" in text

    def test_cancel_while_running(self):
        bot = _reload_bot()
        bot._pipeline_running = True
        bot._cold_start_warned = True

        with patch("src.telegram.bot._reply") as mock_reply:
            bot.handle_update(self._make_update("/cancel"))
            text = mock_reply.call_args[0][1]
            assert "진행 중" in text or "⚠️" in text
        bot._pipeline_running = False

    def test_unknown_command(self):
        bot = _reload_bot()
        bot._cold_start_warned = True

        with patch("src.telegram.bot._reply") as mock_reply:
            bot.handle_update(self._make_update("/unknown"))
            text = mock_reply.call_args[0][1]
            assert "명령어" in text

    def test_non_command_message_ignored(self):
        bot = _reload_bot()
        bot._cold_start_warned = True

        with patch("src.telegram.bot._reply") as mock_reply:
            bot.handle_update(self._make_update("안녕하세요"))
            mock_reply.assert_not_called()

    def test_update_without_message_ignored(self):
        bot = _reload_bot()
        bot._cold_start_warned = True

        with patch("src.telegram.bot._reply") as mock_reply:
            bot.handle_update({"callback_query": {}})
            mock_reply.assert_not_called()

    def test_bot_suffix_stripped(self):
        """그룹 채팅에서 /run@mybot 형태 처리."""
        bot = _reload_bot()
        bot._cold_start_warned = True

        with patch("src.telegram.bot._reply") as mock_reply, \
             patch("src.telegram.bot.threading.Thread") as mock_thread:
            mock_thread.return_value.start = MagicMock()
            bot.handle_update(self._make_update("/run@myideawikibot"))
            assert mock_reply.called


class TestWebhookEndpoint:
    """FastAPI /webhook 엔드포인트 테스트."""

    def test_webhook_returns_ok(self):
        from fastapi.testclient import TestClient
        # main 모듈을 직접 import하면 _mark_started()가 호출됨
        with patch("src.telegram.bot.handle_update"):
            from src.main import app
            client = TestClient(app)
            response = client.post(
                "/webhook",
                json={"message": {"chat": {"id": 1}, "text": "/status"}},
            )
            assert response.status_code == 200
            assert response.json() == {"ok": True}

    def test_webhook_invalid_json(self):
        from fastapi.testclient import TestClient
        with patch("src.telegram.bot.handle_update"):
            from src.main import app
            client = TestClient(app)
            response = client.post(
                "/webhook",
                content=b"not json",
                headers={"content-type": "application/json"},
            )
            assert response.status_code == 400

    def test_health_endpoint(self):
        from fastapi.testclient import TestClient
        from src.main import app
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_webhook_secret_valid(self, monkeypatch):
        import importlib
        monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "mysecret")

        # main 재로드
        if "src.main" in sys.modules:
            del sys.modules["src.main"]

        from fastapi.testclient import TestClient
        with patch("src.telegram.bot.handle_update"):
            import src.main as main_mod
            client = TestClient(main_mod.app)
            response = client.post(
                "/webhook",
                json={"update_id": 1},
                headers={"X-Telegram-Bot-Api-Secret-Token": "mysecret"},
            )
            assert response.status_code == 200

        monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)
        if "src.main" in sys.modules:
            del sys.modules["src.main"]

    def test_webhook_secret_invalid(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "mysecret")

        if "src.main" in sys.modules:
            del sys.modules["src.main"]

        from fastapi.testclient import TestClient
        with patch("src.telegram.bot.handle_update"):
            import src.main as main_mod
            client = TestClient(main_mod.app)
            response = client.post(
                "/webhook",
                json={"update_id": 1},
                headers={"X-Telegram-Bot-Api-Secret-Token": "wrongsecret"},
            )
            assert response.status_code == 403

        monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)
        if "src.main" in sys.modules:
            del sys.modules["src.main"]


class TestPersistPrdToWiki:
    """#59 — 텔레그램 PRD 생성 후 wiki.json item.prd 저장 검증."""

    def _make_wiki_json(self, item_id: str = "item_abc12345", prd=None, prd_history=None) -> str:
        import json
        return json.dumps({
            "schema_version": "1",
            "updated_at": "2026-06-01T00:00:00+00:00",
            "last_processed_at": None,
            "items": [{
                "id": item_id,
                "title": "테스트 아이템",
                "tags": ["#test"],
                "summary": "요약",
                "versions": [{"week": "2026-06-01", "content": "내용", "source_note_ids": [], "tokens": 0}],
                "related": [],
                "comments": [],
                "prd": prd,
                "prd_history": prd_history if prd_history is not None else [],
            }],
        }, ensure_ascii=False)

    def test_persist_sets_prd_field(self, monkeypatch):
        """생성된 PRD 텍스트가 item.prd에 저장되고 Drive에 업로드된다."""
        import json
        bot = _reload_bot()
        monkeypatch.setenv("DRIVE_WIKI_FOLDER_ID", "folder123")

        uploaded = {}

        def fake_upload(folder_id, filename, content, existing_file_id=None, **kw):
            uploaded["folder_id"] = folder_id
            uploaded["filename"] = filename
            uploaded["content"] = content
            uploaded["existing_file_id"] = existing_file_id
            return "file123"

        with patch("src.drive.client.find_file_in_folder", return_value="file123"), \
             patch("src.drive.client.read_note", return_value=self._make_wiki_json()), \
             patch("src.drive.client.upload_json", side_effect=fake_upload):
            bot._persist_prd_to_wiki("item_abc12345", "# 새 PRD 내용")

        assert uploaded["filename"] == "wiki.json"
        assert uploaded["existing_file_id"] == "file123"
        saved = json.loads(uploaded["content"])
        assert saved["items"][0]["prd"] == "# 새 PRD 내용"

    def test_persist_moves_existing_prd_to_history(self, monkeypatch):
        """기존 PRD가 있으면 prd_history 맨 앞으로 이관된다."""
        import json
        bot = _reload_bot()
        monkeypatch.setenv("DRIVE_WIKI_FOLDER_ID", "folder123")

        old_history = [{"date": "2026-05-01", "content": "# 아주 옛날 PRD"}]
        wiki_json = self._make_wiki_json(prd="# 기존 PRD", prd_history=old_history)
        uploaded = {}

        def fake_upload(folder_id, filename, content, existing_file_id=None, **kw):
            uploaded["content"] = content
            return "file123"

        with patch("src.drive.client.find_file_in_folder", return_value="file123"), \
             patch("src.drive.client.read_note", return_value=wiki_json), \
             patch("src.drive.client.upload_json", side_effect=fake_upload):
            bot._persist_prd_to_wiki("item_abc12345", "# 새 PRD")

        saved = json.loads(uploaded["content"])
        item = saved["items"][0]
        assert item["prd"] == "# 새 PRD"
        assert item["prd_history"][0]["content"] == "# 기존 PRD"
        assert item["prd_history"][1]["content"] == "# 아주 옛날 PRD"

    def test_persist_raises_when_wiki_missing(self, monkeypatch):
        """wiki.json이 없으면 예외를 올린다 (호출부에서 경고 처리)."""
        import pytest
        bot = _reload_bot()
        monkeypatch.setenv("DRIVE_WIKI_FOLDER_ID", "folder123")

        with patch("src.drive.client.find_file_in_folder", return_value=None):
            with pytest.raises(RuntimeError):
                bot._persist_prd_to_wiki("item_abc12345", "# PRD")

    def test_persist_raises_when_item_missing(self, monkeypatch):
        """item_id가 wiki.json에 없으면 예외를 올린다."""
        import pytest
        bot = _reload_bot()
        monkeypatch.setenv("DRIVE_WIKI_FOLDER_ID", "folder123")

        with patch("src.drive.client.find_file_in_folder", return_value="file123"), \
             patch("src.drive.client.read_note", return_value=self._make_wiki_json("item_other")):
            with pytest.raises(RuntimeError):
                bot._persist_prd_to_wiki("item_abc12345", "# PRD")
