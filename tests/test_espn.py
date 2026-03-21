import datetime
import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# check_championship_final — must not fire before April
# ---------------------------------------------------------------------------

class TestCheckChampionshipFinal:

    def _espn_event(self, name="National Championship", status="STATUS_FINAL",
                    date="2026-03-21T22:00Z"):
        return {
            "name": name,
            "shortName": name,
            "date": date,
            "competitions": [{
                "status": {"type": {"name": status}},
                "notes": [{"headline": "National Championship"}],
            }],
        }

    def _mock_response(self, events):
        mock = MagicMock()
        mock.raise_for_status.return_value = None
        mock.json.return_value = {"events": events}
        return mock

    def test_returns_none_in_march_regardless_of_espn_response(self):
        """Conference championships in March must never trigger wrap-up."""
        from sources.espn import check_championship_final
        event = self._espn_event(date="2026-03-21T22:00Z")
        with patch("sources.espn.requests.get", return_value=self._mock_response([event])), \
             patch("sources.espn.datetime") as mock_dt:
            mock_dt.date.today.return_value = datetime.date(2026, 3, 21)
            mock_dt.date.fromisoformat = datetime.date.fromisoformat
            result = check_championship_final("men")
        assert result is None, "Must not confirm championship in March"

    def test_returns_none_in_february(self):
        from sources.espn import check_championship_final
        with patch("sources.espn.datetime") as mock_dt:
            mock_dt.date.today.return_value = datetime.date(2026, 2, 15)
            mock_dt.date.fromisoformat = datetime.date.fromisoformat
            result = check_championship_final("men")
        assert result is None

    def test_returns_date_in_april_when_final(self):
        """Real championship in April with STATUS_FINAL must return the date."""
        from sources.espn import check_championship_final
        event = self._espn_event(date="2026-04-06T23:09Z")
        with patch("sources.espn.requests.get", return_value=self._mock_response([event])), \
             patch("sources.espn.datetime") as mock_dt:
            mock_dt.date.today.return_value = datetime.date(2026, 4, 7)
            mock_dt.date.fromisoformat = datetime.date.fromisoformat
            result = check_championship_final("men")
        assert result == datetime.date(2026, 4, 6)

    def test_skips_non_championship_events(self):
        """Regular season games must never be treated as championship."""
        from sources.espn import check_championship_final
        event = self._espn_event(name="Duke vs North Carolina", date="2026-04-06T23:09Z")
        # Override notes to have no championship
        event["competitions"][0]["notes"] = []
        with patch("sources.espn.requests.get", return_value=self._mock_response([event])), \
             patch("sources.espn.datetime") as mock_dt:
            mock_dt.date.today.return_value = datetime.date(2026, 4, 7)
            mock_dt.date.fromisoformat = datetime.date.fromisoformat
            result = check_championship_final("men")
        assert result is None

    def test_skips_game_not_yet_final(self):
        """A championship game still in progress must not trigger wrap-up."""
        from sources.espn import check_championship_final
        event = self._espn_event(status="STATUS_IN_PROGRESS", date="2026-04-06T23:09Z")
        with patch("sources.espn.requests.get", return_value=self._mock_response([event])), \
             patch("sources.espn.datetime") as mock_dt:
            mock_dt.date.today.return_value = datetime.date(2026, 4, 6)
            mock_dt.date.fromisoformat = datetime.date.fromisoformat
            result = check_championship_final("men")
        assert result is None

    def test_returns_none_on_network_error(self):
        """Network failure must return None, never raise."""
        from sources.espn import check_championship_final
        with patch("sources.espn.requests.get", side_effect=Exception("timeout")), \
             patch("sources.espn.datetime") as mock_dt:
            mock_dt.date.today.return_value = datetime.date(2026, 4, 7)
            mock_dt.date.fromisoformat = datetime.date.fromisoformat
            result = check_championship_final("men")
        assert result is None

    def test_april_date_in_event_but_today_is_march_still_blocked(self):
        """Even if ESPN returns an April date, must be blocked if today is March."""
        from sources.espn import check_championship_final
        event = self._espn_event(date="2026-04-06T23:09Z")
        with patch("sources.espn.requests.get", return_value=self._mock_response([event])), \
             patch("sources.espn.datetime") as mock_dt:
            mock_dt.date.today.return_value = datetime.date(2026, 3, 31)
            mock_dt.date.fromisoformat = datetime.date.fromisoformat
            result = check_championship_final("men")
        assert result is None, "today is March — must not confirm even if ESPN date is April"

    def test_works_for_womens_gender(self):
        """Women's path must use the correct ESPN URL and return correctly."""
        from sources.espn import check_championship_final
        event = self._espn_event(date="2026-04-05T23:09Z")
        with patch("sources.espn.requests.get", return_value=self._mock_response([event])) as mock_get, \
             patch("sources.espn.datetime") as mock_dt:
            mock_dt.date.today.return_value = datetime.date(2026, 4, 6)
            mock_dt.date.fromisoformat = datetime.date.fromisoformat
            result = check_championship_final("women")
        assert result == datetime.date(2026, 4, 5)
        assert "womens" in mock_get.call_args[0][0]

    def test_april_first_is_allowed(self):
        """April 1 is the earliest valid date — must not be blocked."""
        from sources.espn import check_championship_final
        event = self._espn_event(date="2026-04-01T23:09Z")
        with patch("sources.espn.requests.get", return_value=self._mock_response([event])), \
             patch("sources.espn.datetime") as mock_dt:
            mock_dt.date.today.return_value = datetime.date(2026, 4, 1)
            mock_dt.date.fromisoformat = datetime.date.fromisoformat
            result = check_championship_final("men")
        assert result == datetime.date(2026, 4, 1)

    def test_ignores_non_championship_events_before_real_one(self):
        """Must skip non-championship events and still find the real one."""
        from sources.espn import check_championship_final
        noise = self._espn_event(name="Duke vs UNC", date="2026-04-06T23:09Z")
        noise["competitions"][0]["notes"] = []
        real = self._espn_event(name="National Championship", date="2026-04-06T23:09Z")
        with patch("sources.espn.requests.get", return_value=self._mock_response([noise, real])), \
             patch("sources.espn.datetime") as mock_dt:
            mock_dt.date.today.return_value = datetime.date(2026, 4, 7)
            mock_dt.date.fromisoformat = datetime.date.fromisoformat
            result = check_championship_final("men")
        assert result == datetime.date(2026, 4, 6)

    def test_malformed_date_falls_back_to_today(self):
        """Unparseable ESPN date must not raise — falls back to today."""
        from sources.espn import check_championship_final
        event = self._espn_event(date="not-a-date")
        with patch("sources.espn.requests.get", return_value=self._mock_response([event])), \
             patch("sources.espn.datetime") as mock_dt:
            mock_dt.date.today.return_value = datetime.date(2026, 4, 7)
            mock_dt.date.fromisoformat = datetime.date.fromisoformat
            result = check_championship_final("men")
        # Malformed date → falls back to today (April) → still valid
        assert result == datetime.date(2026, 4, 7)

    def test_empty_events_list_returns_none(self):
        """ESPN returning zero events must return None cleanly."""
        from sources.espn import check_championship_final
        with patch("sources.espn.requests.get", return_value=self._mock_response([])), \
             patch("sources.espn.datetime") as mock_dt:
            mock_dt.date.today.return_value = datetime.date(2026, 4, 7)
            mock_dt.date.fromisoformat = datetime.date.fromisoformat
            result = check_championship_final("men")
        assert result is None

    def test_march_31_is_still_blocked(self):
        """March 31 is the day before April — must still be blocked."""
        from sources.espn import check_championship_final
        event = self._espn_event(date="2026-03-31T23:09Z")
        with patch("sources.espn.requests.get", return_value=self._mock_response([event])), \
             patch("sources.espn.datetime") as mock_dt:
            mock_dt.date.today.return_value = datetime.date(2026, 3, 31)
            mock_dt.date.fromisoformat = datetime.date.fromisoformat
            result = check_championship_final("men")
        assert result is None, "March 31 must be blocked — tournament ends in April"

    def test_detects_championship_via_short_name_only(self):
        """shortName containing 'championship' must be sufficient to match."""
        from sources.espn import check_championship_final
        event = self._espn_event(date="2026-04-06T23:09Z")
        event["name"] = "Duke vs UNC"
        event["shortName"] = "National Championship"
        event["competitions"][0]["notes"] = []
        with patch("sources.espn.requests.get", return_value=self._mock_response([event])), \
             patch("sources.espn.datetime") as mock_dt:
            mock_dt.date.today.return_value = datetime.date(2026, 4, 7)
            mock_dt.date.fromisoformat = datetime.date.fromisoformat
            result = check_championship_final("men")
        assert result == datetime.date(2026, 4, 6)

    def test_detects_championship_via_note_headline_only(self):
        """A note headline of 'national championship' must be sufficient to match."""
        from sources.espn import check_championship_final
        event = self._espn_event(date="2026-04-06T23:09Z")
        event["name"] = "Duke vs UNC"
        event["shortName"] = "Duke vs UNC"
        event["competitions"][0]["notes"] = [{"headline": "National Championship"}]
        with patch("sources.espn.requests.get", return_value=self._mock_response([event])), \
             patch("sources.espn.datetime") as mock_dt:
            mock_dt.date.today.return_value = datetime.date(2026, 4, 7)
            mock_dt.date.fromisoformat = datetime.date.fromisoformat
            result = check_championship_final("men")
        assert result == datetime.date(2026, 4, 6)

    def test_status_final_lowercase_variant_not_matched(self):
        """Status must be uppercased before comparison — lowercase 'final' must not match."""
        from sources.espn import check_championship_final
        event = self._espn_event(date="2026-04-06T23:09Z")
        event["competitions"][0]["status"]["type"]["name"] = "final"  # lowercase
        with patch("sources.espn.requests.get", return_value=self._mock_response([event])), \
             patch("sources.espn.datetime") as mock_dt:
            mock_dt.date.today.return_value = datetime.date(2026, 4, 7)
            mock_dt.date.fromisoformat = datetime.date.fromisoformat
            result = check_championship_final("men")
        assert result == datetime.date(2026, 4, 6)

    def test_scheduled_status_not_matched(self):
        """A scheduled but not yet played championship must return None."""
        from sources.espn import check_championship_final
        event = self._espn_event(status="STATUS_SCHEDULED", date="2026-04-06T23:09Z")
        with patch("sources.espn.requests.get", return_value=self._mock_response([event])), \
             patch("sources.espn.datetime") as mock_dt:
            mock_dt.date.today.return_value = datetime.date(2026, 4, 6)
            mock_dt.date.fromisoformat = datetime.date.fromisoformat
            result = check_championship_final("men")
        assert result is None

    def test_men_url_does_not_contain_womens(self):
        """Men's URL must never include 'womens'."""
        from sources.espn import check_championship_final
        with patch("sources.espn.requests.get", return_value=self._mock_response([])) as mock_get, \
             patch("sources.espn.datetime") as mock_dt:
            mock_dt.date.today.return_value = datetime.date(2026, 4, 7)
            mock_dt.date.fromisoformat = datetime.date.fromisoformat
            check_championship_final("men")
        url = mock_get.call_args[0][0]
        assert "womens" not in url
        assert "mens" in url

    def test_http_error_returns_none(self):
        """HTTPError (e.g. 500) must return None, never raise."""
        from sources.espn import check_championship_final
        import requests as req
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = req.HTTPError("500")
        with patch("sources.espn.requests.get", return_value=mock_resp), \
             patch("sources.espn.datetime") as mock_dt:
            mock_dt.date.today.return_value = datetime.date(2026, 4, 7)
            mock_dt.date.fromisoformat = datetime.date.fromisoformat
            result = check_championship_final("men")
        assert result is None

    def test_multiple_championship_events_returns_first_final(self):
        """If ESPN returns two championship events both final, return the first one."""
        from sources.espn import check_championship_final
        first = self._espn_event(date="2026-04-05T23:09Z")
        second = self._espn_event(date="2026-04-06T23:09Z")
        with patch("sources.espn.requests.get", return_value=self._mock_response([first, second])), \
             patch("sources.espn.datetime") as mock_dt:
            mock_dt.date.today.return_value = datetime.date(2026, 4, 7)
            mock_dt.date.fromisoformat = datetime.date.fromisoformat
            result = check_championship_final("men")
        assert result == datetime.date(2026, 4, 5)

    def test_january_is_blocked(self):
        """January must be blocked — no tournament games occur then."""
        from sources.espn import check_championship_final
        with patch("sources.espn.datetime") as mock_dt:
            mock_dt.date.today.return_value = datetime.date(2026, 1, 10)
            mock_dt.date.fromisoformat = datetime.date.fromisoformat
            result = check_championship_final("women")
        assert result is None

    def test_event_date_in_march_skipped_even_if_today_is_april(self):
        """An event whose date is in March must be skipped even if today is April."""
        from sources.espn import check_championship_final
        event = self._espn_event(date="2026-03-30T23:09Z")
        with patch("sources.espn.requests.get", return_value=self._mock_response([event])), \
             patch("sources.espn.datetime") as mock_dt:
            mock_dt.date.today.return_value = datetime.date(2026, 4, 1)
            mock_dt.date.fromisoformat = datetime.date.fromisoformat
            result = check_championship_final("men")
        assert result is None, "Event date is March — must be skipped regardless of today"

    def test_missing_date_field_falls_back_to_today(self):
        """Event with no date key must not raise — falls back to today."""
        from sources.espn import check_championship_final
        event = self._espn_event(date="2026-04-06T23:09Z")
        del event["date"]
        with patch("sources.espn.requests.get", return_value=self._mock_response([event])), \
             patch("sources.espn.datetime") as mock_dt:
            mock_dt.date.today.return_value = datetime.date(2026, 4, 7)
            mock_dt.date.fromisoformat = datetime.date.fromisoformat
            result = check_championship_final("men")
        assert result == datetime.date(2026, 4, 7)


