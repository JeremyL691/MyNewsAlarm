from __future__ import annotations

import argparse
import queue
import subprocess
import sys
import threading
from pathlib import Path

# Allow running from a git checkout without installing.
PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str((PROJECT_DIR / "src").resolve()))

from mynewsalarm_app.config import (  # noqa: E402
    config_path,
    feeds_by_id,
    load_config,
    load_status,
    save_config,
    validate_alarm_time,
)
from mynewsalarm_app.launchagent import install_launchagent, label, uninstall_launchagent  # noqa: E402
from mynewsalarm_app.logging_utils import setup_logging  # noqa: E402
from mynewsalarm_app.run_once import run_once  # noqa: E402
from mynewsalarm_app.speech import stop_speaking  # noqa: E402


def _launchctl(args: list[str]) -> int:
    proc = subprocess.run(["/bin/launchctl", *args], capture_output=True, text=True)
    return proc.returncode


def _os_getuid() -> int:
    import os

    return os.getuid()


def _guess_app_bundle_path() -> Path | None:
    # When packaged by py2app, argv[0] is .../MyNewsAlarm.app/Contents/MacOS/MyNewsAlarm
    p = Path(sys.argv[0]).resolve()
    for parent in p.parents:
        if parent.suffix == ".app":
            return parent
        if parent.name == "Contents" and parent.parent.suffix == ".app":
            return parent.parent
    return None


def _resource_path(rel: str) -> str:
    """Return absolute path to a resource for both source runs and py2app bundles."""
    bundle = _guess_app_bundle_path()
    if bundle is not None:
        candidate = bundle / "Contents" / "Resources" / rel
        return str(candidate)
    # source run
    return str((PROJECT_DIR / rel).resolve())


def _list_say_voices() -> list[str]:
    try:
        proc = subprocess.run(["/usr/bin/say", "-v", "?"], capture_output=True, text=True, check=True)
        voices: list[str] = []
        for line in proc.stdout.splitlines():
            # Format: Name  Locale  # Description
            parts = line.strip().split()
            if parts:
                voices.append(parts[0])
        seen = set()
        out: list[str] = []
        for v in voices:
            if v in seen:
                continue
            seen.add(v)
            out.append(v)
        return out
    except Exception:
        return []


def _slugify(s: str) -> str:
    out = []
    for ch in (s or ""):
        if ch.isalnum():
            out.append(ch.lower())
        elif ch in (" ", "-", "_", "."):
            out.append("_")
    slug = "".join(out).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug or "feed"


