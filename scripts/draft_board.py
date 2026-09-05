#!/usr/bin/env python3
"""
PHASE 2: LIVE DRAFT CHEAT SHEET

Run this during your draft, as often as you like. Each run:

  1. Asks ESPN which players have already been taken (updates in real time
     as picks happen).
  2. Loads consensus expert rankings.
  3. Subtracts the taken players from the rankings.
  4. Shows you what is left, ordered best to worst, overall and by position.
  5. Tells you what your own roster still needs.

It does NOT make picks for you. You click picks on ESPN's site; this is the
list you look at while you do.

--- A QUICK GLOSSARY, since you said you do not follow football ---

  QB   Quarterback. Throws the ball. You start exactly one, usually.
  RB   Running back. Runs the ball. Scarce, so they go early.
  WR   Wide receiver. Catches the ball. Deep position, lots of good ones.
  TE   Tight end. Catches the ball but blocks too. Very top-heavy: a few
       great ones, then a long flat wasteland.
  FLEX A roster slot you can fill with any RB, WR, or TE.
  K    Kicker. Kicks field goals. Nearly random week to week. Draft last.
  D/ST A whole team's defense counted as one fantasy "player". Also close
       to random. Draft second to last.

  BYE WEEK  Every NFL team takes one week off during the season. If a player
       is on bye, he scores zero. You want your roster spread across
       different bye weeks so you are never left with nobody to start.

  TIER  Experts group players into tiers where everyone inside a tier is
       roughly equally good. This is the single most useful draft concept:
       if 5 players remain in a tier, you can wait. If 1 remains, take him
       now or lose that entire quality level.

  ADP  Average Draft Position. Where a player typically gets picked. If a
       player's consensus rank is far better than his ADP, he is a value.
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
from fantasy.names import normalize
from fantasy.output import Report, fail
from fantasy.rankings import fetch_rankings

# How many players to show in each section.
TOP_OVERALL = 30
TOP_PER_POSITION = 10

# The positions we build separate lists for, in draft-relevance order.
POSITIONS = ["RB", "WR", "TE", "QB", "K", "DST"]

# ESPN and FantasyPros disagree on what to call a team defense.
POSITION_ALIASES = {"D/ST": "DST", "DEF": "DST", "PK": "K"}


def canonical_position(position: str) -> str:
    position = (position or "").strip().upper()
    return POSITION_ALIASES.get(position, position)


def collect_drafted_keys(league) -> tuple[set[str], list]:
    """
    Work out every player who is already off the board.

    Two independent sources, unioned together, because either one can lag
    during a live draft:
      - league.draft: the official pick log.
      - every team's roster: who ESPN currently shows as owned.
    """
    drafted: set[str] = set()

    picks = list(getattr(league, "draft", []) or [])
    for pick in picks:
        key = normalize(getattr(pick, "playerName", "") or "")
        if key:
            drafted.add(key)

    for team in league.teams:
        for player in team.roster or []:
            key = normalize(player.name, canonical_position(player.position))
            if key:
                drafted.add(key)

    return drafted, picks


def build_espn_index(league) -> dict:
    """
    Pull ESPN's own player data so we can show injury status and ESPN's
    projection next to each consensus ranking.

    If this fails (it can, before a draft starts), we carry on without it.
    """
    index: dict[str, object] = {}
    try:
        pool = league.free_agents(size=500)
    except Exception:  # noqa: BLE001 - never let enrichment break the board
        return index

    for player in pool:
        key = normalize(player.name, canonical_position(player.position))
        if key and key not in index:
            index[key] = player
    return index


def draft_position_math(league, my_team, picks) -> dict:
    """
    Snake draft arithmetic.

    In a snake draft the order reverses every round: if there are 12 teams
    and you pick 3rd, you pick 3rd in round 1, then 10th in round 2, then
    3rd in round 3, and so on. That means after an early pick you wait a
    long time, so you need to plan two picks ahead, not one.
    """
    team_count = league.settings.team_count or len(league.teams)
    picks_made = len(picks)

    info = {
        "team_count": team_count,
        "picks_made": picks_made,
        "current_round": picks_made // team_count + 1,
        "current_pick_in_round": picks_made % team_count + 1,
        "my_slot": None,
        "next_pick_overall": None,
        "picks_until_my_turn": None,
    }

    # Find my draft slot from round 1 of the pick log.
    for pick in picks:
        if getattr(pick, "round_num", None) == 1:
            team = getattr(pick, "team", None)
            if team is not None and getattr(team, "team_id", None) == my_team.team_id:
                info["my_slot"] = getattr(pick, "round_pick", None)
                break

    slot = info["my_slot"]
    if slot:
        # Walk forward through rounds until we find my next pick.
        for round_num in range(1, 21):
            if round_num % 2 == 1:
                pick_in_round = slot
            else:
                pick_in_round = team_count - slot + 1
            overall = (round_num - 1) * team_count + pick_in_round
            if overall > picks_made:
                info["next_pick_overall"] = overall
                info["picks_until_my_turn"] = overall - picks_made - 1
                break

    return info


def roster_needs(league, my_team) -> tuple[dict, list[str]]:
    """
    Compare what your roster holds against what the league requires you to
    start each week, and report the gaps.
    """
    slots = dict(getattr(league.settings, "position_slot_counts", {}) or {})
    slots.pop("BE", None)
    slots.pop("IR", None)

    have: dict[str, int] = {}
    for player in my_team.roster or []:
        pos = canonical_position(player.position)
        have[pos] = have.get(pos, 0) + 1

    needs: list[str] = []
    for slot, count in slots.items():
        if not count:
            continue
        slot_key = canonical_position(slot)
        if slot_key in ("RB/WR/TE", "FLEX", "OP", "RB/WR"):
            continue
        owned = have.get(slot_key, 0)
        if owned < count:
            needs.append(f"{slot_key} (need {count}, have {owned})")

    return have, needs


def tier_summary(available_ranked, position: str) -> str:
    """
    Say how urgent this position is, using tiers.

    Plain terms: everyone in a tier is roughly the same quality. If the best
    remaining tier still has plenty of players in it, you can safely draft a
    different position and come back. If it is down to its last one or two,
    that quality level is about to vanish.
    """
    at_position = [p for p in available_ranked if canonical_position(p.position) == position]
    if not at_position:
        return "none left"

    best_tier = at_position[0].tier
    if not best_tier:
        return f"{len(at_position)} available"

    same_tier = [p for p in at_position if p.tier == best_tier]
    count = len(same_tier)
    if count == 1:
        return f"**Tier {best_tier}: only 1 left. Last chance at this quality.**"
    if count <= 3:
        return f"**Tier {best_tier}: {count} left. Getting thin.**"
    return f"Tier {best_tier}: {count} left. No rush."


def main() -> None:
    try:
        config = load_config()
    except ConfigError as exc:
        fail(str(exc), "draft-board.md")
        return

    try:
        league = connect(config)
    except (AuthError, LeagueNotFoundError) as exc:
        fail(str(exc), "draft-board.md")
        return

    # Always re-pull the draft log so a refresh mid-draft sees the newest picks.
    try:
        league.refresh_draft(refresh_teams=True)
    except Exception:  # noqa: BLE001 - a stale draft log is better than a crash
        pass

    try:
        my_team = find_my_team(league, config)
    except LeagueNotFoundError as exc:
        fail(str(exc), "draft-board.md")
        return

    scoring = describe_scoring(league)
    drafted, picks = collect_drafted_keys(league)
    espn_index = build_espn_index(league)
    rankings = fetch_rankings(scoring["slug"], kind="draft")
    position_info = draft_position_math(league, my_team, picks)

    report = Report(f"Draft Board: {league.settings.name}")

    # --- Where the numbers came from -------------------------------------
    if rankings.is_fresh:
        report.note(f"Rankings source: {rankings.source}. Scoring: {scoring['label']}.")
    elif rankings.players:
        report.warning(
            f"Using cached rankings, not live ones. {rankings.source}. "
            "The list below is still usable, just possibly a few hours stale."
        )
    else:
        report.warning(
            f"Consensus rankings unavailable. {rankings.source} "
            "Falling back to ESPN's own projections, which are noticeably worse. "
            "The board still works."
        )

    # --- Draft state ------------------------------------------------------
    report.heading("Where the draft stands", 2)
    state_rows = [
        ["Picks made so far", position_info["picks_made"]],
        ["Current round", position_info["current_round"]],
        ["Pick in this round", f"{position_info['current_pick_in_round']} of {position_info['team_count']}"],
    ]
    if position_info["my_slot"]:
        state_rows.append(["Your draft slot", f"#{position_info['my_slot']} of {position_info['team_count']}"])
    if position_info["next_pick_overall"]:
        waiting = position_info["picks_until_my_turn"]
        state_rows.append(["Your next pick", f"overall #{position_info['next_pick_overall']}"])
        state_rows.append([
            "Picks until your turn",
            "**YOU ARE ON THE CLOCK**" if waiting == 0 else f"{waiting}",
        ])
    report.table(["", ""], state_rows)

    if position_info["picks_made"] == 0:
        report.text("_The draft has not started yet, so everyone below is available._")

    # --- Your roster and what it still needs ------------------------------
    have, needs = roster_needs(league, my_team)
    report.heading(f"Your roster so far ({len(my_team.roster or [])} players)", 2)
    if my_team.roster:
        report.table(
            ["Player", "Pos", "NFL team"],
            [[p.name, canonical_position(p.position), p.proTeam] for p in my_team.roster],
        )
    else:
        report.text("_Empty. Nothing drafted yet._")

    report.text("**Starting slots you have not filled yet:** " + (", ".join(needs) if needs else "none, all covered"))
    report.text(
        "_Reminder: filling a slot is not the same as filling it well. "
        "Needing a position does not mean you should reach for a bad player at it._"
    )

    # --- The actual board -------------------------------------------------
    if rankings.players:
        available = [p for p in rankings.players if p.key not in drafted]
        source_label = "consensus rank"
    else:
        # ESPN fallback: build pseudo-rankings from ESPN projections.
        class _EspnRanked:
            def __init__(self, player, rank):
                self.name = player.name
                self.position = canonical_position(player.position)
                self.team = player.proTeam
                self.overall_rank = rank
                self.position_rank = ""
                self.tier = 0
                self.bye_week = 0
                self.key = normalize(player.name, self.position)

        pool = sorted(espn_index.values(), key=lambda p: -(p.projected_total_points or 0))
        available = [
            _EspnRanked(p, i + 1)
            for i, p in enumerate(pool)
            if normalize(p.name, canonical_position(p.position)) not in drafted
        ]
        source_label = "ESPN projection rank"

    def row_for(ranked, show_pos: bool = True):
        espn_player = espn_index.get(ranked.key)
        injury = ""
        projection = ""
        if espn_player is not None:
            status = (espn_player.injuryStatus or "").upper()
            if status and status not in ("ACTIVE", "NORMAL"):
                injury = status.title()
            projection = round(espn_player.projected_total_points or 0, 1)
        cells = [
            int(ranked.overall_rank),
            ranked.name,
        ]
        if show_pos:
            cells.append(canonical_position(ranked.position))
        cells += [
            ranked.team or "-",
            ranked.position_rank or "-",
            ranked.tier or "-",
            ranked.bye_week or "-",
            projection if projection != "" else "-",
            injury or "-",
        ]
        return cells

    headers_overall = [source_label, "Player", "Pos", "NFL", "Pos rank", "Tier", "Bye", "ESPN proj", "Injury"]
    headers_position = [source_label, "Player", "NFL", "Pos rank", "Tier", "Bye", "ESPN proj", "Injury"]

    report.heading(f"Best available overall (top {TOP_OVERALL})", 2)
    report.text("_This is the list to look at when you have no strong positional need. Take the top name._")
    report.table(headers_overall, [row_for(p) for p in available[:TOP_OVERALL]])

    report.heading("Positional urgency", 2)
    report.text(
        "_Read this before picking. It tells you which positions are about to "
        "fall off a cliff and which can safely wait._"
    )
    report.table(
        ["Position", "Best remaining tier", "Total available"],
        [
            [
                pos,
                tier_summary(available, pos),
                len([p for p in available if canonical_position(p.position) == pos]),
            ]
            for pos in POSITIONS
        ],
    )

    for pos in POSITIONS:
        at_pos = [p for p in available if canonical_position(p.position) == pos][:TOP_PER_POSITION]
        if not at_pos:
            continue
        report.heading(f"Best available: {pos}", 3)
        report.table(headers_position, [row_for(p, show_pos=False) for p in at_pos])

    # --- Recent picks, so you can sanity check the board is live ----------
    if picks:
        report.heading("Last 10 picks (proof this board is current)", 2)
        recent = picks[-10:]
        report.table(
            ["Round", "Pick", "Player", "Drafted by"],
            [
                [
                    getattr(p, "round_num", "?"),
                    getattr(p, "round_pick", "?"),
                    getattr(p, "playerName", "?"),
                    getattr(getattr(p, "team", None), "team_name", "?"),
                ]
                for p in recent
            ],
        )

    path = report.deliver("draft-board.md")
    print(f"\nSaved to {path}")


if __name__ == "__main__":
    main()
