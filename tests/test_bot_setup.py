# ---------------------------------------------------------------------------
# run_setup tests
# All external I/O is mocked — no real Slack calls, files, or browser.
# ---------------------------------------------------------------------------

import datetime
import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_config():
    return {
        "METHOD": "cli",
        "TOP_N": 5,
        "MINUTES_BETWEEN_MESSAGES": 60,
        "POST_WEEKENDS": False,
        "SEND_GAME_UPDATES": True,
        "SEND_DAILY_SUMMARY": True,
        "TOURNAMENT_END_MEN": "2026-04-07",
        "TOURNAMENT_END_WOMEN": "2026-04-06",
        "SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/TEST",
        "SLACK_MANAGER_ID": "",
        "MANUAL_TOP": [],
        "POOLS": [{"SOURCE": "custom", "MEN_URL": "", "WOMEN_URL": ""}],
        "PLAYWRIGHT_HEADLESS": True,
        "PLAYWRIGHT_STATE": "playwright_state.json",
    }

_CONFIG_WITH_URLS = lambda: {
    **_base_config(),
    "POOLS": [{"SOURCE": "custom",
               "MEN_URL": "https://picks.cbssports.com/college-basketball/ncaa-tournament/bracket/pools/unittestpool1/standings",
               "WOMEN_URL": "https://picks.cbssports.com/college-basketball/ncaaw-tournament/bracket/pools/unittestpool2/standings"}],
}

# URLs that pass _is_placeholder_url (no test/placeholder slug patterns)
_REAL_MEN_URL   = "https://picks.cbssports.com/college-basketball/ncaa-tournament/bracket/pools/realmenspool/standings"
_REAL_WOMEN_URL = "https://picks.cbssports.com/college-basketball/ncaaw-tournament/bracket/pools/realwomenspool/standings"

def _config_with_urls(**overrides):
    """Config with unittestpool URLs (placeholder) + credentials."""
    c = {
        **_CONFIG_WITH_URLS(),
        "SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/REAL",
        "SLACK_MANAGER_ID": "U012ABC",
    }
    c.update(overrides)
    return c

def _config_with_real_urls(**overrides):
    """Config with non-placeholder URLs — lines 406/411 do NOT fire."""
    config = {
        **_base_config(),
        "METHOD": "cli",
        "SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/REAL",
        "SLACK_MANAGER_ID": "TEST_SUITE",
        "POOLS": [{"SOURCE": "custom",
                   "MEN_URL": _REAL_MEN_URL,
                   "WOMEN_URL": _REAL_WOMEN_URL}],
    }
    config.update(overrides)
    return config

# Sequences for _config_with_urls() — unittestpool slugs → _is_placeholder_url=True
# so lines 406+411 fire (men_url="", women_url="") → both empty → line 417 fires (manual="n")
# method, TOP_N, MINUTES, POST_WEEKENDS, GAME_UPDATES, DAILY_SUMMARY,
# men_url, women_url, manual(n), go-live, [had_problem if go-live=y]
_CLI_Y = ["cli", "5", "0", "n", "y", "y", "", "", "n", "y"]       # go-live = yes
_CLI_N = ["cli", "5", "0", "n", "y", "y", "", "", "n", "n", "n"]  # go-live = no

# Sequences for _config_with_real_urls() — URL prompts do NOT fire
# method, TOP_N, MINUTES, POST_WEEKENDS, GAME_UPDATES, DAILY_SUMMARY, go-live, had_problem
_REAL_CLI_Y = ["cli", "5", "0", "n", "y", "y", "y"]   # go-live = yes (no problem prompt on success)
_REAL_CLI_N = ["cli", "5", "0", "n", "y", "y", "n", "n"]  # go-live = no, had_problem = no

def _was_called_with_text(mock_calls, text):
    return any(
        c.kwargs.get("text") == text or (c.args[1:2] and c.args[1] == text)
        for c in mock_calls
    )


# ---------------------------------------------------------------------------
# _clean_url
# ---------------------------------------------------------------------------

def test_clean_url_plain():
    from bot_setup.bot_setup import _clean_url
    assert _clean_url("https://example.com") == "https://example.com"

