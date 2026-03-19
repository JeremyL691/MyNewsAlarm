from __future__ import annotations

from datetime import datetime

from .config import AppConfig, load_status, save_status
from .logging_utils import setup_logging
from .news import fetch_news
from .speech import speak_text


def _voice_for_item(cfg: AppConfig, language_tag: str) -> str | None:
    # Priority:
    # 1) Per-language override
    # 2) Global default_voice
    v = (cfg.voice_by_language or {}).get(language_tag)
    return v or cfg.default_voice


def run_once(cfg: AppConfig, *, cancel_event=None) -> int:
    """Run one full fetch+briefing cycle.

    cancel_event: optional threading.Event; if set, speech stops between items.
    """
    logger = setup_logging()
    st = load_status()

    started_at = datetime.now()
    logger.info("MyNewsAlarm run-once started")

    def cancelled() -> bool:
        return bool(cancel_event is not None and cancel_event.is_set())

    try:
        items, feed_errors = fetch_news(cfg, logger=logger)
        logger.info(f"Fetched {len(items)} items (feed_errors={feed_errors})")

        now_str = started_at.strftime("%A, %B %d")
        intro = f"Good morning. Here is your news briefing for {now_str}."
        if not cancelled():
            speak_text(cfg, intro, logger=logger)

        if cancelled():
            raise RuntimeError("Cancelled")

        if not items:
            speak_text(cfg, "I could not fetch any news items right now.", logger=logger)
        else:
            for i, it in enumerate(items, start=1):
                if cancelled():
                    raise RuntimeError("Cancelled")

                if cfg.include_source_name:
                    head = f"Item {i}. From {it.source}. {it.title}."
                else:
                    head = f"Item {i}. {it.title}."

                voice = _voice_for_item(cfg, it.language_tag)
                speak_text(cfg, head, logger=logger, voice=voice)
                if cancelled():
                    raise RuntimeError("Cancelled")
                speak_text(cfg, it.summary, logger=logger, voice=voice)

        if not cancelled():
            speak_text(cfg, "That is all for now.", logger=logger)

        duration = (datetime.now() - started_at).total_seconds()
        st.last_run_at_local = started_at.strftime("%Y-%m-%d %H:%M:%S")
        st.last_run_ok = True
        st.last_items_read = len(items)
        st.last_feed_errors = int(feed_errors)
        st.last_run_duration_sec = float(duration)
        msg = f"OK: read {len(items)} item(s)"
        if feed_errors:
            msg += f" ({feed_errors} feed error(s))"
        st.last_run_message = msg
        save_status(st)

        logger.info("MyNewsAlarm run-once complete")
        return 0

    except Exception as e:
        duration = (datetime.now() - started_at).total_seconds()
        st.last_run_at_local = started_at.strftime("%Y-%m-%d %H:%M:%S")
        st.last_run_ok = False
        st.last_run_duration_sec = float(duration)
        st.last_run_message = f"ERROR: {e}"
        save_status(st)

        logger.info(f"MyNewsAlarm run-once failed: {e}")
        return 1
