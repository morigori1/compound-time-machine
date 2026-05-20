"""Phase 3b: Microsoft Global ML Building Footprints — fill OSM gaps."""
import sqlite3, urllib.request, json, hashlib, time, sys, os, math, gzip, io, csv, datetime

con = sqlite3.connect('/tmp/compounds.db'); cur = con.cursor()

DATASET_LINKS = "https://minedbuildings.z5.web.core.windows.net/global-buildings/dataset-links.csv"

def latlon_to_qk(lat, lon, zoom):
    sin_lat = math.sin(lat * math.pi / 180)
    x = int((lon + 180) / 360 * (1 << zoom))
    y = int((0.5 - math.log((1 + sin_lat) / (1 - sin_lat)) / (4 * math.pi)) * (1 << zoom))
    qk = ""
    for i in range(zoom, 0, -1):
        digit = 0; mask = 1 << (i - 1)
        if (x & mask) != 0: digit += 1
        if (y & mask) != 0: digit += 2
        qk += str(digit)
    return qk

# fetch dataset-links.csv (cached)
LINKS_LOCAL = '/tmp/ms_links.csv'
if not os.path.exists(LINKS_LOCAL):
    try:
        req = urllib.request.Request(DATASET_LINKS, headers={'User-Agent':'compounds-poc/0.3'})
        body = urllib.request.urlopen(req, timeout=30).read()
        with open(LINKS_LOCAL,'wb') as f: f.write(body)
        print(f"[MSB] dataset-links.csv DLed ({len(body)//1024} KB)")
    except Exception as e:
        print(f"[MSB ERR] dataset-links DL: {e}", file=sys.stderr); sys.exit(1)

# index by quadkey
qk_to_urls = {}
with open(LINKS_LOCAL, newline='') as f:
    reader = csv.DictReader(f)
    cols = reader.fieldnames
    for row in reader:
        qk = row.get('QuadKey','').strip()
        url = row.get('Url','').strip()
        if qk and url:
            qk_to_urls.setdefault(qk, []).append((row.get('Location',''), url, row.get('Size','')))
print(f"[MSB] indexed {len(qk_to_urls)} unique quadkeys, {sum(len(v) for v in qk_to_urls.values())} rows")

TARGETS = ['Dara Sakor', "O'Smach", 'Bavet']
rows = cur.execute("SELECT id, canonical_id, label, rep_lat, rep_lon FROM compound_candidate").fetchall()

for cand_id, can_id, label, lat, lon in rows:
    if not any(t in label for t in TARGETS): continue
    # try zoom levels 9 then 7
    found = None
    for zoom in [9, 8, 7, 6]:
        qk = latlon_to_qk(lat, lon, zoom)
        if qk in qk_to_urls:
            found = (zoom, qk, qk_to_urls[qk])
            break
    if not found:
        print(f"[MSB] {label}: no MS tile at any zoom for ({lat},{lon})")
        continue
    zoom, qk, links = found
    print(f"[MSB] {label}: quadkey={qk} zoom={zoom} files={len(links)}")
    for loc, url, sz in links:
        local = '/tmp/ms_' + qk + '_' + str(hash(url) & 0xffff) + '.tmp'
        if not os.path.exists(local):
            try:
                t0 = time.time()
                req = urllib.request.Request(url, headers={'User-Agent':'compounds-poc/0.3'})
                with urllib.request.urlopen(req, timeout=60) as r, open(local,'wb') as f:
                    while True:
                        chunk = r.read(1<<20)
                        if not chunk: break
                        f.write(chunk)
                print(f"[MSB] DL {loc:30s} {os.path.getsize(local)//1024} KB in {time.time()-t0:.1f}s")
            except Exception as e:
                print(f"[MSB ERR] DL {url}: {e}", file=sys.stderr); continue
        # parse: GeoJSONL gzipped
        d = 0.012
        bbox = (lat-d, lon-d, lat+d, lon+d)  # s,w,n,e
        sha = hashlib.sha256(open(local,'rb').read()).hexdigest()
        cur.execute("INSERT INTO source(kind, url, captured_at, archive_sha256) VALUES('ms_buildings', ?, ?, ?)",
                    (url, datetime.datetime.utcnow().isoformat()+'Z', sha))
        src_id = cur.lastrowid
        try:
            opener = gzip.open if url.endswith('.gz') else open
            mode = 'rt' if url.endswith('.gz') else 'rb'
            f = opener(local, mode, encoding='utf-8') if url.endswith('.gz') else open(local,'rb')
        except Exception as e:
            print(f"[MSB parse ERR] {e}", file=sys.stderr); continue
        kept = 0; total = 0
        try:
            for line in f:
                total += 1
                if isinstance(line, bytes): line = line.decode('utf-8', errors='ignore')
                line = line.strip()
                if not line: continue
                try: feat = json.loads(line)
                except: continue
                # Polygon coords
                geom = feat.get('geometry') or {}
                coords = geom.get('coordinates')
                if not coords: continue
                # get any coordinate for bbox check
                try:
                    if geom.get('type') == 'Polygon':
                        ring = coords[0]
                    elif geom.get('type') == 'MultiPolygon':
                        ring = coords[0][0]
                    else:
                        continue
                    lons = [p[0] for p in ring]
                    lats = [p[1] for p in ring]
                    clat = sum(lats)/len(lats); clon = sum(lons)/len(lons)
                except: continue
                if not (bbox[0] <= clat <= bbox[2] and bbox[1] <= clon <= bbox[3]): continue
                payload = json.dumps({'ms_id': feat.get('id') or feat.get('properties',{}).get('id'),
                                     'props': feat.get('properties',{}),
                                     'centroid':[clat,clon]}, ensure_ascii=False)
                cur.execute("""INSERT INTO observation(kind, captured_at, obs_lat, obs_lon, payload_json, source_id, archive_sha256, confidence_tier)
                               VALUES('ms_building', datetime('now'), ?, ?, ?, ?, ?, 'circumstantial')""",
                            (clat, clon, payload, src_id, sha))
                obs_id = cur.lastrowid
                cur.execute("INSERT INTO obs_link(observation_id, target_canonical_id, link_kind, weight, by) VALUES(?, ?, 'co_located', 0.3, 'auto:ms_buildings')",
                            (obs_id, can_id))
                kept += 1
                if kept >= 5000: break
        finally:
            f.close()
        con.commit()
        print(f"[MSB] {label[:38]:38s}: scanned {total} parsed -> kept {kept} in bbox")

con.close()
