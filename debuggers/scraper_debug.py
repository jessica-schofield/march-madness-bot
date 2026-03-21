"""
Run this standalone to debug leaderboard scraping for any bracket site.

Usage:
    python3 scraper_debug.py <url>
"""

import asyncio
import sys
import re
from pathlib import Path
from collections import Counter
from playwright.async_api import async_playwright

PLAYWRIGHT_STATE = "playwright_state.json"

# ESPN URL patterns to try for group standings
# groupID will be extracted from the input URL and substituted in
ESPN_STANDINGS_PATTERNS = [
    "https://fantasy.espn.com/games/tournament-challenge-bracket-2026/group?id={groupID}",
    "https://fantasy.espn.com/games/tournament-challenge-bracket-2026/group?id={groupID}&view=standings",
    "https://fantasy.espn.com/games/tournament-challenge-bracket-2026/group?id={groupID}&tab=standings",
    # legacy URL style — keep as fallback
    "https://fantasy.espn.com/tournament-challenge-bracket/2026/en/group?groupID={groupID}&view=standings",
    "https://fantasy.espn.com/tournament-challenge-bracket/2026/en/group?groupID={groupID}&tab=standings",
]


def extract_group_id(url):
    # UUID style: id=b1e6fb01-f1eb-450b-8b77-...
    m = re.search(r'[?&]id=([\w-]+)', url, re.IGNORECASE)
    if m:
        return m.group(1)
    # Legacy style: groupID=12345
    m = re.search(r'groupID=(\w+)', url, re.IGNORECASE)
    if m:
        return m.group(1)
    return None


async def try_url(page, url, label):
    print(f"\n[TRY] {label}")
    print(f"      {url}")
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(4000)
        title = await page.title()
        current_url = page.url
        body = await page.inner_text("body")

        # Score this page — higher = more likely to have standings
        score = 0
        score_reasons = []

        if "make picks" not in title.lower():
            score += 2
            score_reasons.append("not 'Make Picks'")
        if any(w in title.lower() for w in ["group", "standing", "leaderboard"]):
            score += 3
            score_reasons.append("title has standing/group keyword")
        if any(w in body.lower() for w in ["rank", "points", "standings", "leaderboard"]):
            score += 2
            score_reasons.append("body has rank/points keywords")

        tables = await page.query_selector_all("table")
        if tables:
            score += 5
            score_reasons.append(f"{len(tables)} table(s) found")

        # Check for repeated row-like elements
        row_els = await page.query_selector_all("[class*='row'],[class*='entry'],[class*='member'],[class*='item']")
        if len(row_els) > 5:
            score += 3
            score_reasons.append(f"{len(row_els)} row-like elements")

        print(f"      Title: '{title}'")
        print(f"      Final URL: {current_url}")
        print(f"      Score: {score}/13 — {', '.join(score_reasons) or 'nothing useful found'}")

        return score, current_url, title

    except Exception as e:
        print(f"      ❌ Failed: {e}")
        return -1, url, ""


