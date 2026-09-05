#!/usr/bin/env python3
"""
Offline smoke test.

This runs the real draft board code against a FAKE league and FAKE rankings,
so we can verify the logic works without touching ESPN's servers. It is not a
substitute for the real connection test, it just proves the maths and the
report formatting are correct.

Run it any time you want to check nothing is broken, with no cookies needed.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("LEAGUE_ID", "999999")
os.environ.setdefault("SEASON_YEAR", "2026")
os.environ.setdefault("ESPN_S2", "fake_s2_for_offline_test")
os.environ.setdefault("SWID", "{FAKE-0000-0000-0000-000000000001}")

from fantasy.names import normalize                       # noqa: E402
from fantasy.rankings import RankedPlayer, RankingsResult  # noqa: E402
import scripts.draft_board as board                        # noqa: E402


# --------------------------------------------------------------------------
# Fake ESPN objects, shaped like the real espn_api ones
# --------------------------------------------------------------------------

class FakePlayer:
    def __init__(self, name, position, pro_team, projected=0.0, injury="ACTIVE"):
        self.name = name
        self.position = position
        self.proTeam = pro_team
        self.projected_total_points = projected
        self.injuryStatus = injury


class FakeTeam:
    def __init__(self, team_id, name, owner_swid=None, roster=None):
        self.team_id = team_id
        self.team_name = name
        self.roster = roster or []
        self.owners = [{"id": owner_swid, "displayName": name + " owner"}] if owner_swid else []


class FakePick:
    def __init__(self, team, player_name, round_num, round_pick):
        self.team = team
        self.playerName = player_name
        self.round_num = round_num
        self.round_pick = round_pick


class FakeSettings:
    name = "Test League of Testing"
    team_count = 12
    reg_season_count = 14
    playoff_team_count = 6
    faab = True
    position_slot_counts = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "RB/WR/TE": 1, "D/ST": 1, "K": 1, "BE": 7}
    scoring_format = [{"abbr": "REC", "label": "Each reception", "points": 0.5}]


class FakeLeague:
    def __init__(self, teams, picks, free_agents):
        self.settings = FakeSettings()
        self.teams = teams
        self.draft = picks
        self._free_agents = free_agents

    def refresh_draft(self, **kwargs):
        return None

    def free_agents(self, size=50, **kwargs):
        return self._free_agents[:size]


# --------------------------------------------------------------------------
# Build a scenario: 12 team league, mid round 3, I pick 3rd
# --------------------------------------------------------------------------

MY_SWID = "{FAKE-0000-0000-0000-000000000001}"

CONSENSUS = [
    ("Ja'Marr Chase", "WR", "CIN", 1, "WR1", 1, 10),
    ("Bijan Robinson", "RB", "ATL", 2, "RB1", 1, 5),
    ("Justin Jefferson", "WR", "MIN", 3, "WR2", 1, 6),
    ("Saquon Barkley", "RB", "PHI", 4, "RB2", 1, 9),
    ("CeeDee Lamb", "WR", "DAL", 5, "WR3", 2, 7),
    ("Jahmyr Gibbs", "RB", "DET", 6, "RB3", 2, 5),
    ("Amon-Ra St. Brown", "WR", "DET", 7, "WR4", 2, 5),
    ("Puka Nacua", "WR", "LAR", 8, "WR5", 2, 8),
    ("Malik Nabers", "WR", "NYG", 9, "WR6", 2, 14),
    ("Derrick Henry", "RB", "BAL", 10, "RB4", 3, 7),
    ("Brock Bowers", "TE", "LV", 11, "TE1", 1, 10),
    ("Nico Collins", "WR", "HOU", 12, "WR7", 3, 6),
    ("Ashton Jeanty", "RB", "LV", 13, "RB5", 3, 10),
    ("Trey McBride", "TE", "ARI", 14, "TE2", 2, 8),
    ("Josh Allen", "QB", "BUF", 15, "QB1", 1, 7),
    ("Lamar Jackson", "QB", "BAL", 16, "QB2", 1, 7),
    ("George Kittle", "TE", "SF", 17, "TE3", 3, 14),
    ("Bucky Irving", "RB", "TB", 18, "RB6", 4, 9),
    ("Jayden Daniels", "QB", "WAS", 19, "QB3", 2, 14),
    ("Marvin Harrison Jr.", "WR", "ARI", 20, "WR8", 4, 8),
    ("Chase Brown", "RB", "CIN", 21, "RB7", 4, 10),
    ("Sam LaPorta", "TE", "DET", 22, "TE4", 3, 5),
    ("Philadelphia Eagles", "DST", "PHI", 130, "DST1", 12, 9),
    ("Baltimore Ravens", "DST", "BAL", 135, "DST2", 12, 7),
    ("Brandon Aubrey", "K", "DAL", 150, "K1", 14, 7),
    ("Cameron Dicker", "K", "LAC", 155, "K2", 14, 12),
]

ranked_players = [
    RankedPlayer(name=n, position=p, team=t, overall_rank=r, position_rank=pr, tier=ti, bye_week=b)
    for (n, p, t, r, pr, ti, b) in CONSENSUS
]

# 26 picks have happened (12 team league -> we are in round 3, pick 3).
DRAFTED_NAMES = [c[0] for c in CONSENSUS[:26]][:26]
taken = [
    "Ja'Marr Chase", "Bijan Robinson", "Justin Jefferson", "Saquon Barkley",
    "CeeDee Lamb", "Jahmyr Gibbs", "Amon-Ra St. Brown", "Puka Nacua",
    "Malik Nabers", "Derrick Henry", "Brock Bowers", "Nico Collins",
    "Ashton Jeanty", "Trey McBride", "Josh Allen", "Lamar Jackson",
    "George Kittle", "Bucky Irving", "Jayden Daniels", "Marvin Harrison Jr.",
    "Chase Brown", "Sam LaPorta",
]

my_team = FakeTeam(3, "Design Dynasty", MY_SWID, roster=[
    FakePlayer("Justin Jefferson", "WR", "MIN", 285.0),
    FakePlayer("Derrick Henry", "RB", "BAL", 240.0),
])
other_teams = [FakeTeam(i, f"Team {i}") for i in range(1, 13) if i != 3]
teams = sorted([my_team] + other_teams, key=lambda t: t.team_id)
teams_by_id = {t.team_id: t for t in teams}

# Build a plausible snake pick log: 22 picks made.
picks = []
for i, player_name in enumerate(taken):
    round_num = i // 12 + 1
    pick_in_round = i % 12 + 1
    slot = pick_in_round if round_num % 2 == 1 else 12 - pick_in_round + 1
    picks.append(FakePick(teams_by_id[slot], player_name, round_num, pick_in_round))

free_agents = [
    FakePlayer(n, p, t, projected=float(300 - r), injury="QUESTIONABLE" if n == "Bucky Irving" else "ACTIVE")
    for (n, p, t, r, _pr, _ti, _b) in CONSENSUS
]

fake_league = FakeLeague(teams, picks, free_agents)


# --------------------------------------------------------------------------
# Patch the network-touching functions and run the real report
# --------------------------------------------------------------------------

board.connect = lambda config: fake_league
board.find_my_team = lambda league, config: my_team
board.fetch_rankings = lambda slug, kind="draft": RankingsResult(
    players=ranked_players,
    source=f"OFFLINE TEST FIXTURE ({slug})",
    is_fresh=True,
)


def assert_true(condition, message):
    if not condition:
        print(f"FAIL: {message}")
        sys.exit(1)
    print(f"  ok: {message}")


print("=" * 70)
print("Checking the pieces individually")
print("=" * 70)

drafted_keys, returned_picks = board.collect_drafted_keys(fake_league)
assert_true(normalize("Ja'Marr Chase", "WR") in drafted_keys, "drafted players are detected from the pick log")
assert_true(normalize("Bucky Irving", "RB") in drafted_keys, "22nd pick detected")
assert_true(normalize("Brandon Aubrey", "K") not in drafted_keys, "undrafted kicker is NOT marked as taken")

pos_info = board.draft_position_math(fake_league, my_team, picks)
assert_true(pos_info["picks_made"] == 22, f"picks_made == 22 (got {pos_info['picks_made']})")
assert_true(pos_info["current_round"] == 2, f"currently in round 2 (got {pos_info['current_round']})")
assert_true(pos_info["my_slot"] == 3, f"my draft slot detected as 3 (got {pos_info['my_slot']})")
# Slot 3 in a 12 team snake: picks 3, 22, 27, 46, ...
assert_true(
    pos_info["next_pick_overall"] == 27,
    f"snake math says my next pick is overall #27 (got {pos_info['next_pick_overall']})",
)
assert_true(
    pos_info["picks_until_my_turn"] == 4,
    f"4 picks until my turn (got {pos_info['picks_until_my_turn']})",
)

have, needs = board.roster_needs(fake_league, my_team)
assert_true(have.get("WR") == 1 and have.get("RB") == 1, "roster counted correctly")
need_text = " ".join(needs)
assert_true("QB" in need_text, "QB flagged as an unfilled slot")
assert_true("TE" in need_text, "TE flagged as an unfilled slot")
assert_true("RB" in need_text, "RB flagged (need 2, have 1)")

available = [p for p in ranked_players if p.key not in drafted_keys]
assert_true(len(available) == 4, f"4 players left in the fixture pool (got {len(available)})")
summary_te = board.tier_summary(available, "TE")
assert_true("none left" in summary_te, "all tight ends correctly shown as gone")
summary_dst = board.tier_summary(available, "DST")
assert_true("Tier 12" in summary_dst, f"defense tier reported (got: {summary_dst})")

print()
print("=" * 70)
print("Running the full report end to end")
print("=" * 70)
board.main()

output_file = ROOT / "output" / "draft-board.md"
assert_true(output_file.exists(), "report file was written to output/")
body = output_file.read_text()
assert_true("Best available overall" in body, "report contains the overall board")
assert_true("Positional urgency" in body, "report contains the tier urgency table")
assert_true("YOU ARE ON THE CLOCK" not in body, "correctly does NOT say you are on the clock")
assert_true("Ja'Marr Chase" not in body.split("Last 10 picks")[0], "drafted players excluded from the board")

print()
print("ALL OFFLINE CHECKS PASSED")
