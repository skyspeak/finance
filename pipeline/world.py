"""What happened in the world this week, from major outlets' RSS -> world.json

No API keys and no LLM: headlines and standfirsts from a fixed set of outlets, grouped
when several outlets cover the same story, and ranked by how many outlets carried it
(breadth of coverage stands in for importance), then by recency. The email digest
(build_email2.py) leads with this.
"""
import datetime as dt
import email.utils
import html
import json
import re
import time
import urllib.request
import xml.etree.ElementTree as ET

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ten-themes-weekly/1.0"
WINDOW_DAYS = 7
FEEDS = [  # (outlet, section, url)
    ("BBC", "world", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("NYT", "world", "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"),
    ("Guardian", "world", "https://www.theguardian.com/world/rss"),
    ("Al Jazeera", "world", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("NPR", "world", "https://feeds.npr.org/1004/rss.xml"),
    ("FT", "world", "https://www.ft.com/world?format=rss"),
    ("BBC", "economy", "https://feeds.bbci.co.uk/news/business/rss.xml"),
    ("NYT", "economy", "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml"),
    ("Guardian", "economy", "https://www.theguardian.com/business/rss"),
    ("NPR", "economy", "https://feeds.npr.org/1006/rss.xml"),
    ("CNBC", "economy", "https://www.cnbc.com/id/100727362/device/rss/rss.html"),
    ("BBC", "tech", "https://feeds.bbci.co.uk/news/technology/rss.xml"),
]
TAKE = {"world": 8, "economy": 5, "tech": 3}
STOP = set("""a an the and or but of to in on at for from by with as is are was were be been being has have had
it its this that these those after before over under into about against amid says said say new will would could
can may might not no than then more most how why what who when where which while up down out off just also
their they them he she his her we our you your us per vs via than first last week year years""".split())


def _text(s):
    s = re.sub(r"<[^>]+>", " ", html.unescape(s or ""))
    return re.sub(r"\s+", " ", s).strip()


def _summary(s, limit=230):
    s = _text(s)
    if len(s) <= limit:
        return s
    cut = s[:limit]
    end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
    return cut[:end + 1] if end > 80 else cut.rsplit(" ", 1)[0] + "…"


def _tokens(s):
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) > 2 and w not in STOP}


def _when(s):
    try:
        d = email.utils.parsedate_to_datetime(s)
        return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
    except Exception:
        return None


def fetch(outlet, section, url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml,application/xml,*/*"})
    with urllib.request.urlopen(req, timeout=25) as r:
        root = ET.fromstring(r.read())
    items = []
    for it in root.iter("item"):
        title = _text(it.findtext("title"))
        when = _when(it.findtext("pubDate") or "")
        if not title or not when:
            continue
        items.append({"title": title, "link": (it.findtext("link") or "").strip(), "outlet": outlet,
                      "section": section, "summary": _summary(it.findtext("description")),
                      "published": when, "tok": _tokens(title + " " + _text(it.findtext("description"))[:200])})
    return items


def cluster(items, threshold=0.16):
    """Greedy single-link grouping of the same story across outlets.

    Similarity is IDF-weighted Jaccard over headline + standfirst words, so sharing
    rare words ("MI5", "Fairford") counts far more than sharing common ones."""
    import math
    df = {}
    for it in items:
        for w in it["tok"]:
            df[w] = df.get(w, 0) + 1
    idf = {w: math.log((len(items) + 1) / c) for w, c in df.items()}
    groups = []
    for it in sorted(items, key=lambda x: x["published"], reverse=True):
        best, score = None, 0.0
        for g in groups:
            for m in g:
                u = sum(idf[w] for w in it["tok"] | m["tok"]) or 1
                j = sum(idf[w] for w in it["tok"] & m["tok"]) / u
                if j > score:
                    best, score = g, j
        if best is not None and score >= threshold:
            best.append(it)
        else:
            groups.append([it])
    return groups


def build():
    now = dt.datetime.now(dt.timezone.utc)
    since = now - dt.timedelta(days=WINDOW_DAYS)
    items, ok, failed = [], 0, []
    for outlet, section, url in FEEDS:
        try:
            got = [i for i in fetch(outlet, section, url) if i["published"] >= since]
            items += got
            ok += 1
            print(f"  ok   {outlet:10s} {section:8s} {len(got):3d} items", flush=True)
        except Exception as e:
            failed.append(outlet + "/" + section)
            print(f"  FAIL {outlet:10s} {section:8s} {str(e)[:70]}", flush=True)
        time.sleep(0.3)

    out = {"asof": now.date().isoformat(), "window_days": WINDOW_DAYS, "feeds_ok": ok,
           "feeds_failed": failed, "sections": {}}
    for section, n in TAKE.items():
        groups = cluster([i for i in items if i["section"] == section])
        ranked = []
        for g in groups:
            outlets = sorted({m["outlet"] for m in g})
            latest = max(m["published"] for m in g)
            age_days = (now - latest).total_seconds() / 86400
            lead = max(g, key=lambda m: (len(m["summary"]), -abs((m["published"] - latest).total_seconds())))
            ranked.append({
                "title": lead["title"], "link": lead["link"], "outlet": lead["outlet"],
                "summary": lead["summary"], "outlets": outlets, "n_outlets": len(outlets),
                "published": latest.date().isoformat(),
                "_rank": len(outlets) * 3 + len(g) * 0.5 - age_days * 0.6,
            })
        ranked.sort(key=lambda r: r["_rank"], reverse=True)
        seen, picked = set(), []
        for r in ranked:  # the same outlet can file one story twice under different headlines
            key = r["title"].lower()[:60]
            if key in seen:
                continue
            seen.add(key)
            r.pop("_rank")
            picked.append(r)
            if len(picked) == n:
                break
        out["sections"][section] = picked

    json.dump(out, open("world.json", "w"), indent=1)
    print(f"saved world.json — {ok}/{len(FEEDS)} feeds, "
          + ", ".join(f"{k} {len(v)}" for k, v in out["sections"].items()))
    for k, v in out["sections"].items():
        for r in v:
            print(f"  [{k}] ({r['n_outlets']}) {r['title'][:90]}")


if __name__ == "__main__":
    build()