def test_clean_url_slack_wrapped():
    from bot_setup.bot_setup import _clean_url
    assert _clean_url("<https://example.com>") == "https://example.com"

def test_clean_url_slack_with_label():
    from bot_setup.bot_setup import _clean_url
    assert _clean_url("<https://example.com|Click here>") == "https://example.com"

def test_clean_url_none_returns_none():
    from bot_setup.bot_setup import _clean_url
    assert _clean_url(None) is None

def test_clean_url_empty_string_returns_empty():
    from bot_setup.bot_setup import _clean_url
    assert _clean_url("") == ""

def test_clean_url_whitespace_stripped():
    from bot_setup.bot_setup import _clean_url
    assert _clean_url("  https://example.com  ") == "https://example.com"

def test_clean_url_pipe_without_angle_brackets():
    from bot_setup.bot_setup import _clean_url
    assert _clean_url("https://example.com/path|extra") == "https://example.com/path"

def test_clean_url_angle_brackets_no_pipe():
    from bot_setup.bot_setup import _clean_url
    assert _clean_url("<https://example.com/path>") == "https://example.com/path"

def test_clean_url_nested_pipe_in_label():
    from bot_setup.bot_setup import _clean_url
    assert _clean_url("<https://example.com|label|extra>") == "https://example.com"


# ---------------------------------------------------------------------------
# _tournament_end
# ---------------------------------------------------------------------------

def test_tournament_end_reads_from_config_men():
    from bot_setup.bot_setup import _tournament_end
    assert _tournament_end({"TOURNAMENT_END_MEN": "2027-04-05"}, "men's") == datetime.date(2027, 4, 5)

def test_tournament_end_reads_from_config_women():
    from bot_setup.bot_setup import _tournament_end
    assert _tournament_end({"TOURNAMENT_END_WOMEN": "2027-04-04"}, "women's") == datetime.date(2027, 4, 4)

def test_tournament_end_falls_back_to_default_men():
    from bot_setup.bot_setup import _tournament_end, _DEFAULT_TOURNAMENT_END_MEN
    assert _tournament_end({}, "men's") == _DEFAULT_TOURNAMENT_END_MEN

def test_tournament_end_falls_back_to_default_women():
    from bot_setup.bot_setup import _tournament_end, _DEFAULT_TOURNAMENT_END_WOMEN
    assert _tournament_end({}, "women's") == _DEFAULT_TOURNAMENT_END_WOMEN

def test_tournament_end_invalid_date_falls_back_to_default(capsys):
    from bot_setup.bot_setup import _tournament_end, _DEFAULT_TOURNAMENT_END_MEN
    result = _tournament_end({"TOURNAMENT_END_MEN": "not-a-date"}, "men's")
    assert result == _DEFAULT_TOURNAMENT_END_MEN
    assert "[WARN]" in capsys.readouterr().out

def test_tournament_end_defaults_differ():
    from bot_setup.bot_setup import _tournament_end
    assert _tournament_end({}, "men's") != _tournament_end({}, "women's")


# ---------------------------------------------------------------------------
# schedule / check / clear incomplete config reminder
# ---------------------------------------------------------------------------

def test_schedule_incomplete_config_reminder_writes_flag(tmp_path):
    from bot_setup.bot_setup import schedule_incomplete_config_reminder
    with patch("bot_setup.bot_setup.INCOMPLETE_CONFIG_FLAG", tmp_path / "incomplete_config.json"), \
         patch("bot_setup.bot_setup.next_weekday_morning", return_value=datetime.datetime(2026, 3, 16, 9, 0)):
        schedule_incomplete_config_reminder()
        data = json.loads((tmp_path / "incomplete_config.json").read_text())
        assert data["remind_at"] == "2026-03-16T09:00:00"

def test_check_incomplete_config_reminder_no_file_is_noop(tmp_path, capsys):
    from bot_setup.bot_setup import check_incomplete_config_reminder
    with patch("bot_setup.bot_setup.INCOMPLETE_CONFIG_FLAG", tmp_path / "missing.json"):
        check_incomplete_config_reminder()
    assert capsys.readouterr().out == ""

