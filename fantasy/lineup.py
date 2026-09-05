"""
Working out the best possible starting lineup.

THE PROBLEM IN PLAIN TERMS
Each week your league makes you start a fixed set of positions: one
quarterback, two running backs, and so on. Everyone else sits on your bench
and scores nothing. So every week you have one decision to make: which of
your players go in the starting slots.

THE COMPLICATION
Most slots accept exactly one position, but a "FLEX" slot accepts a running
back, a wide receiver, OR a tight end. That flexibility is what makes this
slightly more than "start your highest projected player at each position".

THE ALGORITHM
Fill the pickiest slots first, then the flexible ones. Concretely: sort the
slots by how many positions they accept, then walk through them filling each
with the highest projected player still available.

This is genuinely optimal here, not just a decent guess, because the slots
nest cleanly: FLEX accepts a superset of what RB, WR and TE accept. Under
that structure, whichever specific RB you put in the RB slot versus the FLEX
slot does not change the total, so filling the narrow slots first can never
paint you into a corner.
"""

from __future__ import annotations

from dataclasses import dataclass

# Which player positions each lineup slot will accept.
SLOT_ELIGIBILITY: dict[str, set[str]] = {
    "QB": {"QB"},
    "RB": {"RB"},
    "WR": {"WR"},
    "TE": {"TE"},
    "K": {"K"},
    "D/ST": {"D/ST"},
    "RB/WR": {"RB", "WR"},
    "WR/TE": {"WR", "TE"},
    "RB/WR/TE": {"RB", "WR", "TE"},
    "FLEX": {"RB", "WR", "TE"},
    "OP": {"QB", "RB", "WR", "TE"},
    "SUPERFLEX": {"QB", "RB", "WR", "TE"},
}

# Slots that are not part of your starting lineup.
NON_STARTING_SLOTS = {"BE", "IR", "ER", ""}

# Injury designations, worst first. "OUT" means he is definitely not playing.
INJURY_SEVERITY = {
    "OUT": 4,
    "INJURY_RESERVE": 4,
    "SUSPENSION": 4,
    "DOUBTFUL": 3,
    "QUESTIONABLE": 2,
    "PROBABLE": 1,
    "ACTIVE": 0,
    "NORMAL": 0,
    "": 0,
}

INJURY_PLAIN_ENGLISH = {
    "OUT": "will not play this week",
    "INJURY_RESERVE": "on injured reserve, will not play",
    "SUSPENSION": "suspended, will not play",
    "DOUBTFUL": "unlikely to play (roughly 25% chance)",
    "QUESTIONABLE": "might play, decided close to kickoff (roughly 50/50)",
    "PROBABLE": "expected to play",
}


@dataclass
class Candidate:
    """One player being considered for a lineup slot."""
    name: str
    position: str
    current_slot: str
    projected: float
    injury_status: str
    on_bye: bool
    opponent: str
    opponent_rank: int

    @property
    def is_out(self) -> bool:
        return INJURY_SEVERITY.get(self.injury_status.upper(), 0) >= 4

    @property
    def effective_projection(self) -> float:
        """
        The number we actually optimize against.

        Two hard overrides on top of ESPN's projection:
          - A player on a bye week is not playing at all, so he scores zero.
          - A player ruled OUT is not playing, so he scores zero.

        ESPN usually zeroes these itself, but not always, and starting a
        player who cannot play is the single most expensive mistake available
        in fantasy football. So we enforce it rather than trusting the feed.
        """
        if self.on_bye or self.is_out:
            return 0.0
        return max(0.0, float(self.projected or 0.0))

    def flag(self) -> str:
        if self.on_bye:
            return "BYE WEEK, scores 0"
        status = self.injury_status.upper()
        if status in INJURY_PLAIN_ENGLISH:
            return INJURY_PLAIN_ENGLISH[status]
        return ""


def expand_slots(slot_counts: dict[str, int]) -> list[str]:
    """
    Turn {"RB": 2, "WR": 2, "FLEX": 1} into a flat list of slots to fill:
    ["RB", "RB", "WR", "WR", "FLEX"].
    """
    slots: list[str] = []
    for slot, count in (slot_counts or {}).items():
        if slot in NON_STARTING_SLOTS:
            continue
        if slot not in SLOT_ELIGIBILITY:
            continue
        slots.extend([slot] * int(count or 0))
    return slots


def optimize(candidates: list[Candidate], slot_counts: dict[str, int]) -> tuple[list[tuple[str, Candidate]], list[Candidate]]:
    """
    Assign players to starting slots to maximize total projected points.

    Returns (assignments, bench) where assignments is a list of
    (slot_name, player) pairs.
    """
    slots = expand_slots(slot_counts)

    # Pickiest slots first. Ties broken by name so results are reproducible.
    slots.sort(key=lambda s: (len(SLOT_ELIGIBILITY[s]), s))

    remaining = sorted(
        candidates,
        key=lambda c: (-c.effective_projection, c.name),
    )

    assignments: list[tuple[str, Candidate]] = []
    used: set[int] = set()

    for slot in slots:
        eligible_positions = SLOT_ELIGIBILITY[slot]
        for i, candidate in enumerate(remaining):
            if i in used:
                continue
            if candidate.position in eligible_positions:
                assignments.append((slot, candidate))
                used.add(i)
                break
        else:
            # No eligible player left for this slot. Rare, but it happens if
            # your whole tight end room is on bye and you own no others.
            assignments.append((slot, None))

    bench = [c for i, c in enumerate(remaining) if i not in used]

    # Present starters in a sensible reading order rather than algorithm order.
    display_order = ["QB", "RB", "WR", "TE", "RB/WR", "WR/TE", "RB/WR/TE", "FLEX", "OP", "SUPERFLEX", "D/ST", "K"]
    assignments.sort(key=lambda pair: (display_order.index(pair[0]) if pair[0] in display_order else 99))

    return assignments, bench


def total_projected(assignments: list[tuple[str, Candidate]]) -> float:
    return round(sum(c.effective_projection for _slot, c in assignments if c), 2)


def diff_lineups(current_starters: list[Candidate], optimal: list[tuple[str, Candidate]]) -> tuple[list[Candidate], list[Candidate]]:
    """
    Work out what actually needs to change: who to bench, who to start.
    """
    current_names = {c.name for c in current_starters}
    optimal_names = {c.name for _s, c in optimal if c}

    to_bench = [c for c in current_starters if c.name not in optimal_names]
    to_start = [c for _s, c in optimal if c and c.name not in current_names]

    to_bench.sort(key=lambda c: c.effective_projection)
    to_start.sort(key=lambda c: -c.effective_projection)
    return to_bench, to_start
