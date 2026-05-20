"""Phase 2: events + tiled overpass + crt.sh + multilayer dashboard."""
import sqlite3, urllib.request, urllib.parse, json, hashlib, time, sys, os, datetime, shutil

DB = '/tmp/compounds.db'
OUT = '/sessions/quirky-trusting-archimedes/mnt/outputs'
SS  = '/sessions/quirky-trusting-archimedes/mnt/SS'

con = sqlite3.connect(DB)
cur = con.cursor()
PHASE = sys.argv[1] if len(sys.argv) > 1 else 'all'

# -------------------- EVENTS --------------------
EVENTS = [
    # (match_substr, kind, date, summary, url)
    (None, 'sanction', '2025-10-14', 'OFAC: Prince Group関連大規模制裁。Jin Bei Group, Golden Fortune Resorts World, Warp Data Lao 等を指定',
     'https://home.treasury.gov/news/press-releases/sb0278'),
    (None, 'finance_designation', '2025-05-02', 'FinCEN: Huione を primary money laundering concern に指定',
     'https://www.reuters.com/sustainability/boards-policy-regulation/us-moves-ban-cambodias-huione-over-alleged-money-laundering-2025-05-02/'),
    (None, 'border_closure', '2025-06-24', 'タイ・カンボジア国境通行制限 (Reuters)',
     'https://www.reuters.com/world/asia-pacific/thailand-closes-border-crossings-with-cambodia-dispute-deepens-2025-06-24/'),
    (None, 'drone_ban', '2025-07-15', 'タイCAAT: 全国ドローン飛行禁止 (国境安全保障)',
     'https://www.caat.or.th/en/caat-media/171316/'),
    (None, 'drone_rule', '2026-02-06', 'タイCAAT Notice No.15: ドローン規則更新、国境地域は禁止維持',
     'https://thailand.go.th/issue-focus-detail/flying-a-drone-in-thailand--updated-guide-for-tourists-from-6-feb-2026'),
    (None, 'rescue_aggregate', '2026-03-15', 'AP: カンボジア当局が250地点中80%閉鎖を主張、約1万人を23ヵ国へ送還(政治数字含む)',
     'https://apnews.com/article/9bbfe6ee970b5a73529f5f820b931e1f'),
    (None, 'human_rights_report', '2025-06-26', 'Amnesty: カンボジアで少なくとも53のスキャムコンパウンドを記録',
     'https://www.amnesty.org/en/documents/asa23/9447/2025/en/'),
    ('Poipet', 'electricity_cut', '2025-02-05', 'タイ政府: 詐欺センター対策で国境一帯への電力・燃料・通信遮断を検討/実施',
     'https://world.thaipbs.or.th/detail/thailand-considers-power-internet-cuts-to-combat-callcentre-scams-in-cambodia/57801'),
    ('Jin Bei', 'sanction', '2025-10-14', 'OFAC: Jin Bei Group 個別指定 (Prince Group関連制裁内)',
     'https://home.treasury.gov/news/press-releases/sb0278'),
    ('Dara Sakor', 'sanction_context', '2025-10-14', 'Dara Sakor (UDG) は Prince Group 関連報道との交差。OFAC文書を参照',
     'https://home.treasury.gov/news/press-releases/sb0278'),
    ('KK Park', 'media_investigation', '2024-09-15', 'Reuters/AFP/GI-TOC等が KK Park / Shwe Kokko を継続的に名指し報道',
     'https://www.reuters.com/'),
    (None, 'unodc_report', '2025-04-21', 'UNODC: メコン地域のサイバー詐欺がinflection pointに達し、周辺へ拡散と評価',
     'https://www.unodc.org/unodc/frontpage/2025/April/cyberfraud-in-the-mekong-reaches-inflection-point--unodc-reveals.html'),
]

def insert_events():
    n = 0
    for match, kind, date, summary, url in EVENTS:
        cur.execute("INSERT INTO source(kind, url, captured_at) VALUES('news', ?, datetime('now'))", (url,))
        src = cur.lastrowid
        cand_id, place_id = None, None
        if match:
            r = cur.execute("SELECT id, place_id FROM compound_candidate WHERE label LIKE ?", (f'%{match}%',)).fetchone()
            if r: cand_id, place_id = r
        cur.execute("""INSERT INTO event(kind, happened_on, resolution, place_id, candidate_id, summary, source_id)
                       VALUES(?,?,?,?,?,?,?)""", (kind, date, 'day', place_id, cand_id, summary, src))
        n += 1
    con.commit()
    print(f"[EVT] inserted {n} events")

# -------------------- OVERPASS RE-FETCH --------------------
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
        data=data, headers={'User-Agent':'compounds-poc/0.2','Accept':'application/json'})
    return urllib.request.urlopen(req, timeout=60).read()

