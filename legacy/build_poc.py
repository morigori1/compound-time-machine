"""Compound Candidate POC builder."""
import sqlite3, json, urllib.request, urllib.parse, hashlib, time, os, datetime, sys, shutil

OUT = '/sessions/quirky-trusting-archimedes/mnt/outputs'
SS  = '/sessions/quirky-trusting-archimedes/mnt/SS'
DB_WORK = '/tmp/compounds.db'
DB_OUT  = os.path.join(OUT, 'compounds.db')
HTML_OUT = os.path.join(OUT, 'dashboard.html')

SCHEMA = """
DROP TABLE IF EXISTS obs_link;
DROP TABLE IF EXISTS observation;
DROP TABLE IF EXISTS event;
DROP TABLE IF EXISTS capacity_estimate;
DROP TABLE IF EXISTS compound_candidate;
DROP TABLE IF EXISTS alias;
DROP TABLE IF EXISTS source;
DROP TABLE IF EXISTS place;
DROP TABLE IF EXISTS canonical_entity;

CREATE TABLE canonical_entity (id INTEGER PRIMARY KEY, kind TEXT NOT NULL, created_at TEXT DEFAULT (datetime('now')));
CREATE TABLE alias (id INTEGER PRIMARY KEY, canonical_id INTEGER, surface TEXT NOT NULL, lang TEXT, script TEXT, confidence TEXT, source_id INTEGER);
CREATE TABLE place (id INTEGER PRIMARY KEY, name_canonical TEXT, admin_country TEXT, admin_state TEXT, centroid_lat REAL, centroid_lon REAL);
CREATE TABLE compound_candidate (id INTEGER PRIMARY KEY, canonical_id INTEGER, label TEXT, place_id INTEGER, rep_lat REAL, rep_lon REAL, uncertainty_m INTEGER, kind_hypothesis TEXT, first_seen TEXT, last_seen TEXT, status TEXT, notes TEXT);
CREATE TABLE source (id INTEGER PRIMARY KEY, kind TEXT, url TEXT, captured_at TEXT, archive_uri TEXT, archive_sha256 TEXT, risk_to_operator INTEGER DEFAULT 0);
CREATE TABLE observation (id INTEGER PRIMARY KEY, kind TEXT NOT NULL, captured_at TEXT, obs_lat REAL, obs_lon REAL, payload_json TEXT, source_id INTEGER, archive_uri TEXT, archive_sha256 TEXT, confidence_tier TEXT);
CREATE TABLE obs_link (id INTEGER PRIMARY KEY, observation_id INTEGER, target_canonical_id INTEGER, link_kind TEXT, weight REAL, by TEXT, at TEXT DEFAULT (datetime('now')));
CREATE TABLE event (id INTEGER PRIMARY KEY, kind TEXT, happened_on TEXT, resolution TEXT, place_id INTEGER, candidate_id INTEGER, summary TEXT, source_id INTEGER);
CREATE TABLE capacity_estimate (id INTEGER PRIMARY KEY, candidate_id INTEGER, as_of TEXT, low INTEGER, mid INTEGER, high INTEGER, method TEXT, inputs_json TEXT);
CREATE INDEX idx_obs_link_target ON obs_link(target_canonical_id);
CREATE INDEX idx_obs_kind ON observation(kind);
CREATE INDEX idx_event_candidate ON event(candidate_id);
"""

