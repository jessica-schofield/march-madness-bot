# ---------------------------------------------------------------------------
# slack_utils.py tests
# All HTTP calls are mocked — no real Slack requests made.
# ---------------------------------------------------------------------------

import datetime
import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _config(webhook="https://hooks.slack.com/services/TEST", post_weekends=True):
    return {
        "SLACK_WEBHOOK_URL": webhook,
        "POST_WEEKENDS": post_weekends,
    }


def _mock_resp(text="ok", status=200, json_data=None):
    resp = MagicMock()
    resp.text = text
    resp.status_code = status
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value=json_data or {"ok": True})
    return resp


# ---------------------------------------------------------------------------
# Weekend gating
# ---------------------------------------------------------------------------

@patch("slack_utils.datetime")
def test_post_message_skips_on_saturday_when_weekends_disabled(mock_dt):
    mock_dt.datetime.now.return_value = datetime.datetime(2026, 3, 21)  # Saturday
    from slack_utils import post_message
    result = post_message(_config(post_weekends=False), text="hello")
    assert result == {}


@patch("slack_utils.datetime")
def test_post_message_skips_on_sunday_when_weekends_disabled(mock_dt):
    mock_dt.datetime.now.return_value = datetime.datetime(2026, 3, 22)  # Sunday
    from slack_utils import post_message
    result = post_message(_config(post_weekends=False), text="hello")
    assert result == {}


@patch("slack_utils.datetime")
def test_post_message_posts_on_weekend_when_enabled(mock_dt):
    mock_dt.datetime.now.return_value = datetime.datetime(2026, 3, 21)  # Saturday
    from slack_utils import post_message
    with patch("requests.post", return_value=_mock_resp()) as mock_post:
        post_message(_config(post_weekends=True), text="hello")
        mock_post.assert_called_once()


@patch("slack_utils.datetime")
def test_post_message_skips_returns_empty_dict_not_none(mock_dt):
    mock_dt.datetime.now.return_value = datetime.datetime(2026, 3, 21)  # Saturday
    from slack_utils import post_message
    result = post_message(_config(post_weekends=False), text="hello")
    assert result is not None
    assert result == {}


# ---------------------------------------------------------------------------
# mock mode
# ---------------------------------------------------------------------------

@patch("slack_utils.datetime")
def test_post_message_mock_mode_does_not_call_requests(mock_dt, capsys):
    mock_dt.datetime.now.return_value = datetime.datetime(2026, 3, 23)  # Monday
    from slack_utils import post_message
    with patch("requests.post") as mock_req:
        result = post_message(_config(), text="hello", mock=True)
        mock_req.assert_not_called()
    assert result == {}
    assert "[MOCK]" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# missing webhook / empty payload guards
# ---------------------------------------------------------------------------

@patch("slack_utils.datetime")
def test_post_message_no_webhook_returns_empty(mock_dt, capsys):
    mock_dt.datetime.now.return_value = datetime.datetime(2026, 3, 23)
    from slack_utils import post_message
    result = post_message(_config(webhook=""), text="hello")
    assert result == {}
    assert "[WARN]" in capsys.readouterr().out


@patch("slack_utils.datetime")
def test_post_message_no_text_or_blocks_skips_request(mock_dt, capsys):
    mock_dt.datetime.now.return_value = datetime.datetime(2026, 3, 23)
    from slack_utils import post_message
    with patch("requests.post") as mock_req:
        result = post_message(_config())
        mock_req.assert_not_called()
    assert result == {}
    assert "[WARN]" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# successful post
# ---------------------------------------------------------------------------

@patch("slack_utils.datetime")
def test_post_message_text_ok_response(mock_dt):
    mock_dt.datetime.now.return_value = datetime.datetime(2026, 3, 23)
    from slack_utils import post_message
    with patch("requests.post", return_value=_mock_resp(text="ok")):
        result = post_message(_config(), text="hello")
    assert result == {"ok": True}


@patch("slack_utils.datetime")
def test_post_message_json_response(mock_dt):
    mock_dt.datetime.now.return_value = datetime.datetime(2026, 3, 23)
    from slack_utils import post_message
    with patch("requests.post", return_value=_mock_resp(text='{"ok": true}', json_data={"ok": True})):
        result = post_message(_config(), text="hello")
    assert result.get("ok") is True


