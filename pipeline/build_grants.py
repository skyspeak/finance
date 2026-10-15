#!/usr/bin/env python3
"""Build the grant map. No market data: reads data/grants.json, writes public/grants.html.

The page is the interactive part. This script only embeds the dataset and checks
the offer math that the page reimplements.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "grants.json"
TEMPLATE = Path(__file__).resolve().parent / "grant_page.html"
OUT = ROOT / "public" / "grants.html"


def package(v: float, lab: bool, a: dict) -> float:
    """Dollar grant that never falls as the company gets more expensive.

    The chart's step function does fall: 0.20% of $99M is ~$198k and 0.10% of
    $100M is $100k; the 0.05% band and the $200k cap cut it again. Hold across
    each cut. $500k is the top of the 0.10% band, not the chart's $200k cap.
    """
    s = a["offer_schedule"]
    if lab and v >= a["lab_above"]:
        return float(a["lab_grant"])
    if v < s["early_until"]:
        return s["pct_early"] * v
    if v < s["bridge_until"]:
        return float(s["bridge_grant"])
    if v < s["mid_until"]:
        return s["pct_mid"] * v
    return float(s["late_floor"])


def stake(v: float, mark: float, keep: float, lab: bool, a: dict) -> float:
    return package(v, lab, a) * mark * keep


def check(data: dict) -> None:
    a = data["assumptions"]
    # Chart rule.
    assert package(56e6, False, a) == 0.002 * 56e6
    assert package(99e6, False, a) == 0.002 * 99e6
    assert package(100e6, False, a) == 200_000
    assert package(150e6, False, a) == 200_000  # literal rule would pay $150k
    assert package(250e6, False, a) == 250_000
    assert package(500e6, False, a) == 500_000
    assert package(800e6, False, a) == 500_000  # literal 0.05% would pay $400k
    assert package(2e9, False, a) == 500_000  # literal cap would pay $200k
    assert package(965e9, False, a) == 500_000
    assert package(965e9, True, a) == 2_000_000
    prev = 0.0
    v = 20e6
    while v < 40e9:
        g = package(v, False, a)
        if g + 1e-6 < prev:
            raise SystemExit(f"grant fell at {v:,.0f}: {prev:,.0f} -> {g:,.0f}")
        prev = g
        v *= 1.05
    # $250M, 10x, no second dilution haircut -> $2.5M, on the chart's 10x line.
    assert stake(250e6, 10, 1, False, a) == 2_500_000
    # Same grant with a 50% extra haircut is $1.25M, and clearing $5M then needs a $10B company.
    assert stake(250e6, 10, 0.5, False, a) == 1_250_000
    grant = package(250e6, False, a)
    assert 5_000_000 / grant == 20
    assert 250e6 * (20 / 0.5) == 10_000_000_000

    for w in data["winners"]:
        implied = w["entry"] * w["mult"]
        gap = abs(implied - w["now"]) / w["now"]
        if gap > 0.08:
            raise SystemExit(f"{w['name']}: entry × multiple is {implied:,.0f}, chart says {w['now']:,.0f}")
    for p in data["peaks"]:
        if p.get("plot"):
            if p["peak"] is None or p["latest"] is None:
                raise SystemExit(f"{p['name']} is plotted without a dollar pair")
            if p["latest"] > p["peak"]:
                raise SystemExit(f"{p['name']} latest above peak")


def main() -> None:
    data = json.loads(DATA.read_text())
    check(data)
    payload = json.dumps(data, separators=(",", ":")).replace("<", "\\u003c")
    html = TEMPLATE.read_text().replace("__GRANTS_JSON__", payload)
    if "__GRANTS_JSON__" in html:
        raise SystemExit("template placeholder left in output")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(html)
    print(f"wrote {OUT} ({len(html):,} bytes), {len(data['winners'])} grants, {len(data['peaks'])} peaks")


if __name__ == "__main__":
    main()
