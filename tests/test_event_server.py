"""Tests for slack_bot/event_server.py — Flask event handler routes."""
import json
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def client():
    from slack_bot.event_server import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _make_client_mock():
    mock = MagicMock()
    mock.conversations_open.return_value = {"channel": {"id": "C123"}}
    return mock


class TestUrlVerification:

    def test_challenge_returned(self, client):
        payload = {"type": "url_verification", "challenge": "abc123"}
        resp = client.post(
            "/slack/events",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.get_json()["challenge"] == "abc123"


class TestMemberJoinedEvent:

    def test_member_joined_triggers_dm(self, client):
        payload = {
            "event": {"type": "member_joined_channel", "user": "U001"},
        }
        with patch("slack_bot.event_server._get_client", return_value=_make_client_mock()), \
             patch("slack_bot.event_server._load_pools", return_value={}), \
             patch("slack_bot.event_server._save_pools"):
            resp = client.post(
                "/slack/events",
                data=json.dumps(payload),
                content_type="application/json",
            )
        assert resp.status_code == 200
        assert resp.get_json() == {"ok": True}


class TestDmReplyEvent:

    def test_bracket_url_saved(self, client):
        pools = {}
        saved = {}

        def fake_save(p):
            saved.update(p)

        payload = {
            "event": {
                "type": "message",
                "channel_type": "im",
                "user": "U001",
                "text": "https://picks.cbssports.com/brackets/abc",
            }
        }
        with patch("slack_bot.event_server._get_client", return_value=_make_client_mock()), \
             patch("slack_bot.event_server._load_pools", return_value=pools), \
             patch("slack_bot.event_server._save_pools", side_effect=fake_save):
            resp = client.post(
                "/slack/events",
                data=json.dumps(payload),
                content_type="application/json",
            )
        assert resp.status_code == 200
        assert "U001" in saved

    def test_missing_token_returns_500(self, client):
        payload = {"event": {"type": "member_joined_channel", "user": "U001"}}
        with patch("slack_bot.event_server._get_client", side_effect=ValueError("no token")), \
             patch("slack_bot.event_server._load_pools", return_value={}):
            resp = client.post(
                "/slack/events",
                data=json.dumps(payload),
                content_type="application/json",
            )
        assert resp.status_code == 500
