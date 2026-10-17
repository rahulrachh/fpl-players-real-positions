"""Application settings, read from environment variables only.

Every variable is listed in the root `.env.example`. Nothing here may hold a
machine-specific path: relative paths resolve against the backend directory.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ (the directory that contains the `app` package)
BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    # SQLite file. Relative paths are resolved against backend/.
    database_path: Path = Path("data/fpl.db")
    # Open the web app's connection with `immutable=1` (no locking, no journal
    # lookups). Only safe when nothing writes the file while the app runs,
    # e.g. on Vercel. Leave off locally so a running sync is seen.
    database_immutable: bool = False

    # Official FPL API (public, no login).
    fpl_api_base_url: str = "https://fantasy.premierleague.com/api"
    # TTL for the in-memory cache of live FPL calls.
    fpl_cache_ttl_seconds: float = Field(default=60.0, ge=0)
    # TTL for a team's gameweek once FPL has checked its points (data_checked):
    # that data never changes. Unfinished gameweeks use FPL_CACHE_TTL_SECONDS.
    fpl_finished_cache_ttl_seconds: float = Field(default=86400.0, ge=0)

    # Positions source (Sofascore), used only by offline scripts.
    # (api.sofascore.com answers 403; the www host works.)
    sofascore_api_base_url: str = "https://www.sofascore.com/api/v1"
    # Polite minimum delay between consecutive requests to the positions source.
    sofascore_request_delay_seconds: float = Field(default=2.5, ge=0)
    # Retries for 429 / 5xx / network errors, waiting backoff * 2^attempt
    # seconds (5, 10, 20 by default). A 403 is never retried.
    sofascore_max_retries: int = Field(default=3, ge=0)
    sofascore_backoff_seconds: float = Field(default=5.0, ge=0)

    # Position logic (`app/logic/`): a stored match is usable for a dot only
    # if its average is built from at least this many on-ball actions
    # (`points_count`); otherwise the player falls back to an earlier match.
    position_min_points_count: int = Field(default=1, ge=0)

    log_level: str = "INFO"

    @property
    def database_file(self) -> Path:
        path = self.database_path
        if not path.is_absolute():
            path = BACKEND_DIR / path
        return path.resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
