from playwright.sync_api import sync_playwright

CBS_MEN_URL = "https://picks.cbssports.com/college-basketball/ncaa-tournament/bracket/pools/kbxw63b2ge3deojqg4ydq===/standings"
SESSION_FILE_MEN = "playwright_state_men.json"

def login_and_save_men():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(CBS_MEN_URL)

        print("⚠️ Please log in manually for the men’s pool...")
        page.wait_for_timeout(10000)  # 10 seconds to log in

        context.storage_state(path=SESSION_FILE_MEN)
        print(f"[INFO] Men’s session saved to {SESSION_FILE_MEN}")
        browser.close()

if __name__ == "__main__":
    login_and_save_men()