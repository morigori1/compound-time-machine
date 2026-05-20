"""Phase 3d: OFAC SDN wallet/legal_entity extraction."""
import sqlite3, urllib.request, json, hashlib, time, sys, os, datetime
import xml.etree.ElementTree as ET

con = sqlite3.connect('/tmp/compounds.db'); cur = con.cursor()

# Ensure wallet & legal_entity tables exist
cur.executescript("""
CREATE TABLE IF NOT EXISTS legal_entity (
    id INTEGER PRIMARY KEY,
    canonical_id INTEGER,
    jurisdiction TEXT,
    reg_no TEXT,
    name TEXT,
    sdn_uid INTEGER,
    programs TEXT,
    sanctioned_on TEXT,
    source_id INTEGER
);
CREATE TABLE IF NOT EXISTS wallet (
    id INTEGER PRIMARY KEY,
    canonical_id INTEGER,
    chain TEXT,
    address TEXT,
    first_seen TEXT,
    label TEXT,
    frozen_by TEXT,
    sdn_uid INTEGER,
    source_id INTEGER
);
""")
con.commit()

# Download SDN.xml
LOCAL = '/tmp/sdn.xml'
URL = 'https://www.treasury.gov/ofac/downloads/sdn.xml'
if not os.path.exists(LOCAL) or os.path.getsize(LOCAL) < 1000000:
    t0 = time.time()
    req = urllib.request.Request(URL, headers={'User-Agent':'compounds-poc/0.3'})
    with urllib.request.urlopen(req, timeout=60) as r, open(LOCAL,'wb') as f:
        while True:
            chunk = r.read(1<<20)
            if not chunk: break
            f.write(chunk)
    print(f"[OFAC] DL {os.path.getsize(LOCAL)//1024} KB in {time.time()-t0:.1f}s")
else:
    print(f"[OFAC] cached {os.path.getsize(LOCAL)//1024} KB")

sha = hashlib.sha256(open(LOCAL,'rb').read()).hexdigest()
cur.execute("INSERT INTO source(kind, url, captured_at, archive_sha256) VALUES('ofac_sdn_xml', ?, ?, ?)",
            (URL, datetime.datetime.utcnow().isoformat()+'Z', sha))
src_id = cur.lastrowid
con.commit()
print(f"[OFAC] sha={sha[:12]} src_id={src_id}")

# Parse
tree = ET.parse(LOCAL)
root = tree.getroot()
ns = ''
# strip namespace if present
tag = root.tag
if tag.startswith('{'):
    ns = tag.split('}')[0] + '}'

def text(el, name):
    e = el.find(ns + name)
    return e.text if e is not None else None

# Match patterns
NAME_RE = ['PRINCE', 'JIN BEI', 'HUIONE', 'DARA SAKOR', 'KK PARK', 'SHWE KOKKO',
           'GOLDEN FORTUNE', 'WARP DATA', 'CHANG WEI', 'PRINCE HOLDING', 'UNION DEVELOPMENT']

KH_MM_match = 0
crypto_match = 0
name_match = 0
total = 0

def jget(can_id, label_match):
    """get canonical for compound match"""
    r = cur.execute("SELECT canonical_id FROM compound_candidate WHERE label LIKE ?", (f'%{label_match}%',)).fetchone()
    return r[0] if r else None

