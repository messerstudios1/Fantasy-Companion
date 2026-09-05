#!/usr/bin/env python3
"""
Offline tests for the lineup optimizer. No ESPN connection needed.

These prove the maths, especially the two things most likely to cost you
real points: correctly handling the FLEX slot, and refusing to start a
player who is on a bye week or ruled out.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fantasy.lineup import Candidate, diff_lineups, optimize, total_projected

PASSED = 0


def check(condition, message):
    global PASSED
    if not condition:
        print(f"FAIL: {message}")
        sys.exit(1)
    PASSED += 1
    print(f"  ok: {message}")


def player(name, pos, proj, slot="BE", injury="ACTIVE", bye=False):
    return Candidate(
        name=name, position=pos, current_slot=slot, projected=proj,
        injury_status=injury, on_bye=bye, opponent="OPP", opponent_rank=15,
    )


SLOTS = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "RB/WR/TE": 1, "D/ST": 1, "K": 1, "BE": 6}

print("=" * 70)
print("TEST 1: basic optimization picks the highest projections")
print("=" * 70)

roster = [
    player("Star QB", "QB", 22.0),
    player("Backup QB", "QB", 14.0),
    player("RB One", "RB", 18.0),
    player("RB Two", "RB", 15.0),
    player("RB Three", "RB", 12.0),
    player("WR One", "WR", 17.0),
    player("WR Two", "WR", 14.0),
    player("WR Three", "WR", 13.0),
    player("TE One", "TE", 11.0),
    player("TE Two", "TE", 6.0),
    player("Kicker", "K", 8.0),
    player("Defense", "D/ST", 7.0),
]

assignments, bench = optimize(roster, SLOTS)
by_slot = {}
for slot, cand in assignments:
    by_slot.setdefault(slot, []).append(cand.name if cand else None)

check(by_slot["QB"] == ["Star QB"], "starts the better quarterback")
check(sorted(by_slot["RB"]) == ["RB One", "RB Two"], "starts the two best running backs")
check(sorted(by_slot["WR"]) == ["WR One", "WR Two"], "starts the two best receivers")
check(by_slot["TE"] == ["TE One"], "starts the better tight end")
# FLEX should take the best remaining RB/WR/TE: WR Three (13.0) beats RB Three (12.0)
check(by_slot["RB/WR/TE"] == ["WR Three"], "FLEX correctly takes WR Three (13.0) over RB Three (12.0)")
check(total_projected(assignments) == 22.0 + 18 + 15 + 17 + 14 + 11 + 13 + 8 + 7,
      f"total is the true maximum (got {total_projected(assignments)})")
check("Backup QB" in [c.name for c in bench], "backup QB is benched")

print()
print("=" * 70)
print("TEST 2: a player on a bye week is never started")
print("=" * 70)

roster2 = [
    player("Star QB", "QB", 22.0),
    player("Elite RB ON BYE", "RB", 21.0, bye=True),   # highest projection, but on bye
    player("RB Two", "RB", 15.0),
    player("RB Three", "RB", 12.0),
    player("WR One", "WR", 17.0),
    player("WR Two", "WR", 14.0),
    player("WR Three", "WR", 13.0),
    player("TE One", "TE", 11.0),
    player("Kicker", "K", 8.0),
    player("Defense", "D/ST", 7.0),
]
assignments2, bench2 = optimize(roster2, SLOTS)
started2 = [c.name for _s, c in assignments2 if c]
check("Elite RB ON BYE" not in started2,
      "the 21-point projection is ignored because he is on a bye week")
check("RB Two" in started2 and "RB Three" in started2,
      "the two healthy running backs start instead")

print()
print("=" * 70)
print("TEST 3: a player ruled OUT is never started")
print("=" * 70)

roster3 = list(roster)
roster3[2] = player("RB One", "RB", 18.0, injury="OUT")
assignments3, _ = optimize(roster3, SLOTS)
started3 = [c.name for _s, c in assignments3 if c]
check("RB One" not in started3, "a player ruled OUT is benched despite a high projection")
check("RB Three" in started3, "the next healthy running back is promoted")

print()
print("=" * 70)
print("TEST 4: the swap list matches what actually changed")
print("=" * 70)

# Someone has set a deliberately bad lineup: benching WR One, starting WR Three.
bad_lineup = [
    player("Star QB", "QB", 22.0, slot="QB"),
    player("RB One", "RB", 18.0, slot="RB"),
    player("RB Two", "RB", 15.0, slot="RB"),
    player("WR Three", "WR", 13.0, slot="WR"),
    player("WR Two", "WR", 14.0, slot="WR"),
    player("TE Two", "TE", 6.0, slot="TE"),
    player("RB Three", "RB", 12.0, slot="RB/WR/TE"),
    player("Kicker", "K", 8.0, slot="K"),
    player("Defense", "D/ST", 7.0, slot="D/ST"),
    player("WR One", "WR", 17.0, slot="BE"),
    player("TE One", "TE", 11.0, slot="BE"),
    player("Backup QB", "QB", 14.0, slot="BE"),
]
optimal4, _ = optimize(bad_lineup, SLOTS)
current_starters = [c for c in bad_lineup if c.current_slot not in ("BE", "IR")]
to_bench, to_start = diff_lineups(current_starters, optimal4)

bench_names = {c.name for c in to_bench}
start_names = {c.name for c in to_start}
check("WR One" in start_names, "recommends starting the benched 17-point receiver")
check("TE One" in start_names, "recommends starting the benched 11-point tight end")
check("TE Two" in bench_names, "recommends benching the 6-point tight end")
check(len(to_bench) == len(to_start), "every player benched is replaced by one started")

current_total = sum(c.effective_projection for c in current_starters)
check(total_projected(optimal4) > current_total,
      f"optimal ({total_projected(optimal4)}) beats current ({current_total})")

print()
print("=" * 70)
print("TEST 5: an empty slot is reported rather than silently skipped")
print("=" * 70)

thin = [
    player("Star QB", "QB", 22.0),
    player("RB One", "RB", 18.0),
    player("RB Two", "RB", 15.0),
    player("WR One", "WR", 17.0),
    player("WR Two", "WR", 14.0),
    player("Kicker", "K", 8.0),
    player("Defense", "D/ST", 7.0),
]  # no tight end at all
assignments5, _ = optimize(thin, SLOTS)
te_slot = [c for s, c in assignments5 if s == "TE"]
check(te_slot == [None], "TE slot reports as empty when you own no tight end")

print()
print(f"ALL {PASSED} LINEUP CHECKS PASSED")
