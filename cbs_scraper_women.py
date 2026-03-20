from playwright.sync_api import sync_playwright

# CBS Women’s bracket standings URL
CBS_WOMEN_URL = "https://picks.cbssports.com/college-basketball/ncaaw-tournament/bracket/pools/kbxw63b2ge3deojqhazts===/standings"
SESSION_FILE = "playwright_state.json"  # use the same saved Playwright session

def get_top_three():
    """
    Returns the top 3 bracket entries for the women’s pool
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # visible for debugging
        context = browser.new_context(storage_state=SESSION_FILE)
        page = context.new_page()
        page.goto(CBS_WOMEN_URL)
        page.wait_for_timeout(5000)  # wait for tables to render

        tables = page.query_selector_all("table")
        print(f"Found {len(tables)} tables on page (women's)")

        if len(tables) < 2:
            print("Leaderboard table not found")
            return []

        leaderboard_table = tables[1]  # skip first table (personal bracket)
        rows = leaderboard_table.query_selector_all("tr")[1:]  # skip header

        top_three = []
        for row in rows[:3]:  # only top 3
            cells = row.query_selector_all("td")
            if len(cells) >= 3:
                name = cells[2].inner_text().strip()  # Bracket Name
                points = cells[3].inner_text().strip()  # PTS column
                top_three.append(f"{name} ({points})")

        browser.close()
        return top_three


if __name__ == "__main__":
    top3 = get_top_three()
    print("👑 Current Women’s Top 3:")
    for i, entry in enumerate(top3, 1):
        print(f"{i}. {entry}")