@patch("slack_utils.datetime")
def test_post_message_sends_text_payload(mock_dt):
    mock_dt.datetime.now.return_value = datetime.datetime(2026, 3, 23)
    from slack_utils import post_message
    with patch("requests.post", return_value=_mock_resp()) as mock_req:
        post_message(_config(), text="go team")
    payload = mock_req.call_args.kwargs["json"]
    assert payload["text"] == "go team"


@patch("slack_utils.datetime")
def test_post_message_sends_blocks_payload(mock_dt):
    mock_dt.datetime.now.return_value = datetime.datetime(2026, 3, 23)
    from slack_utils import post_message
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "hi"}}]
    with patch("requests.post", return_value=_mock_resp()) as mock_req:
        post_message(_config(), blocks=blocks)
    payload = mock_req.call_args.kwargs["json"]
    assert payload["blocks"] == blocks


@patch("slack_utils.datetime")
def test_post_message_sends_both_text_and_blocks(mock_dt):
    mock_dt.datetime.now.return_value = datetime.datetime(2026, 3, 23)
    from slack_utils import post_message
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "hi"}}]
    with patch("requests.post", return_value=_mock_resp()) as mock_req:
        post_message(_config(), text="fallback", blocks=blocks)
    payload = mock_req.call_args.kwargs["json"]
    assert "text" in payload
    assert "blocks" in payload


# ---------------------------------------------------------------------------
# plain-text error response (e.g. "invalid_payload")
# ---------------------------------------------------------------------------

@patch("slack_utils.datetime")
def test_post_message_plain_text_error_response(mock_dt, capsys):
    mock_dt.datetime.now.return_value = datetime.datetime(2026, 3, 23)
    from slack_utils import post_message
    resp = _mock_resp(text="invalid_payload")
    resp.json.side_effect = ValueError("not json")
    with patch("requests.post", return_value=resp):
        result = post_message(_config(), text="hello")
    assert result == {"ok": False, "error": "invalid_payload"}
    assert "[WARN]" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# retry on ConnectionError
# ---------------------------------------------------------------------------

@patch("slack_utils.datetime")
def test_post_message_retries_on_connection_error(mock_dt, capsys):
    mock_dt.datetime.now.return_value = datetime.datetime(2026, 3, 23)
    import requests as req_lib
    from slack_utils import post_message

    with patch("requests.post", side_effect=[
        req_lib.exceptions.ConnectionError("timeout"),
        _mock_resp(),
    ]) as mock_req:
        result = post_message(_config(), text="hello")

    assert mock_req.call_count == 2
    assert result == {"ok": True}
    assert "[WARN]" in capsys.readouterr().out


@patch("slack_utils.datetime")
def test_post_message_fails_after_two_connection_errors(mock_dt, capsys):
    mock_dt.datetime.now.return_value = datetime.datetime(2026, 3, 23)
    import requests as req_lib
    from slack_utils import post_message

    with patch("requests.post", side_effect=[
        req_lib.exceptions.ConnectionError("timeout"),
        req_lib.exceptions.ConnectionError("timeout again"),
    ]) as mock_req:
        result = post_message(_config(), text="hello")

    assert mock_req.call_count == 2
    assert result == {}
    assert "[ERROR]" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# non-connection exceptions (no retry)
# ---------------------------------------------------------------------------

@patch("slack_utils.datetime")
def test_post_message_generic_exception_no_retry(mock_dt, capsys):
    mock_dt.datetime.now.return_value = datetime.datetime(2026, 3, 23)
    from slack_utils import post_message

    with patch("requests.post", side_effect=Exception("something unexpected")) as mock_req:
        result = post_message(_config(), text="hello")

    assert mock_req.call_count == 1
    assert result == {}
    assert "[ERROR]" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# timeout kwarg passed to requests.post
# ---------------------------------------------------------------------------

@patch("slack_utils.datetime")
def test_post_message_passes_timeout(mock_dt):
    mock_dt.datetime.now.return_value = datetime.datetime(2026, 3, 23)
    from slack_utils import post_message
    with patch("requests.post", return_value=_mock_resp()) as mock_req:
        post_message(_config(), text="hello")
    assert mock_req.call_args.kwargs.get("timeout") == 10
