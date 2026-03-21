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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_config(**overrides):
    config = {
        "METHOD": "cli",
        "TOP_N": 3,
        "SLACK_WEBHOOK_URL": "https://hooks.slack.com/fake",
        "SLACK_MANAGER_ID": "U012ABC",
        "POOLS": [{"SOURCE": "cbs",
                   "MEN_URL": "https://www.cbssports.com/brackets/men/group/123",
                   "WOMEN_URL": "https://www.cbssports.com/brackets/women/group/456"}],
        "SEND_DAILY_SUMMARY": True,
        "POST_WEEKENDS": True,
        "MINUTES_BETWEEN_MESSAGES": 0,
    }
    config.update(overrides)
    return config


def _live_flag():
    return {"LIVE_FOR_YEAR": True}


def _dead_flag():
    return {"LIVE_FOR_YEAR": False}


# ---------------------------------------------------------------------------
# Shared patch context
# ---------------------------------------------------------------------------

from contextlib import contextmanager

@contextmanager
def _main_patches(config, yearly_flag, run_setup_return=None, **overrides):
    """Patch everything main.run() touches except run_setup."""
    default_setup_result = (config, "cli", [], [], [], [])
    mocks = {
        "load_json":            MagicMock(side_effect=[config, yearly_flag]),
        "check_tournament_end": MagicMock(),
        "needs_setup":          MagicMock(return_value=False),
        "run_setup":            MagicMock(return_value=run_setup_return or default_setup_result),
        "get_final_games":      MagicMock(return_value=[]),
        "ensure_cbs_login":     MagicMock(),
        "get_top_n_async":      MagicMock(return_value=[]),
        "deduplicate_top_users":MagicMock(side_effect=lambda x: x),
        "build_daily_summary":  MagicMock(return_value=([{"type": "section"}], False)),
        "post_message":         MagicMock(),
        "yearly_reminder":      MagicMock(),
        "needs_config_reminder":MagicMock(return_value=False),
        "save_json":            MagicMock(),
        "run_async":            MagicMock(return_value=[]),
    }
    mocks.update(overrides)

    with patch("main.load_json",             mocks["load_json"]), \
         patch("main.check_tournament_end",  mocks["check_tournament_end"]), \
         patch("main.needs_setup",           mocks["needs_setup"]), \
         patch("main.run_setup",             mocks["run_setup"]), \
         patch("main.get_final_games",       mocks["get_final_games"]), \
         patch("main.ensure_cbs_login",      mocks["ensure_cbs_login"]), \
         patch("main.get_top_n_async",       mocks["get_top_n_async"]), \
         patch("main.deduplicate_top_users", mocks["deduplicate_top_users"]), \
         patch("main.build_daily_summary",   mocks["build_daily_summary"]), \
         patch("main.post_message",          mocks["post_message"]), \
         patch("main.yearly_reminder",       mocks["yearly_reminder"]), \
         patch("main.needs_config_reminder", mocks["needs_config_reminder"]), \
         patch("main.save_json",             mocks["save_json"]), \
         patch("main.run_async",             mocks["run_async"]):
        yield mocks


# ---------------------------------------------------------------------------
# Setup trigger tests — the regression class for this bug
# ---------------------------------------------------------------------------

