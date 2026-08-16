#!/usr/bin/env python3
"""
Enrich insiders.json with actual Form 4 XML details.
The primary document field is 'xslF345X06/filename.xml' - strip the prefix.
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

MIN_INTERVAL = 0.13
SINCE_DATE = date(2026, 5, 18)

# All tickers to process
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

def make_request(url, text=False):
    headers = {
        'User-Agent': 'InsiderEnrichV2/1.0 research@example.com',
        'Accept-Encoding': 'gzip, deflate',
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            enc = resp.info().get('Content-Encoding', '')
            if enc == 'gzip':
                raw = gzip.decompress(raw)
            decoded = raw.decode('utf-8', errors='replace')
            if text:
                return decoded
            return json.loads(decoded)
    except Exception:
        return None

def get_cik_map():
    url = "https://www.sec.gov/files/company_tickers.json"
    time.sleep(MIN_INTERVAL)
    data = make_request(url)
    if not data:
        return {}
    mapping = {}
    for entry in data.values():
        ticker = entry.get('ticker', '').upper()
        cik = str(entry.get('cik_str', ''))
        if ticker:
            mapping[ticker] = cik
    return mapping

def fetch_form4_xml(cik_unpadded, accession, pdoc):
    """Fetch the Form 4 XML document."""
    acc_nd = accession.replace('-', '')
    # Strip xslF345X06/ prefix from pdoc
    if '/' in pdoc:
        xml_file = pdoc.split('/')[-1]
    else:
        xml_file = pdoc

    if not xml_file.endswith('.xml'):
        # Try common fallbacks
        xml_file = xml_file.replace('.htm', '.xml').replace('.html', '.xml')

    xml_url = f"https://www.sec.gov/Archives/edgar/data/{cik_unpadded}/{acc_nd}/{xml_file}"
    time.sleep(MIN_INTERVAL)
    return make_request(xml_url, text=True)

def parse_form4_xml(xml_text):
    """Parse Form 4 XML and return structured data."""
    if not xml_text or '<ownershipDocument>' not in xml_text:
        return None

    result = {}

    # Reporter name
    name_m = re.search(r'<rptOwnerName>\s*([^<]+)\s*</rptOwnerName>', xml_text)
    if name_m:
        result['name'] = name_m.group(1).strip()

    # Role
    is_director = re.search(r'<isDirector>\s*([^<]+)\s*</isDirector>', xml_text)
    is_officer = re.search(r'<isOfficer>\s*([^<]+)\s*</isOfficer>', xml_text)
    is_ten = re.search(r'<isTenPercentOwner>\s*([^<]+)\s*</isTenPercentOwner>', xml_text)
    officer_title = re.search(r'<officerTitle>\s*([^<]+)\s*</officerTitle>', xml_text)

    roles = []
    if is_director and is_director.group(1).strip() in ('1', 'true', 'True'):
        roles.append('Director')
    if is_officer and is_officer.group(1).strip() in ('1', 'true', 'True'):
        t = officer_title.group(1).strip() if officer_title else 'Officer'
        roles.append(t)
    if is_ten and is_ten.group(1).strip() in ('1', 'true', 'True'):
        roles.append('10% Owner')
    result['role'] = ', '.join(roles) if roles else 'Unknown'

    # Transactions (non-derivative)
    transactions = []
    nd_blocks = re.findall(r'<nonDerivativeTransaction>(.*?)</nonDerivativeTransaction>', xml_text, re.DOTALL)
    for block in nd_blocks:
        tx = {}
        date_m = re.search(r'<transactionDate>.*?<value>\s*([^<]+)\s*</value>', block, re.DOTALL)
        code_m = re.search(r'<transactionCode>\s*([^<]+)\s*</transactionCode>', block)
        shares_m = re.search(r'<transactionShares>.*?<value>\s*([^<]+)\s*</value>', block, re.DOTALL)
        price_m = re.search(r'<transactionPricePerShare>.*?<value>\s*([^<]+)\s*</value>', block, re.DOTALL)
        ad_m = re.search(r'<transactionAcquiredDisposedCode>.*?<value>\s*([^<]+)\s*</value>', block, re.DOTALL)

        if date_m: tx['date'] = date_m.group(1).strip()
        if code_m: tx['code'] = code_m.group(1).strip()
        if shares_m:
            try: tx['shares'] = float(shares_m.group(1).strip())
            except: pass
        if price_m:
            try: tx['price'] = float(price_m.group(1).strip())
            except: pass
        if ad_m: tx['acquired_disposed'] = ad_m.group(1).strip()
        if tx: transactions.append(tx)

    result['transactions'] = transactions
    return result

def build_note(details):
    """Build a human-readable note from parsed Form 4 data."""
    if not details:
        return "Form 4 filed; XML parse failed"

    txs = details.get('transactions', [])
    if not txs:
        return "Non-open-market transaction (grant/exercise/award)"

    sell_shares = 0; sell_value = 0
    buy_shares = 0; buy_value = 0

    for tx in txs:
        code = tx.get('code', '')
        shares = tx.get('shares', 0)
        price = tx.get('price', 0)
        ad = tx.get('acquired_disposed', '')

        is_sale = (ad == 'D' and code == 'S') or code == 'S'
        is_buy = (ad == 'A' and code in ('P',)) or code == 'P'
        is_grant = code in ('A', 'M', 'G', 'F', 'D', 'J', 'K', 'L', 'U', 'W', 'X', 'Z') and not is_sale

        if is_sale:
            sell_shares += shares
            if price: sell_value += shares * price
        elif is_buy:
            buy_shares += shares
            if price: buy_value += shares * price

    parts = []
    if sell_shares > 0:
        val_str = f"~${sell_value/1e6:.1f}M" if sell_value > 0 else "price N/A"
        parts.append(f"Sold {sell_shares:,.0f} sh ({val_str})")
    if buy_shares > 0:
        val_str = f"~${buy_value/1e6:.1f}M" if buy_value > 0 else "price N/A"
        parts.append(f"Bought {buy_shares:,.0f} sh ({val_str})")
    if not parts:
        codes = set(t.get('code','') for t in txs)
        parts.append(f"Non-open-market tx (codes: {','.join(sorted(codes))})")

    return "; ".join(parts)

def compute_signal_from_notables(notables, n_form4):
    """Determine signal from enriched notable entries."""
    total_sell_value = 0
    total_buy_value = 0
    has_dollar = False

    for n in notables:
        note = n.get('note', '')
        sell_m = re.search(r'Sold.*?\$([0-9.]+)M', note)
        buy_m = re.search(r'Bought.*?\$([0-9.]+)M', note)
        if sell_m:
            total_sell_value += float(sell_m.group(1))
            has_dollar = True
        if buy_m:
            total_buy_value += float(buy_m.group(1))
            has_dollar = True

    if has_dollar:
        if total_sell_value > 50:
            return "heavy selling"
        elif total_sell_value > 5:
            return "moderate selling"
        elif total_buy_value > total_sell_value and total_buy_value > 1:
            return "buying"
        elif total_sell_value > 0:
            return "moderate selling"
        return "quiet"
    else:
        if n_form4 >= 10: return "heavy selling"
        if n_form4 >= 5: return "moderate selling"
        if n_form4 >= 2: return "moderate selling"
        return "quiet"

def main():
    with open('/agent/workspace/insiders.json') as f:
        insiders = json.load(f)

    cik_map = get_cik_map()
    updated = 0

    for ticker in TICKERS:
        entry = insiders.get(ticker)
        if not entry or entry.get('error') or not entry.get('cik'):
            continue

        cik = entry.get('cik', cik_map.get(ticker, ''))
        if not cik:
            continue

        cik_padded = edgar.pad_cik(cik)
        cik_unpadded = str(int(cik))

        # Get submissions
        url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
        time.sleep(MIN_INTERVAL)
        subs = make_request(url)
        if not subs:
            continue

        recent = subs.get('filings', {}).get('recent', {})
        forms = recent.get('form', [])
        dates = recent.get('filingDate', [])
        accs = recent.get('accessionNumber', [])
        pdocs = recent.get('primaryDocument', [])

        # Collect Form 4s in window
        form4s = []
        for i, f in enumerate(forms):
            if f in ('4', '4/A'):
                d = dates[i] if i < len(dates) else ''
                if d >= SINCE_DATE.isoformat():
                    acc = accs[i] if i < len(accs) else ''
                    pdoc = pdocs[i] if i < len(pdocs) else ''
                    form4s.append({'date': d, 'accession': acc, 'pdoc': pdoc})

        # Fetch XML for first 3
        notables = []
        has_dollar = False

        for f4 in form4s[:3]:
            xml_text = fetch_form4_xml(cik_unpadded, f4['accession'], f4['pdoc'])
            details = parse_form4_xml(xml_text)
            note = build_note(details)

            n = {
                "insider": details['name'] if details and 'name' in details else "see filing",
                "role": details['role'] if details and 'role' in details else "see filing",
                "date": f4['date'],
                "note": note,
                "filing_url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik_unpadded}&type=4&dateb=&owner=include&count=40"
            }
            notables.append(n)

            if details and details.get('transactions'):
                for tx in details['transactions']:
                    if tx.get('price', 0) > 0:
                        has_dollar = True

        signal = compute_signal_from_notables(notables, entry.get('n_form4', 0))
        method = ("submissions_api_form4_xml_dollar_amounts_extracted"
                  if has_dollar else
                  "submissions_api_form4_xml_no_dollar_amounts_in_top3_filings")

        entry['notable'] = notables
        entry['signal'] = signal
        entry['method'] = method
        insiders[ticker] = entry
        updated += 1

        print(f"{ticker}: n={entry['n_form4']}, signal={signal}, dollar={has_dollar}", flush=True)
        for n in notables:
            print(f"  {n['date']} | {n['insider'][:30]} | {n['role'][:25]} | {n['note'][:70]}", flush=True)

    with open('/agent/workspace/insiders.json', 'w') as f:
        json.dump(insiders, f, indent=2)

    with open('/agent/workspace/insiders.json') as f:
        parsed = json.load(f)

    print(f"\nDone. Updated {updated} tickers. Total: {len(parsed)} in insiders.json", flush=True)

    # Stats
    signals = {}
    has_dollar = sum(1 for v in parsed.values() if 'dollar_amounts_extracted' in v.get('method',''))
    for v in parsed.values():
        s = v.get('signal', 'quiet')
        signals[s] = signals.get(s, 0) + 1
    print(f"Signals: {signals}", flush=True)
    print(f"Tickers with dollar amounts extracted: {has_dollar}", flush=True)

if __name__ == '__main__':
    main()
