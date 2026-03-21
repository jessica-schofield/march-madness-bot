import json
import datetime
import shutil
from pathlib import Path

CONFIG_FILE = Path(__file__).parent / "config.json"
CONFIG_EXAMPLE_FILE = Path(__file__).parent / "config.example.json"
SEEN_FILE = Path("seen_games.json")
LAST_POST_FILE = Path("last_post.json")
LAST_RANKINGS_FILE = Path("last_rankings.json")
YEARLY_FLAG_FILE = Path("yearly_flag.json")
YEARLY_REMINDER_FLAG_FILE = Path("yearly_reminder_flag.json")
PLAYWRIGHT_STATE = Path("playwright_state.json")
PLAYWRIGHT_HEADLESS = True

REQUIRED_KEYS = {
    "TOP_N": 3,
    "POOLS": [],
    "MINUTES_BETWEEN_MESSAGES": 30,
    "POST_WEEKENDS": False,
    "SEND_GAME_UPDATES": True,
    "SEND_DAILY_SUMMARY": True,
    "PLAYWRIGHT_HEADLESS": True,
    "PLAYWRIGHT_STATE": "playwright_state.json",
    "SLACK_WEBHOOK_URL": "",
    "SLACK_MANAGER_ID": "",
    "LIVE_COUNTER_URL": "",
    "VERSION": "1.1.0",
}

# Keys that are allowed to be empty string — they are optional
_OPTIONAL_KEYS = {"SLACK_MANAGER_ID", "LIVE_COUNTER_URL"}

# ⚠️ UPDATE EACH YEAR
_FALLBACK_TOURNAMENT_END_MEN = datetime.date(2026, 4, 7)
_FALLBACK_TOURNAMENT_END_WOMEN = datetime.date(2026, 4, 6)

_MISSING = object()  # sentinel so callers can pass None or [] as explicit defaults


def _seed_config_from_example():
    """
    Copy config.example.json → config.json on first run so new users
    get a valid starting point without any manual steps.
    """
    if CONFIG_EXAMPLE_FILE.exists():
        shutil.copy(CONFIG_EXAMPLE_FILE, CONFIG_FILE)
        print(f"[INFO] Created config.json from config.example.json")
    else:
        CONFIG_FILE.write_text(json.dumps({}, indent=2))
        print(f"[WARN] config.example.json not found — created empty config.json")


def load_json(path, default=_MISSING):
    if default is _MISSING:
        default = {}
    target = Path(path)

    # Seed config.json from example on first run
    if not target.exists() and target.resolve() == CONFIG_FILE.resolve():
        _seed_config_from_example()

    if target.exists():
        try:
            with open(target) as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARN] Failed to load {path}: {e}")
            return default
    return default


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def needs_setup(cfg):
    """Return True if any required config key is missing or has an empty/None value.
    Treats 0 and False as valid values — only None and '' are considered unset.
    Optional keys (SLACK_MANAGER_ID, LIVE_COUNTER_URL) may be empty strings.
    """
    for k in REQUIRED_KEYS:
        if k not in cfg:
            return True
        v = cfg[k]
        if k in _OPTIONAL_KEYS:
            continue
        if v is None or v == "":
            return True
        if k == "POOLS" and isinstance(v, list) and len(v) == 0:
            return True
    return False


def get_tournament_end(config, gender=None):
    """
    Return the tournament end date for the given gender, or the later of the two
    if gender is None. Falls back to module-level defaults if not set in config.
    """
    men_raw = config.get("TOURNAMENT_END_MEN", "")
    women_raw = config.get("TOURNAMENT_END_WOMEN", "")

    try:
        men_end = datetime.date.fromisoformat(men_raw) if men_raw else _FALLBACK_TOURNAMENT_END_MEN
    except ValueError:
        men_end = _FALLBACK_TOURNAMENT_END_MEN

    try:
        women_end = datetime.date.fromisoformat(women_raw) if women_raw else _FALLBACK_TOURNAMENT_END_WOMEN
    except ValueError:
        women_end = _FALLBACK_TOURNAMENT_END_WOMEN

    if gender == "men":
        return men_end
    if gender == "women":
        return women_end
    return max(men_end, women_end)  # bot stays live until both are done


def fill_defaults(cfg):
    for key, default in REQUIRED_KEYS.items():
        if key not in cfg:
            cfg[key] = default
    return cfg
