# ---------------------------------------------------------------------------
# config.py tests
# Uses tmp_path so no real config.json is touched.
# ---------------------------------------------------------------------------

import json
import datetime
import pytest
from pathlib import Path
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Bugs found in config.py — tests document expected behaviour once fixed
# ---------------------------------------------------------------------------
# 1. load_json signature is missing `default={}` — calls without default kwarg
#    will raise TypeError until fixed. Tests use explicit default={} for now.
# 2. load_json has unreachable code (duplicate open() call after return).
#    The except block never runs because the exception fires on the bare
#    `open()` before the with-block. Tests assert the fallback IS returned
#    to lock in the correct post-fix behaviour.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# save_json / load_json round-trip
# ---------------------------------------------------------------------------

def test_save_json_writes_file(tmp_path):
    from config import save_json
    target = tmp_path / "out.json"
    save_json(target, {"key": "value"})
    assert target.exists()
    data = json.loads(target.read_text())
    assert data == {"key": "value"}


def test_save_json_pretty_prints(tmp_path):
    from config import save_json
    target = tmp_path / "out.json"
    save_json(target, {"a": 1})
    raw = target.read_text()
    assert "\n" in raw


def test_save_json_uses_ensure_ascii_false(tmp_path):
    from config import save_json
    target = tmp_path / "unicode.json"
    save_json(target, {"name": "José"})
    raw = target.read_text()
    assert "José" in raw  # not escaped as \u00e9


def test_save_json_uses_indent_2(tmp_path):
    from config import save_json
    target = tmp_path / "indent.json"
    save_json(target, {"a": {"b": 1}})
    raw = target.read_text()
    assert "  " in raw  # 2-space indent present


def test_load_json_returns_data(tmp_path):
    from config import load_json
    target = tmp_path / "data.json"
    target.write_text(json.dumps({"x": 42}))
    result = load_json(target, default={})
    assert result == {"x": 42}


def test_load_json_missing_file_returns_default(tmp_path):
    from config import load_json
    result = load_json(tmp_path / "missing.json", default={"fallback": True})
    assert result == {"fallback": True}


def test_load_json_missing_file_default_is_empty_dict(tmp_path):
    from config import load_json
    result = load_json(tmp_path / "missing.json", default={})
    assert result == {}


def test_load_json_invalid_json_returns_default(tmp_path):
    from config import load_json
    bad = tmp_path / "bad.json"
    bad.write_text("not valid json {{{{")
    result = load_json(bad, default={"safe": True})
    assert result == {"safe": True}


def test_load_json_invalid_json_prints_warn(tmp_path, capsys):
    from config import load_json
    bad = tmp_path / "bad.json"
    bad.write_text("{bad json")
    load_json(bad, default={})
    assert "[WARN]" in capsys.readouterr().out


def test_save_then_load_round_trip(tmp_path):
    from config import save_json, load_json
    target = tmp_path / "round_trip.json"
    original = {"TOP_N": 5, "POST_WEEKENDS": False, "POOLS": [{"MEN_URL": "https://example.com"}]}
    save_json(target, original)
    result = load_json(target, default={})
    assert result == original


def test_save_json_overwrites_existing_file(tmp_path):
    from config import save_json, load_json
    target = tmp_path / "config.json"
    save_json(target, {"version": 1})
    save_json(target, {"version": 2})
    assert load_json(target, default={}) == {"version": 2}


def test_load_json_default_list(tmp_path):
    from config import load_json
    result = load_json(tmp_path / "missing.json", default=[])
    assert result == []


def test_load_json_default_none(tmp_path):
    from config import load_json
    result = load_json(tmp_path / "missing.json", default=None)
    assert result is None


def test_save_json_nested_structure(tmp_path):
    from config import save_json, load_json
    target = tmp_path / "nested.json"
    data = {"POOLS": [{"MEN_URL": "https://a.com", "WOMEN_URL": "https://b.com"}]}
    save_json(target, data)
    result = load_json(target, default={})
    assert result["POOLS"][0]["MEN_URL"] == "https://a.com"


