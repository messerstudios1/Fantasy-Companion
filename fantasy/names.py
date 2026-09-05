"""
Matching player names between two different websites.

This is boring but it is where these tools usually break. ESPN writes a name
one way ("Marvin Harrison Jr."), another site writes it another way
("Marvin Harrison"). Team defenses are worse: ESPN says "Eagles D/ST" while
ranking sites say "Philadelphia Eagles".

The approach here is deliberately simple and readable rather than clever:
squash both names down to a plain lowercase key and compare those.
"""

from __future__ import annotations

import re
import unicodedata

# Suffixes that one site includes and another drops.
_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}

# Every NFL team's nickname, used to match defenses regardless of how the
# site writes them. Key is the nickname, value is the canonical key we use.
NFL_NICKNAMES = [
    "cardinals", "falcons", "ravens", "bills", "panthers", "bears", "bengals",
    "browns", "cowboys", "broncos", "lions", "packers", "texans", "colts",
    "jaguars", "chiefs", "raiders", "chargers", "rams", "dolphins", "vikings",
    "patriots", "saints", "giants", "jets", "eagles", "steelers", "49ers",
    "seahawks", "buccaneers", "titans", "commanders",
]

DEFENSE_MARKERS = ("d/st", "dst", "defense", "d st")


def _strip_accents(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(ch)
    )


def is_defense(name: str, position: str = "") -> bool:
    lowered = name.lower()
    if position.upper() in {"D/ST", "DST", "DEF"}:
        return True
    return any(marker in lowered for marker in DEFENSE_MARKERS)


def normalize(name: str, position: str = "") -> str:
    """
    Turn a player name into a stable comparison key.

    "Marvin Harrison Jr." -> "marvinharrison"
    "Ken Walker III"      -> "kenwalker"
    "Eagles D/ST"         -> "dst:eagles"
    "Philadelphia Eagles" -> "dst:eagles"   (when flagged as a defense)
    """
    if not name:
        return ""

    text = _strip_accents(name).lower().strip()

    if is_defense(name, position):
        for nickname in NFL_NICKNAMES:
            if nickname in text:
                return f"dst:{nickname}"
        # Unknown defense: fall through to the generic path so we at least
        # produce a key rather than an empty string.

    # Drop anything that is not a letter, number or space.
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    parts = [p for p in text.split() if p and p not in _SUFFIXES]
    return "".join(parts)


def build_index(items, key_fn) -> dict:
    """
    Build a lookup dictionary from normalized name -> item.

    If two players normalize to the same key (rare, but it happens with
    common names), the first one wins and the second is skipped. That is
    safer than silently overwriting a higher-ranked player.
    """
    index: dict[str, object] = {}
    for item in items:
        key = key_fn(item)
        if key and key not in index:
            index[key] = item
    return index