def run_ui() -> None:
    import rumps

    # UI events posted from worker threads -> drained on the main thread.
    # NOTE: rumps UI mutation is not thread-safe.
    UiEvent = tuple[str, object, object, object]

    class MyNewsAlarmApp(rumps.App):
        def __init__(self):
            icon_path = _resource_path("assets/MyNewsAlarmStatus.png")
            super().__init__("MyNewsAlarm", quit_button=None, icon=icon_path)
            self.logger = setup_logging()

            self.cfg = load_config()
            self.voices = _list_say_voices()

            self._run_thread: threading.Thread | None = None
            self._cancel_event = threading.Event()

            self._ui_queue: queue.Queue[UiEvent] = queue.Queue()

            self.status_item = rumps.MenuItem("Last run: (never)")

            self.menu = [
                rumps.MenuItem("Run now"),
                rumps.MenuItem("Stop speaking"),
                self.status_item,
                None,
                rumps.MenuItem("Alarm time"),
                rumps.MenuItem("Items to read"),
                rumps.MenuItem("Summary length"),
                None,
                rumps.MenuItem("Default voice"),
                rumps.MenuItem("Voices by language"),
                rumps.MenuItem("Speech rate"),
                None,
                rumps.MenuItem("Feeds"),
                rumps.MenuItem("Custom feeds"),
                None,
                rumps.MenuItem("Install LaunchAgent"),
                rumps.MenuItem("Reinstall LaunchAgent"),
                rumps.MenuItem("Uninstall LaunchAgent"),
                None,
                rumps.MenuItem("Open config folder"),
                rumps.MenuItem("Open status file"),
                rumps.MenuItem("Open log file"),
                None,
                rumps.MenuItem("Quit"),
            ]

            # Drain worker-posted UI events on the main thread.
            self._ui_timer = rumps.Timer(self._drain_ui_queue, 0.5)
            self._ui_timer.start()

            # Defer menu building until the app runloop is active.
            # (On some systems rumps' underlying NSMenu objects are not ready during __init__.)
            self._post_ui("rebuild")
            self._post_ui("refresh_status")

            # Keep the status line fresh without updating UI from background threads.
            self._status_timer = rumps.Timer(lambda _: self._refresh_status_text(), 5)
            self._status_timer.start()

        # -------------------- Main-thread UI queue --------------------

        def _post_ui(self, kind: str, a: object = None, b: object = None, c: object = None) -> None:
            # queue.Queue is thread-safe.
            self._ui_queue.put((kind, a, b, c))

        def _drain_ui_queue(self, _=None) -> None:
            # Always runs on the main thread (rumps.Timer callback).
            while True:
                try:
                    kind, a, b, c = self._ui_queue.get_nowait()
                except queue.Empty:
                    break

                if kind == "rebuild":
                    try:
                        self._rebuild_dynamic_menus()
                    except AttributeError:
                        # rumps menu backing objects may not be ready yet; retry next tick.
                        self._ui_queue.put(("rebuild", None, None, None))
                elif kind == "refresh_status":
                    self._refresh_status_text()
                elif kind == "notify":
                    # a=title, b=subtitle, c=message
                    try:
                        rumps.notification("MyNewsAlarm", str(a or ""), str(c or ""))
                    except Exception:
                        # Don't crash the UI if notifications fail.
                        self.logger.exception("Notification failed")
                else:
                    self.logger.warning("Unknown UI event: %s", kind)

        # -------------------- Menu builders --------------------

        def _rebuild_dynamic_menus(self) -> None:
            self.cfg = load_config()  # in case file changed externally

            self.menu["Alarm time"].title = f"Alarm time: {self.cfg.alarm_time}"

            # Items
            items_root = self.menu["Items to read"]
            items_root.clear()
            for n in range(3, 21):
                it = rumps.MenuItem(str(n), callback=self._set_max_items)
                it.state = n == int(self.cfg.max_items)
                items_root.add(it)

            # Summary length
            summ_root = self.menu["Summary length"]
            summ_root.clear()
            for n in range(1, 7):
                it = rumps.MenuItem(f"{n} sentence(s)", callback=self._set_summary_sentences)
                it._sentences = n  # type: ignore[attr-defined]
                it.state = n == int(self.cfg.summary_sentences)
                summ_root.add(it)

            # Default voice
            voice_root = self.menu["Default voice"]
            voice_root.clear()
            none_item = rumps.MenuItem("(System default)", callback=self._set_default_voice)
            none_item.state = self.cfg.default_voice is None
            voice_root.add(none_item)
            voice_root.add(None)

            for v in (self.voices or [])[:80]:
                mi = rumps.MenuItem(v, callback=self._set_default_voice)
                mi.state = self.cfg.default_voice == v
                voice_root.add(mi)

            voice_root.add(None)
            voice_root.add(rumps.MenuItem("Refresh voices", callback=self._refresh_voices))

            # Voices by language
            vbl_root = self.menu["Voices by language"]
            vbl_root.clear()
            feeds = feeds_by_id(self.cfg.custom_feeds)
            lang_tags = sorted(
                {feeds[fid].get("language_tag", "en-US") for fid in self.cfg.selected_feed_ids if fid in feeds}
            )
            if not lang_tags:
                vbl_root.add(rumps.MenuItem("(Select some feeds first)", callback=None))
            else:
                for tag in lang_tags:
                    sub = rumps.MenuItem(tag)
                    clear = rumps.MenuItem("(Use default)", callback=self._clear_language_voice)
                    clear._lang_tag = tag  # type: ignore[attr-defined]
                    clear.state = tag not in (self.cfg.voice_by_language or {})
                    sub.add(clear)
                    sub.add(None)
                    for v in (self.voices or [])[:80]:
                        mi = rumps.MenuItem(v, callback=self._set_language_voice)
                        mi._lang_tag = tag  # type: ignore[attr-defined]
                        mi.state = (self.cfg.voice_by_language or {}).get(tag) == v
                        sub.add(mi)
                    vbl_root.add(sub)

            # Speech rate
            rate_root = self.menu["Speech rate"]
            rate_root.clear()
            sysdef = rumps.MenuItem("(System default)", callback=self._set_say_rate)
            sysdef._rate = None  # type: ignore[attr-defined]
            sysdef.state = self.cfg.say_rate is None
            rate_root.add(sysdef)
            rate_root.add(None)
            for r in [140, 160, 180, 200, 220, 240]:
                mi = rumps.MenuItem(str(r), callback=self._set_say_rate)
                mi._rate = r  # type: ignore[attr-defined]
                mi.state = self.cfg.say_rate == r
                rate_root.add(mi)
            rate_root.add(None)
            rate_root.add(rumps.MenuItem("Custom…", callback=self._custom_rate))

            # Feeds (defaults+custom)
            feeds_root = self.menu["Feeds"]
            feeds_root.clear()

            all_feeds = list(feeds_by_id(self.cfg.custom_feeds).values())
            all_feeds.sort(key=lambda f: (f.get("country", ""), f.get("category", ""), f.get("name", "")))

            by_country: dict[str, list[dict[str, str]]] = {}
            for f in all_feeds:
                by_country.setdefault(f.get("country", "Other"), []).append(f)

            selected = set(self.cfg.selected_feed_ids)
            for country in sorted(by_country.keys()):
                country_menu = rumps.MenuItem(country)
                by_cat: dict[str, list[dict[str, str]]] = {}
                for f in by_country[country]:
                    by_cat.setdefault(f.get("category", "Other"), []).append(f)

                for cat in sorted(by_cat.keys()):
                    cat_menu = rumps.MenuItem(cat)
                    for f in by_cat[cat]:
                        feed_item = rumps.MenuItem(f"{f['name']}", callback=self._toggle_feed)
                        feed_item.state = f["id"] in selected
                        feed_item._feed_id = f["id"]  # type: ignore[attr-defined]
                        cat_menu.add(feed_item)
                    country_menu.add(cat_menu)
                feeds_root.add(country_menu)

            feeds_root.add(None)
            feeds_root.add(rumps.MenuItem("Select all feeds", callback=self._select_all_feeds))
            feeds_root.add(rumps.MenuItem("Select none", callback=self._select_none_feeds))

            # Custom feeds
            cf_root = self.menu["Custom feeds"]
            cf_root.clear()
            cf_root.add(rumps.MenuItem("Add custom feed…", callback=self._add_custom_feed))
            if self.cfg.custom_feeds:
                cf_root.add(None)
                for f in self.cfg.custom_feeds:
                    name = f.get("name", f.get("id", "(unnamed)"))
                    mi = rumps.MenuItem(f"Remove: {name}", callback=self._remove_custom_feed)
                    mi._feed_id = f.get("id")  # type: ignore[attr-defined]
                    cf_root.add(mi)

            # Stop speaking enabled only while a run is active
            self.menu["Stop speaking"].set_callback(self.on_stop_speaking)
            self.menu["Stop speaking"].hidden = not self._is_running()

        def _refresh_status_text(self) -> None:
            st = load_status()
            if not st.last_run_at_local:
                self.status_item.title = "Last run: (never)"
                return
            ok = "OK" if st.last_run_ok else "ERROR"
            msg = st.last_run_message or ""
            self.status_item.title = f"Last run: {ok} @ {st.last_run_at_local} — {msg}"

        def _is_running(self) -> bool:
            t = self._run_thread
            return bool(t is not None and t.is_alive())

        # -------------------- Actions --------------------

        @rumps.clicked("Run now")
        def on_run_now(self, _):
            if self._is_running():
                rumps.alert("Already running", "A run is currently in progress.")
                return
            self._run_now_background()

        @rumps.clicked("Stop speaking")
        def on_stop_speaking(self, _):
            if not self._is_running():
                return
            self._cancel_event.set()
            stop_speaking(logger=self.logger)
            rumps.notification("MyNewsAlarm", "Stopping", "Stopping speech…")

        def _run_now_background(self) -> None:
            self._cancel_event.clear()

            def worker():
                try:
                    self.logger.info("Run now triggered")
                    cfg = load_config()
                    rc = run_once(cfg, cancel_event=self._cancel_event)
                    title = "Run complete" if rc == 0 else "Run finished with errors"
                    msg = load_status().last_run_message or ""
                    self._post_ui("notify", title, None, msg)
                finally:
                    # Always request a UI refresh from the main thread.
                    self._post_ui("rebuild")
                    self._post_ui("refresh_status")

            self._run_thread = threading.Thread(target=worker, daemon=True)
            self._run_thread.start()
            self._rebuild_dynamic_menus()

        @rumps.clicked("Alarm time")
        def on_alarm_time(self, _):
            w = rumps.Window(
                title="Alarm time (24-hour format)",
                message="Enter a local time like 07:30",
                default_text=self.cfg.alarm_time,
                ok="Save",
                cancel="Cancel",
            )
            r = w.run()
            if not r.clicked:
                return

            txt = (r.text or "").strip()
            try:
                hh, mm = validate_alarm_time(txt)
            except Exception as e:
                rumps.alert("Invalid time", str(e))
                return

            # Normalize to HH:MM so the UI and config remain consistent.
            self.cfg.alarm_time = f"{hh:02d}:{mm:02d}"
            save_config(self.cfg)
            self._rebuild_dynamic_menus()

        def _set_max_items(self, sender):
            try:
                n = int(sender.title)
            except Exception:
                return
            self.cfg.max_items = n
            save_config(self.cfg)
            self._rebuild_dynamic_menus()

        def _set_summary_sentences(self, sender):
            n = getattr(sender, "_sentences", None)
            if not n:
                return
            self.cfg.summary_sentences = int(n)
            save_config(self.cfg)
            self._rebuild_dynamic_menus()

        def _set_default_voice(self, sender):
            if sender.title == "(System default)":
                self.cfg.default_voice = None
            else:
                self.cfg.default_voice = sender.title
            save_config(self.cfg)
            self._rebuild_dynamic_menus()

        def _set_language_voice(self, sender):
            tag = getattr(sender, "_lang_tag", None)
            if not tag:
                return
            self.cfg.voice_by_language = dict(self.cfg.voice_by_language or {})
            self.cfg.voice_by_language[str(tag)] = sender.title
            save_config(self.cfg)
            self._rebuild_dynamic_menus()

        def _clear_language_voice(self, sender):
            tag = getattr(sender, "_lang_tag", None)
            if not tag:
                return
            m = dict(self.cfg.voice_by_language or {})
            m.pop(str(tag), None)
            self.cfg.voice_by_language = m
            save_config(self.cfg)
            self._rebuild_dynamic_menus()

        def _refresh_voices(self, _):
            self.voices = _list_say_voices()
            self._rebuild_dynamic_menus()

        def _set_say_rate(self, sender):
            rate = getattr(sender, "_rate", "MISSING")
            if rate == "MISSING":
                return
            self.cfg.say_rate = None if rate is None else int(rate)
            save_config(self.cfg)
            self._rebuild_dynamic_menus()

        def _custom_rate(self, _):
            cur = "" if self.cfg.say_rate is None else str(self.cfg.say_rate)
            w = rumps.Window(
                title="Speech rate",
                message="Enter a say rate number (typical: 140–240). Leave blank for system default.",
                default_text=cur,
                ok="Save",
                cancel="Cancel",
            )
            r = w.run()
            if not r.clicked:
                return
            txt = (r.text or "").strip()
            if not txt:
                self.cfg.say_rate = None
            else:
                try:
                    self.cfg.say_rate = int(txt)
                except Exception:
                    rumps.alert("Invalid rate", "Please enter a whole number.")
                    return
            save_config(self.cfg)
            self._rebuild_dynamic_menus()

        def _toggle_feed(self, sender):
            fid = getattr(sender, "_feed_id", None)
            if not fid:
                return
            selected = list(self.cfg.selected_feed_ids)
            if fid in selected:
                selected.remove(fid)
            else:
                selected.append(fid)
            self.cfg.selected_feed_ids = selected
            save_config(self.cfg)
            self._rebuild_dynamic_menus()

        def _select_all_feeds(self, _):
            self.cfg.selected_feed_ids = list(feeds_by_id(self.cfg.custom_feeds).keys())
            save_config(self.cfg)
            self._rebuild_dynamic_menus()

        def _select_none_feeds(self, _):
            self.cfg.selected_feed_ids = []
            save_config(self.cfg)
            self._rebuild_dynamic_menus()

        def _add_custom_feed(self, _):
            w = rumps.Window(
                title="Add custom RSS feed",
                message="Enter: Name | URL | Language tag (optional)\nExample: My Blog | https://example.com/rss.xml | en-US",
                default_text="",
                ok="Add",
                cancel="Cancel",
            )
            r = w.run()
            if not r.clicked:
                return
            raw = (r.text or "").strip()
            if not raw:
                return
            parts = [p.strip() for p in raw.split("|")]
            if len(parts) < 2:
                rumps.alert("Invalid", "Please include at least Name and URL separated by |")
                return
            name, url = parts[0], parts[1]
            lang = parts[2] if len(parts) >= 3 and parts[2] else "en-US"

            fid = f"custom_{_slugify(name)}"
            existing_ids = {f.get("id") for f in (self.cfg.custom_feeds or [])}
            if fid in existing_ids:
                fid = f"{fid}_{len(existing_ids) + 1}"

            self.cfg.custom_feeds = list(self.cfg.custom_feeds or []) + [
                {
                    "id": fid,
                    "name": name,
                    "url": url,
                    "country": "Custom",
                    "category": "Custom",
                    "language_tag": lang,
                }
            ]
            # Auto-select newly added feed.
            if fid not in self.cfg.selected_feed_ids:
                self.cfg.selected_feed_ids = list(self.cfg.selected_feed_ids) + [fid]

            save_config(self.cfg)
            self._rebuild_dynamic_menus()

        def _remove_custom_feed(self, sender):
            fid = getattr(sender, "_feed_id", None)
            if not fid:
                return
            self.cfg.custom_feeds = [f for f in (self.cfg.custom_feeds or []) if f.get("id") != fid]
            self.cfg.selected_feed_ids = [x for x in (self.cfg.selected_feed_ids or []) if x != fid]
            save_config(self.cfg)
            self._rebuild_dynamic_menus()

        @rumps.clicked("Install LaunchAgent")
        def on_install_launchagent(self, _):
            app_path = _guess_app_bundle_path()
            if not app_path:
                rumps.alert(
                    "Not packaged",
                    "Install LaunchAgent works best from the packaged MyNewsAlarm.app.\n\n"
                    "If you are running from source, build the app first (py2app) and reopen it.",
                )
                return

            self.cfg.installed_app_path = str(app_path)
            save_config(self.cfg)

            log_file = Path.home() / "Library" / "Logs" / "MyNewsAlarm" / "mynewsalarm.log"
            plist_path = install_launchagent(alarm_time=self.cfg.alarm_time, app_path=app_path, log_path=log_file)

            rc = _launchctl(["bootstrap", f"gui/{_os_getuid()}", str(plist_path)])
            if rc != 0:
                _launchctl(["load", str(plist_path)])

            rumps.alert("LaunchAgent installed", f"Label: {label()}\n\nPlist: {plist_path}")

        @rumps.clicked("Reinstall LaunchAgent")
        def on_reinstall_launchagent(self, _):
            app_path = _guess_app_bundle_path() or (
                Path(self.cfg.installed_app_path).expanduser().resolve() if self.cfg.installed_app_path else None
            )
            if not app_path or not app_path.exists():
                rumps.alert("App not found", "Could not find the installed app path. Build/open the packaged app first.")
                return
            log_file = Path.home() / "Library" / "Logs" / "MyNewsAlarm" / "mynewsalarm.log"
            plist_path = install_launchagent(alarm_time=self.cfg.alarm_time, app_path=app_path, log_path=log_file)
            _launchctl(["bootout", f"gui/{_os_getuid()}/{label()}"])
            rc = _launchctl(["bootstrap", f"gui/{_os_getuid()}", str(plist_path)])
            if rc != 0:
                _launchctl(["load", str(plist_path)])
            rumps.alert("LaunchAgent updated", f"Plist: {plist_path}")

        @rumps.clicked("Uninstall LaunchAgent")
        def on_uninstall_launchagent(self, _):
            _launchctl(["bootout", f"gui/{_os_getuid()}/{label()}"])
            _launchctl(["remove", label()])
            plist_path = uninstall_launchagent()
            rumps.alert("LaunchAgent removed", f"Plist: {plist_path}")

        @rumps.clicked("Open config folder")
        def on_open_config_folder(self, _):
            subprocess.run(["/usr/bin/open", str(config_path().parent)])

        @rumps.clicked("Open status file")
        def on_open_status(self, _):
            subprocess.run(["/usr/bin/open", str(config_path().parent / "status.json")])

        @rumps.clicked("Open log file")
        def on_open_log_file(self, _):
            log_file = Path.home() / "Library" / "Logs" / "MyNewsAlarm" / "mynewsalarm.log"
            subprocess.run(["/usr/bin/open", str(log_file)])

        @rumps.clicked("Quit")
        def on_quit(self, _):
            if self._is_running():
                self._cancel_event.set()
                stop_speaking(logger=self.logger)
            rumps.quit_application()

    MyNewsAlarmApp().run()


def main() -> int:
    parser = argparse.ArgumentParser(description="MyNewsAlarm menubar app")
    parser.add_argument("--run-once", action="store_true", help="Run once and exit (used by LaunchAgent).")
    args = parser.parse_args()

    if args.run_once:
        cfg = load_config()
        return int(run_once(cfg))

    run_ui()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
