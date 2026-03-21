# filepath: /Users/jess/march-madness-bot/bot_setup/setup_cli.py
def get_input_safe(prompt, default=None, config=None):
    response = input(f"{prompt} (default: {default}): ") or default
    if config is not None and response is not None:
        config[prompt] = response
    return response

def ask_if_missing(config, key, prompt, default=None, cast=str):
    if key not in config or not config[key]:
        response = get_input_safe(prompt, default, config)
        if response is not None:
            config[key] = cast(response)

def ask_slack_credentials_cli(config):
    config["SLACK_WEBHOOK_URL"] = get_input_safe("Enter your Slack webhook URL", config.get("SLACK_WEBHOOK_URL"))
    config["SLACK_MANAGER_ID"] = get_input_safe("Enter your Slack manager user ID", config.get("SLACK_MANAGER_ID"))
    return config

TOURNAMENT_DATES_HELP = "Please provide the tournament end dates in YYYY-MM-DD format."

def run_cli_setup(config):
    print("\n--- March Madness Bot CLI Setup ---\n")
    
    ask_if_missing(config, "TOP_N", "How many top users to display?", default="5", cast=int)
    ask_if_missing(config, "MINUTES_BETWEEN_MESSAGES", "Minutes between messages?", default="60", cast=int)
    ask_if_missing(config, "POST_WEEKENDS", "Post on weekends? (y/n)", default="n", cast=lambda x: x.lower() == "y")
    ask_if_missing(config, "SEND_GAME_UPDATES", "Send game-by-game updates? (y/n)", default="y", cast=lambda x: x.lower() == "y")
    ask_if_missing(config, "SEND_DAILY_SUMMARY", "Send daily summary? (y/n)", default="y", cast=lambda x: x.lower() == "y")
    
    ask_if_missing(config, "TOURNAMENT_END_MEN", "Men's championship date (YYYY-MM-DD)?", default="2026-04-07")
    ask_if_missing(config, "TOURNAMENT_END_WOMEN", "Women's championship date (YYYY-MM-DD)?", default="2026-04-06")
    
    return config