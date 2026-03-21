"""
Smoke tests: verify every first-party module can be imported cleanly.
These catch stale import paths (e.g. `from slack_dm import` instead of
`from slack_bot.slack_dm import`) that mocked unit tests can silently miss.
No mocking — if the import fails, the test fails.
"""

import importlib
import pytest


# Every internal module that could have a broken import path.
# Add new modules here as the project grows.
MODULES = [
    "bot_setup.bot_setup",
    "bot_setup.config",
    "bot_setup.setup_cli",
    "slack_bot.messages",
    "slack_bot.slack_utils",
    "slack_bot.event_server",
    "slack_bot.events",
    "sources.cbs",
    "sources.espn",
    "status.yearly_setup_reminder",
    "main",
]


@pytest.mark.parametrize("module", MODULES)
def test_module_imports_cleanly(module):
    """Module must be importable with no side-effects or missing dependencies."""
    importlib.import_module(module)


# ---------------------------------------------------------------------------
# Verify the specific cross-module symbols that have broken before.
# These catch `from slack_dm import X` vs `from slack_bot.slack_dm import X`.
# ---------------------------------------------------------------------------

def test_bot_setup_can_access_fetch_leaderboard():
    from bot_setup.bot_setup import _fetch_leaderboard
    assert callable(_fetch_leaderboard)


def test_bot_setup_can_access_run_setup():
    from bot_setup.bot_setup import run_setup
    assert callable(run_setup)


def test_bot_setup_can_access_ping_live_counter():
    from bot_setup.bot_setup import _ping_live_counter
    assert callable(_ping_live_counter)


def test_slack_dm_send_dm_importable_from_correct_path():
    """Guard against `from slack_dm import` instead of `from slack_bot.slack_dm import`."""
    from slack_bot.slack_dm import send_dm
    assert callable(send_dm)


def test_slack_dm_ask_manual_top_users_importable():
    from slack_bot.slack_dm import ask_manual_top_users
    assert callable(ask_manual_top_users)


def test_slack_dm_poll_for_reply_importable():
    from slack_bot.slack_dm import poll_for_reply
    assert callable(poll_for_reply)


def test_no_bare_slack_dm_module_at_top_level():
    """
    Ensure `slack_dm` is NOT importable as a top-level module.
    If this passes it means nobody accidentally created a top-level slack_dm.py.
    """
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("slack_dm")


def test_no_bare_bot_setup_attributes_for_internal_functions():
    """
    The `bot_setup` package __init__ must NOT re-export internal functions.
    Patching `bot_setup.get_input_safe` should be impossible — it lives at
    `bot_setup.bot_setup.get_input_safe`.
    """
    import bot_setup
    assert not hasattr(bot_setup, "get_input_safe"), \
        "get_input_safe leaked into bot_setup.__init__ — patch targets will be wrong"
    assert not hasattr(bot_setup, "run_setup"), \
        "run_setup leaked into bot_setup.__init__ — patch targets will be wrong"
    assert not hasattr(bot_setup, "send_dm"), \
        "send_dm leaked into bot_setup.__init__ — wrong module entirely"


def test_slack_bot_package_has_expected_modules():
    """Guard: every module we import in production code must be importable."""
    import importlib
    real_slack_bot_modules = [
        "slack_bot.messages",
        "slack_bot.slack_utils",
        "slack_bot.slack_dm",
    ]
    for mod in real_slack_bot_modules:
        importlib.import_module(mod)


def test_slack_bot_slack_setup_does_not_exist():
    """slack_bot.slack_setup was never created — confirm it stays absent."""
    import importlib
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("slack_bot.slack_setup")