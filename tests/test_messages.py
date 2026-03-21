# ---------------------------------------------------------------------------
# messages.py tests
# Covers: is_upset, format_leaderboard, parse_pts, calculate_movers,
#         build_daily_summary, build_yearly_intro_message
# No real file I/O — LAST_RANKINGS_FILE load/save is mocked throughout.
# ---------------------------------------------------------------------------

import pytest
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_EMPTY_RANKINGS = {"men": [], "women": []}

_BASE_CONFIG = {
    "TOP_N": 5,
    "POST_WEEKENDS": False,
    "SEND_GAME_UPDATES": True,
    "SEND_DAILY_SUMMARY": True,
    "MINUTES_BETWEEN_MESSAGES": 60,
    "POOLS": [{"MEN_URL": "", "WOMEN_URL": ""}],
}


def _game(home="TeamA", away="TeamB", home_score=70, away_score=65,
          home_seed=1, away_seed=8, gender="men"):
    return {
        "id": f"{home}-{away}",
        "home": home,
        "away": away,
        "home_score": home_score,
        "away_score": away_score,
        "home_seed": home_seed,
        "away_seed": away_seed,
        "gender": gender,
    }


def _config(**overrides):
    """Return a copy of _BASE_CONFIG with any overrides applied."""
    return {**_BASE_CONFIG, **overrides}


def _all_text(blocks):
    """Extract all text from a list of Slack blocks."""
    return " ".join(b.get("text", {}).get("text", "") for b in blocks)


# ---------------------------------------------------------------------------
# is_upset
# ---------------------------------------------------------------------------

def test_is_upset_lower_seed_wins_home():
    from messages import is_upset
    assert is_upset(80, 70, 8, 1) is True


def test_is_upset_lower_seed_wins_away():
    from messages import is_upset
    assert is_upset(70, 80, 2, 10) is True


def test_is_upset_favourite_wins():
    from messages import is_upset
    assert is_upset(80, 70, 1, 8) is False


def test_is_upset_equal_seeds():
    from messages import is_upset
    assert is_upset(80, 70, 4, 4) is False


@pytest.mark.parametrize("home_seed,away_seed", [
    (None, None),
    (0, 5),
])
def test_is_upset_invalid_seeds_return_false(home_seed, away_seed):
    from messages import is_upset
    assert is_upset(80, 70, home_seed, away_seed) is False


def test_is_upset_invalid_seed_string_returns_false():
    from messages import is_upset
    assert is_upset(80, 70, "one", "eight") is False


@pytest.mark.parametrize("home_score,away_score,home_seed,away_seed,expected", [
    (80, 70, "1",  "10", False),  # favourite wins
    (80, 70, "10", "1",  True),   # upset — lower seed home wins
    (70, 80, "1",  "10", True),   # upset — lower seed away wins
    # "9" > "10" as strings but 9 < 10 as ints — verifies int cast
    (80, 70, "9",  "10", False),  # 9 is higher seed, wins — not upset
])
def test_is_upset_string_seeds(home_score, away_score, home_seed, away_seed, expected):
    from messages import is_upset
    assert is_upset(home_score, away_score, home_seed, away_seed) is expected


# ---------------------------------------------------------------------------
# format_leaderboard
# ---------------------------------------------------------------------------

def test_format_leaderboard_empty():
    from messages import format_leaderboard
    assert format_leaderboard([]) == "_No data yet_"


def test_format_leaderboard_single_entry():
    from messages import format_leaderboard
    result = format_leaderboard(["Alice (100 pts)"])
    assert "Alice" in result
    assert "1." in result


def test_format_leaderboard_sequential_ranks():
    from messages import format_leaderboard
    entries = ["Alice (100 pts)", "Bob (90 pts)", "Carol (80 pts)"]
    lines = format_leaderboard(entries).splitlines()
    assert lines[0].startswith("1.")
    assert lines[1].startswith("2.")
    assert lines[2].startswith("3.")


