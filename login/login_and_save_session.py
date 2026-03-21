from playwright.sync_api import sync_playwright

SESSION_FILE = "playwright_state.json"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)  # visible browser
    context = browser.new_context()
    page = context.new_page()

    # Go to CBS login
    page.goto("https://www.cbssports.com/login/")

    print("👉 Log in manually in the browser window...")
    input("Press ENTER after you are fully logged in and can see your bracket...")

    # Save session (cookies, localStorage, etc.)
    context.storage_state(path=SESSION_FILE)

    print("✅ Session saved!")
    browser.close()