# ---------------------------------------------------------------------------
# get_input_safe — must not raise in cron (no stdin)
# ---------------------------------------------------------------------------

class TestGetInputSafeEOF:

    def test_returns_default_on_eof(self):
        """Cron has no stdin — EOFError must return default, never raise."""
        from bot_setup.setup_cli import get_input_safe
        with patch("builtins.input", side_effect=EOFError):
            result = get_input_safe("Method?", default="cli")
        assert result == "cli"

    def test_returns_empty_string_on_eof_with_no_default(self):
        from bot_setup.setup_cli import get_input_safe
        with patch("builtins.input", side_effect=EOFError):
            result = get_input_safe("Method?")
        assert result == ""

    def test_does_not_raise_on_eof(self):
        from bot_setup.setup_cli import get_input_safe
        with patch("builtins.input", side_effect=EOFError):
            try:
                get_input_safe("Method?", default="slack")
            except EOFError:
                pytest.fail("get_input_safe raised EOFError — will crash in cron")

    def test_exit_typed_calls_sys_exit(self):
        """'exit' is a deliberate escape hatch — must call sys.exit(0)."""
        from bot_setup.setup_cli import get_input_safe
        with patch("builtins.input", return_value="exit"):
            with pytest.raises(SystemExit) as exc_info:
                get_input_safe("Method?", default="cli")
        assert exc_info.value.code == 0

    def test_eof_mid_setup_does_not_leave_config_in_broken_state(self):
        """If EOFError fires during ask_if_missing, config must keep its default — not None."""
        from bot_setup.setup_cli import ask_if_missing
        config = {}
        with patch("builtins.input", side_effect=EOFError):
            ask_if_missing(config, "TOP_N", "How many?", default="5", cast=int)
        assert config.get("TOP_N") == 5, \
            "EOFError during ask_if_missing must still write the default into config"


