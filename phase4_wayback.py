"""Phase 4: Esri Wayback historical satellite — build a per-candidate imagery timeline.

For each compound candidate we fetch the z15 center tile of every ~quarterly Wayback
release, hash it, and keep the releases where the imagery actually changed. That gives
a "time machine" track per candidate: empty land -> compound build-out.
"""
import sqlite3, urllib.request, json, hashlib, time, sys, os, math, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, 'compounds.db')
CONFIG_URL = 'https://s3-us-west-2.amazonaws.com/config.maptiles.arcgis.com/waybackconfig.json'
UA = 'compounds-poc/0.4'
TILE_Z = 15           # ~1.2km tile — matches candidate uncertainty radius
MIN_GAP_DAYS = 0      # scan every Wayback release — the hash diff keeps only distinct imagery

con = sqlite3.connect(DB)
cur = con.cursor()

cur.executescript("""
CREATE TABLE IF NOT EXISTS imagery_release (
    id INTEGER PRIMARY KEY,
    candidate_id INTEGER,
    canonical_id INTEGER,
    release_num INTEGER,
    release_date TEXT,
    tile_z INTEGER, tile_x INTEGER, tile_y INTEGER,
    tile_url TEXT,
    tile_sha256 TEXT,
    is_distinct INTEGER
);
CREATE INDEX IF NOT EXISTS idx_imagery_cand ON imagery_release(candidate_id);
""")
cur.execute("DELETE FROM imagery_release")
con.commit()


def deg2tile(lat, lon, z):
    n = 1 << z
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)
    return x, y


def http(url, timeout=25):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    return urllib.request.urlopen(req, timeout=timeout).read()


# 1) fetch + curate releases
print('[WB] fetching wayback config ...')
cfg = json.loads(http(CONFIG_URL, timeout=40))
rels_all = sorted(
    ((int(k), v['itemTitle'][-11:-1], v['itemURL']) for k, v in cfg.items()),
    key=lambda r: r[1])
curated = []
last_dt = None
for num, date, tmpl in rels_all:
    try:
        dt = datetime.date.fromisoformat(date)
    except ValueError:
        continue
    if last_dt is None or (dt - last_dt).days >= MIN_GAP_DAYS or num == rels_all[-1][0]:
        curated.append((num, date, tmpl))
        last_dt = dt
print(f'[WB] {len(rels_all)} releases -> {len(curated)} curated (>= {MIN_GAP_DAYS}d gap), '
      f'{curated[0][1]} .. {curated[-1][1]}')

# 2) per candidate, walk the curated releases and detect imagery changes.
#    Center the change-detection tile on the observed building-density cluster when
#    available (poi table) — the reported coordinate can be ~1-1.5 km off the compound.
rows = cur.execute(
    "SELECT id, canonical_id, label, rep_lat, rep_lon FROM compound_candidate").fetchall()
has_poi = cur.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name='poi'").fetchone() is not None
grand_distinct = 0
for cand_id, can_id, label, rep_lat, rep_lon in rows:
    lat, lon, ctr = rep_lat, rep_lon, 'rep'
    if has_poi:
        cl = cur.execute("""SELECT lat, lon FROM poi
                            WHERE candidate_id=? AND name='中心建物群'""", (cand_id,)).fetchone()
        if cl:
            lat, lon, ctr = cl[0], cl[1], 'cluster'
    tx, ty = deg2tile(lat, lon, TILE_Z)
    last_hash = None
    distinct = 0
    for num, date, tmpl in curated:
        url = (tmpl.replace('{level}', str(TILE_Z))
                   .replace('{row}', str(ty))
                   .replace('{col}', str(tx)))
        try:
            body = http(url, timeout=20)
        except Exception as e:
            print(f'  [WB ERR] {label[:24]} {date}: {e}', file=sys.stderr)
            time.sleep(0.5)
            continue
        sha = hashlib.sha256(body).hexdigest()
        is_distinct = 1 if sha != last_hash else 0
        if is_distinct:
            distinct += 1
            last_hash = sha
        cur.execute("""INSERT INTO imagery_release
            (candidate_id, canonical_id, release_num, release_date,
             tile_z, tile_x, tile_y, tile_url, tile_sha256, is_distinct)
            VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (cand_id, can_id, num, date, TILE_Z, tx, ty, tmpl, sha, is_distinct))
        time.sleep(0.12)
    con.commit()
    grand_distinct += distinct
    print(f'  [WB] {label[:34]:34s}: {len(curated):3d} releases -> {distinct:2d} distinct frames '
          f'(center={ctr})')

print(f'[WB] done. {grand_distinct} distinct imagery frames across {len(rows)} candidates.')
con.close()
