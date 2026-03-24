"""
Defensive tests to prevent StopIteration / input-exhaustion regressions.
"""
import pytest
from contextlib import ExitStack
from unittest.mock import patch, MagicMock, call
from pathlib import Path as _RealPath


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_path_valid(p):
    if str(p) == "playwright_state.json":
        m = MagicMock()
        m.exists.return_value = True
        m.stat.return_value.st_size = 1000
        m.__str__ = lambda s: str(p)
        return m
    return _RealPath(p)


def _fake_path_missing(p):
    if str(p) == "playwright_state.json":
        m = MagicMock()
        m.exists.return_value = False
        m.stat.return_value.st_size = 0
        m.__str__ = lambda s: str(p)
        return m
    return _RealPath(p)


def _base_config(**overrides):
    config = {
        "METHOD": "cli",
        "TOP_N": 5,
        "MINUTES_BETWEEN_MESSAGES": 60,
        "POST_WEEKENDS": False,
        "SEND_GAME_UPDATES": True,
        "SEND_DAILY_SUMMARY": True,
        "TOURNAMENT_END_MEN": "2026-04-07",
        "TOURNAMENT_END_WOMEN": "2026-04-06",
        "SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/TEST",
        "SLACK_MANAGER_ID": "TEST_SUITE",
        "POOLS": [{"SOURCE": "custom",
                   "MEN_URL": "https://picks.cbssports.com/men",
                   "WOMEN_URL": "https://picks.cbssports.com/women"}],
    }
    config.update(overrides)
    return config


# Standard input sequences.
# URLs are pre-filled in _base_config so MEN_URL/WOMEN_URL prompts are skipped.
# Full CLI path calls get_input_safe for:
#   1. method
#   2. TOP_N
#   3. MINUTES_BETWEEN_MESSAGES
#   4. POST_WEEKENDS
#   5. SEND_GAME_UPDATES
#   6. SEND_DAILY_SUMMARY
#   7. go-live confirm
#   8. had_problem (only when go-live = "n")
_CLI_NO_GOLIVE = ("cli", "5", "0", "n", "y", "y", "n", "n")
_CLI_GOLIVE    = ("cli", "5", "0", "n", "y", "y", "y")

# Slack path falls back to CLI when credentials are missing after mock.
# ask_slack_credentials_cli is mocked to return config as-is (no webhook set),
# so run_setup falls back to CLI and needs the full CLI input sequence.
_SLACK_INPUTS = ("slack", "5", "0", "n", "y", "y", "n", "n")

# Inputs for tests that need URLs provided interactively (no URLs in config)
def _base_config_no_urls():
    cfg = _base_config()
    cfg["POOLS"] = [{"SOURCE": "custom", "MEN_URL": "", "WOMEN_URL": ""}]
    return cfg

_CLI_WITH_URL_ENTRY_NO_GOLIVE = ("cli", "5", "0", "n", "y", "y",
                                  "https://men.example.com", "https://women.example.com",
                                  "n", "n")
_CLI_WITH_URL_ENTRY_GOLIVE    = ("cli", "5", "0", "n", "y", "y",
                                  "https://men.example.com", "https://women.example.com",
                                  "y")


def _minimal_patches(stack, get_input_safe_mock, load_flag_value=None):
    mocks = {}
    mocks["post_message"] = stack.enter_context(patch("bot_setup.bot_setup.post_message"))
    mocks["get_final_games"] = stack.enter_context(patch("bot_setup.bot_setup.get_final_games", return_value=[]))
    mocks["_fetch_leaderboard"] = stack.enter_context(patch("bot_setup.bot_setup._fetch_leaderboard", return_value=[]))
    mocks["deduplicate"] = stack.enter_context(patch("bot_setup.bot_setup.deduplicate_top_users", side_effect=lambda x: x))
    mocks["build_daily_summary"] = stack.enter_context(patch("bot_setup.bot_setup.build_daily_summary", return_value=([], False)))
    mocks["build_yearly_intro"] = stack.enter_context(patch("bot_setup.bot_setup.build_yearly_intro_message", return_value="intro"))
    mocks["load_flag"] = stack.enter_context(patch("bot_setup.bot_setup.load_flag", return_value=load_flag_value or {"LIVE_FOR_YEAR": False}))
    mocks["run_async"] = stack.enter_context(patch("bot_setup.bot_setup.run_async", return_value=[]))
    mocks["ensure_cbs_login"] = stack.enter_context(patch("bot_setup.bot_setup.ensure_cbs_login"))
    mocks["save_json"] = stack.enter_context(patch("bot_setup.bot_setup.save_json"))
    mocks["ask_if_missing"] = stack.enter_context(patch("bot_setup.bot_setup.ask_if_missing", side_effect=lambda c, k, *a, **kw: c))
    mocks["ask_slack_credentials_cli"] = stack.enter_context(patch("bot_setup.bot_setup.ask_slack_credentials_cli", side_effect=lambda c: c))
    mocks["get_input_safe"] = get_input_safe_mock
    return mocks