def test_check_incomplete_config_reminder_prints_when_overdue(tmp_path, capsys):
    from bot_setup.bot_setup import check_incomplete_config_reminder
    flag = tmp_path / "incomplete_config.json"
    past = (datetime.datetime.now() - datetime.timedelta(hours=1)).isoformat()
    flag.write_text(json.dumps({"remind_at": past}))
    with patch("bot_setup.bot_setup.INCOMPLETE_CONFIG_FLAG", flag), \
         patch("bot_setup.bot_setup.next_weekday_morning", return_value=datetime.datetime(2026, 3, 17, 9, 0)):
        check_incomplete_config_reminder()
    assert "REMINDER" in capsys.readouterr().out

def test_check_incomplete_config_reminder_silent_when_not_yet_due(tmp_path, capsys):
    from bot_setup.bot_setup import check_incomplete_config_reminder
    flag = tmp_path / "incomplete_config.json"
    future = (datetime.datetime.now() + datetime.timedelta(hours=2)).isoformat()
    flag.write_text(json.dumps({"remind_at": future}))
    with patch("bot_setup.bot_setup.INCOMPLETE_CONFIG_FLAG", flag):
        check_incomplete_config_reminder()
    assert capsys.readouterr().out == ""

def test_clear_incomplete_config_reminder_removes_file(tmp_path):
    from bot_setup.bot_setup import clear_incomplete_config_reminder
    flag = tmp_path / "incomplete_config.json"
    flag.write_text("{}")
    with patch("bot_setup.bot_setup.INCOMPLETE_CONFIG_FLAG", flag):
        clear_incomplete_config_reminder()
    assert not flag.exists()

def test_clear_incomplete_config_reminder_noop_if_missing(tmp_path):
    from bot_setup.bot_setup import clear_incomplete_config_reminder
    with patch("bot_setup.bot_setup.INCOMPLETE_CONFIG_FLAG", tmp_path / "missing.json"):
        clear_incomplete_config_reminder()


# ---------------------------------------------------------------------------
# run_setup — CLI path
# ---------------------------------------------------------------------------

@patch("bot_setup.bot_setup.save_json")
@patch("bot_setup.bot_setup.post_message")
@patch("bot_setup.bot_setup.build_yearly_intro_message", return_value="intro")
@patch("bot_setup.bot_setup.build_daily_summary", return_value=([{"type": "section", "text": {"type": "mrkdwn", "text": "s"}}], False))
@patch("bot_setup.bot_setup.deduplicate_top_users", side_effect=lambda x: x)
@patch("bot_setup.bot_setup.get_final_games", return_value=[])
@patch("bot_setup.bot_setup.load_flag", return_value={"LIVE_FOR_YEAR": False})
@patch("bot_setup.bot_setup.ask_if_missing", side_effect=lambda config, key, *a, **kw: config)
@patch("bot_setup.bot_setup.get_input_safe", side_effect=list(_CLI_N))
def test_run_setup_cli_no_urls_go_live(
    mock_input, mock_ask, mock_load_flag,
    mock_games, mock_dedup, mock_summary, mock_intro, mock_post, mock_save
):
    from bot_setup.bot_setup import run_setup
    config_in = _config_with_urls()
    config_in.pop("METHOD", None)
    result_config, method, *_ = run_setup(config_in)
    assert method == "cli"


@patch("bot_setup.bot_setup.save_json")
@patch("bot_setup.bot_setup.post_message")
@patch("bot_setup.bot_setup.build_yearly_intro_message", return_value="intro")
@patch("bot_setup.bot_setup.build_daily_summary", return_value=([{"type": "section", "text": {"type": "mrkdwn", "text": "s"}}], False))
@patch("bot_setup.bot_setup.deduplicate_top_users", side_effect=lambda x: x)
@patch("bot_setup.bot_setup._fetch_leaderboard", return_value=[])
@patch("bot_setup.bot_setup.get_final_games", return_value=[])
@patch("bot_setup.bot_setup.load_flag", return_value={"LIVE_FOR_YEAR": False})
@patch("bot_setup.bot_setup.ask_if_missing", side_effect=lambda config, key, *a, **kw: config)
@patch("bot_setup.bot_setup.get_input_safe", side_effect=list(_REAL_CLI_Y))
def test_run_setup_cli_with_urls_posts_on_go_live(
    mock_input, mock_ask, mock_load_flag, mock_games, mock_fetch,
    mock_dedup, mock_summary, mock_intro, mock_post, mock_save
):
    from bot_setup.bot_setup import run_setup
    config_in = _config_with_real_urls()
    config_in.pop("METHOD", None)
    result_config, method, *_ = run_setup(config_in)
    assert mock_post.called


