"""Tests for status/yearly_setup_reminder.py — scheduling helpers and flag logic."""
import datetime
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestNextWeekdayMorning:

    def test_returns_weekday(self):
        from status.yearly_setup_reminder import next_weekday_morning
        result = next_weekday_morning()
        assert result.weekday() < 5

    def test_returns_future_datetime(self):
        from status.yearly_setup_reminder import next_weekday_morning
        result = next_weekday_morning()
        assert result > datetime.datetime.now()

    def test_hour_is_nine_by_default(self):
        from status.yearly_setup_reminder import next_weekday_morning
        result = next_weekday_morning()
        assert result.hour == 9

    def test_custom_hour(self):
        from status.yearly_setup_reminder import next_weekday_morning
        result = next_weekday_morning(hour=10)
        assert result.hour == 10


class TestNeedsConfigReminder:

    def test_returns_true_when_webhook_missing(self):
        from status.yearly_setup_reminder import needs_config_reminder
        assert needs_config_reminder({}) is True

    def test_returns_false_when_config_complete(self):
        from status.yearly_setup_reminder import needs_config_reminder
        config = {"SLACK_WEBHOOK_URL": "https://hooks.slack.com/X", "SLACK_MANAGER_ID": "U123"}
        assert needs_config_reminder(config) is False

    def test_returns_true_when_never_reminded(self):
        from status.yearly_setup_reminder import needs_config_reminder
        config = {"SLACK_WEBHOOK_URL": ""}
        assert needs_config_reminder(config, last_reminded_at=None) is True

    def test_returns_false_within_24h(self):
        from status.yearly_setup_reminder import needs_config_reminder
        config = {"SLACK_WEBHOOK_URL": ""}
        recent = datetime.datetime.now() - datetime.timedelta(hours=1)
        assert needs_config_reminder(config, last_reminded_at=recent) is False

    def test_returns_true_after_24h(self):
        from status.yearly_setup_reminder import needs_config_reminder
        config = {"SLACK_WEBHOOK_URL": ""}
        old = datetime.datetime.now() - datetime.timedelta(hours=25)
        assert needs_config_reminder(config, last_reminded_at=old) is True


class TestYearlyReminder:

    def _base_flag(self, **overrides):
        flag = {"STOPPED": False, "LIVE_FOR_YEAR": False, "TOURNAMENT_ENDED": True}
        flag.update(overrides)
        return flag

    def test_does_nothing_when_stopped(self):
        from status.yearly_setup_reminder import yearly_reminder
        flag = self._base_flag(STOPPED=True)
        with patch("status.yearly_setup_reminder.load_flag", return_value=flag), \
             patch("status.yearly_setup_reminder.post_message") as mock_post:
            yearly_reminder({}, "U001")
        mock_post.assert_not_called()

    def test_does_nothing_when_live_for_year(self):
        from status.yearly_setup_reminder import yearly_reminder
        flag = self._base_flag(LIVE_FOR_YEAR=True)
        with patch("status.yearly_setup_reminder.load_flag", return_value=flag), \
             patch("status.yearly_setup_reminder.post_message") as mock_post:
            yearly_reminder({}, "U001")
        mock_post.assert_not_called()

    def test_sends_message_when_webhook_set(self, capsys):
        from status.yearly_setup_reminder import yearly_reminder
        flag = self._base_flag()
        config = {"SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/X"}
        with patch("status.yearly_setup_reminder.load_flag", return_value=flag), \
             patch("status.yearly_setup_reminder.save_flag"), \
             patch("status.yearly_setup_reminder.post_message") as mock_post:
            yearly_reminder(config, "U001")
        mock_post.assert_called_once()

    def test_mock_mode_prints_when_no_webhook(self, capsys):
        from status.yearly_setup_reminder import yearly_reminder
        flag = self._base_flag()
        with patch("status.yearly_setup_reminder.load_flag", return_value=flag), \
             patch("status.yearly_setup_reminder.save_flag"), \
             patch("status.yearly_setup_reminder.post_message") as mock_post:
            yearly_reminder({}, "U001")
        mock_post.assert_not_called()
        captured = capsys.readouterr()
        assert "REMINDER" in captured.out or "MOCK" in captured.out

    def test_skips_when_next_reminder_in_future(self, capsys):
        from status.yearly_setup_reminder import yearly_reminder
        future = (datetime.datetime.now() + datetime.timedelta(hours=2)).isoformat()
        flag = self._base_flag(NEXT_REMINDER=future)
        with patch("status.yearly_setup_reminder.load_flag", return_value=flag), \
             patch("status.yearly_setup_reminder.post_message") as mock_post:
            yearly_reminder({}, "U001")
        mock_post.assert_not_called()


class TestHandleStop:

    def test_sets_stopped_flag(self):
        from status.yearly_setup_reminder import handle_stop
        saved = {}
        with patch("status.yearly_setup_reminder.load_flag", return_value={}), \
             patch("status.yearly_setup_reminder.save_flag", side_effect=lambda f: saved.update(f)), \
             patch("status.yearly_setup_reminder.post_message"):
            handle_stop({"SLACK_WEBHOOK_URL": "https://hooks.slack.com/X"})
        assert saved.get("STOPPED") is True
