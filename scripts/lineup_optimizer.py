#!/usr/bin/env python3
"""
PHASE 3: WEEKLY LINEUP OPTIMIZER

Once a week, before games start, this compares your bench against your
starters and tells you if you are leaving points on the table.

WHAT IT DOES
  1. Reads your current lineup for the week from ESPN.
  2. Reads every player's projected points for that week.
  3. Overrides those projections to zero for anyone on a bye week or ruled
     OUT, because those players cannot score.
  4. Works out the highest scoring legal lineup you could set.
  5. Shows you the difference, as a plain list of swaps.

WHAT IT DOES NOT DO
  It does not change your lineup. It cannot. Every ESPN call here is a read.
  You make the swaps yourself on ESPN's site or app.

WHEN TO RUN IT
  Sunday morning is the useful time, because that is after Saturday's injury
  reports are final but before the early games lock. Running it earlier in
  the week is still informative, just less reliable.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fantasy.config import ConfigError, load_config
from fantasy.espn_client import (
    AuthError,
    LeagueNotFoundError,
    connect,
    describe_scoring,
    find_my_team,
)
from fantasy.lineup import (
    NON_STARTING_SLOTS,
    Candidate,
    diff_lineups,
    optimize,
    total_projected,
)
from fantasy.export import write_json
from fantasy.output import Report, fail

# Below this many projected points, a swap is not worth the risk of being
# wrong. Projections are not precise enough to act on tiny differences.
MEANINGFUL_GAIN = 1.0


def build_candidates(box_players) -> list[Candidate]:
    candidates = []
    for player in box_players:
        candidates.append(
            Candidate(
                name=player.name,
                position=(player.position or "").upper(),
                current_slot=player.slot_position or "BE",
                projected=float(getattr(player, "projected_points", 0) or 0),
                injury_status=(getattr(player, "injuryStatus", "") or "").upper(),
                on_bye=bool(getattr(player, "on_bye_week", False)),
                opponent=getattr(player, "pro_opponent", "") or "-",
                opponent_rank=int(getattr(player, "pro_pos_rank", 0) or 0),
            )
        )
    return candidates


def find_my_box_lineup(league, my_team, week):
    """Locate my team inside this week's matchups and return my player list."""
    for box in league.box_scores(week):
        if getattr(box.home_team, "team_id", None) == my_team.team_id:
            return box.home_lineup, box.away_team, box.home_projected
        if getattr(box.away_team, "team_id", None) == my_team.team_id:
            return box.away_lineup, box.home_team, box.away_projected
    return None, None, None


