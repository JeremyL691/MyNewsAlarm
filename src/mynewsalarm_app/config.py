from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

APP_NAME = "MyNewsAlarm"
BUNDLE_ID = "com.openclaw.mynewsalarm"


def app_support_dir() -> Path:
    base = Path.home() / "Library" / "Application Support" / APP_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base


def logs_dir() -> Path:
    base = Path.home() / "Library" / "Logs" / APP_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base


def config_path() -> Path:
    return app_support_dir() / "config.json"


def status_path() -> Path:
    return app_support_dir() / "status.json"


# Curated default RSS feeds.
# Each feed has a stable id used for config selection.
DEFAULT_FEEDS: list[dict[str, str]] = [
    # United States
    {
        "id": "us_top_npr",
        "name": "NPR News",
        "url": "https://feeds.npr.org/1001/rss.xml",
        "country": "United States",
        "category": "Top",
        "language_tag": "en-US",
    },
    {
        "id": "us_top_ap",
        "name": "Associated Press (Top News)",
        "url": "https://feeds.apnews.com/apf-topnews",
        "country": "United States",
        "category": "Top",
        "language_tag": "en-US",
    },
    {
        "id": "us_business_nyt",
        "name": "NYT Business",
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
        "country": "United States",
        "category": "Business",
        "language_tag": "en-US",
    },
    {
        "id": "us_tech_verge",
        "name": "The Verge",
        "url": "https://www.theverge.com/rss/index.xml",
        "country": "United States",
        "category": "Technology",
        "language_tag": "en-US",
    },
    {
        "id": "us_tech_arstechnica",
        "name": "Ars Technica",
        "url": "https://feeds.arstechnica.com/arstechnica/index",
        "country": "United States",
        "category": "Technology",
        "language_tag": "en-US",
    },
    # United Kingdom
    {
        "id": "uk_top_bbc",
        "name": "BBC News",
        "url": "https://feeds.bbci.co.uk/news/rss.xml",
        "country": "United Kingdom",
        "category": "Top",
        "language_tag": "en-GB",
    },
    {
        "id": "uk_world_bbc",
        "name": "BBC World",
        "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
        "country": "United Kingdom",
        "category": "World",
        "language_tag": "en-GB",
    },
    {
        "id": "uk_business_bbc",
        "name": "BBC Business",
        "url": "https://feeds.bbci.co.uk/news/business/rss.xml",
        "country": "United Kingdom",
        "category": "Business",
        "language_tag": "en-GB",
    },
    # Canada
    {
        "id": "ca_top_cbc",
        "name": "CBC Top Stories",
        "url": "https://www.cbc.ca/cmlink/rss-topstories",
        "country": "Canada",
        "category": "Top",
        "language_tag": "en-CA",
    },
    # Australia
    {
        "id": "au_top_abc",
        "name": "ABC Australia Top Stories",
        "url": "https://www.abc.net.au/news/feed/51120/rss.xml",
        "country": "Australia",
        "category": "Top",
        "language_tag": "en-AU",
    },
    # International
    {
        "id": "int_world_reuters",
        "name": "Reuters World News",
        "url": "https://feeds.reuters.com/Reuters/worldNews",
        "country": "International",
        "category": "World",
        "language_tag": "en-US",
    },
]


def feeds_by_id(custom_feeds: list[dict[str, str]] | None = None) -> dict[str, dict[str, str]]:
    """Return feeds keyed by stable id.

    custom_feeds entries override defaults if ids collide.
    """
    out = {f["id"]: dict(f) for f in DEFAULT_FEEDS}
    for f in (custom_feeds or []):
        if not f.get("id"):
            continue
        out[str(f["id"])] = {k: str(v) for k, v in f.items() if v is not None}
    return out


@dataclass
class AppStatus:
    last_run_at_local: str | None = None
    last_run_ok: bool | None = None
    last_run_message: str | None = None
    last_run_duration_sec: float | None = None
    last_items_read: int | None = None
    last_feed_errors: int | None = None


@dataclass
class AppConfig:
    # Alarm
    alarm_time: str = "07:30"  # HH:MM local time

    # Feeds
    selected_feed_ids: list[str] = field(default_factory=lambda: ["us_top_npr", "uk_top_bbc"])
    custom_feeds: list[dict[str, str]] = field(default_factory=list)

    # Reading
    max_items: int = 10  # UI supports 3..20
    summary_sentences: int = 4

    # Speech
    default_voice: str | None = None  # macOS say voice name (e.g., "Samantha")
    voice_by_language: dict[str, str] = field(default_factory=dict)  # e.g., {"en-GB": "Daniel"}
    say_rate: int | None = None

    # Network
    request_timeout_sec: int = 15
    user_agent: str = "MyNewsAlarm/1.0 (+https://openclaw.ai)"

    # Behavior
    include_source_name: bool = True

    # Scheduling
    installed_app_path: str | None = None  # used when installing LaunchAgent from the UI


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config() -> AppConfig:
    cfg_file = config_path()
    defaults = AppConfig()

    if not cfg_file.exists():
        save_config(defaults)
        return defaults

    try:
        data = json.loads(cfg_file.read_text(encoding="utf-8"))
        merged = _deep_merge(defaults.__dict__, data)
        return AppConfig(**merged)
    except Exception:
        # Fall back to defaults but keep the user's file intact.
        return defaults


def save_config(cfg: AppConfig) -> None:
    cfg_file = config_path()
    cfg_file.write_text(
        json.dumps(cfg.__dict__, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_status() -> AppStatus:
    p = status_path()
    if not p.exists():
        return AppStatus()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return AppStatus(**data)
    except Exception:
        return AppStatus(last_run_ok=False, last_run_message="Could not read status.json")


def save_status(st: AppStatus) -> None:
    p = status_path()
    p.write_text(json.dumps(st.__dict__, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_alarm_time(alarm_time: str) -> tuple[int, int]:
    parts = alarm_time.strip().split(":")
    if len(parts) != 2:
        raise ValueError("alarm_time must be in HH:MM format")
    hh, mm = int(parts[0]), int(parts[1])
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise ValueError("alarm_time must be a valid 24h time (00:00..23:59)")
    return hh, mm