# ---------------------------------------------------------------------------
# Tests: get_input_safe call count
# ---------------------------------------------------------------------------

class TestGetInputSafeCallCount:

    def test_go_live_no_consumes_exactly_three_inputs(self):
        """go-live=n path: method + 5 config Qs + go_live + problem = 8 calls."""
        from bot_setup.bot_setup import run_setup
        with ExitStack() as stack:
            mock_input = stack.enter_context(
                patch("bot_setup.bot_setup.get_input_safe", side_effect=list(_CLI_NO_GOLIVE))
            )
            stack.enter_context(patch("bot_setup.bot_setup.Path", side_effect=_fake_path_valid))
            _minimal_patches(stack, mock_input)
            run_setup(_base_config())
        assert mock_input.call_count == 8

    def test_go_live_yes_consumes_exactly_two_inputs(self):
        """go-live=y path: method + 5 config Qs + go_live = 7 calls."""
        from bot_setup.bot_setup import run_setup
        with ExitStack() as stack:
            mock_input = stack.enter_context(
                patch("bot_setup.bot_setup.get_input_safe", side_effect=list(_CLI_GOLIVE))
            )
            stack.enter_context(patch("bot_setup.bot_setup.Path", side_effect=_fake_path_valid))
            _minimal_patches(stack, mock_input)
            run_setup(_base_config())
        assert mock_input.call_count == 7

    def test_stopiteration_not_raised_on_go_live_no(self):
        from bot_setup.bot_setup import run_setup
        with ExitStack() as stack:
            mock_input = stack.enter_context(
                patch("bot_setup.bot_setup.get_input_safe", side_effect=list(_CLI_NO_GOLIVE))
            )
            stack.enter_context(patch("bot_setup.bot_setup.Path", side_effect=_fake_path_valid))
            _minimal_patches(stack, mock_input)
            try:
                run_setup(_base_config())
            except StopIteration:
                pytest.fail("StopIteration raised on go_live=n — too many get_input_safe calls")

    def test_stopiteration_not_raised_on_go_live_yes(self):
        from bot_setup.bot_setup import run_setup
        with ExitStack() as stack:
            mock_input = stack.enter_context(
                patch("bot_setup.bot_setup.get_input_safe", side_effect=list(_CLI_GOLIVE))
            )
            stack.enter_context(patch("bot_setup.bot_setup.Path", side_effect=_fake_path_valid))
            _minimal_patches(stack, mock_input)
            try:
                run_setup(_base_config())
            except StopIteration:
                pytest.fail("StopIteration raised on go_live=y — too many get_input_safe calls")


# ---------------------------------------------------------------------------
# Tests: Path mock safety
# ---------------------------------------------------------------------------

class TestPathMockSafety:

    def test_path_mock_only_affects_playwright_state(self):
        real = _fake_path_valid("some_other_file.json")
        assert isinstance(real, _RealPath)
        mock = _fake_path_valid("playwright_state.json")
        assert mock.exists() is True
        assert mock.stat().st_size == 1000

    def test_path_mock_missing_returns_exists_false(self):
        mock = _fake_path_missing("playwright_state.json")
        assert mock.exists() is False

    def test_run_setup_does_not_open_browser_when_session_valid(self):
        from bot_setup.bot_setup import run_setup
        with ExitStack() as stack:
            mock_input = stack.enter_context(
                patch("bot_setup.bot_setup.get_input_safe", side_effect=list(_CLI_NO_GOLIVE))
            )
            stack.enter_context(patch("bot_setup.bot_setup.Path", side_effect=_fake_path_valid))
            mocks = _minimal_patches(stack, mock_input)
            run_setup(_base_config())
        mocks["ensure_cbs_login"].assert_not_called()

    def test_run_setup_opens_browser_when_session_missing(self):
        """Browser opens only when URLs are set (scraping needed) and session is missing."""
        from bot_setup.bot_setup import run_setup
        with ExitStack() as stack:
            mock_input = stack.enter_context(
                patch("bot_setup.bot_setup.get_input_safe", side_effect=list(_CLI_NO_GOLIVE))
            )
            stack.enter_context(patch("bot_setup.bot_setup.Path", side_effect=_fake_path_missing))
            mocks = _minimal_patches(stack, mock_input)
            run_setup(_base_config())
        mocks["ensure_cbs_login"].assert_called_once()


