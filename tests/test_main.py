import sys
import os
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from main import run


LIVE_CONFIG = {
    "SLACK_WEBHOOK_URL": "https://hooks.slack.com/test",
    "SLACK_MANAGER_ID": "",
    "TOP_N": 5,
    "SEND_DAILY_SUMMARY": True,
    "POOLS": [{"MEN_URL": "", "WOMEN_URL": ""}],
}
LIVE_FLAG = {"LIVE_FOR_YEAR": True}


def _patch_all(config=None, yearly_flag=None, men_games=None, women_games=None):
    """Return a dict of patches common to most main.run() tests."""
    return {
        "main.check_tournament_end": MagicMock(),
        "main.get_final_games": MagicMock(return_value=[]),
        "main.ensure_cbs_login": MagicMock(return_value=None),
        "main.get_top_n_async": MagicMock(return_value=[]),
        "main.deduplicate_top_users": MagicMock(side_effect=lambda x: x),
        "main.build_daily_summary": MagicMock(return_value=[]),
        "main.post_message": MagicMock(),
        "main.load_json": MagicMock(return_value={}),
        "main.save_json": MagicMock(),
        "main.yearly_reminder": MagicMock(),
        "main.needs_config_reminder": MagicMock(return_value=False),
        "main.run_async": MagicMock(return_value=[]),
    }


# ---------------------------------------------------------------------------
# Basic smoke tests
# ---------------------------------------------------------------------------

def test_run_calls_check_tournament_end():
    with patch("main.check_tournament_end") as mock_check, \
         patch("main.needs_setup", return_value=False), \
         patch("main.get_final_games", return_value=[]), \
         patch("main.run_async", return_value=[]), \
         patch("main.deduplicate_top_users", side_effect=lambda x: x), \
         patch("main.build_daily_summary", return_value=[]), \
         patch("main.post_message"), \
         patch("main.load_json", return_value={}), \
         patch("main.save_json"), \
         patch("main.yearly_reminder"), \
         patch("main.needs_config_reminder", return_value=False):
        run(config=LIVE_CONFIG, yearly_flag=LIVE_FLAG)
    mock_check.assert_called_once_with(LIVE_CONFIG)


def test_run_triggers_setup_when_needs_setup():
    mock_setup = MagicMock(return_value=(LIVE_CONFIG, None, [], [], [], []))
    with patch("main.needs_setup", return_value=True), \
         patch("main.run_setup", mock_setup), \
         patch("main.check_tournament_end"), \
         patch("main.load_json", return_value={}), \
         patch("main.save_json"), \
         patch("main.yearly_reminder"), \
         patch("main.needs_config_reminder", return_value=False):
        run(config=LIVE_CONFIG, yearly_flag={"LIVE_FOR_YEAR": False})
    mock_setup.assert_called_once()


def test_run_skips_setup_when_live():
    with patch("main.needs_setup", return_value=False), \
         patch("main.check_tournament_end"), \
         patch("main.get_final_games", return_value=[]), \
         patch("main.run_async", return_value=[]), \
         patch("main.deduplicate_top_users", side_effect=lambda x: x), \
         patch("main.build_daily_summary", return_value=[]), \
         patch("main.post_message"), \
         patch("main.load_json", return_value={}), \
         patch("main.save_json"), \
         patch("main.yearly_reminder"), \
         patch("main.needs_config_reminder", return_value=False) as mock_setup:
        run(config=LIVE_CONFIG, yearly_flag=LIVE_FLAG)
    # run_setup should NOT have been called
    with patch("main.run_setup") as mock_setup:
        mock_setup.assert_not_called()


def test_run_posts_daily_summary_when_enabled():
    mock_post = MagicMock()
    config = {**LIVE_CONFIG, "SEND_DAILY_SUMMARY": True}
    with patch("main.needs_setup", return_value=False), \
         patch("main.check_tournament_end"), \
         patch("main.get_final_games", return_value=[]), \
         patch("main.run_async", return_value=[]), \
         patch("main.deduplicate_top_users", side_effect=lambda x: x), \
         patch("main.build_daily_summary", return_value=["block"]), \
         patch("main.post_message", mock_post), \
         patch("main.load_json", return_value={}), \
         patch("main.save_json"), \
         patch("main.yearly_reminder"), \
         patch("main.needs_config_reminder", return_value=False):
        run(config=config, yearly_flag=LIVE_FLAG)
    mock_post.assert_called_once()


def test_run_skips_daily_summary_when_disabled():
    mock_post = MagicMock()
    config = {**LIVE_CONFIG, "SEND_DAILY_SUMMARY": False}
    with patch("main.needs_setup", return_value=False), \
         patch("main.check_tournament_end"), \
         patch("main.get_final_games", return_value=[]), \
         patch("main.run_async", return_value=[]), \
         patch("main.deduplicate_top_users", side_effect=lambda x: x), \
         patch("main.load_json", return_value={}), \
         patch("main.save_json"), \
         patch("main.yearly_reminder"), \
         patch("main.needs_config_reminder", return_value=False):
        run(config=config, yearly_flag=LIVE_FLAG)
    mock_post.assert_not_called()


def test_run_calls_yearly_reminder_when_not_live():
    mock_reminder = MagicMock()
    mock_setup = MagicMock(return_value=(LIVE_CONFIG, None, [], [], [], []))
    with patch("main.needs_setup", return_value=True), \
         patch("main.run_setup", mock_setup), \
         patch("main.check_tournament_end"), \
         patch("main.load_json", return_value={}), \
         patch("main.save_json"), \
         patch("main.yearly_reminder", mock_reminder), \
         patch("main.needs_config_reminder", return_value=False):
        run(config=LIVE_CONFIG, yearly_flag={"LIVE_FOR_YEAR": False})
    mock_reminder.assert_called_once()


def test_run_skips_yearly_reminder_when_already_live():
    mock_reminder = MagicMock()
    with patch("main.needs_setup", return_value=False), \
         patch("main.check_tournament_end"), \
         patch("main.get_final_games", return_value=[]), \
         patch("main.run_async", return_value=[]), \
         patch("main.deduplicate_top_users", side_effect=lambda x: x), \
         patch("main.build_daily_summary", return_value=[]), \
         patch("main.post_message"), \
         patch("main.load_json", return_value={}), \
         patch("main.save_json"), \
         patch("main.yearly_reminder", mock_reminder), \
         patch("main.needs_config_reminder", return_value=False):
        run(config=LIVE_CONFIG, yearly_flag=LIVE_FLAG)
    mock_reminder.assert_not_called()