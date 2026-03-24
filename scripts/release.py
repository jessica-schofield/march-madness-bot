#!/usr/bin/env python3
"""
Release agent — run before every commit/tag.

Usage:
    python3 scripts/release.py [patch|minor|major] [--message "changelog entry"]

Examples:
    python3 scripts/release.py patch --message "Fix webhook guard firing before pools check"
    python3 scripts/release.py minor --message "Add multi-pool Yahoo support"
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Files that must never be committed
# ---------------------------------------------------------------------------

SENSITIVE_FILES = [
    Path("bot_setup/config.json"),
    Path("playwright_state.json"),
    Path(".env"),
    Path("seen_games.json"),
    Path("last_post.json"),
    Path("last_rankings.json"),
    Path("yearly_flag.json"),
    Path("yearly_reminder_flag.json"),
    Path("status/incomplete_config.json"),
    Path("cron.log"),
]

GITIGNORE = Path(".gitignore")
VERSION_FILE = Path("bot_setup/config.py")
CHANGELOG = Path("CHANGELOG.md")
README = Path("README.md")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(cmd, check=True):
    print(f"  $ {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"[ERROR] Command failed:\n{result.stderr}")
        sys.exit(1)
    return result.stdout.strip()


def read(path):
    return path.read_text() if path.exists() else ""


def write(path, content):
    path.write_text(content)
    print(f"  [WRITE] {path}")


# ---------------------------------------------------------------------------
# Step 1 — ensure .gitignore covers all sensitive files
# ---------------------------------------------------------------------------

def ensure_gitignore():
    print("\n[1] Checking .gitignore...")
    content = read(GITIGNORE)
    missing = []
    for f in SENSITIVE_FILES:
        pattern = str(f)
        if pattern not in content:
            missing.append(pattern)
    if missing:
        additions = "\n".join(missing)
        write(GITIGNORE, content.rstrip() + "\n" + additions + "\n")
        print(f"  [INFO] Added {len(missing)} entries to .gitignore")
    else:
        print("  [OK] .gitignore up to date")


# ---------------------------------------------------------------------------
# Step 2 — remove any sensitive files from git index (untrack without delete)
# ---------------------------------------------------------------------------

def untrack_sensitive_files():
    print("\n[2] Untracking sensitive files from git index...")
    for f in SENSITIVE_FILES:
        result = run(f"git ls-files --error-unmatch {f} 2>/dev/null", check=False)
        if result:
            run(f"git rm --cached {f}", check=False)
            print(f"  [UNTRACKED] {f}")


# ---------------------------------------------------------------------------
# Step 3 — bump version in config.py and return new version string
# ---------------------------------------------------------------------------

def bump_version(part):
    print(f"\n[3] Bumping {part} version in {VERSION_FILE}...")
    content = read(VERSION_FILE)
    match = re.search(r'"VERSION":\s*"(\d+)\.(\d+)\.(\d+)"', content)
    if not match:
        print("  [ERROR] VERSION key not found in config.py")
        sys.exit(1)

    major, minor, patch_n = int(match.group(1)), int(match.group(2)), int(match.group(3))
    if part == "major":
        major, minor, patch_n = major + 1, 0, 0
    elif part == "minor":
        minor, patch_n = minor + 1, 0
    else:
        patch_n += 1

    new_version = f"{major}.{minor}.{patch_n}"
    new_content = content.replace(match.group(0), f'"VERSION": "{new_version}"')
    write(VERSION_FILE, new_content)
    print(f"  [VERSION] {match.group(1)}.{match.group(2)}.{match.group(3)} → {new_version}")
    return new_version


# ---------------------------------------------------------------------------
# Step 4 — prepend entry to CHANGELOG.md
# ---------------------------------------------------------------------------

def update_changelog(version, message):
    print(f"\n[4] Updating {CHANGELOG}...")
    today = date.today().isoformat()
    content = read(CHANGELOG)

    # Find the first existing ## [x.y.z] line to insert before it
    insert_marker = re.search(r"^## \[", content, re.MULTILINE)
    new_entry = f"## [{version}] - {today}\n\n### Changed\n- {message}\n\n"

    if insert_marker:
        pos = insert_marker.start()
        new_content = content[:pos] + new_entry + content[pos:]
    else:
        # No existing entries — append after header
        new_content = content.rstrip() + "\n\n" + new_entry

    write(CHANGELOG, new_content)


# ---------------------------------------------------------------------------
# Step 5 — update version badge in README if present
# ---------------------------------------------------------------------------

def update_readme(version):
    print(f"\n[5] Checking {README} for version badge...")
    content = read(README)
    new_content = re.sub(
        r"version-\d+\.\d+\.\d+-",
        f"version-{version}-",
        content
    )
    if new_content != content:
        write(README, new_content)
        print(f"  [UPDATED] Version badge → {version}")
    else:
        print("  [SKIP] No version badge found")


# ---------------------------------------------------------------------------
# Step 6 — run tests
# ---------------------------------------------------------------------------

def run_tests():
    print("\n[6] Running test suite...")
    result = subprocess.run("pytest tests/ -q", shell=True, capture_output=True, text=True)
    summary = [l for l in result.stdout.splitlines() if "passed" in l or "failed" in l or "error" in l]
    for line in summary:
        print(f"  {line}")
    if result.returncode != 0:
        print("[ERROR] Tests failed — aborting release.")
        print(result.stdout[-2000:])
        sys.exit(1)
    print("  [OK] All tests passed")


# ---------------------------------------------------------------------------
# Step 7 — commit and tag
# ---------------------------------------------------------------------------

def commit_and_tag(version, message):
    print(f"\n[7] Committing and tagging v{version}...")
    run("git add -A")
    run(f'git commit -m "v{version} — {message}"')
    run(f"git tag v{version}")
    print(f"  [TAGGED] v{version}")
    print(f"\n  To push:  git push origin main --tags")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def prompt_version_part():
    """Interactively ask which part of the version to bump."""
    current = get_current_version()
    parts = current.split(".")
    major, minor, patch_n = int(parts[0]), int(parts[1]), int(parts[2])

    print(f"\nCurrent version: {current}")
    print("\nWhat kind of release is this?")
    print(f"  [1] patch  — bug fix         ({current} → {major}.{minor}.{patch_n + 1})")
    print(f"  [2] minor  — new feature     ({current} → {major}.{minor + 1}.0)")
    print(f"  [3] major  — breaking change ({current} → {major + 1}.0.0)")
    choice = input("\nChoose [1/2/3] (default: 1): ").strip() or "1"
    return {"1": "patch", "2": "minor", "3": "major"}.get(choice, "patch")


def get_current_version():
    content = read(VERSION_FILE)
    match = re.search(r'"VERSION":\s*"(\d+\.\d+\.\d+)"', content)
    return match.group(1) if match else "unknown"


REQUIRED_EXAMPLE_CONFIG_KEYS = [
    "METHOD",
    "TOP_N",
    "MINUTES_BETWEEN_MESSAGES",
    "POST_WEEKENDS",
    "SEND_GAME_UPDATES",
    "SEND_DAILY_SUMMARY",
    "SLACK_WEBHOOK_URL",
    "SLACK_MANAGER_ID",
    "MANUAL_TOP",
    "LIVE_COUNTER_URL",
    "POOLS",
    "PLAYWRIGHT_HEADLESS",
    "PLAYWRIGHT_STATE",
    "TOURNAMENT_END_MEN",
    "TOURNAMENT_END_WOMEN",
]

EXAMPLE_CONFIG = Path("bot_setup/example.config.json")


def check_example_config():
    print("\n[*] Checking example.config.json has all required keys...")
    if not EXAMPLE_CONFIG.exists():
        print(f"  [ERROR] {EXAMPLE_CONFIG} not found")
        sys.exit(1)
    data = json.loads(EXAMPLE_CONFIG.read_text())
    missing = [k for k in REQUIRED_EXAMPLE_CONFIG_KEYS if k not in data]
    if missing:
        print(f"  [ERROR] example.config.json is missing keys: {missing}")
        sys.exit(1)
    print("  [OK] example.config.json contains all required keys")


def main():
    parser = argparse.ArgumentParser(description="March Madness Bot release agent")
    parser.add_argument("part", choices=["patch", "minor", "major"],
                        nargs="?", default=None,
                        help="Version part to bump — omit to be prompted")
    parser.add_argument("--message", "-m", default=None,
                        help="Changelog entry and commit message")
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        print("[DRY RUN] No files will be written or committed.\n")

    # Prompt if not provided as argument
    part = args.part or prompt_version_part()

    message = args.message
    if not message:
        message = input("\nChangelog entry / commit message: ").strip()
        if not message:
            print("[ERROR] Commit message is required.")
            sys.exit(1)

    ensure_gitignore()
    untrack_sensitive_files()
    check_example_config()

    if not args.dry_run:
        version = bump_version(part)
        update_changelog(version, message)
        update_readme(version)

        if not args.skip_tests:
            run_tests()

        commit_and_tag(version, message)
        print(f"\n✅ Released v{version}")
    else:
        print(f"\n[DRY RUN] Would bump '{part}' → next version")
        print(f"[DRY RUN] Complete — re-run without --dry-run to apply.")


if __name__ == "__main__":
    main()