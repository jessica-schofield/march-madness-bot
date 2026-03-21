# ---------------------------------------------------------------------------
# run_setup tests
# All external I/O is mocked — no real Slack calls, files, or browser.
# ---------------------------------------------------------------------------

import datetime
import json
import pytest
from unittest.mock import patch, MagicMock, call
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_config():
    """Minimal valid config that skips all setup prompts."""
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


def _was_called_with_text(mock_calls, text):
    """Return True if any call passed `text` as positional arg 1 or as kwarg."""
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
    config = {"TOURNAMENT_END_MEN": "2027-04-05"}
    assert _tournament_end(config, "men's") == datetime.date(2027, 4, 5)

def test_tournament_end_reads_from_config_women():
    from bot_setup.bot_setup import _tournament_end
    config = {"TOURNAMENT_END_WOMEN": "2027-04-04"}
    assert _tournament_end(config, "women's") == datetime.date(2027, 4, 4)

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
    with patch("bot_setup.bot_setup.INCOMPLETE_CONFIG_FLAG", tmp_path / "incomplete_config.json"):
        with patch("bot_setup.bot_setup.next_weekday_morning", return_value=datetime.datetime(2026, 3, 16, 9, 0)):
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
    with patch("bot_setup.bot_setup.INCOMPLETE_CONFIG_FLAG", flag):
        with patch("bot_setup.bot_setup.next_weekday_morning", return_value=datetime.datetime(2026, 3, 17, 9, 0)):
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
        clear_incomplete_config_reminder()  # should not raise


# ---------------------------------------------------------------------------
# run_setup — CLI path, no bracket URLs, go-live declined ("cli" != "y")
# ---------------------------------------------------------------------------

@patch("bot_setup.bot_setup.save_json")
@patch("bot_setup.bot_setup.post_message")
@patch("bot_setup.bot_setup.build_yearly_intro_message", return_value="intro")
@patch("bot_setup.bot_setup.build_daily_summary", return_value=([{"type": "section", "text": {"type": "mrkdwn", "text": "s"}}], False))
@patch("bot_setup.bot_setup.deduplicate_top_users", side_effect=lambda x: x)
@patch("bot_setup.bot_setup.get_final_games", return_value=[])
@patch("bot_setup.bot_setup.load_flag", return_value={"LIVE_FOR_YEAR": False})
@patch("bot_setup.bot_setup.ask_if_missing", side_effect=lambda config, key, *a, **kw: config)
@patch("bot_setup.bot_setup.get_input_safe", return_value="cli")
def test_run_setup_cli_no_urls_go_live(
    mock_input, mock_ask_if_missing, mock_load_flag,
    mock_games, mock_dedup, mock_summary, mock_intro,
    mock_post, mock_save
):
    from bot_setup.bot_setup import run_setup
    config_in = _base_config()
    config_in.pop("METHOD", None)
    config_in["POOLS"] = [{"SOURCE": "custom", "MEN_URL": "https://men.example.com", "WOMEN_URL": "https://women.example.com"}]

    result_config, method, men, women, top_m, top_w = run_setup(config_in)

    assert method == "cli"
    assert not mock_post.called  # "cli" != "y" so go-live is skipped


# ---------------------------------------------------------------------------
# run_setup — CLI path, URLs set, go-live confirmed ("y")
# ---------------------------------------------------------------------------

@patch("bot_setup.bot_setup.save_json")
@patch("bot_setup.bot_setup.post_message")
@patch("bot_setup.bot_setup.build_yearly_intro_message", return_value="intro")
@patch("bot_setup.bot_setup.build_daily_summary", return_value=([{"type": "section", "text": {"type": "mrkdwn", "text": "s"}}], False))
@patch("bot_setup.bot_setup.deduplicate_top_users", side_effect=lambda x: x)
@patch("bot_setup.bot_setup.get_final_games", return_value=[])
@patch("bot_setup.bot_setup.load_flag", return_value={"LIVE_FOR_YEAR": False})
@patch("bot_setup.bot_setup.ask_if_missing", side_effect=lambda config, key, *a, **kw: config)
@patch("bot_setup.bot_setup.get_input_safe", return_value="y")
def test_run_setup_cli_with_urls_posts_on_go_live(
    mock_input, mock_ask_if_missing, mock_load_flag,
    mock_games, mock_dedup, mock_summary, mock_intro,
    mock_post, mock_save
):
    from bot_setup.bot_setup import run_setup
    config_in = _base_config()
    config_in.pop("METHOD", None)
    config_in["POOLS"] = [{"SOURCE": "custom", "MEN_URL": "https://men.example.com", "WOMEN_URL": "https://women.example.com"}]

    result_config, method, men, women, top_m, top_w = run_setup(config_in)

    assert method == "cli"
    assert mock_post.called


