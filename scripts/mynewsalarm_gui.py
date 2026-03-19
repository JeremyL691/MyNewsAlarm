from __future__ import annotations

import sys
import threading
import queue
from pathlib import Path

import tkinter as tk
from tkinter import messagebox, simpledialog

# Import from installed/bundled package when available (PyInstaller).
# Fallback: allow running from a git checkout without installing.
try:
    from mynewsalarm_app.config import load_config, save_config, validate_alarm_time
    from mynewsalarm_app.run_once import run_once
    from mynewsalarm_app.speech import stop_speaking
except ModuleNotFoundError:
    PROJECT_DIR = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str((PROJECT_DIR / "src").resolve()))
    from mynewsalarm_app.config import load_config, save_config, validate_alarm_time
    from mynewsalarm_app.run_once import run_once
    from mynewsalarm_app.speech import stop_speaking


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("MyNewsAlarm")
        self.root.geometry("520x240")

        self.cfg = load_config()

        self._run_thread: threading.Thread | None = None
        self._cancel_event = threading.Event()
        self._ui_queue: queue.Queue[tuple[str, object]] = queue.Queue()

        # UI
        top = tk.Frame(root)
        top.pack(fill="x", padx=12, pady=10)

        self.status_var = tk.StringVar(value="Ready")
        tk.Label(top, textvariable=self.status_var, anchor="w").pack(fill="x")

        btns = tk.Frame(root)
        btns.pack(fill="x", padx=12, pady=8)

        tk.Button(btns, text="Run now", command=self.on_run_now, width=14).pack(side="left")
        tk.Button(btns, text="Stop speaking", command=self.on_stop_speaking, width=14).pack(side="left", padx=(8, 0))
        tk.Button(btns, text="Set alarm time…", command=self.on_set_alarm_time, width=14).pack(side="left", padx=(8, 0))
        tk.Button(btns, text="Quit", command=self.root.destroy, width=10).pack(side="right")

        helpf = tk.Frame(root)
        helpf.pack(fill="both", expand=True, padx=12, pady=(6, 10))

        msg = (
            "This is the desktop UI build (windowed).\n"
            "Use ‘Run now’ to fetch/summarize/speak.\n"
            "Use ‘Set alarm time…’ to update the LaunchAgent schedule used by install-alarm (CLI)."
        )
        tk.Label(helpf, text=msg, justify="left", anchor="nw").pack(fill="both", expand=True)

        # Poll UI queue
        self.root.after(200, self._drain_ui_queue)

    def _set_status(self, s: str) -> None:
        self.status_var.set(s)

    def _post_ui(self, kind: str, payload: object = None) -> None:
        self._ui_queue.put((kind, payload))

    def _drain_ui_queue(self) -> None:
        try:
            while True:
                kind, payload = self._ui_queue.get_nowait()
                if kind == "status":
                    self._set_status(str(payload))
                elif kind == "error":
                    messagebox.showerror("MyNewsAlarm", str(payload))
                elif kind == "done":
                    self._set_status("Done")
        except queue.Empty:
            pass
        self.root.after(200, self._drain_ui_queue)

    def on_stop_speaking(self) -> None:
        try:
            stop_speaking()
            self._set_status("Stopped")
        except Exception as e:
            self._post_ui("error", f"Failed to stop speaking: {e}")

    def on_set_alarm_time(self) -> None:
        current = getattr(self.cfg, "alarm_time", "08:00")
        txt = simpledialog.askstring("Alarm time", "Enter alarm time (HH:MM)", initialvalue=current)
        if txt is None:
            return
        try:
            hh, mm = validate_alarm_time(txt)
            self.cfg.alarm_time = f"{hh:02d}:{mm:02d}"
            save_config(self.cfg)
            self._set_status(f"Saved alarm time: {self.cfg.alarm_time}")
        except Exception as e:
            self._post_ui("error", f"Invalid time: {e}")

    def on_run_now(self) -> None:
        if self._run_thread and self._run_thread.is_alive():
            self._set_status("Already running…")
            return

        self._cancel_event.clear()
        self._set_status("Running…")

        def worker() -> None:
            try:
                # run_once already uses cfg fields; pass cancel event so it can stop between items
                run_once(self.cfg, cancel_event=self._cancel_event)
                self._post_ui("done")
            except Exception as e:
                self._post_ui("error", f"Run failed: {e}")
                self._post_ui("status", "Error")

        self._run_thread = threading.Thread(target=worker, daemon=True)
        self._run_thread.start()


def main() -> int:
    root = tk.Tk()
    App(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
