"""
Deciding who is worth picking up off the free agent pool.

THE FOOTBALL IDEA BEHIND THIS, IN PLAIN TERMS
Not every unowned player is equally likely to be good next week. The single
most predictive thing you can look at is OPPORTUNITY: how many times the
coaching staff actually gives the player the ball.

  - For a running back, that is CARRIES (rushing attempts).
  - For a receiver or tight end, that is TARGETS (passes thrown his way,
    whether he catches them or not).

Opportunity matters more than recent fantasy points because points are
heavily distorted by touchdowns, and touchdowns are close to random week to
week. A player who got 18 carries and scored zero touchdowns had a good week
in the only sense you can predict from. A player who got 3 carries and
happened to score twice did not.

So this module scores free agents on two things and shows both separately:

  OPPORTUNITY  How much the coaches are using him lately.
  PRODUCTION   How many fantasy points that actually turned into.

A player high on opportunity but low on production is the classic buy: the
usage is real, the points will follow. A player high on production but low
on opportunity is the classic trap: he got lucky and will regress.

WHAT WE CANNOT SEE
ESPN's API does not expose snap counts (the percentage of his team's plays a
player was on the field for). That is a genuinely useful metric and we simply
do not have access to it. Carries and targets are the closest available
substitute, and they are most of the value anyway.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Stat keys as espn-api names them.
TARGETS_KEY = "receivingTargets"
CARRIES_KEY = "rushingAttempts"
RECEPTIONS_KEY = "receivingReceptions"

# Positions worth scanning. Kickers and defenses are close to random week to
# week, so churning them is mostly wasted effort.
SCAN_POSITIONS = ["RB", "WR", "TE", "QB"]

POSITION_ALIASES = {"D/ST": "DST", "DEF": "DST", "PK": "K"}


def canonical_position(position: str) -> str:
    position = (position or "").strip().upper()
    return POSITION_ALIASES.get(position, position)


@dataclass
class PlayerTrend:
    """Recent usage and production for one player."""
    name: str
    position: str
    pro_team: str
    percent_owned: float
    injury_status: str
    on_bye: bool
    opponent: str
    season_projection: float

    games_counted: int = 0
    recent_points: float = 0.0
    recent_opportunities: float = 0.0
    season_ppg: float = 0.0

    opportunity_percentile: float = 0.0
    production_percentile: float = 0.0
    add_score: float = 0.0
    reasons: list[str] = field(default_factory=list)

    @property
    def recent_ppg(self) -> float:
        if not self.games_counted:
            return 0.0
        return round(self.recent_points / self.games_counted, 1)

    @property
    def opportunities_per_game(self) -> float:
        if not self.games_counted:
            return 0.0
        return round(self.recent_opportunities / self.games_counted, 1)

    @property
    def trend(self) -> float:
        """Positive means he has been better lately than his season average."""
        if not self.games_counted or not self.season_ppg:
            return 0.0
        return round(self.recent_ppg - self.season_ppg, 1)


def summarize_recent(player, current_week: int, lookback: int = 3) -> PlayerTrend:
    """
    Roll up a player's last few weeks of usage and scoring.

    Only weeks where he actually recorded something are counted, so a player
    who missed two games is judged on the games he played rather than being
    punished twice for the same injury.
    """
    position = canonical_position(getattr(player, "position", ""))

    trend = PlayerTrend(
        name=player.name,
        position=position,
        pro_team=getattr(player, "proTeam", "") or "-",
        percent_owned=float(getattr(player, "percent_owned", 0) or 0),
        injury_status=(getattr(player, "injuryStatus", "") or "").upper(),
        on_bye=bool(getattr(player, "on_bye_week", False)),
        opponent=getattr(player, "pro_opponent", "") or "-",
        season_projection=float(getattr(player, "projected_total_points", 0) or 0),
    )

    stats = getattr(player, "stats", {}) or {}

    weeks = [w for w in range(max(1, current_week - lookback), current_week) if w in stats]
    for week in weeks:
        entry = stats.get(week, {}) or {}
        breakdown = entry.get("breakdown", {}) or {}
        points = entry.get("points")

        # Skip weeks with no real game data (bye, inactive, not yet played).
        if points is None and not breakdown:
            continue

        targets = float(breakdown.get(TARGETS_KEY, 0) or 0)
        carries = float(breakdown.get(CARRIES_KEY, 0) or 0)
        receptions = float(breakdown.get(RECEPTIONS_KEY, 0) or 0)

        # A week with literally zero involvement means he did not play.
        if targets + carries + receptions == 0 and not points:
            continue

        trend.games_counted += 1
        trend.recent_points += float(points or 0)
        trend.recent_opportunities += targets + carries

    trend.season_ppg = round(float(getattr(player, "avg_points", 0) or 0), 1)
    return trend


def _percentile_ranks(values: list[float]) -> list[float]:
    """
    Turn raw numbers into 0-100 scores relative to the group.

    Used so we can fairly combine two things measured in different units
    (fantasy points and number of carries) without one drowning out the other.
    """
    if not values:
        return []
    ordered = sorted(values)
    n = len(ordered)
    if n == 1:
        return [50.0]
    out = []
    for value in values:
        # How many in the group this value beats.
        beaten = sum(1 for other in ordered if other < value)
        tied = sum(1 for other in ordered if other == value)
        out.append(round(100.0 * (beaten + tied / 2) / n, 1))
    return out


def score_group(trends: list[PlayerTrend]) -> None:
    """
    Score a group of same-position players against each other, in place.

    The final Add Score weights opportunity slightly higher than production,
    for the reason explained at the top of this file: usage predicts, points
    describe.
    """
    if not trends:
        return

    opportunity_scores = _percentile_ranks([t.opportunities_per_game for t in trends])
    production_scores = _percentile_ranks([t.recent_ppg for t in trends])

    for trend, opportunity, production in zip(trends, opportunity_scores, production_scores):
        trend.opportunity_percentile = opportunity
        trend.production_percentile = production
        trend.add_score = round(0.6 * opportunity + 0.4 * production, 1)

        trend.reasons = []
        if trend.games_counted == 0:
            trend.reasons.append("no recent game data")
        if opportunity >= 80 and production < 55:
            trend.reasons.append("heavy usage that has not paid off yet: the classic buy")
        if opportunity >= 80 and production >= 80:
            trend.reasons.append("high usage AND scoring, likely to be added everywhere")
        if opportunity < 40 and production >= 80:
            trend.reasons.append("scoring without the usage to back it up: likely to regress")
        if trend.trend >= 3:
            trend.reasons.append(f"trending up, {trend.trend} points per game above his season average")
        if trend.on_bye:
            trend.reasons.append("on a bye week, will score zero if you start him")
        if trend.injury_status in ("OUT", "DOUBTFUL", "INJURY_RESERVE"):
            trend.reasons.append(f"injury status {trend.injury_status.title()}")
        if trend.percent_owned >= 40:
            trend.reasons.append(f"already owned in {trend.percent_owned:.0f}% of leagues, expect competition")


def suggest_faab_bid(add_score: float, percent_owned: float) -> str:
    """
    Suggest a FAAB bid as a percentage of your season budget.

    FAAB, in plain terms: instead of a waiver priority order, everyone gets a
    fake budget (usually 100) for the whole season and secretly bids on
    players. Highest bid wins. Spending it all in week 2 leaves you helpless
    in week 10, so these are deliberately conservative.
    """
    if add_score >= 85 and percent_owned < 50:
        return "18-25% (a genuine difference maker, worth being aggressive)"
    if add_score >= 70:
        return "8-15% (a solid starter, bid to win but do not overpay)"
    if add_score >= 55:
        return "3-7% (useful depth)"
    if add_score >= 40:
        return "1-2% (a lottery ticket, only if you have a free roster spot)"
    return "0-1% (only worth it if nobody else bids)"
