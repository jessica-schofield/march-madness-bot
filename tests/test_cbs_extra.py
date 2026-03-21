import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sources.cbs import _extract_espn_group_id, _parse_espn_api_response, detect_site, deduplicate_top_users, _format_user, _build_top_n


# ---------------------------------------------------------------------------
# detect_site
# ---------------------------------------------------------------------------

def test_detect_site_cbs():
    assert detect_site("https://www.cbssports.com/bracket/games/") == "cbs"


def test_detect_site_espn():
    assert detect_site("https://fantasy.espn.com/games/tournament-challenge-bracket-2026/group?id=abc") == "espn"


def test_detect_site_yahoo():
    assert detect_site("https://sports.yahoo.com/bracket/groups/12345") == "yahoo"


def test_detect_site_unknown():
    assert detect_site("https://example.com/bracket") == "unknown"


def test_detect_site_none():
    assert detect_site(None) == "unknown"


def test_detect_site_empty_string():
    assert detect_site("") == "unknown"


def test_detect_site_cbs_subdomain():
    assert detect_site("https://brackets.cbssports.com/pool") == "cbs"


def test_detect_site_espn_subdomain():
    assert detect_site("https://fantasy.espn.com/games/tournament-challenge-bracket-women-2026/group?id=abc") == "espn"


def test_detect_site_uppercase_url_still_works():
    assert detect_site("https://www.CBSSPORTS.COM/bracket/") == "cbs"


def test_detect_site_yahoo_fantasy_subdomain():
    assert detect_site("https://tournament.fantasysports.yahoo.com/t1/group/1") == "yahoo"


def test_detect_site_returns_string():
    assert isinstance(detect_site("https://example.com"), str)


# ---------------------------------------------------------------------------
# _extract_espn_group_id
# ---------------------------------------------------------------------------

def test_extract_espn_group_id_id_param():
    url = "https://fantasy.espn.com/games/tournament-challenge-bracket-2026/group?id=b1e6fb01-f1eb-450b-8b77-0b994d62563e"
    assert _extract_espn_group_id(url) == "b1e6fb01-f1eb-450b-8b77-0b994d62563e"


def test_extract_espn_group_id_groupID_param():
    url = "https://fantasy.espn.com/games/tournament-challenge-bracket-2026/group?groupID=b1e6fb01-f1eb-450b-8b77-0b994d62563e"
    assert _extract_espn_group_id(url) == "b1e6fb01-f1eb-450b-8b77-0b994d62563e"


def test_extract_espn_group_id_case_insensitive():
    url = "https://fantasy.espn.com/group?GROUPID=abc-def-1234567890"
    assert _extract_espn_group_id(url) == "abc-def-1234567890"


def test_extract_espn_group_id_missing_returns_none():
    assert _extract_espn_group_id("https://fantasy.espn.com/games/tournament-challenge-bracket-2026/") is None


def test_extract_espn_group_id_no_url_returns_none():
    assert _extract_espn_group_id("") is None


def test_extract_espn_group_id_short_value_ignored():
    assert _extract_espn_group_id("https://fantasy.espn.com/group?id=abc") is None


def test_extract_espn_group_id_mid_querystring():
    url = "https://fantasy.espn.com/group?foo=bar&id=b1e6fb01-f1eb-450b-8b77-0b994d62563e&baz=1"
    assert _extract_espn_group_id(url) == "b1e6fb01-f1eb-450b-8b77-0b994d62563e"


def test_extract_espn_group_id_returns_string():
    url = "https://fantasy.espn.com/group?id=b1e6fb01-f1eb-450b-8b77-0b994d62563e"
    assert isinstance(_extract_espn_group_id(url), str)


def test_extract_espn_group_id_numeric_id():
    url = "https://fantasy.espn.com/group?id=1234567890"
    assert _extract_espn_group_id(url) == "1234567890"


# ---------------------------------------------------------------------------
# _parse_espn_api_response
# ---------------------------------------------------------------------------

def _make_entry(rank, name, points, is_viewer=False):
    return {"rank": rank, "entryName": name, "totalPoints": points, "isViewer": is_viewer}


def test_parse_espn_api_response_basic():
    data = {"entries": [_make_entry(1, "Alice", 120), _make_entry(2, "Bob", 90)]}
    result = _parse_espn_api_response(data)
    assert result == [(1, "Alice", 120), (2, "Bob", 90)]


def test_parse_espn_api_response_empty_entries():
    assert _parse_espn_api_response({"entries": []}) == []


