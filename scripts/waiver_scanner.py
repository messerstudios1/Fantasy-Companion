#!/usr/bin/env python3
"""
PHASE 4: WAIVER WIRE SCANNER

Once a week, this looks at every unowned player and tells you which ones are
worth adding, and who on your roster is the weakest link they would replace.

WHAT "WAIVER WIRE" MEANS
Any player nobody in your league owns is a free agent. After each week's
games, the ones who did something interesting get claimed. Winning your
league is mostly about noticing those players one week before everyone else
does. That is what this scans for.

HOW IT DECIDES
See the long explanation at the top of fantasy/waivers.py. Short version:
it weights OPPORTUNITY (carries and targets, which coaches control and which
are stable) above PRODUCTION (fantasy points, which are distorted by
touchdown luck).

WHAT IT DOES NOT DO
It does not submit claims. Every ESPN call is a read. You place any claims
yourself on ESPN.

WHEN TO RUN IT
Tuesday is the sweet spot: after Monday night's game finishes, before most
leagues process waivers on Wednesday morning.
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
from fantasy.output import Report, fail
from fantasy.waivers import (
    SCAN_POSITIONS,
    canonical_position,
    score_group,
    suggest_faab_bid,
    summarize_recent,
)

# How many free agents to pull from ESPN. They come back sorted by how widely
# owned they are, so this covers everyone realistically worth considering.
POOL_SIZE = 250

# How many weeks back to judge recent form.
LOOKBACK_WEEKS = 3

# How many suggestions to show per position.
TOP_PER_POSITION = 6

# A free agent must beat one of your players by this much in recent points
# per game before we suggest the swap. Below this, churning your roster
# costs you more in noise than it gains.
SWAP_THRESHOLD_PPG = 2.0


def main() -> None:
    try:
        config = load_config()
    except ConfigError as exc:
        fail(str(exc), "waivers.md")
        return

    try:
        league = connect(config)
        my_team = find_my_team(league, config)
    except (AuthError, LeagueNotFoundError) as exc:
        fail(str(exc), "waivers.md")
        return

    week_override = (os.getenv("WEEK") or "").strip()
    week = int(week_override) if week_override.isdigit() else league.current_week

    scoring = describe_scoring(league)

    report = Report(f"Waiver Wire Scan: Week {week}")
    report.text(
        f"League: **{league.settings.name}**. Your team: **{my_team.team_name}**. "
        f"Scoring: {scoring['label']}."
    )

    if week <= 1:
        report.note(
            "It is week 1, so there is no game data to judge recent form from yet. "
            "Everything below is based on preseason projections and ownership only. "
            "This tool becomes genuinely useful after week 2 or 3."
        )

    # --- Pull the free agent pool ----------------------------------------
    try:
        free_agents = league.free_agents(size=POOL_SIZE)
    except Exception as exc:  # noqa: BLE001
        fail(
            f"Could not load the free agent list from ESPN.\n\n"
            f"({type(exc).__name__}: {exc})\n\n"
            "If this keeps happening, run the connection test first.",
            "waivers.md",
        )
        return

    # --- Score the free agents, position by position ----------------------
    by_position: dict[str, list] = {}
    for player in free_agents:
        position = canonical_position(getattr(player, "position", ""))
        if position not in SCAN_POSITIONS:
            continue
        by_position.setdefault(position, []).append(
            summarize_recent(player, week, LOOKBACK_WEEKS)
        )

    for trends in by_position.values():
        score_group(trends)

    # --- Score my own roster the same way, so comparisons are fair --------
    my_trends = [summarize_recent(p, week, LOOKBACK_WEEKS) for p in (my_team.roster or [])]
    my_by_position: dict[str, list] = {}
    for trend in my_trends:
        my_by_position.setdefault(trend.position, []).append(trend)

    # --- The headline: your weakest spots ---------------------------------
    report.heading("Your weakest roster spots", 2)
    report.text(
        "_These are the players on your roster producing the least over the last "
        f"{LOOKBACK_WEEKS} weeks. They are the ones a waiver add would replace._"
    )
    droppable = sorted(
        [t for t in my_trends if t.position in SCAN_POSITIONS],
        key=lambda t: (t.recent_ppg, t.opportunities_per_game),
    )[:6]
    report.table(
        ["Player", "Pos", f"Pts/game last {LOOKBACK_WEEKS}wk", "Touches/game", "Season avg", "Status"],
        [
            [
                t.name, t.position, t.recent_ppg, t.opportunities_per_game, t.season_ppg,
                t.injury_status.title() if t.injury_status not in ("", "ACTIVE", "NORMAL") else "healthy",
            ]
            for t in droppable
        ],
    )
    report.warning(
        "**Be careful dropping injured players.** A good player who is hurt but will "
        "return is usually worth more than the free agent replacing him. Only drop "
        "an injured player if he is on season-ending injured reserve or you are "
        "desperate for the roster spot this week."
    )

    # --- Concrete upgrade suggestions -------------------------------------
    report.heading("Suggested claims", 2)
    report.text(
        "_Each row is a specific upgrade: add the free agent, drop the player from "
        "your roster. Only swaps worth at least "
        f"{SWAP_THRESHOLD_PPG} points per game are listed, because smaller edges are "
        "inside the noise._"
    )

    suggestions = []
    for position, trends in by_position.items():
        mine = sorted(my_by_position.get(position, []), key=lambda t: t.recent_ppg)
        if not mine:
            continue
        weakest = mine[0]
        for candidate in sorted(trends, key=lambda t: -t.add_score)[:TOP_PER_POSITION]:
            gain = round(candidate.recent_ppg - weakest.recent_ppg, 1)
            if gain < SWAP_THRESHOLD_PPG:
                continue
            if candidate.injury_status in ("OUT", "INJURY_RESERVE", "SUSPENSION"):
                continue
            suggestions.append((gain, candidate, weakest))

    suggestions.sort(key=lambda row: -row[0])

    if not suggestions:
        report.note(
            "**No clear upgrades available this week.** Every free agent worth adding "
            "is no better than what you already have. Doing nothing is a legitimate "
            "and often correct move."
        )
    else:
        report.table(
            ["Add", "Pos", "Add score", "Pts/gm", "Touches/gm", "Drop", "Gain/gm", "Suggested FAAB bid"],
            [
                [
                    candidate.name,
                    candidate.position,
                    candidate.add_score,
                    candidate.recent_ppg,
                    candidate.opportunities_per_game,
                    weakest.name,
                    f"+{gain}",
                    suggest_faab_bid(candidate.add_score, candidate.percent_owned)
                    if league.settings.faab else "n/a, this league uses waiver priority",
                ]
                for gain, candidate, weakest in suggestions[:10]
            ],
        )

    # --- Full board by position -------------------------------------------
    report.heading("Best available free agents, by position", 2)
    report.text(
        "**Add score** blends two things, weighted 60/40:\n"
        "- **Opportunity** (60%): carries plus targets per game, versus other free "
        "agents at the same position. This is what coaches control, and it is the "
        "most stable predictor of future points.\n"
        "- **Production** (40%): actual fantasy points per game. Real, but noisy, "
        "because touchdowns bounce around.\n\n"
        "A high opportunity score with a low production score is the most "
        "interesting profile on this page. It means the usage is already there and "
        "the points have not caught up yet."
    )

    for position in SCAN_POSITIONS:
        trends = by_position.get(position, [])
        if not trends:
            continue
        top = sorted(trends, key=lambda t: -t.add_score)[:TOP_PER_POSITION]
        report.heading(position, 3)
        report.table(
            ["Player", "NFL", "Add score", "Opportunity", "Production", "Touches/gm", "Pts/gm", "Trend", "% owned", "Notes"],
            [
                [
                    t.name, t.pro_team, t.add_score,
                    t.opportunity_percentile, t.production_percentile,
                    t.opportunities_per_game, t.recent_ppg,
                    f"+{t.trend}" if t.trend > 0 else t.trend,
                    f"{t.percent_owned:.0f}%",
                    "; ".join(t.reasons) or "-",
                ]
                for t in top
            ],
        )

    report.note(
        "Nothing was claimed or dropped. This tool only reads from ESPN. "
        "Place any claims yourself on ESPN's site."
    )

    path = report.deliver("waivers.md")
    print(f"\nSaved to {path}")


if __name__ == "__main__":
    main()
