from bot_setup import slack_setup
from unittest.mock import patch
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


def test_prompt_manager_for_top():
    with patch('builtins.input', side_effect=['Player1 (10)', 'Player2 (20)', 'Player3 (30)']):
        top3 = slack_setup.prompt_manager_for_top("Main CBS Pool", "men", 3)
    assert len(top3) == 3
