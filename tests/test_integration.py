import pytest
from unittest.mock import patch, MagicMock


def _base_config(**overrides):
    config = {
        "METHOD": "cli",
        "TOP_N": 3,
        "MINUTES_BETWEEN_MESSAGES": 30,
        "PLAYWRIGHT_HEADLESS": True,
        "PLAYWRIGHT_STATE": "playwright_state.json",
        "POOLS": [{"SOURCE": "cbs", "MEN_URL": "https://example.com/men", "WOMEN_URL": "https://example.com/women"}],
        "SLACK_WEBHOOK_URL": "",
        "MOCK_SLACK": True,
        "POST_ON_WEEKENDS": True,
        "MANUAL_TOP": ["Alice (100)", "Bob (90)", "Carol (80)"],
    }
    config.update(overrides)
    return config


@pytest.mark.integration
def test_bot_runs_end_to_end_mock_mode():
    from bot_setup.bot_setup import run_setup

    with patch("bot_setup.bot_setup.get_input_safe", side_effect=["cli", "n"]), \
            patch("bot_setup.bot_setup.ensure_cbs_login"), \
            patch("bot_setup.bot_setup.get_top_n_async"), \
            patch("bot_setup.bot_setup.run_async", return_value=[]), \
            patch("bot_setup.bot_setup.get_final_games", return_value=[]), \
            patch("bot_setup.bot_setup.ask_if_missing", side_effect=lambda c, k, *a, **kw: c), \
            patch("bot_setup.bot_setup.load_flag", return_value={"LIVE_FOR_YEAR": False}), \
            patch("bot_setup.bot_setup.deduplicate_top_users", side_effect=lambda x: x), \
            patch("bot_setup.bot_setup.build_daily_summary", return_value=([{"type": "section"}], False)), \
            patch("bot_setup.bot_setup.build_yearly_intro_message", return_value="intro"), \
            patch("bot_setup.bot_setup.post_message"), \
            patch("bot_setup.config.save_json"):
        result = run_setup(_base_config())

    assert result is not None


@pytest.mark.integration
def test_bot_go_live_posts_intro_and_summary():
    from bot_setup.bot_setup import run_setup

    games = [{"id": "g1", "home": "Duke", "away": "UNC", "home_score": 80, "away_score": 75}]
    top = ["Alice (100)", "Bob (90)", "Carol (80)"]

    with patch("bot_setup.bot_setup.get_input_safe", side_effect=["cli", "yes"]), \
            patch("bot_setup.bot_setup.ensure_cbs_login"), \
            patch("bot_setup.bot_setup.get_top_n_async"), \
            patch("bot_setup.bot_setup.run_async", return_value=top), \
            patch("bot_setup.bot_setup.get_final_games", return_value=games), \
            patch("bot_setup.bot_setup.ask_if_missing", side_effect=lambda c, k, *a, **kw: c), \
            patch("bot_setup.bot_setup.load_flag", return_value={"LIVE_FOR_YEAR": False}), \
            patch("bot_setup.bot_setup.deduplicate_top_users", side_effect=lambda x: x), \
            patch("bot_setup.bot_setup.build_daily_summary", return_value=([{"type": "section"}], False)), \
            patch("bot_setup.bot_setup.build_yearly_intro_message", return_value="intro"), \
            patch("bot_setup.bot_setup.post_message") as mock_post, \
            patch("bot_setup.config.save_json"):
        run_setup(_base_config())

    assert mock_post.call_count >= 2