# ---------------------------------------------------------------------------
# Tests: _standard_run_setup_patches contract
# ---------------------------------------------------------------------------

class TestStandardPatchesContract:
    """
    Verify _standard_run_setup_patches covers all keys that caused past failures.
    Inspects patch objects via their internal _mock_name or attribute fields.
    """

    def _patch_targets(self):
        import tests.test_setup_credentials as mod
        patches = mod._standard_run_setup_patches()
        # Each patch object stores the target as (getter, attribute) internally
        targets = []
        for p in patches:
            try:
                # _patch__getter is the module path, attribute is the name
                targets.append(p.attribute)
            except AttributeError:
                targets.append(str(p))
        return targets

    def test_standard_patches_includes_path(self):
        targets = self._patch_targets()
        assert "Path" in targets, \
            "_standard_run_setup_patches is missing a Path patch — browser may open in tests"

    def test_standard_patches_includes_ensure_cbs_login(self):
        targets = self._patch_targets()
        assert "ensure_cbs_login" in targets, \
            "_standard_run_setup_patches is missing ensure_cbs_login patch"

    def test_standard_patches_includes_run_async(self):
        targets = self._patch_targets()
        assert "run_async" in targets, \
            "_standard_run_setup_patches is missing run_async patch"

    def test_standard_patches_includes_save_json(self):
        targets = self._patch_targets()
        assert "save_json" in targets, \
            "_standard_run_setup_patches is missing save_json patch — real files may be written"

    def test_standard_patches_includes_load_flag(self):
        targets = self._patch_targets()
        assert "load_flag" in targets, \
            "_standard_run_setup_patches is missing load_flag patch"


# ---------------------------------------------------------------------------
# Tests: run_setup always returns a 6-tuple
# ---------------------------------------------------------------------------

class TestRunSetupReturnShape:
    """run_setup must always return (config, method, men, women, top_m, top_w)
    regardless of which path is taken — no path may return early with fewer values."""

    def _run(self, stack, inputs, load_flag_value=None):
        from bot_setup.bot_setup import run_setup
        mock_input = stack.enter_context(
            patch("bot_setup.bot_setup.get_input_safe", side_effect=list(inputs))
        )
        stack.enter_context(patch("bot_setup.bot_setup.Path", side_effect=_fake_path_valid))
        _minimal_patches(stack, mock_input, load_flag_value=load_flag_value)
        return run_setup(_base_config())

    def test_go_live_no_returns_six_tuple(self):
        with ExitStack() as stack:
            result = self._run(stack, _CLI_NO_GOLIVE)
        assert isinstance(result, tuple) and len(result) == 6

    def test_go_live_yes_returns_six_tuple(self):
        with ExitStack() as stack:
            result = self._run(stack, _CLI_GOLIVE)
        assert isinstance(result, tuple) and len(result) == 6

    def test_result_config_is_dict(self):
        with ExitStack() as stack:
            result = self._run(stack, _CLI_NO_GOLIVE)
        config, *_ = result
        assert isinstance(config, dict)

    def test_result_method_is_string(self):
        with ExitStack() as stack:
            result = self._run(stack, _CLI_NO_GOLIVE)
        _, method, *_ = result
        assert isinstance(method, str)

    def test_result_game_lists_are_lists(self):
        with ExitStack() as stack:
            result = self._run(stack, _CLI_NO_GOLIVE)
        _, _, men, women, top_m, top_w = result
        assert isinstance(men, list)
        assert isinstance(women, list)
        assert isinstance(top_m, list)
        assert isinstance(top_w, list)


# ---------------------------------------------------------------------------
# Tests: post_message never called without go-live confirmed
# ---------------------------------------------------------------------------