@patch("bot_setup.bot_setup.save_json")
@patch("bot_setup.bot_setup.ask_if_missing", side_effect=lambda config, key, *a, **kw: config)
@patch("bot_setup.bot_setup.get_final_games", return_value=[])
@patch("bot_setup.bot_setup.build_daily_summary", return_value=([], False))
@patch("bot_setup.bot_setup.deduplicate_top_users", side_effect=lambda x: x)
@patch("bot_setup.bot_setup.load_flag", return_value={"LIVE_FOR_YEAR": False})
@patch("bot_setup.bot_setup.post_message")
@patch("bot_setup.bot_setup.build_yearly_intro_message", return_value="intro")
@patch("bot_setup.bot_setup.get_input_safe", side_effect=list(_CLI_N))
def test_run_setup_second_pools_guard_returns_six_tuple(
    mock_input, mock_intro, mock_post, mock_load_flag,
    mock_dedup, mock_summary, mock_games, mock_ask, mock_save
):
    from bot_setup.bot_setup import run_setup
    config_in = _config_with_urls()
    config_in["POOLS"] = [{"SOURCE": "custom", "MEN_URL": "", "WOMEN_URL": ""}]
    result = run_setup(config_in)
    assert isinstance(result, tuple)
    assert len(result) == 6


@patch("bot_setup.bot_setup.save_json")
@patch("bot_setup.bot_setup.post_message")
@patch("bot_setup.bot_setup.build_yearly_intro_message", return_value="intro")
@patch("bot_setup.bot_setup.build_daily_summary", return_value=([{"type": "section", "text": {"type": "mrkdwn", "text": "s"}}], False))
@patch("bot_setup.bot_setup.deduplicate_top_users", side_effect=lambda x: x)
@patch("bot_setup.bot_setup._fetch_leaderboard", return_value=[])
@patch("bot_setup.bot_setup.get_final_games", side_effect=[
    [{"id": "m1", "home": "A", "away": "B", "home_score": 70, "away_score": 65}],
    [{"id": "w1", "home": "C", "away": "D", "home_score": 80, "away_score": 75}],
])
@patch("bot_setup.bot_setup.load_flag", return_value={"LIVE_FOR_YEAR": False})
@patch("bot_setup.bot_setup.ask_if_missing", side_effect=lambda config, key, *a, **kw: config)
@patch("bot_setup.bot_setup.get_input_safe", side_effect=list(_REAL_CLI_Y))
def test_run_setup_writes_seen_file_with_game_ids(
    mock_input, mock_ask, mock_load_flag, mock_games, mock_fetch,
    mock_dedup, mock_summary, mock_intro, mock_post, mock_save
):
    from bot_setup.bot_setup import run_setup, SEEN_FILE
    saved = {}
    mock_save.side_effect = lambda path, data: saved.update({path: data})
    run_setup(_config_with_real_urls())
    assert SEEN_FILE in saved
    assert set(saved[SEEN_FILE]) >= {"m1", "w1"}


