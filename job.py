#!/usr/bin/env python3
"""Weekly Ten Themes job.

Fetches prices / fundamentals / technicals / options / macro, scores the universe,
writes a Postgres snapshot, generates the desk + map HTML, and publishes public/ by
committing it to the site repo (skyspeak/industry), which Vercel deploys.

Research JSON (analysts, events, IPOs, 13F, privates, insiders, activists) is
carried forward from the latest snapshot so the job can run unattended.
Override with files in data/ on the first run (`--seed`).

Usage:
  DATABASE_URL=... python3 job.py --seed     # load committed snapshot into Postgres
  DATABASE_URL=... python3 job.py            # full weekly fetch + publish
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import traceback
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "pipeline"
DATA = ROOT / "data"
PUBLIC = ROOT / "public"
OUTPUT = ROOT / "output"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WORK))

MIN_PRICES = 60
MIN_TRADES = 8
FETCH = ("prices.py", "enrich.py", "tech.py", "score.py", "options.py", "score2.py")
MAP = ("macro.py", "sectors.py", "factors.py")


def load_json(path: Path):
    return json.loads(path.read_text()) if path.exists() else None


def dump_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=1))


def run_script(name: str) -> None:
    print(f"==> {name}", flush=True)
    r = subprocess.run([sys.executable, name], cwd=WORK)
    if r.returncode != 0:
        raise SystemExit(f"{name} failed with exit {r.returncode}")


def stage_from_data() -> None:
    WORK.mkdir(exist_ok=True)
    for src in DATA.glob("*.json"):
        shutil.copy(src, WORK / src.name)
    print("staged research + snapshot JSON from data/", flush=True)


def stage_research_from_snapshot(snap: dict) -> str:
    """Write carried research files. Returns research_asof iso string."""
    analysts = snap.get("analysts") or {}
    dump_json(WORK / "analysts_1.json", analysts)
    dump_json(WORK / "analysts_2.json", {})
    dump_json(WORK / "insiders.json", snap.get("insiders") or {})
    dump_json(WORK / "activists.json", snap.get("activists") or [])
    dump_json(WORK / "hedgefunds.json", snap.get("hedgefunds") or {})
    dump_json(WORK / "private_1.json", snap.get("privates") or [])
    dump_json(WORK / "private_2.json", [])
    dump_json(WORK / "events.json", snap.get("events") or [])
    dump_json(WORK / "ipos.json", snap.get("ipos") or [])
    layers = snap.get("layers")
    if layers:
        dump_json(WORK / "layers.json", layers)
    elif (DATA / "layers.json").exists():
        shutil.copy(DATA / "layers.json", WORK / "layers.json")
    rasof = snap.get("research_asof") or snap.get("asof")
    rasof_s = rasof.isoformat() if hasattr(rasof, "isoformat") else str(rasof)[:10]
    print(f"carried research from snapshot asof {snap.get('asof')} (research_asof {rasof_s})", flush=True)
    return rasof_s


def stage_prev(snap: dict | None) -> None:
    """Last good prices/enrich/sectors as *_prev.json: the fallback when a source refuses
    this week (fields carried from here are marked stale)."""
    for key in ("prices", "enrich", "sectors"):
        obj = (snap or {}).get(key) or load_json(DATA / f"{key}.json")
        if obj:
            dump_json(WORK / f"{key}_prev.json", obj)
    print("staged prior prices/enrich/sectors for carry-forward", flush=True)


def collect_blobs() -> dict:
    a1 = load_json(WORK / "analysts_1.json") or {}
    a2 = load_json(WORK / "analysts_2.json") or {}
    p1 = load_json(WORK / "private_1.json") or []
    p2 = load_json(WORK / "private_2.json") or []
    return {
        "analysts": {**a1, **a2},
        "insiders": load_json(WORK / "insiders.json"),
        "activists": load_json(WORK / "activists.json"),
        "hedgefunds": load_json(WORK / "hedgefunds.json"),
        "privates": list(p1) + list(p2),
        "events": load_json(WORK / "events.json"),
        "ipos": load_json(WORK / "ipos.json"),
        "prices": load_json(WORK / "prices.json"),
        "enrich": load_json(WORK / "enrich.json"),
        "tech": load_json(WORK / "tech.json"),
        "hist": load_json(WORK / "hist.json"),
        "options": load_json(WORK / "options.json"),
        "data": load_json(WORK / "data.json"),
        "data2": load_json(WORK / "data2.json"),
        "macro": load_json(WORK / "macro.json"),
        "sectors": load_json(WORK / "sectors.json"),
        "factors": load_json(WORK / "factors.json"),
        "layers": load_json(WORK / "layers.json"),
    }


def copy_artifacts() -> None:
    OUTPUT.mkdir(exist_ok=True)
    PUBLIC.mkdir(exist_ok=True)
    site = WORK / "site2.html"
    email = WORK / "email2.html"
    mapp = WORK / "map.html"
    bt = WORK / "backtest.html"
    if site.exists():
        shutil.copy(site, OUTPUT / "dashboard.html")
        shutil.copy(site, PUBLIC / "index.html")
    if email.exists():
        shutil.copy(email, OUTPUT / "email.html")
        shutil.copy(email, PUBLIC / "email.html")
    if mapp.exists():
        shutil.copy(mapp, OUTPUT / "map_room.html")
        shutil.copy(mapp, PUBLIC / "map.html")
    if bt.exists():
        shutil.copy(bt, OUTPUT / "backtest.html")
        shutil.copy(bt, PUBLIC / "backtest.html")


def seed() -> None:
    from db import migrate, parse_asof, save_snapshot

    migrate()
    stage_from_data()
    data2 = load_json(DATA / "data2.json")
    if not data2:
        raise SystemExit("data/data2.json missing — cannot seed")
    asof = parse_asof(data2["asof"])
    html = (OUTPUT / "dashboard.html").read_text() if (OUTPUT / "dashboard.html").exists() else None
    email_html = (OUTPUT / "email.html").read_text() if (OUTPUT / "email.html").exists() else None
    map_html = (OUTPUT / "map_room.html").read_text() if (OUTPUT / "map_room.html").exists() else None
    save_snapshot(
        asof=asof,
        research_asof=asof,
        blobs=collect_blobs(),
        html=html,
        email_html=email_html,
        map_html=map_html,
        rows=data2.get("rows"),
    )
    print(f"seeded snapshot asof={asof}", flush=True)


def weekly() -> None:
    from db import latest_snapshot, migrate, parse_asof, previous_ratings, save_snapshot
    from strategy import write_copy

    migrate()
    prev = latest_snapshot()
    if prev:
        research_asof = stage_research_from_snapshot(prev)
    else:
        stage_from_data()
        d2 = load_json(WORK / "data2.json") or {}
        research_asof = str(d2.get("asof") or date.today())
    stage_prev(prev)

    public_url = os.environ.get("PUBLIC_URL", "https://ten-themes.vercel.app")
    (WORK / "link.txt").write_text(public_url.strip() + "\n")

    asof = None
    try:
        for script in FETCH:
            run_script(script)

        prices = load_json(WORK / "prices.json") or {}
        if len(prices) < MIN_PRICES:
            raise SystemExit(f"prices.py returned {len(prices)} tickers (need {MIN_PRICES})")

        data2 = load_json(WORK / "data2.json")
        if not data2:
            raise SystemExit("score2.py did not write data2.json")
        trades = sum(1 for r in data2["rows"] if r.get("trade"))
        if trades < MIN_TRADES:
            raise SystemExit(f"only {trades} option tickets (floor {MIN_TRADES}) — expiry selection likely regressed")

        if not (WORK / "layers.json").exists() and (DATA / "layers.json").exists():
            shutil.copy(DATA / "layers.json", WORK / "layers.json")
        for script in MAP:
            run_script(script)

        mac = load_json(WORK / "macro.json") or {}
        if len((mac.get("series") or {})) < 8:
            raise SystemExit(f"macro.py returned {len(mac.get('series') or {})} series (need 8+)")
        if not load_json(WORK / "factors.json"):
            raise SystemExit("factors.py did not write factors.json")

        asof = parse_asof(data2["asof"])
        prev_r = previous_ratings(asof)
        strategy, intro = write_copy(WORK, data2, prev_r, research_asof)

        try:
            run_script("world.py")  # news section for the digest; the desk doesn't depend on it
        except SystemExit as e:
            print(f"world.py failed ({e}) — digest goes out without the news section", flush=True)
        run_script("build_site2.py")
        run_script("build_email2.py")
        run_script("build_map.py")
        run_script("backtest.py")
        run_script("build_backtest.py")
        copy_artifacts()

        html = (PUBLIC / "index.html").read_text() if (PUBLIC / "index.html").exists() else None
        email_html = (PUBLIC / "email.html").read_text() if (PUBLIC / "email.html").exists() else None
        map_html = (PUBLIC / "map.html").read_text() if (PUBLIC / "map.html").exists() else None
        save_snapshot(
            asof=asof,
            research_asof=parse_asof(research_asof),
            blobs=collect_blobs(),
            strategy=strategy,
            intro=intro,
            html=html,
            email_html=email_html,
            map_html=map_html,
            rows=data2["rows"],
        )
        print(f"saved snapshot asof={asof} trades={trades}", flush=True)

        if os.environ.get("GITHUB_TOKEN"):
            from publish import publish_public
            publish_public(PUBLIC, asof=str(asof))
        else:
            print("GITHUB_TOKEN unset — skipped publish; HTML is in public/", flush=True)
    except (Exception, SystemExit) as err:  # SystemExit: the MIN_PRICES / MIN_TRADES / macro guards
        traceback.print_exc()
        fail_asof = asof or date.today()
        try:
            save_snapshot(asof=fail_asof, status="failed", error=str(err)[:2000], blobs=collect_blobs())
        except Exception:
            traceback.print_exc()
        alert_failure(err)
        raise

    mail_digest()


def mail_digest() -> None:
    """Email this week's digest. Runs only after a successful publish; a mail failure
    exits non-zero (visible in Railway) without marking the snapshot failed."""
    import mailer

    if not mailer.configured():
        print("mail not configured (MAIL_RELAY_URL/SECRET or GMAIL_APP_PASSWORD) — digest not emailed", flush=True)
        return
    params = WORK / "email2_params.json"
    if not params.exists():
        raise SystemExit("email2_params.json missing — digest not emailed")
    try:
        mailer.send_params(params)
    except Exception as e:
        raise SystemExit(f"digest email failed: {e}")


def alert_failure(err: BaseException) -> None:
    """Best-effort heads-up when the weekly job fails, so silence never means 'fine'."""
    try:
        import mailer

        if mailer.configured():
            mailer.send(
                f"Ten Themes weekly job FAILED — {date.today()}",
                f"The weekly job stopped before publishing; the site still shows last week.\n\n"
                f"Error: {str(err)[:1500]}\n\nLogs: Railway -> fortunate-healing -> finance -> Deployments.",
                to=os.environ.get("MAIL_TO") or "stuymusty@gmail.com",
            )
    except Exception:
        traceback.print_exc()


def main() -> None:
    p = argparse.ArgumentParser(description="Ten Themes weekly job")
    p.add_argument("--seed", action="store_true", help="load data/ into Postgres, do not fetch")
    args = p.parse_args()
    if args.seed:
        seed()
    else:
        weekly()


if __name__ == "__main__":
    main()
