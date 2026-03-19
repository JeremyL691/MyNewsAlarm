# Contributing

Thanks for contributing to **MyNewsAlarm**.

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## Run

```bash
python scripts/mynewsalarm_ui.py
```

## Tests + lint

```bash
ruff check .
pytest
```

## Packaging (py2app)

```bash
python setup.py py2app
open dist/MyNewsAlarm.app
```

## Pull requests

- Keep changes focused and well-described.
- Add tests where it makes sense.
- Avoid adding new runtime dependencies unless they provide clear user value.
