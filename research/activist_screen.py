#!/usr/bin/env python3
"""
Task 2 v6: SC 13D activist screen - CIK-only matching.
In crawler.idx the CIK belongs to the SUBJECT company.
We match ONLY by exact CIK to avoid false positives from short tickers.
"""

import sys
import json
import time
import re
import urllib.request
import urllib.error
import gzip
from datetime import date

sys.path.insert(0, '/agent/workspace/skills/SEC EDGAR API')
import _edgar as edgar

SINCE_DATE = date(2025, 8, 16)
TODAY = date(2026, 8, 16)
MIN_INTERVAL = 0.13

TICKERS = [
    "NVDA","AMD","AVGO","TSM","MU","ARM","MRVL",
    "VST","CEG","GEV","ETN","PWR","TLN","NRG",
    "PLTR","LMT","RTX","LDOS","KTOS","AVAV","LHX","RKLB","ASTS","LUNR","IRDM","BA","HEI",
    "ISRG","ABBV","TER","ROK","SYM","ZBRA",
    "CRWD","PANW","ZS","S","FTNT","OKTA","NET",
    "LLY","VRTX","RXRX","SDGR","TEM","ILMN",
    "TSLA","ENPH","FLNC","ALB","MP","FSLR","EOSE",
    "V","MA","COIN","HOOD","XYZ","PYPL","AFRM","CRCL",
    "MSFT","GOOGL","CRM","NOW","SNOW","DDOG","MDB","AI",
]

KNOWN_ACTIVISTS = [
    'elliott', 'starboard', 'valueact', 'jana partners', 'third point',
    'trian', 'icahn', 'ancora', 'politan', 'irenic', 'sachem head',
    'pershing square', 'corvex', 'legion partners', 'blue harbour',
    'inclusive capital', 'engine capital', 'standard general',
    'greenlight', 'glenview', 'water island', 'barington',
    'land & buildings', 'oasis management', 'cevian',
    'de shaw', 'd.e. shaw', 'appaloosa', 'soroban',
    'blue whirl', 'dalton investments', 'engaged capital',
    'mfn partners', 'spring creek', 'mantle ridge',
]