def test_save_json_empty_dict(tmp_path):
    from config import save_json, load_json
    target = tmp_path / "empty.json"
    save_json(target, {})
    assert load_json(target, default=None) == {}


def test_save_json_list_value(tmp_path):
    from config import save_json, load_json
    target = tmp_path / "list.json"
    save_json(target, ["id1", "id2", "id3"])
    assert load_json(target, default=[]) == ["id1", "id2", "id3"]


def test_load_json_empty_file_returns_default(tmp_path):
    from config import load_json
    empty = tmp_path / "empty.json"
    empty.write_text("")
    result = load_json(empty, default={"ok": True})
    assert result == {"ok": True}


def test_load_json_preserves_types(tmp_path):
    from config import save_json, load_json
    target = tmp_path / "types.json"
    data = {"int": 1, "float": 1.5, "bool": True, "none": None, "list": [1, 2]}
    save_json(target, data)
    result = load_json(target, default={})
    assert result == data


# ---------------------------------------------------------------------------
# CONFIG_FILE / SEEN_FILE / LAST_RANKINGS_FILE / LAST_POST_FILE are Paths
# ---------------------------------------------------------------------------

def test_config_file_is_path():
    from config import CONFIG_FILE
    assert isinstance(CONFIG_FILE, Path)


def test_seen_file_is_path():
    from config import SEEN_FILE
    assert isinstance(SEEN_FILE, Path)


def test_last_rankings_file_is_path():
    from config import LAST_RANKINGS_FILE
    assert isinstance(LAST_RANKINGS_FILE, Path)


def test_last_post_file_is_path():
    from config import LAST_POST_FILE
    assert isinstance(LAST_POST_FILE, Path)


def test_playwright_state_is_path():
    from config import PLAYWRIGHT_STATE
    assert isinstance(PLAYWRIGHT_STATE, Path)


def test_config_file_named_config_json():
    from config import CONFIG_FILE
    assert CONFIG_FILE.name == "config.json"


def test_seen_file_named_correctly():
    from config import SEEN_FILE
    assert SEEN_FILE.name == "seen_games.json"


def test_last_rankings_file_named_correctly():
    from config import LAST_RANKINGS_FILE
    assert LAST_RANKINGS_FILE.name == "last_rankings.json"


# ---------------------------------------------------------------------------
# needs_setup
# ---------------------------------------------------------------------------

def test_needs_setup_returns_true_when_empty():
    from config import needs_setup
    assert needs_setup({}) is True


def test_needs_setup_returns_false_when_all_keys_present():
    from config import needs_setup, REQUIRED_KEYS
    cfg = {k: v for k, v in REQUIRED_KEYS.items()}
    # give non-empty values to keys that default to empty
    cfg["TOP_N"] = 5
    cfg["POOLS"] = [{"MEN_URL": "https://example.com"}]
    cfg["SLACK_WEBHOOK_URL"] = "https://hooks.slack.com/TEST"
    cfg["SLACK_MANAGER_ID"] = "U123"
    assert needs_setup(cfg) is False


def test_needs_setup_returns_true_for_empty_string_value():
    from config import needs_setup, REQUIRED_KEYS
    cfg = {k: v for k, v in REQUIRED_KEYS.items()}
    cfg["SLACK_WEBHOOK_URL"] = ""  # empty string → still needs setup
    assert needs_setup(cfg) is True


def test_needs_setup_returns_true_for_none_value():
    from config import needs_setup, REQUIRED_KEYS
    cfg = {k: v for k, v in REQUIRED_KEYS.items()}
    cfg["TOP_N"] = None
    assert needs_setup(cfg) is True


def test_needs_setup_returns_true_for_empty_list():
    from config import needs_setup, REQUIRED_KEYS
    cfg = {k: v for k, v in REQUIRED_KEYS.items()}
    cfg["POOLS"] = []
    assert needs_setup(cfg) is True


