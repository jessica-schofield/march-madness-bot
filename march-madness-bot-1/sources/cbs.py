# filepath: /Users/jess/march-madness-bot/sources/cbs.py

import asyncio
from playwright.async_api import async_playwright

async def ensure_cbs_login(pool, state_file):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # Navigate to CBS Sports login page
        await page.goto("https://www.cbssports.com/")
        
        # Perform login actions here (fill in username and password)
        # Example:
        # await page.fill('input[name="username"]', pool["USERNAME"])
        # await page.fill('input[name="password"]', pool["PASSWORD"])
        # await page.click('button[type="submit"]')

        # Wait for navigation after login
        await page.wait_for_navigation()

        # Save the state for future sessions
        await context.storage_state(path=state_file)

        await browser.close()

async def get_top_n_async(url, top_n, state_file):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=state_file)
        page = await context.new_page()

        await page.goto(url)

        # Logic to scrape the leaderboard data
        # Example:
        # leaderboard_data = await page.query_selector_all('.leaderboard-item')
        # top_users = [await item.inner_text() for item in leaderboard_data[:top_n]]

        await browser.close()
        return top_users

def deduplicate_top_users(top_users):
    seen = set()
    deduplicated = []
    for user in top_users:
        if user not in seen:
            seen.add(user)
            deduplicated.append(user)
    return deduplicated