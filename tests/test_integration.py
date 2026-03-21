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
                   "MEN_URL": "https://www.cbssports.com/brackets/men/group/123",
                   "WOMEN_URL": "https://www.cbssports.com/brackets/women/group/456"}],
        "SLACK_WEBHOOK_URL": "",
        "MOCK_SLACK": True,
        "POST_ON_WEEKENDS": True,
        "MANUAL_TOP": ["Alice (100)", "Bob (90)", "Carol (80)"],
    }
    config.update(overrides)
    return config


def _placeholder_config(**overrides):
    """Config with empty pool URLs — browser block not entered."""
    config = _base_config()
    config["POOLS"] = [{"SOURCE": "cbs", "MEN_URL": "", "WOMEN_URL": ""}]
    config.update(overrides)
    return config


def _example_url_config(**overrides):
    """Config with example.com URLs — enters browser block but skips login."""
    config = _base_config()
    config["POOLS"] = [{"SOURCE": "cbs",
                        "MEN_URL": "https://example.com/men",
                        "WOMEN_URL": "https://example.com/women"}]
    config.update(overrides)
    return config


# ---------------------------------------------------------------------------
# Shared patch context manager
# ---------------------------------------------------------------------------

@contextmanager
def _standard_patches(**overrides):
    """
    Yields a dict of all active mocks keyed by their patch target name.
    Call as: with _standard_patches() as m: ... then inspect m["post_message"] etc.
    Individual patches can be overridden: _standard_patches(load_flag=MagicMock(...))

    NOTE: get_input_safe has no default — every test must set side_effect explicitly.
    This ensures forgotten mocks fail loudly rather than silently returning a value.
    """
    mocks = {
        "ensure_cbs_login":           MagicMock(),
        "get_top_n_async":            MagicMock(),
        "run_async":                  MagicMock(return_value=[]),
        "get_final_games":            MagicMock(return_value=[]),
        "ask_if_missing":             MagicMock(side_effect=lambda c, k, *a, **kw: c),
        "load_flag":                  MagicMock(return_value={"LIVE_FOR_YEAR": False}),
        "deduplicate_top_users":      MagicMock(side_effect=lambda x: x),
        "build_daily_summary":        MagicMock(return_value=([{"type": "section"}], False)),
        "build_yearly_intro_message": MagicMock(return_value="intro"),
        "post_message":               MagicMock(),
        "save_json":                  MagicMock(),
        "get_input_safe":             MagicMock(),  # no default — each test must set side_effect
    }
    mocks.update(overrides)

    with patch("bot_setup.bot_setup.ensure_cbs_login",           mocks["ensure_cbs_login"]), \
         patch("bot_setup.bot_setup.get_top_n_async",            mocks["get_top_n_async"]), \
         patch("bot_setup.bot_setup.run_async",                  mocks["run_async"]), \
         patch("bot_setup.bot_setup.get_final_games",            mocks["get_final_games"]), \
         patch("bot_setup.bot_setup.ask_if_missing",             mocks["ask_if_missing"]), \
         patch("bot_setup.bot_setup.load_flag",                  mocks["load_flag"]), \
         patch("bot_setup.bot_setup.deduplicate_top_users",      mocks["deduplicate_top_users"]), \
         patch("bot_setup.bot_setup.build_daily_summary",        mocks["build_daily_summary"]), \
         patch("bot_setup.bot_setup.build_yearly_intro_message", mocks["build_yearly_intro_message"]), \
         patch("bot_setup.bot_setup.post_message",               mocks["post_message"]), \
         patch("bot_setup.config.save_json",                     mocks["save_json"]), \
         patch("bot_setup.bot_setup.get_input_safe",             mocks["get_input_safe"]):
        yield mocks


# ---------------------------------------------------------------------------
# General bot behaviour
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_bot_runs_end_to_end_mock_mode():
    with _standard_patches() as m:
        m["get_input_safe"].side_effect = ["cli", "n"]
        result = run_setup(_base_config())
    assert result is not None


