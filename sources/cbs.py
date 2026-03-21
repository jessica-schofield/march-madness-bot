import asyncio
import json
import re
import requests
from pathlib import Path
from urllib.parse import urlparse, urlencode
from playwright.async_api import async_playwright


def same_domain(url1, url2):
    if not url1 or not url2:
        return False
    return urlparse(url1).netloc == urlparse(url2).netloc


def detect_site(url):
    if not url:
        return "unknown"
    netloc = urlparse(url).netloc.lower()
    if "cbssports.com" in netloc:
        return "cbs"
    if "espn.com" in netloc:
        return "espn"
    if "yahoo.com" in netloc:
        return "yahoo"
    return "unknown"


def _extract_espn_group_id(url):
    """
    Extract the UUID group ID from any ESPN TC URL format.
    Handles both:
      - /group?id=b1e6fb01-f1eb-450b-8b77-0b994d62563e
      - /group?groupID=b1e6fb01-...
    """
    m = re.search(r'[?&](?:id|groupID)=([\w-]{10,})', url, re.IGNORECASE)
    return m.group(1) if m else None


def _get_espn_cookies(playwright_state_path):
    """Load ESPN cookies from saved Playwright state."""
    state_path = Path(playwright_state_path)
    if not state_path.exists():
        return {}
    try:
        state = json.loads(state_path.read_text())
        cookies = {
            c["name"]: c["value"]
            for c in state.get("cookies", [])
            if "espn.com" in c.get("domain", "")
        }
        return cookies
    except Exception as e:
        print(f"[WARN] Failed to load ESPN cookies: {e}")
        return {}


def _fetch_espn_group_api(group_id, cookies, challenge_id=277, limit=200):
    """
    Call the ESPN gambit API directly to get group standings.
    Returns raw API response dict, or None on failure.

    challenge_id 277 = Men's 2026 TC. Women's will be different — we detect it below.
    """
    filter_param = json.dumps({
        "filterSortId": {"value": 0},
        "limit": limit,
        "offset": 0
    })
    params = {
        "platform": "chui",
        "view": "chui_default_group",
        "filter": filter_param,
    }
    url = (
        f"https://gambit-api.fantasy.espn.com/apis/v1/challenges/"
        f"{challenge_id}/groups/{group_id}/"
        f"?{urlencode(params)}"
    )
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json",
        "Referer": "https://fantasy.espn.com/",
        "Origin": "https://fantasy.espn.com",
    }

    print(f"[DEBUG] ESPN API call: {url[:120]}...")
    try:
        resp = requests.get(url, headers=headers, cookies=cookies, timeout=15)
        print(f"[DEBUG] ESPN API status: {resp.status_code}")
        if resp.status_code != 200:
            print(f"[WARN] ESPN API returned {resp.status_code}")
            return None
        return resp.json()
    except Exception as e:
        print(f"[WARN] ESPN API request failed: {e}")
        return None


