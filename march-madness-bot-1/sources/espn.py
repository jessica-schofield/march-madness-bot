# filepath: /Users/jess/march-madness-bot/sources/espn.py

import requests

ESPN_API_URL = "https://site.api.espn.com/apis/site/v2/sports"

def get_final_games(gender):
    """Fetch final game results from ESPN for the specified gender."""
    if gender not in ["men", "women"]:
        raise ValueError("Gender must be 'men' or 'women'.")

    # Example endpoint, adjust as necessary for actual API usage
    endpoint = f"{ESPN_API_URL}/{gender}/scores"
    response = requests.get(endpoint)

    if response.status_code != 200:
        raise Exception(f"Failed to fetch data from ESPN: {response.status_code}")

    data = response.json()
    final_games = []

    for game in data.get("events", []):
        if game.get("status") == "final":
            final_games.append({
                "id": game.get("id"),
                "home_team": game.get("competitions")[0]["competitors"][0]["team"]["name"],
                "away_team": game.get("competitions")[0]["competitors"][1]["team"]["name"],
                "score": game.get("competitions")[0]["status"]["displayClock"],
            })

    return final_games