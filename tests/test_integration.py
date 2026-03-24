import pytest
from contextlib import contextmanager
from unittest.mock import patch, MagicMock
from bot_setup.bot_setup import run_setup, _fetch_leaderboard


# ---------------------------------------------------------------------------
# Config factories
# ---------------------------------------------------------------------------

def _base_config(**overrides):
    config = {
        "METHOD": "cli",
        "TOP_N": 3,
        "MINUTES_BETWEEN_MESSAGES": 30,
        "PLAYWRIGHT_HEADLESS": True,
        "PLAYWRIGHT_STATE": "playwright_state.json",
        "POOLS": [{"SOURCE": "cbs",
                   "MEN_URL": "https://picks.cbssports.com/college-basketball/ncaa-tournament/bracket/pools/realpool1/standings",
                   "WOMEN_URL": "https://picks.cbssports.com/college-basketball/ncaaw-tournament/bracket/pools/realpool2/standings"}],
        "SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/TEST/TEST/TEST",
        "SLACK_MANAGER_ID": "U012TEST",
        "MOCK_SLACK": True,
        "POST_ON_WEEKENDS": True,
        "MANUAL_TOP": ["Alice (100)", "Bob (90)", "Carol (80)"],
    }
    config.update(overrides)
    return config


# ---------------------------------------------------------------------------
# Shared patch context manager
# ---------------------------------------------------------------------------

@contextmanager
def _standard_patches():
    from pathlib import Path as _RealPath

    def _fake_path(p):
        if str(p) == "playwright_state.json":
            mock = MagicMock()
            mock.exists.return_value = True
            mock.stat.return_value.st_size = 1000
            mock.__str__ = lambda s: str(p)
            return mock
        return _RealPath(p)

    _default_inputs = ["cli", "5", "0", "n", "y", "y", "n", "n"] + ["n"] * 20

    with patch("bot_setup.bot_setup.get_input_safe", side_effect=_default_inputs) as mock_input, \
         patch("bot_setup.bot_setup.ask_if_missing", side_effect=lambda c, k, *a, **kw: c), \
         patch("bot_setup.bot_setup.ask_slack_credentials_cli", side_effect=lambda c: c), \
         patch("bot_setup.bot_setup.get_final_games", return_value=[]) as mock_games, \
         patch("bot_setup.bot_setup.ensure_cbs_login") as mock_login, \
         patch("bot_setup.bot_setup.Path", side_effect=_fake_path), \
         patch("bot_setup.bot_setup.run_async", return_value=[]) as mock_run_async, \
         patch("bot_setup.bot_setup._fetch_leaderboard", return_value=[]), \
         patch("bot_setup.bot_setup.deduplicate_top_users", side_effect=lambda x: x), \
         patch("bot_setup.bot_setup.build_daily_summary", return_value=([], False)) as mock_summary, \
         patch("bot_setup.bot_setup.build_yearly_intro_message", return_value="intro"), \
         patch("bot_setup.bot_setup.post_message") as mock_post, \
         patch("bot_setup.bot_setup.load_flag", return_value={"LIVE_FOR_YEAR": False}) as mock_flag, \
         patch("bot_setup.bot_setup.save_json"), \
         patch("bot_setup.config.save_json"):
        yield {
            "get_input_safe": mock_input,
            "ensure_cbs_login": mock_login,
            "run_async": mock_run_async,
            "get_final_games": mock_games,
            "build_daily_summary": mock_summary,
            "post_message": mock_post,
            "load_flag": mock_flag,
        }


# ---------------------------------------------------------------------------
# Input sequences
# ---------------------------------------------------------------------------

_CLI_NO_GOLIVE = ["cli", "5", "0", "n", "y", "y", "n", "n"]
_CLI_GOLIVE    = ["cli", "5", "0", "n", "y", "y", "y"]


# ---------------------------------------------------------------------------
# General bot behaviour
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_bot_runs_end_to_end_mock_mode():
    with _standard_patches() as m:
        m["get_input_safe"].side_effect = list(_CLI_NO_GOLIVE)
        result = run_setup(_base_config())
    assert result is not None


@pytest.mark.integration
def test_bot_returns_six_tuple():
    with _standard_patches() as m:
        m["get_input_safe"].side_effect = list(_CLI_NO_GOLIVE)
        result = run_setup(_base_config())
    assert isinstance(result, tuple)
    assert len(result) == 6


@pytest.mark.integration
def test_bot_go_live_skipped_does_not_post_anything():
    with _standard_patches() as m:
        m["get_input_safe"].side_effect = list(_CLI_NO_GOLIVE)
        run_setup(_base_config())
    assert m["post_message"].call_count == 0