# ---------------------------------------------------------------------------
# get_final_games — ESPN game fetching
# ---------------------------------------------------------------------------

class TestGetFinalGames:

    def _make_event(self, event_id="1", status="STATUS_FINAL", home="Duke",
                    away="UNC", home_score="72", away_score="68",
                    home_seed=1, away_seed=4):
        return {
            "id": event_id,
            "name": f"{away} vs {home}",
            "date": "2026-03-28T00:00Z",
            "competitions": [{
                "status": {"type": {"name": status}},
                "competitors": [
                    {
                        "homeAway": "home",
                        "score": home_score,
                        "team": {"displayName": home},
                        "curatedRank": {"current": home_seed},
                    },
                    {
                        "homeAway": "away",
                        "score": away_score,
                        "team": {"displayName": away},
                        "curatedRank": {"current": away_seed},
                    },
                ],
            }],
        }

    def _mock_response(self, events):
        mock = MagicMock()
        mock.raise_for_status.return_value = None
        mock.json.return_value = {"events": events}
        return mock

    def test_returns_final_games_only(self):
        from sources.espn import get_final_games
        final = self._make_event(status="STATUS_FINAL")
        live = self._make_event(event_id="2", status="STATUS_IN_PROGRESS")
        with patch("sources.espn.requests.get", return_value=self._mock_response([final, live])):
            result = get_final_games("men")
        assert len(result) == 1
        assert result[0]["id"] == "1"

    def test_returns_empty_list_on_network_error(self):
        from sources.espn import get_final_games
        with patch("sources.espn.requests.get", side_effect=Exception("timeout")):
            result = get_final_games("men")
        assert result == []

    def test_returns_empty_list_when_no_events(self):
        from sources.espn import get_final_games
        with patch("sources.espn.requests.get", return_value=self._mock_response([])):
            result = get_final_games("men")
        assert result == []

    def test_game_fields_populated_correctly(self):
        from sources.espn import get_final_games
        event = self._make_event(home="Duke", away="UNC", home_score="72",
                                  away_score="68", home_seed=1, away_seed=4)
        with patch("sources.espn.requests.get", return_value=self._mock_response([event])):
            result = get_final_games("men")
        assert len(result) == 1
        g = result[0]
        assert g["home"] == "Duke"
        assert g["away"] == "UNC"
        assert g["home_score"] == "72"
        assert g["away_score"] == "68"
        assert g["home_seed"] == 1
        assert g["away_seed"] == 4
        assert g["gender"] == "men"

    def test_women_url_used_for_women(self):
        from sources.espn import get_final_games
        with patch("sources.espn.requests.get", return_value=self._mock_response([])) as mock_get:
            get_final_games("women")
        assert "womens" in mock_get.call_args[0][0]

    def test_men_url_used_for_men(self):
        from sources.espn import get_final_games
        with patch("sources.espn.requests.get", return_value=self._mock_response([])) as mock_get:
            get_final_games("men")
        assert "mens" in mock_get.call_args[0][0]

    def test_skips_malformed_event_continues(self):
        """A malformed event must be skipped — other games must still be returned."""
        from sources.espn import get_final_games
        bad = {"id": "bad", "competitions": []}  # missing required fields
        good = self._make_event(event_id="2")
        with patch("sources.espn.requests.get", return_value=self._mock_response([bad, good])):
            result = get_final_games("men")
        assert len(result) == 1
        assert result[0]["id"] == "2"

    def test_multiple_final_games_all_returned(self):
        """All final games in a response must be returned, not just the first."""
        from sources.espn import get_final_games
        events = [
            self._make_event(event_id=str(i), home=f"Team{i}", away=f"Away{i}")
            for i in range(5)
        ]
        with patch("sources.espn.requests.get", return_value=self._mock_response(events)):
            result = get_final_games("men")
        assert len(result) == 5

    def test_date_field_preserved_from_event(self):
        """The date field must be passed through from the ESPN event unchanged."""
        from sources.espn import get_final_games
        event = self._make_event()
        with patch("sources.espn.requests.get", return_value=self._mock_response([event])):
            result = get_final_games("men")
        assert result[0]["date"] == "2026-03-28T00:00Z"

    def test_status_final_variant_also_accepted(self):
        """Status 'FINAL' (without STATUS_ prefix) must also be accepted."""
        from sources.espn import get_final_games
        event = self._make_event(status="FINAL")
        with patch("sources.espn.requests.get", return_value=self._mock_response([event])):
            result = get_final_games("men")
        assert len(result) == 1

    def test_unseeded_team_returns_zero_seed(self):
        """A team with no curatedRank must get seed 0, not crash."""
        from sources.espn import get_final_games
        event = self._make_event()
        del event["competitions"][0]["competitors"][0]["curatedRank"]
        with patch("sources.espn.requests.get", return_value=self._mock_response([event])):
            result = get_final_games("men")
        assert result[0]["home_seed"] == 0