def make_request(url, text=False):
    headers = {
        'User-Agent': 'ActivistScreenV6/1.0 research@example.com',
        'Accept-Encoding': 'gzip, deflate',
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read()
            enc = resp.info().get('Content-Encoding', '')
            if enc == 'gzip':
                raw = gzip.decompress(raw)
            decoded = raw.decode('utf-8', errors='replace')
            if text:
                return decoded
            return json.loads(decoded)
    except urllib.error.HTTPError as e:
        return None
    except Exception:
        return None

def get_cik_map():
    url = "https://www.sec.gov/files/company_tickers.json"
    time.sleep(MIN_INTERVAL)
    data = make_request(url)
    if not data:
        return {}, {}, {}
    ticker_to_cik = {}
    cik_to_ticker = {}
    cik_to_name = {}
    for entry in data.values():
        ticker = entry.get('ticker', '').upper()
        cik = str(entry.get('cik_str', ''))
        name = entry.get('title', '').upper()
        if ticker:
            ticker_to_cik[ticker] = cik
            cik_to_ticker[cik] = ticker
            cik_to_name[cik] = name
    return ticker_to_cik, cik_to_ticker, cik_to_name

def parse_crawler_idx(text, since_date, today, universe_cik_set):
    """
    Parse crawler.idx and return only entries where subject CIK is in our universe.
    CIK match is exact and lstrip('0') normalized.
    """
    results = []
    lines = text.split('\n')

    for line in lines:
        if 'SCHEDULE 13D' not in line:
            continue

        parts = re.split(r'\s{2,}', line.strip())
        if len(parts) < 4:
            continue

        form_idx = None
        for i, p in enumerate(parts):
            if 'SCHEDULE 13D' in p:
                form_idx = i
                break
        if form_idx is None:
            continue

        subject_name = ' '.join(parts[:form_idx]).strip()
        form_type = parts[form_idx].strip()
        remaining = parts[form_idx+1:]
        if len(remaining) < 3:
            continue

        raw_cik = remaining[0].strip()
        filing_date = remaining[1].strip()
        index_url = remaining[2].strip() if len(remaining) > 2 else ''

        if not re.match(r'^\d+$', raw_cik):
            continue
        if not re.match(r'\d{4}-\d{2}-\d{2}', filing_date):
            continue

        # Normalize CIK: remove leading zeros
        subject_cik = str(int(raw_cik))

        # Only keep if in our universe
        if subject_cik not in universe_cik_set:
            continue

        try:
            fd = date.fromisoformat(filing_date)
        except:
            continue

        if fd < since_date or fd > today:
            continue

        results.append({
            'subject_name': subject_name,
            'subject_cik': subject_cik,
            'form_type': form_type,
            'filing_date': filing_date,
            'index_url': index_url,
        })

    return results

def get_all_13d_from_indexes(universe_cik_set):
    quarters = [
        ('2025', 'QTR3'),
        ('2025', 'QTR4'),
        ('2026', 'QTR1'),
        ('2026', 'QTR2'),
        ('2026', 'QTR3'),
    ]
    all_filings = []
    for year, qtr in quarters:
        url = f"https://www.sec.gov/Archives/edgar/full-index/{year}/{qtr}/crawler.idx"
        print(f"  Fetching {year}/{qtr} crawler.idx...", flush=True)
        time.sleep(MIN_INTERVAL)
        text = make_request(url, text=True)
        if not text:
            print(f"    -> Not available", flush=True)
            continue
        filings = parse_crawler_idx(text, SINCE_DATE, TODAY, universe_cik_set)
        print(f"    -> {len(filings)} universe matches in window", flush=True)
        all_filings.extend(filings)
    return all_filings

def extract_filer_from_header(header_text):
    """Extract FILED BY company name and CIK."""
    if not header_text:
        return None, None

    filer_name = None
    filer_cik = None

    # Find FILED BY section
    # Format:
    # FILED BY:
    #
    # COMPANY DATA:
    #     COMPANY CONFORMED NAME:    SomeActivist
    #     CENTRAL INDEX KEY:         1234567
    filed_match = re.search(
        r'FILED BY:.*?COMPANY CONFORMED NAME:\s*([^\n]+)',
        header_text, re.DOTALL
    )
    if filed_match:
        filer_name = filed_match.group(1).strip()

    cik_match = re.search(
        r'FILED BY:.*?CENTRAL INDEX KEY:\s*(\d+)',
        header_text, re.DOTALL
    )
    if cik_match:
        filer_cik = cik_match.group(1).strip().lstrip('0') or '0'

    return filer_name, filer_cik

def fetch_filing_txt(index_url):
    """Fetch main filing .txt to get header. First 3500 chars only."""
    txt_url = re.sub(r'-index\.htm.*$', '.txt', index_url)
    time.sleep(MIN_INTERVAL)
    text = make_request(txt_url, text=True)
    if text:
        return text[:3500]
    return None

def is_known_activist(name):
    if not name:
        return False
    nl = name.lower()
    return any(a in nl for a in KNOWN_ACTIVISTS)

def main():
    print("Loading CIK map...", flush=True)
    ticker_to_cik, cik_to_ticker, cik_to_name = get_cik_map()

    # Build universe CIK set (unpadded)
    universe_cik_to_ticker = {}
    for t in TICKERS:
        cik = ticker_to_cik.get(t)
        if cik:
            normalized = str(int(cik))
            universe_cik_to_ticker[normalized] = t

    print(f"Universe: {len(TICKERS)} tickers, {len(universe_cik_to_ticker)} CIKs resolved", flush=True)
    print("Sample CIKs:", list(universe_cik_to_ticker.items())[:5], flush=True)

    print("\nFetching SCHEDULE 13D/A filings from quarterly crawler.idx (CIK match only)...", flush=True)
    universe_cik_set = set(universe_cik_to_ticker.keys())
    filings_13d = get_all_13d_from_indexes(universe_cik_set)
    print(f"\nTotal universe hits: {len(filings_13d)}", flush=True)

    # Fetch filer info for each hit
    hits = []
    for filing in filings_13d:
        ticker = universe_cik_to_ticker.get(filing['subject_cik'], 'UNKNOWN')
        print(f"  {ticker} | {filing['subject_name']} | {filing['form_type']} | {filing['filing_date']}", flush=True)

        header = fetch_filing_txt(filing['index_url'])
        filer_name, filer_cik = extract_filer_from_header(header)
        known = is_known_activist(filer_name)

        print(f"    Filer: {filer_name} | known={known}", flush=True)

        entry = {
            "ticker": ticker,
            "subject_company": filing['subject_name'],
            "subject_cik": filing['subject_cik'],
            "filer_name": filer_name or "unknown",
            "filer_cik": filer_cik or "",
            "form_type": filing['form_type'],
            "filing_date": filing['filing_date'],
            "accession_url": filing['index_url'],
            "is_known_activist": known,
            "activist_agenda": None
        }
        hits.append(entry)

    # Sort by ticker, date
    hits.sort(key=lambda x: (x['ticker'], x['filing_date']))

    output_path = '/agent/workspace/activists.json'
    with open(output_path, 'w') as f:
        json.dump(hits, f, indent=2)

    with open(output_path) as f:
        parsed = json.load(f)

    print(f"\nDone. {len(parsed)} SC 13D entries in activists.json", flush=True)
    known_hits = [h for h in parsed if h.get('is_known_activist')]
    print(f"Known activist hits: {len(known_hits)}", flush=True)
    print("\nAll entries:")
    for h in parsed:
        print(f"  {h['ticker']} | {h['filer_name']} | {h['form_type']} | {h['filing_date']} | known={h['is_known_activist']}", flush=True)

if __name__ == '__main__':
    main()
