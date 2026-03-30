import random
import datetime
from bot_setup.config import load_json, save_json, LAST_RANKINGS_FILE

_INTROS = [
    "☀️ Good morning! Here's the madness from yesterday:",
    "🎉 Daily chaos report incoming!",
    "😂 Buckle up: yesterday in March Madness...",
    "☕ Grab your coffee, here's what happened on the court yesterday:",
    "🏀 Another day, another bracket disaster report:",
]


def is_upset(home_score, away_score, home_seed, away_seed):
    """Returns True if the lower-seeded (worse) team won."""
    try:
        home_seed = int(home_seed)
        away_seed = int(away_seed)
    except (TypeError, ValueError):
        return False
    if home_seed == 0 or away_seed == 0:
        return False
    return (
        (home_score > away_score and home_seed > away_seed) or
        (away_score > home_score and away_seed > home_seed)
    )


def format_leaderboard(entries):
    if not entries:
        return "_No data yet_"
    lines = []
    rank = 1
    prev_pts = None
    for i, e in enumerate(entries):
        curr_pts = e.split("(")[-1].rstrip(")")
        if prev_pts is not None and curr_pts != prev_pts:
            rank = i + 1
        lines.append(f"{rank}. {e}")
        prev_pts = curr_pts
    return "\n".join(lines)


def parse_pts(entry):
    """Parse points from a leaderboard entry string like 'Alice (100 pts)'."""
    try:
        return int(entry.split("(")[-1].split()[0])
    except Exception:
        return None


def calculate_movers(new, old):
    """Return biggest_riser string based on points change, or None."""
    if not old or not new:
        return None

    old_pts = {}
    for e in old:
        pts = parse_pts(e)
        if pts is not None:
            old_pts[e.split(" (")[0]] = pts

    movers = []
    for entry in new:
        name = entry.split(" (")[0]
        new_p = parse_pts(entry)
        if new_p is None:
            continue
        if name in old_pts:
            change = new_p - old_pts[name]
            if change > 0:
                movers.append((name, change))

    if not movers:
        return None

    movers.sort(key=lambda x: -x[1])
    name, pts = movers[0]
    return f"🚀📈 *{name}* gained {pts} point{'s' if pts != 1 else ''} — on fire!"


def _game_lines(games):
    lines = []
    for g in games:
        home_score = int(g['home_score'])
        away_score = int(g['away_score'])
        home_seed = g.get('home_seed')
        away_seed = g.get('away_seed')
        upset = " ⚡🔥" if is_upset(home_score, away_score, home_seed, away_seed) else ""
        lines.append(f"- {g['away']} {g['away_score']} - {home_score} {g['home']}{upset}")
    return "\n".join(lines) if lines else "No games yesterday. 😴"


def build_slack_message(game, top_men, top_women, men_url=None, women_url=None):
    """Build a Slack block message for a single game result."""
    home_score = int(game.get('home_score', 0))
    away_score = int(game.get('away_score', 0))
    home_seed  = game.get('home_seed')
    away_seed  = game.get('away_seed')
    upset = "⚡🔥" if is_upset(home_score, away_score, home_seed, away_seed) else ""
    bracket_emoji = "🏆" if game.get('gender') == 'men' else "👑"

    score_line = f"{bracket_emoji} *FINAL*: {game['away']} {away_score} - {home_score} {game['home']} {upset}"

    men_label = f"<{men_url}|Men's Top {len(top_men)}>" if men_url else f"Men's Top {len(top_men)}"
    women_label = f"<{women_url}|Women's Top {len(top_women)}>" if women_url else f"Women's Top {len(top_women)}"

    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": score_line}},
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*{men_label}:*\n{format_leaderboard(top_men)}"}},
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*{women_label}:*\n{format_leaderboard(top_women)}"}}
    ]


