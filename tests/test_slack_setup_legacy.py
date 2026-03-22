# ---------------------------------------------------------------------------
# Tests for bot_setup/slack_setup.py (legacy prototype)
#
# This module predates the current bot_setup/bot_setup.py architecture.
# It is NOT imported by any production code path. These tests document its
# behaviour and flag the known issues so it can be safely deleted or replaced.
# ---------------------------------------------------------------------------

import json
import pytest
from unittest.mock import patch, MagicMock, call
from pathlib import Path


# ---------------------------------------------------------------------------
# is_upset
# ---------------------------------------------------------------------------

def test_is_upset_lower_seed_wins_home():
    from bot_setup.slack_setup import is_upset
    # home seed 10 beats away seed 3 — upset
    assert is_upset(75, 70, 10, 3) is True

def test_is_upset_lower_seed_wins_away():
    from bot_setup.slack_setup import is_upset
    # away seed 12 beats home seed 5 — upset
    assert is_upset(70, 75, 5, 12) is True

def test_is_upset_favourite_wins_no_upset():
    from bot_setup.slack_setup import is_upset
    # home seed 1 beats away seed 8 — expected result
    assert is_upset(80, 65, 1, 8) is False

def test_is_upset_equal_seeds_not_upset():
    from bot_setup.slack_setup import is_upset
    assert is_upset(80, 70, 4, 4) is False

def test_is_upset_zero_seeds_not_upset():
    from bot_setup.slack_setup import is_upset
    assert is_upset(80, 70, 0, 0) is False


# ---------------------------------------------------------------------------
# simulate_slack_message
# ---------------------------------------------------------------------------

def test_simulate_slack_message_prints_section(capsys):
    from bot_setup.slack_setup import simulate_slack_message
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "Hello world"}}]
    simulate_slack_message(blocks)
    assert "Hello world" in capsys.readouterr().out

def test_simulate_slack_message_prints_divider(capsys):
    from bot_setup.slack_setup import simulate_slack_message
    blocks = [{"type": "divider"}]
    simulate_slack_message(blocks)
    assert "-" * 10 in capsys.readouterr().out

def test_simulate_slack_message_empty_blocks_no_crash(capsys):
    from bot_setup.slack_setup import simulate_slack_message
    simulate_slack_message([])
    capsys.readouterr()  # just confirm no exception


# ---------------------------------------------------------------------------
# build_slack_message
# ---------------------------------------------------------------------------

def _sample_game(gender="men", home_score=70, away_score=65, home_seed=1, away_seed=8):
    return {
        "gender": gender,
        "home": "Duke",
        "away": "UNC",
        "home_score": home_score,
        "away_score": away_score,
        "home_seed": home_seed,
        "away_seed": away_seed,
    }

def test_build_slack_message_returns_blocks():
    from bot_setup.slack_setup import build_slack_message
    blocks = build_slack_message(_sample_game(), ["Alice (100)"], ["Carol (95)"])
    assert isinstance(blocks, list)
    assert len(blocks) > 0

def test_build_slack_message_men_uses_trophy_emoji():
    from bot_setup.slack_setup import build_slack_message
    blocks = build_slack_message(_sample_game(gender="men"), [], [])
    text = blocks[0]["text"]["text"]
    assert "🏆" in text

def test_build_slack_message_women_uses_crown_emoji():
    from bot_setup.slack_setup import build_slack_message
    blocks = build_slack_message(_sample_game(gender="women"), [], [])
    text = blocks[0]["text"]["text"]
    assert "👑" in text

def test_build_slack_message_upset_includes_lightning():
    from bot_setup.slack_setup import build_slack_message
    # seed 10 beats seed 2 — upset
    game = _sample_game(home_score=75, away_score=70, home_seed=10, away_seed=2)
    blocks = build_slack_message(game, [], [])
    text = blocks[0]["text"]["text"]
    assert "⚡" in text

def test_build_slack_message_no_upset_no_lightning():
    from bot_setup.slack_setup import build_slack_message
    # seed 1 beats seed 8 — no upset
    game = _sample_game(home_score=80, away_score=60, home_seed=1, away_seed=8)
    blocks = build_slack_message(game, [], [])
    text = blocks[0]["text"]["text"]
    assert "⚡" not in text

def test_build_slack_message_includes_top_men():
    from bot_setup.slack_setup import build_slack_message
    blocks = build_slack_message(_sample_game(), ["Alice (100)", "Bob (90)"], [])
    full_text = " ".join(b.get("text", {}).get("text", "") for b in blocks)
    assert "Alice" in full_text
    assert "Bob" in full_text

def test_build_slack_message_includes_top_women():
    from bot_setup.slack_setup import build_slack_message
    blocks = build_slack_message(_sample_game(), [], ["Carol (95)", "Dana (85)"])
    full_text = " ".join(b.get("text", {}).get("text", "") for b in blocks)
    assert "Carol" in full_text
    assert "Dana" in full_text


# ---------------------------------------------------------------------------
# build_daily_summary_blocks
# ---------------------------------------------------------------------------