class TestSetupTrigger:
    """Guards the condition that decides when run_setup is called."""

    def test_setup_runs_when_needs_setup_true(self):
        from main import run
        config = _base_config()
        with _main_patches(config, _live_flag(), needs_setup=MagicMock(return_value=True)) as m:
            run(config, _live_flag())
        assert m["run_setup"].called

    def test_setup_runs_when_not_live_for_year(self):
        from main import run
        config = _base_config()
        with _main_patches(config, _dead_flag()) as m:
            run(config, _dead_flag())
        assert m["run_setup"].called

    def test_setup_skipped_when_live_and_config_complete(self):
        from main import run
        config = _base_config()
        with _main_patches(config, _live_flag()) as m:
            run(config, _live_flag())
        assert not m["run_setup"].called

    def test_setup_runs_when_both_not_live_and_needs_setup(self):
        from main import run
        config = _base_config()
        with _main_patches(config, _dead_flag(), needs_setup=MagicMock(return_value=True)) as m:
            run(config, _dead_flag())
        assert m["run_setup"].called

    # --- THE BUG THIS PR FIXES ---

    def test_method_key_stripped_before_run_setup(self):
        """METHOD must not be in the config passed to run_setup.
        If it is, get_input_safe skips the slack/cli prompt and the
        user never gets asked — the root cause of the reported bug."""
        from main import run
        config = _base_config(METHOD="cli")  # METHOD already saved in config.json
        with _main_patches(config, _dead_flag()) as m:
            run(config, _dead_flag())
        passed_config = m["run_setup"].call_args[0][0]
        assert "METHOD" not in passed_config, (
            "METHOD was passed to run_setup — the slack/cli prompt will be silently skipped"
        )

    def test_other_keys_preserved_before_run_setup(self):
        """All other saved config keys must be forwarded to run_setup
        so the user is not re-prompted for things they already configured."""
        from main import run
        config = _base_config(METHOD="cli")
        with _main_patches(config, _dead_flag()) as m:
            run(config, _dead_flag())
        passed_config = m["run_setup"].call_args[0][0]
        for key in ("TOP_N", "SLACK_WEBHOOK_URL", "POOLS", "SEND_DAILY_SUMMARY"):
            assert key in passed_config, f"Key '{key}' was missing from config passed to run_setup"

    def test_setup_result_none_does_not_crash(self):
        """If run_setup returns None (setup paused), run() exits cleanly."""
        from main import run
        config = _base_config()
        with _main_patches(config, _dead_flag(), run_setup_return=(None, "cli", [], [], [], [])):
            run(config, _dead_flag())  # should not raise

    def test_setup_result_propagates_to_live_path(self):
        """Config returned by run_setup is used for the rest of the run."""
        from main import run
        updated_config = _base_config(TOP_N=10)
        with _main_patches(
            _base_config(), _dead_flag(),
            run_setup_return=(updated_config, "cli", [], [], [], [])
        ) as m:
            run(_base_config(), _dead_flag())
        # yearly_reminder receives the post-setup config
        called_config = m["yearly_reminder"].call_args[0][0]
        assert called_config.get("TOP_N") == 10


# ---------------------------------------------------------------------------
# Live path tests
# ---------------------------------------------------------------------------

class TestLivePath:
    """Guards the normal daily-run path (setup already complete)."""

    def test_live_path_fetches_games(self):
        from main import run
        config = _base_config()
        with _main_patches(config, _live_flag()) as m:
            run(config, _live_flag())
        assert m["get_final_games"].call_count == 2

    def test_live_path_posts_daily_summary(self):
        from main import run
        config = _base_config()
        with _main_patches(config, _live_flag()) as m:
            run(config, _live_flag())
        assert m["post_message"].called

    def test_live_path_skips_summary_when_disabled(self):
        from main import run
        config = _base_config(SEND_DAILY_SUMMARY=False)
        with _main_patches(config, _live_flag()) as m:
            run(config, _live_flag())
        assert not m["post_message"].called

    def test_live_path_does_not_call_run_setup(self):
        from main import run
        config = _base_config()
        with _main_patches(config, _live_flag()) as m:
            run(config, _live_flag())
        assert not m["run_setup"].called

    def test_live_path_saves_seen_games(self):
        from main import run
        config = _base_config()
        games = [{"id": "g1"}, {"id": "g2"}]
        with _main_patches(config, _live_flag(),
                           get_final_games=MagicMock(return_value=games)) as m:
            run(config, _live_flag())
        assert m["save_json"].called

    def test_live_path_skips_browser_when_no_urls(self):
        from main import run
        config = _base_config(POOLS=[{"SOURCE": "cbs", "MEN_URL": "", "WOMEN_URL": ""}])
        with _main_patches(config, _live_flag()) as m:
            run(config, _live_flag())
        assert not m["ensure_cbs_login"].called

    def test_live_path_calls_yearly_reminder_when_not_live(self):
        from main import run
        config = _base_config()
        # needs_setup=False but LIVE_FOR_YEAR=False — setup runs, then reminder fires
        with _main_patches(config, _dead_flag()) as m:
            run(config, _dead_flag())
        assert m["yearly_reminder"].called

    def test_live_path_skips_yearly_reminder_when_live(self):
        from main import run
        config = _base_config()
        with _main_patches(config, _live_flag()) as m:
            run(config, _live_flag())
        assert not m["yearly_reminder"].called


# ---------------------------------------------------------------------------
# Setup method tests — guards slack/cli prompt behaviour
# ---------------------------------------------------------------------------

