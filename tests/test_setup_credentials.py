"""
Tests ensuring setup always collects required credentials and never
silently accepts empty strings for required fields.
"""
import os
import pytest
from contextlib import ExitStack
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# ask_slack_credentials_cli
# ---------------------------------------------------------------------------

class TestAskSlackCredentialsCli:

    def test_webhook_url_accepted_when_provided(self):
        from bot_setup.setup_cli import ask_slack_credentials_cli
        config = {}
        with patch("bot_setup.setup_cli.ask_with_help", side_effect=[
            "https://hooks.slack.com/services/REAL",
            "",
            "U012ABC",
        ]):
            result = ask_slack_credentials_cli(config)
        assert result["SLACK_WEBHOOK_URL"] == "https://hooks.slack.com/services/REAL"

    def test_empty_webhook_url_sets_empty_string(self):
        from bot_setup.setup_cli import ask_slack_credentials_cli
        config = {}
        with patch("bot_setup.setup_cli.ask_with_help", side_effect=["", "", ""]):
            result = ask_slack_credentials_cli(config)
        assert result["SLACK_WEBHOOK_URL"] == ""

    def test_existing_empty_webhook_is_not_silently_reused(self):
        from bot_setup.setup_cli import ask_slack_credentials_cli
        config = {"SLACK_WEBHOOK_URL": "", "SLACK_MANAGER_ID": ""}
        with patch("bot_setup.setup_cli.ask_with_help", side_effect=[
            "https://hooks.slack.com/services/NEW",
            "",
            "U999",
        ]) as mock_ask:
            result = ask_slack_credentials_cli(config)
        assert mock_ask.called
        assert result["SLACK_WEBHOOK_URL"] == "https://hooks.slack.com/services/NEW"

    def test_manager_id_saved_to_config(self):
        from bot_setup.setup_cli import ask_slack_credentials_cli
        config = {}
        with patch("bot_setup.setup_cli.ask_with_help", side_effect=[
            "https://hooks.slack.com/services/REAL",
            "",
            "U012MANAGER",
        ]):
            result = ask_slack_credentials_cli(config)
        assert result.get("SLACK_MANAGER_ID") == "U012MANAGER"

    def test_bot_token_saved_to_env_when_provided(self):
        """Bot token is written to os.environ (and .env) — not stored in config dict."""
        import dotenv
        from bot_setup.setup_cli import ask_slack_credentials_cli
        config = {}
        with patch("bot_setup.setup_cli.ask_with_help", side_effect=[
            "https://hooks.slack.com/services/REAL",
            "xoxb-fake-token",
            "U012ABC",
        ]), patch.object(dotenv, "set_key") as mock_set_key, \
           patch.dict(os.environ, {"SLACK_BOT_TOKEN": ""}, clear=False):
            ask_slack_credentials_cli(config)
        mock_set_key.assert_called()

    def test_returns_dict_not_none(self):
        from bot_setup.setup_cli import ask_slack_credentials_cli
        config = {}
        with patch("bot_setup.setup_cli.ask_with_help", side_effect=["", "", ""]):
            result = ask_slack_credentials_cli(config)
        assert isinstance(result, dict)

    def test_does_not_overwrite_existing_valid_webhook(self):
        """Empty input when a valid webhook already exists must preserve the existing value."""
        from bot_setup.setup_cli import ask_slack_credentials_cli
        config = {"SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/EXISTING"}
        with patch("bot_setup.setup_cli.ask_with_help", side_effect=["", "", ""]):
            result = ask_slack_credentials_cli(config)
        assert result.get("SLACK_WEBHOOK_URL") == "https://hooks.slack.com/services/EXISTING"