SEEDS = [
    ("KK Park / Shwe Kokko area", "MM", "Kayin (Karen)", 16.7100, 98.5440, "scam",
     "corroborated", "Reuters/AFP/GI-TOC で繰り返し名指し、タイ-ミャンマー国境(Moei川対岸)",
     [("KK Park","en"),("KK园区","zh"),("Shwe Kokko","en"),("ရွှေကုက္ကိုလ်","my")]),
    ("Jin Bei compound (Sihanoukville)", "KH", "Preah Sihanouk", 10.6273, 103.5183, "scam",
     "corroborated", "OFAC 2025-10 制裁 (Jin Bei Group)",
     [("Jin Bei","en"),("金贝","zh"),("ជីនបី","km")]),
    ("Chinatown compound (Otres)", "KH", "Preah Sihanouk", 10.6028, 103.5288, "scam",
     "corroborated", "GI-TOC / Humanity Research / Reuters",
     [("Chinatown Sihanoukville","en"),("中国城","zh")]),
    ("Dara Sakor (UDG)", "KH", "Koh Kong", 11.0660, 102.9710, "sez",
     "circumstantial", "中国系大型SEZ。Prince Group関連報道、空港・港・カジノ複合",
     [("Dara Sakor","en"),("七星海","zh"),("ដារាសាគរ","km"),("Union Development Group","en")]),
    ("O'Smach border zone", "KH", "Oddar Meanchey", 14.3996, 103.9658, "mixed",
     "speculative", "タイ-カンボジア国境、国境カジノ集積",
     [("O'Smach","en"),("អូរស្មាច់","km")]),
    ("Poipet O'Neang corridor", "KH", "Banteay Meanchey", 13.6601, 102.5670, "mixed",
     "circumstantial", "タイ-カンボジア国境、2025年タイ側電力遮断対象",
     [("Poipet","en"),("Paoy Paet","en"),("ប៉ោយប៉ែត","km"),("波贝","zh")]),
    ("Bavet border zone", "KH", "Svay Rieng", 11.0892, 105.9921, "mixed",
     "circumstantial", "カンボジア-ベトナム国境、カジノ集積",
     [("Bavet","en"),("បាវិត","km")]),
]

def init_schema():
    if os.path.exists(DB_WORK):
        try: os.remove(DB_WORK)
        except OSError: pass
    con = sqlite3.connect(DB_WORK)
    con.executescript(SCHEMA)
    con.commit()
    return con