def _detect_espn_challenge_id(url, cookies):
    """
    Look up the challenge ID for this ESPN TC year/gender from the challenge slug.
    Falls back to 277 (Men's 2026) if it can't determine it.
    """
    slug_match = re.search(
        r'(tournament-challenge-bracket(?:-women)?-\d{4})',
        url, re.IGNORECASE
    )
    slug = slug_match.group(1).lower() if slug_match else "tournament-challenge-bracket-2026"

    try:
        meta_url = (
            f"https://gambit-api.fantasy.espn.com/apis/v1/challenges/{slug}/"
            f"?platform=chui&view=chui_default"
        )
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://fantasy.espn.com/",
        }
        resp = requests.get(meta_url, headers=headers, cookies=cookies, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            challenge_id = data.get("id")
            if challenge_id:
                print(f"[DEBUG] ESPN challenge ID for '{slug}': {challenge_id}")
                return challenge_id
    except Exception as e:
        print(f"[WARN] Could not detect ESPN challenge ID: {e}")

    print(f"[DEBUG] Falling back to challenge ID 277")
    return 277


def _parse_espn_api_response(data, logged_in_display_name=None):
    """
    Parse the gambit API group response into (rank, name, points) tuples.

    Response structure (confirmed from DevTools):
    {
      "entries": [
        {
          "rank": 1,
          "entryId": "...",
          "entryName": "Ahersh22's Picks 1",
          "displayName": "Amy Hersheway",
          "totalPoints": 120,
          "isViewer": true   <- this is the logged-in user
        },
        ...
      ]
    }
    """
    entries = data.get("entries", [])
    if not entries:
        print(f"[WARN] ESPN API response had no entries. Keys: {list(data.keys())}")
        return []

    print(f"[DEBUG] ESPN API returned {len(entries)} entries")

    results = []
    seen = set()

    for entry in entries:
        try:
            rank = entry.get("rank") or entry.get("standing")
            name = entry.get("entryName") or entry.get("displayName") or entry.get("name")
            points = entry.get("totalPoints") or entry.get("points") or 0
            is_viewer = entry.get("isViewer", False)

            if not name or rank is None:
                continue

            if is_viewer:
                print(f"[DEBUG] Skipping pinned viewer entry: {name} (rank {rank})")
                continue
            if logged_in_display_name and name == logged_in_display_name:
                print(f"[DEBUG] Skipping pinned logged-in user by name match: {name}")
                continue

            key = f"{rank}|{name}"
            if key in seen:
                continue
            seen.add(key)

            results.append((int(rank), str(name), int(points)))
        except Exception as e:
            print(f"[WARN] Skipping ESPN entry: {e} — {entry}")
            continue

    results.sort(key=lambda x: x[0])
    print(f"[DEBUG] ESPN parsed {len(results)} entries (viewer row excluded)")
    for r in results[:5]:
        print(f"  Rank {r[0]}: {r[1]} ({r[2]} pts)")

    return results


async def _get_espn_groups_api(group_id, cookies, challenge_id=277):
    """
    Check if the user has multiple ESPN groups via the members API.
    Returns list of {name, groupId, url} dicts.
    """
    try:
        url = (
            f"https://gambit-api.fantasy.espn.com/apis/v1/challenges/"
            f"{challenge_id}/members/?platform=chui&view=chui_default"
        )
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://fantasy.espn.com/"}
        resp = requests.get(url, headers=headers, cookies=cookies, timeout=10)
        if resp.status_code != 200:
            return []
        data = resp.json()

        groups = []
        seen = set()
        for entry in data.get("entries", []):
            for cg in entry.get("challengeGroups", []):
                gid = cg.get("groupId")
                gname = cg.get("groupName") or gid
                if gid and gid not in seen:
                    seen.add(gid)
                    groups.append({
                        "name": gname,
                        "groupId": gid,
                        "url": f"https://fantasy.espn.com/games/tournament-challenge-bracket-2026/group?id={gid}"
                    })
        return groups
    except Exception as e:
        print(f"[WARN] Could not fetch ESPN groups: {e}")
        return []


def _format_user(rank: int, name: str, points: int) -> str:
    """Format a leaderboard entry as a display string."""
    if points > 0:
        pt_label = "pt" if points == 1 else "pts"
        return f"{name} ({points} {pt_label})"
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(rank, "th")
    return f"{name} ({rank}{suffix} place)"


def _build_top_n(all_users: list, n: int) -> list:
    """Slice sorted (rank, name, points) list to top-n, respecting ties."""
    if not all_users:
        return []
    all_users.sort(key=lambda x: x[0])
    cutoff_rank = all_users[min(n, len(all_users)) - 1][0]
    return [
        _format_user(rank, name, points)
        for rank, name, points in all_users
        if rank <= cutoff_rank
    ]


def get_espn_top_n(url, n=5, playwright_state=None, slack_user_id=None):
    """
    Fetch ESPN Tournament Challenge group standings via the gambit JSON API.
    Uses saved Playwright cookies for auth — no browser needed.
    """
    state_path = str(playwright_state) if playwright_state else "playwright_state.json"
    cookies = _get_espn_cookies(state_path)
    if not cookies:
        print("[WARN] No ESPN cookies found — login state missing or expired.")
        return []

    group_id = _extract_espn_group_id(url)
    if not group_id:
        print(f"[WARN] Could not extract ESPN group ID from URL: {url}")
        return []

    print(f"[DEBUG] ESPN group ID: {group_id}")

    challenge_id = _detect_espn_challenge_id(url, cookies)
    data = _fetch_espn_group_api(group_id, cookies, challenge_id=challenge_id)
    if data is None:
        return []

    all_groups = asyncio.run(_get_espn_groups_api(group_id, cookies, challenge_id))
    if len(all_groups) > 1:
        print(f"[INFO] Multiple ESPN groups found: {[g['name'] for g in all_groups]}")
        chosen = _pick_espn_group_sync(all_groups, group_id, slack_user_id)
        if chosen["groupId"] != group_id:
            data = _fetch_espn_group_api(chosen["groupId"], cookies, challenge_id)
            if data is None:
                return []

    all_users = _parse_espn_api_response(data)
    top_users = _build_top_n(all_users, n)
    print(f"[DEBUG] ESPN top {n}: {top_users}")
    return top_users


def _pick_espn_group_sync(groups, current_group_id, slack_user_id=None):
    """Ask the user to pick which ESPN group to track. Returns chosen group dict."""
    default = next((g for g in groups if g["groupId"] == current_group_id), groups[0])
    group_list = "\n".join(f"{i+1}. {g['name']}" for i, g in enumerate(groups))

    if slack_user_id:
        from slack_dm import send_dm, poll_for_reply
        channel_id, ts = send_dm(
            slack_user_id,
            f"🏀 I found multiple ESPN bracket groups — which one should I track?\n\n"
            f"{group_list}\n\n"
            f"Reply with the number (e.g. `1`)."
        )
        reply = poll_for_reply(channel_id, ts, timeout_seconds=600)
        try:
            idx = int(reply.strip()) - 1
            if 0 <= idx < len(groups):
                chosen = groups[idx]
                send_dm(slack_user_id, f"✅ Got it — I'll track *{chosen['name']}*.")
                return chosen
        except Exception:
            send_dm(slack_user_id, f"⚠️ Couldn't parse that — using *{default['name']}*.")
    else:
        print(f"\nMultiple ESPN groups found:\n{group_list}")
        try:
            idx = int(input("Which group should I track? Enter the number: ").strip()) - 1
            if 0 <= idx < len(groups):
                return groups[idx]
        except Exception:
            pass
        print(f"[WARN] Invalid choice — using '{default['name']}'.")

    return default


async def _extract_cbs(page, n):
    """Extract leaderboard from CBS Sports bracket pool page."""
    tables = await page.query_selector_all("table")
    rows = []
    for table in tables:
        table_rows = await table.query_selector_all("tbody tr")
        if len(table_rows) > len(rows):
            rows = table_rows

    if not rows:
        return None  # signal caller to dump HTML debug

    # CBS columns: 0=RANK, 1=CHAMPION, 2=BRACKET NAME, 3=PTS
    NAME_COL, PTS_COL, RANK_COL = 2, 3, 0
    all_users = []
    for row in rows:
        try:
            cells = await row.query_selector_all("td")
            if len(cells) <= PTS_COL:
                continue
            rank_text = (await cells[RANK_COL].inner_text()).strip()
            name = (await cells[NAME_COL].inner_text()).strip()
            points_text = (await cells[PTS_COL].inner_text()).strip()
            try:
                rank = int(rank_text)
            except ValueError:
                continue
            try:
                points = int(points_text)
            except ValueError:
                points = 0
            if name:
                all_users.append((rank, name, points))
        except Exception as e:
            print(f"[WARN] Skipping CBS row: {e}")
            continue

    return all_users


async def _extract_espn(page, n):
    """
    Extract leaderboard from ESPN Tournament Challenge group page.

    Page structure (confirmed from DevTools):
      GROUP RESULTS
        MY BRACKETS header    <- skip entire section (pinned logged-in user)
          rank | champ | bracket name / display name
        GROUP BRACKETS header <- this is the real leaderboard
          rank | champ | bracket name / display name
          ...

    There are no <table> elements — it's all divs.
    We find the GROUP BRACKETS section heading and collect sibling rows after it.
    """
    await page.wait_for_timeout(4000)

    for _ in range(3):
        await page.evaluate("window.scrollBy(0, 500)")
        await page.wait_for_timeout(600)
    await page.wait_for_timeout(1000)

    all_users = await page.evaluate("""
        () => {
            const headings = Array.from(document.querySelectorAll('*')).filter(el =>
                el.children.length === 0 &&
                el.textContent.trim().toUpperCase() === 'GROUP BRACKETS'
            );

            if (headings.length === 0) {
                console.log('[ESPN] Could not find GROUP BRACKETS heading');
                return null;
            }

            const heading = headings[0];
            console.log('[ESPN] Found GROUP BRACKETS heading:', heading.className);

            let section = heading;
            for (let i = 0; i < 5; i++) {
                if (!section.parentElement) break;
                section = section.parentElement;
                if (section.children.length >= 3) break;
            }

            const results = [];
            const seen = new Set();
            const allEls = Array.from(section.querySelectorAll('*'));

            let pastHeading = false;
            for (const el of allEls) {
                const txt = el.textContent.trim().toUpperCase();
                if (txt === 'GROUP BRACKETS') {
                    pastHeading = true;
                    continue;
                }
                if (!pastHeading) continue;

                const leaves = Array.from(el.querySelectorAll('*'))
                    .filter(c => c.children.length === 0 && c.textContent.trim())
                    .map(c => c.textContent.trim());

                if (leaves.length < 2) continue;

                const rankLeaf = leaves.find(l => /^\\d{1,3}$/.test(l) && parseInt(l) <= 500);
                if (!rankLeaf) continue;
                const rank = parseInt(rankLeaf);

                const name = leaves.find(l =>
                    !/^\\d+$/.test(l) &&
                    l.length > 2 &&
                    !['RANK', 'CHAMP', 'MY BRACKETS', 'GROUP BRACKETS'].includes(l.toUpperCase())
                );
                if (!name) continue;

                const key = `${rank}|${name}`;
                if (seen.has(key)) continue;
                seen.add(key);

                results.push({ rank, name, points: 0 });
            }

            return results;
        }
    """)

    if all_users is None:
        headings = await page.evaluate("""
            () => Array.from(document.querySelectorAll('*'))
                .filter(el => el.children.length === 0 && el.textContent.trim().length < 40)
                .map(el => el.textContent.trim())
                .filter(t => t.length > 2)
                .slice(0, 40)
        """)
        print(f"[DEBUG] ESPN leaf text nodes (first 40): {headings}")
        return None

    print(f"[DEBUG] ESPN extracted {len(all_users)} entries from GROUP BRACKETS section:")
    for u in all_users[:10]:
        print(f"  Rank {u['rank']}: {u['name']}")

    return [(u["rank"], u["name"], u["points"]) for u in all_users]


async def _extract_yahoo(page, n):
    """
    Extract leaderboard from Yahoo Tourney Pick'em group page.
    Yahoo renders standings in a table. Columns: Rank | Team/Entry | Pts | Correct | ...
    """
    await page.wait_for_timeout(4000)

    rows = await page.query_selector_all(
        "table tbody tr, .yPickemStandings tr, [data-tst='standings-row']"
    )

    if not rows:
        return None

    all_users = []

    for row in rows:
        try:
            cells = await row.query_selector_all("td")
            if len(cells) < 3:
                continue

            texts = [(await c.inner_text()).strip() for c in cells]
            print(f"[DEBUG] Yahoo row cells: {texts}")

            rank = None
            name = None
            points = 0

            try:
                rank = int(texts[0].rstrip("T").rstrip("t").rstrip("."))
            except (ValueError, IndexError):
                continue

            if len(texts) > 1:
                name = texts[1].split("\n")[0].strip()

            if len(texts) > 2:
                try:
                    points = int(texts[2].replace(",", ""))
                except ValueError:
                    points = 0

            if not name:
                continue

            all_users.append((rank, name, points))

        except Exception as e:
            print(f"[WARN] Skipping Yahoo row: {e}")
            continue

    return all_users


async def get_top_n_async(url, n=5, playwright_state=None, slack_user_id=None):
    """
    slack_user_id is optional — if provided and multiple ESPN groups are found,
    we'll ask which one to use via DM instead of blocking on CLI input.
    """
    state_path = Path(playwright_state) if playwright_state else Path("playwright_state.json")

    if not url:
        return []
    if not state_path.exists():
        print("[WARN] Playwright login state not found.")
        return []

    site = detect_site(url)
    print(f"[DEBUG] Detected site: {site} for URL: {url}")

    # ESPN uses the JSON API directly — no Playwright needed after login
    if site == "espn":
        return get_espn_top_n(
            url, n=n,
            playwright_state=str(state_path),
            slack_user_id=slack_user_id
        )

    # CBS and Yahoo still use Playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=str(state_path))
        page = await context.new_page()

        print(f"[DEBUG] Navigating to: {url}")
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)
        except Exception as e:
            print(f"[WARN] Page load issue: {e}")
            await browser.close()
            return []

        title = await page.title()
        print(f"[DEBUG] Page title: {title}")

        if site == "cbs":
            all_users = await _extract_cbs(page, n)
        elif site == "yahoo":
            all_users = await _extract_yahoo(page, n)
        else:
            print(f"[WARN] Unknown site for URL: {url} — attempting CBS-style extraction")
            all_users = await _extract_cbs(page, n)

        if all_users is None:
            html = await page.content()
            print(f"[DEBUG] Could not find standings table. HTML snippet:\n{html[:3000]}")
            await browser.close()
            return []

        await browser.close()

        if not all_users:
            print(f"[WARN] No users extracted from {site} page.")
            return []

        top_users = _build_top_n(all_users, n)
        print(f"[DEBUG] {site} top users: {top_users}")
        return top_users


