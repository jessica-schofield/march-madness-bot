"""Tests for slack_bot/slack_dm.py — DM helpers and pending DM flag."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from slack_sdk.errors import SlackApiError


class TestGetDmClient:

    def test_raises_when_no_token(self):
        from slack_bot.slack_dm import get_dm_client
        with patch.dict("os.environ", {"SLACK_BOT_TOKEN": ""}, clear=False):
            with pytest.raises(ValueError, match="SLACK_BOT_TOKEN"):
                get_dm_client()

    def test_returns_client_when_token_set(self):
        from slack_bot.slack_dm import get_dm_client
        with patch.dict("os.environ", {"SLACK_BOT_TOKEN": "xoxb-fake"}, clear=False):
            from slack_sdk import WebClient
            client = get_dm_client()
            assert isinstance(client, WebClient)


class TestSendDm:

    def _mock_client(self, channel_id="C123", ts="1234.56"):
        client = MagicMock()
        client.conversations_open.return_value = {"channel": {"id": channel_id}}
        client.chat_postMessage.return_value = {"ts": ts}
        return client

    def test_returns_channel_and_ts(self):
        from slack_bot.slack_dm import send_dm
        client = self._mock_client("C999", "9999.0")
        with patch("slack_bot.slack_dm.get_dm_client", return_value=client), \
             patch("slack_bot.slack_dm._dm_channel_cache", {}):
            channel_id, ts = send_dm("U001", "hello")
        assert channel_id == "C999"
        assert ts == "9999.0"

    def test_returns_none_tuple_on_api_error(self):
        from slack_bot.slack_dm import send_dm
        client = self._mock_client()
        client.chat_postMessage.side_effect = SlackApiError("err", MagicMock())
        with patch("slack_bot.slack_dm.get_dm_client", return_value=client), \
             patch("slack_bot.slack_dm._dm_channel_cache", {}):
            result = send_dm("U001", "hello")
        assert result == (None, None)


class TestSavePendingDm:

    def test_saves_and_loads_pending_dm(self, tmp_path):
        from slack_bot import slack_dm
        flag_path = tmp_path / "pending_dm.json"
        with patch.object(slack_dm, "PENDING_DM_FLAG", flag_path), \
             patch("slack_bot.slack_dm.next_weekday_morning",
                   return_value=__import__("datetime").datetime(2099, 4, 1, 9, 0, 0)):
            slack_dm.save_pending_dm("U001", "What's the URL?", "default_val")
            result = slack_dm.check_pending_dm()
        # retry_at is in 2099 so it won't be "due" yet — returns None
        assert result is None

    def test_check_returns_data_when_due(self, tmp_path):
        from slack_bot import slack_dm
        import datetime
        flag_path = tmp_path / "pending_dm.json"
        flag_path.write_text(json.dumps({
            "retry_at": "2000-01-01T09:00:00",  # past — always due
            "user_id": "U001",
            "question": "What's your URL?",
            "default": None,
            "optional": False,
        }))
        with patch.object(slack_dm, "PENDING_DM_FLAG", flag_path):
            result = slack_dm.check_pending_dm()
        assert result is not None
        user_id, question, default, optional = result
        assert user_id == "U001"
        assert question == "What's your URL?"

    def test_returns_none_when_no_flag(self, tmp_path):
        from slack_bot import slack_dm
        flag_path = tmp_path / "nonexistent.json"
        with patch.object(slack_dm, "PENDING_DM_FLAG", flag_path):
            result = slack_dm.check_pending_dm()
        assert result is None

    def test_clear_pending_dm_removes_file(self, tmp_path):
        from slack_bot import slack_dm
        flag_path = tmp_path / "pending_dm.json"
        flag_path.write_text(json.dumps({"retry_at": "2099-01-01T09:00:00", "user_id": "U1", "question": "Q"}))
        with patch.object(slack_dm, "PENDING_DM_FLAG", flag_path):
            slack_dm.clear_pending_dm()
        assert not flag_path.exists()