@patch("bot_setup.bot_setup.save_json")
@patch("bot_setup.bot_setup.post_message")
@patch("bot_setup.bot_setup.build_yearly_intro_message", return_value="intro")
@patch("bot_setup.bot_setup.build_daily_summary", return_value=([{"type": "section", "text": {"type": "mrkdwn", "text": "s"}}], True))
@patch("bot_setup.bot_setup.deduplicate_top_users", side_effect=lambda x: x)
@patch("bot_setup.bot_setup._fetch_leaderboard", return_value=[])
@patch("bot_setup.bot_setup.get_final_games", return_value=[])
@patch("bot_setup.bot_setup.load_flag", return_value={"LIVE_FOR_YEAR": False})
@patch("bot_setup.bot_setup.ask_if_missing", side_effect=lambda config, key, *a, **kw: config)
@patch("bot_setup.bot_setup.get_input_safe", side_effect=list(_REAL_CLI_Y))
def test_run_setup_off_day_skips_summary_post(
    mock_input, mock_ask, mock_load_flag, mock_games, mock_fetch,
    mock_dedup, mock_summary, mock_intro, mock_post, mock_save
):
    from bot_setup.bot_setup import run_setup
    run_setup(_config_with_real_urls())
    assert mock_post.called


@patch("bot_setup.bot_setup.save_json")
@patch("bot_setup.bot_setup.post_message")
@patch("bot_setup.bot_setup.build_yearly_intro_message", return_value="intro")
@patch("bot_setup.bot_setup.build_daily_summary", return_value=([{"type": "section", "text": {"type": "mrkdwn", "text": "s"}}], False))
@patch("bot_setup.bot_setup.deduplicate_top_users", side_effect=lambda x: x)
@patch("bot_setup.bot_setup._fetch_leaderboard", return_value=["Alice (100 pts)"])
@patch("bot_setup.bot_setup.get_final_games", return_value=[])
@patch("bot_setup.bot_setup.load_flag", return_value={"LIVE_FOR_YEAR": False})
@patch("bot_setup.bot_setup.ask_if_missing", side_effect=lambda config, key, *a, **kw: config)
@patch("bot_setup.bot_setup.get_input_safe", side_effect=list(_REAL_CLI_Y))
def test_run_setup_fetches_leaderboard_when_url_set(
    mock_input, mock_ask, mock_load_flag, mock_games, mock_fetch,
    mock_dedup, mock_summary, mock_intro, mock_post, mock_save
):
    from bot_setup.bot_setup import run_setup
    run_setup(_config_with_real_urls())
    assert mock_fetch.called


# ---------------------------------------------------------------------------
# _fetch_leaderboard
# Use URLs with real-looking pool slugs — _is_placeholder_url blocks
# slugs matching test/placeholder patterns like "unittestpool1".
# ---------------------------------------------------------------------------

def test_fetch_leaderboard_returns_results():
    from bot_setup.bot_setup import _fetch_leaderboard
    pool = {"MEN_URL": _REAL_MEN_URL}
    with patch("bot_setup.bot_setup.run_async", return_value=["Alice (100 pts)", "Bob (90 pts)"]), \
         patch("bot_setup.bot_setup.get_top_n_async", return_value=MagicMock()):
        result = _fetch_leaderboard(pool, "men", {"TOP_N": 5}, "cli")
    assert result == ["Alice (100 pts)", "Bob (90 pts)"]


def test_fetch_leaderboard_exception_returns_empty_in_cli_mode(capsys):
    from bot_setup.bot_setup import _fetch_leaderboard
    pool = {"MEN_URL": _REAL_MEN_URL}
    with patch("bot_setup.bot_setup.run_async", side_effect=Exception("scrape failed")), \
         patch("bot_setup.bot_setup.get_top_n_async", return_value=MagicMock()):
        result = _fetch_leaderboard(pool, "men", {}, "cli")
    assert result == []
    assert "[WARN]" in capsys.readouterr().out


def test_fetch_leaderboard_exception_asks_manual_in_slack_mode():
    from bot_setup.bot_setup import _fetch_leaderboard
    pool = {"MEN_URL": _REAL_MEN_URL}
    config = {"TOP_N": 3, "SLACK_MANAGER_ID": "U123"}
    with patch("bot_setup.bot_setup.run_async", side_effect=Exception("scrape failed")), \
         patch("bot_setup.bot_setup.get_top_n_async", return_value=MagicMock()), \
         patch("slack_bot.slack_dm.send_dm", return_value=("C123", "ts1")), \
         patch("slack_bot.slack_dm.ask_manual_top_users",
               return_value=["Manual User (50 pts)"]) as mock_manual:
        result = _fetch_leaderboard(pool, "men", config, "slack")
    mock_manual.assert_called_once_with("U123", "men's", 3)
    assert result == ["Manual User (50 pts)"]