async def debug_page(url):
    state_path = Path(PLAYWRIGHT_STATE)
    if not state_path.exists():
        print("[ERROR] No playwright_state.json found — run the bot first to log in.")
        return

    group_id = extract_group_id(url)
    print(f"\n[DEBUG] Extracted groupID: {group_id}")

    # Collect all network requests so we can spot the standings API call
    api_calls = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(storage_state=str(state_path))
        page = await context.new_page()

        # ── Intercept all requests ────────────────────────────────────────────
        async def on_request(request):
            req_url = request.url
            if any(w in req_url.lower() for w in [
                "entry", "scoring", "standing", "member", "leaderboard",
                "rank", "group", "bracket", "picks"
            ]):
                if request.resource_type in ("fetch", "xhr"):
                    api_calls.append(req_url)
                    print(f"  [NET] {request.resource_type.upper()}: {req_url[:120]}")

        page.on("request", on_request)

        # ── PHASE 1: Try URL patterns ─────────────────────────────────────────
        print("\n══ PHASE 1: Finding the right standings URL ══")
        best_score = -1
        best_url = url
        best_title = ""

        urls_to_try = [(url, "Original URL")]
        if group_id:
            for pattern in ESPN_STANDINGS_PATTERNS:
                candidate = pattern.format(groupID=group_id)
                if candidate != url:
                    urls_to_try.append((candidate, f"Pattern: {pattern[:70]}"))

        for try_url_str, label in urls_to_try:
            score, final_url, title = await try_url(page, try_url_str, label)
            if score > best_score:
                best_score = score
                best_url = final_url
                best_title = title

        print(f"\n[DEBUG] ✅ Best URL (score {best_score}): {best_url}")
        print(f"[DEBUG] Title: '{best_title}'")

        # ── PHASE 2: Full analysis ────────────────────────────────────────────
        print(f"\n══ PHASE 2: Full analysis of best URL ══")
        print("[NET] Watching for API calls (scroll down when the browser opens)...\n")
        await page.goto(best_url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        # Scroll to trigger lazy-loaded standings
        print("[DEBUG] Scrolling to trigger lazy-loaded content...")
        for _ in range(5):
            await page.evaluate("window.scrollBy(0, 400)")
            await page.wait_for_timeout(800)

        await page.wait_for_timeout(2000)

        # ── Print captured API calls ──────────────────────────────────────────
        print(f"\n[DEBUG] Captured {len(api_calls)} relevant API/fetch calls:")
        if api_calls:
            for a in api_calls:
                print(f"  {a}")
        else:
            print("  None captured — standings may be in the initial HTML or need a tab click")

        # ── 2. Login check ────────────────────────────────────────────────────
        body_text = await page.inner_text("body")
        login_hints = ["sign in", "log in", "login", "create account", "register"]
        if any(hint in body_text.lower() for hint in login_hints):
            print("⚠️  WARNING: Login wall detected.")
        else:
            print("[DEBUG] ✅ Appears to be logged in")

        print("\n[DEBUG] Links containing 'group', 'standing', 'leaderboard':")
        all_links = await page.query_selector_all("a[href]")
        for el in all_links:
            href = (await el.get_attribute("href") or "")
            text = (await el.inner_text()).strip().replace("\n", " ")
            if any(w in href.lower() or w in text.lower() for w in ["group", "standing", "leaderboard", "my group"]):
                print(f"  '{text[:50]}' → {href[:100]}")

        tables = await page.query_selector_all("table")
        print(f"\n[DEBUG] {len(tables)} <table> element(s)")
        for i, table in enumerate(tables):
            rows = await table.query_selector_all("tbody tr")
            print(f"\n  Table {i+1}: {len(rows)} rows")
            for j, row in enumerate(rows[:7]):
                cells = await row.query_selector_all("td")
                texts = [(await c.inner_text()).strip().replace("\n", " ") for c in cells]
                classes = await row.get_attribute("class") or ""
                pin_hint = " ← ⚠️ PINNED?" if any(w in classes.lower() for w in ["pin", "sticky", "fixed", "highlight", "self", "user"]) else ""
                print(f"    Row {j+1}{pin_hint}: {texts}  [class='{classes[:60]}']")
            if len(rows) > 7:
                print(f"    ... ({len(rows) - 7} more rows)")

        print("\n[DEBUG] Leaderboard selectors:")
        selectors_to_try = [
            ".tc-group-standings__row",
            "[data-testid='standings-row']",
            "[data-testid='entry-row']",
            "[data-testid='group-standings']",
            ".standings-row",
            ".leaderboard-row",
            "[class*='standing']",
            "[class*='leaderboard']",
            "[class*='rank']",
            "[class*='entry']",
            "[class*='member']",
            "[class*='participant']",
            ".tabs__list__item",
            "[class*='tabs']",
        ]
        for sel in selectors_to_try:
            try:
                els = await page.query_selector_all(sel)
                if els:
                    print(f"\n  ✅ '{sel}' → {len(els)} element(s)")
                    for j, el in enumerate(els[:5]):
                        text = (await el.inner_text()).strip().replace("\n", " | ")
                        classes = await el.get_attribute("class") or ""
                        pin_hint = " ← ⚠️ PINNED?" if any(w in classes.lower() for w in ["pin", "sticky", "fixed", "highlight", "self", "user"]) else ""
                        print(f"     [{j+1}]{pin_hint} '{classes[:60]}' → {text[:100]}")
            except Exception:
                pass

        html = await page.content()
        print("\n[DEBUG] High-frequency CSS classes:")
        all_classes = re.findall(r'class="([^"]+)"', html)
        class_counter = Counter()
        for class_str in all_classes:
            for cls in class_str.split():
                class_counter[cls] += 1
        noise = {"true", "false", "active", "selected", "hidden", "show", "hide",
                 "flex", "block", "inline", "relative", "absolute", "static"}
        candidates = [
            (cls, count) for cls, count in class_counter.most_common(80)
            if count >= 4
            and len(cls) > 3
            and cls not in noise
            and not re.match(r'^css-[a-z0-9]+$', cls)
            and not re.match(r'^[A-Z]', cls)
        ]
        for cls, count in candidates[:25]:
            print(f"  .{cls}  (×{count})")

        pts_matches = re.findall(r'(?:points|pts|score)["\s:=]+(\d+)', html.lower())
        known_pts = sorted(set(pts_matches), key=int)[:5]
        print(f"\n[DEBUG] JS hunt for points values: {known_pts}")
        for pts in known_pts:
            try:
                els = await page.evaluate(f"""
                    () => Array.from(document.querySelectorAll('*'))
                        .filter(el => el.children.length === 0
                                   && el.textContent.trim() === '{pts}')
                        .slice(0, 2)
                        .map(el => ({{
                            tag: el.tagName,
                            cls: el.className,
                            parentTag: el.parentElement?.tagName,
                            parentCls: el.parentElement?.className || '',
                            grandparentCls: el.parentElement?.parentElement?.className || '',
                            rowText: el.closest('[class*="row"],[class*="entry"],[class*="member"],[class*="item"]')
                                       ?.innerText?.trim()?.replace(/\\n/g,' ') || ''
                        }}))
                """)
                if els:
                    print(f"\n  '{pts}':")
                    for el in els:
                        print(f"    <{el['tag'].lower()} class='{el['cls']}'>")
                        print(f"      parent:      <{el['parentTag'].lower()} class='{el['parentCls']}'>")
                        print(f"      grandparent: class='{el['grandparentCls']}'")
                        if el['rowText']:
                            print(f"      nearest row: '{el['rowText'][:120]}'")
            except Exception as e:
                print(f"  [WARN] JS eval failed for pts={pts}: {e}")

        html_after = await page.content()
        out_path = Path("debug_page.html")
        out_path.write_text(html_after, encoding="utf-8")
        print(f"\n[DEBUG] HTML saved to: {out_path.resolve()}")
        print("        Cmd+F a participant's name to find the surrounding structure.\n")

        input("[DEBUG] Browser still open — use DevTools now if needed. Press Enter to close...")
        await browser.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scraper_debug.py <url>")
        sys.exit(1)
    asyncio.run(debug_page(sys.argv[1]))