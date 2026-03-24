#!/usr/bin/env python3
"""
Release agent — runs pre-release checks and bumps the version.

Usage:
    python3 scripts/release_agent.py [--dry-run]
"""
import argparse
import subprocess
import sys
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent
CHANGELOG = ROOT / "CHANGELOG.md"


def run(cmd, capture=False):
    result = subprocess.run(cmd, shell=True, capture_output=capture, text=True)
    if result.returncode != 0:
        print(f"[FAIL] {cmd}\n{result.stderr}")
        sys.exit(1)
    return result.stdout.strip() if capture else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--minor", action="store_true",
                        help="Minor release: bump minor version and reset patch to 0")
    parser.add_argument("--major", action="store_true",
                        help="Major release: bump major version and reset minor+patch to 0")
    args = parser.parse_args()

    print("🏀 March Madness Bot — Release Agent")
    print(f"   {date.today()}\n")

    # 1. Tests must pass
    print("  Running pytest...")
    run(f"{sys.executable} -m pytest --tb=short -q")
    print("  ✅ All tests passed\n")

    # 2. No critical findings
    print("  Running review agent...")
    result = subprocess.run(
        f"{sys.executable} scripts/review_agent.py 2>&1",
        shell=True, capture_output=True, text=True
    )
    output = result.stdout + result.stderr
    criticals = re.findall(r"🔴 CRITICAL \((\d+)\)", output)
    n_critical = int(criticals[0]) if criticals else 0
    if n_critical > 0:
        print(f"  ❌ {n_critical} critical findings — fix before releasing.")
        print(output)
        sys.exit(1)
    print("  ✅ 0 critical findings\n")

    # 3. No uncommitted changes
    dirty = subprocess.run("git status --porcelain", shell=True, capture_output=True, text=True).stdout.strip()
    if dirty:
        print(f"  ❌ Uncommitted changes:\n{dirty}")
        sys.exit(1)
    print("  ✅ Working tree clean\n")

    # 4. Determine next version from CHANGELOG
    text = CHANGELOG.read_text()
    versions = re.findall(r"## \[(\d+\.\d+\.\d+)\]", text)
    if not versions:
        print("  ❌ No version found in CHANGELOG.md")
        sys.exit(1)
    latest = versions[0]
    major, minor, patch = map(int, latest.split("."))

    if args.major:
        next_ver = f"{major + 1}.0.0"
    elif args.minor:
        next_ver = f"{major}.{minor + 1}.0"
    else:
        next_ver = f"{major}.{minor}.{patch + 1}"

    print(f"  Current version : {latest}")
    print(f"  Next version    : {next_ver}\n")

    if args.dry_run:
        print("  [dry-run] Skipping tag + push.")
        return

    # 5. Tag and push
    run(f'git tag -a v{next_ver} -m "Release v{next_ver}"')
    run("git push origin main --tags")
    print(f"  ✅ Tagged and pushed v{next_ver}")


if __name__ == "__main__":
    main()