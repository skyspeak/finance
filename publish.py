"""Deploy public/ to the existing Vercel project via the REST API (no Node required)."""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path


def _req(url: str, token: str, payload: dict, team: str | None) -> dict:
    if team:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}teamId={team}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise SystemExit(f"Vercel API {e.code}: {body}") from e


def publish_public(public_dir: Path) -> str:
    token = os.environ.get("VERCEL_TOKEN")
    if not token:
        raise SystemExit("VERCEL_TOKEN is required to publish")
    project = os.environ.get("VERCEL_PROJECT_ID") or os.environ.get("VERCEL_PROJECT_NAME", "ten-themes")
    team = os.environ.get("VERCEL_TEAM_ID") or os.environ.get("VERCEL_ORG_ID")

    files = []
    for path in sorted(public_dir.iterdir()):
        if not path.is_file():
            continue
        raw = path.read_bytes()
        files.append({
            "file": path.name,
            "encoding": "base64",
            "data": base64.b64encode(raw).decode("ascii"),
        })
    if not files:
        raise SystemExit(f"no files in {public_dir}")

    payload = {
        "name": os.environ.get("VERCEL_PROJECT_NAME", "ten-themes"),
        "project": project,
        "files": files,
        "target": "production",
        "projectSettings": {"framework": None},
    }
    # Files are already the site root (index.html, email.html)
    out = _req("https://api.vercel.com/v13/deployments", token, payload, team)
    url = out.get("url") or out.get("alias")
    print("published", url, flush=True)
    return ("https://" + url) if url and not str(url).startswith("http") else (url or "")