def test_format_leaderboard_tied_players_share_rank():
    from messages import format_leaderboard
    entries = ["Alice (100 pts)", "Bob (100 pts)", "Carol (80 pts)"]
    lines = format_leaderboard(entries).splitlines()
    assert lines[0].startswith("1.")
    assert lines[1].startswith("1.")
    assert lines[2].startswith("3.")


# ---------------------------------------------------------------------------
# parse_pts
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("entry,expected", [
    ("Alice (120 pts)", 120),
    ("Alice (0 pts)",   0),
    ("no points here",  None),
])
def test_parse_pts(entry, expected):
    from messages import parse_pts
    assert parse_pts(entry) == expected


# ---------------------------------------------------------------------------
# calculate_movers
# ---------------------------------------------------------------------------

def test_calculate_movers_returns_biggest_riser():
    from messages import calculate_movers
    old = ["Alice (100 pts)", "Bob (90 pts)"]
    new = ["Alice (120 pts)", "Bob (95 pts)"]
    result = calculate_movers(new, old)
    assert "Alice" in result
    assert "20" in result


def test_calculate_movers_picks_largest_gain():
    from messages import calculate_movers
    old = ["Alice (100 pts)", "Bob (100 pts)"]
    new = ["Alice (110 pts)", "Bob (130 pts)"]
    result = calculate_movers(new, old)
    assert "Bob" in result
    assert "30" in result


@pytest.mark.parametrize("new,old", [
    (["Alice (100 pts)", "Bob (90 pts)"], ["Alice (100 pts)", "Bob (90 pts)"]),  # no change
    (["Alice (100 pts)"], []),   # empty old
    ([], ["Alice (100 pts)"]),   # empty new
])
def test_calculate_movers_returns_none(new, old):
    from messages import calculate_movers
    assert calculate_movers(new, old) is None


def test_calculate_movers_new_user_not_in_old_ignored():
    from messages import calculate_movers
    old = ["Alice (100 pts)"]
    new = ["Alice (100 pts)", "NewPerson (50 pts)"]
    # Alice unchanged, NewPerson has no baseline — expect None
    assert calculate_movers(new, old) is None


# ---------------------------------------------------------------------------
# build_daily_summary
# ---------------------------------------------------------------------------

@patch("messages.save_json")
@patch("messages.load_json", return_value=_EMPTY_RANKINGS)
def test_build_daily_summary_returns_tuple(mock_load, mock_save):
    from messages import build_daily_summary
    blocks, no_games = build_daily_summary([], [], [], [])
    assert isinstance(blocks, list)
    assert isinstance(no_games, bool)


@pytest.mark.parametrize("men_games,women_games,expected_no_games", [
    ([], [],       True),
    ([_game()], [], False),
])
@patch("messages.save_json")
@patch("messages.load_json", return_value=_EMPTY_RANKINGS)
def test_build_daily_summary_no_games_flag(mock_load, mock_save, men_games, women_games, expected_no_games):
    from messages import build_daily_summary
    _, no_games = build_daily_summary(men_games, women_games, [], [])
    assert no_games is expected_no_games


@patch("messages.save_json")
@patch("messages.load_json", return_value=_EMPTY_RANKINGS)
def test_build_daily_summary_off_day_message(mock_load, mock_save):
    from messages import build_daily_summary
    blocks, _ = build_daily_summary([], [], [], [])
    text = _all_text(blocks).lower()
    assert "no games" in text or "rest day" in text


@patch("messages.save_json")
@patch("messages.load_json", return_value=_EMPTY_RANKINGS)
def test_build_daily_summary_includes_leaderboard(mock_load, mock_save):
    from messages import build_daily_summary
    top_men = ["Alice (100 pts)", "Bob (90 pts)"]
    blocks, _ = build_daily_summary([], [], top_men, [], top_n=5)
    text = _all_text(blocks)
    assert "Alice" in text
    assert "Bob" in text