# ---------------------------------------------------------------------------
# _extract_seed
# ---------------------------------------------------------------------------

class TestExtractSeed:

    def test_dict_rank_returns_current(self):
        from sources.espn import _extract_seed
        assert _extract_seed({"curatedRank": {"current": 3}}) == 3

    def test_int_rank_returns_int(self):
        from sources.espn import _extract_seed
        assert _extract_seed({"curatedRank": 5}) == 5

    def test_missing_rank_returns_zero(self):
        from sources.espn import _extract_seed
        assert _extract_seed({}) == 0

    def test_non_numeric_rank_returns_zero(self):
        from sources.espn import _extract_seed
        assert _extract_seed({"curatedRank": "NR"}) == 0

    def test_zero_rank_returns_zero(self):
        from sources.espn import _extract_seed
        assert _extract_seed({"curatedRank": 0}) == 0

    def test_dict_rank_missing_current_key_returns_zero(self):
        from sources.espn import _extract_seed
        assert _extract_seed({"curatedRank": {}}) == 0

    def test_float_rank_truncates_to_int(self):
        from sources.espn import _extract_seed
        assert _extract_seed({"curatedRank": 3.9}) == 3

    def test_string_numeric_rank_converts(self):
        from sources.espn import _extract_seed
        assert _extract_seed({"curatedRank": "8"}) == 8