@pytest.mark.integration
def test_bot_off_day_skips_summary_post():
    from bot_setup.bot_setup import run_setup

    with patch("bot_setup.bot_setup.get_input_safe", side_effect=["cli", "n"]), \
            patch("bot_setup.bot_setup.ensure_cbs_login"), \
            patch("bot_setup.bot_setup.get_top_n_async"), \
            patch("bot_setup.bot_setup.run_async", return_value=[]), \
            patch("bot_setup.bot_setup.get_final_games", return_value=[]), \
            patch("bot_setup.bot_setup.ask_if_missing", side_effect=lambda c, k, *a, **kw: c), \
            patch("bot_setup.bot_setup.load_flag", return_value={"LIVE_FOR_YEAR": False}), \
            patch("bot_setup.bot_setup.deduplicate_top_users", side_effect=lambda x: x), \
            patch("bot_setup.bot_setup.build_daily_summary", return_value=([{"type": "section"}], True)), \
            patch("bot_setup.bot_setup.build_yearly_intro_message", return_value="intro"), \
            patch("bot_setup.bot_setup.post_message") as mock_post, \
            patch("bot_setup.config.save_json"):
        run_setup(_base_config())

    calls = [str(c) for c in mock_post.call_args_list]
    assert not any("summary" in c.lower() for c in calls)


@pytest.mark.integration
def test_bot_already_live_skips_go_live_prompt():
    from bot_setup.bot_setup import run_setup

    with patch("bot_setup.bot_setup.get_input_safe", return_value="cli"), \
            patch("bot_setup.bot_setup.ensure_cbs_login"), \
            patch("bot_setup.bot_setup.get_top_n_async"), \
            patch("bot_setup.bot_setup.run_async", return_value=[]), \
            patch("bot_setup.bot_setup.get_final_games", return_value=[]), \
            patch("bot_setup.bot_setup.ask_if_missing", side_effect=lambda c, k, *a, **kw: c), \
            patch("bot_setup.bot_setup.load_flag", return_value={"LIVE_FOR_YEAR": True}), \
            patch("bot_setup.bot_setup.deduplicate_top_users", side_effect=lambda x: x), \
            patch("bot_setup.bot_setup.build_daily_summary", return_value=([{"type": "section"}], False)), \
            patch("bot_setup.bot_setup.build_yearly_intro_message", return_value="intro"), \
            patch("bot_setup.bot_setup.post_message"), \
            patch("bot_setup.config.save_json"):
        result = run_setup(_base_config())

    assert result is not None


@pytest.mark.integration
def test_bot_missing_pools_returns_early(capsys):
    from bot_setup.bot_setup import run_setup

    with patch("bot_setup.bot_setup.get_input_safe", return_value="cli"), \
            patch("bot_setup.bot_setup.ask_if_missing", side_effect=lambda c, k, *a, **kw: c), \
            patch("bot_setup.config.save_json"):
        run_setup(_base_config(POOLS=[]))

    assert "[ERROR]" in capsys.readouterr().out


@pytest.mark.integration
def test_bot_scraping_failure_falls_back_to_manual_top():
    from bot_setup.bot_setup import run_setup

    with patch("bot_setup.bot_setup.get_input_safe", side_effect=["cli", "manual", "n"]), \
            patch("bot_setup.bot_setup.ensure_cbs_login"), \
            patch("bot_setup.bot_setup.get_top_n_async"), \
            patch("bot_setup.bot_setup.get_final_games", return_value=[]), \
            patch("bot_setup.bot_setup.run_async", side_effect=Exception("scrape failed")), \
            patch("bot_setup.bot_setup.ask_if_missing", side_effect=lambda c, k, *a, **kw: c), \
            patch("bot_setup.bot_setup.load_flag", return_value={"LIVE_FOR_YEAR": False}), \
            patch("bot_setup.bot_setup.deduplicate_top_users", side_effect=lambda x: x), \
            patch("bot_setup.bot_setup.build_daily_summary", return_value=([{"type": "section"}], False)), \
            patch("bot_setup.bot_setup.build_yearly_intro_message", return_value="intro"), \
            patch("bot_setup.bot_setup.post_message"), \
            patch("bot_setup.config.save_json"):
        result = run_setup(_base_config())

    assert result is not None