# ---------------------------------------------------------------------------
# run_setup — invalid method input falls back to CLI
# ---------------------------------------------------------------------------

@patch("bot_setup.bot_setup.save_json")
@patch("bot_setup.bot_setup.post_message")
@patch("bot_setup.bot_setup.build_yearly_intro_message", return_value="intro")
@patch("bot_setup.bot_setup.build_daily_summary", return_value=([{"type": "section", "text": {"type": "mrkdwn", "text": "s"}}], False))
@patch("bot_setup.bot_setup.deduplicate_top_users", side_effect=lambda x: x)
@patch("bot_setup.bot_setup.get_final_games", return_value=[])
@patch("bot_setup.bot_setup.load_flag", return_value={"LIVE_FOR_YEAR": False})
@patch("bot_setup.bot_setup.ask_if_missing", side_effect=lambda config, key, *a, **kw: config)
@patch("bot_setup.bot_setup.get_input_safe", side_effect=["garbage", "", "", "", "n"])
def test_run_setup_invalid_method_falls_back_to_cli(
    mock_input, mock_ask_if_missing, mock_load_flag,
    mock_games, mock_dedup, mock_summary, mock_intro,
    mock_post, mock_save, capsys
):
    from bot_setup.bot_setup import run_setup
    config_in = _base_config()
    result_config, method, *_ = run_setup(config_in)
    assert method == "cli"
    assert "[WARN]" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# run_setup — missing POOLS returns early
# ---------------------------------------------------------------------------

@patch("bot_setup.bot_setup.save_json")
@patch("bot_setup.bot_setup.ask_if_missing", side_effect=lambda config, key, *a, **kw: config)
@patch("bot_setup.bot_setup.get_input_safe", return_value="cli")
def test_run_setup_missing_pools_returns_early(mock_input, mock_ask, mock_save, capsys):
    from bot_setup.bot_setup import run_setup
    config_in = {"METHOD": "cli", "POOLS": []}

    with patch("bot_setup.bot_setup.get_final_games", return_value=[]):
        result = run_setup(config_in)

    assert "[ERROR]" in capsys.readouterr().out
    assert result is not None
    assert len(result) == 6
    _, _, men, women, top_m, top_w = result
    assert men == []
    assert women == []


# ---------------------------------------------------------------------------
# run_setup — games returned, seen file written on go-live
# ---------------------------------------------------------------------------

@patch("bot_setup.bot_setup.save_json")
@patch("bot_setup.bot_setup.post_message")
@patch("bot_setup.bot_setup.build_yearly_intro_message", return_value="intro")
@patch("bot_setup.bot_setup.build_daily_summary", return_value=([{"type": "section", "text": {"type": "mrkdwn", "text": "s"}}], False))
@patch("bot_setup.bot_setup.deduplicate_top_users", side_effect=lambda x: x)
@patch("bot_setup.bot_setup.get_final_games", side_effect=[
    [{"id": "m1", "home": "A", "away": "B", "home_score": 70, "away_score": 65}],
    [{"id": "w1", "home": "C", "away": "D", "home_score": 80, "away_score": 75}],
])
@patch("bot_setup.bot_setup.load_flag", return_value={"LIVE_FOR_YEAR": False})
@patch("bot_setup.bot_setup.ask_if_missing", side_effect=lambda config, key, *a, **kw: config)
@patch("bot_setup.bot_setup.get_input_safe", side_effect=["cli", "", "", "", "y"])
def test_run_setup_writes_seen_file_with_game_ids(
    mock_input, mock_ask, mock_load_flag,
    mock_games, mock_dedup, mock_summary, mock_intro,
    mock_post, mock_save
):
    from bot_setup.bot_setup import run_setup, SEEN_FILE
    config_in = _base_config()
    run_setup(config_in)

    seen_call = next(
        (c for c in mock_save.call_args_list if c.args[0] == SEEN_FILE), None
    )
    assert seen_call is not None
    seen_ids = set(seen_call.args[1])
    assert "m1" in seen_ids
    assert "w1" in seen_ids


