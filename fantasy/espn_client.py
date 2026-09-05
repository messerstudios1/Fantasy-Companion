"""
Connects to ESPN's fantasy football API and translates its unhelpful errors
into plain English.

ESPN does not publish an official API. The 'espn-api' library talks to the
same private endpoints the ESPN website itself uses. Because of that, the
main thing that breaks over time is authentication: the two browser cookies
(espn_s2 and SWID) expire every month or two and have to be re-copied.
"""

from __future__ import annotations

from espn_api.football import League
from espn_api.requests.espn_requests import (
    ESPNAccessDenied,
    ESPNInvalidLeague,
    ESPNUnknownError,
)

from .config import Config

COOKIE_HELP = """
------------------------------------------------------------------------
HOW TO REFRESH YOUR ESPN COOKIES (takes about 60 seconds, no terminal)
------------------------------------------------------------------------
1. In Chrome or Edge, go to https://fantasy.espn.com and make sure you
   are logged in and can see your league.
2. Press F12 to open Developer Tools. (Mac: Cmd + Option + I)
3. Click the "Application" tab. If you do not see it, click the "»"
   arrows at the end of the tab row to reveal hidden tabs.
4. In the left sidebar, expand "Cookies" and click "https://fantasy.espn.com".
5. You will see a table of cookies. Find these two rows:
      espn_s2   -> a very long string of letters, numbers, % signs
      SWID      -> looks like {1A2B3C4D-5E6F-7890-ABCD-EF1234567890}
6. Double click the Value cell for each one and copy the whole thing.
7. Paste them into your GitHub repository Secrets:
      Your repo -> Settings -> Secrets and variables -> Actions
      -> Update ESPN_S2 and SWID
   (Or, if running locally, paste them into the ".env" file.)

Two things that silently break this:
  - Copying only part of espn_s2. It is long. Select the entire value.
  - Dropping the curly braces on SWID. Keep them.
------------------------------------------------------------------------
"""


class AuthError(Exception):
    """Raised when ESPN rejects our credentials. Message includes a fix."""


class LeagueNotFoundError(Exception):
    """Raised when the league ID or season year does not resolve."""


def connect(config: Config) -> League:
    """
    Log in to the league and return a League object.

    Raises AuthError or LeagueNotFoundError with an actionable message
    instead of letting a raw ESPN error bubble up.
    """
    try:
        return League(
            league_id=config.league_id,
            year=config.year,
            espn_s2=config.espn_s2,
            swid=config.swid,
        )
    except ESPNAccessDenied as exc:
        raise AuthError(
            "ESPN rejected your credentials (access denied).\n"
            "\n"
            "This almost always means your espn_s2 / SWID cookies expired.\n"
            "They expire on their own every month or two, so this is normal\n"
            "and not a sign anything is broken.\n"
            f"{COOKIE_HELP}"
            f"\n(Raw error from ESPN: {exc})"
        ) from exc
    except ESPNInvalidLeague as exc:
        raise LeagueNotFoundError(
            f"ESPN could not find league {config.league_id} for the {config.year} season.\n"
            "\n"
            "Check these three things:\n"
            f"  1. LEAGUE_ID is {config.league_id}. Compare it to the number after\n"
            "     'leagueId=' in your ESPN league URL.\n"
            f"  2. SEASON_YEAR is {config.year}. ESPN treats each season as a\n"
            "     separate league, so a wrong year looks like a missing league.\n"
            "  3. Your cookies are for the account that is actually in this league.\n"
            f"\n(Raw error from ESPN: {exc})"
        ) from exc
    except ESPNUnknownError as exc:
        raise AuthError(
            "ESPN returned an error we could not classify.\n"
            "\n"
            "The most common cause is still expired cookies, so try refreshing\n"
            "them first. If that does not help, ESPN's servers may be having\n"
            "trouble, which happens during heavy traffic on Sunday afternoons.\n"
            f"{COOKIE_HELP}"
            f"\n(Raw error from ESPN: {exc})"
        ) from exc


def find_my_team(league: League, config: Config):
    """
    Figure out which of the league's teams is yours.

    Three methods, tried in order:

      1. Match the SWID cookie against each team's owner list. The SWID *is*
         your ESPN user ID, so this is exact when it works.
      2. Match TEAM_ID, the number after 'teamId=' in your ESPN team URL.
         This is the reliable fallback: it does not depend on the cookies
         belonging to the right account, and it survives you renaming your
         team mid-season.
      3. Match TEAM_NAME, if one is configured.
    """
    target_swid = config.swid.strip("{}").upper()

    for team in league.teams:
        for owner in getattr(team, "owners", []) or []:
            owner_id = owner.get("id") if isinstance(owner, dict) else str(owner)
            if owner_id and owner_id.strip("{}").upper() == target_swid:
                return team

    if config.team_id is not None:
        for team in league.teams:
            if team.team_id == config.team_id:
                return team
        raise LeagueNotFoundError(
            f"No team with ID {config.team_id} in this league.\n"
            "Check the 'team_id' value in league.json against the number after\n"
            "'teamId=' in your ESPN team URL. Teams found:\n  "
            + "\n  ".join(f"{t.team_id}: {t.team_name}" for t in league.teams)
        )

    if config.team_name:
        wanted = config.team_name.strip().lower()
        for team in league.teams:
            if team.team_name.strip().lower() == wanted:
                return team
        raise LeagueNotFoundError(
            f"No team named '{config.team_name}' in this league.\n"
            "Teams found:\n  "
            + "\n  ".join(t.team_name for t in league.teams)
        )

    raise LeagueNotFoundError(
        "Could not work out which team is yours.\n"
        "\n"
        "Your SWID did not match any team owner in this league. That usually\n"
        "means the cookies came from a different ESPN account than the one\n"
        "that owns your team.\n"
        "\n"
        "Quick fix: set TEAM_NAME to your exact team name. Teams in this league:\n  "
        + "\n  ".join(t.team_name for t in league.teams)
    )


def describe_scoring(league: League) -> dict:
    """
    Read the league's scoring rules and work out the reception format.

    Plain English: 'PPR' means Point Per Reception, where every catch a
    player makes is worth 1 fantasy point. This matters a lot for rankings,
    because it inflates the value of players who catch a lot of short passes
    (slot receivers, pass-catching running backs) relative to players who
    only run the ball.

      1.0 points per reception  -> Full PPR
      0.5 points per reception  -> Half PPR
      0.0 points per reception  -> Standard
    """
    per_reception = 0.0
    for item in getattr(league.settings, "scoring_format", []) or []:
        if item.get("abbr") == "REC":
            per_reception = float(item.get("points", 0) or 0)
            break

    if per_reception >= 0.75:
        label, slug = "PPR (full point per reception)", "ppr"
    elif per_reception >= 0.25:
        label, slug = "Half PPR (half point per reception)", "half-ppr"
    else:
        label, slug = "Standard (no points for receptions)", "standard"

    return {
        "points_per_reception": per_reception,
        "label": label,
        "slug": slug,
    }