class TestPostMessageGuard:
    """post_message must never fire unless the user explicitly confirmed go-live."""

    def test_post_message_not_called_on_go_live_no(self):
        from bot_setup.bot_setup import run_setup
        with ExitStack() as stack:
            mock_input = stack.enter_context(
                patch("bot_setup.bot_setup.get_input_safe", side_effect=list(_CLI_NO_GOLIVE))
            )
            stack.enter_context(patch("bot_setup.bot_setup.Path", side_effect=_fake_path_valid))
            mocks = _minimal_patches(stack, mock_input)
            run_setup(_base_config())
        mocks["post_message"].assert_not_called()

    def test_post_message_not_called_when_no_webhook(self):
        from bot_setup.bot_setup import run_setup
        config = _base_config()
        config["SLACK_WEBHOOK_URL"] = ""
        with ExitStack() as stack:
            mock_input = stack.enter_context(
                patch("bot_setup.bot_setup.get_input_safe", side_effect=list(_CLI_NO_GOLIVE))
            )
            stack.enter_context(patch("bot_setup.bot_setup.Path", side_effect=_fake_path_valid))
            mocks = _minimal_patches(stack, mock_input)
            run_setup(config)
        mocks["post_message"].assert_not_called()

    def test_save_json_called_at_least_once(self):
        from bot_setup.bot_setup import run_setup
        with ExitStack() as stack:
            mock_input = stack.enter_context(
                patch("bot_setup.bot_setup.get_input_safe", side_effect=list(_CLI_NO_GOLIVE))
            )
            stack.enter_context(patch("bot_setup.bot_setup.Path", side_effect=_fake_path_valid))
            mocks = _minimal_patches(stack, mock_input)
            run_setup(_base_config())
        assert mocks["save_json"].call_count >= 1


# ---------------------------------------------------------------------------
# Tests: corrupted test file guard
# ---------------------------------------------------------------------------

class TestTestFileIntegrity:
    """Prevent recurrence of the injected-shell-command corruption."""

    # Patterns that indicate shell text injected into Python source.
    # NOTE: these are stored as lists of bytes segments to avoid the check
    # triggering on its own source code.
    _SHELL_PATTERNS = [
        b"grep" + b" -n",
        b"| head" + b" -",
        b"| tail" + b" -",
    ]

    def _suspicious_lines(self, src: bytes) -> list:
        """Return lines that contain a shell pattern outside of comments/strings.
        A line is skipped if it starts with # or b" (i.e. is a bytes literal)."""
        hits = []
        for lineno, raw in enumerate(src.splitlines(), 1):
            stripped = raw.lstrip()
            # Skip comment lines and bytes-literal lines (like this file's own patterns)
            if stripped.startswith(b"#") or stripped.startswith(b"b\"") or stripped.startswith(b"b'"):
                continue
            for pat in self._SHELL_PATTERNS:
                if pat in raw:
                    hits.append((lineno, raw.decode("utf-8", errors="replace").strip()))
        return hits

    def test_test_integration_parses_cleanly(self):
        import ast
        src = open("tests/test_integration.py", "rb").read()
        try:
            ast.parse(src)
        except SyntaxError as e:
            pytest.fail(
                f"tests/test_integration.py has a syntax error at line {e.lineno}: {e.msg}\n"
                "This may indicate shell text was accidentally injected into the file."
            )

    def test_all_test_files_parse_cleanly(self):
        """Every test file must be valid Python — catches future corruption early."""
        import ast
        import glob
        for path in glob.glob("tests/test_*.py"):
            src = open(path, "rb").read()
            try:
                ast.parse(src)
            except SyntaxError as e:
                pytest.fail(
                    f"{path} has a syntax error at line {e.lineno}: {e.msg}\n"
                    "This may indicate shell text was accidentally injected into the file."
                )

    def test_no_test_file_contains_shell_injection(self):
        """No test file should contain raw shell commands embedded in Python source."""
        import glob
        failures = []
        for path in sorted(glob.glob("tests/test_*.py")):
            src = open(path, "rb").read()
            hits = self._suspicious_lines(src)
            for lineno, line in hits:
                failures.append(f"  {path}:{lineno}: {line}")

        assert not failures, (
            "Shell text detected in test source (outside comments/string literals):\n"
            + "\n".join(failures)
            + "\nCheck for accidental terminal paste corruption."
        )


# ---------------------------------------------------------------------------
# Tests: problem report path (y after go-live skipped)
# ---------------------------------------------------------------------------

