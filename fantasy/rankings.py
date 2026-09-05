"""
Outside player rankings, with a safety net.

WHY THIS EXISTS
ESPN gives us its own projections for every player, and those are free and
always available. They are also mediocre. The fantasy community publishes
"consensus" rankings that average together dozens of expert opinions, and
those are meaningfully better at predicting who is actually worth drafting.

WHY IT IS BUILT DEFENSIVELY
Consensus rankings come from scraping a public web page, and scraping breaks
when a site changes its layout or blocks the request. Your draft is a bad
time to discover that. So this module has three layers, tried in order:

  1. Fetch fresh consensus rankings from FantasyPros.
  2. If that fails, reuse the last successful fetch from the local cache.
  3. If there is no cache either, return nothing and let the caller fall
     back to ESPN's own numbers.

Every code path reports which layer it used, so the cheat sheet always says
out loud where its numbers came from.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path

import requests

from .config import ROOT
from .names import normalize

CACHE_PATH = ROOT / "data" / "rankings_cache.json"

# FantasyPros publishes one cheat sheet page per scoring format.
DRAFT_URLS = {
    "ppr": "https://www.fantasypros.com/nfl/rankings/ppr-cheatsheets.php",
    "half-ppr": "https://www.fantasypros.com/nfl/rankings/half-point-ppr-cheatsheets.php",
    "standard": "https://www.fantasypros.com/nfl/rankings/consensus-cheatsheets.php",
}

# Weekly (in-season) rankings, used by the lineup optimizer later.
WEEKLY_URLS = {
    "ppr": "https://www.fantasypros.com/nfl/rankings/ppr-flex.php",
    "half-ppr": "https://www.fantasypros.com/nfl/rankings/half-point-ppr-flex.php",
    "standard": "https://www.fantasypros.com/nfl/rankings/flex.php",
}

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}


@dataclass
class RankedPlayer:
    """One player's consensus ranking."""
    name: str
    position: str
    team: str
    overall_rank: float          # 1 = best player available overall
    position_rank: str           # e.g. "RB4"
    tier: int                    # players in the same tier are ~interchangeable
    bye_week: int

    @property
    def key(self) -> str:
        return normalize(self.name, self.position)


@dataclass
class RankingsResult:
    players: list[RankedPlayer]
    source: str        # human readable description of where the data came from
    is_fresh: bool     # True only if we successfully fetched live data

    @property
    def index(self) -> dict[str, RankedPlayer]:
        out: dict[str, RankedPlayer] = {}
        for player in self.players:
            if player.key and player.key not in out:
                out[player.key] = player
        return out


def _extract_ecr_json(html: str) -> dict | None:
    """
    Pull the rankings JSON out of the page.

    FantasyPros renders its table with JavaScript from a variable that looks
    like:   var ecrData = { "players": [ ... ] };
    We find that assignment and read forward, counting braces, until the
    object closes. Regex alone cannot do this reliably because the JSON
    contains nested objects.
    """
    marker = re.search(r"(?:var|let|const)\s+ecrData\s*=\s*", html)
    if not marker:
        return None

    start = html.find("{", marker.end())
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(html)):
        ch = html[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _parse_players(payload: dict) -> list[RankedPlayer]:
    players: list[RankedPlayer] = []
    for row in payload.get("players", []) or []:
        name = (row.get("player_name") or "").strip()
        if not name:
            continue
        position = (row.get("player_position_id") or "").strip().upper()
        try:
            overall = float(row.get("rank_ecr") or 0)
        except (TypeError, ValueError):
            overall = 0.0
        if overall <= 0:
            continue
        try:
            tier = int(row.get("tier") or 0)
        except (TypeError, ValueError):
            tier = 0
        try:
            bye = int(row.get("player_bye_week") or 0)
        except (TypeError, ValueError):
            bye = 0

        players.append(
            RankedPlayer(
                name=name,
                position=position,
                team=(row.get("player_team_id") or "").strip().upper(),
                overall_rank=overall,
                position_rank=(row.get("pos_rank") or "").strip(),
                tier=tier,
                bye_week=bye,
            )
        )

    players.sort(key=lambda p: p.overall_rank)
    return players


def _read_cache(scoring_slug: str) -> RankingsResult | None:
    if not CACHE_PATH.exists():
        return None
    try:
        blob = json.loads(CACHE_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return None

    entry = blob.get(scoring_slug)
    if not entry or not entry.get("players"):
        return None

    age_hours = (time.time() - entry.get("fetched_at", 0)) / 3600
    players = [RankedPlayer(**row) for row in entry["players"]]
    return RankingsResult(
        players=players,
        source=f"cached FantasyPros consensus ({age_hours:.1f} hours old)",
        is_fresh=False,
    )


def _write_cache(scoring_slug: str, players: list[RankedPlayer]) -> None:
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        blob = {}
        if CACHE_PATH.exists():
            try:
                blob = json.loads(CACHE_PATH.read_text())
            except json.JSONDecodeError:
                blob = {}
        blob[scoring_slug] = {
            "fetched_at": time.time(),
            "players": [asdict(p) for p in players],
        }
        CACHE_PATH.write_text(json.dumps(blob, indent=1))
    except OSError:
        # A cache write failure must never break the actual tool.
        pass


def fetch_rankings(
    scoring_slug: str,
    kind: str = "draft",
    timeout: int = 20,
) -> RankingsResult:
    """
    Get consensus rankings for the given scoring format.

    scoring_slug: "ppr", "half-ppr" or "standard"
    kind:         "draft" (whole season) or "weekly" (this week only)

    Never raises. Worst case it returns an empty result with a source string
    explaining what went wrong.
    """
    urls = DRAFT_URLS if kind == "draft" else WEEKLY_URLS
    url = urls.get(scoring_slug, urls["ppr"])

    failure_reason = ""
    try:
        response = requests.get(url, headers=BROWSER_HEADERS, timeout=timeout)
        response.raise_for_status()
        payload = _extract_ecr_json(response.text)
        if payload is None:
            failure_reason = (
                "the page loaded but the rankings data block was not found "
                "(FantasyPros likely changed their page layout)"
            )
        else:
            players = _parse_players(payload)
            if players:
                _write_cache(f"{kind}:{scoring_slug}", players)
                return RankingsResult(
                    players=players,
                    source=f"live FantasyPros consensus ({len(players)} players, {scoring_slug})",
                    is_fresh=True,
                )
            failure_reason = "the rankings data block was empty"
    except requests.RequestException as exc:
        failure_reason = f"the request failed ({type(exc).__name__}: {exc})"

    cached = _read_cache(f"{kind}:{scoring_slug}")
    if cached:
        cached.source = f"{cached.source} -- live fetch failed because {failure_reason}"
        return cached

    return RankingsResult(
        players=[],
        source=f"UNAVAILABLE -- {failure_reason}; falling back to ESPN's own numbers",
        is_fresh=False,
    )