def test_needs_setup_returns_true_for_missing_key():
    from config import needs_setup, REQUIRED_KEYS
    cfg = {k: v for k, v in REQUIRED_KEYS.items()}
    del cfg["TOP_N"]
    assert needs_setup(cfg) is True


def test_needs_setup_allows_empty_slack_manager_id():
    """SLACK_MANAGER_ID is optional — empty string should not trigger needs_setup."""
    from config import needs_setup
    cfg = {
        "TOP_N": 5,
        "POOLS": [{"SOURCE": "cbs"}],
        "MINUTES_BETWEEN_MESSAGES": 30,
        "POST_WEEKENDS": False,
        "SEND_GAME_UPDATES": True,
        "SEND_DAILY_SUMMARY": True,
        "PLAYWRIGHT_HEADLESS": True,
        "PLAYWRIGHT_STATE": "playwright_state.json",
        "SLACK_WEBHOOK_URL": "https://hooks.slack.com/fake",
        "SLACK_MANAGER_ID": "",          # optional — allowed to be empty
        "LIVE_COUNTER_URL": "",          # optional — allowed to be empty
        "VERSION": "1.0.0",
    }
    assert needs_setup(cfg) is False


def test_needs_setup_allows_empty_live_counter_url():
    """LIVE_COUNTER_URL is optional — empty string should not trigger needs_setup."""
    from config import needs_setup
    cfg = {
        "TOP_N": 5,
        "POOLS": [{"SOURCE": "cbs"}],
        "MINUTES_BETWEEN_MESSAGES": 30,
        "POST_WEEKENDS": False,
        "SEND_GAME_UPDATES": True,
        "SEND_DAILY_SUMMARY": True,
        "PLAYWRIGHT_HEADLESS": True,
        "PLAYWRIGHT_STATE": "playwright_state.json",
        "SLACK_WEBHOOK_URL": "https://hooks.slack.com/fake",
        "SLACK_MANAGER_ID": "U123456",
        "LIVE_COUNTER_URL": "",          # optional — allowed to be empty
        "VERSION": "1.0.0",
    }
    assert needs_setup(cfg) is False


def test_needs_setup_still_requires_slack_webhook():
    """SLACK_WEBHOOK_URL is NOT optional — empty string should still trigger needs_setup."""
    from config import needs_setup
    cfg = {
        "TOP_N": 5,
        "POOLS": [{"SOURCE": "cbs"}],
        "MINUTES_BETWEEN_MESSAGES": 30,
        "POST_WEEKENDS": False,
        "SEND_GAME_UPDATES": True,
        "SEND_DAILY_SUMMARY": True,
        "PLAYWRIGHT_HEADLESS": True,
        "PLAYWRIGHT_STATE": "playwright_state.json",
        "SLACK_WEBHOOK_URL": "",         # required — should trigger needs_setup
        "SLACK_MANAGER_ID": "U123456",
        "LIVE_COUNTER_URL": "",
        "VERSION": "1.0.0",
    }
    assert needs_setup(cfg) is True


# ---------------------------------------------------------------------------
# fill_defaults
# ---------------------------------------------------------------------------

def test_fill_defaults_adds_missing_keys():
    from config import fill_defaults, REQUIRED_KEYS
    result = fill_defaults({})
    for key in REQUIRED_KEYS:
        assert key in result


def test_fill_defaults_does_not_overwrite_existing():
    from config import fill_defaults
    cfg = {"TOP_N": 99, "POST_WEEKENDS": True}
    result = fill_defaults(cfg)
    assert result["TOP_N"] == 99
    assert result["POST_WEEKENDS"] is True


def test_fill_defaults_returns_same_dict():
    from config import fill_defaults
    cfg = {}
    result = fill_defaults(cfg)
    assert result is cfg


def test_fill_defaults_sets_minutes_between_messages():
    from config import fill_defaults
    result = fill_defaults({})
    assert result["MINUTES_BETWEEN_MESSAGES"] == 30