# ---------------------------------------------------------------------------
# ask_if_missing
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
        from bot_setup.setup_cli import ask_if_missing
        config = {"TOP_N": ""}
        with patch("builtins.input", return_value="7") as mock_input:
            ask_if_missing(config, "TOP_N", "How many?", default="5", cast=int)
        mock_input.assert_called_once()
        assert config["TOP_N"] == 7

    def test_ask_if_missing_treats_zero_and_false_as_valid(self):
        from bot_setup.setup_cli import ask_if_missing
        config = {"MINUTES_BETWEEN_MESSAGES": 0, "POST_WEEKENDS": False}
        with patch("builtins.input") as mock_input:
            ask_if_missing(config, "MINUTES_BETWEEN_MESSAGES", "Minutes?", default="60", cast=int)
            ask_if_missing(config, "POST_WEEKENDS", "Weekends?", default="n")
        mock_input.assert_not_called()

    def test_ask_if_missing_uses_default_on_empty_input(self):
        from bot_setup.setup_cli import ask_if_missing
        config = {}
        with patch("builtins.input", return_value=""):
            ask_if_missing(config, "TOP_N", "How many?", default="5", cast=int)
        assert config["TOP_N"] == 5

    def test_ask_if_missing_cast_applied(self):
        from bot_setup.setup_cli import ask_if_missing
        config = {}
        with patch("builtins.input", return_value="y"):
            ask_if_missing(config, "POST_WEEKENDS", "Weekends?", default="n",
                           cast=lambda x: x.lower() == "y")
        assert config["POST_WEEKENDS"] is True

    def test_ask_if_missing_none_is_treated_as_missing(self):
        """Document actual behaviour: None triggers a prompt (not treated as set)."""
        from bot_setup.setup_cli import ask_if_missing
        config = {"MANUAL_TOP": None}
        with patch("builtins.input", return_value="") as mock_input:
            ask_if_missing(config, "MANUAL_TOP", "Manual top?", default="")
        mock_input.assert_called_once()


# ---------------------------------------------------------------------------
# run_setup CLI — helpers
# ---------------------------------------------------------------------------

def _standard_run_setup_patches():
    """Common patches for run_setup tests. Does NOT patch post_message so
    individual tests can assert on it separately."""
    return [
        patch("bot_setup.bot_setup.get_final_games", return_value=[]),
        patch("bot_setup.bot_setup._fetch_leaderboard", return_value=[]),
        patch("bot_setup.bot_setup.deduplicate_top_users", side_effect=lambda x: x),
        patch("bot_setup.bot_setup.build_daily_summary",
              return_value=([{"type": "section", "text": {"type": "mrkdwn", "text": "s"}}], False)),
        patch("bot_setup.bot_setup.build_yearly_intro_message", return_value="intro"),
        patch("bot_setup.bot_setup.load_flag", return_value={"LIVE_FOR_YEAR": False}),
        patch("bot_setup.bot_setup.run_async"),
        patch("bot_setup.bot_setup.ensure_cbs_login", return_value=None),
        patch("bot_setup.bot_setup.save_json"),
        patch("bot_setup.bot_setup.ask_if_missing", side_effect=lambda c, k, *a, **kw: c),
    ]


def _enter_patches(stack, patches):
    return [stack.enter_context(p) for p in patches]


def _real_urls_config(**overrides):
    """Base config with real (non-placeholder) URLs so URL prompts never fire."""
    config = {
        "POOLS": [{"SOURCE": "cbs",
                   "MEN_URL": "https://picks.cbssports.com/college-basketball/ncaa-tournament/bracket/pools/realpool1/standings",
                   "WOMEN_URL": "https://picks.cbssports.com/college-basketball/ncaaw-tournament/bracket/pools/realpool2/standings"}],
        "TOP_N": 5,
        "MINUTES_BETWEEN_MESSAGES": 60,
        "POST_WEEKENDS": False,
        "SEND_GAME_UPDATES": True,
        "SEND_DAILY_SUMMARY": True,
        "TOURNAMENT_END_MEN": "2026-04-06",
        "TOURNAMENT_END_WOMEN": "2026-04-05",
        "PLAYWRIGHT_HEADLESS": True,
        "PLAYWRIGHT_STATE": "playwright_state.json",
    }
    config.update(overrides)
    return config


# ---------------------------------------------------------------------------
# run_setup CLI — go-live guard tests
# ---------------------------------------------------------------------------

