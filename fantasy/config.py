"""
Loads your league settings and ESPN credentials.

Settings come from two places, deliberately separated by sensitivity:

  SECRET (cookies)      Never written to a file in this repository. They come
                        from GitHub's encrypted Secrets when running in
                        Actions, or from a local ".env" file (which .gitignore
                        blocks from ever being committed) when running on your
                        own machine.

  NOT SECRET (league    Committed to "league.json" at the project root. A
  id, team id, season)  league ID identifies a league but grants no access to
                        it, so there is nothing gained by hiding it, and
                        keeping it in the repo means one less thing to paste
                        into a settings page.

Environment variables win over league.json, so a workflow can point the tools
at a different season or league without anyone editing a file.
"""

from __future__ import annotations

import json
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
    team_id: int | None = None
    team_name: str | None = None

    @property
    def is_private(self) -> bool:
        return bool(self.espn_s2 and self.swid)


def _load_league_file() -> dict:
    """Read league.json if it exists. A missing or broken file is not fatal."""
    path = ROOT / "league.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


LEAGUE_FILE = _load_league_file()


def _setting(name: str) -> str:
    """
    Look a setting up, environment first, then league.json.

    Environment wins so that a workflow input or a one-off override always
    beats the committed default.
    """
    value = (os.getenv(name) or "").strip()
    if value:
        return value
    from_file = LEAGUE_FILE.get(name.lower())
    return str(from_file).strip() if from_file not in (None, "") else ""


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
    raw_league_id = _setting("LEAGUE_ID")
    if not raw_league_id:
        raise ConfigError(
            "Missing required setting: LEAGUE_ID\n"
            "\n"
            "  Normally this comes from 'league.json' in the project root.\n"
            "  If that file is missing, either restore it or set LEAGUE_ID as a\n"
            "  repository Secret under Settings -> Secrets and variables -> Actions.\n"
            "\n"
            "  Find the value in your ESPN league URL, after 'leagueId=':\n"
            "  https://fantasy.espn.com/football/team?leagueId=123456789"
        )
    try:
        league_id = int(raw_league_id)
    except ValueError:
        raise ConfigError(
            f"LEAGUE_ID must be a number, but got '{raw_league_id}'.\n"
            f"  Find it in your ESPN league URL, the part after 'leagueId=':\n"
            f"  https://fantasy.espn.com/football/league?leagueId=123456789"
        ) from None

    raw_year = _setting("SEASON_YEAR")
    if not raw_year:
        raise ConfigError(
            "Missing required setting: SEASON_YEAR (for example: 2026).\n"
            "  Normally this comes from 'league.json' in the project root."
        )
    try:
        year = int(raw_year)
    except ValueError:
        raise ConfigError(f"SEASON_YEAR must be a number, but got '{raw_year}'.") from None

    espn_s2 = _require("ESPN_S2")
    swid = _normalize_swid(_require("SWID"))

    raw_team_id = _setting("TEAM_ID")
    try:
        team_id = int(raw_team_id) if raw_team_id else None
    except ValueError:
        team_id = None

    team_name = (os.getenv("TEAM_NAME") or "").strip() or None

    OUTPUT_DIR.mkdir(exist_ok=True)

    return Config(
        league_id=league_id,
        year=year,
        espn_s2=espn_s2,
        swid=swid,
        team_id=team_id,
        team_name=team_name,
    )
