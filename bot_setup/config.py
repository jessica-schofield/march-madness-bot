import json
import datetime
import shutil
from pathlib import Path

CONFIG_FILE               = Path(__file__).parent / "config.json"
CONFIG_EXAMPLE_FILE       = Path(__file__).parent / "example.config.json"
SEEN_FILE                 = Path(__file__).parent / "seen_games.json"
LAST_POST_FILE            = Path(__file__).parent / "last_post.json"
YEARLY_FLAG_FILE          = Path(__file__).parent.parent / "yearly_flag.json"
YEARLY_REMINDER_FLAG_FILE = Path(__file__).parent.parent / "yearly_reminder_flag.json"
PLAYWRIGHT_STATE          = Path(__file__).parent.parent / "playwright_state.json"
LAST_RANKINGS_FILE        = Path(__file__).parent.parent / "last_rankings.json"

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
    "VERSION": "1.2.0",
}

_OPTIONAL_KEYS = {"SLACK_MANAGER_ID", "LIVE_COUNTER_URL"}

_FALLBACK_TOURNAMENT_END_MEN   = datetime.date(2026, 4, 7)
_FALLBACK_TOURNAMENT_END_WOMEN = datetime.date(2026, 4, 6)

_MISSING = object()


def _seed_config_from_example():
    if CONFIG_EXAMPLE_FILE.exists():
        shutil.copy(CONFIG_EXAMPLE_FILE, CONFIG_FILE)
        print("[INFO] Created config.json from config.example.json")
    else:
        CONFIG_FILE.write_text(json.dumps({}, indent=2))
        print("[WARN] config.example.json not found — created empty config.json")


def load_json(path, default=_MISSING):
    if default is _MISSING:
        default = {}
    target = Path(path)
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
    men_raw   = config.get("TOURNAMENT_END_MEN", "")
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
    return max(men_end, women_end)


def fill_defaults(cfg):
    for key, default in REQUIRED_KEYS.items():
        if key not in cfg:
            cfg[key] = default
    return cfg


def test_method_key_stripped_before_run_setup(self):
    """METHOD must not be in the config passed to run_setup."""
    passed_config = self._get_config_for_run_setup()
    assert "METHOD" not in passed_config
