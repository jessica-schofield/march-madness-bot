"""
Tests to prevent regressions in the bot_setup setup flow ordering and URL validation.
"""
import pytest
from unittest.mock import patch, MagicMock, call
from bot_setup.bot_setup import _ask_bracket_url_via_dm, run_slack_dm_setup


# ---------------------------------------------------------------------------
# _ask_bracket_url_via_dm — placeholder URL handling
# ---------------------------------------------------------------------------

def test_placeholder_men_url_triggers_prompt():
    """example.com/men must NOT be treated as a real URL — should ask via DM."""
    pool = {"MEN_URL": "https://example.com/men"}
    config = {}

    with patch("slack_bot.slack_dm.send_dm", return_value=("C123", "ts1")) as mock_send, \
         patch("slack_bot.slack_dm.poll_for_reply", return_value="https://cbssports.com/bracket/real") as mock_poll, \
         patch("slack_bot.slack_dm.save_pending_dm"):
        result = _ask_bracket_url_via_dm("U123", "men's", config, pool)

    mock_send.assert_called_once()
    mock_poll.assert_called_once()
    assert result == "https://cbssports.com/bracket/real"
    assert pool["MEN_URL"] == "https://cbssports.com/bracket/real"


def test_placeholder_women_url_triggers_prompt():
    """example.com/women must NOT be treated as a real URL — should ask via DM."""
    pool = {"WOMEN_URL": "https://example.com/women"}
    config = {}

    with patch("slack_bot.slack_dm.send_dm", return_value=("C123", "ts1")), \
         patch("slack_bot.slack_dm.poll_for_reply", return_value="https://espn.com/bracket/real"), \
         patch("slack_bot.slack_dm.save_pending_dm"):
        result = _ask_bracket_url_via_dm("U123", "women's", config, pool)

    assert result == "https://espn.com/bracket/real"


def test_real_url_skips_prompt():
    """A real non-placeholder URL should be returned immediately without asking."""
    pool = {"MEN_URL": "https://cbssports.com/college-basketball/bracket/groups/12345"}
    config = {}

    with patch("slack_bot.slack_dm.send_dm") as mock_send:
        result = _ask_bracket_url_via_dm("U123", "men's", config, pool)

    mock_send.assert_not_called()
    assert result == "https://cbssports.com/college-basketball/bracket/groups/12345"


def test_empty_url_triggers_prompt():
    """Empty string should trigger the DM prompt."""
    pool = {"MEN_URL": ""}
    config = {}

    with patch("slack_bot.slack_dm.send_dm", return_value=("C123", "ts1")), \
         patch("slack_bot.slack_dm.poll_for_reply", return_value="https://cbssports.com/real"), \
         patch("slack_bot.slack_dm.save_pending_dm"):
        result = _ask_bracket_url_via_dm("U123", "men's", config, pool)

    assert result == "https://cbssports.com/real"


def test_missing_url_key_triggers_prompt():
    """Pool with no MEN_URL key at all should trigger the DM prompt."""
    pool = {}
    config = {}

    with patch("slack_bot.slack_dm.send_dm", return_value=("C123", "ts1")), \
         patch("slack_bot.slack_dm.poll_for_reply", return_value="https://cbssports.com/real"), \
         patch("slack_bot.slack_dm.save_pending_dm"):
        result = _ask_bracket_url_via_dm("U123", "men's", config, pool)

    assert result == "https://cbssports.com/real"


# ---------------------------------------------------------------------------
# run_slack_dm_setup — question ordering
# ---------------------------------------------------------------------------

def _make_ask_via_dm_sequence(*replies):
    """Return a side_effect list for ask_via_dm calls in order."""
    return list(replies)


def test_urls_asked_before_date_questions():
    """
    URL questions must be asked BEFORE any tournament date questions.
    Track the order of all ask_via_dm and _ask_bracket_url_via_dm calls.
    """
    call_order = []

    def fake_ask_via_dm(user_id, question, default=None):
        call_order.append(("ask_via_dm", question[:40]))
        if "top bracket" in question.lower():
            return "5"
        if "game" in question.lower() or "update" in question.lower():
            return "yes"
        if "daily" in question.lower() or "summary" in question.lower():
            return "yes"
        if "often" in question.lower() or "minutes" in question.lower() or "batch" in question.lower():
            return "live"
        if "weekend" in question.lower():
            return "no"
        if "tournament end" in question.lower() or "when does" in question.lower():
            return "skip"
        return str(default) if default is not None else "skip"

    def fake_ask_bracket_url(user_id, gender_label, config, pool):
        call_order.append(("url_prompt", gender_label))
        pool["MEN_URL" if gender_label == "men's" else "WOMEN_URL"] = f"https://cbssports.com/{gender_label}"
        return f"https://cbssports.com/{gender_label}"

    config = {
        "SLACK_MANAGER_ID": "U123",
        "POOLS": [{"SOURCE": "cbs", "MEN_URL": "", "WOMEN_URL": ""}],
        "SLACK_WEBHOOK_URL": "https://hooks.slack.com/fake",
    }

    with patch("slack_bot.slack_dm.ask_via_dm", side_effect=fake_ask_via_dm), \
         patch("bot_setup.bot_setup._ask_bracket_url_via_dm", side_effect=fake_ask_bracket_url), \
         patch("slack_bot.slack_dm.send_dm", return_value=("C123", "ts1")), \
         patch("slack_bot.slack_dm.clear_pending_dm"), \
         patch("bot_setup.bot_setup.save_json"):
        run_slack_dm_setup(config)

    url_positions = [i for i, (kind, _) in enumerate(call_order) if kind == "url_prompt"]
    date_positions = [
        i for i, (kind, label) in enumerate(call_order)
        if kind == "ask_via_dm" and ("tournament" in label.lower() or "when does" in label.lower())
    ]

    assert url_positions, "URL prompts were never called"

    if date_positions:
        assert min(date_positions) > max(url_positions), (
            f"Date questions fired before URL questions!\n"
            f"Call order: {call_order}\n"
            f"URL prompt positions: {url_positions}\n"
            f"Date question positions: {date_positions}"
        )


