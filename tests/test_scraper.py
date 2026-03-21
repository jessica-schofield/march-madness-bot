"""
Unit tests for sources/cbs.py — scraper logic, URL detection, and data parsing.
These tests are fast (no browser/network) and will catch regressions when
CBS/ESPN/Yahoo change their page structure.
"""
import pytest
from sources.cbs import (
    detect_site,
    _extract_espn_group_id,
    _parse_espn_api_response,
    _build_top_n,
    _format_user,
    deduplicate_top_users,
    _get_espn_cookies,
    same_domain,
)
from bot_setup.bot_setup import _is_placeholder_url


# ── detect_site ──────────────────────────────────────────────────────────────

class TestDetectSite:
    def test_cbssports_com(self):
        assert detect_site("https://cbssports.com/brackets/men/group/123") == "cbs"

    def test_picks_cbssports_com(self):
        """picks.cbssports.com must be recognised as CBS — this was the live regression."""
        assert detect_site(
            "https://picks.cbssports.com/college-basketball/ncaa-tournament/bracket/pools/abc123/standings"
        ) == "cbs"

    def test_www_cbssports_com(self):
        assert detect_site("https://www.cbssports.com/brackets/women/group/456") == "cbs"

    def test_espn(self):
        assert detect_site(
            "https://fantasy.espn.com/games/tournament-challenge-bracket-2026/group?id=abc"
        ) == "espn"

    def test_yahoo(self):
        assert detect_site("https://tournament.fantasysports.yahoo.com/t1/group/123") == "yahoo"

    def test_unknown(self):
        assert detect_site("https://example.com/brackets") == "unknown"

    def test_empty(self):
        assert detect_site("") == "unknown"

    def test_none(self):
        assert detect_site(None) == "unknown"


# ── same_domain ───────────────────────────────────────────────────────────────

class TestSameDomain:
    def test_same(self):
        assert same_domain("https://cbssports.com/a", "https://cbssports.com/b") is True

    def test_different(self):
        assert same_domain("https://cbssports.com/a", "https://espn.com/b") is False

    def test_empty(self):
        assert same_domain("", "https://cbssports.com") is False

    def test_none(self):
        assert same_domain(None, "https://cbssports.com") is False


# ── ESPN group ID extraction ──────────────────────────────────────────────────

class TestExtractEspnGroupId:
    def test_id_param(self):
        url = "https://fantasy.espn.com/games/tournament-challenge-bracket-2026/group?id=b1e6fb01-f1eb-450b-8b77-0b994d62563e"
        assert _extract_espn_group_id(url) == "b1e6fb01-f1eb-450b-8b77-0b994d62563e"

    def test_groupID_param(self):
        url = "https://fantasy.espn.com/games/tournament-challenge-bracket-2026/group?groupID=b1e6fb01-f1eb-450b-8b77"
        assert _extract_espn_group_id(url) == "b1e6fb01-f1eb-450b-8b77"

    def test_no_id(self):
        assert _extract_espn_group_id("https://fantasy.espn.com/games/tcb-2026/") is None

    def test_empty(self):
        assert _extract_espn_group_id("") is None


# ── ESPN API response parsing ─────────────────────────────────────────────────

class TestParseEspnApiResponse:
    def _make_entry(self, rank, name, points, is_viewer=False):
        return {
            "rank": rank,
            "entryName": name,
            "totalPoints": points,
            "isViewer": is_viewer,
        }

    def test_basic_parsing(self):
        data = {"entries": [
            self._make_entry(1, "Alice", 120),
            self._make_entry(2, "Bob", 100),
            self._make_entry(3, "Carol", 80),
        ]}
        result = _parse_espn_api_response(data)
        assert result == [(1, "Alice", 120), (2, "Bob", 100), (3, "Carol", 80)]

    def test_viewer_entry_excluded(self):
        data = {"entries": [
            self._make_entry(1, "Alice", 120, is_viewer=True),
            self._make_entry(2, "Bob", 100),
        ]}
        result = _parse_espn_api_response(data)
        assert len(result) == 1
        assert result[0][1] == "Bob"

    def test_empty_entries(self):
        assert _parse_espn_api_response({"entries": []}) == []

    def test_missing_entries_key(self):
        assert _parse_espn_api_response({}) == []

    def test_duplicate_rank_name_deduped(self):
        data = {"entries": [
            self._make_entry(1, "Alice", 120),
            self._make_entry(1, "Alice", 120),  # duplicate
        ]}
        result = _parse_espn_api_response(data)
        assert len(result) == 1

    def test_sorted_by_rank(self):
        data = {"entries": [
            self._make_entry(3, "Carol", 80),
            self._make_entry(1, "Alice", 120),
            self._make_entry(2, "Bob", 100),
        ]}
        result = _parse_espn_api_response(data)
        assert [r[0] for r in result] == [1, 2, 3]

    def test_logged_in_user_excluded_by_name(self):
        data = {"entries": [
            self._make_entry(1, "Alice", 120),
            self._make_entry(2, "Bob", 100),
        ]}
        result = _parse_espn_api_response(data, logged_in_display_name="Alice")
        assert len(result) == 1
        assert result[0][1] == "Bob"


