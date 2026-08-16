#!/usr/bin/env python3
"""
Enrich activists.json with activist_agenda notes from research.
Also deduplicate to show most recent filing per (ticker, filer) pair
and add context for notable positions.
"""

import json

AGENDAS = {
    # (ticker, filer_fragment) -> agenda note
    ('EOSE', 'Cerberus'): "Cerberus holds ~31% stake via Series B Preferred Stock with board designation rights; partnering to launch Frontier Power USA JV with $100M commitment and backing a $150M rights offering to scale zinc-based long-duration energy storage.",
    ('FLNC', 'Qatar'): "Qatar Investment Authority (QIA) holds ~8.9% of Fluence Energy Class A shares; filed 13D upon a partial sale of 2.87M shares at $21 on May 15 2026; passive sovereign wealth fund stake, not an activist campaign.",
    ('SYM', 'SOFTBANK'): "SoftBank Group holds ~31.3% of Symbotic Class A shares across multiple Vision Fund vehicles; sold 5.59M shares at $50.42 in May 2026 but remains largest outside shareholder; strategic investor, not typical activist.",
    ('SYM', 'Cohen'): "Richard B. Cohen (Symbotic founder/executive) filed 13D/A updating personal stake; insider/founder position rather than external activist.",
    ('SYM', 'Walmart'): "Walmart holds strategic stake in Symbotic; relationship stems from warehouse-automation partnership; filed 13D/A updating beneficial ownership in connection with supply/commercial arrangement.",
    ('RKLB', 'Khosla'): "Khosla Ventures (Vinod Khosla) holds ~9% of Rocket Lab via VK Services LLC; early venture investor distributing shares to LP base over time; not an activist, long-term strategic holder.",
    ('RKLB', 'VK Services'): "VK Services LLC (Vinod Khosla personal vehicle) holds RKLB shares as part of ongoing LP distributions from Khosla Ventures V; passive long-term VC investor.",
    ('RKLB', 'Beck'): "Peter Beck (Rocket Lab CEO/founder) filed 13D/A updating his personal beneficial ownership; founder/executive disclosure.",
    ('ASTS', 'Avellan'): "Abel Avellan (AST SpaceMobile CEO/founder) filing updates to his personal 13D reflecting share sales or awards; founder/executive position, not activist.",
    ('ASTS', 'AMERICAN TOWER'): "American Tower holds strategic stake in AST SpaceMobile tied to commercial/infrastructure partnership for satellite connectivity; filed 13D/A updating ownership.",
    ('ASTS', 'Vodafone'): "Vodafone Ventures holds strategic ASTS stake as part of satellite connectivity partnership agreement; not an activist position.",
    ('ASTS', 'Mikitani'): "Hiroshi Mikitani (Rakuten founder) holds ASTS stake as part of Rakuten's satellite connectivity partnership with AST SpaceMobile; strategic partner position.",
    ('LUNR', 'Ghaffarian'): "Kamal Ghaffarian (Intuitive Machines co-founder/chairman) updating personal beneficial ownership; founder/executive position rather than external activist.",
    ('IRDM', 'Baralonco'): "Baralonco Ltd holds strategic stake in Iridium Communications; filing updates reflect ownership changes in a large passive shareholder block.",
    ('RXRX', 'Mubadala'): "Mubadala Investment Company (UAE sovereign wealth fund) holds strategic stake in Recursion Pharmaceuticals; invested as part of Recursion's AI-drug-discovery financing round; passive SWF investor.",
    ('TEM', 'Tempus AI'): "Tempus AI Inc. itself filed the 13D; this is typically a company buying back its own shares or a miscellaneous internal filing — not an external activist.",
    ('MP', 'Litinsky'): "James Litinsky (MP Materials CEO/co-founder) updating personal 13D reflecting his beneficial ownership; founder/executive position.",
    ('LLY', 'ELI LILLY'): "Eli Lilly itself filed a 13D — likely a cross-ownership or buyback-related disclosure; not an external activist campaign.",
    ('AVAV', 'Altitude'): "Altitude V Holdings LLC disclosed a 13D/A for AeroVironment; appears to be an investment fund building or adjusting a position in AVAV.",
}

def main():
    with open('/agent/workspace/activists.json') as f:
        hits = json.load(f)

    # Deduplicate: keep latest filing per (ticker, filer_name)
    deduped = {}
    for h in hits:
        key = (h['ticker'], h['filer_name'])
        if key not in deduped or h['filing_date'] > deduped[key]['filing_date']:
            deduped[key] = h

    hits_deduped = sorted(deduped.values(), key=lambda x: (x['ticker'], x['filing_date']))

    # Add agendas
    for h in hits_deduped:
        ticker = h['ticker']
        filer = h['filer_name']
        agenda = None
        for (t, f_frag), note in AGENDAS.items():
            if t == ticker and f_frag.lower() in filer.lower():
                agenda = note
                break
        h['activist_agenda'] = agenda

    # Write back
    with open('/agent/workspace/activists.json', 'w') as f:
        json.dump(hits_deduped, f, indent=2)

    # Validate
    with open('/agent/workspace/activists.json') as f:
        parsed = json.load(f)

    print(f"activists.json: {len(parsed)} unique positions", flush=True)
    print("\nSummary:")
    for h in parsed:
        agenda_snippet = (h['activist_agenda'] or 'no note')[:80]
        print(f"  {h['ticker']} | {h['filer_name'][:40]} | {h['form_type']} | {h['filing_date']}", flush=True)
        print(f"    agenda: {agenda_snippet}", flush=True)

if __name__ == '__main__':
    main()
