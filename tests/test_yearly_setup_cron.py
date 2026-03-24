"""Tests for status/yearly_setup_cron.py — cron entrypoint logic."""
import datetime
import pytest
from unittest.mock import patch, MagicMock


class TestLoadFlag:

    def test_returns_default_when_file_missing(self, tmp_path):
        from status import yearly_setup_cron as cron
        with patch.object(cron, "YEARLY_FLAG_FILE", tmp_path / "missing.json"):
            result = cron.load_flag()
        assert result == {"stop": False, "last_reminder": None}

    def test_loads_existing_flag(self, tmp_path):
        import json
        from status import yearly_setup_cron as cron
        flag_path = tmp_path / "flag.json"
        flag_path.write_text(json.dumps({"stop": True, "last_reminder": "2026-03-10"}))
        with patch.object(cron, "YEARLY_FLAG_FILE", flag_path):
            result = cron.load_flag()
        assert result["stop"] is True


class TestMain:

    def _base_config(self):
        return {
            "SLACK_MANAGER_ID": "U001",
            "SLACK_BOT_TOKEN": "xoxb-fake",
        }

    def test_exits_early_when_no_manager_id(self, capsys):
        from status import yearly_setup_cron as cron
        with patch.object(cron, "load_config", return_value={}), \
             patch.object(cron, "load_flag", return_value={}):
            cron.main()
        assert "SLACK_MANAGER_ID" in capsys.readouterr().out

    def test_calls_yearly_reminder_when_due(self):
        from status import yearly_setup_cron as cron
        flag = {"stop": False, "last_reminder": "2000-01-01"}  # past date → due
        with patch.object(cron, "load_config", return_value=self._base_config()), \
             patch.object(cron, "load_flag", return_value=flag), \
             patch("status.yearly_setup_cron.WebClient", return_value=MagicMock()), \
             patch("status.yearly_setup_cron.yearly_reminder") as mock_reminder:
            cron.main()
        mock_reminder.assert_called_once()

    def test_skips_reminder_when_stopped(self, capsys):
        from status import yearly_setup_cron as cron
        flag = {"stop": True, "last_reminder": "2000-01-01"}
        with patch.object(cron, "load_config", return_value=self._base_config()), \
             patch.object(cron, "load_flag", return_value=flag), \
             patch("status.yearly_setup_cron.WebClient", return_value=MagicMock()), \
             patch("status.yearly_setup_cron.yearly_reminder") as mock_reminder:
            cron.main()
        mock_reminder.assert_not_called()

    def test_no_reminder_due_prints_status(self, capsys):
        from status import yearly_setup_cron as cron
        # Set last_reminder to far future so nothing is due
        far_future = (datetime.date.today() + datetime.timedelta(days=365)).isoformat()
        flag = {"stop": False, "last_reminder": far_future}
        with patch.object(cron, "load_config", return_value=self._base_config()), \
             patch.object(cron, "load_flag", return_value=flag), \
             patch("status.yearly_setup_cron.WebClient", return_value=MagicMock()), \
             patch("status.yearly_setup_cron.yearly_reminder") as mock_reminder:
            cron.main()
        mock_reminder.assert_not_called()
        assert "No reminder due" in capsys.readouterr().out
