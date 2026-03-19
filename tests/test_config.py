import pytest

from mynewsalarm_app.config import AppConfig, feeds_by_id, validate_alarm_time


def test_validate_alarm_time_ok():
    assert validate_alarm_time("07:30") == (7, 30)
    assert validate_alarm_time("00:00") == (0, 0)
    assert validate_alarm_time("23:59") == (23, 59)


@pytest.mark.parametrize("bad", ["", "24:00", "12:60", "aa:bb", "123"])
def test_validate_alarm_time_bad(bad: str):
    with pytest.raises(ValueError):
        validate_alarm_time(bad)


def test_custom_feeds_override_and_merge():
    cfg = AppConfig(custom_feeds=[{"id": "us_top_npr", "name": "Override", "url": "https://example.com/rss"}])
    merged = feeds_by_id(cfg.custom_feeds)
    assert merged["us_top_npr"]["name"] == "Override"
    assert merged["us_top_npr"]["url"] == "https://example.com/rss"