# ---------------------------------------------------------------------------
# run_setup — off-day: no_games=True, summary block NOT posted
# ---------------------------------------------------------------------------

@patch("bot_setup.bot_setup.save_json")
@patch("bot_setup.bot_setup.post_message")
@patch("bot_setup.bot_setup.build_yearly_intro_message", return_value="intro")
@patch("bot_setup.bot_setup.build_daily_summary", return_value=([{"type": "section", "text": {"type": "mrkdwn", "text": "s"}}], True))
@patch("bot_setup.bot_setup.deduplicate_top_users", side_effect=lambda x: x)
@patch("bot_setup.bot_setup.get_final_games", return_value=[])
@patch("bot_setup.bot_setup.load_flag", return_value={"LIVE_FOR_YEAR": False})
@patch("bot_setup.bot_setup.ask_if_missing", side_effect=lambda config, key, *a, **kw: config)
@patch("bot_setup.bot_setup.get_input_safe", side_effect=["cli", "", "", "", "y"])
def test_run_setup_off_day_skips_summary_post(
    mock_input, mock_ask, mock_load_flag,
    mock_games, mock_dedup, mock_summary, mock_intro,
    mock_post, mock_save
):
    from bot_setup.bot_setup import run_setup
    config_in = _base_config()
    run_setup(config_in)

    calls = mock_post.call_args_list
    assert _was_called_with_text(calls, "intro"), "intro message should be posted"
    assert not any("blocks" in c.kwargs and c.kwargs["blocks"] for c in calls), \
        "summary blocks should NOT be posted on an off-day"


# ---------------------------------------------------------------------------
# run_setup — Slack method, DM setup times out → returns None config
# ---------------------------------------------------------------------------

@patch("bot_setup.bot_setup.schedule_incomplete_config_reminder")
@patch("bot_setup.bot_setup.save_json")
@patch("bot_setup.bot_setup.run_slack_dm_setup", return_value=None)
@patch("bot_setup.bot_setup.ask_slack_credentials_cli", side_effect=lambda c: {
    **c,
    "SLACK_WEBHOOK_URL": "https://hooks.slack.com/TEST",
    "SLACK_MANAGER_ID": "U123",
})
@patch("bot_setup.bot_setup.get_input_safe", return_value="slack")
def test_run_setup_slack_dm_timeout_returns_none_config(
    mock_input, mock_creds, mock_dm_setup, mock_save, mock_reminder
):
    from bot_setup.bot_setup import run_setup
    config_out, method, men, women, top_m, top_w = run_setup({})
    assert config_out is None
    assert men == []
    assert women == []
    mock_reminder.assert_called_once()


# ---------------------------------------------------------------------------
# run_setup — Slack method, missing credentials falls back to CLI
# ---------------------------------------------------------------------------

@patch("bot_setup.bot_setup.save_json")
@patch("bot_setup.bot_setup.post_message")
@patch("bot_setup.bot_setup.build_yearly_intro_message", return_value="intro")
@patch("bot_setup.bot_setup.build_daily_summary", return_value=([{"type": "section", "text": {"type": "mrkdwn", "text": "s"}}], False))
@patch("bot_setup.bot_setup.deduplicate_top_users", side_effect=lambda x: x)
@patch("bot_setup.bot_setup.get_final_games", return_value=[])
@patch("bot_setup.bot_setup.load_flag", return_value={"LIVE_FOR_YEAR": False})
@patch("bot_setup.bot_setup.ask_if_missing", side_effect=lambda config, key, *a, **kw: config)
@patch("bot_setup.bot_setup.ask_slack_credentials_cli", side_effect=lambda c: c)
@patch("bot_setup.bot_setup.get_input_safe", side_effect=["slack", "", "", "", "n"])
def test_run_setup_slack_missing_creds_falls_back_to_cli(
    mock_input, mock_creds, mock_ask, mock_load_flag,
    mock_games, mock_dedup, mock_summary, mock_intro,
    mock_post, mock_save, capsys
):
    from bot_setup.bot_setup import run_setup
    config_in = _base_config()
    config_in.pop("SLACK_WEBHOOK_URL", None)
    config_in.pop("SLACK_MANAGER_ID", None)

    _, method, *_ = run_setup(config_in)
    assert method == "cli"
    assert "[WARN]" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# run_setup — mock=True when no webhook set
