# Fantasy Companion

Read-only tools for an ESPN Fantasy Football league. They tell you what to do.
They never do it for you: no lineup is changed, no waiver claim is submitted,
no draft pick is made on your behalf. Every ESPN call in this repo is a read.

Everything runs on GitHub's servers through the **Actions** tab, so you never
open a terminal or install anything on your computer.

---

## Table of contents

1. [Before anything else: the one time setup](#before-anything-else-the-one-time-setup)
2. [Getting your ESPN cookies](#getting-your-espn-cookies)
3. [The dashboard](#the-dashboard)
4. [Brand](#brand)
5. [The tools](#the-tools)
6. [Draft day playbook](#draft-day-playbook)
7. [When your cookies expire](#when-your-cookies-expire)
8. [Asking Claude to run things](#asking-claude-to-run-things)
9. [Football terms used in the reports](#football-terms-used-in-the-reports)
10. [How the code is organized](#how-the-code-is-organized)
11. [Appendix: running on your own computer instead](#appendix-running-on-your-own-computer-instead)

---

## Before anything else: the one time setup

There are two manual steps. Both happen in your browser. Neither needs a
terminal. Do them in this order.

### Step A: get the workflows onto your main branch

**This one is easy to miss and nothing works without it.** GitHub only shows
the "Run workflow" button for workflows that exist on the repository's
**default branch** (`main`). While this code sits on a feature branch, the
Actions tab will look empty.

So: merge the branch into `main`. On GitHub, open the pull request for this
branch and click **Merge pull request**. If no pull request exists yet, GitHub
shows a **Compare & pull request** button on the repo's main page after a
push.

After the merge, the Actions tab will list all four workflows.

### Step B: add your two secrets

1. Open this repository on GitHub.
2. Click **Settings** (the tab along the top of the repo, with the gear icon).
3. In the left sidebar, click **Secrets and variables**, then **Actions**.
4. Make sure you are on the **Secrets** tab, not "Variables".
5. Click the green **New repository secret** button and add these two, one at
   a time:

| Name (type it exactly, case matters) | Value |
|---|---|
| `ESPN_S2` | A long cookie value. See the next section. |
| `SWID` | A short cookie value in curly braces. See the next section. |

That is the whole list. GitHub encrypts secrets and censors them out of
workflow logs. Once saved you cannot read a secret back, only overwrite it.
That is normal, not a bug.

#### Why the league ID is not in that list

Your league ID, team ID and season live in `league.json` at the project root:

```json
{
  "league_id": 1283630842,
  "team_id": 10,
  "season_year": 2026
}
```

None of those are credentials. A league ID identifies a league but grants no
access to it, and reading a private league still requires valid cookies from
an actual member. So there is nothing gained by hiding them, and keeping them
in the repo means two fewer things to paste into a settings page.

Both numbers come straight out of your ESPN team URL:

```
https://fantasy.espn.com/football/team?leagueId=1283630842&teamId=10&seasonId=2026
                                                ^^^^^^^^^^        ^^          ^^^^
                                                league_id     team_id   season_year
```

To point the tools at a different season or league, edit that file. An
environment variable or repository Secret of the same name (`LEAGUE_ID`,
`TEAM_ID`, `SEASON_YEAR`) overrides it if you ever need that.

### Step C: confirm it works

Go to the **Actions** tab, run **"1. Test ESPN Connection"**, and read the
result. Instructions for running a workflow are in
[The tools](#the-tools) below.

---

## Getting your ESPN cookies

ESPN has no official API and issues no API keys. The only way for a program to
read a private league is to borrow the same two cookies your browser already
uses to keep you logged in. That is what `ESPN_S2` and `SWID` are.

They expire on their own every month or two. That is normal and does not mean
anything is broken. You just re-copy them.

### Chrome or Edge (Windows or Mac)

1. Go to **https://fantasy.espn.com** and confirm you are logged in and can
   see your league.
2. Press **F12** to open Developer Tools. On a Mac, press **Cmd + Option + I**.
3. Along the top of the panel that opens, click the **Application** tab. If
   you cannot see it, click the **»** arrows at the end of the tab row to
   reveal hidden tabs.
4. In the left sidebar of that panel, find **Cookies**, click the arrow to
   expand it, then click **https://fantasy.espn.com**.
5. A table of cookies appears, with a filter box above it.
6. Type `espn_s2` into the filter. Click the matching row, then look at the
   **Cookie Value** box at the bottom of the panel. Select all of it and copy.
   It is long, several hundred characters, and full of `%` symbols.
7. Clear the filter, type `SWID`, and do the same. That one is short and looks
   like `{1A2B3C4D-5E6F-7890-ABCD-EF1234567890}`. **Keep the curly braces.**

### Safari (Mac)

Safari hides developer tools until you turn them on:

1. **Safari** menu > **Settings** > **Advanced** tab > tick **Show features
   for web developers** at the bottom.
2. Go to https://fantasy.espn.com and log in.
3. **Develop** menu > **Show Web Inspector**.
4. Click the **Storage** tab, expand **Cookies**, and find `espn_s2` and
   `SWID` as described above.

### Two mistakes that quietly break everything

- **Copying only part of `espn_s2`.** It is very long and easy to truncate. If
  what you pasted looks short, you did not get all of it.
- **Dropping the braces on `SWID`.** The code adds them back if you forget,
  but include them anyway.

### Nothing sensitive lives in the code

Cookies live in exactly two places: GitHub's encrypted Secrets (for workflow
runs) and an optional local `.env` file, which `.gitignore` blocks from ever
being committed. No credential is written into a source file.

---

## The dashboard

All four tools feed one web page, built for reading on a phone. Draft board,
lineup optimizer and waiver scanner live behind three tabs, in dark or light
depending on your device setting.

**Your dashboard URL, once Pages is switched on:**

```
https://messerstudios1.github.io/Fantasy-Companion/
```

Add it to your phone's home screen and it behaves like an app.

### Turning it on (one time, in a browser)

GitHub Pages does not publish from a private repository on a free account, so
this step makes the repository public.

**What becomes visible:** the code, and your league data (team names, rosters,
recommendations). **What stays private:** your ESPN cookies. Those live in
encrypted Secrets, which stay secret on a public repository, and they were
never committed to a file. Nobody can access your ESPN account from anything
that becomes public here.

If that trade is not worth it to you, skip this section. Every tool still works
and still reports through the Actions tab and the weekly email; you just do not
get the dashboard.

1. Repository **Settings** > scroll to the bottom > **Danger Zone** >
   **Change repository visibility** > **Change to public**. Confirm.
2. Repository **Settings** > **Pages** (left sidebar).
3. Under **Build and deployment**, set **Source** to *Deploy from a branch*.
4. Set **Branch** to `main` and the folder to `/docs`. Click **Save**.
5. Wait a minute or two, then open the URL above.

### How it stays current

Each tool writes a JSON file into `docs/data/`, and the workflow commits it
back to the repository. The dashboard reads those files through GitHub's API,
which returns the newest version the moment a workflow commits it. That skips
the 30 to 60 seconds Pages takes to rebuild, so a refresh is about 45 seconds
end to end rather than a minute and a half.

The page tells you how old its data is, and shows a warning during a draft if
the board is more than 8 minutes stale. A quietly outdated board is worse than
no board.

### Auto-refresh on draft night

Workflow **"5. Live draft auto-refresh"** re-runs the draft board every 5
minutes so the dashboard updates without you tapping anything. It is gated
behind a switch so it does nothing the rest of the year.

**Switch it on before your draft:**

1. Repository **Settings** > **Secrets and variables** > **Actions**.
2. Click the **Variables** tab (not Secrets).
3. **New repository variable**. Name `DRAFT_MODE`, value `on`. Save.

**Switch it off after your draft** by editing that value to anything else, or
deleting it. Left on, it would add commits to your history all season.

Honest caveat: GitHub throttles 5 minute schedules harder than any other
interval and delays them when busy. Expect a refresh every 5 to 15 minutes in
practice. Treat it as a background top-up and still trigger a manual run when
you want the board current for your own pick.

---

## Brand

Live brand pack: **https://messerstudios1.github.io/Fantasy-Companion/brand.html**

Everything on that page reads its colour values from `docs/brand/tokens.css` at
runtime, which is the same file the dashboard loads. The swatches physically
cannot drift from the product.

### The mark

Three bars, descending, on an 8° lean. It is a ranked stack, not a football.

A football would say "sports", which you already know. A descending stack says
*tiers*, which is the one idea the whole product is built on: players are
grouped by quality, and the moment a group runs out is the moment you act.
Three shapes is few enough to survive at 16px.

### The bold choice: the lean

**Everything structural leans 8°. Nothing informational ever does.**

Fantasy sports interfaces are relentlessly upright. A consistent lean across
the furniture gives this one a silhouette you can recognise from across a room.

It is also load-bearing rather than decorative. The lean is how you tell chrome
from content without reading either: the logo leans, tier ticks lean, decorative
marks lean. Player names, projections, ranks and any number you might act on
stay dead level. If a user could misread something because it is tilted, it does
not tilt.

### Signal

One accent, `--signal`, and it means one thing: **act now**.

Not a colour sprinkled on things we like. It marks the moment the product exists
for: you are on the clock, this lineup is costing you points, this tier is about
to empty. If Signal is on screen, there is something to do. Used decoratively it
would mean nothing, which is how most accent colours end up.

The single exception is the logo, which is the product's signature rather than a
piece of advice.

### The depth chart

Position colours are fixed and never reassigned, so they become readable without
the label after about a week of use. They and Signal are the only chroma in the
system.

| | | | | | |
|---|---|---|---|---|---|
| QB | RB | WR | TE | K | D/ST |

### Type

The system font stack, deliberately. No webfont means nothing to load, nothing
to license, nothing to break offline, and text that already looks native on
whatever device is reading it. The personality lives in the lean and in Signal,
not in a typeface.

Every numeral is set in tabular figures so columns of numbers line up, and stats
carry more weight than the labels beside them. You are here to compare numbers.

### Assets

```
docs/brand/mark.svg        Two colour, primary
docs/brand/mark-mono.svg   Single colour, for tiny sizes and one-colour print
docs/brand/logo.svg        Horizontal lockup
docs/brand/tokens.css      Every token. The source of truth.

docs/favicon.svg           Small-size optical variant of the mark
docs/favicon.ico           16/32/48/64, for browsers that ignore SVG icons
docs/apple-touch-icon.png  180px on an opaque ground, for iOS home screens
docs/icon-192.png          PWA icon
docs/icon-512.png          PWA icon, also used maskable
docs/site.webmanifest      Makes "Add to Home Screen" name it properly
```

The mark ships in two cuts. Above roughly 32px it uses the display version.
Below that, the third bar sits at 42% opacity and dissolves into the
background, so favicons use an optically adjusted cut with less padding,
thicker bars, and the lower two lifted to 92% and 62%. Same three shapes,
same lean.

---

## The tools

### How to run any workflow

1. Click the **Actions** tab at the top of the repository.
2. Pick the workflow from the left sidebar.
3. Click the grey **Run workflow** dropdown on the right, then the green
   **Run workflow** button inside it.
4. Wait roughly 40 seconds and refresh the page.
5. Click the run that appears. The report is on its summary page.

---

### 1. Test ESPN Connection

Run this first, and any time something else fails.

It checks four things in order and tells you exactly which one broke:

1. Are the settings present?
2. Does ESPN accept the cookies? *(this is the part that expires)*
3. Can it work out which team is yours?
4. Can it read your roster and the league's scoring rules?

Step 3 has three fallbacks, tried in order: your SWID cookie matched against
each team's owner list, then `team_id` from `league.json`, then `TEAM_NAME` if
you set one. The team ID fallback is the dependable one, since it does not
care which ESPN account the cookies came from, and it survives you renaming
your team mid-season.

It also prints your league setup: team count, scoring format, and which roster
slots you have to fill each week.

---

### 2. Draft Board

Your draft-day sidekick. Run it as often as you like during the draft.

Each run re-checks who has already been taken and shows:

- **Where the draft stands.** Round, your draft slot, which overall pick is
  yours next, and how many picks until your turn.
- **Your roster so far** and which starting slots are still empty.
- **Best available overall**, the top 30 undrafted players by consensus expert
  ranking.
- **Positional urgency**, which positions are about to run dry, explained with
  tiers.
- **Best available at each position.**
- **The last 10 picks**, so you can confirm at a glance the board is current
  and not stale.

It does not make picks. You click picks on ESPN; this is the list you read
while doing it.

#### Where the rankings come from

The board prefers **consensus expert rankings**, which average many analysts'
opinions together and are meaningfully better than ESPN's own numbers. Those
come from scraping a public page, and scraping can break. So there are three
layers, tried in order:

1. Fetch live consensus rankings.
2. If that fails, use the last successful download, cached between runs.
3. If there is no cache either, fall back to ESPN's own projections.

**The report always states at the top which layer it used.** A yellow warning
box means the rankings are stale or fell back. The board still works either
way.

---

### 3. Weekly Check (lineup + waivers)

Runs both weekly tools together. Scheduled automatically, and also runnable on
demand.

**Schedule (all times UTC, which is how GitHub works):**

| When | UTC | US Eastern | Why then |
|---|---|---|---|
| Sunday | 15:00 | 11am | After Saturday's injury reports are final, before the early games lock |
| Tuesday | 14:00 | 10am | After Monday night's game, before most leagues process waivers Wednesday |

Two honest caveats about GitHub's scheduler:

- **It does not adjust for daylight saving.** These shift by an hour relative
  to your clock in early November. Edit the `cron:` lines in
  `.github/workflows/weekly-check.yml` if that matters to you.
- **It is not punctual.** GitHub delays scheduled runs when their servers are
  busy, sometimes by 30 minutes or more. Fine for a Tuesday waiver scan.
  Do not rely on it to beat a Sunday 1pm kickoff by five minutes.

**How the results reach you:** the run opens a GitHub Issue containing both
reports. GitHub emails you when an issue is opened on your own repo, so a
scheduled run nobody is watching still gets your attention. Close the issue
once you have read it.

#### The lineup optimizer

Compares your bench against your starters and tells you if you are leaving
points on the table.

It reads your current lineup, reads every player's projected points, then
**forces the projection to zero for anyone on a bye week or ruled OUT**,
because those players cannot score. ESPN usually does this itself, but not
always, and accidentally starting a player who is not playing is the most
expensive mistake available in fantasy football.

It then works out the highest-scoring legal lineup and shows the difference as
a plain list of swaps. If the best available change is worth less than 1
projected point, it tells you to leave your lineup alone, because that is
inside the margin of error on these projections.

#### The waiver wire scanner

Looks at every unowned player and ranks who is worth adding.

The scoring blends two things, weighted 60/40:

- **Opportunity (60%):** carries plus targets per game over the last 3 weeks.
- **Production (40%):** actual fantasy points per game over the same period.

Opportunity is weighted higher on purpose. Carries and targets are decided by
coaches and are stable week to week. Fantasy points are heavily distorted by
touchdowns, and touchdowns are close to random. A player with 18 carries and
no touchdown had a better week, predictively, than one with 3 carries who
happened to score twice.

The most interesting profile on the page is **high opportunity, low
production**. That means the usage is already there and the points have not
caught up yet. That is the player to add before everyone else notices.

It also identifies your own weakest roster spots and pairs them into concrete
"add this, drop that" suggestions, with a suggested FAAB bid if your league
uses a waiver budget.

**One thing it cannot see:** ESPN's API does not expose snap counts (the
percentage of his team's plays a player was on the field for). That is a
genuinely useful metric and we do not have access to it. Carries and targets
are the closest available substitute.

---

### 4. Run offline tests

Runs all the logic tests against fake data. No ESPN cookies involved, so it
can never fail because your credentials expired. If this one goes red, real
code is broken.

It runs automatically on every push.

---

## Draft day playbook

1. **The day before**, run **"1. Test ESPN Connection"**. If your cookies are
   stale, you want to find out now, not at 8:01pm.
2. **An hour before**, run **"2. Draft Board"** once. This warms the rankings
   cache, so if the rankings site goes down mid-draft you still have real data
   to fall back on.
3. **Turn on `DRAFT_MODE`** (see [Auto-refresh on draft night](#auto-refresh-on-draft-night))
   so the board updates itself in the background.
4. **During the draft**, keep the dashboard open on your phone and pull to
   refresh. If you want the board current for your own pick rather than
   whenever the schedule fires, trigger **"2. Draft Board"** from the Actions
   tab and reload about 45 seconds later.
5. **Sanity check every refresh** by glancing at the "Last 10 picks" table at
   the bottom. If it shows picks you just watched happen, the board is live.
   If it looks frozen, ESPN's draft feed is lagging.
6. **Read "Positional urgency" before every pick.** That is the section that
   actually changes decisions. "Only 1 left in this tier" means take him now.
   "6 left, no rush" means take a different position and come back.

If the board breaks entirely mid-draft, you still have ESPN's own draft screen,
which shows their rankings. You will be fine. This is a sidekick, not a
crutch.

---

## When your cookies expire

**Symptom:** a workflow run fails and the report says ESPN denied access.

**Fix:**

1. Redo [Getting your ESPN cookies](#getting-your-espn-cookies).
2. Repository **Settings** > **Secrets and variables** > **Actions**.
3. Click the pencil icon next to `ESPN_S2`, paste the new value, save.
4. Do the same for `SWID`. Those two are the only secrets there.
5. Re-run **"1. Test ESPN Connection"** to confirm.

You do not need to change any code, and you do not need to touch anything else.

The error message in the failed run contains these same instructions, so you
do not have to remember where to find them.

---

## Asking Claude to run things

You do not have to remember any of this. In Claude Code you can say:

| Say this | What happens |
|---|---|
| "Test my ESPN connection" | Triggers the connection test and reads you the result |
| "Refresh my draft board" | Triggers a draft board run and summarizes the best available |
| "Run the weekly check" | Triggers the lineup optimizer and waiver scan, then summarizes both |
| "My cookies expired, walk me through it" | Step by step cookie refresh instructions |
| "Why is it recommending this player?" | Explanation of the reasoning behind any recommendation |
| "Turn on draft mode" | Sets the DRAFT_MODE variable so the board auto-refreshes |

Claude cannot reach ESPN directly from its own session, because the sandbox it
runs in blocks `espn.com` at the network level. So it triggers the GitHub
Actions workflow and reads the run's logs instead. Same result, slightly
longer round trip.

---

## Football terms used in the reports

| Term | What it means |
|---|---|
| **QB** | Quarterback. Throws the ball. You start one. |
| **RB** | Running back. Runs the ball. Scarce, so they go early in drafts. |
| **WR** | Wide receiver. Catches the ball. Deep position, many good ones. |
| **TE** | Tight end. Catches and blocks. Very top-heavy: a few great ones, then a long flat wasteland. |
| **K** | Kicker. Nearly random week to week. Draft last, never think about again. |
| **D/ST** | An entire team's defense, counted as one fantasy player. Also close to random. |
| **FLEX** | A roster slot you can fill with any RB, WR, or TE. |
| **Bye week** | Every NFL team takes one week off. A player on bye scores exactly zero. |
| **PPR** | Point Per Reception. Every catch is worth a point, which raises the value of players who catch a lot of short passes. |
| **Tier** | A group of players experts consider roughly interchangeable. The most useful draft concept there is: if a tier still has 6 players, you can wait. If it has 1, that quality level is about to vanish. |
| **ADP** | Average Draft Position. Where a player typically gets picked. |
| **Targets** | Passes thrown at a receiver, caught or not. Measures how much the offense wants to use him. |
| **Carries** | Rushing attempts. The running back equivalent of targets. |
| **FAAB** | Free Agent Acquisition Budget. Instead of a waiver priority order, everyone gets a fake budget for the season and bids secretly on players. Highest bid wins. |
| **Waiver wire** | The pool of players nobody owns. Most leagues are won by noticing someone there a week before everyone else. |

---

## How the code is organized

```
fantasy/
  config.py        Loads settings from .env or GitHub Secrets. No secrets in code.
  espn_client.py   Connects to ESPN. Turns cryptic errors into plain English.
  names.py         Matches player names across sites (including team defenses,
                   which the two sources name completely differently).
  rankings.py      Downloads consensus rankings, with cache and fallback.
  lineup.py        The lineup optimization algorithm, and why it is optimal.
  waivers.py       Free agent scoring, and the football reasoning behind it.
  output.py        Formats reports for console, file, and the GitHub summary page.
  export.py        Writes the JSON files the dashboard reads.

scripts/
  test_connection.py    Phase 1: prove the connection works.
  draft_board.py        Phase 2: the live draft cheat sheet.
  lineup_optimizer.py   Phase 3: weekly start/sit recommendations.
  waiver_scanner.py     Phase 4: weekly free agent recommendations.

tests/
  lineup_test.py          Optimizer maths, including bye weeks and injuries.
  waivers_test.py         Free agent scoring, including the usage-over-luck rule.
  offline_smoke_test.py   Full draft board against fixtures, including the
                          degraded fallback path.

.github/workflows/
  test-connection.yml   "1. Test ESPN Connection"
  draft-board.yml       "2. Draft Board"
  weekly-check.yml      "3. Weekly Check", scheduled Sun + Tue
  tests.yml             "4. Run offline tests", runs on every push
  draft-live.yml        "5. Live draft auto-refresh", gated behind DRAFT_MODE

docs/
  index.html            The dashboard. Plain HTML, CSS and JavaScript, no build
                        step and no framework, so it cannot rot.
  brand.html            The live brand pack.
  brand/tokens.css      Every design token. Loaded by both pages, so they
                        cannot drift apart.
  brand/*.svg           Logo assets.
  data/*.json           Written by each tool, committed by the workflow, read
                        by the dashboard.

league.json             League ID, team ID and season. Not secret, committed.
.env.example            Template for local runs. Secrets only.

data/
  rankings_cache.json   Last successful rankings download. Auto-managed.

output/
  Generated reports. Overwritten every run, not committed.
```

Every script is read-only against ESPN. None of them can change your team.

---

## Appendix: running on your own computer instead

You do not need this. It is documented in case you ever want it.

Running locally means installing Python, installing the dependencies, creating
a `.env` file, and configuring your operating system's scheduler. That last
part is a genuine one time manual step that cannot happen inside Claude Code,
because Claude Code cannot open Task Scheduler or edit your crontab for you.

The honest comparison:

| | GitHub Actions | Your computer |
|---|---|---|
| Setup | Paste 3 secrets into a web page | Install Python, dependencies, configure OS scheduler |
| Runs when your machine is off | Yes | No |
| Terminal required | Never | Yes, for setup |
| Cost | Free for this usage | Free |

If you still want it:

**Local setup (all platforms)**

1. Install Python 3.11 or newer from python.org. On Windows, tick **"Add
   Python to PATH"** during install.
2. Download this repository to a folder.
3. Copy `.env.example` to `.env` and fill in your league ID and cookies.
4. Install dependencies: `pip install -r requirements.txt`
5. Run a tool: `python scripts/draft_board.py`

**Windows: Task Scheduler**

1. Press the Windows key, type `Task Scheduler`, press Enter.
2. In the right panel click **Create Basic Task**.
3. Name it `Fantasy weekly check`. Click **Next**.
4. Choose **Weekly**. Click **Next**.
5. Pick Sunday, set the time to 11:00 AM. Click **Next**.
6. Choose **Start a program**. Click **Next**.
7. In **Program/script**, type `python`.
8. In **Add arguments**, type `scripts\lineup_optimizer.py`.
9. In **Start in**, paste the full path to this repo folder, for example
   `C:\Users\YourName\Fantasy-Companion`. This field is not optional; leaving
   it blank is the most common reason scheduled tasks fail silently.
10. Click **Next**, then **Finish**.
11. Test it: find the task in the list, right click, **Run**. A console window
    should flash open. Check `output\lineup.md` for the report.

**Mac: cron**

1. Open **Terminal** (Applications > Utilities > Terminal).
2. Type `crontab -e` and press Enter. This opens a text editor called `vi`.
3. Press the `i` key to start typing.
4. Add this line, replacing the path with your actual repo folder:
   ```
   0 11 * * 0 cd /Users/yourname/Fantasy-Companion && /usr/bin/python3 scripts/lineup_optimizer.py
   ```
5. Press `Esc`, then type `:wq` and press Enter to save and quit.
6. macOS will pop up a permission request the first time it runs. Approve it,
   or the job fails silently forever.

If any of that sounds unpleasant, that is a reasonable reaction, and it is
exactly why the GitHub Actions route is the default here.