def test_fetch_leaderboard_women_uses_women_url():
    from bot_setup.bot_setup import _fetch_leaderboard
    pool = {"WOMEN_URL": _REAL_WOMEN_URL}
    with patch("bot_setup.bot_setup.run_async", return_value=["Carol (95 pts)"]), \
         patch("bot_setup.bot_setup.get_top_n_async", return_value=MagicMock()):
        result = _fetch_leaderboard(pool, "women", {"TOP_N": 3}, "cli")
    assert result == ["Carol (95 pts)"]


# ---------------------------------------------------------------------------
# run_setup — edge cases
# ---------------------------------------------------------------------------

@patch("bot_setup.bot_setup.save_json")
@patch("bot_setup.bot_setup.post_message")
@patch("bot_setup.bot_setup.build_yearly_intro_message", return_value="intro")
@patch("bot_setup.bot_setup.build_daily_summary", return_value=([{"type": "section", "text": {"type": "mrkdwn", "text": "s"}}], False))
@patch("bot_setup.bot_setup.deduplicate_top_users", side_effect=lambda x: x)
@patch("bot_setup.bot_setup._fetch_leaderboard", return_value=[])
@patch("bot_setup.bot_setup.get_final_games", return_value=[])
@patch("bot_setup.bot_setup.load_flag", return_value={"LIVE_FOR_YEAR": False})
@patch("bot_setup.bot_setup.ask_if_missing", side_effect=lambda config, key, *a, **kw: config)
@patch("bot_setup.bot_setup.ask_slack_credentials_cli", side_effect=lambda c: c)
@patch("bot_setup.bot_setup.get_input_safe", side_effect=list(_REAL_CLI_Y))
def test_run_setup_no_webhook_returns_early_without_posting(
    mock_input, mock_creds, mock_ask, mock_load_flag,
    mock_games, mock_fetch, mock_dedup, mock_summary, mock_intro, mock_post, mock_save, capsys
):
    """Empty SLACK_WEBHOOK_URL triggers early return — nothing is posted."""
    from bot_setup.bot_setup import run_setup
    config_in = _config_with_real_urls()
    config_in["SLACK_WEBHOOK_URL"] = ""
    result = run_setup(config_in)
    assert isinstance(result, tuple) and len(result) == 6
    assert not mock_post.called
    assert "cannot go live" in capsys.readouterr().out


@patch("bot_setup.bot_setup.save_json")
@patch("bot_setup.bot_setup.post_message")
@patch("bot_setup.bot_setup.build_yearly_intro_message", return_value="intro")
@patch("bot_setup.bot_setup.build_daily_summary", return_value=([{"type": "section", "text": {"type": "mrkdwn", "text": "s"}}], False))
@patch("bot_setup.bot_setup.deduplicate_top_users", side_effect=lambda x: x)
@patch("bot_setup.bot_setup._fetch_leaderboard", return_value=[])
@patch("bot_setup.bot_setup.get_final_games", return_value=[])
@patch("bot_setup.bot_setup.load_flag", return_value={"LIVE_FOR_YEAR": False})
@patch("bot_setup.bot_setup.ask_if_missing", side_effect=lambda config, key, *a, **kw: config)
@patch("bot_setup.bot_setup.ask_slack_credentials_cli", side_effect=lambda c: c)
@patch("bot_setup.bot_setup.get_input_safe", side_effect=["slack", "5", "0", "n", "y", "y", "n", "n"])
def test_run_setup_slack_missing_creds_falls_back_to_cli(
    mock_input, mock_creds, mock_ask, mock_load_flag,
    mock_games, mock_fetch, mock_dedup, mock_summary, mock_intro, mock_post, mock_save, capsys
):
    from bot_setup.bot_setup import run_setup
    config_in = _config_with_real_urls()
    config_in.pop("SLACK_WEBHOOK_URL", None)
    config_in.pop("SLACK_MANAGER_ID", None)
    _, method, *_ = run_setup(config_in)
    assert method == "cli"
    assert "falling back to CLI" in capsys.readouterr().out