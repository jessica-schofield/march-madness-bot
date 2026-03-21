from slack_sdk import WebClient
import pytest

client = WebClient(token="your-slack-bot-token")


def test_slack_setup():
    response = client.api_test()
    assert response["ok"] is True
