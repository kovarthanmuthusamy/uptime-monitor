"""Test-session setup: give the whole suite a throwaway SQLite database.

This runs before any test module imports the app, so ``app.db`` builds its
engine against the temp file instead of a developer's real database.
"""

import os
import tempfile

_fd, _path = tempfile.mkstemp(prefix="uptime-test-", suffix=".db")
os.close(_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{_path}"