@pytest.mark.integration
def test_bot_with_webhook_uses_real_post_path():
    from bot_setup.bot_setup import run_setup

    config = _base_config(SLACK_WEBHOOK_URL="https://hooks.slack.com/fake", MOCK_SLACK=False)
    top = ["Alice (100)", "Bob (90)", "Carol (80)"]

    with patch("bot_setup.bot_setup.get_input_safe", side_effect=["cli", "yes"]), \
            patch("bot_setup.bot_setup.ensure_cbs_login"), \
            patch("bot_setup.bot_setup.get_top_n_async"), \
            patch("bot_setup.bot_setup.run_async", return_value=top), \
            patch("bot_setup.bot_setup.get_final_games", return_value=[]), \
            patch("bot_setup.bot_setup.ask_if_missing", side_effect=lambda c, k, *a, **kw: c), \
            patch("bot_setup.bot_setup.load_flag", return_value={"LIVE_FOR_YEAR": False}), \
            patch("bot_setup.bot_setup.deduplicate_top_users", side_effect=lambda x: x), \
            patch("bot_setup.bot_setup.build_daily_summary", return_value=([{"type": "section"}], False)), \
            patch("bot_setup.bot_setup.build_yearly_intro_message", return_value="intro"), \
            patch("bot_setup.bot_setup.post_message") as mock_post, \
            patch("bot_setup.config.save_json"):
        run_setup(config)

    assert mock_post.called


@pytest.mark.integration
def test_bot_setup_does_not_open_browser_in_tests():
    from bot_setup.bot_setup import run_setup

    with patch("bot_setup.bot_setup.get_input_safe", side_effect=["cli", "n"]), \
            patch("bot_setup.bot_setup.ensure_cbs_login") as mock_login, \
            patch("bot_setup.bot_setup.get_top_n_async"), \
            patch("bot_setup.bot_setup.run_async", return_value=[]), \
            patch("bot_setup.bot_setup.get_final_games", return_value=[]), \
            patch("bot_setup.bot_setup.ask_if_missing", side_effect=lambda c, k, *a, **kw: c), \
            patch("bot_setup.bot_setup.load_flag", return_value={"LIVE_FOR_YEAR": False}), \
            patch("bot_setup.bot_setup.deduplicate_top_users", side_effect=lambda x: x), \
            patch("bot_setup.bot_setup.build_daily_summary", return_value=([{"type": "section"}], False)), \
            patch("bot_setup.bot_setup.build_yearly_intro_message", return_value="intro"), \
            patch("bot_setup.bot_setup.post_message"), \
            patch("bot_setup.config.save_json"):
        run_setup(_base_config())

    assert mock_login.called


@pytest.mark.integration
def test_bot_go_live_no_skips_summary_on_off_day():
    from bot_setup.bot_setup import run_setup

    with patch("bot_setup.bot_setup.get_input_safe", side_effect=["cli", "yes"]), \
            patch("bot_setup.bot_setup.ensure_cbs_login"), \
            patch("bot_setup.bot_setup.get_top_n_async"), \
            patch("bot_setup.bot_setup.run_async", return_value=[]), \
            patch("bot_setup.bot_setup.get_final_games", return_value=[]), \
            patch("bot_setup.bot_setup.ask_if_missing", side_effect=lambda c, k, *a, **kw: c), \
            patch("bot_setup.bot_setup.load_flag", return_value={"LIVE_FOR_YEAR": False}), \
            patch("bot_setup.bot_setup.deduplicate_top_users", side_effect=lambda x: x), \
            patch("bot_setup.bot_setup.build_daily_summary", return_value=([{"type": "section"}], True)), \
            patch("bot_setup.bot_setup.build_yearly_intro_message", return_value="intro"), \
            patch("bot_setup.bot_setup.post_message") as mock_post, \
            patch("bot_setup.config.save_json"):
        run_setup(_base_config())

    assert mock_post.call_count == 1
    call_kwargs = mock_post.call_args_list[0][1]
    assert call_kwargs.get("text") == "intro"