# ── _format_user ──────────────────────────────────────────────────────────────

class TestFormatUser:
    def test_with_points(self):
        assert _format_user(1, "Alice", 120) == "Alice (120 pts)"

    def test_one_point(self):
        assert _format_user(1, "Alice", 1) == "Alice (1 pt)"

    def test_zero_points_rank_1(self):
        assert _format_user(1, "Alice", 0) == "Alice (1st place)"

    def test_zero_points_rank_2(self):
        assert _format_user(2, "Bob", 0) == "Bob (2nd place)"

    def test_zero_points_rank_3(self):
        assert _format_user(3, "Carol", 0) == "Carol (3rd place)"

    def test_zero_points_rank_4(self):
        assert _format_user(4, "Dave", 0) == "Dave (4th place)"


# ── _build_top_n ──────────────────────────────────────────────────────────────

class TestBuildTopN:
    def test_basic(self):
        users = [(1, "Alice", 120), (2, "Bob", 100), (3, "Carol", 80)]
        result = _build_top_n(users, 2)
        assert len(result) == 2
        assert "Alice" in result[0]
        assert "Bob" in result[1]

    def test_tie_includes_all_tied(self):
        users = [(1, "Alice", 120), (2, "Bob", 100), (2, "Carol", 100), (4, "Dave", 80)]
        result = _build_top_n(users, 2)
        # rank 2 is tied — both Bob and Carol should be included
        assert len(result) == 3
        names = " ".join(result)
        assert "Bob" in names
        assert "Carol" in names

    def test_empty(self):
        assert _build_top_n([], 5) == []

    def test_n_larger_than_list(self):
        users = [(1, "Alice", 120), (2, "Bob", 100)]
        result = _build_top_n(users, 10)
        assert len(result) == 2


# ── deduplicate_top_users ─────────────────────────────────────────────────────

class TestDeduplicateTopUsers:
    def test_dedupes_strings(self):
        users = ["Alice (120 pts)", "Bob (100 pts)", "Alice (120 pts)"]
        result = deduplicate_top_users(users)
        assert result == ["Alice (120 pts)", "Bob (100 pts)"]

    def test_dedupes_dicts(self):
        users = [{"name": "Alice"}, {"name": "Bob"}, {"name": "Alice"}]
        result = deduplicate_top_users(users)
        assert len(result) == 2
        assert result[0]["name"] == "Alice"
        assert result[1]["name"] == "Bob"

    def test_empty(self):
        assert deduplicate_top_users([]) == []


# ── _get_espn_cookies ─────────────────────────────────────────────────────────

class TestGetEspnCookies:
    def test_returns_empty_when_file_missing(self, tmp_path):
        result = _get_espn_cookies(str(tmp_path / "nonexistent.json"))
        assert result == {}

    def test_filters_espn_cookies(self, tmp_path):
        import json
        state = {
            "cookies": [
                {"name": "espn_token", "value": "abc", "domain": ".espn.com"},
                {"name": "cbs_token", "value": "xyz", "domain": ".cbssports.com"},
            ]
        }
        p = tmp_path / "state.json"
        p.write_text(json.dumps(state))
        result = _get_espn_cookies(str(p))
        assert "espn_token" in result
        assert "cbs_token" not in result

    def test_returns_empty_on_corrupt_file(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("not json {{{")
        result = _get_espn_cookies(str(p))
        assert result == {}


# ── _is_placeholder_url ───────────────────────────────────────────────────────

class TestIsPlaceholderUrl:
    def test_none_is_placeholder(self):
        assert _is_placeholder_url(None) is True

    def test_empty_is_placeholder(self):
        assert _is_placeholder_url("") is True

    def test_example_com_is_placeholder(self):
        assert _is_placeholder_url("https://example.com/brackets") is True

    def test_fake_cbs_men_is_placeholder(self):
        """The test fixture URL that caused the real-world regression."""
        assert _is_placeholder_url("https://cbssports.com/brackets/men/group/123") is True

    def test_fake_cbs_women_is_placeholder(self):
        assert _is_placeholder_url("https://cbssports.com/brackets/women/group/456") is True

    def test_real_picks_cbs_url_is_not_placeholder(self):
        assert _is_placeholder_url(
            "https://picks.cbssports.com/college-basketball/ncaa-tournament/bracket/pools/kbxw63b2ge3deojqg4ydq===/standings"
        ) is False

    def test_real_espn_url_is_not_placeholder(self):
        assert _is_placeholder_url(
            "https://fantasy.espn.com/games/tournament-challenge-bracket-2026/group?id=b1e6fb01-f1eb"
        ) is False

    def test_fake_slack_webhook_is_placeholder(self):
        assert _is_placeholder_url("https://hooks.slack.com/services/TEST") is True

    def test_real_slack_webhook_is_not_placeholder(self):
        assert _is_placeholder_url("https://hooks.slack.com/services/T00/B00/abc123xyz") is False