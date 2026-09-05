"""
Loads your league settings and ESPN credentials.

Nothing sensitive is stored in this file. Values come from either:
  1. A local ".env" file (used when running on your own machine), or
  2. Environment variables (used when running inside GitHub Actions,
     where the values come from encrypted repository Secrets).

Both paths end up in the same place, so the rest of the code never has to
care where the credentials came from.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Project root = the folder this repo lives in.
ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"

# Load .env if it exists. On GitHub Actions there is no .env file, and that is
# fine: load_dotenv simply does nothing and we fall back to real env vars.
load_dotenv(ROOT / ".env")


class ConfigError(Exception):
    """Raised when a required setting is missing or malformed."""


@dataclass
class Config:
    league_id: int
    year: int
    espn_s2: str
    swid: str
    team_name: str | None = None

    @property
    def is_private(self) -> bool:
        return bool(self.espn_s2 and self.swid)


def _require(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value or value.startswith("paste_your") or value.startswith("{paste-"):
        raise ConfigError(
            f"Missing required setting: {name}\n"
            f"\n"
            f"  If you are running this on your own computer, open the file '.env' "
            f"in the project folder and set {name}.\n"
            f"  If this is running in GitHub Actions, add {name} as a repository "
            f"Secret under Settings -> Secrets and variables -> Actions.\n"
            f"\n"
            f"  The README section 'Getting your ESPN cookies' has step by step "
            f"instructions with no terminal required."
        )
    return value


def _normalize_swid(raw: str) -> str:
    """
    ESPN's SWID cookie is a GUID wrapped in curly braces, like {ABC-DEF-...}.
    People commonly paste it without the braces. Add them back so the API
    call works either way.
    """
    swid = raw.strip().strip('"').strip("'")
    if not swid.startswith("{"):
        swid = "{" + swid
    if not swid.endswith("}"):
        swid = swid + "}"
    return swid


def load_config() -> Config:
    """Read settings from the environment and sanity check them."""
    raw_league_id = _require("LEAGUE_ID")
    try:
        league_id = int(raw_league_id)
    except ValueError:
        raise ConfigError(
            f"LEAGUE_ID must be a number, but got '{raw_league_id}'.\n"
            f"  Find it in your ESPN league URL, the part after 'leagueId=':\n"
            f"  https://fantasy.espn.com/football/league?leagueId=123456789"
        ) from None

    raw_year = (os.getenv("SEASON_YEAR") or "").strip()
    if not raw_year:
        raise ConfigError("Missing required setting: SEASON_YEAR (for example: 2026)")
    try:
        year = int(raw_year)
    except ValueError:
        raise ConfigError(f"SEASON_YEAR must be a number, but got '{raw_year}'.") from None

    espn_s2 = _require("ESPN_S2")
    swid = _normalize_swid(_require("SWID"))

    team_name = (os.getenv("TEAM_NAME") or "").strip() or None

    OUTPUT_DIR.mkdir(exist_ok=True)

    return Config(
        league_id=league_id,
        year=year,
        espn_s2=espn_s2,
        swid=swid,
        team_name=team_name,
    )
