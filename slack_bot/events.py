import re
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


WELCOME_MESSAGE = (
    "👋 Hey! I'm the March Madness bot — I track bracket standings and post "
    "score updates to the channel.\n\n"
    "🏀 *Do you have any personal bracket pools you'd like me to track privately?* "
    "(e.g. a friends group, family pool, or side bet)\n\n"
    "If yes, reply with the URL to your bracket pool and I'll set it up just for you. "
    "Reply `no thanks` to skip — you can always ask me later!"
)

CONFIRMATION_MESSAGE = (
    "✅ Got it! I'll keep an eye on that pool and DM you updates privately. "
    "You won't be bothered during off-days 🙂"
)

DECLINE_MESSAGE = (
    "No problem! If you ever want to add a personal pool later, "
    "just DM me a bracket URL and I'll get it set up."
)

UNRECOGNISED_MESSAGE = (
    "Hmm, I didn't quite catch that 🤔 "
    "Send me a bracket URL to track it, or reply `no thanks` to skip."
)

SUPPORTED_DOMAINS = ("cbssports.com", "espn.com", "yahoo.com")


def _looks_like_bracket_url(text):
    return any(domain in text for domain in SUPPORTED_DOMAINS)


def _open_dm(client, user_id):
    resp = client.conversations_open(users=user_id)
    return resp["channel"]["id"]


def handle_member_joined(event, client: WebClient, private_pools: dict, save_fn):
    """
    Called when a member_joined_channel event fires.
    Sends a DM asking if they have a personal bracket pool.
    """
    user_id = event.get("user")
    if not user_id:
        return

    try:
        channel_id = _open_dm(client, user_id)
        client.chat_postMessage(channel=channel_id, text=WELCOME_MESSAGE)
        print(f"[INFO] Sent bracket onboarding DM to {user_id}")
    except SlackApiError as e:
        print(f"[WARN] Could not DM user {user_id}: {e}")


def handle_dm_reply(event, client: WebClient, private_pools: dict, save_fn):
    """
    Called when a message arrives in a DM channel.
    Handles the user's response to the onboarding prompt.
    """
    user_id = event.get("user")
    text = (event.get("text") or "").strip().lower()

    if not user_id or event.get("bot_id"):
        return

    if _looks_like_bracket_url(text):
        url = re.search(r'https?://\S+', event.get("text", ""))
        if url:
            bracket_url = url.group(0)
            private_pools[user_id] = bracket_url
            save_fn(private_pools)

            try:
                channel_id = _open_dm(client, user_id)
                client.chat_postMessage(channel=channel_id, text=CONFIRMATION_MESSAGE)
                print(f"[INFO] Saved private pool for {user_id}: {bracket_url}")
            except SlackApiError as e:
                print(f"[WARN] Could not confirm DM to {user_id}: {e}")
        return

    if any(phrase in text for phrase in ("no", "skip", "no thanks", "nope", "pass")):
        try:
            channel_id = _open_dm(client, user_id)
            client.chat_postMessage(channel=channel_id, text=DECLINE_MESSAGE)
        except SlackApiError as e:
            print(f"[WARN] Could not send decline message to {user_id}: {e}")
        return

    # Unrecognised reply
    try:
        channel_id = _open_dm(client, user_id)
        client.chat_postMessage(channel=channel_id, text=UNRECOGNISED_MESSAGE)
    except SlackApiError as e:
        print(f"[WARN] Could not send unrecognised message to {user_id}: {e}")