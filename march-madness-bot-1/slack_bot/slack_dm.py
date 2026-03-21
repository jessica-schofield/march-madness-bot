# slack_bot/slack_dm.py

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import time

def send_dm(user_id, message):
    client = WebClient(token='YOUR_SLACK_BOT_TOKEN')
    try:
        response = client.chat_postMessage(channel=user_id, text=message)
        return response['channel'], response['ts']
    except SlackApiError as e:
        print(f"Error sending message: {e.response['error']}")
        return None, None

def poll_for_reply(channel_id, question_ts, timeout_seconds=1800):
    client = WebClient(token='YOUR_SLACK_BOT_TOKEN')
    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        response = client.conversations_replies(channel=channel_id, ts=question_ts)
        messages = response['messages']
        if messages and len(messages) > 1:  # Check for replies
            return messages[1]['text']  # Return the reply
        time.sleep(5)  # Wait before checking again
    return None

def save_pending_dm(user_id, question, reply, optional=False):
    # This function can be implemented to save pending DMs for follow-up
    pass

def clear_pending_dm():
    # This function can be implemented to clear any saved pending DMs
    pass

def ask_manual_top_users(user_id, gender_label, top_n):
    # This function can be implemented to ask the user for manual top users
    pass