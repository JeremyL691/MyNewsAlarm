# MyNewsAlarm

A small macOS app (runs from source) that:

1) fetches your selected RSS feeds
2) summarizes items
3) reads them aloud using macOS **`say`**

No API keys required.

## Features

- Fetches RSS feeds, summarizes items, and reads them aloud using `say`
- Curated default feeds + **custom feed** support
- Per-language voice overrides (e.g., use a UK voice for `en-GB` feeds)
- Adjustable speech rate

## Requirements

- macOS
- Python **3.9+**

## Install (from source)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run (from source)

Windowed UI:

```bash
source .venv/bin/activate
python scripts/mynewsalarm_gui.py
```

(There is also a CLI for `run-once` / config inspection, see below.)

## Configuration & Logs

MyNewsAlarm stores its data in standard macOS locations:

- Config: `~/Library/Application Support/MyNewsAlarm/config.json`
- Last run status: `~/Library/Application Support/MyNewsAlarm/status.json`
- Logs (rotating): `~/Library/Logs/MyNewsAlarm/mynewsalarm.log`

## Using the UI

In the window:

- **Run now**: runs immediately (fetch + summarize + speak)
- **Stop speaking**: cancels the current run
- **Set alarm time…**: updates the stored `alarm_time` setting (used by the CLI scheduler if you choose to set one up)

### Tip: install better macOS voices

If you only see a few voices, macOS can download higher-quality voices:

System Settings → Accessibility → Spoken Content → System voice → Manage Voices.

(Community write-up: https://romanzipp.com/blog/get-tts-with-natural-voices-on-macos-without-external-tools)

## CLI (optional)

A small CLI is included for debugging:

```bash
./mynewsalarm validate-config
./mynewsalarm run-once
./mynewsalarm show-config
./mynewsalarm show-status
```

(App bundle packaging has been intentionally removed from this repo; users run from source.)

## License

MIT. See [LICENSE](LICENSE).
