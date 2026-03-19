from playwright.sync_api import sync_playwright

CBS_WOMEN_URL = "https://picks.cbssports.com/college-basketball/ncaaw-tournament/bracket/pools/kbxw63b2ge3deojqhazts===/standings"
SESSION_FILE_WOMEN = "playwright_state_women.json"

def login_and_save_women():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(CBS_WOMEN_URL)

        print("⚠️ Please log in manually for the women’s pool...")
        page.wait_for_timeout(10000)  # 10 seconds to log in

        context.storage_state(path=SESSION_FILE_WOMEN)
        print(f"[INFO] Women’s session saved to {SESSION_FILE_WOMEN}")
        browser.close()

if __name__ == "__main__":
    login_and_save_women()