def main() -> None:
    try:
        config = load_config()
    except ConfigError as exc:
        fail(str(exc), "lineup.md", json_name="lineup")
        return

    try:
        league = connect(config)
        my_team = find_my_team(league, config)
    except (AuthError, LeagueNotFoundError) as exc:
        fail(str(exc), "lineup.md", json_name="lineup")
        return

    week_override = (os.getenv("WEEK") or "").strip()
    week = int(week_override) if week_override.isdigit() else league.current_week

    lineup, opponent_team, my_projected_total = find_my_box_lineup(league, my_team, week)
    if not lineup:
        fail(
            f"Could not find a week {week} matchup for {my_team.team_name}.\n"
            "\n"
            "This normally means the week has not been scheduled yet, or the\n"
            "season has not started. Try setting WEEK to a week that has a\n"
            "game scheduled.",
            "lineup.md",
            json_name="lineup",
        )
        return

    scoring = describe_scoring(league)
    candidates = build_candidates(lineup)

    current_starters = [c for c in candidates if c.current_slot not in NON_STARTING_SLOTS]
    current_bench = [c for c in candidates if c.current_slot in NON_STARTING_SLOTS]
    current_total = round(sum(c.effective_projection for c in current_starters), 2)

    slot_counts = dict(getattr(league.settings, "position_slot_counts", {}) or {})
    optimal, optimal_bench = optimize(candidates, slot_counts)
    optimal_total = total_projected(optimal)
    gain = round(optimal_total - current_total, 2)

    report = Report(f"Week {week} Lineup: {my_team.team_name}")
    report.text(
        f"Opponent this week: **{getattr(opponent_team, 'team_name', 'unknown')}**. "
        f"Scoring: {scoring['label']}."
    )

    # --- The headline -----------------------------------------------------
    to_bench, to_start = diff_lineups(current_starters, optimal)

    if gain < MEANINGFUL_GAIN:
        report.note(
            f"**Your lineup is already optimal, or close enough.** "
            f"The best possible change is worth {gain} projected points, which is "
            f"inside the margin of error on these projections. Leave it alone."
        )
    else:
        report.warning(
            f"**{len(to_start)} change(s) recommended, worth about {gain} projected points.** "
            f"Currently projected {current_total}, best possible {optimal_total}."
        )
        report.heading("Make these swaps", 2)
        rows = []
        for i in range(max(len(to_bench), len(to_start))):
            out_player = to_bench[i] if i < len(to_bench) else None
            in_player = to_start[i] if i < len(to_start) else None
            rows.append([
                f"{out_player.name} ({out_player.position})" if out_player else "-",
                f"{out_player.effective_projection:.1f}" if out_player else "-",
                f"{in_player.name} ({in_player.position})" if in_player else "-",
                f"{in_player.effective_projection:.1f}" if in_player else "-",
                (in_player.flag() or out_player.flag() if out_player else "") if in_player else "",
            ])
        report.table(["Bench this player", "Proj", "Start this player", "Proj", "Why"], rows)
        report.text(
            "_These are shown as pairs for readability. On ESPN you move players "
            "one at a time; the pairing does not have to be exact, you just need "
            "to end up with the recommended starters below._"
        )

    # --- Urgent problems --------------------------------------------------
    broken = [c for c in current_starters if c.on_bye or c.is_out]
    if broken:
        report.warning(
            "**You are currently starting " + str(len(broken)) +
            " player(s) who will score exactly zero.** Fix this before kickoff:\n> "
            + "\n> ".join(f"- {c.name} ({c.position}): {c.flag()}" for c in broken)
        )

    questionable = [
        c for c in current_starters
        if c.injury_status.upper() == "QUESTIONABLE" and not c.on_bye
    ]
    if questionable:
        report.note(
            "**Check these before kickoff.** They are listed as questionable, which "
            "means the team decides shortly before the game whether they play:\n> "
            + "\n> ".join(f"- {c.name} ({c.position})" for c in questionable)
        )

    # --- The recommended lineup ------------------------------------------
    report.heading("Recommended starting lineup", 2)
    report.table(
        ["Slot", "Player", "Pos", "Projected", "Opponent", "Status"],
        [
            [
                slot,
                player.name if player else "**EMPTY, no eligible player**",
                player.position if player else "-",
                f"{player.effective_projection:.1f}" if player else "0.0",
                player.opponent if player else "-",
                (player.flag() or "healthy") if player else "-",
            ]
            for slot, player in optimal
        ],
    )
    report.text(f"**Total projected: {optimal_total}**")

    report.heading("Bench under the recommended lineup", 2)
    report.table(
        ["Player", "Pos", "Projected", "Opponent", "Status"],
        [
            [c.name, c.position, f"{c.effective_projection:.1f}", c.opponent, c.flag() or "healthy"]
            for c in sorted(optimal_bench, key=lambda c: -c.effective_projection)
        ],
    )

    report.heading("What you have set right now", 2)
    report.table(
        ["Slot", "Player", "Pos", "Projected", "Status"],
        [
            [c.current_slot, c.name, c.position, f"{c.effective_projection:.1f}", c.flag() or "healthy"]
            for c in sorted(current_starters, key=lambda c: c.current_slot)
        ],
    )
    report.text(f"**Total projected: {current_total}**")

    report.note(
        "Nothing was changed in your league. This tool only reads. "
        "Make any swaps yourself on ESPN."
    )

    # --- Emit the same data as JSON for the web dashboard ----------------
    def json_candidate(candidate, slot=None):
        return {
            "slot": slot if slot is not None else candidate.current_slot,
            "name": candidate.name,
            "position": candidate.position,
            "projected": round(candidate.effective_projection, 1),
            "raw_projection": round(float(candidate.projected or 0), 1),
            "opponent": candidate.opponent,
            "injury": candidate.injury_status.title() if candidate.injury_status not in ("", "ACTIVE", "NORMAL") else "",
            "on_bye": candidate.on_bye,
            "flag": candidate.flag(),
        }

    write_json("lineup", {
        "ok": True,
        "league_name": league.settings.name,
        "team_name": my_team.team_name,
        "opponent_name": getattr(opponent_team, "team_name", ""),
        "scoring": scoring["label"],
        "week": week,
        "current_total": current_total,
        "optimal_total": optimal_total,
        "gain": gain,
        "is_optimal": gain < MEANINGFUL_GAIN,
        "swaps": [
            {
                "out": json_candidate(to_bench[i]) if i < len(to_bench) else None,
                "in": json_candidate(to_start[i]) if i < len(to_start) else None,
            }
            for i in range(max(len(to_bench), len(to_start)))
        ],
        "zero_point_starters": [json_candidate(c) for c in broken],
        "questionable_starters": [json_candidate(c) for c in questionable],
        "recommended": [json_candidate(c, slot) for slot, c in optimal if c],
        "empty_slots": [slot for slot, c in optimal if not c],
        "recommended_bench": [
            json_candidate(c) for c in sorted(optimal_bench, key=lambda c: -c.effective_projection)
        ],
        "current": [
            json_candidate(c) for c in sorted(current_starters, key=lambda c: c.current_slot)
        ],
    })

    path = report.deliver("lineup.md")
    print(f"\nSaved to {path}")


if __name__ == "__main__":
    main()
