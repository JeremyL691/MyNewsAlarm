from __future__ import annotations

import subprocess
import threading

from .config import AppConfig

_lock = threading.Lock()
_current_proc: subprocess.Popen[str] | None = None


def stop_speaking(logger=None) -> None:
    """Best-effort: stop the current `/usr/bin/say` process."""
    global _current_proc
    with _lock:
        proc = _current_proc
        _current_proc = None

    if not proc:
        return

    try:
        if proc.poll() is None:
            proc.terminate()
    except Exception as e:
        if logger:
            logger.info(f"Failed to terminate say: {e}")


def speak_text(cfg: AppConfig, text: str, logger, voice: str | None = None) -> None:
    text = (text or "").strip()
    if not text:
        return

    cmd: list[str] = ["/usr/bin/say"]

    final_voice = voice or cfg.default_voice
    if final_voice:
        cmd += ["-v", final_voice]
    if cfg.say_rate:
        cmd += ["-r", str(int(cfg.say_rate))]

    cmd.append(text)

    logger.info("Speaking via say")

    global _current_proc
    with _lock:
        # If something is already speaking, stop it first.
        if _current_proc and _current_proc.poll() is None:
            try:
                _current_proc.terminate()
            except Exception:
                pass
        _current_proc = subprocess.Popen(cmd, text=True)
        proc = _current_proc

    try:
        proc.wait()
    except Exception as e:
        logger.info(f"say failed: {e}")
    finally:
        with _lock:
            if _current_proc is proc:
                _current_proc = None
