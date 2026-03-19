"""Pytest path bootstrap for repository-level test execution."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER_SRC = ROOT / "server" / "src"

if str(SERVER_SRC) not in sys.path:
    sys.path.insert(0, str(SERVER_SRC))