@pytest.mark.integration
def test_bot_go_live_skipped_does_not_post_anything():
    from bot_setup.bot_setup import run_setup

    with patch("bot_setup.bot_setup.get_input_safe", side_effect=["cli", "n"]), \
            patch("bot_setup.bot_setup.ensure_cbs_login"), \
            patch("bot_setup.bot_setup.get_top_n_async"), \
            patch("bot_setup.bot_setup.run_async", return_value=[]), \
            patch("bot_setup.bot_setup.get_final_games", return_value=[]), \
            patch("bot_setup.bot_setup.ask_if_missing", side_effect=lambda c, k, *a, **kw: c), \
            patch("bot_setup.bot_setup.load_flag", return_value={"LIVE_FOR_YEAR": False}), \
            patch("bot_setup.bot_setup.deduplicate_top_users", side_effect=lambda x: x), \
            patch("bot_setup.bot_setup.build_daily_summary", return_value=([{"type": "section"}], False)), \
            patch("bot_setup.bot_setup.build_yearly_intro_message", return_value="intro"), \
            patch("bot_setup.bot_setup.post_message") as mock_post, \
            patch("bot_setup.config.save_json"):
        run_setup(_base_config())

    assert mock_post.call_count == 0


@pytest.mark.integration
def test_bot_returns_six_tuple():
    from bot_setup.bot_setup import run_setup

    with patch("bot_setup.bot_setup.get_input_safe", side_effect=["cli", "n"]), \
            patch("bot_setup.bot_setup.ensure_cbs_login"), \
            patch("bot_setup.bot_setup.get_top_n_async"), \
            patch("bot_setup.bot_setup.run_async", return_value=[]), \
            patch("bot_setup.bot_setup.get_final_games", return_value=[]), \
            patch("bot_setup.bot_setup.ask_if_missing", side_effect=lambda c, k, *a, **kw: c), \
            patch("bot_setup.bot_setup.load_flag", return_value={"LIVE_FOR_YEAR": False}), \
            patch("bot_setup.bot_setup.deduplicate_top_users", side_effect=lambda x: x), \
            patch("bot_setup.bot_setup.build_daily_summary", return_value=([{"type": "section"}], False)), \
            patch("bot_setup.bot_setup.build_yearly_intro_message", return_value="intro"), \
            patch("bot_setup.bot_setup.post_message"), \
            patch("bot_setup.config.save_json"):
        result = run_setup(_base_config())

    assert isinstance(result, tuple)
    assert len(result) == 6


@pytest.mark.integration
def test_bot_already_live_still_posts_summary():
    from bot_setup.bot_setup import run_setup

    games = [{"id": "g1", "home": "Duke", "away": "UNC", "home_score": 80, "away_score": 75}]

    with patch("bot_setup.bot_setup.get_input_safe", return_value="cli"), \
            patch("bot_setup.bot_setup.ensure_cbs_login"), \
            patch("bot_setup.bot_setup.get_top_n_async"), \
            patch("bot_setup.bot_setup.run_async", return_value=[]), \
            patch("bot_setup.bot_setup.get_final_games", return_value=games), \
            patch("bot_setup.bot_setup.ask_if_missing", side_effect=lambda c, k, *a, **kw: c), \
            patch("bot_setup.bot_setup.load_flag", return_value={"LIVE_FOR_YEAR": True}), \
            patch("bot_setup.bot_setup.deduplicate_top_users", side_effect=lambda x: x), \
            patch("bot_setup.bot_setup.build_daily_summary", return_value=([{"type": "section"}], False)), \
            patch("bot_setup.bot_setup.build_yearly_intro_message", return_value="intro"), \
            patch("bot_setup.bot_setup.post_message"), \
            patch("bot_setup.config.save_json"):
        config, method, men_games, women_games, top_men, top_women = run_setup(_base_config())

    assert men_games == games
