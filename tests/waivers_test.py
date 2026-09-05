#!/usr/bin/env python3
"""
Offline tests for the waiver scanner logic. No ESPN connection needed.

The important thing being verified: that a player with heavy usage but few
points scores ABOVE a player with few touches who got lucky with touchdowns.
That is the whole point of the tool, and getting it backwards would give
consistently bad advice.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fantasy.waivers import (
    _percentile_ranks,
    score_group,
    suggest_faab_bid,
    summarize_recent,
)

PASSED = 0


def check(condition, message):
    global PASSED
    if not condition:
        print(f"FAIL: {message}")
        sys.exit(1)
    PASSED += 1
    print(f"  ok: {message}")


class FakePlayer:
    """Shaped like an espn_api BoxPlayer."""

    def __init__(self, name, position, weekly, percent_owned=5.0,
                 injury="ACTIVE", bye=False, avg_points=0.0):
        self.name = name
        self.position = position
        self.proTeam = "TST"
        self.percent_owned = percent_owned
        self.injuryStatus = injury
        self.on_bye_week = bye
        self.pro_opponent = "OPP"
        self.projected_total_points = 120.0
        self.avg_points = avg_points
        # weekly = {week: (points, targets, carries)}
        self.stats = {
            week: {
                "points": points,
                "breakdown": {"receivingTargets": targets, "rushingAttempts": carries},
            }
            for week, (points, targets, carries) in weekly.items()
        }


CURRENT_WEEK = 8  # so lookback of 3 covers weeks 5, 6, 7

print("=" * 70)
print("TEST 1: recent form is summarized from the right weeks")
print("=" * 70)

workhorse = FakePlayer(
    "Workhorse Back", "RB",
    weekly={
        4: (30.0, 0, 25),   # outside the lookback window, must be ignored
        5: (8.0, 2, 19),
        6: (7.5, 3, 21),
        7: (9.0, 1, 20),
        8: (0.0, 0, 0),     # current week, not yet played, must be ignored
    },
    avg_points=8.0,
)
t = summarize_recent(workhorse, CURRENT_WEEK, lookback=3)
check(t.games_counted == 3, f"counted exactly 3 games (got {t.games_counted})")
check(abs(t.recent_ppg - 8.2) < 0.05, f"points per game averaged correctly (got {t.recent_ppg})")
check(t.opportunities_per_game == 22.0,
      f"touches per game = (21+24+21)/3 = 22.0 (got {t.opportunities_per_game})")

print()
print("=" * 70)
print("TEST 2: usage is valued above touchdown luck")
print("=" * 70)

# Same recent points per game. One earns them from volume, one from two
# fluke touchdowns on almost no touches.
volume_guy = FakePlayer("Volume Guy", "RB", {5: (9.0, 3, 18), 6: (9.0, 2, 20), 7: (9.0, 4, 19)})
lucky_guy = FakePlayer("Lucky Guy", "RB", {5: (9.0, 1, 3), 6: (9.0, 0, 2), 7: (9.0, 1, 4)})
filler = [
    FakePlayer(f"Filler {i}", "RB", {5: (3.0, 1, 5), 6: (3.0, 1, 5), 7: (3.0, 1, 5)})
    for i in range(6)
]

group = [summarize_recent(p, CURRENT_WEEK) for p in [volume_guy, lucky_guy] + filler]
score_group(group)
scores = {t.name: t for t in group}

check(scores["Volume Guy"].recent_ppg == scores["Lucky Guy"].recent_ppg,
      "both players scored identical fantasy points per game")
check(scores["Volume Guy"].add_score > scores["Lucky Guy"].add_score,
      f"the high-usage player ranks higher ({scores['Volume Guy'].add_score} "
      f"vs {scores['Lucky Guy'].add_score})")
check(scores["Volume Guy"].opportunity_percentile > scores["Lucky Guy"].opportunity_percentile,
      "opportunity percentile separates them correctly")

print()
print("=" * 70)
print("TEST 3: the explanation strings fire on the right profiles")
print("=" * 70)

# A realistic pool: one heavily-used receiver with no points yet, one who
# scored a lot on almost no targets, and a spread of ordinary players in
# between so the percentiles have something real to rank against.
buy_low = FakePlayer("Buy Low", "WR", {5: (2.0, 11, 0), 6: (3.0, 12, 0), 7: (2.5, 10, 0)})
touchdown_fluke = FakePlayer("TD Fluke", "WR", {5: (15.0, 1, 0), 6: (16.0, 2, 0), 7: (14.0, 1, 0)})
ordinary = [
    FakePlayer(f"Ordinary {i}", "WR",
               {5: (6.0, 4 + i, 0), 6: (6.5, 4 + i, 0), 7: (5.5, 5 + i, 0)})
    for i in range(8)
]
group3 = [summarize_recent(p, CURRENT_WEEK) for p in [buy_low, touchdown_fluke] + ordinary]
score_group(group3)

buy_low_result = next(t for t in group3 if t.name == "Buy Low")
check("classic buy" in " ".join(buy_low_result.reasons),
      f"heavy usage with low output is labelled a buy (reasons: {buy_low_result.reasons})")

fluke_result = next(t for t in group3 if t.name == "TD Fluke")
check("regress" in " ".join(fluke_result.reasons),
      f"scoring without usage is labelled a regression risk (reasons: {fluke_result.reasons})")
check(buy_low_result.add_score > fluke_result.add_score,
      f"the buy-low profile outranks the fluke ({buy_low_result.add_score} vs {fluke_result.add_score})")

print()
print("=" * 70)
print("TEST 4: injured and bye-week players are flagged, not hidden")
print("=" * 70)

hurt = FakePlayer("Hurt Guy", "RB", {5: (12.0, 2, 15), 6: (11.0, 3, 14), 7: (10.0, 2, 16)}, injury="OUT")
bye = FakePlayer("Bye Guy", "RB", {5: (12.0, 2, 15), 6: (11.0, 3, 14), 7: (10.0, 2, 16)}, bye=True)
group4 = [summarize_recent(p, CURRENT_WEEK) for p in [hurt, bye, volume_guy, lucky_guy]]
score_group(group4)
hurt_result = next(t for t in group4 if t.name == "Hurt Guy")
bye_result = next(t for t in group4 if t.name == "Bye Guy")
check("Out" in " ".join(hurt_result.reasons), "an OUT player carries an injury note")
check("bye week" in " ".join(bye_result.reasons), "a bye week player carries a bye note")

print()
print("=" * 70)
print("TEST 5: edge cases do not crash")
print("=" * 70)

empty = FakePlayer("Never Played", "WR", {})
t5 = summarize_recent(empty, CURRENT_WEEK)
check(t5.games_counted == 0 and t5.recent_ppg == 0.0, "a player with no games returns zeros, no crash")
score_group([t5])
check("no recent game data" in " ".join(t5.reasons), "no-data players are labelled as such")

check(_percentile_ranks([]) == [], "percentile ranking of an empty list is safe")
check(_percentile_ranks([5.0]) == [50.0], "percentile ranking of a single player is 50")

check("18-25%" in suggest_faab_bid(90, 10), "an elite, unowned add gets an aggressive bid")
check("0-1%" in suggest_faab_bid(20, 2), "a marginal add gets a minimal bid")

print()
print(f"ALL {PASSED} WAIVER CHECKS PASSED")
