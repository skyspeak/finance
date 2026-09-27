"""Publish public/ by committing it to the site repo; Vercel deploys every push to main.

The site repo (default skyspeak/industry) is Git-connected to the Vercel project, so
this is the only publish path — a direct Vercel deploy would be overwritten by the
next push. Uses the GitHub Git Data API (stdlib only) to write all pages as one commit.

Env:
  GITHUB_TOKEN     fine-grained token, Contents: read & write on the site repo only
  PUBLISH_REPO     owner/name, default skyspeak/industry
  PUBLISH_BRANCH   default main
  PUBLISH_DIR      path inside the repo, default public
"""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

API = "https://api.github.com"


def _api(method: str, path: str, token: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "ten-themes-publish",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise SystemExit(f"GitHub API {method} {path} -> {e.code}: {body}") from e


def publish_public(public_dir: Path, asof: str | None = None) -> str:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN is required to publish")
    repo = os.environ.get("PUBLISH_REPO", "skyspeak/industry")
    branch = os.environ.get("PUBLISH_BRANCH", "main")
    prefix = os.environ.get("PUBLISH_DIR", "public").strip("/")

    pages = sorted(p for p in public_dir.iterdir() if p.is_file() and p.suffix == ".html")
    if not pages:
        raise SystemExit(f"no .html files in {public_dir}")

    head = _api("GET", f"/repos/{repo}/git/ref/heads/{branch}", token)["object"]["sha"]
    base_tree = _api("GET", f"/repos/{repo}/git/commits/{head}", token)["tree"]["sha"]

    entries = []
    for page in pages:
        blob = _api("POST", f"/repos/{repo}/git/blobs", token, {
            "content": base64.b64encode(page.read_bytes()).decode("ascii"),
            "encoding": "base64",
        })
        path = f"{prefix}/{page.name}" if prefix else page.name
        entries.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})

    tree = _api("POST", f"/repos/{repo}/git/trees", token, {"base_tree": base_tree, "tree": entries})["sha"]
    if tree == base_tree:
        print(f"publish: {repo}@{branch} already up to date ({head[:7]})", flush=True)
        return head

    label = asof or date.today().isoformat()
    commit = _api("POST", f"/repos/{repo}/git/commits", token, {
        "message": f"Weekly refresh: {label}\n\nPublished by ten-themes job.py ({len(entries)} pages).",
        "tree": tree,
        "parents": [head],
    })["sha"]
    # Not forced: if someone pushed meanwhile this fails rather than discarding their commit.
    _api("PATCH", f"/repos/{repo}/git/refs/heads/{branch}", token, {"sha": commit, "force": False})
    print(f"published {len(entries)} pages to {repo}@{branch} as {commit[:7]}; Vercel deploys from there", flush=True)
    return commit
