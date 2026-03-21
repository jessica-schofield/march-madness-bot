def build_daily_summary(men_games, women_games, top_men, top_women, men_url=None, women_url=None, top_n=5):
    # Function to build a daily summary message for Slack
    blocks = []
    
    if men_games:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*Men's Games:*"}})
        for game in men_games:
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"{game['team1']} vs {game['team2']} - {game['status']}"}})
    
    if women_games:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*Women's Games:*"}})
        for game in women_games:
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"{game['team1']} vs {game['team2']} - {game['status']}"}})
    
    blocks.append({"type": "divider"})
    
    if top_men:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*Top Men's Bracket Players:*"}})
        for player in top_men[:top_n]:
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"{player['name']} - {player['score']} points"}})
    
    if top_women:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*Top Women's Bracket Players:*"}})
        for player in top_women[:top_n]:
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"{player['name']} - {player['score']} points"}})
    
    return blocks

def build_yearly_intro_message(config):
    # Function to build the introductory message for the yearly setup
    return f"🎉🏆 Welcome to the March Madness Bot! We're excited to have you on board for this year's tournament. Let's get started!"