# ---------------------------------------------------------------------------

@patch("bot_setup.bot_setup.save_json")
@patch("bot_setup.bot_setup.post_message")
@patch("bot_setup.bot_setup.build_yearly_intro_message", return_value="intro")
@patch("bot_setup.bot_setup.build_daily_summary", return_value=([{"type": "section", "text": {"type": "mrkdwn", "text": "s"}}], False))
@patch("bot_setup.bot_setup.deduplicate_top_users", side_effect=lambda x: x)
@patch("bot_setup.bot_setup.get_final_games", return_value=[])
@patch("bot_setup.bot_setup.load_flag", return_value={"LIVE_FOR_YEAR": False})
@patch("bot_setup.bot_setup.ask_if_missing", side_effect=lambda config, key, *a, **kw: config)
@patch("bot_setup.bot_setup.get_input_safe", side_effect=["cli", "", "", "", "y"])
def test_run_setup_posts_in_mock_mode_when_no_webhook(
    mock_input, mock_ask, mock_load_flag,
    mock_games, mock_dedup, mock_summary, mock_intro,
    mock_post, mock_save
):
    from bot_setup.bot_setup import run_setup
    config_in = _base_config()
    config_in["SLACK_WEBHOOK_URL"] = ""
    run_setup(config_in)

    for c in mock_post.call_args_list:
        assert c.kwargs.get("mock") is True or (len(c.args) > 2 and c.args[2] is True), \
            "post_message should be called with mock=True when no webhook is set"


# ---------------------------------------------------------------------------
# run_setup — second POOLS guard returns 6-tuple
# ---------------------------------------------------------------------------

@patch("bot_setup.bot_setup.save_json")
@patch("bot_setup.bot_setup.ask_if_missing", side_effect=lambda config, key, *a, **kw: config)
@patch("bot_setup.bot_setup.get_final_games", return_value=[])
@patch("bot_setup.bot_setup.build_daily_summary", return_value=([], False))
@patch("bot_setup.bot_setup.deduplicate_top_users", side_effect=lambda x: x)
@patch("bot_setup.bot_setup.load_flag", return_value={"LIVE_FOR_YEAR": False})
@patch("bot_setup.bot_setup.post_message")
@patch("bot_setup.bot_setup.build_yearly_intro_message", return_value="intro")
@patch("bot_setup.bot_setup.get_input_safe", side_effect=["cli", "", "", "", "n"])
def test_run_setup_second_pools_guard_returns_six_tuple(
    mock_input, mock_intro, mock_post, mock_load_flag,
    mock_dedup, mock_summary, mock_games, mock_ask, mock_save
):
    from bot_setup.bot_setup import run_setup
    config_in = _base_config()
    config_in["POOLS"] = [{"SOURCE": "custom", "MEN_URL": "", "WOMEN_URL": ""}]

    result = run_setup(config_in)
    assert result is not None
    assert len(result) == 6


# ---------------------------------------------------------------------------
# _fetch_leaderboard
# ---------------------------------------------------------------------------

@patch("bot_setup.bot_setup.run_async", return_value=["Alice (100 pts)", "Bob (90 pts)"])
@patch("bot_setup.bot_setup.get_top_n_async")
def test_fetch_leaderboard_returns_results(mock_get_top, mock_run_async):
    from bot_setup.bot_setup import _fetch_leaderboard
    result = _fetch_leaderboard({"MEN_URL": "https://example.com/standings"}, "men", {"TOP_N": 5}, "cli")
    assert result == ["Alice (100 pts)", "Bob (90 pts)"]

def test_fetch_leaderboard_no_url_returns_empty():
    from bot_setup.bot_setup import _fetch_leaderboard
    assert _fetch_leaderboard({"MEN_URL": ""}, "men", {}, "cli") == []

@patch("bot_setup.bot_setup.run_async", side_effect=Exception("scrape failed"))
@patch("bot_setup.bot_setup.get_top_n_async")
def test_fetch_leaderboard_exception_returns_empty_in_cli_mode(mock_get_top, mock_run_async, capsys):
    from bot_setup.bot_setup import _fetch_leaderboard
    result = _fetch_leaderboard({"MEN_URL": "https://example.com/standings"}, "men", {}, "cli")
    assert result == []
    assert "[WARN]" in capsys.readouterr().out