# ---------------------------------------------------------------------------
# check_tournament_end — yearly wrap-up guard
# ---------------------------------------------------------------------------

class TestCheckTournamentEnd:

    def _make_flag(self, live=True, ended=False, men_date=None, women_date=None):
        flag = {"LIVE_FOR_YEAR": live, "TOURNAMENT_ENDED": ended}
        if men_date:
            flag["MEN_CHAMPIONSHIP_DATE"] = men_date
        if women_date:
            flag["WOMEN_CHAMPIONSHIP_DATE"] = women_date
        return flag

    def test_does_nothing_when_not_live(self):
        """Must exit early and never call ESPN when not live."""
        from status.yearly_setup_reminder import check_tournament_end
        flag = self._make_flag(live=False)
        with patch("status.yearly_setup_reminder.load_flag", return_value=flag), \
             patch("sources.espn.check_championship_final") as mock_espn:
            check_tournament_end({})
        mock_espn.assert_not_called()

    def test_does_nothing_when_already_ended(self):
        """Must not re-run wrap-up if TOURNAMENT_ENDED is already True."""
        from status.yearly_setup_reminder import check_tournament_end
        flag = self._make_flag(live=True, ended=True)
        with patch("status.yearly_setup_reminder.load_flag", return_value=flag), \
             patch("sources.espn.check_championship_final") as mock_espn:
            check_tournament_end({})
        mock_espn.assert_not_called()

    def test_waits_when_only_men_done(self):
        """Must not wrap up when only one championship is confirmed."""
        from status.yearly_setup_reminder import check_tournament_end
        flag = self._make_flag(live=True, men_date="2026-04-06")
        with patch("status.yearly_setup_reminder.load_flag", return_value=flag), \
             patch("status.yearly_setup_reminder.save_flag"), \
             patch("sources.espn.check_championship_final", return_value=None), \
             patch("status.yearly_setup_reminder._advance_tournament_dates") as mock_advance:
            check_tournament_end({})
        mock_advance.assert_not_called()

    def test_wraps_up_when_both_done(self):
        from status.yearly_setup_reminder import check_tournament_end
        flag = self._make_flag(
            live=True,
            men_date="2026-04-06",
            women_date="2026-04-05"
        )
        with patch("status.yearly_setup_reminder.load_flag", return_value=flag), \
             patch("status.yearly_setup_reminder.save_flag") as mock_save, \
             patch("sources.espn.check_championship_final", return_value=None), \
             patch("status.yearly_setup_reminder._advance_tournament_dates") as mock_advance, \
             patch("status.yearly_setup_reminder._update_yearly_crontab"), \
             patch("slack_bot.slack_utils.post_message"):
            check_tournament_end({"SLACK_WEBHOOK_URL": "https://hooks.slack.com/test"})

        mock_advance.assert_called_once()
        saved_flag = mock_save.call_args[0][0]
        assert saved_flag["LIVE_FOR_YEAR"] is False
        assert saved_flag["TOURNAMENT_ENDED"] is True

    def test_championship_confirmed_in_march_never_triggers_wrapup(self):
        from status.yearly_setup_reminder import check_tournament_end
        flag = self._make_flag(live=True)
        with patch("status.yearly_setup_reminder.load_flag", return_value=flag), \
             patch("status.yearly_setup_reminder.save_flag"), \
             patch("sources.espn.check_championship_final", return_value=None), \
             patch("status.yearly_setup_reminder._advance_tournament_dates") as mock_advance:
            check_tournament_end({})
        mock_advance.assert_not_called()


