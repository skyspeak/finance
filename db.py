"""Postgres snapshot store. Railway injects DATABASE_URL when Postgres is attached."""
from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any, Optional

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
  id            bigserial PRIMARY KEY,
  asof          date NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  status        text NOT NULL DEFAULT 'success',
  error         text,
  research_asof date,
  analysts      jsonb,
  insiders      jsonb,
  activists     jsonb,
  hedgefunds    jsonb,
  privates      jsonb,
  events        jsonb,
  ipos          jsonb,
  prices        jsonb,
  enrich        jsonb,
  tech          jsonb,
  hist          jsonb,
  options       jsonb,
  data          jsonb,
  data2         jsonb NOT NULL DEFAULT '{}'::jsonb,
  strategy      text,
  intro         text,
  html          text,
  email_html    text,
  map_html      text,
  macro         jsonb,
  sectors       jsonb,
  factors       jsonb,
  layers        jsonb,
  UNIQUE (asof)
);

CREATE TABLE IF NOT EXISTS ratings (
  asof       date NOT NULL,
  ticker     text NOT NULL,
  name       text,
  theme      text,
  rating     text NOT NULL,
  composite  numeric,
  squeeze    integer,
  last_px    numeric,
  PRIMARY KEY (asof, ticker)
);

CREATE INDEX IF NOT EXISTS ratings_ticker_asof_idx ON ratings (ticker, asof DESC);
"""


def _dsn() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is required (Railway Postgres).")
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    return url


def connect():
    return psycopg.connect(_dsn(), row_factory=dict_row, autocommit=True)


def migrate(conn=None) -> None:
    own = conn is None
    if own:
        conn = connect()
    try:
        conn.execute(SCHEMA)
        for col, typ in (
            ("map_html", "text"),
            ("macro", "jsonb"),
            ("sectors", "jsonb"),
            ("factors", "jsonb"),
            ("layers", "jsonb"),
        ):
            conn.execute(f"ALTER TABLE snapshots ADD COLUMN IF NOT EXISTS {col} {typ}")
    finally:
        if own:
            conn.close()


def latest_snapshot(conn=None, *, before: Optional[date] = None) -> Optional[dict]:
    own = conn is None
    if own:
        conn = connect()
    try:
        if before:
            row = conn.execute(
                "SELECT * FROM snapshots WHERE status = 'success' AND asof < %s ORDER BY asof DESC LIMIT 1",
                (before,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM snapshots WHERE status = 'success' ORDER BY asof DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None
    finally:
        if own:
            conn.close()


def previous_ratings(asof: date, conn=None) -> dict[str, dict]:
    """ticker -> {rating, composite} from the latest snapshot strictly before asof."""
    own = conn is None
    if own:
        conn = connect()
    try:
        rows = conn.execute(
            """
            SELECT ticker, rating, composite
            FROM ratings
            WHERE asof = (
              SELECT MAX(asof) FROM snapshots
              WHERE status = 'success' AND asof < %s
            )
            """,
            (asof,),
        ).fetchall()
        return {r["ticker"]: {"rating": r["rating"], "composite": float(r["composite"] or 0)} for r in rows}
    finally:
        if own:
            conn.close()


def _jb(obj: Any):
    return None if obj is None else Jsonb(obj)


def save_snapshot(
    *,
    asof: date,
    status: str = "success",
    error: Optional[str] = None,
    research_asof: Optional[date] = None,
    blobs: Optional[dict] = None,
    strategy: Optional[str] = None,
    intro: Optional[str] = None,
    html: Optional[str] = None,
    email_html: Optional[str] = None,
    map_html: Optional[str] = None,
    rows: Optional[list] = None,
    conn=None,
) -> None:
    own = conn is None
    if own:
        conn = connect()
    blobs = blobs or {}
    try:
        conn.execute(
            """
            INSERT INTO snapshots (
              asof, status, error, research_asof,
              analysts, insiders, activists, hedgefunds, privates, events, ipos,
              prices, enrich, tech, hist, options, data, data2,
              macro, sectors, factors, layers,
              strategy, intro, html, email_html, map_html
            ) VALUES (
              %s, %s, %s, %s,
              %s, %s, %s, %s, %s, %s, %s,
              %s, %s, %s, %s, %s, %s, %s,
              %s, %s, %s, %s,
              %s, %s, %s, %s, %s
            )
            ON CONFLICT (asof) DO UPDATE SET
              created_at = now(),
              status = EXCLUDED.status,
              error = EXCLUDED.error,
              research_asof = EXCLUDED.research_asof,
              analysts = EXCLUDED.analysts,
              insiders = EXCLUDED.insiders,
              activists = EXCLUDED.activists,
              hedgefunds = EXCLUDED.hedgefunds,
              privates = EXCLUDED.privates,
              events = EXCLUDED.events,
              ipos = EXCLUDED.ipos,
              prices = EXCLUDED.prices,
              enrich = EXCLUDED.enrich,
              tech = EXCLUDED.tech,
              hist = EXCLUDED.hist,
              options = EXCLUDED.options,
              data = EXCLUDED.data,
              data2 = EXCLUDED.data2,
              macro = EXCLUDED.macro,
              sectors = EXCLUDED.sectors,
              factors = EXCLUDED.factors,
              layers = EXCLUDED.layers,
              strategy = EXCLUDED.strategy,
              intro = EXCLUDED.intro,
              html = EXCLUDED.html,
              email_html = EXCLUDED.email_html,
              map_html = EXCLUDED.map_html
            """,
            (
                asof, status, error, research_asof,
                _jb(blobs.get("analysts")), _jb(blobs.get("insiders")),
                _jb(blobs.get("activists")), _jb(blobs.get("hedgefunds")),
                _jb(blobs.get("privates")), _jb(blobs.get("events")),
                _jb(blobs.get("ipos")),
                _jb(blobs.get("prices")), _jb(blobs.get("enrich")),
                _jb(blobs.get("tech")), _jb(blobs.get("hist")),
                _jb(blobs.get("options")), _jb(blobs.get("data")),
                _jb(blobs.get("data2") or {}),
                _jb(blobs.get("macro")), _jb(blobs.get("sectors")),
                _jb(blobs.get("factors")), _jb(blobs.get("layers")),
                strategy, intro, html, email_html, map_html,
            ),
        )
        conn.execute("DELETE FROM ratings WHERE asof = %s", (asof,))
        if status == "success" and rows:
            with conn.cursor() as cur:
                for r in rows:
                    cur.execute(
                        """
                        INSERT INTO ratings (asof, ticker, name, theme, rating, composite, squeeze, last_px)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            asof, r.get("ticker"), r.get("name"), r.get("theme"),
                            r.get("rating"), r.get("composite"), r.get("squeeze"), r.get("last"),
                        ),
                    )
    finally:
        if own:
            conn.close()


def parse_asof(value) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return date.fromisoformat(str(value)[:10])