def test_parse_espn_api_response_no_entries_key():
    assert _parse_espn_api_response({}) == []


def test_parse_espn_api_response_skips_viewer():
    data = {"entries": [
        _make_entry(1, "Alice", 120, is_viewer=True),
        _make_entry(2, "Bob", 90),
    ]}
    result = _parse_espn_api_response(data)
    assert len(result) == 1
    assert result[0] == (2, "Bob", 90)


def test_parse_espn_api_response_skips_logged_in_user_by_name():
    data = {"entries": [
        _make_entry(1, "Alice", 120),
        _make_entry(2, "Bob", 90),
    ]}
    result = _parse_espn_api_response(data, logged_in_display_name="Alice")
    assert len(result) == 1
    assert result[0] == (2, "Bob", 90)


def test_parse_espn_api_response_deduplicates():
    data = {"entries": [
        _make_entry(1, "Alice", 120),
        _make_entry(1, "Alice", 120),
        _make_entry(2, "Bob", 90),
    ]}
    result = _parse_espn_api_response(data)
    assert len(result) == 2


def test_parse_espn_api_response_sorted_by_rank():
    data = {"entries": [
        _make_entry(3, "Carol", 80),
        _make_entry(1, "Alice", 120),
        _make_entry(2, "Bob", 90),
    ]}
    result = _parse_espn_api_response(data)
    assert [r[0] for r in result] == [1, 2, 3]


def test_parse_espn_api_response_falls_back_to_display_name():
    entry = {"rank": 1, "displayName": "Alice", "totalPoints": 100, "isViewer": False}
    result = _parse_espn_api_response({"entries": [entry]})
    assert result == [(1, "Alice", 100)]


def test_parse_espn_api_response_falls_back_to_points_field():
    entry = {"rank": 1, "entryName": "Alice", "points": 100, "isViewer": False}
    result = _parse_espn_api_response({"entries": [entry]})
    assert result == [(1, "Alice", 100)]


def test_parse_espn_api_response_skips_entry_with_no_name():
    data = {"entries": [
        {"rank": 1, "totalPoints": 100, "isViewer": False},
        _make_entry(2, "Bob", 90),
    ]}
    result = _parse_espn_api_response(data)
    assert len(result) == 1
    assert result[0][1] == "Bob"


def test_parse_espn_api_response_zero_points_allowed():
    data = {"entries": [_make_entry(1, "Alice", 0)]}
    result = _parse_espn_api_response(data)
    assert result == [(1, "Alice", 0)]


def test_parse_espn_api_response_returns_tuples():
    data = {"entries": [_make_entry(1, "Alice", 50)]}
    result = _parse_espn_api_response(data)
    assert isinstance(result[0], tuple)
    rank, name, pts = result[0]
    assert isinstance(rank, int)
    assert isinstance(name, str)
    assert isinstance(pts, int)


def test_parse_espn_api_response_skips_entry_with_no_rank():
    data = {"entries": [
        {"entryName": "Alice", "totalPoints": 100, "isViewer": False},
        _make_entry(2, "Bob", 90),
    ]}
    result = _parse_espn_api_response(data)
    assert len(result) == 1
    assert result[0][1] == "Bob"


def test_parse_espn_api_response_all_viewers_returns_empty():
    data = {"entries": [
        _make_entry(1, "Alice", 120, is_viewer=True),
        _make_entry(2, "Bob", 90, is_viewer=True),
    ]}
    assert _parse_espn_api_response(data) == []


def test_parse_espn_api_response_logged_in_name_no_match_keeps_all():
    data = {"entries": [_make_entry(1, "Alice", 120), _make_entry(2, "Bob", 90)]}
    result = _parse_espn_api_response(data, logged_in_display_name="Carol")
    assert len(result) == 2


def test_parse_espn_api_response_large_leaderboard():
    entries = [_make_entry(i, f"User{i}", 200 - i) for i in range(1, 101)]
    result = _parse_espn_api_response({"entries": entries})
    assert len(result) == 100
    assert result[0] == (1, "User1", 199)
    assert result[-1] == (100, "User100", 100)


def test_parse_espn_api_response_tied_ranks_both_included():
    data = {"entries": [
        _make_entry(1, "Alice", 120),
        _make_entry(1, "Bob", 120),
        _make_entry(3, "Carol", 80),
    ]}
    result = _parse_espn_api_response(data)
    assert len(result) == 3
    assert [r[0] for r in result].count(1) == 2


