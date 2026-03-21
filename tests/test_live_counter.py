import pytest
import json
from unittest.mock import patch, MagicMock
from io import BytesIO


# ---------------------------------------------------------------------------
# Unit tests for _ping_live_counter
# ---------------------------------------------------------------------------

def _make_response(data: dict, status: int = 200):
    """Helper — fake urllib response."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(data).encode()
    mock_resp.status = status
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def test_ping_live_counter_no_url_is_noop():
    """If LIVE_COUNTER_URL is not set, function returns immediately."""
    from bot_setup.bot_setup import _ping_live_counter
    with patch("urllib.request.urlopen") as mock_open:
        _ping_live_counter({"LIVE_COUNTER_URL": ""})
    mock_open.assert_not_called()


def test_ping_live_counter_success(capsys):
    """Successful ping prints live bot count."""
    from bot_setup.bot_setup import _ping_live_counter
    response_data = {"total": 42, "thisYear": 7, "year": 2026}

    with patch("urllib.request.urlopen", return_value=_make_response(response_data)):
        _ping_live_counter({
            "LIVE_COUNTER_URL": "https://script.google.com/fake",
            "VERSION": "1.0.0",
        })

    out = capsys.readouterr().out
    assert "7" in out
    assert "42" in out


def test_ping_live_counter_network_error_is_silent():
    """Network failure never raises — always fails silently."""
    from bot_setup.bot_setup import _ping_live_counter

    with patch("urllib.request.urlopen", side_effect=OSError("network down")):
        _ping_live_counter({
            "LIVE_COUNTER_URL": "https://script.google.com/fake",
            "VERSION": "1.0.0",
        })


def test_ping_live_counter_timeout_is_silent():
    """Timeout never raises — always fails silently."""
    from bot_setup.bot_setup import _ping_live_counter
    import urllib.error

    with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
        _ping_live_counter({
            "LIVE_COUNTER_URL": "https://script.google.com/fake",
            "VERSION": "1.0.0",
        })


def test_ping_live_counter_bad_json_is_silent():
    """Malformed JSON response never raises."""
    from bot_setup.bot_setup import _ping_live_counter

    mock_resp = MagicMock()
    mock_resp.read.return_value = b"not valid json {{{"
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        _ping_live_counter({
            "LIVE_COUNTER_URL": "https://script.google.com/fake",
            "VERSION": "1.0.0",
        })


def test_ping_live_counter_includes_year_and_version_in_url():
    """URL sent to counter includes year and version params."""
    from bot_setup.bot_setup import _ping_live_counter
    import datetime

    year = datetime.datetime.now().year
    response_data = {"total": 1, "thisYear": 1, "year": year}
    captured_urls = []

    def fake_urlopen(url, timeout=None):
        captured_urls.append(url)
        return _make_response(response_data)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        _ping_live_counter({
            "LIVE_COUNTER_URL": "https://script.google.com/fake",
            "VERSION": "2.0.0",
        })

    assert len(captured_urls) == 1
    assert f"year={year}" in captured_urls[0]
    assert "version=2.0.0" in captured_urls[0]


# ---------------------------------------------------------------------------
# Integration tests — go-live path calls _ping_live_counter
# ---------------------------------------------------------------------------

def _live_counter_config():
    return {
        "METHOD": "cli",
        "TOP_N": 5,
        "MINUTES_BETWEEN_MESSAGES": 30,
        "POST_WEEKENDS": False,
        "SEND_GAME_UPDATES": True,
        "SEND_DAILY_SUMMARY": True,
        "SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/TEST",
        "SLACK_MANAGER_ID": "",
        "MANUAL_TOP": ["Alice (100)", "Bob (90)", "Carol (80)"],
        "LIVE_COUNTER_URL": "https://script.google.com/fake",
        "POOLS": [{"SOURCE": "custom",
                   "MEN_URL": "https://picks.cbssports.com/college-basketball/ncaa-tournament/bracket/pools/unittestpool1/standings",
                   "WOMEN_URL": "https://picks.cbssports.com/college-basketball/ncaaw-tournament/bracket/pools/unittestpool2/standings"}],
        "PLAYWRIGHT_HEADLESS": True,
        "PLAYWRIGHT_STATE": "playwright_state.json",
        "TOURNAMENT_END_MEN": "2026-04-07",
        "TOURNAMENT_END_WOMEN": "2026-04-06",
    }


@pytest.mark.integration
def test_go_live_calls_ping_counter():
    """When go_live=True, _ping_live_counter is called once."""
    from bot_setup.bot_setup import run_setup

    with patch("bot_setup.bot_setup.get_input_safe", side_effect=["cli", "yes"]), \
            patch("bot_setup.bot_setup._fetch_leaderboard", return_value=[]), \
            patch("bot_setup.bot_setup.get_final_games", return_value=[]), \
            patch("bot_setup.bot_setup.ask_if_missing", side_effect=lambda c, k, *a, **kw: c), \
            patch("bot_setup.bot_setup.load_flag", return_value={"LIVE_FOR_YEAR": False}), \
            patch("bot_setup.bot_setup.deduplicate_top_users", side_effect=lambda x: x), \
            patch("bot_setup.bot_setup.build_daily_summary", return_value=([{"type": "section"}], False)), \
            patch("bot_setup.bot_setup.build_yearly_intro_message", return_value="intro"), \
            patch("bot_setup.bot_setup.post_message"), \
            patch("bot_setup.bot_setup._ping_live_counter") as mock_ping, \
            patch("bot_setup.config.save_json"):
        run_setup(_live_counter_config())

    mock_ping.assert_called_once()


@pytest.mark.integration
def test_go_live_skipped_does_not_call_ping_counter():
    """When go_live=False, _ping_live_counter is never called."""
    from bot_setup.bot_setup import run_setup

    with patch("bot_setup.bot_setup.get_input_safe", side_effect=["cli", "n"]), \
            patch("bot_setup.bot_setup._fetch_leaderboard", return_value=[]), \
            patch("bot_setup.bot_setup.get_final_games", return_value=[]), \
            patch("bot_setup.bot_setup.ask_if_missing", side_effect=lambda c, k, *a, **kw: c), \
            patch("bot_setup.bot_setup.load_flag", return_value={"LIVE_FOR_YEAR": False}), \
            patch("bot_setup.bot_setup.deduplicate_top_users", side_effect=lambda x: x), \
            patch("bot_setup.bot_setup.build_daily_summary", return_value=([{"type": "section"}], False)), \
            patch("bot_setup.bot_setup.build_yearly_intro_message", return_value="intro"), \
            patch("bot_setup.bot_setup.post_message"), \
            patch("bot_setup.bot_setup._ping_live_counter") as mock_ping, \
            patch("bot_setup.config.save_json"):
        run_setup(_live_counter_config())

    mock_ping.assert_not_called()
