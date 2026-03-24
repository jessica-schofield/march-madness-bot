import os
import time
import datetime
import json
from pathlib import Path
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from status.yearly_setup_reminder import next_weekday_morning

load_dotenv()

PENDING_DM_FLAG = Path("pending_dm.json")
_dm_channel_cache = {}


def get_dm_client():
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        raise ValueError("SLACK_BOT_TOKEN not set. Run setup or check your .env file.")
    return WebClient(token=token)


def open_dm_channel(user_id):
    if user_id in _dm_channel_cache:
        return _dm_channel_cache[user_id]
    client = get_dm_client()
    response = client.conversations_open(users=user_id)
    channel_id = response["channel"]["id"]
    _dm_channel_cache[user_id] = channel_id
    return channel_id


def send_dm(user_id, text, blocks=None):
    """Send a plain text DM to a user."""
    client = get_dm_client()
    channel_id = open_dm_channel(user_id)
    try:
        result = client.chat_postMessage(
            channel=channel_id,
            text=text,
            **({"blocks": blocks} if blocks else {})
        )
    except SlackApiError as e:
        print(f"[ERROR] Failed to send DM to {user_id}: {e}")
        return None, None
    return channel_id, result["ts"]


def send_dm_blocks(user_id, blocks):
    """Send block-format DM to a user."""
    client = get_dm_client()
    channel_id = open_dm_channel(user_id)
    result = client.chat_postMessage(channel=channel_id, blocks=blocks, text="March Madness Bot update")
    return channel_id, result["ts"]


def poll_for_reply(channel_id, after_ts, timeout_seconds=1800, poll_interval=5):
    """
    Poll a DM channel for a new message after after_ts.
    Returns the reply text, or None if timed out.
    """
    client = get_dm_client()
    deadline = time.time() + timeout_seconds

    print(f"[INFO] Waiting for reply in channel {channel_id} after ts={after_ts}...")

    while time.time() < deadline:
        try:
            result = client.conversations_history(
                channel=channel_id,
                oldest=after_ts,
                limit=10
            )
            messages = result.get("messages", [])
            user_messages = [
                m for m in messages
                if not m.get("bot_id")
                and not m.get("subtype")
                and m.get("text")
                and float(m.get("ts", 0)) > float(after_ts)
            ]
            if user_messages:
                user_messages.sort(key=lambda m: float(m["ts"]))
                reply = user_messages[0]["text"].strip()
                print(f"[INFO] Got reply: {reply}")
                return reply
        except SlackApiError as e:
            print(f"[WARN] Slack poll error: {e}")
        time.sleep(poll_interval)

    return None


def ask_via_dm(user_id, question, default=None, timeout_seconds=1800, optional=False):
    """
    Send a question to a user via DM and wait for their reply.
    Returns their reply text, or default if they time out.
    If optional=True, 'no' or 'skip' returns empty string without scheduling retry.
    """
    if default is not None:
        full_question = f"{question} (default: {default})\n_Reply here or type `skip` to use the default._"
    elif optional:
        full_question = f"{question}\n_Reply with a URL, or `no` to skip and be reminded tomorrow._"
    else:
        full_question = f"{question}\n_Reply here._"

    print(f"[INFO] Sending DM to {user_id}: {question}")
    channel_id, question_ts = send_dm(user_id, full_question)

    reply = poll_for_reply(channel_id, question_ts, timeout_seconds=timeout_seconds)
    if reply is None:
        return str(default) if default is not None else None

    if reply.lower() == "no" and optional:
        # User said no to an optional question — schedule retry tomorrow
        next_morning = next_weekday_morning()
        send_dm(
            user_id,
            f"👍 No problem! I'll ask again tomorrow at *{next_morning.strftime('%A %B %d at 9:00am')}*.\n"
            f"_(Reply `stop` at any time to stop being asked.)_"
        )
        save_pending_dm(user_id, question, default, optional=True)
        return None

    if reply.lower() in ("skip", "") and default is not None:
        return str(default)

    return reply


def _handle_no_response(user_id, question, default, optional=False):
    """Send timeout message and save pending DM for retry."""
    next_morning = next_weekday_morning()
    send_dm(
        user_id,
        f"⏰ No response received — no worries! I'll ask again tomorrow.\n"
        f"I'll check back in at *{next_morning.strftime('%A %B %d at 9:00am')}*. 👋\n"
        f"_(Reply `stop` at any time to stop these reminders.)_"
    )
    save_pending_dm(user_id, question, default, optional=optional)
    print(f"[INFO] DM timed out. Retry scheduled for {next_morning.strftime('%A %B %d at 9:00am')}.")


def save_pending_dm(user_id, question, default, optional=False):
    """Save the pending DM question so it can be retried at next startup."""
    data = {
        "user_id": user_id,
        "question": question,
        "default": default,
        "optional": optional,
        "retry_at": next_weekday_morning().isoformat()
    }
    PENDING_DM_FLAG.write_text(json.dumps(data))  # ← overwrites any existing pending question


def check_pending_dm():
    """
    Called at startup. If there's a pending DM question and it's time, re-ask it.
    Returns (user_id, question, default, optional) if pending and due, else None.
    """
    if not PENDING_DM_FLAG.exists():
        return None
    try:
        data = json.loads(PENDING_DM_FLAG.read_text())
        retry_at = datetime.datetime.fromisoformat(data["retry_at"])
        if datetime.datetime.now() >= retry_at:
            return data["user_id"], data["question"], data.get("default"), data.get("optional", False)
    except Exception:
        pass  # corrupt file = silently lost pending question
    return None


def clear_pending_dm():
    if PENDING_DM_FLAG.exists():
        PENDING_DM_FLAG.unlink()


def ask_manual_top_users(user_id, gender_label, top_n):
    """
    DM the manager to enter top users manually.
    Returns a list of strings, or [] if skipped.
    """
    send_dm(
        user_id,
        f"⚠️ I couldn't scrape the *{gender_label} leaderboard* automatically.\n"
        f"Please enter the top {top_n} names manually, one per message.\n"
        f"Type `skip` to leave the leaderboard empty for today."
    )

    results = []
    for i in range(1, top_n + 1):
        channel_id, ts = send_dm(user_id, f"#{i} place {gender_label} name? (or `skip` to stop)")
        reply = poll_for_reply(channel_id, ts, timeout_seconds=300)
        if reply is None or reply.lower() == "skip":
            break
        results.append(reply.strip())

    return results