def seed(con):
    cur = con.cursor()
    cur.execute("INSERT INTO source(kind, url, captured_at) VALUES('seed_note', NULL, datetime('now'))")
    seed_src = cur.lastrowid
    for label, country, state, lat, lon, kind, status, notes, aliases in SEEDS:
        cur.execute("INSERT INTO canonical_entity(kind) VALUES('compound')")
        can_id = cur.lastrowid
        cur.execute("INSERT INTO place(name_canonical, admin_country, admin_state, centroid_lat, centroid_lon) VALUES(?,?,?,?,?)",
                    (state, country, state, lat, lon))
        pid = cur.lastrowid
        cur.execute("""INSERT INTO compound_candidate
            (canonical_id, label, place_id, rep_lat, rep_lon, uncertainty_m, kind_hypothesis, first_seen, last_seen, status, notes)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (can_id, label, pid, lat, lon, 800, kind, "2018-01-01", "2026-05-19", status, notes))
        for surface, lang in aliases:
            cur.execute("INSERT INTO alias(canonical_id, surface, lang, confidence, source_id) VALUES(?,?,?,?,?)",
                        (can_id, surface, lang, "corroborated", seed_src))
    con.commit()

def overpass(bbox):
    s, w, n, e = bbox
    q = (f'[out:json][timeout:25];('
         f'way[building]({s},{w},{n},{e});'
         f'way[landuse=industrial]({s},{w},{n},{e});'
         f'way[landuse=commercial]({s},{w},{n},{e});'
         f'way[tourism=hotel]({s},{w},{n},{e});'
         f'way[amenity=casino]({s},{w},{n},{e});'
         f'way[leisure=resort]({s},{w},{n},{e});'
         f');out tags center 300;')
    url = 'https://overpass-api.de/api/interpreter'
    data = urllib.parse.urlencode({'data': q}).encode()
    req = urllib.request.Request(url, data=data, headers={
        'User-Agent': 'compounds-poc/0.1', 'Accept': 'application/json'})
    return urllib.request.urlopen(req, timeout=60).read()

def fetch_osm(con):
    cur = con.cursor()
    rows = cur.execute("SELECT id, canonical_id, label, rep_lat, rep_lon FROM compound_candidate").fetchall()
    for cand_id, can_id, label, lat, lon in rows:
        d = 0.006
        bbox = (lat-d, lon-d, lat+d, lon+d)
        try:
            body = overpass(bbox)
        except Exception as e:
            print(f"[OSM ERR] {label}: {e}", file=sys.stderr); time.sleep(3); continue
        sha = hashlib.sha256(body).hexdigest()
        try: data = json.loads(body)
        except Exception:
            print(f"[OSM parse err] {label}", file=sys.stderr); continue
        elements = data.get('elements', [])
        cur.execute("INSERT INTO source(kind, url, captured_at, archive_sha256) VALUES('osm_overpass', ?, ?, ?)",
                    ('https://overpass-api.de/api/interpreter',
                     datetime.datetime.utcnow().isoformat() + 'Z', sha))
        src_id = cur.lastrowid
        kept = 0
        for el in elements:
            c = el.get('center') or {}
            elat = c.get('lat') or el.get('lat')
            elon = c.get('lon') or el.get('lon')
            if elat is None or elon is None: continue
            tags = el.get('tags', {})
            payload = json.dumps({'osm_id': el.get('id'), 'osm_type': el.get('type'), 'tags': tags}, ensure_ascii=False)
            cur.execute("""INSERT INTO observation
                (kind, captured_at, obs_lat, obs_lon, payload_json, source_id, archive_sha256, confidence_tier)
                VALUES('osm', datetime('now'), ?, ?, ?, ?, ?, 'circumstantial')""",
                (elat, elon, payload, src_id, sha))
            obs_id = cur.lastrowid
            cur.execute("INSERT INTO obs_link(observation_id, target_canonical_id, link_kind, weight, by) VALUES(?, ?, 'co_located', 0.3, 'auto:osm_proximity')",
                        (obs_id, can_id))
            kept += 1
        con.commit()
        print(f"[OSM] {label[:38]:38s}: {kept:3d} elements (sha={sha[:8]})")
        time.sleep(1.5)

DASHBOARD = r"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<title>Compound Candidate POC — Mekong</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
body{margin:0;font-family:system-ui,-apple-system,sans-serif;background:#0e1116;color:#e6e6e6}
#app{display:grid;grid-template-columns:380px 1fr;height:100vh}
#side{overflow-y:auto;padding:14px;border-right:1px solid #222}
#map{height:100vh}
h1{font-size:14px;margin:0 0 6px;color:#9cd}
h2{font-size:11px;color:#888;margin:18px 0 6px;text-transform:uppercase;letter-spacing:.08em}
small{color:#777}
.card{background:#161a22;border:1px solid #2a3140;border-radius:6px;padding:10px;margin-bottom:8px;cursor:pointer}
.card:hover{border-color:#4a82c4}
.card .label{font-weight:600;color:#fff;font-size:13px}
.card .meta{font-size:11px;color:#9aa;margin-top:3px}
.badge{display:inline-block;font-size:10px;padding:2px 6px;border-radius:3px;margin-right:4px;line-height:1.4}
.b-scam{background:#5a1a1a;color:#fbb}
.b-sez{background:#1a3a5a;color:#bcf}
.b-mixed{background:#3a3a1a;color:#fec}
.b-casino,.b-hotel,.b-unknown{background:#2a2a2a;color:#ccc}
.b-verified{background:#1a5a2a;color:#bfb}
.b-corroborated{background:#1a4a5a;color:#bdf}
.b-circumstantial{background:#5a4a1a;color:#fec}
.b-speculative{background:#3a2a3a;color:#fbe}
.stat{color:#7cf;font-size:11px}
.alias{font-size:11px;color:#aaa;margin-top:4px}
.alias span{margin-right:6px}
.layers{font-size:11px;color:#9aa;line-height:1.7}
.layers .impl{color:#9fc}
.layers .stub{color:#777}
</style></head>
<body><div id="app"><div id="side">
<h1>Compound Candidate POC — Mekong border zones</h1>
<small>Public OSINT only. 座標は近似(報道エリア中心)。観測=OSM proximity.</small>
<h2>Candidates</h2><div id="list"></div>
<h2>Schema layers (POC状態)</h2>
<div class="layers">
<div class="impl">● canonical_entity / alias</div>
<div class="impl">● compound_candidate (notes付き)</div>
<div class="impl">● observation / obs_link (proximityのみ)</div>
<div class="impl">● source (archive_sha256付き)</div>
<div class="stub">○ event / capacity_estimate</div>
<div class="stub">○ legal_entity / role_tenure</div>
<div class="stub">○ wallet / domain / web_fingerprint</div>
<div class="stub">○ rescue_record / sanction_action</div>
</div>
<h2>Caveats</h2>
<div class="layers stub">
座標精度: ±800m (uncertainty_m)。<br>
観測リンクは 'co_located' 仮説、用途確定ではない。<br>
OSMはボランティアデータで、コンパウンド境界は不明確。
</div></div><div id="map"></div></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const candidates = __CANDIDATES__;
const map = L.map('map').setView([12.5,104.0], 6);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OpenStreetMap',maxZoom:18}).addTo(map);
const colors = {scam:'#e44',sez:'#48c',mixed:'#fc4',casino:'#aaa',hotel:'#9c9',unknown:'#888'};
candidates.forEach(c=>{
  L.circle([c.lat,c.lon],{radius:800, color:colors[c.kind]||'#888', weight:1, fillOpacity:0.05}).addTo(map);
  const m = L.circleMarker([c.lat,c.lon],{radius:9, color:colors[c.kind]||'#888', weight:2, fillColor:colors[c.kind]||'#888', fillOpacity:0.6}).addTo(map);
  const aliasHtml = c.aliases.map(a=>`<span><b>${a[0]}</b> <small>(${a[1]||'?'})</small></span>`).join('');
  m.bindPopup(`<div style="font:13px system-ui"><b>${c.label}</b><br>
    <span style="color:#888">${c.country}/${c.state}</span><br>
    kind: <b>${c.kind}</b> · status: <b>${c.status}</b><br>
    obs(OSM): <b>${c.obs_count}</b><br>
    <div style="margin-top:6px;font-size:11px">${aliasHtml}</div>
    <div style="margin-top:6px;font-size:11px;color:#555">${c.notes||''}</div></div>`);
  c.observations.forEach(o=>{
    const tags = o[2].tags||{};
    let lab='';
    if(tags.building) lab='building';
    if(tags.tourism==='hotel') lab='hotel';
    if(tags.amenity==='casino') lab='casino';
    if(tags.landuse==='industrial') lab='industrial';
    if(tags.landuse==='commercial') lab='commercial';
    if(tags.leisure==='resort') lab='resort';
    L.circleMarker([o[0],o[1]],{radius:2,color:'#5af',weight:0,fillColor:'#5af',fillOpacity:0.55}).addTo(map).bindTooltip(`${lab}<br>${JSON.stringify(tags)}`,{direction:'top'});
  });
});
const list = document.getElementById('list');
candidates.forEach(c=>{
  const div=document.createElement('div'); div.className='card';
  div.innerHTML = `<div class="label">${c.label}</div>
    <div class="meta">
      <span class="badge b-${c.kind}">${c.kind}</span>
      <span class="badge b-${c.status}">${c.status}</span>
      <span class="stat">OSM obs: ${c.obs_count}</span></div>
    <div class="meta">${c.country} · ${c.state}</div>
    <div class="alias">${c.aliases.map(a=>a[0]).join(' / ')}</div>`;
  div.onclick=()=>{ map.setView([c.lat,c.lon],15); };
  list.appendChild(div);
});
</script></body></html>"""

def build_dashboard(con, out_path):
    cur = con.cursor()
    candidates = []
    for row in cur.execute("""SELECT c.id, c.canonical_id, c.label, c.rep_lat, c.rep_lon,
                                     c.kind_hypothesis, c.status, c.notes,
                                     p.admin_country, p.admin_state
                              FROM compound_candidate c JOIN place p ON c.place_id=p.id ORDER BY c.id"""):
        cid, can_id, label, lat, lon, kind, status, notes, country, state = row
        c2 = con.cursor()
        c2.execute("SELECT COUNT(*) FROM obs_link WHERE target_canonical_id=?", (can_id,))
        obs_count = c2.fetchone()[0]
        c2.execute("SELECT o.obs_lat, o.obs_lon, o.payload_json FROM observation o JOIN obs_link l ON l.observation_id=o.id WHERE l.target_canonical_id=?", (can_id,))
        observations = [(r[0], r[1], json.loads(r[2])) for r in c2.fetchall()]
        c2.execute("SELECT surface, lang FROM alias WHERE canonical_id=?", (can_id,))
        aliases = c2.fetchall()
        candidates.append({'id':cid,'label':label,'lat':lat,'lon':lon,'kind':kind,'status':status,'notes':notes,
                          'country':country,'state':state,'obs_count':obs_count,
                          'observations':observations,'aliases':aliases})
    html = DASHBOARD.replace("__CANDIDATES__", json.dumps(candidates, ensure_ascii=False))
    with open(out_path,'w',encoding='utf-8') as f:
        f.write(html)
    print(f"[HTML] {out_path} written, candidates={len(candidates)}")

def publish(src, dst):
    try:
        shutil.copyfile(src, dst)
        print(f"[PUB] {dst}")
    except Exception as e:
        print(f"[PUB ERR] {dst}: {e}", file=sys.stderr)

def main():
    con = init_schema()
    seed(con)
    fetch_osm(con)
    build_dashboard(con, '/tmp/dashboard.html')
    cur = con.cursor()
    print("--- counts ---")
    for name, q in [
        ("candidates",   "SELECT COUNT(*) FROM compound_candidate"),
        ("aliases",      "SELECT COUNT(*) FROM alias"),
        ("places",       "SELECT COUNT(*) FROM place"),
        ("sources",      "SELECT COUNT(*) FROM source"),
        ("observations", "SELECT COUNT(*) FROM observation"),
        ("obs_links",    "SELECT COUNT(*) FROM obs_link"),
        ("events",       "SELECT COUNT(*) FROM event"),
    ]:
        print(f"{name:>15s}: {cur.execute(q).fetchone()[0]}")
    print("--- observation kinds ---")
    for kind, n in cur.execute("SELECT kind, COUNT(*) FROM observation GROUP BY kind"):
        print(f"{kind:>15s}: {n}")
    print("--- per-candidate obs ---")
    for label, n in cur.execute("""SELECT c.label, COUNT(l.id) FROM compound_candidate c
                                   LEFT JOIN obs_link l ON l.target_canonical_id=c.canonical_id
                                   GROUP BY c.id ORDER BY 2 DESC"""):
        print(f"  {n:>4d}  {label}")
    print("--- tag breakdown ---")
    for kind, n in cur.execute("""SELECT json_extract(payload_json,'$.tags.building') AS b, COUNT(*)
                                  FROM observation GROUP BY b ORDER BY 2 DESC LIMIT 10"""):
        print(f"  building={kind!r:20s}: {n}")
    con.close()
    publish(DB_WORK, DB_OUT)
    publish('/tmp/dashboard.html', HTML_OUT)
    # Also copy to SS (user-visible) folder
    if os.path.isdir(SS):
        publish(DB_WORK, os.path.join(SS, 'compounds.db'))
        publish('/tmp/dashboard.html', os.path.join(SS, 'dashboard.html'))
        publish('/tmp/build_poc.py', os.path.join(SS, 'build_poc.py'))

if __name__ == '__main__':
    main()