def test_fill_defaults_sets_send_game_updates_true():
    from config import fill_defaults
    result = fill_defaults({})
    assert result["SEND_GAME_UPDATES"] is True


def test_fill_defaults_sets_send_daily_summary_true():
    from config import fill_defaults
    result = fill_defaults({})
    assert result["SEND_DAILY_SUMMARY"] is True


def test_fill_defaults_sets_post_weekends_false():
    from config import fill_defaults
    result = fill_defaults({})
    assert result["POST_WEEKENDS"] is False


# ---------------------------------------------------------------------------
# get_tournament_end
# ---------------------------------------------------------------------------

def test_get_tournament_end_men_from_config():
    from config import get_tournament_end
    cfg = {"TOURNAMENT_END_MEN": "2027-04-06", "TOURNAMENT_END_WOMEN": "2027-04-05"}
    assert get_tournament_end(cfg, gender="men") == datetime.date(2027, 4, 6)


def test_get_tournament_end_women_from_config():
    from config import get_tournament_end
    cfg = {"TOURNAMENT_END_MEN": "2027-04-06", "TOURNAMENT_END_WOMEN": "2027-04-05"}
    assert get_tournament_end(cfg, gender="women") == datetime.date(2027, 4, 5)


def test_get_tournament_end_no_gender_returns_later_date():
    from config import get_tournament_end
    cfg = {"TOURNAMENT_END_MEN": "2027-04-07", "TOURNAMENT_END_WOMEN": "2027-04-06"}
    assert get_tournament_end(cfg) == datetime.date(2027, 4, 7)


def test_get_tournament_end_falls_back_to_default_men():
    from config import get_tournament_end
    result = get_tournament_end({}, gender="men")
    assert isinstance(result, datetime.date)
    assert result.month == 4  # April


def test_get_tournament_end_falls_back_to_default_women():
    from config import get_tournament_end
    result = get_tournament_end({}, gender="women")
    assert isinstance(result, datetime.date)
    assert result.month == 4


def test_get_tournament_end_invalid_date_falls_back(capsys):
    from config import get_tournament_end
    cfg = {"TOURNAMENT_END_MEN": "not-a-date"}
    result = get_tournament_end(cfg, gender="men")
    assert isinstance(result, datetime.date)
    # invalid date should silently fall back — no crash


def test_get_tournament_end_empty_string_falls_back():
    from config import get_tournament_end
    cfg = {"TOURNAMENT_END_MEN": "", "TOURNAMENT_END_WOMEN": ""}
    result_men = get_tournament_end(cfg, gender="men")
    result_women = get_tournament_end(cfg, gender="women")
    assert isinstance(result_men, datetime.date)
    assert isinstance(result_women, datetime.date)


def test_get_tournament_end_women_later_than_men_still_correct():
    from config import get_tournament_end
    # unusual but should still work — returns max
    cfg = {"TOURNAMENT_END_MEN": "2027-04-05", "TOURNAMENT_END_WOMEN": "2027-04-08"}
    assert get_tournament_end(cfg) == datetime.date(2027, 4, 8)


# ---------------------------------------------------------------------------
# REQUIRED_KEYS structure
# ---------------------------------------------------------------------------

def test_required_keys_is_dict():
    from config import REQUIRED_KEYS
    assert isinstance(REQUIRED_KEYS, dict)


def test_required_keys_contains_top_n():
    from config import REQUIRED_KEYS
    assert "TOP_N" in REQUIRED_KEYS


def test_required_keys_contains_pools():
    from config import REQUIRED_KEYS
    assert "POOLS" in REQUIRED_KEYS


def test_required_keys_contains_slack_webhook():
    from config import REQUIRED_KEYS
    assert "SLACK_WEBHOOK_URL" in REQUIRED_KEYS


def test_required_keys_post_weekends_default_is_false():
    from config import REQUIRED_KEYS
    assert REQUIRED_KEYS["POST_WEEKENDS"] is False
