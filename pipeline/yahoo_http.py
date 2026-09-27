"""Yahoo GET with backoff. Unauthenticated chart calls 429 easily."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

def get_json(url, headers, timeout=25, tries=7):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 500, 502, 503) and i < tries - 1:
                wait = min(120, 20 * (i + 1))
                print(f"  http {e.code} wait {wait}s  {url.split('?', 1)[0]}", flush=True)
                time.sleep(wait)
                continue
            raise
        except Exception as e:
            last = e
            if i < tries - 1:
                wait = min(30, 4 * (i + 1))
                print(f"  http err wait {wait}s  {e}", flush=True)
                time.sleep(wait)
                continue
            raise
    raise last
