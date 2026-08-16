UNIVERSE = {
 "AI Compute & Semiconductors": ["NVDA","AMD","AVGO","TSM","MU","ARM","MRVL"],
 "Power & Grid for AI Datacenters": ["VST","CEG","GEV","ETN","PWR","TLN","NRG"],
 "Defense Tech & Autonomy": ["PLTR","LMT","RTX","LDOS","KTOS","AVAV","LHX"],
 "Space & Satellite Economy": ["RKLB","ASTS","LUNR","IRDM","BA","HEI"],
 "Robotics & Physical AI": ["ISRG","TER","ROK","SYM","ZBRA","FANUY","SERV"],
 "Cybersecurity": ["CRWD","PANW","ZS","S","FTNT","OKTA","NET"],
 "Biotech & AI Drug Discovery": ["LLY","NVO","VRTX","RXRX","SDGR","TEM","ILMN","ABBV"],
 "Energy Storage & Critical Minerals": ["TSLA","ENPH","FLNC","ALB","MP","FSLR","EOSE"],
 "Fintech & Payment Rails": ["V","MA","COIN","HOOD","XYZ","PYPL","AFRM","CRCL"],
 "Enterprise Software & AI Agents": ["MSFT","GOOGL","CRM","NOW","SNOW","DDOG","MDB","AI"],
}
ALL = sorted({t for v in UNIVERSE.values() for t in v})
if __name__ == "__main__":
    print(len(ALL), ALL)