for entry in root.findall(ns + 'sdnEntry'):
    total += 1
    uid = text(entry, 'uid')
    fn = text(entry, 'firstName') or ''
    ln = text(entry, 'lastName') or ''
    sdn_type = text(entry, 'sdnType') or ''
    name = (fn + ' ' + ln).strip()
    progs = []
    pl = entry.find(ns + 'programList')
    if pl is not None:
        for p in pl.findall(ns + 'program'):
            if p.text: progs.append(p.text)
    # akaList
    akas = []
    al = entry.find(ns + 'akaList')
    if al is not None:
        for a in al.findall(ns + 'aka'):
            fn2 = text(a, 'firstName') or ''
            ln2 = text(a, 'lastName') or ''
            akas.append((fn2 + ' ' + ln2).strip())
    haystack = (name + ' ' + ' '.join(akas)).upper()
    # check addresses for KH/MM
    al2 = entry.find(ns + 'addressList')
    countries = set()
    if al2 is not None:
        for a in al2.findall(ns + 'address'):
            c = text(a, 'country')
            if c: countries.add(c)
    is_kh_mm = bool(countries & {'Cambodia','Burma','Myanmar'})
    # check digital currency addresses
    crypto_addrs = []
    il = entry.find(ns + 'idList')
    if il is not None:
        for ide in il.findall(ns + 'id'):
            it = text(ide, 'idType') or ''
            iv = text(ide, 'idNumber') or ''
            if 'Digital Currency' in it:
                crypto_addrs.append((it, iv))
    has_name = any(p in haystack for p in NAME_RE)
    if not (has_name or is_kh_mm or crypto_addrs and (is_kh_mm or has_name)):
        # skip uninteresting entries; but we still want crypto+match
        if not (has_name or is_kh_mm):
            continue
    if crypto_addrs: crypto_match += 1
    if is_kh_mm: KH_MM_match += 1
    if has_name: name_match += 1
    # Determine which candidate to link
    link_can = None
    for sub in ['Prince','Jin Bei','Dara Sakor','KK Park']:
        if sub.upper() in haystack:
            link_can = jget(None, sub); break
    # Insert legal_entity
    cur.execute("INSERT INTO canonical_entity(kind) VALUES('legal_entity')")
    can_id = cur.lastrowid
    cur.execute("""INSERT INTO legal_entity(canonical_id, jurisdiction, name, sdn_uid, programs, sanctioned_on, source_id)
                   VALUES(?, ?, ?, ?, ?, ?, ?)""",
                (can_id, ';'.join(sorted(countries)), name, int(uid) if uid else None,
                 ';'.join(progs), '2025-10-14' if 'PRINCE' in haystack else None, src_id))
    le_id = cur.lastrowid
    # Insert aliases
    for nm in [name] + akas:
        if nm.strip():
            cur.execute("INSERT INTO alias(canonical_id, surface, lang, confidence, source_id) VALUES(?, ?, ?, ?, ?)",
                        (can_id, nm.strip(), 'en', 'verified', src_id))
    # Insert wallets
    for it, iv in crypto_addrs:
        chain = it.replace('Digital Currency Address -','').strip()
        cur.execute("""INSERT INTO wallet(canonical_id, chain, address, label, frozen_by, sdn_uid, source_id)
                       VALUES(?, ?, ?, ?, ?, ?, ?)""",
                    (can_id, chain, iv, name, 'OFAC', int(uid) if uid else None, src_id))
    # Insert observation + link to candidate if matched
    payload = json.dumps({'sdn_uid': uid, 'name': name, 'aka': akas[:5], 'countries': sorted(countries),
                         'programs': progs, 'crypto': crypto_addrs}, ensure_ascii=False)
    cur.execute("""INSERT INTO observation(kind, captured_at, payload_json, source_id, archive_sha256, confidence_tier)
                   VALUES('sanction_entry', datetime('now'), ?, ?, ?, 'verified')""",
                (payload, src_id, sha))
    obs_id = cur.lastrowid
    if link_can:
        cur.execute("INSERT INTO obs_link(observation_id, target_canonical_id, link_kind, weight, by) VALUES(?, ?, 'attributes', 0.8, 'auto:ofac_name')",
                    (obs_id, link_can))

con.commit()
print(f"[OFAC] scanned {total} entries; name_match={name_match} kh_mm={KH_MM_match} crypto_match={crypto_match}")
print("--- legal_entity counts ---")
for r in cur.execute("SELECT COUNT(*), jurisdiction FROM legal_entity GROUP BY jurisdiction ORDER BY 1 DESC LIMIT 10"):
    print(f"  {r[0]:>4d}  {r[1]}")
print("--- wallets by chain ---")
for r in cur.execute("SELECT chain, COUNT(*) FROM wallet GROUP BY chain ORDER BY 2 DESC"):
    print(f"  {r[1]:>4d}  {r[0]}")
print("--- sample legal_entities matching watch list ---")
for r in cur.execute("""SELECT name, jurisdiction, programs FROM legal_entity
                        WHERE upper(name) LIKE '%PRINCE%' OR upper(name) LIKE '%JIN BEI%'
                           OR upper(name) LIKE '%HUIONE%' OR upper(name) LIKE '%DARA%'
                           OR upper(name) LIKE '%GOLDEN FORTUNE%'
                        LIMIT 15"""):
    print(f"  {r[0][:50]:50s} | {r[1]:20s} | {r[2][:40]}")
con.close()