def test_parse_espn_api_response_uses_standing_fallback():
    entry = {"standing": 2, "entryName": "Bob", "totalPoints": 90, "isViewer": False}
    result = _parse_espn_api_response({"entries": [entry]})
    assert result == [(2, "Bob", 90)]


def test_parse_espn_api_response_falls_back_to_name_field():
    entry = {"rank": 1, "name": "Alice", "totalPoints": 50, "isViewer": False}
    result = _parse_espn_api_response({"entries": [entry]})
    assert result == [(1, "Alice", 50)]


# ---------------------------------------------------------------------------
# _format_user
# ---------------------------------------------------------------------------

def test_format_user_with_points():
    assert _format_user(1, "Alice", 120) == "Alice (120 pts)"


def test_format_user_single_point():
    assert _format_user(1, "Alice", 1) == "Alice (1 pt)"


def test_format_user_zero_points_first():
    assert _format_user(1, "Alice", 0) == "Alice (1st place)"


def test_format_user_zero_points_second():
    assert _format_user(2, "Bob", 0) == "Bob (2nd place)"


def test_format_user_zero_points_third():
    assert _format_user(3, "Carol", 0) == "Carol (3rd place)"


def test_format_user_zero_points_fourth():
    assert _format_user(4, "Dave", 0) == "Dave (4th place)"


def test_format_user_zero_points_eleventh():
    assert _format_user(11, "Eve", 0) == "Eve (11th place)"


def test_format_user_returns_string():
    assert isinstance(_format_user(1, "Alice", 100), str)


# ---------------------------------------------------------------------------
# _build_top_n
# ---------------------------------------------------------------------------

def test_build_top_n_empty():
    assert _build_top_n([], 3) == []


def test_build_top_n_basic():
    users = [(1, "Alice", 120), (2, "Bob", 90), (3, "Carol", 80), (4, "Dave", 70)]
    result = _build_top_n(users, 3)
    assert len(result) == 3
    assert "Alice" in result[0]
    assert "Bob" in result[1]
    assert "Carol" in result[2]


def test_build_top_n_respects_ties():
    users = [(1, "Alice", 120), (1, "Bob", 120), (3, "Carol", 80)]
    result = _build_top_n(users, 1)
    assert len(result) == 2


def test_build_top_n_n_larger_than_list():
    users = [(1, "Alice", 120), (2, "Bob", 90)]
    result = _build_top_n(users, 10)
    assert len(result) == 2


def test_build_top_n_sorts_by_rank():
    users = [(3, "Carol", 80), (1, "Alice", 120), (2, "Bob", 90)]
    result = _build_top_n(users, 3)
    assert "Alice" in result[0]
    assert "Bob" in result[1]
    assert "Carol" in result[2]


def test_build_top_n_returns_list_of_strings():
    users = [(1, "Alice", 120)]
    result = _build_top_n(users, 1)
    assert isinstance(result, list)
    assert isinstance(result[0], str)


# ---------------------------------------------------------------------------
# deduplicate_top_users
# ---------------------------------------------------------------------------

def test_deduplicate_top_users_no_dupes():
    result = deduplicate_top_users(["Alice (120 pts)", "Bob (90 pts)"])
    assert result == ["Alice (120 pts)", "Bob (90 pts)"]


def test_deduplicate_top_users_removes_duplicate():
    result = deduplicate_top_users(["Alice (120 pts)", "Alice (120 pts)", "Bob (90 pts)"])
    assert result == ["Alice (120 pts)", "Bob (90 pts)"]


def test_deduplicate_top_users_empty():
    assert deduplicate_top_users([]) == []


def test_deduplicate_top_users_dict_format():
    users = [{"name": "Alice", "pts": 120}, {"name": "Alice", "pts": 120}, {"name": "Bob", "pts": 90}]
    result = deduplicate_top_users(users)
    assert len(result) == 2
    assert result[0]["name"] == "Alice"
    assert result[1]["name"] == "Bob"


def test_deduplicate_top_users_preserves_order():
    result = deduplicate_top_users(["Carol (80 pts)", "Alice (120 pts)", "Bob (90 pts)"])
    assert result[0] == "Carol (80 pts)"
    assert result[1] == "Alice (120 pts)"
    assert result[2] == "Bob (90 pts)"


def test_deduplicate_top_users_single_entry():
    result = deduplicate_top_users(["Alice (120 pts)"])
    assert result == ["Alice (120 pts)"]