@pytest.mark.integration
def test_bot_returns_six_tuple():
    with _standard_patches() as m:
        m["get_input_safe"].side_effect = ["cli", "n"]
        result = run_setup(_base_config())
    assert isinstance(result, tuple)
    assert len(result) == 6


@pytest.mark.integration
def test_bot_go_live_posts_intro_and_summary():
    with _standard_patches() as m:
        m["get_input_safe"].side_effect = ["cli", "y"]
        m["build_daily_summary"].return_value = ([{"type": "section"}], False)
        run_setup(_base_config())
    assert m["post_message"].call_count >= 2


@pytest.mark.integration
def test_bot_off_day_skips_summary_post():
    """When there are no games (off day), only the intro is posted."""
    with _standard_patches() as m:
        m["get_input_safe"].side_effect = ["cli", "y"]
        m["build_daily_summary"].return_value = ([{"type": "section"}], True)  # no_games=True
        run_setup(_base_config())
    assert m["post_message"].call_count == 1
    assert m["post_message"].call_args_list[0][1].get("text") == "intro"


@pytest.mark.integration
def test_bot_go_live_skipped_does_not_post_anything():
    with _standard_patches() as m:
        m["get_input_safe"].side_effect = ["cli", "n"]
        run_setup(_base_config())
    assert m["post_message"].call_count == 0


@pytest.mark.integration
def test_bot_missing_pools_returns_early(capsys):
    with _standard_patches() as m:
        m["get_input_safe"].side_effect = ["cli"]
        run_setup(_base_config(POOLS=[]))
    assert "[ERROR]" in capsys.readouterr().out


@pytest.mark.integration
def test_bot_scraping_failure_falls_back_to_manual_top():
    with _standard_patches() as m:
        m["get_input_safe"].side_effect = ["cli", "n"]
        m["run_async"].side_effect = Exception("scrape failed")
        result = run_setup(_base_config())
    assert result is not None


@pytest.mark.integration
def test_bot_with_webhook_uses_real_post_path():
    config = _base_config(SLACK_WEBHOOK_URL="https://hooks.slack.com/fake", MOCK_SLACK=False)
    with _standard_patches() as m:
        m["get_input_safe"].side_effect = ["cli", "y"]
        run_setup(config)
    assert m["post_message"].called


@pytest.mark.integration
def test_bot_already_live_skips_go_live_prompt():
    """LIVE_FOR_YEAR=True does not skip the go-live prompt — bot still asks.
    Answering 'n' means nothing is posted."""
    with _standard_patches() as m:
        m["get_input_safe"].side_effect = ["cli", "n"]
        m["load_flag"].return_value = {"LIVE_FOR_YEAR": True}
        result = run_setup(_base_config())
    assert result is not None
    assert m["post_message"].call_count == 0


@pytest.mark.integration
def test_bot_go_live_returns_games_from_espn():
    """Games fetched from ESPN are returned in the result tuple regardless of LIVE_FOR_YEAR."""
    games = [{"id": "g1", "home": "Duke", "away": "UNC", "home_score": 80, "away_score": 75}]
    with _standard_patches() as m:
        m["get_input_safe"].side_effect = ["cli", "y"]
        m["load_flag"].return_value = {"LIVE_FOR_YEAR": True}
        m["get_final_games"].return_value = games
        config, method, men_games, women_games, top_men, top_women = run_setup(_base_config())
    assert men_games == games


# ---------------------------------------------------------------------------
# Browser / session handling
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_bot_setup_does_not_open_browser_in_tests():
    """Real playwright_state.json exists on disk — browser login is skipped."""
    with _standard_patches() as m:
        m["get_input_safe"].side_effect = ["cli", "n"]
        run_setup(_base_config())
    assert not m["ensure_cbs_login"].called


@pytest.mark.integration
def test_bot_setup_skips_browser_when_both_urls_are_empty():
    """Browser block is not entered at all when both URLs are empty strings."""
    with _standard_patches() as m:
        m["get_input_safe"].side_effect = ["cli", "", "", "n", "n"]
        run_setup(_placeholder_config())
    assert not m["ensure_cbs_login"].called


