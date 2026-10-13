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
    if lab and v >= a["lab_above"]:
        return float(a["lab_grant"])
    for band in a["bands"]:
        if v < band["below"]:
            return band["pct"] * v
    return float(a["cap_grant"])


def stake(v: float, mark: float, keep: float, lab: bool, a: dict) -> float:
    return package(v, lab, a) * mark * keep


def check(data: dict) -> None:
    a = data["assumptions"]
    # Chart rule.
    assert package(56e6, False, a) == 0.002 * 56e6
    assert package(250e6, False, a) == 250_000
    assert package(800e6, False, a) == 0.0005 * 800e6
    assert package(2e9, False, a) == 200_000
    assert package(965e9, False, a) == 200_000
    assert package(965e9, True, a) == 2_000_000
    # $250M, mark 10x, keep half -> net 5x on a $250k grant.
    assert stake(250e6, 10, 0.5, False, a) == 1_250_000
    # $5M stake from that grant needs 20x net. At 50% keep, the mark must 40x: $10B.
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
