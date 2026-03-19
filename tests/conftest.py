"""Pytest configuration.

Tests should run directly from a git checkout without requiring an editable install.
We add the project's ``src/`` directory to ``sys.path``.

On macOS, the system Python may be linked against LibreSSL. urllib3 v2 emits a
NotOpenSSLWarning in that environment; it's harmless for our unit tests but makes
output noisy.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure imports work from a git checkout without installing the package.
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str((project_root / "src").resolve()))

# Note: urllib3 may emit a NotOpenSSLWarning on macOS system Pythons linked
# against LibreSSL. We leave it visible here since it doesn't affect correctness.
