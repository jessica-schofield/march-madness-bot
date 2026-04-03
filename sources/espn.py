import requests
import datetime


def espn_url(gender, days_ago=1):
    """Build ESPN scoreboard URL for a date offset (default: yesterday)."""
    target_day = (datetime.datetime.now() - datetime.timedelta(days=days_ago)).strftime("%Y%m%d")
    if gender == "men":
        return f"https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard?groups=100&limit=50&dates={target_day}"
    return f"https://site.api.espn.com/apis/site/v2/sports/basketball/womens-college-basketball/scoreboard?groups=100&limit=50&dates={target_day}"


def get_final_games(gender, days_ago=1):
    """Fetch final games from ESPN for a date offset (default: yesterday)."""
    url = espn_url(gender, days_ago=days_ago)
    games = []
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        # print(f"[DEBUG] ESPN returned {len(data.get('events', []))} events for {gender}")
        for event in data.get("events", []):
            try:
                comp = event["competitions"][0]
                status = comp["status"]["type"]["name"].upper()
                # print(f"[DEBUG] Game: {event.get('name')} | Status: {status}")
                if status not in ("STATUS_FINAL", "FINAL"):
                    continue
                teams = {t["homeAway"]: t for t in comp["competitors"]}
                games.append({
                    "id": event["id"],
                    "gender": gender,
                    "home": teams["home"]["team"]["displayName"],
                    "home_score": teams["home"]["score"],
                    "home_seed": _extract_seed(teams["home"]),
                    "away": teams["away"]["team"]["displayName"],
                    "away_score": teams["away"]["score"],
                    "away_seed": _extract_seed(teams["away"]),
                    "date": event.get("date")
                })
            except Exception as e:
                print(f"[WARN] Skipping game: {e}")
                continue
    except Exception as e:
        print(f"[WARN] Failed to fetch ESPN {gender} games: {e}")
    return games


def check_championship_final(gender):
    """
    Check ESPN to see if this year's championship game has a final score.
    Looks at the current season's tournament for a game with 'championship'
    in the name that has STATUS_FINAL.

    Returns the final date as datetime.date if found, None otherwise.
    """
    if gender == "men":
        url = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard?groups=100&limit=50"
    else:
        url = "https://site.api.espn.com/apis/site/v2/sports/basketball/womens-college-basketball/scoreboard?groups=100&limit=50"

    # Must not confirm championship before April — guards against conference
    # championship games (also called "championship") triggering a false positive.
    today = datetime.date.today()
    if today.month < 4:
        return None

    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        for event in data.get("events", []):
            name = event.get("name", "").lower()
            short_name = event.get("shortName", "").lower()
            notes = event.get("competitions", [{}])[0].get("notes", [])
            note_texts = [n.get("headline", "").lower() for n in notes]

            is_championship = (
                "championship" in name
                or "championship" in short_name
                or any("championship" in n for n in note_texts)
                or any("national championship" in n for n in note_texts)
            )

            if not is_championship:
                continue

            comp = event["competitions"][0]
            status = comp["status"]["type"]["name"].upper()

            if status in ("STATUS_FINAL", "FINAL"):
                raw_date = event.get("date", "")
                try:
                    end_date = datetime.date.fromisoformat(raw_date[:10])
                except Exception:
                    end_date = datetime.date.today()

                # Double-check: must be in April or later to be the NCAA championship
                if end_date.month < 4:
                    print(f"[INFO] Skipping '{event.get('name')}' — final date {end_date} is before April (not NCAA championship)")
                    continue

                print(f"[INFO] {gender.capitalize()} championship is final — ended {end_date}")
                return end_date

    except Exception as e:
        print(f"[WARN] Failed to check {gender} championship status: {e}")

    return None


def _extract_seed(team):
    rank = team.get("curatedRank", 0)
    if isinstance(rank, dict):
        return int(rank.get("current", 0))
    try:
        return int(rank)
    except Exception:
        return 0