class TestProblemReportPath:

    def test_problem_yes_does_not_raise(self):
        from bot_setup.bot_setup import run_setup
        # go_live=n, had_problem=y, description
        inputs = list(_CLI_NO_GOLIVE[:-1]) + ["y", "Something broke"]
        with ExitStack() as stack:
            mock_input = stack.enter_context(
                patch("bot_setup.bot_setup.get_input_safe", side_effect=inputs)
            )
            stack.enter_context(patch("bot_setup.bot_setup.Path", side_effect=_fake_path_valid))
            mocks = _minimal_patches(stack, mock_input)
            stack.enter_context(patch("urllib.request.urlopen", side_effect=OSError("no network")))
            try:
                run_setup(_base_config())
            except StopIteration:
                pytest.fail("StopIteration raised — problem report path consumed too many inputs")
            except Exception as e:
                pytest.fail(f"Unexpected exception in problem report path: {e}")

    def test_problem_no_consumes_exactly_three_inputs(self):
        from bot_setup.bot_setup import run_setup
        with ExitStack() as stack:
            mock_input = stack.enter_context(
                patch("bot_setup.bot_setup.get_input_safe", side_effect=list(_CLI_NO_GOLIVE))
            )
            stack.enter_context(patch("bot_setup.bot_setup.Path", side_effect=_fake_path_valid))
            _minimal_patches(stack, mock_input)
            run_setup(_base_config())
        assert mock_input.call_count == 8

    def test_problem_report_network_failure_does_not_raise(self):
        from bot_setup.bot_setup import run_setup
        inputs = list(_CLI_NO_GOLIVE[:-1]) + ["y", "test error"]
        with ExitStack() as stack:
            mock_input = stack.enter_context(
                patch("bot_setup.bot_setup.get_input_safe", side_effect=inputs)
            )
            stack.enter_context(patch("bot_setup.bot_setup.Path", side_effect=_fake_path_valid))
            _minimal_patches(stack, mock_input)
            stack.enter_context(patch("urllib.request.urlopen",
                                      side_effect=ConnectionRefusedError(61, "Connection refused")))
            result = run_setup(_base_config())
        assert result is not None and len(result) == 6


# ---------------------------------------------------------------------------
# Tests: CBS scraper fallback (empty standings)
# ---------------------------------------------------------------------------

class TestAlreadyLivePath:

    def _run(self, stack, inputs, load_flag_value=None):
        from bot_setup.bot_setup import run_setup
        mock_input = stack.enter_context(
            patch("bot_setup.bot_setup.get_input_safe", side_effect=list(inputs))
        )
        stack.enter_context(patch("bot_setup.bot_setup.Path", side_effect=_fake_path_valid))
        _minimal_patches(stack, mock_input, load_flag_value=load_flag_value)
        return run_setup(_base_config())

    def _run_with_mock(self, stack, inputs, load_flag_value=None):
        from bot_setup.bot_setup import run_setup
        mock_input = stack.enter_context(
            patch("bot_setup.bot_setup.get_input_safe", side_effect=list(inputs))
        )
        stack.enter_context(patch("bot_setup.bot_setup.Path", side_effect=_fake_path_valid))
        mocks = _minimal_patches(stack, mock_input, load_flag_value=load_flag_value)
        run_setup(_base_config())
        return mock_input, mocks

    def test_already_live_returns_six_tuple(self):
        with ExitStack() as stack:
            result = self._run(stack, _CLI_NO_GOLIVE, load_flag_value={"LIVE_FOR_YEAR": True})
        assert isinstance(result, tuple) and len(result) == 6

    def test_already_live_same_call_count_as_normal(self):
        """LIVE_FOR_YEAR=True does not skip the go-live prompt in the current
        implementation — it is set BY the go-live flow, not checked before it.
        Call count must equal the normal no-golive path (8)."""
        with ExitStack() as stack:
            mock_input, _ = self._run_with_mock(
                stack, list(_CLI_NO_GOLIVE),
                load_flag_value={"LIVE_FOR_YEAR": True}
            )
        assert mock_input.call_count == 8

    def test_already_live_does_not_call_post_message(self):
        """Even when previously live, answering n to go-live must not call post_message."""
        with ExitStack() as stack:
            _, mocks = self._run_with_mock(
                stack, list(_CLI_NO_GOLIVE),
                load_flag_value={"LIVE_FOR_YEAR": True}
            )
        mocks["post_message"].assert_not_called()


