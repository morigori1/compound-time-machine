"""Phase 3a: Overpass 3x3 split for high-density candidates."""
import sqlite3, urllib.request, urllib.parse, json, hashlib, time, sys, datetime

con = sqlite3.connect('/tmp/compounds.db'); cur = con.cursor()

# Only re-split candidates that hit the 500-out limit
TARGETS = ['Poipet', 'Jin Bei', 'Chinatown']

def overpass(bbox):
    s, w, n, e = bbox
    q = (f'[out:json][timeout:25];('
         f'way[building]({s},{w},{n},{e});'
         f'way[landuse=industrial]({s},{w},{n},{e});'
         f'way[landuse=commercial]({s},{w},{n},{e});'
         f'way[tourism=hotel]({s},{w},{n},{e});'
         f'way[amenity=casino]({s},{w},{n},{e});'
         f'way[leisure=resort]({s},{w},{n},{e});'
         f');out tags center 500;')
    data = urllib.parse.urlencode({'data': q}).encode()
    req = urllib.request.Request('https://overpass-api.de/api/interpreter',
        data=data, headers={'User-Agent':'compounds-poc/0.3','Accept':'application/json'})
    return urllib.request.urlopen(req, timeout=60).read()

rows = cur.execute("SELECT id, canonical_id, label, rep_lat, rep_lon FROM compound_candidate").fetchall()
total_new_grand = 0
for cand_id, can_id, label, lat, lon in rows:
    if not any(t in label for t in TARGETS): continue
    # seen osm_ids
    seen = set()
    for r in cur.execute("""SELECT o.payload_json FROM observation o JOIN obs_link l ON l.observation_id=o.id
                            WHERE l.target_canonical_id=? AND o.kind='osm'""", (can_id,)):
        try: seen.add(json.loads(r[0]).get('osm_id'))
        except: pass
    pre = len(seen)
    # 3x3 grid within outer d=0.012
    D = 0.012
    cell = D * 2 / 3  # full cell width
    new_total = 0
    for i in range(3):
        for j in range(3):
            sub_lat0 = lat - D + i * cell
            sub_lat1 = sub_lat0 + cell
            sub_lon0 = lon - D + j * cell
            sub_lon1 = sub_lon0 + cell
            bbox = (sub_lat0, sub_lon0, sub_lat1, sub_lon1)
            try: body = overpass(bbox)
            except Exception as e:
                print(f"[OSM-3x3 ERR] {label}[{i}{j}]: {e}", file=sys.stderr); time.sleep(2); continue
            sha = hashlib.sha256(body).hexdigest()
            try: data = json.loads(body)
            except: continue
            elements = data.get('elements', [])
            cur.execute("INSERT INTO source(kind, url, captured_at, archive_sha256) VALUES('osm_overpass_3x3', ?, ?, ?)",
                        ('https://overpass-api.de/api/interpreter', datetime.datetime.utcnow().isoformat()+'Z', sha))
            src_id = cur.lastrowid
            kept = 0
            for el in elements:
                oid = el.get('id')
                if oid in seen: continue
                seen.add(oid)
                c = el.get('center') or {}
                elat = c.get('lat') or el.get('lat')
                elon = c.get('lon') or el.get('lon')
                if elat is None or elon is None: continue
                tags = el.get('tags', {})
                payload = json.dumps({'osm_id':oid,'osm_type':el.get('type'),'tags':tags}, ensure_ascii=False)
                cur.execute("""INSERT INTO observation(kind, captured_at, obs_lat, obs_lon, payload_json, source_id, archive_sha256, confidence_tier)
                               VALUES('osm', datetime('now'), ?, ?, ?, ?, ?, 'circumstantial')""",
                            (elat, elon, payload, src_id, sha))
                obs_id = cur.lastrowid
                cur.execute("INSERT INTO obs_link(observation_id, target_canonical_id, link_kind, weight, by) VALUES(?, ?, 'co_located', 0.3, 'auto:osm_proximity_tiled')",
                            (obs_id, can_id))
                kept += 1
                new_total += 1
            time.sleep(0.7)
    con.commit()
    print(f"[OSM-3x3] {label[:38]:38s}: pre={pre} +new={new_total} -> total={len(seen)}")
    total_new_grand += new_total

print(f"\n[GRAND-NEW] {total_new_grand}")
print("--- per-candidate counts ---")
for r in cur.execute("""SELECT c.label, COUNT(l.id) FROM compound_candidate c
                        LEFT JOIN obs_link l ON l.target_canonical_id=c.canonical_id
                        LEFT JOIN observation o ON o.id=l.observation_id AND o.kind='osm'
                        GROUP BY c.id ORDER BY 2 DESC"""):
    print(f"  {r[1]:>5d}  {r[0]}")
con.close()
