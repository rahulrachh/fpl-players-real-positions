"""Vercel deployment files: the `api/index.py` entrypoint and the root
`requirements.txt` the Python function is built from."""

import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent


def test_vercel_entrypoint_serves_the_app_read_only_and_immutable():
    # Run from the repo root in a fresh interpreter, as Vercel loads it.
    code = (
        "import runpy, sys; from fastapi.testclient import TestClient; "
        "app = runpy.run_path('api/index.py')['app']; "
        "body = TestClient(app).get('/api/health').json(); "
        "from app.db.engine import get_read_only_engine; "
        "url = str(get_read_only_engine().url); "
        "ok = body['database']['read_only'] and 'immutable=1' in url; "
        "bad = [m for m in sys.modules if m.startswith(('app.positions', 'app.sync', 'curl_cffi'))]; "
        "sys.exit(0 if ok and not bad else 1)"
    )
    env = {k: v for k, v in os.environ.items() if k != "DATABASE_IMMUTABLE"}
    assert subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env).returncode == 0


def test_requirements_match_the_lock_file():
    # Regenerate with (from backend/):
    #   uv export --no-default-groups --no-hashes --no-emit-project -o ../requirements.txt
    pins = dict(
        re.match(r"^([A-Za-z0-9_.-]+)(?:\[[^\]]*\])?==(\S+)", line).groups()
        for line in (ROOT / "requirements.txt").read_text().splitlines()
        if line and not line.startswith((" ", "#"))
    )
    lock = tomllib.loads((BACKEND / "uv.lock").read_text())
    locked = {p["name"]: p["version"] for p in lock["package"] if "version" in p}
    assert all(locked.get(name.lower()) == version for name, version in pins.items())

    project = tomllib.loads((BACKEND / "pyproject.toml").read_text())["project"]
    direct = {re.split(r"[\[<>=]", dep)[0].lower() for dep in project["dependencies"]}
    assert direct <= set(pins)
    # Offline-only and dev packages stay out of the web function.
    assert not {"curl-cffi", "rapidfuzz", "pytest"} & set(pins)
