# MyNewsAlarm

A fast, lightweight macOS app that automatically fetches, summarizes, and reads your news aloud—entirely on your machine.

```
RSS Feeds → Summarization → Text-to-Speech
```

No API keys. No cloud dependency. No subscriptions.

## ✨ Features

- **Fast parallel fetching**: Fetch multiple RSS feeds concurrently (up to 5 in parallel by default)
- **Smart deduplication**: Automatically removes duplicate stories across feeds
- **Intelligent summarization**: Extracts key sentences from articles, configurable length
- **Multi-language voices**: Per-language voice overrides (UK English voice for `en-GB`, etc.)
- **Connection pooling**: Efficient HTTP connection reuse across all feeds
- **Curated default feeds** + **custom feed support**
- **Adjustable speech rate** and voice selection
- **Rotating logs** for debugging
- **Status tracking**: See details of your last run (duration, items read, feed errors)

## Requirements

- **macOS** (10.13+)
- **Python 3.9+**

## Installation

```bash
# Clone the repository
git clone https://github.com/JeremyL691/MyNewsAlarm.git
cd MyNewsAlarm

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Quick Start

### GUI (Recommended)

```bash
source .venv/bin/activate
python scripts/mynewsalarm_gui.py
```

In the window:
- **Run now**: Fetch feeds, summarize, and read aloud
- **Stop speaking**: Cancel the current briefing
- **Set alarm time…**: Configure when your daily briefing runs
- **Settings**: Customize feeds, voices, summary length, and more

### CLI

For automation or debugging:

```bash
source .venv/bin/activate

./mynewsalarm run-once          # Fetch, summarize, and speak
./mynewsalarm validate-config   # Check config validity
./mynewsalarm show-config       # Display current settings
./mynewsalarm show-status       # View last run details
```

## Configuration

MyNewsAlarm stores settings and logs in standard macOS locations:

- **Config**: `~/Library/Application Support/MyNewsAlarm/config.json`
- **Status**: `~/Library/Application Support/MyNewsAlarm/status.json`
- **Logs**: `~/Library/Logs/MyNewsAlarm/mynewsalarm.log`

### Key Settings

Edit `config.json` to customize:

```json
{
  "alarm_time": "07:30",
  "max_items": 10,
  "summary_sentences": 4,
  "min_sentence_length": 25,
  "default_voice": "Daniel",
  "say_rate": 200,
  "dedup_enabled": true,
  "use_article_full_text": true,
  "max_parallel_feeds": 5,
  "selected_feed_ids": ["us_top_npr", "uk_top_bbc"],
  "voice_by_language": {
    "en-GB": "Daniel",
    "en-AU": "Karen"
  }
}
```

| Setting | Default | Description |
|---------|---------|-------------|
| `max_items` | 10 | Maximum news items to read (3–20) |
| `summary_sentences` | 4 | Number of sentences per summary |
| `min_sentence_length` | 25 | Minimum character length for a sentence |
| `dedup_enabled` | true | Skip duplicate stories across feeds |
| `use_article_full_text` | true | Fetch full article if RSS summary is empty |
| `max_parallel_feeds` | 5 | Number of feeds to fetch concurrently |
| `default_voice` | (macOS default) | Voice for reading (e.g., "Daniel", "Samantha") |
| `say_rate` | (macOS default) | Speech rate in words per minute |

## Default Feeds

MyNewsAlarm includes curated feeds from:

- **🇺🇸 United States**: NPR, AP, NYT, The Verge, Ars Technica
- **🇬🇧 United Kingdom**: BBC News
- **🇨🇦 Canada**: CBC
- **🇦🇺 Australia**: ABC
- **🌍 International**: Reuters World News

See [config.py](src/mynewsalarm_app/config.py) for the full list.

## Tips

### 🎙️ Better Voice Quality

macOS includes high-quality voices that aren't installed by default:

**System Settings** → **Accessibility** → **Spoken Content** → **System voice** → **Manage Voices**

Download English variants: `Daniel` (UK), `Karen` (Australian), `Fiona` (Irish).

[More info](https://romanzipp.com/blog/get-tts-with-natural-voices-on-macos-without-external-tools)

### ⏰ Automated Daily Briefing

To run your briefing automatically every morning, install the LaunchAgent:

```bash
source .venv/bin/activate
python scripts/mynewsalarm_gui.py
# Click "Install LaunchAgent" in the menu
```

Or manually:

```bash
cp templates/com.openclaw.mynewsalarm.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.openclaw.mynewsalarm.plist
```

### 🔧 Custom Feeds

Add RSS feeds to your config:

```json
{
  "custom_feeds": [
    {
      "id": "my_company_blog",
      "name": "My Company Blog",
      "url": "https://example.com/feed.xml",
      "language_tag": "en-US"
    }
  ],
  "selected_feed_ids": ["us_top_npr", "my_company_blog"]
}
```

## Performance

- **Parallel fetching**: Fetches up to 5 feeds simultaneously (configurable)
- **Connection pooling**: HTTP connections are reused
- **Smart parsing**: Uses `lxml` for fast HTML parsing
- **Efficient filtering**: Deduplication prevents redundant processing

A typical 10-feed fetch + summarization takes **~2–5 seconds**.

## Project Structure

```
MyNewsAlarm/
├── src/mynewsalarm_app/
│   ├── news.py           # RSS fetching, deduplication, parallel processing
│   ├── summarize.py      # Text extraction and summarization
│   ├── speech.py         # macOS text-to-speech integration
│   ├── config.py         # Configuration and status management
│   ├── run_once.py       # Main orchestration logic
│   └── logging_utils.py  # Logging setup
├── scripts/
│   ├── mynewsalarm_gui.py   # Windowed UI (PyQt/Rumps)
│   └── mynewsalarm_ui.py    # UI components
├── tests/                # Unit tests
├── templates/            # LaunchAgent template
└── requirements.txt      # Python dependencies
```

## Development

### Running Tests

```bash
pip install -r requirements-dev.txt
pytest
```

### Linting

```bash
ruff check src/
```

## Contributing

Contributions welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for recent updates.

## License

MIT. See [LICENSE](LICENSE) for details.

---

**Questions?** Open an issue on [GitHub](https://github.com/JeremyL691/MyNewsAlarm).
