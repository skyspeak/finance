"""Mechanical STRATEGY / INTRO from this week's numbers and last week's ratings.

Unattended runs must not ship last week's prose. This is numerate and dated,
not a strategist rewrite — it names flips, sleeves, concentration, and the
research lag so the desk stays honest.
"""
from __future__ import annotations

from pathlib import Path


def _sleeve_line(port, name):
    grp = [p for p in port if p.get("sleeve") == name]
    if not grp:
        return f"**{name}.** Empty this week."
    names = ", ".join(p["ticker"] for p in grp)
    w = sum(p["weight"] for p in grp)
    return f"**{name} ({w:.0f}%).** {names}."


def _flips(rows, prev):
    if not prev:
        return "First snapshot in the database — no week-over-week rating flips to report."
    lines = []
    by = {r["ticker"]: r for r in rows}
    for t, old in sorted(prev.items()):
        new = by.get(t)
        if not new:
            continue
        if new["rating"] != old["rating"]:
            lines.append(
                f"- **{t}** {old['rating']} → {new['rating']} (composite {new['composite']:.2f})"
            )
    return "\n".join(lines) if lines else "No PICK / NEUTRAL / AVOID flips versus the prior snapshot."


def write_copy(work: Path, data2: dict, prev_ratings: dict, research_asof: str) -> tuple[str, str]:
    rows = data2["rows"]
    port = data2.get("portfolio") or []
    picks = [r for r in rows if r["rating"] == "PICK"]
    avoids = [r for r in rows if r["rating"] == "AVOID"]
    trades = [r for r in rows if r.get("trade")]
    asof = data2["asof"]
    cash = data2.get("cash")
    beta = data2.get("port_beta")
    cluster = data2.get("cluster_w")
    invested = round(100 - (cash or 0), 1)
    top_corr = (data2.get("corr_pairs") or [{}])[0]
    corr_s = ""
    if top_corr.get("corr") is not None:
        corr_s = f"{top_corr['a']} / {top_corr['b']} at **{top_corr['corr']}**"

    flips = _flips(rows, prev_ratings)
    core = _sleeve_line(port, "Core")
    contra = _sleeve_line(port, "Contrarian")
    tact = _sleeve_line(port, "Tactical")
    avoid_names = ", ".join(r["ticker"] for r in avoids) or "none"

    strategy = f"""Auto-generated for the **{asof}** close. Analyst coverage, events, IPOs, 13F and private-company files are carried from the **{research_asof}** research pass — they are not refreshed by the daily job.

{len(picks)} picks, {invested}% invested, {cash}% cash held back by the single-name cap. Portfolio beta is **{beta}**. {len(trades)} defined-risk tickets cleared the liquidity screen.

**Rating flips vs prior snapshot.**
{flips}

{core}

{contra}

{tact}

**Funding sources.** AVOID: {avoid_names}.

**The risk that actually matters.** {cluster}% of invested capital sits in AI compute, power, and enterprise software. Highest theme-pair correlation: {corr_s or 'n/a'}. Treat the cash sleeve as thesis insurance, not leftover.
"""

    intro = (
        f"{len(picks)} picks, {invested}% invested, {cash}% cash. Book beta is {beta}. "
        f"{cluster}% of invested capital sits in three AI-adjacent themes. "
        f"{len(trades)} defined-risk tickets are live below. "
        f"Research files (analysts, events, IPOs) are as of {research_asof}; prices and options as of {asof}."
    )

    (work / "strategy.md").write_text(strategy.strip() + "\n")
    (work / "intro.md").write_text(intro.strip() + "\n")
    return strategy, intro
