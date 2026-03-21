"""
Tests ensuring setup always collects required credentials and never
silently accepts empty strings for required fields.

These tests would have caught:
- CLI setup skipping SLACK_WEBHOOK_URL when key exists but is empty string
- ask_if_missing treating "" as a valid set value
- Go-live proceeding without a webhook URL
"""
import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# ask_slack_credentials_cli — must re-prompt on empty string
# ---------------------------------------------------------------------------

class TestAskSlackCredentialsCli:

    def test_webhook_url_accepted_when_provided(self):
        from bot_setup.setup_cli import ask_slack_credentials_cli
        config = {}
        with patch("bot_setup.setup_cli.ask_with_help", side_effect=[
            "https://hooks.slack.com/services/REAL",  # webhook
            "",                                        # token (optional)
            "U012ABC",                                 # manager ID
        ]):
            result = ask_slack_credentials_cli(config)
        assert result["SLACK_WEBHOOK_URL"] == "https://hooks.slack.com/services/REAL"

    def test_empty_webhook_url_sets_empty_string(self):
        """Entering nothing should leave SLACK_WEBHOOK_URL as '' (mock mode)."""
        from bot_setup.setup_cli import ask_slack_credentials_cli
        config = {}
        with patch("bot_setup.setup_cli.ask_with_help", side_effect=["", "", ""]):
            result = ask_slack_credentials_cli(config)
        assert result["SLACK_WEBHOOK_URL"] == ""

    def test_existing_empty_webhook_is_not_silently_reused(self):
        """
        If config already has SLACK_WEBHOOK_URL="" the prompt must still show —
        ask_slack_credentials_cli must not skip based on existing empty value.
        """
        from bot_setup.setup_cli import ask_slack_credentials_cli
        config = {"SLACK_WEBHOOK_URL": "", "SLACK_MANAGER_ID": ""}
        with patch("bot_setup.setup_cli.ask_with_help", side_effect=[
            "https://hooks.slack.com/services/NEW",
            "",
            "U999",
        ]) as mock_ask:
            result = ask_slack_credentials_cli(config)
        # ask_with_help must have been called (not skipped)
        assert mock_ask.called
        assert result["SLACK_WEBHOOK_URL"] == "https://hooks.slack.com/services/NEW"


# ---------------------------------------------------------------------------
# ask_if_missing — must NOT treat empty string as a set value
# ---------------------------------------------------------------------------

class TestAskIfMissing:

    def test_ask_if_missing_skips_when_value_is_set(self):
        from bot_setup.setup_cli import ask_if_missing
        config = {"TOP_N": 5}
        with patch("builtins.input") as mock_input:
            ask_if_missing(config, "TOP_N", "How many?", default="5", cast=int)
        mock_input.assert_not_called()
        assert config["TOP_N"] == 5

    def test_ask_if_missing_prompts_when_key_missing(self):
        from bot_setup.setup_cli import ask_if_missing
        config = {}
        with patch("builtins.input", return_value="10"):
            ask_if_missing(config, "TOP_N", "How many?", default="5", cast=int)
        assert config["TOP_N"] == 10

    def test_ask_if_missing_prompts_when_value_is_empty_string(self):
        """
        Empty string must NOT be treated as a valid value — must re-prompt.
        This is the core bug: ask_if_missing(config, "TOP_N", ...) where
        config["TOP_N"] = "" should still ask the question.
        """
        from bot_setup.setup_cli import ask_if_missing
        config = {"TOP_N": ""}
        with patch("builtins.input", return_value="7") as mock_input:
            ask_if_missing(config, "TOP_N", "How many?", default="5", cast=int)
        mock_input.assert_called_once()
        assert config["TOP_N"] == 7

    def test_ask_if_missing_treats_zero_and_false_as_valid(self):
        """0 and False are real values — must not re-prompt."""
        from bot_setup.setup_cli import ask_if_missing
        config = {"MINUTES_BETWEEN_MESSAGES": 0, "POST_WEEKENDS": False}
        with patch("builtins.input") as mock_input:
            ask_if_missing(config, "MINUTES_BETWEEN_MESSAGES", "Minutes?", default="60", cast=int)
            ask_if_missing(config, "POST_WEEKENDS", "Weekends?", default="n")
        mock_input.assert_not_called()


# ---------------------------------------------------------------------------
# run_setup CLI path — must block go-live without webhook URL
# ---------------------------------------------------------------------------

class TestRunSetupCliGoLiveGuard:

    def _base_config(self):
        return {
            "POOLS": [{"SOURCE": "cbs", "MEN_URL": "", "WOMEN_URL": ""}],
            "TOP_N": 5,
            "MINUTES_BETWEEN_MESSAGES": 60,
            "POST_WEEKENDS": False,
            "SEND_GAME_UPDATES": True,
            "SEND_DAILY_SUMMARY": True,
            "TOURNAMENT_END_MEN": "2026-04-06",
            "TOURNAMENT_END_WOMEN": "2026-04-05",
        }

    def test_run_setup_cli_blocks_go_live_without_webhook(self):
        """
        If user provides no webhook URL, run_setup must return early
        and never reach the go-live prompt.
        """
        from bot_setup.bot_setup import run_setup
        config = self._base_config()
        config["SLACK_WEBHOOK_URL"] = ""

        with patch("bot_setup.bot_setup.get_input_safe", side_effect=["cli"]), \
             patch("bot_setup.bot_setup.ask_slack_credentials_cli", return_value=config), \
             patch("bot_setup.bot_setup.save_json"):
            result = run_setup(config)

        assert result is not None
        cfg, method, men, women, top_men, top_women = result
        # Must have returned early — no games or leaderboard fetched
        assert men == []
        assert women == []
        assert top_men == []
        assert top_women == []

    def test_run_setup_cli_proceeds_with_valid_webhook(self):
        """With a real webhook, setup should reach the preview/go-live stage."""
        from bot_setup.bot_setup import run_setup
        config = self._base_config()
        config["SLACK_WEBHOOK_URL"] = "https://hooks.slack.com/services/REAL"
        config["SLACK_MANAGER_ID"] = "U012ABC"
        config["POOLS"] = [{"SOURCE": "cbs",
                            "MEN_URL": "https://picks.cbssports.com/college-basketball/ncaa-tournament/bracket/pools/unittestpool1/standings",
                            "WOMEN_URL": ""}]

        with patch("bot_setup.bot_setup.get_input_safe", side_effect=[
                "cli",   # method prompt
                "",      # women's URL prompt (skip)
                "n",     # go-live confirm
             ]) as mock_input, \
             patch("bot_setup.bot_setup.ask_slack_credentials_cli", return_value=config), \
             patch("bot_setup.bot_setup.ask_if_missing"), \
             patch("bot_setup.bot_setup.get_final_games", return_value=[]), \
             patch("bot_setup.bot_setup._fetch_leaderboard", return_value=[]), \
             patch("bot_setup.bot_setup.build_daily_summary", return_value=([], True)), \
             patch("bot_setup.bot_setup.save_json"):
            result = run_setup(config)

        assert result is not None
        cfg, method, *_ = result
        assert method == "cli"
        # Women's URL must not have been set to "n"
        assert cfg["POOLS"][0].get("WOMEN_URL") in ("", None)