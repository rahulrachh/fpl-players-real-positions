"""Vercel entrypoint: serves the FastAPI app in `backend/app` as one Python
function. `vercel.json` rewrites every `/api/*` request here (the app sees the
original path) and bundles `backend/app` and `backend/data/fpl.db` with it.

Nothing writes the bundled database on Vercel, so it is opened with
`immutable=1` unless the environment says otherwise.
"""

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("DATABASE_IMMUTABLE", "true")

from app.main import app  # noqa: E402

__all__ = ["app"]
