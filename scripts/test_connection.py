#!/usr/bin/env python3
"""
PHASE 1 TEST: prove we can talk to ESPN.

Run this first, and any time something stops working. It answers four
questions in order, and tells you exactly which one failed:

  1. Are the settings present?        (league ID, season, cookies)
  2. Will ESPN accept the cookies?    (this is what expires)
  3. Can we find YOUR team?
  4. Can we read your roster and the league's scoring rules?

It never changes anything in your league. It only reads.
"""

from __future__ import annotations

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
from fantasy.output import Report, fail


def main() -> None:
    report = Report("ESPN Connection Test")

    # --- Step 1: settings -------------------------------------------------
    try:
        config = load_config()
    except ConfigError as exc:
        fail(f"STEP 1 FAILED (settings)\n\n{exc}", "connection-test.md")
        return

    report.text(f"**Step 1 passed.** Settings loaded for league `{config.league_id}`, season {config.year}.")

    # --- Step 2: authentication ------------------------------------------
    try:
        league = connect(config)
    except (AuthError, LeagueNotFoundError) as exc:
        fail(f"STEP 2 FAILED (ESPN login)\n\n{exc}", "connection-test.md")
        return

    report.text(f"**Step 2 passed.** ESPN accepted the cookies. League name: **{league.settings.name}**")

    # --- Step 3: find your team ------------------------------------------
    try:
        my_team = find_my_team(league, config)
    except LeagueNotFoundError as exc:
        fail(f"STEP 3 FAILED (identifying your team)\n\n{exc}", "connection-test.md")
        return

    report.text(f"**Step 3 passed.** Your team is **{my_team.team_name}** (team ID {my_team.team_id}).")

    # --- Step 4: read the data -------------------------------------------
    scoring = describe_scoring(league)

    report.heading("League setup", 2)
    report.table(
        ["Setting", "Value"],
        [
            ["League name", league.settings.name],
            ["Season", config.year],
            ["Teams", league.settings.team_count],
            ["Scoring format", scoring["label"]],
            ["Points per reception", scoring["points_per_reception"]],
            ["Regular season length", f"{league.settings.reg_season_count} weeks"],
            ["Teams making playoffs", league.settings.playoff_team_count],
            ["Waiver budget (FAAB)", "Yes" if league.settings.faab else "No, priority order"],
        ],
    )

    slots = getattr(league.settings, "position_slot_counts", {}) or {}
    starting_slots = [(pos, count) for pos, count in slots.items() if count and pos not in ("BE", "IR")]
    bench = slots.get("BE", 0)
    report.heading("Roster slots", 2)
    report.text(
        "These are the positions you must fill each week. "
        "QB = quarterback, RB = running back, WR = wide receiver, TE = tight end, "
        "FLEX = any RB/WR/TE, D/ST = a whole team's defense, K = kicker, "
        "BE = bench (players you own but do not start)."
    )
    report.table(
        ["Slot", "How many"],
        [[pos, count] for pos, count in starting_slots] + [["BE (bench)", bench]],
    )

    report.heading(f"Your roster: {my_team.team_name}", 2)
    if not my_team.roster:
        report.note(
            "Your roster is empty. That is expected before your draft happens. "
            "Everything above still confirms the connection works."
        )
    else:
        rows = []
        for player in sorted(my_team.roster, key=lambda p: -(p.projected_total_points or 0)):
            rows.append([
                player.name,
                player.position,
                player.proTeam,
                player.injuryStatus or "ACTIVE",
                round(player.projected_total_points or 0, 1),
            ])
        report.table(
            ["Player", "Pos", "NFL team", "Injury status", "ESPN projected season points"],
            rows,
        )

    report.heading("All teams in the league", 2)
    report.table(
        ["Team ID", "Team name", "Owner"],
        [
            [
                team.team_id,
                team.team_name + ("  <-- YOU" if team.team_id == my_team.team_id else ""),
                ", ".join(
                    (o.get("displayName") or f"{o.get('firstName','')} {o.get('lastName','')}").strip()
                    for o in (team.owners or [])
                    if isinstance(o, dict)
                ) or "unknown",
            ]
            for team in league.teams
        ],
    )

    report.note("All four checks passed. The connection is working.")
    path = report.deliver("connection-test.md")
    print(f"\nSaved to {path}")


if __name__ == "__main__":
    main()
