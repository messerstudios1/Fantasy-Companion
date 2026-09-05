"""
Where results go.

Every tool writes the same report to three places so you can read it however
is convenient at the time:

  1. The console (what you see if Claude runs it for you).
  2. A file in the "output/" folder.
  3. The GitHub Actions run summary, which is the nicely formatted page you
     see in your browser after a workflow run finishes.

Reports are written in Markdown because GitHub renders it as real tables.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from .config import OUTPUT_DIR


class Report:
    """Collects Markdown lines, then writes them everywhere at the end."""

    def __init__(self, title: str):
        self.lines: list[str] = []
        self.title = title
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        self.heading(f"{title}")
        self.text(f"_Generated {stamp}_")

    # --- building blocks -------------------------------------------------

    def heading(self, text: str, level: int = 1) -> None:
        self.lines.append(f"\n{'#' * level} {text}\n")

    def text(self, text: str = "") -> None:
        self.lines.append(text)

    def bullet(self, text: str) -> None:
        self.lines.append(f"- {text}")

    def note(self, text: str) -> None:
        """A callout box. GitHub renders this with a blue info icon."""
        self.lines.append(f"\n> [!NOTE]\n> {text}\n")

    def warning(self, text: str) -> None:
        self.lines.append(f"\n> [!WARNING]\n> {text}\n")

    def table(self, headers: list[str], rows: list[list]) -> None:
        if not rows:
            self.text("_(nothing to show)_")
            return
        self.lines.append("| " + " | ".join(str(h) for h in headers) + " |")
        self.lines.append("|" + "|".join(["---"] * len(headers)) + "|")
        for row in rows:
            cells = [str(c).replace("|", "\\|") for c in row]
            self.lines.append("| " + " | ".join(cells) + " |")
        self.lines.append("")

    # --- delivery --------------------------------------------------------

    def render(self) -> str:
        return "\n".join(self.lines) + "\n"

    def deliver(self, filename: str) -> Path:
        """Print, save to output/, and push to the GitHub Actions summary."""
        body = self.render()

        print(body)

        OUTPUT_DIR.mkdir(exist_ok=True)
        path = OUTPUT_DIR / filename
        path.write_text(body, encoding="utf-8")

        summary_path = os.getenv("GITHUB_STEP_SUMMARY")
        if summary_path:
            with open(summary_path, "a", encoding="utf-8") as handle:
                handle.write(body)

        return path


def fail(message: str, filename: str = "error.md") -> None:
    """
    Print a friendly failure report and exit with a non-zero status so
    GitHub Actions marks the run as failed (and emails you about it).
    """
    report = Report("Something went wrong")
    report.warning("This run did not complete. Details below.")
    report.text("```")
    report.text(message)
    report.text("```")
    report.deliver(filename)
    raise SystemExit(1)