def get_top_n(url, n=5, playwright_state=None):
    return asyncio.run(get_top_n_async(url, n, playwright_state))


async def ensure_cbs_login(pool, playwright_state_path, slack_user_id=None):
    """
    Open a browser for the user to log in to all required bracket sites.
    Groups URLs by domain so we only need one login per site.
    """
    state_path = Path(playwright_state_path)
    if state_path.exists() and state_path.stat().st_size >= 500:
        return
    if state_path.exists():
        state_path.unlink()
        print("[INFO] Old session was invalid, deleting...")

    men_url = pool.get("MEN_URL", "")
    women_url = pool.get("WOMEN_URL", "")

    urls_to_login = []
    seen_domains = set()
    for url in [men_url, women_url]:
        if not url:
            continue
        domain = urlparse(url).netloc
        if domain not in seen_domains:
            urls_to_login.append(url)
            seen_domains.add(domain)

    if not urls_to_login:
        print("[WARN] No pool URLs configured — skipping login.")
        return

    sites = [detect_site(u) for u in urls_to_login]
    site_names = " + ".join(sorted(set(s.upper() for s in sites)))
    print(f"[INFO] Login required for: {site_names}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()

        for url in urls_to_login:
            site = detect_site(url)
            page = await context.new_page()
            await page.goto(url)

            if slack_user_id:
                from slack_dm import send_dm, poll_for_reply
                channel_id, ts = send_dm(
                    slack_user_id,
                    f"🌐 A browser window just opened for *{site.upper()}*!\n\n"
                    f"1. Log in to {site.upper()} in that window\n"
                    "2. Once you can see your bracket standings, reply `done` here ✅"
                )
                print(f"[INFO] Waiting for Slack 'done' reply for {site}...")
                poll_for_reply(channel_id, ts, timeout_seconds=300)
            else:
                input(f"[ACTION] Log in to {site.upper()} in the browser window, then press Enter here...")

        await context.storage_state(path=str(state_path))
        await browser.close()
        print(f"[INFO] Login session saved for: {site_names}")


def deduplicate_top_users(top_list):
    seen = set()
    result = []
    for u in top_list:
        name = u["name"] if isinstance(u, dict) else u.split(" (")[0]
        if name not in seen:
            seen.add(name)
            result.append(u)
    return result