def test_build_daily_summary_blocks_returns_list():
    from bot_setup.slack_setup import build_daily_summary_blocks
    blocks = build_daily_summary_blocks([], [], [], [])
    assert isinstance(blocks, list)
    assert len(blocks) > 0

def test_build_daily_summary_blocks_no_games_shows_fallback():
    from bot_setup.slack_setup import build_daily_summary_blocks
    blocks = build_daily_summary_blocks([], [], [], [])
    full_text = " ".join(b.get("text", {}).get("text", "") for b in blocks)
    assert "No games" in full_text

def test_build_daily_summary_blocks_includes_men_games():
    from bot_setup.slack_setup import build_daily_summary_blocks
    men_games = [_sample_game(gender="men", home_score=70, away_score=65)]
    blocks = build_daily_summary_blocks(men_games, [], [], [])
    full_text = " ".join(b.get("text", {}).get("text", "") for b in blocks)
    assert "Duke" in full_text or "UNC" in full_text

def test_build_daily_summary_blocks_top_rankings_numbered():
    from bot_setup.slack_setup import build_daily_summary_blocks
    blocks = build_daily_summary_blocks([], [], ["Alice (100)", "Bob (90)"], [])
    full_text = " ".join(b.get("text", {}).get("text", "") for b in blocks)
    assert "1." in full_text
    assert "2." in full_text


# ---------------------------------------------------------------------------
# send_dm — mock mode (no real Slack call)
# ---------------------------------------------------------------------------

def test_send_dm_mock_mode_prints_not_calls_slack(capsys):
    from bot_setup.slack_setup import send_dm
    mock_client = MagicMock()
    send_dm(mock_client, "U123", "Hello!", mock=True)
    assert "Hello!" in capsys.readouterr().out
    mock_client.conversations_open.assert_not_called()

def test_send_dm_mock_mode_with_blocks_calls_simulate(capsys):
    from bot_setup.slack_setup import send_dm
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "block text"}}]
    send_dm(MagicMock(), "U123", "msg", blocks=blocks, mock=True)
    assert "block text" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# prompt_manager_for_top
# ---------------------------------------------------------------------------

def test_prompt_manager_for_top_mock_mode_returns_list(monkeypatch):
    from bot_setup.slack_setup import prompt_manager_for_top
    responses = iter(["Alice (100)", "Bob (90)", "Carol (85)"])
    monkeypatch.setattr("builtins.input", lambda _: next(responses))
    result = prompt_manager_for_top("Test Pool", "men", 3, mock=True)
    assert len(result) == 3
    assert "Alice (100)" in result

def test_prompt_manager_for_top_empty_input_uses_fallback(monkeypatch):
    from bot_setup.slack_setup import prompt_manager_for_top
    monkeypatch.setattr("builtins.input", lambda _: "")
    result = prompt_manager_for_top("Test Pool", "men", 3, mock=True)
    assert len(result) == 3
    assert all("TestUser" in r for r in result)

def test_prompt_manager_for_top_respects_n(monkeypatch):
    from bot_setup.slack_setup import prompt_manager_for_top
    monkeypatch.setattr("builtins.input", lambda _: "Player X (50)")
    result = prompt_manager_for_top("Test Pool", "women", 5, mock=True)
    assert len(result) == 5


# ---------------------------------------------------------------------------
# Known issues — documented as tests so they're visible in CI
# ---------------------------------------------------------------------------

def test_known_issue_wait_for_reply_has_no_timeout():
    """
    wait_for_reply() in slack_setup.py contains an infinite while loop with
    no timeout when mock=False. This will hang forever if Slack never replies.
    The fix is to add a timeout parameter (same pattern as poll_for_reply in
    slack_bot/slack_dm.py). This test documents the issue — do not delete until
    the function is fixed or the module is removed.
    """
    import inspect
    from bot_setup.slack_setup import wait_for_reply
    source = inspect.getsource(wait_for_reply)
    assert "while True" in source, "wait_for_reply still has infinite loop — fix or delete this module"

def test_known_issue_slack_setup_is_not_imported_by_production_code():
    """
    bot_setup/slack_setup.py is never imported by bot_setup/bot_setup.py,
    main.py, or any other production module. It is dead code from an earlier
    prototype. It should be deleted or formally replaced.
    """
    import importlib, sys
    # Confirm none of the production entry points import it
    for mod_name in ("bot_setup.bot_setup", "main"):
        mod = importlib.import_module(mod_name)
        source_file = getattr(mod, "__file__", "") or ""
        if source_file:
            source = Path(source_file).read_text()
            assert "slack_setup" not in source, \
                f"{mod_name} must not import the legacy slack_setup module"

def test_known_issue_run_setup_reads_config_json_from_disk():
    """
    slack_setup.run_setup() reads config.json directly from disk — it is not
    injectable. This makes it untestable without a real file and breaks any
    environment without config.json present.
    """
    import inspect
    from bot_setup import slack_setup
    source = inspect.getsource(slack_setup.run_setup)
    assert 'CONFIG_FILE.open' in source or 'CONFIG_FILE.exists' in source, \
        "If this assertion fails the function was fixed — remove this test"