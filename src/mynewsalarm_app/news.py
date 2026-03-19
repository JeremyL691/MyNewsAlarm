from __future__ import annotations

from dataclasses import dataclass

import feedparser
import requests
from bs4 import BeautifulSoup

from .config import AppConfig, feeds_by_id
from .summarize import pick_best_text, strip_html, summarize_text


@dataclass
class NewsItem:
    title: str
    link: str
    published: str | None
    source: str
    summary: str
    feed_id: str
    language_tag: str


def _http_fetch_article_text(url: str, timeout: int, user_agent: str) -> str:
    headers = {"User-Agent": user_agent}
    r = requests.get(url, timeout=timeout, headers=headers)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    main = soup.find("main") or soup.find("article") or soup.body
    text = main.get_text(" ", strip=True) if main else soup.get_text(" ", strip=True)
    return strip_html(text)


def _entry_published(entry: dict) -> str | None:
    if entry.get("published"):
        return str(entry.get("published"))
    if entry.get("updated"):
        return str(entry.get("updated"))
    return None


def _entry_source(feed: feedparser.FeedParserDict) -> str:
    title = feed.get("feed", {}).get("title")
    if title:
        return str(title)
    href = feed.get("href")
    return str(href or "Unknown")


def fetch_news(cfg: AppConfig, logger) -> tuple[list[NewsItem], int]:
    feeds = feeds_by_id(cfg.custom_feeds)
    selected = [fid for fid in cfg.selected_feed_ids if fid in feeds]

    if not selected:
        return [], 0

    items: list[NewsItem] = []
    feed_errors = 0

    for feed_id in selected:
        feed_def = feeds[feed_id]
        feed_url = feed_def["url"]
        language_tag = feed_def.get("language_tag", "en-US")

        try:
            logger.info(f"Fetching feed: {feed_url}")

            # feedparser can fetch URLs itself but does not reliably support timeouts.
            # Use requests with the app-configured timeout, then parse the content.
            headers = {"User-Agent": cfg.user_agent}
            r = requests.get(feed_url, timeout=cfg.request_timeout_sec, headers=headers)
            r.raise_for_status()
            parsed = feedparser.parse(r.content)

            if getattr(parsed, "bozo", 0):
                logger.info(f"Feed parse warning for {feed_url}: {getattr(parsed, 'bozo_exception', None)}")

            source = _entry_source(parsed)

            for entry in parsed.entries[: max(15, cfg.max_items)]:
                title = strip_html(str(entry.get("title", ""))).strip() or "Untitled"
                link = str(entry.get("link", "")).strip()
                published = _entry_published(entry)

                content0 = ""
                if entry.get("content") and isinstance(entry.get("content"), list) and entry["content"]:
                    content0 = str(entry["content"][0].get("value", ""))

                rss_text = pick_best_text(
                    str(entry.get("summary", "")),
                    content0,
                    str(entry.get("description", "")),
                )

                summary = summarize_text(rss_text, max_sentences=cfg.summary_sentences)

                if not summary and link:
                    try:
                        article_text = _http_fetch_article_text(
                            link,
                            timeout=cfg.request_timeout_sec,
                            user_agent=cfg.user_agent,
                        )
                        summary = summarize_text(article_text, max_sentences=cfg.summary_sentences)
                    except Exception:
                        # Include stack trace for better diagnosis (timeouts, parsing errors, etc.).
                        logger.exception(f"Article fetch failed: {link}")

                if not summary:
                    summary = "No summary available."

                items.append(
                    NewsItem(
                        title=title,
                        link=link,
                        published=published,
                        source=source,
                        summary=summary,
                        feed_id=feed_id,
                        language_tag=language_tag,
                    )
                )

                if len(items) >= cfg.max_items:
                    break

            if len(items) >= cfg.max_items:
                break

        except Exception:
            feed_errors += 1
            # Include stack trace for better diagnosis (timeouts, invalid feeds, etc.).
            logger.exception(f"Feed fetch failed: {feed_url}")
            continue

    return items[: cfg.max_items], feed_errors