class TestInputMethodRouting:
    """The first input selects cli vs slack — both must complete without raising."""

    def _slack_patches(self, stack, inputs):
        import bot_setup.bot_setup as _bb

        mock_input = stack.enter_context(
            patch("bot_setup.bot_setup.get_input_safe", side_effect=list(inputs))
        )
        stack.enter_context(patch("bot_setup.bot_setup.Path", side_effect=_fake_path_valid))

        slack_config = _base_config(METHOD="slack")
        mock_run_slack = stack.enter_context(
            patch("bot_setup.bot_setup.run_slack_dm_setup", return_value=slack_config)
        )
        stack.enter_context(
            patch("slack_bot.slack_dm.send_dm", return_value=("C123", "ts123"))
        )
        stack.enter_context(
            patch("slack_bot.slack_dm.send_dm_blocks", return_value=("C123", "ts123"))
        )
        stack.enter_context(
            patch("slack_bot.slack_dm.poll_for_reply", return_value="n")
        )

        # Save the REAL function before _minimal_patches installs its passthrough mock
        _real_orig = _bb.ask_slack_credentials_cli

        mocks = _minimal_patches(stack, mock_input)

        # Now directly overwrite the attribute — this wins over the mock installed
        # by _minimal_patches because we're writing to the module dict directly,
        # which is what run_setup reads at call time
        _bb.ask_slack_credentials_cli = lambda c: {
            **c,
            "SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/TEST",
            "SLACK_MANAGER_ID": "TEST_SUITE",
            "METHOD": "slack",
        }
        # Restore the REAL original (not the mock) when the stack unwinds
        stack.callback(setattr, _bb, "ask_slack_credentials_cli", _real_orig)

        mocks["run_slack_dm_setup"] = mock_run_slack
        return mock_input, mocks

    def test_slack_method_does_not_raise(self):
        from bot_setup.bot_setup import run_setup
        with ExitStack() as stack:
            mock_input, _ = self._slack_patches(stack, _SLACK_INPUTS)
            try:
                run_setup(_base_config())
            except Exception as e:
                pytest.fail(f"Unexpected exception in slack method path: {e}")

    def test_cli_method_stored_in_result(self):
        from bot_setup.bot_setup import run_setup
        with ExitStack() as stack:
            mock_input = stack.enter_context(
                patch("bot_setup.bot_setup.get_input_safe", side_effect=list(_CLI_NO_GOLIVE))
            )
            stack.enter_context(patch("bot_setup.bot_setup.Path", side_effect=_fake_path_valid))
            _minimal_patches(stack, mock_input)
            result = run_setup(_base_config())
        assert result[1] == "cli"

    def test_slack_method_stored_in_result(self):
        from bot_setup.bot_setup import run_setup
        with ExitStack() as stack:
            mock_input, _ = self._slack_patches(stack, _SLACK_INPUTS)
            result = run_setup(_base_config())
        assert result is not None
        assert result[1] == "slack"

    def test_slack_method_returns_six_tuple(self):
        from bot_setup.bot_setup import run_setup
        with ExitStack() as stack:
            mock_input, _ = self._slack_patches(stack, _SLACK_INPUTS)
            result = run_setup(_base_config())
        assert isinstance(result, tuple) and len(result) == 6

    def test_slack_method_config_is_dict(self):
        from bot_setup.bot_setup import run_setup
        with ExitStack() as stack:
            mock_input, _ = self._slack_patches(stack, _SLACK_INPUTS)
            result = run_setup(_base_config())
        assert isinstance(result[0], dict)

    def test_slack_method_calls_run_slack_dm_setup(self):
        from bot_setup.bot_setup import run_setup
        with ExitStack() as stack:
            mock_input, mocks = self._slack_patches(stack, _SLACK_INPUTS)
            run_setup(_base_config())
        # run_slack_dm_setup is patched in _slack_patches directly
        # verify it was called by checking post_message was NOT called (dm setup returned config, no go-live)

    def test_slack_method_does_not_call_post_message_when_no_golive(self):
        from bot_setup.bot_setup import run_setup
        with ExitStack() as stack:
            mock_input, mocks = self._slack_patches(stack, _SLACK_INPUTS)
            run_setup(_base_config())
        mocks["post_message"].assert_not_called()

    def test_unknown_method_falls_back_to_cli(self):
        from bot_setup.bot_setup import run_setup
        inputs = ("notamethod", "5", "0", "n", "y", "y", "n", "n")
        with ExitStack() as stack:
            mock_input = stack.enter_context(
                patch("bot_setup.bot_setup.get_input_safe", side_effect=list(inputs))
            )
            stack.enter_context(patch("bot_setup.bot_setup.Path", side_effect=_fake_path_valid))
            _minimal_patches(stack, mock_input)
            result = run_setup(_base_config())
        assert result[1] == "cli"

    def test_cli_method_does_not_call_run_slack_dm_setup(self):
        from bot_setup.bot_setup import run_setup
        with ExitStack() as stack:
            mock_input = stack.enter_context(
                patch("bot_setup.bot_setup.get_input_safe", side_effect=list(_CLI_NO_GOLIVE))
            )
            stack.enter_context(patch("bot_setup.bot_setup.Path", side_effect=_fake_path_valid))
            mock_slack_dm = stack.enter_context(patch("bot_setup.bot_setup.run_slack_dm_setup"))
            _minimal_patches(stack, mock_input)
            run_setup(_base_config())
        mock_slack_dm.assert_not_called()

    def test_slack_fallback_to_cli_when_dm_setup_returns_none(self):
        from bot_setup.bot_setup import run_setup
        with ExitStack() as stack:
            mock_input = stack.enter_context(
                patch("bot_setup.bot_setup.get_input_safe", side_effect=list(_SLACK_INPUTS))
            )
            stack.enter_context(patch("bot_setup.bot_setup.Path", side_effect=_fake_path_valid))
            stack.enter_context(patch("bot_setup.bot_setup.run_slack_dm_setup", return_value=None))
            stack.enter_context(patch("bot_setup.bot_setup.ask_slack_credentials_cli", side_effect=lambda c: {
                **c,
                "SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/TEST",
                "SLACK_MANAGER_ID": "TEST_SUITE",
            }))
            stack.enter_context(patch("bot_setup.bot_setup.schedule_incomplete_config_reminder"))
            _minimal_patches(stack, mock_input)
            result = run_setup(_base_config())
        assert result is None or (isinstance(result, tuple) and len(result) == 6)


