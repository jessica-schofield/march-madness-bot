# src/sources/cbs.py

import asyncio
from playwright.async_api import async_playwright

async def ensure_cbs_login(pool, playwright_state):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # Navigate to CBS login page
        await page.goto("https://www.cbs.com/login")

        # Perform login actions
        await page.fill("input[name='username']", pool.get("CBS_USERNAME", ""))
        await page.fill("input[name='password']", pool.get("CBS_PASSWORD", ""))
        await page.click("button[type='submit']")

        # Wait for navigation after login
        await page.wait_for_navigation()

        # Save cookies or session state if needed
        cookies = await context.cookies()
        await save_playwright_state(cookies, playwright_state)

        await browser.close()

async def get_top_n_async(url, top_n, playwright_state):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        await load_playwright_state(context, playwright_state)
        page = await context.new_page()

        await page.goto(url)

        # Scrape leaderboard data
        leaderboard_data = await page.evaluate(f"""
            () => {{
                const rows = Array.from(document.querySelectorAll('.leaderboard-row'));
                return rows.slice(0, {top_n}).map(row => {{
                    return {{
                        name: row.querySelector('.name').innerText,
                        score: row.querySelector('.score').innerText
                    }};
                }});
            }}
        """)

        await browser.close()
        return leaderboard_data

async def save_playwright_state(cookies, playwright_state):
    # Implement saving cookies or session state logic here
    pass

async def load_playwright_state(context, playwright_state):
    # Implement loading cookies or session state logic here
    pass