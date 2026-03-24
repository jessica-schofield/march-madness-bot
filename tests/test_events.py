"""Tests for slack_bot/events.py — member join and DM reply handling."""
import pytest
from unittest.mock import MagicMock, call
from slack_sdk.errors import SlackApiError

from slack_bot.events import (
    _looks_like_bracket_url,
    handle_member_joined,
    handle_dm_reply,
    CONFIRMATION_MESSAGE,
    DECLINE_MESSAGE,
    UNRECOGNISED_MESSAGE,
    WELCOME_MESSAGE,
)


def _fake_client(channel_id="C123"):
    client = MagicMock()
    client.conversations_open.return_value = {"channel": {"id": channel_id}}
    return client


class TestLooksLikeBracketUrl:

    def test_cbssports_url_returns_true(self):
        assert _looks_like_bracket_url("https://picks.cbssports.com/brackets/123") is True

    def test_espn_url_returns_true(self):
        assert _looks_like_bracket_url("https://fantasy.espn.com/tournament-challenge-bracket/2026") is True

    def test_yahoo_url_returns_true(self):
        assert _looks_like_bracket_url("https://yahoo.com/sports/brackets") is True

    def test_random_text_returns_false(self):
        assert _looks_like_bracket_url("sure no problem") is False

    def test_empty_string_returns_false(self):
        assert _looks_like_bracket_url("") is False


class TestHandleMemberJoined:

    def test_sends_welcome_dm(self):
        client = _fake_client()
        handle_member_joined({"user": "U001"}, client, {}, lambda p: None)
        client.chat_postMessage.assert_called_once()
        args = client.chat_postMessage.call_args
        assert args.kwargs.get("text") == WELCOME_MESSAGE or args[1].get("text") == WELCOME_MESSAGE

    def test_no_user_id_does_nothing(self):
        client = _fake_client()
        handle_member_joined({}, client, {}, lambda p: None)
        client.chat_postMessage.assert_not_called()

    def test_slack_api_error_does_not_raise(self):
        client = _fake_client()
        client.conversations_open.side_effect = SlackApiError("err", MagicMock())
        handle_member_joined({"user": "U001"}, client, {}, lambda p: None)  # must not raise


class TestHandleDmReply:

    def test_bracket_url_saved_to_pools(self):
        client = _fake_client()
        pools = {}
        saved = {}

        def save_fn(p):
            saved.update(p)

        event = {"user": "U001", "text": "https://picks.cbssports.com/brackets/abc"}
        handle_dm_reply(event, client, pools, save_fn)
        assert "U001" in saved
        assert "cbssports.com" in saved["U001"]

    def test_bracket_url_sends_confirmation(self):
        client = _fake_client()
        event = {"user": "U001", "text": "https://picks.cbssports.com/brackets/abc"}
        handle_dm_reply(event, client, {}, lambda p: None)
        texts = [c.kwargs.get("text") or c[1].get("text") for c in client.chat_postMessage.call_args_list]
        assert CONFIRMATION_MESSAGE in texts

    def test_no_thanks_sends_decline(self):
        client = _fake_client()
        event = {"user": "U001", "text": "no thanks"}
        handle_dm_reply(event, client, {}, lambda p: None)
        texts = [c.kwargs.get("text") or c[1].get("text") for c in client.chat_postMessage.call_args_list]
        assert DECLINE_MESSAGE in texts

    def test_unrecognised_reply_sends_fallback(self):
        client = _fake_client()
        event = {"user": "U001", "text": "huh what"}
        handle_dm_reply(event, client, {}, lambda p: None)
        texts = [c.kwargs.get("text") or c[1].get("text") for c in client.chat_postMessage.call_args_list]
        assert UNRECOGNISED_MESSAGE in texts

    def test_bot_message_ignored(self):
        client = _fake_client()
        event = {"user": "U001", "bot_id": "B001", "text": "no thanks"}
        handle_dm_reply(event, client, {}, lambda p: None)
        client.chat_postMessage.assert_not_called()

    def test_slack_api_error_on_decline_does_not_raise(self):
        client = _fake_client()
        client.conversations_open.side_effect = SlackApiError("err", MagicMock())
        event = {"user": "U001", "text": "no"}
        handle_dm_reply(event, client, {}, lambda p: None)  # must not raise