class TestSetupMethod:
    """Guards that the slack/cli choice is always asked fresh and that
    each method only triggers its own CLI questions."""

    def test_slack_method_only_asks_credentials_not_preferences(self):
        """When the user picks slack, run_setup must NOT call ask_if_missing
        for TOP_N, POST_WEEKENDS, etc. before handing off to run_slack_dm_setup.
        All preferences belong in the DM flow."""
        from bot_setup.bot_setup import run_setup

        with patch("bot_setup.bot_setup.get_input_safe", return_value="slack"), \
             patch("bot_setup.bot_setup.ask_slack_credentials_cli",
                   return_value={
                       "SLACK_WEBHOOK_URL": "https://hooks.slack.com/fake",
                       "SLACK_MANAGER_ID": "U012ABC",
                   }), \
             patch("bot_setup.bot_setup.run_slack_dm_setup",
                   return_value={
                       "SLACK_WEBHOOK_URL": "https://hooks.slack.com/fake",
                       "SLACK_MANAGER_ID": "U012ABC",
                       "TOP_N": 5,
                       "POOLS": [{"SOURCE": "custom", "MEN_URL": "https://cbssports.com/men", "WOMEN_URL": ""}],
                       "PLAYWRIGHT_HEADLESS": True,
                       "PLAYWRIGHT_STATE": "playwright_state.json",
                       "TOURNAMENT_END_MEN": "2026-04-07",
                       "TOURNAMENT_END_WOMEN": "2026-04-06",
                       "MANUAL_TOP": None,
                   }), \
             patch("bot_setup.bot_setup.ask_if_missing") as mock_ask_if_missing, \
             patch("bot_setup.bot_setup.get_final_games", return_value=[]), \
             patch("bot_setup.bot_setup.run_async", return_value=[]), \
             patch("bot_setup.bot_setup.deduplicate_top_users", side_effect=lambda x: x), \
             patch("bot_setup.bot_setup.build_daily_summary", return_value=([], True)), \
             patch("slack_bot.slack_dm.send_dm", return_value=(None, None)), \
             patch("slack_bot.slack_dm.send_dm_blocks", return_value=None), \
             patch("slack_bot.slack_dm.poll_for_reply", return_value=None), \
             patch("slack_bot.slack_dm.save_pending_dm", return_value=None), \
             patch("bot_setup.bot_setup.save_json"):
            run_setup({})

        assert not mock_ask_if_missing.called, (
            "ask_if_missing was called during slack setup — preference questions "
            "should only appear in DMs, not on the command line"
        )

    def test_cli_method_asks_preferences(self):
        """When the user picks cli, ask_if_missing must be called for
        core preferences (TOP_N at minimum)."""
        from bot_setup.bot_setup import run_setup

        asked_keys = []

        def _capture(config, key, *args, **kwargs):
            asked_keys.append(key)

        with patch("bot_setup.bot_setup.get_input_safe", return_value="cli"), \
             patch("bot_setup.bot_setup.ask_if_missing", side_effect=_capture), \
             patch("bot_setup.bot_setup.get_final_games", return_value=[]), \
             patch("bot_setup.bot_setup.run_async", return_value=[]), \
             patch("bot_setup.bot_setup.deduplicate_top_users", side_effect=lambda x: x), \
             patch("bot_setup.bot_setup.build_daily_summary", return_value=([], True)), \
             patch("bot_setup.bot_setup.save_json"):
            run_setup({})

        assert "TOP_N" in asked_keys, "TOP_N was not asked during CLI setup"
        assert "POST_WEEKENDS" in asked_keys, "POST_WEEKENDS was not asked during CLI setup"
        assert "SEND_DAILY_SUMMARY" in asked_keys, "SEND_DAILY_SUMMARY was not asked during CLI setup"

    def test_slack_fallback_to_cli_asks_preferences(self):
        """If slack credentials are incomplete, setup falls back to CLI
        and must still ask preferences."""
        from bot_setup.bot_setup import run_setup

        asked_keys = []

        def _capture(config, key, *args, **kwargs):
            asked_keys.append(key)

        with patch("bot_setup.bot_setup.get_input_safe", return_value="slack"), \
             patch("bot_setup.bot_setup.ask_slack_credentials_cli",
                   return_value={}), \
             patch("bot_setup.bot_setup.ask_if_missing", side_effect=_capture), \
             patch("bot_setup.bot_setup.get_final_games", return_value=[]), \
             patch("bot_setup.bot_setup.run_async", return_value=[]), \
             patch("bot_setup.bot_setup.deduplicate_top_users", side_effect=lambda x: x), \
             patch("bot_setup.bot_setup.build_daily_summary", return_value=([], True)), \
             patch("bot_setup.bot_setup.save_json"):
            run_setup({})

        assert "TOP_N" in asked_keys, (
            "TOP_N was not asked after slack→cli fallback"
        )