@pytest.mark.integration
def test_bot_setup_skips_browser_when_both_urls_are_example_placeholders(capsys):
    """Browser login is skipped and [WARN] logged when both URLs are example.com."""
    with _standard_patches() as m:
        m["get_input_safe"].side_effect = ["cli", "n"]
        run_setup(_example_url_config())
    assert not m["ensure_cbs_login"].called
    assert "[WARN] Both pool URLs are placeholders" in capsys.readouterr().out


@pytest.mark.integration
def test_bot_setup_skips_browser_when_valid_session_exists(capsys):
    """Browser login is skipped when a valid playwright session file already exists."""
    mock_path = MagicMock()
    mock_path.exists.return_value = True
    mock_path.stat.return_value.st_size = 1000

    with _standard_patches() as m, \
         patch("bot_setup.bot_setup.Path", return_value=mock_path):
        m["get_input_safe"].side_effect = ["cli", "n"]
        run_setup(_base_config())

    assert not m["ensure_cbs_login"].called
    assert "[INFO] Browser session found." in capsys.readouterr().out


@pytest.mark.integration
def test_bot_setup_opens_browser_when_real_urls_and_no_session():
    """Browser login is called when real URLs are present and no valid session exists."""
    mock_path = MagicMock()
    mock_path.exists.return_value = False
    mock_path.stat.return_value.st_size = 0

    with _standard_patches() as m, \
         patch("bot_setup.bot_setup.Path", return_value=mock_path):
        m["get_input_safe"].side_effect = ["cli", "n"]
        run_setup(_base_config())

    assert m["ensure_cbs_login"].called


# ---------------------------------------------------------------------------
# Leaderboard 1.5x cap
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_fetch_leaderboard_caps_at_1pt5x_top_n():
    """Results exceeding 1.5x TOP_N are trimmed — TOP_N=4 allows max 6."""
    pool = {"MEN_URL": "https://www.cbssports.com/brackets/men/group/123"}
    oversized = [f"Player {i} (100)" for i in range(8)]

    with patch("bot_setup.bot_setup.run_async", return_value=oversized), \
         patch("bot_setup.bot_setup.get_top_n_async"):
        result = _fetch_leaderboard(pool, "men", _base_config(TOP_N=4), "cli")

    assert len(result) == 6  # int(4 * 1.5)


@pytest.mark.unit
def test_fetch_leaderboard_does_not_trim_when_within_cap():
    """Results at exactly the cap are returned untouched."""
    pool = {"MEN_URL": "https://www.cbssports.com/brackets/men/group/123"}
    at_cap = [f"Player {i} (100)" for i in range(6)]  # 6 == int(4 * 1.5)

    with patch("bot_setup.bot_setup.run_async", return_value=at_cap), \
         patch("bot_setup.bot_setup.get_top_n_async"):
        result = _fetch_leaderboard(pool, "men", _base_config(TOP_N=4), "cli")

    assert len(result) == 6


@pytest.mark.unit
def test_fetch_leaderboard_cap_logged_when_trimmed(capsys):
    """A trim log message is printed when results exceed the cap."""
    pool = {"MEN_URL": "https://www.cbssports.com/brackets/men/group/123"}
    oversized = [f"Player {i} (100)" for i in range(10)]

    with patch("bot_setup.bot_setup.run_async", return_value=oversized), \
         patch("bot_setup.bot_setup.get_top_n_async"):
        _fetch_leaderboard(pool, "men", _base_config(TOP_N=4), "cli")

    assert "1.5x TOP_N cap" in capsys.readouterr().out


@pytest.mark.unit
def test_fetch_leaderboard_cap_uses_floor_not_round():
    """int() truncation is used — TOP_N=3 gives max 4, not 5."""
    pool = {"MEN_URL": "https://www.cbssports.com/brackets/men/group/123"}
    oversized = [f"Player {i} (100)" for i in range(10)]

    with patch("bot_setup.bot_setup.run_async", return_value=oversized), \
         patch("bot_setup.bot_setup.get_top_n_async"):
        result = _fetch_leaderboard(pool, "men", _base_config(TOP_N=3), "cli")

    assert len(result) == 4  # int(3 * 1.5) = 4
