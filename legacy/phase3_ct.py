"""Phase 3c: CT alternative — certspotter + Cloudflare DoH."""
import sqlite3, urllib.request, json, hashlib, time, sys, os, datetime

con = sqlite3.connect('/tmp/compounds.db'); cur = con.cursor()

# Domain candidates from open reporting / industry context
# (label_substring_to_match_candidate, primary_domain_to_probe)
PROBES = [
    ('Jin Bei',     'jinbei88.com'),
    ('Jin Bei',     'jinbei.com'),
    ('Huione',      'huione.com'),       # Huione (no compound match — global org)
    ('Huione',      'huionepay.com'),
    ('Huione',      'huione.cn'),
    ('Prince',      'princegroup.asia'),
    ('Prince',      'princeholding.com'),
    ('Dara Sakor',  'darasakor.com'),
    ('Dara Sakor',  'unionnex.com'),
    ('KK Park',     'shwekokko.com'),
    ('Poipet',      'poipet.com'),
    ('Bavet',       'bavet.com'),
]

# 1) certspotter (no API key needed for limited queries)
def certspotter(domain):
    url = f'https://api.certspotter.com/v1/issuances?domain={domain}&include_subdomains=true&expand=dns_names&expand=issuer'
    req = urllib.request.Request(url, headers={'User-Agent':'compounds-poc/0.3','Accept':'application/json'})
    return urllib.request.urlopen(req, timeout=20).read()

# 2) Cloudflare DoH for liveness check
def doh(domain):
    url = f'https://cloudflare-dns.com/dns-query?name={domain}&type=A'
    req = urllib.request.Request(url, headers={'User-Agent':'compounds-poc/0.3','Accept':'application/dns-json'})
    return urllib.request.urlopen(req, timeout=15).read()

for label_match, domain in PROBES:
    # candidate match
    m = cur.execute("SELECT id, canonical_id FROM compound_candidate WHERE label LIKE ?", (f'%{label_match}%',)).fetchone()
    cand_can = m[1] if m else None
    # certspotter
    try:
        body = certspotter(domain)
        sha = hashlib.sha256(body).hexdigest()
        try: data = json.loads(body)
        except: data = []
        cur.execute("INSERT INTO source(kind, url, captured_at, archive_sha256) VALUES('certspotter', ?, ?, ?)",
                    (f'https://api.certspotter.com/v1/issuances?domain={domain}', datetime.datetime.utcnow().isoformat()+'Z', sha))
        src_id = cur.lastrowid
        cnt = 0
        seen_names = set()
        for entry in data[:60]:
            for nm in entry.get('dns_names', [])[:10]:
                if nm in seen_names: continue
                seen_names.add(nm)
                payload = json.dumps({'common_name': nm, 'issuer': entry.get('issuer',{}).get('name'),
                                     'not_before': entry.get('not_before'), 'probe_domain': domain,
                                     'label': label_match, 'src':'certspotter'}, ensure_ascii=False)
                cur.execute("""INSERT INTO observation(kind, captured_at, payload_json, source_id, archive_sha256, confidence_tier)
                               VALUES('domain_cert', datetime('now'), ?, ?, ?, 'circumstantial')""",
                            (payload, src_id, sha))
                obs_id = cur.lastrowid
                if cand_can:
                    cur.execute("INSERT INTO obs_link(observation_id, target_canonical_id, link_kind, weight, by) VALUES(?, ?, 'name_match', 0.2, 'auto:certspotter')",
                                (obs_id, cand_can))
                cnt += 1
        con.commit()
        print(f"[CS ] {label_match:14s} {domain:28s}: {cnt} unique cert names")
    except Exception as e:
        print(f"[CS ERR] {domain}: {type(e).__name__}: {e}", file=sys.stderr)

    # DoH liveness
    try:
        body = doh(domain)
        sha = hashlib.sha256(body).hexdigest()
        d = json.loads(body)
        answers = d.get('Answer', [])
        ips = [a.get('data') for a in answers if a.get('type') == 1]
        cur.execute("INSERT INTO source(kind, url, captured_at, archive_sha256) VALUES('cloudflare_doh', ?, ?, ?)",
                    (f'https://cloudflare-dns.com/dns-query?name={domain}', datetime.datetime.utcnow().isoformat()+'Z', sha))
        src_id = cur.lastrowid
        payload = json.dumps({'domain': domain, 'A_records': ips, 'status': d.get('Status'),
                             'label': label_match}, ensure_ascii=False)
        cur.execute("""INSERT INTO observation(kind, captured_at, payload_json, source_id, archive_sha256, confidence_tier)
                       VALUES('dns_liveness', datetime('now'), ?, ?, ?, 'verified')""",
                    (payload, src_id, sha))
        obs_id = cur.lastrowid
        if cand_can:
            cur.execute("INSERT INTO obs_link(observation_id, target_canonical_id, link_kind, weight, by) VALUES(?, ?, 'name_match', 0.15, 'auto:doh')",
                        (obs_id, cand_can))
        con.commit()
        live = "LIVE" if ips else "no-A"
        print(f"[DoH] {label_match:14s} {domain:28s}: {live} {ips[:3]}")
    except Exception as e:
        print(f"[DoH ERR] {domain}: {type(e).__name__}: {e}", file=sys.stderr)
    time.sleep(0.7)

print("--- summary ---")
for q in [
    ("dns_liveness", "SELECT COUNT(*) FROM observation WHERE kind='dns_liveness'"),
    ("  LIVE",     "SELECT COUNT(*) FROM observation WHERE kind='dns_liveness' AND payload_json LIKE '%A_records%' AND payload_json NOT LIKE '%\"A_records\": []%'"),
    ("domain_cert","SELECT COUNT(*) FROM observation WHERE kind='domain_cert'"),
]:
    print(f"  {q[0]:>15s}: {cur.execute(q[1]).fetchone()[0]}")
con.close()