def test_date_questions_not_asked_twice():
    """Tournament date questions must appear at most once each."""
    date_questions_seen = []

    def fake_ask_via_dm(user_id, question, default=None):
        q_lower = question.lower()
        if "men's" in q_lower and ("tournament end" in q_lower or "when does" in q_lower):
            date_questions_seen.append("men")
        if "women's" in q_lower and ("tournament end" in q_lower or "when does" in q_lower):
            date_questions_seen.append("women")
        # sane defaults
        if "top bracket" in q_lower:
            return "5"
        if "game" in q_lower or "update" in q_lower:
            return "yes"
        if "daily" in q_lower or "summary" in q_lower:
            return "yes"
        if "often" in q_lower or "batch" in q_lower:
            return "live"
        if "weekend" in q_lower:
            return "no"
        return "skip"

    def fake_ask_bracket_url(user_id, gender_label, config, pool):
        pool["MEN_URL" if gender_label == "men's" else "WOMEN_URL"] = "https://cbssports.com/real"
        return "https://cbssports.com/real"

    config = {
        "SLACK_MANAGER_ID": "U123",
        "POOLS": [{"SOURCE": "cbs", "MEN_URL": "", "WOMEN_URL": ""}],
        "SLACK_WEBHOOK_URL": "https://hooks.slack.com/fake",
    }

    with patch("slack_bot.slack_dm.ask_via_dm", side_effect=fake_ask_via_dm), \
         patch("bot_setup.bot_setup._ask_bracket_url_via_dm", side_effect=fake_ask_bracket_url), \
         patch("slack_bot.slack_dm.send_dm", return_value=("C123", "ts1")), \
         patch("slack_bot.slack_dm.clear_pending_dm"), \
         patch("bot_setup.bot_setup.save_json"):
        run_slack_dm_setup(config)

    men_count = date_questions_seen.count("men")
    women_count = date_questions_seen.count("women")
    assert men_count <= 1, f"Men's date question asked {men_count} times — should be at most once"
    assert women_count <= 1, f"Women's date question asked {women_count} times — should be at most once"


# ---------------------------------------------------------------------------
# Browser login guard — should not fire with placeholder URLs
# ---------------------------------------------------------------------------

def test_run_setup_does_not_open_browser_with_placeholder_urls():
    from bot_setup.bot_setup import run_setup

    config = {
        "METHOD": "cli",
        "TOP_N": 5,
        "SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/REAL",
        "SLACK_MANAGER_ID": "U012ABC",
        "POOLS": [{"SOURCE": "cbs",
                   "MEN_URL": "https://example.com/men",
                   "WOMEN_URL": "https://example.com/women"}],
        "TOURNAMENT_END_MEN": "2026-04-07",
        "TOURNAMENT_END_WOMEN": "2026-04-06",
        "PLAYWRIGHT_STATE": "playwright_state.json",
    }

    # method, TOP_N, MINUTES, POST_WEEKENDS, GAME_UPDATES, DAILY_SUMMARY,
    # men_url prompt (blank→skip), women_url prompt (blank→skip),
    # manual-top prompt (n), go-live (n), had_problem (n)
    inputs = ["cli", "5", "0", "n", "y", "y", "", "", "n", "n", "n"]

    with patch("bot_setup.bot_setup.ensure_cbs_login") as mock_login, \
         patch("bot_setup.bot_setup.get_input_safe", side_effect=inputs), \
         patch("bot_setup.bot_setup.ask_if_missing", side_effect=lambda c, k, *a, **kw: c), \
         patch("bot_setup.bot_setup.get_final_games", return_value=[]), \
         patch("bot_setup.bot_setup.save_json"), \
         patch("pathlib.Path.exists", return_value=False):
        run_setup(existing_config=config)

    mock_login.assert_not_called()