def refetch_osm(cand_subset=None):
    rows = cur.execute("SELECT id, canonical_id, label, rep_lat, rep_lon FROM compound_candidate ORDER BY id").fetchall()
    if cand_subset:
        rows = [r for r in rows if r[0] in cand_subset]
    for cand_id, can_id, label, lat, lon in rows:
        seen = set()
        for r in cur.execute("""SELECT o.payload_json FROM observation o JOIN obs_link l ON l.observation_id=o.id
                                WHERE l.target_canonical_id=? AND o.kind='osm'""", (can_id,)):
            try: seen.add(json.loads(r[0]).get('osm_id'))
            except: pass
        d = 0.012  # ~1.2km
        bbox = (lat-d, lon-d, lat+d, lon+d)
        try: body = overpass(bbox)
        except Exception as e:
            print(f"[OSM ERR] {label}: {e}", file=sys.stderr); time.sleep(2); continue
        sha = hashlib.sha256(body).hexdigest()
        try: data = json.loads(body)
        except: continue
        elements = data.get('elements', [])
        cur.execute("INSERT INTO source(kind, url, captured_at, archive_sha256) VALUES('osm_overpass_wide', ?, ?, ?)",
                    ('https://overpass-api.de/api/interpreter', datetime.datetime.utcnow().isoformat()+'Z', sha))
        src_id = cur.lastrowid
        new = 0
        for el in elements:
            oid = el.get('id')
            if oid in seen: continue
            seen.add(oid)
            c = el.get('center') or {}
            elat = c.get('lat') or el.get('lat')
            elon = c.get('lon') or el.get('lon')
            if elat is None or elon is None: continue
            tags = el.get('tags', {})
            payload = json.dumps({'osm_id': oid, 'osm_type': el.get('type'), 'tags': tags}, ensure_ascii=False)
            cur.execute("""INSERT INTO observation(kind, captured_at, obs_lat, obs_lon, payload_json, source_id, archive_sha256, confidence_tier)
                           VALUES('osm', datetime('now'), ?, ?, ?, ?, ?, 'circumstantial')""",
                        (elat, elon, payload, src_id, sha))
            obs_id = cur.lastrowid
            cur.execute("INSERT INTO obs_link(observation_id, target_canonical_id, link_kind, weight, by) VALUES(?, ?, 'co_located', 0.3, 'auto:osm_proximity')",
                        (obs_id, can_id))
            new += 1
        con.commit()
        print(f"[OSM-W] {label[:38]:38s}: +{new} (total elements returned {len(elements)})")
        time.sleep(1.2)

# -------------------- CT logs --------------------
CT_QUERIES = [
    ('Jin Bei', 'jinbei'),
    ('Jin Bei', '%25jinbei%25'),
    ('Prince Group', 'prince%20holding'),
    ('Huione', 'huione'),
    ('Huione', 'huiwang'),
    ('Dara Sakor', 'dara%20sakor'),
]

def fetch_crtsh():
    for label, q in CT_QUERIES:
        url = f'https://crt.sh/?q={q}&output=json'
        try:
            req = urllib.request.Request(url, headers={'User-Agent':'compounds-poc/0.2','Accept':'application/json'})
            body = urllib.request.urlopen(req, timeout=40).read()
        except Exception as e:
            print(f"[CT ERR] {label}/{q}: {e}", file=sys.stderr); time.sleep(2); continue
        sha = hashlib.sha256(body).hexdigest()
        try: data = json.loads(body) if body else []
        except Exception:
            print(f"[CT parse] {label}/{q}: not json (len={len(body)})"); time.sleep(1); continue
        cur.execute("INSERT INTO source(kind, url, captured_at, archive_sha256) VALUES('crtsh', ?, ?, ?)",
                    (url, datetime.datetime.utcnow().isoformat()+'Z', sha))
        src_id = cur.lastrowid
        m = cur.execute("SELECT id, canonical_id FROM compound_candidate WHERE label LIKE ?", (f'%{label}%',)).fetchone()
        cand_can = m[1] if m else None
        seen_cn = set()
        count = 0
        for entry in data[:300]:
            cn = (entry.get('common_name') or '').strip()
            if not cn:
                nv = entry.get('name_value','').split('\n')[0]
                cn = nv.strip()
            if not cn or cn in seen_cn: continue
            seen_cn.add(cn)
            payload = json.dumps({'common_name': cn, 'issuer': entry.get('issuer_name'),
                                  'not_before': entry.get('not_before'), 'q': q, 'label': label}, ensure_ascii=False)
            cur.execute("""INSERT INTO observation(kind, captured_at, payload_json, source_id, archive_sha256, confidence_tier)
                           VALUES('domain_cert', datetime('now'), ?, ?, ?, 'speculative')""",
                        (payload, src_id, sha))
            obs_id = cur.lastrowid
            if cand_can:
                cur.execute("INSERT INTO obs_link(observation_id, target_canonical_id, link_kind, weight, by) VALUES(?, ?, 'name_match', 0.2, 'auto:crtsh')",
                            (obs_id, cand_can))
            count += 1
        con.commit()
        print(f"[CT ] {label:14s} q={q:24s}: {count} certs")
        time.sleep(2.0)

# dispatch
if PHASE in ('events','all'): insert_events()
if PHASE in ('osm-a','all'): refetch_osm(cand_subset={1,2,3})
if PHASE in ('osm-b','all'): refetch_osm(cand_subset={4,5,6,7})
if PHASE in ('ct','all'): fetch_crtsh()

print("--- summary ---")
for name, q in [
    ('events',       'SELECT COUNT(*) FROM event'),
    ('observations', 'SELECT COUNT(*) FROM observation'),
    ('  osm',        "SELECT COUNT(*) FROM observation WHERE kind='osm'"),
    ('  domain',     "SELECT COUNT(*) FROM observation WHERE kind='domain_cert'"),
    ('obs_links',    'SELECT COUNT(*) FROM obs_link'),
    ('sources',      'SELECT COUNT(*) FROM source'),
]:
    print(f"{name:>15s}: {cur.execute(q).fetchone()[0]}")
con.close()
