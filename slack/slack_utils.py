import datetime
import requests


def post_message(config, text=None, blocks=None, mock=False):
    """Post a message to Slack or print mock output."""
    today = datetime.datetime.now().weekday()
    if not config.get("POST_WEEKENDS", False) and today >= 5:
        print("[INFO] Skipping — weekend posting disabled")
        return {}

    if mock:
        print("[MOCK] Would post:", text or blocks)
        return {}

    webhook_url = config.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        print("[WARN] No webhook URL set.")
        return {}

    if not text and not blocks:
        print("[WARN] post_message called with no text or blocks — skipping.")
        return {}

    payload = {}
    if text:
        payload["text"] = text
    if blocks:
        payload["blocks"] = blocks

    for attempt in range(2):
        try:
            resp = requests.post(webhook_url, json=payload, timeout=10)
            resp.raise_for_status()
            if resp.text == "ok":
                return {"ok": True}
            try:
                return resp.json()
            except ValueError:
                print(f"[WARN] Unexpected Slack response: {resp.text}")
                return {"ok": False, "error": resp.text}
        except requests.exceptions.ConnectionError as e:
            if attempt == 0:
                print(f"[WARN] Connection error posting to Slack, retrying... ({e})")
                continue
            print(f"[ERROR] Failed to post message after retry: {e}")
            return {}
        except Exception as e:
            print(f"[ERROR] Failed to post message: {e}")
            return {}

    return {}