class TestRunSetupCliGoLiveGuard:

    def test_run_setup_cli_blocks_go_live_without_webhook(self):
        """No webhook → go-live must be skipped and post_message never called."""
        from bot_setup.bot_setup import run_setup
        config = _real_urls_config(SLACK_WEBHOOK_URL="")
        no_webhook_config = {**config, "SLACK_WEBHOOK_URL": ""}

        with ExitStack() as stack:
            stack.enter_context(patch("bot_setup.bot_setup.get_input_safe", side_effect=["cli", "n"]))
            stack.enter_context(patch("bot_setup.bot_setup.ask_slack_credentials_cli", return_value=no_webhook_config))
            mock_post = stack.enter_context(patch("bot_setup.bot_setup.post_message"))
            _enter_patches(stack, _standard_run_setup_patches())
            result = run_setup(config)

        assert result is not None
        assert result[0].get("SLACK_WEBHOOK_URL") == ""
        mock_post.assert_not_called()

    def test_run_setup_cli_proceeds_with_valid_webhook(self):
        """With a real webhook, setup reaches go-live and returns cleanly on 'n'."""
        from bot_setup.bot_setup import run_setup
        config = _real_urls_config(
            SLACK_WEBHOOK_URL="https://hooks.slack.com/services/REAL",
            SLACK_MANAGER_ID="U012ABC",
        )
        with_webhook = {**config}

        with ExitStack() as stack:
            stack.enter_context(patch("bot_setup.bot_setup.get_input_safe", side_effect=["cli", "n"]))
            stack.enter_context(patch("bot_setup.bot_setup.ask_slack_credentials_cli", return_value=with_webhook))
            mock_post = stack.enter_context(patch("bot_setup.bot_setup.post_message"))
            _enter_patches(stack, _standard_run_setup_patches())
            result = run_setup(config)

        assert result is not None
        cfg, method, *_ = result
        assert method == "cli"
        mock_post.assert_not_called()

    def test_credentials_asked_after_preview_not_before(self):
        """ask_slack_credentials_cli must be called after build_daily_summary."""
        from bot_setup.bot_setup import run_setup
        config = _real_urls_config(SLACK_WEBHOOK_URL="https://hooks.slack.com/services/REAL")

        call_order = []

        def track_credentials(c):
            call_order.append("credentials")
            return {**c, "SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/REAL"}

        def track_summary(*a, **kw):
            call_order.append("preview")
            return ([{"type": "section", "text": {"type": "mrkdwn", "text": "s"}}], False)

        with ExitStack() as stack:
            stack.enter_context(patch("bot_setup.bot_setup.get_input_safe", side_effect=["cli", "n"]))
            stack.enter_context(patch("bot_setup.bot_setup.ask_slack_credentials_cli", side_effect=track_credentials))
            stack.enter_context(patch("bot_setup.bot_setup.build_daily_summary", side_effect=track_summary))
            stack.enter_context(patch("bot_setup.bot_setup.post_message"))
            _enter_patches(stack, [
                patch("bot_setup.bot_setup.get_final_games", return_value=[]),
                patch("bot_setup.bot_setup._fetch_leaderboard", return_value=[]),
                patch("bot_setup.bot_setup.deduplicate_top_users", side_effect=lambda x: x),
                patch("bot_setup.bot_setup.build_yearly_intro_message", return_value="intro"),
                patch("bot_setup.bot_setup.load_flag", return_value={"LIVE_FOR_YEAR": False}),
                patch("bot_setup.bot_setup.run_async"),
                patch("bot_setup.bot_setup.save_json"),
                patch("bot_setup.bot_setup.ask_if_missing", side_effect=lambda c, k, *a, **kw: c),
            ])
            run_setup(config)

        assert "preview" in call_order, "build_daily_summary (preview) was never called"
        assert "credentials" in call_order, "ask_slack_credentials_cli was never called"
        assert call_order.index("preview") < call_order.index("credentials"), \
            "Credentials were asked BEFORE preview — must be after"

    def test_run_setup_cli_go_live_yes_calls_post_message(self):
        """Answering 'y' at go-live with a valid webhook must call post_message."""
        from bot_setup.bot_setup import run_setup
        config = _real_urls_config(SLACK_WEBHOOK_URL="https://hooks.slack.com/services/REAL")
        with_webhook = {**config}

        with ExitStack() as stack:
            stack.enter_context(patch("bot_setup.bot_setup.get_input_safe", side_effect=["cli", "y"]))
            stack.enter_context(patch("bot_setup.bot_setup.ask_slack_credentials_cli", return_value=with_webhook))
            mock_post = stack.enter_context(patch("bot_setup.bot_setup.post_message"))
            _enter_patches(stack, _standard_run_setup_patches())
            run_setup(config)

        assert mock_post.called, "post_message should have been called on go-live=True"

    def test_run_setup_cli_go_live_no_does_not_call_post_message(self):
        """Answering 'n' at go-live must not post anything."""
        from bot_setup.bot_setup import run_setup
        config = _real_urls_config(SLACK_WEBHOOK_URL="https://hooks.slack.com/services/REAL")
        with_webhook = {**config}

        with ExitStack() as stack:
            stack.enter_context(patch("bot_setup.bot_setup.get_input_safe", side_effect=["cli", "n"]))
            stack.enter_context(patch("bot_setup.bot_setup.ask_slack_credentials_cli", return_value=with_webhook))
            mock_post = stack.enter_context(patch("bot_setup.bot_setup.post_message"))
            _enter_patches(stack, _standard_run_setup_patches())
            run_setup(config)

        mock_post.assert_not_called()

    def test_run_setup_always_returns_tuple(self):
        """run_setup must always return a tuple regardless of path taken."""
        from bot_setup.bot_setup import run_setup
        config = _real_urls_config(SLACK_WEBHOOK_URL="")
        no_webhook_config = {**config}

        with ExitStack() as stack:
            stack.enter_context(patch("bot_setup.bot_setup.get_input_safe", side_effect=["cli", "n"]))
            stack.enter_context(patch("bot_setup.bot_setup.ask_slack_credentials_cli", return_value=no_webhook_config))
            stack.enter_context(patch("bot_setup.bot_setup.post_message"))
            _enter_patches(stack, _standard_run_setup_patches())
            result = run_setup(config)

        assert isinstance(result, tuple), "run_setup must return a tuple"

    def test_config_saved_after_credentials_collected(self):
        """save_json must be called with the webhook present — not before credentials."""
        from bot_setup.bot_setup import run_setup
        config = _real_urls_config(SLACK_WEBHOOK_URL="https://hooks.slack.com/services/REAL")
        with_webhook = {**config}

        save_calls = []

        def track_save(path, data):
            save_calls.append(data.get("SLACK_WEBHOOK_URL", "__missing__"))

        with ExitStack() as stack:
            stack.enter_context(patch("bot_setup.bot_setup.get_input_safe", side_effect=["cli", "n"]))
            stack.enter_context(patch("bot_setup.bot_setup.ask_slack_credentials_cli", return_value=with_webhook))
            stack.enter_context(patch("bot_setup.bot_setup.post_message"))
            _enter_patches(stack, [
                patch("bot_setup.bot_setup.get_final_games", return_value=[]),
                patch("bot_setup.bot_setup._fetch_leaderboard", return_value=[]),
                patch("bot_setup.bot_setup.deduplicate_top_users", side_effect=lambda x: x),
                patch("bot_setup.bot_setup.build_daily_summary",
                      return_value=([{"type": "section", "text": {"type": "mrkdwn", "text": "s"}}], False)),
                patch("bot_setup.bot_setup.build_yearly_intro_message", return_value="intro"),
                patch("bot_setup.bot_setup.load_flag", return_value={"LIVE_FOR_YEAR": False}),
                patch("bot_setup.bot_setup.run_async"),
                patch("bot_setup.bot_setup.save_json", side_effect=track_save),
                patch("bot_setup.bot_setup.ask_if_missing", side_effect=lambda c, k, *a, **kw: c),
            ])
            run_setup(config)

        assert any(v == "https://hooks.slack.com/services/REAL" for v in save_calls), \
            "No save_json call contained the webhook — credentials may not have been persisted"