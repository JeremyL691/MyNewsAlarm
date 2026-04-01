from __future__ import annotations

from pathlib import Path

import requests

from mynewsalarm_app.config import AppConfig
from mynewsalarm_app.news import fetch_news


class DummyLogger:
    def info(self, *_args, **_kwargs):
        return None

    def debug(self, *_args, **_kwargs):
        return None

    def warning(self, *_args, **_kwargs):
        return None

    def exception(self, *_args, **_kwargs):
        return None


def test_fetch_news_from_custom_feed_file(monkeypatch, tmp_path: Path):
    # Point the app at a local RSS file via requests.Session.get monkeypatch.
    sample = Path(__file__).parent / "data" / "sample_rss.xml"
    rss_text = sample.read_text(encoding="utf-8")

    class FakeResp:
        def __init__(self, content: bytes):
            self.content = content

        def raise_for_status(self):
            return None

    def fake_get(self, _url: str, timeout: int, headers: dict[str, str]):
        assert timeout == 15  # default AppConfig.request_timeout_sec
        assert "User-Agent" in headers
        return FakeResp(rss_text.encode("utf-8"))

    monkeypatch.setattr(requests.Session, "get", fake_get)

    cfg = AppConfig(
        selected_feed_ids=["custom_1"],
        custom_feeds=[{"id": "custom_1", "name": "Local", "url": "file://ignored", "language_tag": "en-US"}],
        max_items=5,
        summary_sentences=2,
    )

    items, feed_errors = fetch_news(cfg, logger=DummyLogger())
    assert feed_errors == 0
    assert len(items) == 2
    assert items[0].title
    assert items[0].summary


def test_fetch_news_rss_timeout_increments_error_and_continues(monkeypatch):
    calls: list[str] = []

    def fake_get(self, url: str, timeout: int, headers: dict[str, str]):
        calls.append(url)
        raise requests.Timeout("simulated")

    monkeypatch.setattr(requests.Session, "get", fake_get)

    cfg = AppConfig(
        selected_feed_ids=["custom_1"],
        custom_feeds=[{"id": "custom_1", "name": "Local", "url": "https://example.com/rss", "language_tag": "en-US"}],
        max_items=5,
        summary_sentences=2,
        request_timeout_sec=1,
    )

    items, feed_errors = fetch_news(cfg, logger=DummyLogger())
    assert calls == ["https://example.com/rss"]
    assert items == []
    assert feed_errors == 1
