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

def main():
    parser = argparse.ArgumentParser(description="March Madness Bot release agent")
    parser.add_argument("part", choices=["patch", "minor", "major"],
                        nargs="?", default="patch",
                        help="Version part to bump (default: patch)")
    parser.add_argument("--message", "-m", default="Maintenance update",
                        help="Changelog entry and commit message")
    parser.add_argument("--skip-tests", action="store_true",
                        help="Skip test suite (not recommended)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview changes without writing anything")
    args = parser.parse_args()

    if args.dry_run:
        print("[DRY RUN] No files will be written or committed.\n")

    ensure_gitignore()
    untrack_sensitive_files()

    if not args.dry_run:
        version = bump_version(args.part)
        update_changelog(version, args.message)
        update_readme(version)

        if not args.skip_tests:
            run_tests()

        commit_and_tag(version, args.message)
        print(f"\n✅ Released v{version}")
    else:
        print("\n[DRY RUN] Complete — re-run without --dry-run to apply.")


if __name__ == "__main__":
    main()