class TestAdvanceTournamentDates:

    def test_advances_both_dates_by_one_year(self):
        from status.yearly_setup_reminder import _advance_tournament_dates
        config = {
            "TOURNAMENT_END_MEN": "2026-04-06",
            "TOURNAMENT_END_WOMEN": "2026-04-05",
        }
        with patch("bot_setup.config.save_json"):
            result = _advance_tournament_dates(config)
        assert result["TOURNAMENT_END_MEN"] == "2027-04-06"
        assert result["TOURNAMENT_END_WOMEN"] == "2027-04-05"

    def test_skips_malformed_date_without_raising(self):
        from status.yearly_setup_reminder import _advance_tournament_dates
        config = {"TOURNAMENT_END_MEN": "not-a-date", "TOURNAMENT_END_WOMEN": "2026-04-05"}
        with patch("bot_setup.config.save_json"):
            result = _advance_tournament_dates(config)
        assert result["TOURNAMENT_END_MEN"] == "not-a-date"
        assert result["TOURNAMENT_END_WOMEN"] == "2027-04-05"

    def test_does_nothing_when_keys_missing(self):
        from status.yearly_setup_reminder import _advance_tournament_dates
        config = {}
        with patch("bot_setup.config.save_json") as mock_save:
            result = _advance_tournament_dates(config)
        mock_save.assert_not_called()
        assert result == {}

    def test_saves_config_when_changed(self):
        from status.yearly_setup_reminder import _advance_tournament_dates
        config = {"TOURNAMENT_END_MEN": "2026-04-06"}
        with patch("bot_setup.config.save_json") as mock_save:
            _advance_tournament_dates(config)
        mock_save.assert_called_once()

    def test_advances_only_women_when_men_missing(self):
        from status.yearly_setup_reminder import _advance_tournament_dates
        config = {"TOURNAMENT_END_WOMEN": "2026-04-05"}
        with patch("bot_setup.config.save_json"):
            result = _advance_tournament_dates(config)
        assert result["TOURNAMENT_END_WOMEN"] == "2027-04-05"
        assert "TOURNAMENT_END_MEN" not in result

    def test_return_value_is_the_mutated_config(self):
        """Return value must be the same dict that was passed in."""
        from status.yearly_setup_reminder import _advance_tournament_dates
        config = {"TOURNAMENT_END_MEN": "2026-04-06"}
        with patch("bot_setup.config.save_json"):
            result = _advance_tournament_dates(config)
        assert result is config