def build_daily_summary(men_games, women_games, top_men, top_women, men_url=None, women_url=None, top_n=None):
    """Build daily summary blocks including biggest movers."""
    # fix: if both game lists are empty this is an off-day — skip posting entirely
    # caller should check this return value before calling post_message
    men_games = men_games or []
    women_games = women_games or []
    no_games = not men_games and not women_games

    last_rankings = load_json(LAST_RANKINGS_FILE, {"men": [], "women": []})

    men_riser = calculate_movers(top_men, last_rankings.get("men", []))
    women_riser = calculate_movers(top_women, last_rankings.get("women", []))

    if top_men:
        save_json(LAST_RANKINGS_FILE, {
            "men": top_men,
            "women": top_women if top_women else last_rankings.get("women", [])
        })
    elif top_women:
        save_json(LAST_RANKINGS_FILE, {
            "men": last_rankings.get("men", []),
            "women": top_women
        })

    # Fall back to last known rankings when live data is unavailable (e.g. rest days)
    display_men = top_men or last_rankings.get("men", [])
    display_women = top_women or last_rankings.get("women", [])

    yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%A, %B %-d")

    men_count = len(display_men) if display_men else (top_n or "?")
    women_count = len(display_women) if display_women else (top_n or "?")

    men_header = f"*<{men_url}|🥇 Men's Top {men_count}>*" if men_url else f"*🥇 Men's Top {men_count}*"
    women_header = f"*<{women_url}|👑 Women's Top {women_count}>*" if women_url else f"*👑 Women's Top {women_count}*"

    intro = "_No games yesterday — rest day! 😴_" if no_games else random.choice(_INTROS)

    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": f"{intro}\n_({yesterday})_"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*🏀 Men's Games:*\n{_game_lines(men_games)}"}},
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*👑 Women's Games:*\n{_game_lines(women_games)}"}},
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"{men_header}\n{format_leaderboard(display_men)}"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Men's Movers:*\n{men_riser or '_No changes_'}"}},
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"{women_header}\n{format_leaderboard(display_women)}"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Women's Movers:*\n{women_riser or '_No changes_'}"}},
    ], no_games  # fix: return no_games flag so caller can decide whether to post


def build_yearly_intro_message(config):
    """Generate a yearly intro message based on current config."""
    pools = config.get("POOLS") or []
    top_n = config.get("TOP_N", 5)
    weekend = "yes" if config.get("POST_WEEKENDS") else "no"
    game_updates = "on" if config.get("SEND_GAME_UPDATES") else "off"
    daily_summary = "on" if config.get("SEND_DAILY_SUMMARY") else "off"
    interval = config.get("MINUTES_BETWEEN_MESSAGES", 60)

    # fix: empty POOLS list → show "No pools configured" instead of placeholder lines
    if not pools:
        pools_text = "  • No pools configured"
    else:
        pool_lines = []
        for pool in pools:
            men_url = pool.get("MEN_URL", "")
            women_url = pool.get("WOMEN_URL", "")
            if men_url:
                pool_lines.append(f"  • <{men_url}|Men's bracket pool>")
            else:
                pool_lines.append("  • Men's bracket pool (no URL set)")
            if women_url:
                pool_lines.append(f"  • <{women_url}|Women's bracket pool>")
            else:
                pool_lines.append("  • Women's bracket pool (no URL set)")
        pools_text = "\n".join(pool_lines)

    lines = [
        "🏀 *March Madness Bot is now LIVE!* Here's what I'll be doing:",
        "",
        "Every morning I'll post a recap of the previous day's games plus the current standings from your bracket pools:",
        pools_text,
        "",
        "*Settings:*",
        f"  • Showing top *{top_n}* users per leaderboard",
        f"  • Game-by-game updates: *{game_updates}*",
        f"  • Daily morning summary: *{daily_summary}*",
        f"  • Weekend posts: *{weekend}*",
        f"  • Posting every *{interval} minutes* when active",
        "",
        "May the best bracket win 🏆"
    ]
    return "\n".join(lines)