@patch("bot_setup.bot_setup.run_async", side_effect=Exception("scrape failed"))
@patch("bot_setup.bot_setup.get_top_n_async")
def test_fetch_leaderboard_exception_asks_manual_in_slack_mode(mock_get_top, mock_run_async):
    from bot_setup.bot_setup import _fetch_leaderboard
    pool = {"MEN_URL": "https://example.com/standings"}
    config = {"TOP_N": 3, "SLACK_MANAGER_ID": "U123"}

    # patch at source module level because _fetch_leaderboard imports slack_dm
    # lazily (deferred import inside the function body)
    with patch("slack_bot.slack_dm.send_dm", return_value=("C123", "ts1")):
        with patch("slack_bot.slack_dm.ask_manual_top_users", return_value=["Manual User (50 pts)"]) as mock_manual:
            result = _fetch_leaderboard(pool, "men", config, "slack")
            mock_manual.assert_called_once_with("U123", "men's", 3)
            assert result == ["Manual User (50 pts)"]

@patch("bot_setup.bot_setup.run_async", return_value=["Carol (95 pts)"])
@patch("bot_setup.bot_setup.get_top_n_async")
def test_fetch_leaderboard_women_uses_women_url(mock_get_top, mock_run_async):
    from bot_setup.bot_setup import _fetch_leaderboard
    result = _fetch_leaderboard({"WOMEN_URL": "https://example.com/women"}, "women", {"TOP_N": 3}, "cli")
    assert result == ["Carol (95 pts)"]

def test_fetch_leaderboard_women_no_url_returns_empty():
    from bot_setup.bot_setup import _fetch_leaderboard
    assert _fetch_leaderboard({"WOMEN_URL": ""}, "women", {}, "cli") == []

@patch("bot_setup.bot_setup.run_async", side_effect=Exception("fail"))
@patch("bot_setup.bot_setup.get_top_n_async")
def test_fetch_leaderboard_slack_mode_no_manager_id_returns_empty(mock_get_top, mock_run_async):
    from bot_setup.bot_setup import _fetch_leaderboard
    assert _fetch_leaderboard({"MEN_URL": "https://example.com/standings"}, "men", {}, "slack") == []


# ---------------------------------------------------------------------------
# run_setup — leaderboard fetched when MEN_URL is set
# ---------------------------------------------------------------------------

@patch("bot_setup.bot_setup.save_json")
@patch("bot_setup.bot_setup.post_message")
@patch("bot_setup.bot_setup.build_yearly_intro_message", return_value="intro")
@patch("bot_setup.bot_setup.build_daily_summary", return_value=([{"type": "section", "text": {"type": "mrkdwn", "text": "s"}}], False))
@patch("bot_setup.bot_setup.deduplicate_top_users", side_effect=lambda x: x)
@patch("bot_setup.bot_setup.get_final_games", return_value=[])
@patch("bot_setup.bot_setup.load_flag", return_value={"LIVE_FOR_YEAR": False})
@patch("bot_setup.bot_setup._fetch_leaderboard", return_value=["Alice (100 pts)"])
@patch("bot_setup.bot_setup.ask_if_missing", side_effect=lambda config, key, *a, **kw: config)
@patch("bot_setup.bot_setup.get_input_safe", return_value="y")
def test_run_setup_fetches_leaderboard_when_url_set(
    mock_input, mock_ask, mock_fetch, mock_load_flag,
    mock_games, mock_dedup, mock_summary, mock_intro,
    mock_post, mock_save, tmp_path
):
    from bot_setup.bot_setup import run_setup
    config_in = _base_config()
    config_in["POOLS"] = [{"SOURCE": "custom", "MEN_URL": "https://example.com", "WOMEN_URL": ""}]

    state = tmp_path / "playwright_state.json"
    state.write_text("x" * 600)

    with patch("bot_setup.bot_setup.PLAYWRIGHT_STATE", str(state)):
        result_config, method, men, women, top_m, top_w = run_setup(config_in)

    assert mock_fetch.called
    assert top_m == ["Alice (100 pts)"]