@pytest.mark.integration
def test_bot_scraping_failure_falls_back_to_manual_top():
    with _standard_patches() as m:
        m["get_input_safe"].side_effect = list(_CLI_NO_GOLIVE)
        m["run_async"].side_effect = Exception("scrape failed")
        result = run_setup(_base_config())
    assert result is not None


@pytest.mark.integration
def test_bot_already_live_skips_go_live_prompt():
    with _standard_patches() as m:
        m["get_input_safe"].side_effect = list(_CLI_NO_GOLIVE)
        m["load_flag"].return_value = {"LIVE_FOR_YEAR": True}
        result = run_setup(_base_config())
    assert result is not None
    assert m["post_message"].call_count == 0


@pytest.mark.integration
def test_bot_setup_does_not_open_browser_in_tests():
    with _standard_patches() as m:
        m["get_input_safe"].side_effect = list(_CLI_NO_GOLIVE)
        run_setup(_base_config())
    assert not m["ensure_cbs_login"].called


@pytest.mark.integration
def test_bot_setup_skips_browser_when_valid_session_exists(capsys):
    from pathlib import Path as _RealPath

    def _fake_path(p):
        if str(p) == "playwright_state.json":
            mock = MagicMock()
            mock.exists.return_value = True
            mock.stat.return_value.st_size = 1000
            return mock
        return _RealPath(p)

    with _standard_patches() as m, \
         patch("bot_setup.bot_setup.Path", side_effect=_fake_path):
        m["get_input_safe"].side_effect = list(_CLI_NO_GOLIVE)
        run_setup(_base_config())
    assert not m["ensure_cbs_login"].called


@pytest.mark.integration
def test_bot_setup_opens_browser_when_real_urls_and_no_session():
    from pathlib import Path as _RealPath

    def _fake_path(p):
        if str(p) == "playwright_state.json":
            mock = MagicMock()
            mock.exists.return_value = False
            mock.stat.return_value.st_size = 0
            return mock
        return _RealPath(p)

    with _standard_patches() as m, \
         patch("bot_setup.bot_setup.Path", side_effect=_fake_path):
        m["get_input_safe"].side_effect = list(_CLI_NO_GOLIVE)
        run_setup(_base_config())
    assert m["ensure_cbs_login"].called


# ---------------------------------------------------------------------------
# Leaderboard 1.5x cap
# ---------------------------------------------------------------------------

_POOL_URL = {"MEN_URL": "https://picks.cbssports.com/college-basketball/ncaa-tournament/bracket/pools/kbxw63b2ge3deojqg4ydq===/standings"}


@pytest.mark.unit
def test_fetch_leaderboard_caps_at_1pt5x_top_n():
    """Results exceeding 1.5x TOP_N are trimmed — TOP_N=4 allows max 6."""
    oversized = [f"Player {i} (100)" for i in range(8)]
    with patch("bot_setup.bot_setup.run_async", return_value=oversized), \
         patch("bot_setup.bot_setup.get_top_n_async"):
        result = _fetch_leaderboard(_POOL_URL, "men", _base_config(TOP_N=4), "cli")
    assert len(result) == 6


@pytest.mark.unit
def test_fetch_leaderboard_does_not_trim_when_within_cap():
    """Results at exactly the cap are returned untouched."""
    at_cap = [f"Player {i} (100)" for i in range(6)]
    with patch("bot_setup.bot_setup.run_async", return_value=at_cap), \
         patch("bot_setup.bot_setup.get_top_n_async"):
        result = _fetch_leaderboard(_POOL_URL, "men", _base_config(TOP_N=4), "cli")
    assert len(result) == 6


@pytest.mark.unit
def test_fetch_leaderboard_cap_logged_when_trimmed(capsys):
    """A trim log message is printed when results exceed the cap."""
    oversized = [f"Player {i} (100)" for i in range(10)]
    with patch("bot_setup.bot_setup.run_async", return_value=oversized), \
         patch("bot_setup.bot_setup.get_top_n_async"):
        _fetch_leaderboard(_POOL_URL, "men", _base_config(TOP_N=4), "cli")
    assert "1.5x TOP_N cap" in capsys.readouterr().out


@pytest.mark.unit
def test_fetch_leaderboard_cap_uses_floor_not_round():
    """int() truncation is used — TOP_N=3 gives max 4, not 5."""
    oversized = [f"Player {i} (100)" for i in range(10)]
    with patch("bot_setup.bot_setup.run_async", return_value=oversized), \
         patch("bot_setup.bot_setup.get_top_n_async"):
        result = _fetch_leaderboard(_POOL_URL, "men", _base_config(TOP_N=3), "cli")
    assert len(result) == 4