@patch("messages.save_json")
@patch("messages.load_json", return_value=_EMPTY_RANKINGS)
def test_build_daily_summary_upset_marker(mock_load, mock_save):
    from messages import build_daily_summary
    game = _game(home_score=70, away_score=80, home_seed=1, away_seed=10)
    blocks, _ = build_daily_summary([game], [], [], [])
    text = _all_text(blocks)
    assert "⚡" in text or "🔥" in text


@patch("messages.save_json")
@patch("messages.load_json", return_value=_EMPTY_RANKINGS)
def test_build_daily_summary_men_url_linked(mock_load, mock_save):
    from messages import build_daily_summary
    blocks, _ = build_daily_summary([], [], ["Alice (100 pts)"], [],
                                    men_url="https://example.com/men")
    assert "https://example.com/men" in _all_text(blocks)


@patch("messages.save_json")
@patch("messages.load_json", return_value={"men": ["Alice (80 pts)"], "women": []})
def test_build_daily_summary_shows_movers(mock_load, mock_save):
    from messages import build_daily_summary
    blocks, _ = build_daily_summary([], [], ["Alice (100 pts)"], [])
    assert "Alice" in _all_text(blocks)


@patch("messages.save_json")
@patch("messages.load_json", return_value=_EMPTY_RANKINGS)
def test_build_daily_summary_saves_rankings(mock_load, mock_save):
    from messages import build_daily_summary
    build_daily_summary([], [], ["Alice (100 pts)"], [])
    assert mock_save.called


@patch("messages.save_json")
@patch("messages.load_json", return_value=_EMPTY_RANKINGS)
def test_build_daily_summary_none_games_treated_as_empty(mock_load, mock_save):
    from messages import build_daily_summary
    blocks, no_games = build_daily_summary(None, None, [], [])
    assert no_games is True


# ---------------------------------------------------------------------------
# build_yearly_intro_message
# ---------------------------------------------------------------------------

def test_build_yearly_intro_message_contains_top_n():
    from messages import build_yearly_intro_message
    result = build_yearly_intro_message(_config(TOP_N=7))
    assert "7" in result


def test_build_yearly_intro_message_shows_all_pool_urls():
    from messages import build_yearly_intro_message
    result = build_yearly_intro_message(_config(POOLS=[
        {"MEN_URL": "https://cbs.com/men",  "WOMEN_URL": "https://cbs.com/women"},
        {"MEN_URL": "https://espn.com/men", "WOMEN_URL": ""},
    ]))
    assert "https://cbs.com/men" in result
    assert "https://espn.com/men" in result


def test_build_yearly_intro_message_no_url_shows_placeholder():
    from messages import build_yearly_intro_message
    result = build_yearly_intro_message(_config(SEND_GAME_UPDATES=False)).lower()
    assert "no url" in result


@pytest.mark.parametrize("pools", [
    [],
    # missing key handled in next test
])
def test_build_yearly_intro_message_empty_pools(pools):
    from messages import build_yearly_intro_message
    result = build_yearly_intro_message(_config(POOLS=pools)).lower()
    assert "no pools" in result or "no pools configured" in result


def test_build_yearly_intro_message_missing_pools_key():
    from messages import build_yearly_intro_message
    config = {k: v for k, v in _BASE_CONFIG.items() if k != "POOLS"}
    result = build_yearly_intro_message(config)
    assert isinstance(result, str)


def test_build_yearly_intro_message_weekends_on():
    from messages import build_yearly_intro_message
    result = build_yearly_intro_message(_config(POST_WEEKENDS=True)).lower()
    assert "yes" in result


def test_build_yearly_intro_message_game_updates_off():
    from messages import build_yearly_intro_message
    result = build_yearly_intro_message(_config(SEND_GAME_UPDATES=False)).lower()
    assert "off" in result
