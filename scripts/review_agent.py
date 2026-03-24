#!/usr/bin/env python3
"""
March Madness Bot — Project Review Agent
=========================================
Scans the codebase for bugs, inefficiencies, refactor opportunities,
and missing test coverage. Prints a prioritised report.

Usage:
    python3 scripts/review_agent.py
    python3 scripts/review_agent.py --fix        # auto-fix safe issues
    python3 scripts/review_agent.py --json       # machine-readable output
"""

import ast
import argparse
import datetime
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

ROOT = Path(__file__).parent.parent
SRC_DIRS = ["bot_setup", "sources", "slack_bot", "status", "scrapers", "login"]
TEST_DIR = ROOT / "tests"
VENV = ROOT / "venv"

Severity = Literal["critical", "warning", "info"]


@dataclass
class Finding:
    severity: Severity
    category: str
    file: str
    line: Optional[int]
    message: str
    fix: Optional[str] = None
    auto_fixable: bool = False

    def __str__(self):
        loc = f"{self.file}:{self.line}" if self.line else self.file
        tag = {"critical": "🔴", "warning": "🟡", "info": "🔵"}[self.severity]
        lines = [f"{tag} [{self.category}] {loc}", f"   {self.message}"]
        if self.fix:
            lines.append(f"   Fix: {self.fix}")
        if self.auto_fixable:
            lines.append("   ✨ Auto-fixable with --fix")
        return "\n".join(lines)


