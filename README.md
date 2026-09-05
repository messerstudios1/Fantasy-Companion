# Fantasy Companion

A set of read-only tools for an ESPN Fantasy Football league. They tell you
what to do. They never do it for you: no lineup is ever changed, no waiver
claim is ever submitted, no draft pick is ever made on your behalf.

Everything runs on GitHub's servers through the **Actions** tab, which means
you never have to open a terminal or install anything on your computer.

---

## Table of contents

1. [One time setup](#one-time-setup)
2. [Getting your ESPN cookies](#getting-your-espn-cookies)
3. [The tools](#the-tools)
4. [When your cookies expire](#when-your-cookies-expire)
5. [Asking Claude to run things](#asking-claude-to-run-things)
6. [How the code is organized](#how-the-code-is-organized)

---

## One time setup

You need to give GitHub three pieces of information. They get stored
encrypted, and GitHub censors them out of any log output.

**Step 1.** Go to this repository on GitHub in your browser.

**Step 2.** Click **Settings** (the tab along the top of the repo, with the
gear icon). If you do not see it, you are looking at the wrong repo or do not
have admin rights on it.

**Step 3.** In the left sidebar, click **Secrets and variables**, then click
**Actions** underneath it.

**Step 4.** Make sure you are on the **Secrets** tab (not "Variables"), then
click the green **New repository secret** button. Add these three, one at a
time:

| Name (type exactly) | Value |
|---|---|
| `LEAGUE_ID` | The number in your ESPN league URL after `leagueId=` |
| `ESPN_S2` | A long cookie value. See the next section. |
| `SWID` | A short cookie value in curly braces. See the next section. |

To find `LEAGUE_ID`: open your league on ESPN and look at the address bar.

```
https://fantasy.espn.com/football/league?leagueId=123456789
                                                  ^^^^^^^^^
                                                  this part
```

**Step 5.** Go to the **Actions** tab and run **"1. Test ESPN Connection"**.
Instructions for running a workflow are in [The tools](#the-tools) below. If
it comes back green, setup is done.

---

## Getting your ESPN cookies

ESPN has no official API and no API keys. The only way for a program to read
a private league is to borrow the same two cookies your browser already uses
to keep you logged in. That is what `ESPN_S2` and `SWID` are.

They expire on their own every month or two. That is normal and does not mean
anything is broken. You just re-copy them.

### On Chrome or Edge (Windows or Mac)

1. Go to **https://fantasy.espn.com** and confirm you are logged in and can
   see your league.
2. Press **F12** to open Developer Tools.
   On a Mac, press **Cmd + Option + I**.
3. Along the top of the panel that opens, click the **Application** tab.
   If you cannot see it, click the **»** arrows at the end of the tab row to
   reveal the hidden tabs.
4. In the left sidebar of that panel, find **Cookies** and click the little
   arrow to expand it, then click **https://fantasy.espn.com**.
5. A table of cookies appears. Use the filter box at the top to search.
6. Type `espn_s2` in the filter. Click the row, then look at the **Cookie
   Value** box at the bottom of the panel. Select the whole thing and copy it.
   It is long, several hundred characters, and contains `%` symbols. Get all
   of it.
7. Clear the filter, type `SWID`, and do the same. This one is short and
   looks like `{1A2B3C4D-5E6F-7890-ABCD-EF1234567890}`. **Keep the curly
   braces.**

### On Safari (Mac)

Safari hides the developer tools by default:

1. **Safari** menu > **Settings** > **Advanced** tab > tick
   **Show features for web developers** at the bottom.
2. Go to https://fantasy.espn.com and log in.
3. **Develop** menu > **Show Web Inspector**.
4. Click the **Storage** tab, expand **Cookies**, and find `espn_s2` and
   `SWID` as described above.

### Two mistakes that quietly break everything

- **Copying only part of `espn_s2`.** It is very long and easy to truncate.
  If it looks short, you did not get all of it.
- **Dropping the braces on `SWID`.** The code adds them back if you forget,
  but it is better to just include them.

### Nothing sensitive goes in the code

Cookies live in exactly two places: GitHub's encrypted Secrets (for workflow
runs) and an optional local `.env` file (which `.gitignore` blocks from ever
being committed). They are never written into a source file.

---

## The tools

### How to run any workflow

1. Click the **Actions** tab at the top of the repository.
2. Pick the workflow you want from the left sidebar.
3. Click the grey **Run workflow** dropdown on the right, then the green
   **Run workflow** button inside it.
4. Wait roughly 40 seconds. Refresh the page.
5. Click the run that appears, and read the report on its summary page.

---

### 1. Test ESPN Connection

Run this first, and any time something else fails.

It checks four things in order and tells you exactly which one broke:

1. Are the settings present?
2. Does ESPN accept the cookies? *(this is the one that expires)*
3. Can it work out which team is yours?
4. Can it read your roster and the league's scoring rules?

It also prints your league's setup: how many teams, what the scoring format
is, and which roster slots you have to fill each week.

---

### 2. Draft Board

Your live draft sidekick. Run it as often as you want during the draft.

Each run re-checks who has already been taken and shows you:

- **Where the draft stands.** What round it is, your draft slot, which
  overall pick is yours next, and how many picks until your turn.
- **Your roster so far,** and which starting slots you have not filled.
- **Best available overall.** The top 30 undrafted players by consensus
  expert ranking.
- **Positional urgency.** Which positions are about to run dry, explained
  with tiers.
- **Best available at each position.**
- **The last 10 picks,** so you can confirm at a glance that the board is
  actually current and not stale.

It does not make picks. You click picks on ESPN's site; this is the list you
look at while doing it.

**Draft day tip:** open two browser tabs on the Actions page. Read the board
in one tab while the next refresh builds in the other, so you always have a
list on screen.

#### Where the rankings come from

The board prefers **consensus expert rankings**, which average together many
analysts' opinions and are meaningfully better than ESPN's own numbers.

Those come from scraping a public web page, and scraping can break. So there
are three layers, tried in order:

1. Fetch live consensus rankings.
2. If that fails, use the last successful download (cached between runs).
3. If there is no cache either, fall back to ESPN's own projections.

**The report always says at the top which layer it used.** If you see a
yellow warning box, the rankings are stale or fell back. The board still
works either way.

---

## When your cookies expire

Symptom: a workflow run fails, and the report says ESPN denied access.

Fix: redo [Getting your ESPN cookies](#getting-your-espn-cookies), then:

1. Repository **Settings** > **Secrets and variables** > **Actions**.
2. Click the pencil/edit icon next to `ESPN_S2`, paste the new value, save.
3. Do the same for `SWID`.
4. Re-run **"1. Test ESPN Connection"** to confirm.

You do not need to change anything else, and you do not need to touch the
code.

---

## Asking Claude to run things

You do not have to remember any of this. In Claude Code you can just say:

| Say this | What happens |
|---|---|
| "Test my ESPN connection" | Triggers the connection test and reads you the result |
| "Refresh my draft board" | Triggers a draft board run and summarizes the best available players |
| "My cookies expired, walk me through it" | Step by step cookie refresh instructions |

Claude cannot reach ESPN directly from its own session (network policy blocks
it), so it triggers the GitHub Actions workflow and reads the run's logs.
Same result, just a slightly longer round trip.

---

## How the code is organized

```
fantasy/
  config.py        Loads settings from .env or GitHub Secrets. No secrets in code.
  espn_client.py   Connects to ESPN. Turns cryptic errors into plain English.
  names.py         Matches player names between ESPN and ranking sites.
  rankings.py      Downloads consensus rankings, with cache and fallback.
  output.py        Formats reports and sends them to console, file, and GitHub.

scripts/
  test_connection.py   Phase 1: prove the connection works.
  draft_board.py       Phase 2: the live draft cheat sheet.

tests/
  offline_smoke_test.py   Runs the real logic against fake data. No cookies needed.

.github/workflows/
  test-connection.yml  The "1. Test ESPN Connection" button.
  draft-board.yml      The "2. Draft Board" button.
```

Every script is read-only against ESPN. None of them can change your team.