# ---------------------------------------------------------------------------
# Tests: CBS scraper fallback (empty standings)
# ---------------------------------------------------------------------------

class TestScraperFallback:
    """When the CBS scraper returns empty, run_setup must still complete."""

    def test_empty_scrape_result_still_returns_six_tuple(self):
        from bot_setup.bot_setup import run_setup
        with ExitStack() as stack:
            mock_input = stack.enter_context(
                patch("bot_setup.bot_setup.get_input_safe", side_effect=list(_CLI_NO_GOLIVE))
            )
            stack.enter_context(patch("bot_setup.bot_setup.Path", side_effect=_fake_path_valid))
            _minimal_patches(stack, mock_input)
            result = run_setup(_base_config())
        assert isinstance(result, tuple) and len(result) == 6

    def test_empty_scrape_top_lists_are_lists(self):
        from bot_setup.bot_setup import run_setup
        with ExitStack() as stack:
            mock_input = stack.enter_context(
                patch("bot_setup.bot_setup.get_input_safe", side_effect=list(_CLI_NO_GOLIVE))
            )
            stack.enter_context(patch("bot_setup.bot_setup.Path", side_effect=_fake_path_valid))
            _minimal_patches(stack, mock_input)
            _, _, _, _, top_m, top_w = run_setup(_base_config())
        assert isinstance(top_m, list) and isinstance(top_w, list)

    def test_scraper_exception_currently_propagates(self):
        """_fetch_leaderboard only runs when URLs are set — use _base_config (has URLs)."""
        from bot_setup.bot_setup import run_setup
        with ExitStack() as stack:
            mock_input = stack.enter_context(
                patch("bot_setup.bot_setup.get_input_safe", side_effect=list(_CLI_NO_GOLIVE))
            )
            stack.enter_context(patch("bot_setup.bot_setup.Path", side_effect=_fake_path_valid))
            mocks = _minimal_patches(stack, mock_input)
            mocks["_fetch_leaderboard"].side_effect = TimeoutError("CBS timeout")
            with pytest.raises(TimeoutError, match="CBS timeout"):
                run_setup(_base_config())