class ReviewAgent:

    def __init__(self):
        self.findings: list[Finding] = []

    def add(self, severity, category, file, line, message, fix=None, auto_fixable=False):
        rel = str(Path(file).relative_to(ROOT)) if Path(file).is_absolute() else file
        self.findings.append(Finding(severity, category, rel, line, message, fix, auto_fixable))

    # ------------------------------------------------------------------
    # Runner
    # ------------------------------------------------------------------

    def run(self):
        print("🏀 March Madness Bot — Review Agent")
        print(f"   {datetime.datetime.now().strftime('%A %B %d %Y at %I:%M%p')}")
        print(f"   Root: {ROOT}\n")

        self._check_stale_directories()
        self._check_legacy_files()
        self._check_hardcoded_paths()
        self._check_hardcoded_tournament_dates()
        self._check_utc_naive_datetime()
        self._check_magic_numbers()
        self._check_bare_except()
        self._check_missing_imports_at_top()
        self._check_duplicate_logic()
        self._check_missing_test_coverage()
        self._check_test_quality()
        self._check_pytest_passes()
        self._check_dead_code()
        self._check_config_keys_consistent()

        return self.findings

    # ------------------------------------------------------------------
    # Checks
    # ------------------------------------------------------------------

    def _check_stale_directories(self):
        stale = [
            ROOT / "march-madness-bot-1",
            ROOT / "march-madness-bot" / "src",
        ]
        for path in stale:
            if path.exists():
                self.add(
                    "critical", "STALE_DIR", str(path), None,
                    f"Stale duplicate directory '{path.name}' — Python may import from it instead of the real source.",
                    fix=f"rm -rf {path}",
                    auto_fixable=True,
                )

    def _check_legacy_files(self):
        legacy = {
            ROOT / "slack_bot" / "slack.py": (
                "Loads config.json at import time — crashes if config is missing. "
                "Superseded by slack_utils.py."
            ),
            ROOT / "bot_setup" / "setup.py": (
                "setup.py in a non-packaging context is confusing — "
                "may shadow pip's setup.py detection."
            ),
        }
        for path, reason in legacy.items():
            if path.exists():
                self.add(
                    "critical", "LEGACY_FILE", str(path), None,
                    reason,
                    fix=f"git rm {path.relative_to(ROOT)}",
                    auto_fixable=False,
                )

    def _check_hardcoded_paths(self):
        """Flag any /Users/jess/ absolute paths baked into source files."""
        for py_file in self._src_files():
            for i, line in enumerate(py_file.read_text().splitlines(), 1):
                if "/Users/jess/" in line and not line.strip().startswith("#"):
                    self.add(
                        "critical", "HARDCODED_PATH", str(py_file), i,
                        f"Hardcoded absolute path — breaks on any machine that isn't Jess's Mac.",
                        fix="Use Path(__file__).parent or ROOT = Path(__file__).parent.parent",
                    )

    def _check_hardcoded_tournament_dates(self):
        """Flag # ⚠️ UPDATE EACH YEAR comments — these are manual steps that get forgotten."""
        allowlist = {"bot_setup/config.py"}
        for py_file in self._src_files():
            rel = str(py_file.relative_to(ROOT))
            if rel in allowlist:
                continue
            for i, line in enumerate(py_file.read_text().splitlines(), 1):
                if "UPDATE EACH YEAR" in line or "UPDATE_EACH_YEAR" in line:
                    self.add(
                        "warning", "MANUAL_YEARLY_STEP", str(py_file), i,
                        "Manual yearly update required — easy to forget.",
                        fix="Drive from _TOURNAMENT_DATES dict in bot_setup.py which already has per-year entries.",
                    )

    def _check_utc_naive_datetime(self):
        """Flag datetime.datetime.now() / utcnow() without timezone — cron runs in local time."""
        pattern = re.compile(r'datetime\.datetime\.(now|utcnow)\(\)')
        for py_file in self._src_files():
            text = py_file.read_text()
            for i, line in enumerate(text.splitlines(), 1):
                if pattern.search(line) and "timezone" not in line and not line.strip().startswith("#"):
                    # utcnow is the dangerous one
                    if "utcnow" in line:
                        self.add(
                            "critical", "NAIVE_UTC", str(py_file), i,
                            "datetime.utcnow() returns naive UTC — comparing with local time is wrong by 5+ hours.",
                            fix="Use datetime.datetime.now(datetime.timezone.utc) or arrow/pendulum.",
                        )
                    else:
                        self.add(
                            "info", "NAIVE_DATETIME", str(py_file), i,
                            "datetime.now() is naive (no timezone). Fine for display; risky for scheduling.",
                            fix="Add tz=datetime.timezone.utc if used for timestamp comparisons.",
                        )

    def _check_magic_numbers(self):
        """Flag numeric literals that look like ESPN API IDs / year values with no constant."""
        pattern = re.compile(r'\b(277|100|2024|2025|2026|2027)\b')
        ignore_files = {"test_", "conftest"}
        for py_file in self._src_files():
            if any(ig in py_file.name for ig in ignore_files):
                continue
            # collect line ranges that are inside docstrings using AST
            docstring_lines = set()
            try:
                tree = ast.parse(py_file.read_text())
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
                        if (node.body and isinstance(node.body[0], ast.Expr)
                                and isinstance(node.body[0].value, ast.Constant)
                                and isinstance(node.body[0].value.value, str)):
                            ds = node.body[0]
                            for ln in range(ds.lineno, ds.end_lineno + 1):
                                docstring_lines.add(ln)
            except SyntaxError:
                pass
            for i, line in enumerate(py_file.read_text().splitlines(), 1):
                if i in docstring_lines:
                    continue
                stripped = line.strip()
                # skip constant definitions and comments
                if stripped.startswith("#") or re.match(r'^[a-zA-Z_][\w]* =', stripped):
                    continue
                if pattern.search(line) and "date" not in line.lower():
                    if "277" in line:
                        self.add(
                            "warning", "MAGIC_NUMBER", str(py_file), i,
                            "Magic number 277 = ESPN Men's 2026 challenge ID — will silently break next year.",
                            fix="Replace with _ESPN_CHALLENGE_ID_FALLBACK constant.",
                        )

    def _check_bare_except(self):
        """Flag `except:` with no exception type — swallows KeyboardInterrupt etc."""
        for py_file in self._src_files() + list(TEST_DIR.glob("*.py")):
            for i, line in enumerate(py_file.read_text().splitlines(), 1):
                stripped = line.strip()
                if stripped == "except:" or stripped.startswith("except:  "):
                    self.add(
                        "warning", "BARE_EXCEPT", str(py_file), i,
                        "Bare `except:` catches KeyboardInterrupt and SystemExit — use `except Exception:`.",
                        fix="Replace `except:` with `except Exception:`",
                        auto_fixable=True,
                    )

    def _check_missing_imports_at_top(self):
        """Flag functions that do `from x import y` inside the function body."""
        for py_file in self._src_files():
            try:
                tree = ast.parse(py_file.read_text())
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for child in ast.walk(node):
                        if isinstance(child, (ast.Import, ast.ImportFrom)) and child is not node:
                            self.add(
                                "info", "IMPORT_INSIDE_FUNCTION", str(py_file), child.lineno,
                                f"Import inside function `{node.name}` — slows repeated calls and hides dependencies.",
                                fix="Move to top of file unless it's a circular-import workaround.",
                            )
                            break  # one finding per function is enough

    def _check_duplicate_logic(self):
        """Flag known duplicated patterns across files."""
        duplicates = [
            {
                "pattern": re.compile(r'def send_dm\('),
                "files": ["slack_bot/slack_dm.py", "bot_setup/slack_setup.py"],
                "message": "send_dm() is defined in both slack_dm.py and slack_setup.py — one is unused.",
                "fix": "Delete the copy in slack_setup.py and import from slack_dm.py.",
            },
            {
                "pattern": re.compile(r'CONFIG_FILE\s*=\s*Path\('),
                "files": ["bot_setup/config.py", "bot_setup/slack_setup.py"],
                "message": "CONFIG_FILE path defined in two places — they can diverge.",
                "fix": "Import CONFIG_FILE from bot_setup.config everywhere.",
            },
        ]
        for check in duplicates:
            hits = []
            for rel in check["files"]:
                path = ROOT / rel
                if path.exists() and check["pattern"].search(path.read_text()):
                    hits.append(rel)
            if len(hits) > 1:
                self.add(
                    "warning", "DUPLICATE_LOGIC", ", ".join(hits), None,
                    check["message"],
                    fix=check["fix"],
                )

    def _check_missing_test_coverage(self):
        """Report source modules that have no corresponding test file."""
        tested = {f.stem.replace("test_", "") for f in TEST_DIR.glob("test_*.py")}
        for py_file in self._src_files():
            module = py_file.stem
            if module.startswith("_") or module in ("__init__", "conftest"):
                continue
            if module not in tested and f"test_{module}" not in tested:
                self.add(
                    "info", "NO_TEST_FILE", str(py_file), None,
                    f"No test file found for `{module}` — consider adding tests/{module}_test.py.",
                )

    def _check_test_quality(self):
        """Flag test files with no assertions or only a single test."""
        for test_file in TEST_DIR.glob("test_*.py"):
            text = test_file.read_text()
            test_count = len(re.findall(r'^\s*def test_', text, re.MULTILINE))
            assert_count = len(re.findall(r'\bassert\b', text))
            if test_count == 0:
                self.add(
                    "warning", "EMPTY_TEST_FILE", str(test_file), None,
                    "Test file has no test functions.",
                    fix="Add at least one test_ function or delete the file.",
                )
            elif assert_count == 0:
                self.add(
                    "warning", "NO_ASSERTIONS", str(test_file), None,
                    "Test file has test functions but no assert statements — tests always pass.",
                    fix="Add assertions to verify actual behaviour.",
                )

    def _check_pytest_passes(self):
        """Run the test suite and report failures."""
        print("  Running pytest...")
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=no", "--no-header"],
            capture_output=True, text=True, cwd=ROOT
        )
        lines = result.stdout.strip().splitlines()
        summary = lines[-1] if lines else "No output"
        if result.returncode != 0:
            # Extract failing test names
            failed = [l for l in lines if "FAILED" in l]
            for f in failed[:10]:
                self.add(
                    "critical", "TEST_FAILURE", "tests/", None,
                    f"Failing test: {f.strip()}",
                    fix="Run `pytest tests/ -v` to see full output.",
                )
        else:
            print(f"  ✅ pytest: {summary}")

    def _check_dead_code(self):
        """Flag files that are never imported by any other file in the project."""
        all_text = "\n".join(
            f.read_text() for f in self._src_files() + [ROOT / "main.py"]
            if f.exists()
        )
        suspect = {
            "scrapers/cbs_scraper.py": "cbs_scraper",
            "scrapers/cbs_scraper_women.py": "cbs_scraper_women",
            "login/login_and_save_session.py": "login_and_save_session",
            "login/login_men.py": "login_men",
            "login/login_women.py": "login_women",
            "debuggers/scraper_debug.py": "scraper_debug",
            "bot_setup/slack_setup.py": "slack_setup",
            "slack_bot/slack.py": "slack",
        }
        for rel, module in suspect.items():
            path = ROOT / rel
            if not path.exists():
                continue
            if f"import {module}" not in all_text and f"from {rel.replace('/', '.').rstrip('.py')}" not in all_text:
                self.add(
                    "warning", "DEAD_CODE", rel, None,
                    f"`{rel}` is never imported — likely dead code or a one-off script.",
                    fix="Delete it or move to scripts/ with a clear docstring.",
                )

    def _check_config_keys_consistent(self):
        """Flag config keys referenced as strings that don't exist in REQUIRED_KEYS."""
        required_keys_path = ROOT / "bot_setup" / "config.py"
        if not required_keys_path.exists():
            return
        required_match = re.search(
            r'REQUIRED_KEYS\s*=\s*\{(.+?)\}',
            required_keys_path.read_text(), re.DOTALL
        )
        if not required_match:
            return
        declared = set(re.findall(r'"([A-Z_]{3,})"', required_match.group(1)))

        for py_file in self._src_files() + [ROOT / "main.py"]:
            text = py_file.read_text()
            used = set(re.findall(r'config\.get\("([A-Z_]{3,})"', text))
            undeclared = used - declared - {
                # known optional keys not in REQUIRED_KEYS
                "TOURNAMENT_END_MEN", "TOURNAMENT_END_WOMEN",
                "METHOD", "SEND_GAME_UPDATES",
                "MANUAL_TOP", "_DM_SETUP_STARTED", "SLACK_BOT_TOKEN",
            }
            for key in sorted(undeclared):
                self.add(
                    "info", "UNDECLARED_CONFIG_KEY", str(py_file), None,
                    f"config.get(\"{key}\") used but \"{key}\" is not in REQUIRED_KEYS — "
                    "will silently return None if missing.",
                    fix=f"Add \"{key}\" to REQUIRED_KEYS in bot_setup/config.py.",
                )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _src_files(self) -> list:
        files = []
        for d in SRC_DIRS:
            files.extend((ROOT / d).rglob("*.py"))
        files.extend(ROOT.glob("*.py"))  # top-level files like main.py
        return [f for f in files if "venv" not in str(f) and "march-madness-bot-1" not in str(f)]

    # ------------------------------------------------------------------
    # Auto-fix
    # ------------------------------------------------------------------

    def apply_fixes(self):
        for f in self.findings:
            if not f.auto_fixable:
                continue
            if f.category == "STALE_DIR":
                path = ROOT / f.file
                if path.exists():
                    import shutil
                    shutil.rmtree(path)
                    print(f"  ✅ Deleted stale directory: {f.file}")
            elif f.category == "BARE_EXCEPT":
                path = ROOT / f.file
                text = path.read_text()
                fixed = re.sub(r'\bexcept:\s*$', 'except Exception:', text, flags=re.MULTILINE)
                if fixed != text:
                    path.write_text(fixed)
                    print(f"  ✅ Fixed bare except in: {f.file}:{f.line}")

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------

    def report(self, as_json=False):
        findings = self.findings
        if as_json:
            print(json.dumps(
                [{"severity": f.severity, "category": f.category,
                  "file": f.file, "line": f.line, "message": f.message,
                  "fix": f.fix} for f in findings],
                indent=2
            ))
            return

        by_severity = {"critical": [], "warning": [], "info": []}
        for f in findings:
            by_severity[f.severity].append(f)

        total = len(findings)
        print(f"\n{'='*60}")
        print(f"  {total} finding{'s' if total != 1 else ''} — "
              f"🔴 {len(by_severity['critical'])} critical  "
              f"🟡 {len(by_severity['warning'])} warnings  "
              f"🔵 {len(by_severity['info'])} info")
        print(f"{'='*60}\n")

        for severity in ("critical", "warning", "info"):
            group = by_severity[severity]
            if not group:
                continue
            label = {"critical": "🔴 CRITICAL", "warning": "🟡 WARNINGS", "info": "🔵 INFO"}[severity]
            print(f"{label} ({len(group)})")
            print("-" * 50)
            for f in group:
                print(f)
                print()

        auto_fixable = [f for f in findings if f.auto_fixable]
        if auto_fixable:
            print(f"✨ {len(auto_fixable)} issue(s) can be auto-fixed — run with --fix")


def main():
    parser = argparse.ArgumentParser(description="March Madness Bot review agent")
    parser.add_argument("--fix", action="store_true", help="Auto-fix safe issues")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    agent = ReviewAgent()
    agent.run()

    if args.fix:
        print("\nApplying auto-fixes...")
        agent.apply_fixes()
        print("")

    agent.report(as_json=args.json)

    critical_count = sum(1 for f in agent.findings if f.severity == "critical")
    sys.exit(1 if critical_count > 0 else 0)


if __name__ == "__main__":
    main()