# ---------------------------------------------------------------------------
# needs_config_reminder
# ---------------------------------------------------------------------------

class TestNeedsConfigReminder:

    def test_returns_true_when_webhook_missing(self):
        from status.yearly_setup_reminder import needs_config_reminder
        assert needs_config_reminder({"SLACK_MANAGER_ID": "U123"}) is True

    def test_returns_true_when_manager_id_missing(self):
        from status.yearly_setup_reminder import needs_config_reminder
        assert needs_config_reminder({"SLACK_WEBHOOK_URL": "https://hooks.slack.com/test"}) is True

    def test_returns_false_when_both_set(self):
        from status.yearly_setup_reminder import needs_config_reminder
        config = {"SLACK_WEBHOOK_URL": "https://hooks.slack.com/test", "SLACK_MANAGER_ID": "U123"}
        assert needs_config_reminder(config) is False

    def test_returns_true_when_never_reminded(self):
        from status.yearly_setup_reminder import needs_config_reminder
        assert needs_config_reminder({}, last_reminded_at=None) is True

    def test_returns_false_when_reminded_less_than_24h_ago(self):
        from status.yearly_setup_reminder import needs_config_reminder
        recent = datetime.datetime.now() - datetime.timedelta(hours=12)
        assert needs_config_reminder({}, last_reminded_at=recent) is False

    def test_returns_true_when_reminded_more_than_24h_ago(self):
        from status.yearly_setup_reminder import needs_config_reminder
        old = datetime.datetime.now() - datetime.timedelta(hours=25)
        assert needs_config_reminder({}, last_reminded_at=old) is True

    def test_returns_true_when_config_is_empty(self):
        from status.yearly_setup_reminder import needs_config_reminder
        assert needs_config_reminder({}) is True

    def test_reminded_exactly_24h_ago_triggers_again(self):
        """Exactly 24 h ago is on the boundary — must trigger a new reminder."""
        from status.yearly_setup_reminder import needs_config_reminder
        exactly_24h = datetime.datetime.now() - datetime.timedelta(hours=24)
        assert needs_config_reminder({}, last_reminded_at=exactly_24h) is True

    def test_webhook_empty_string_treated_as_missing(self):
        """An empty string webhook must be treated the same as absent."""
        from status.yearly_setup_reminder import needs_config_reminder
        assert needs_config_reminder({"SLACK_WEBHOOK_URL": "", "SLACK_MANAGER_ID": "U123"}) is True


# ---------------------------------------------------------------------------
# Stale duplicate directories must not exist
# ---------------------------------------------------------------------------

class TestProjectStructure:

    def test_no_stale_duplicate_directories(self):
        from pathlib import Path
        root = Path(__file__).parent.parent
        stale = [
            root / "march-madness-bot-1",
            root / "march-madness-bot" / "src",
        ]
        for path in stale:
            assert not path.exists(), (
                f"{path.name} is a stale duplicate directory — delete it.\n"
                f"Run: rm -rf {path}"
            )

    def test_slack_dot_py_is_legacy(self):
        from pathlib import Path
        legacy = Path(__file__).parent.parent / "slack_bot" / "slack.py"
        assert not legacy.exists(), (
            "slack_bot/slack.py loads config.json at import time and will crash if config is missing. "
            "It is superseded by slack_utils.py — delete it."
        )