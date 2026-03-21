# This file contains functions to build messages for Slack, including daily summaries.

def build_daily_summary(men_games, women_games, top_men, top_women, men_url=None, women_url=None, top_n=5):
    # Function to build a daily summary message for Slack
    blocks = []

    # Add men's games to the summary
    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*Men's Games:*"}})
    for game in men_games:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"{game['team1']} vs {game['team2']} - {game['score']}"}})

    # Add women's games to the summary
    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*Women's Games:*"}})
    for game in women_games:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"{game['team1']} vs {game['team2']} - {game['score']}"}})

    # Add top users to the summary
    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*Top Users:*"}})
    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*Men's Leaderboard:*"}})
    for user in top_men[:top_n]:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"{user['name']} - {user['score']} points"}})

    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*Women's Leaderboard:*"}})
    for user in top_women[:top_n]:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"{user['name']} - {user['score']} points"}})

    return blocks