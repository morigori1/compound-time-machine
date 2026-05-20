"""Phase 5: POI annotations + guided-tour narration.

POI layer (direction C) — built from two HONEST sources only, no fabricated coordinates:
  1. OSM-attested named features (casino / hotel / resort / worship / etc.) inside a
     candidate's radius — real OSM elements with real coordinates.
  2. Density clusters of observed building footprints (OSM + MS ML). A simple grid count
     finds where structures actually concentrate; the POI sits at the cluster centroid.

Narration layer (direction B) — a per-candidate "audio guide" script for the cinematic
guided tour. Editorial text, hedged to public reporting; stored so the dashboard stays
data-driven.
"""
import sqlite3, json, os, math
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, 'compounds.db')

con = sqlite3.connect(DB)
cur = con.cursor()

cur.executescript("""
CREATE TABLE IF NOT EXISTS poi (
    id INTEGER PRIMARY KEY,
    candidate_id INTEGER,
    canonical_id INTEGER,
    lat REAL, lon REAL,
    poi_type TEXT,
    name TEXT,
    descr TEXT,
    confidence TEXT,
    source TEXT
);
CREATE INDEX IF NOT EXISTS idx_poi_cand ON poi(candidate_id);
CREATE TABLE IF NOT EXISTS narration (
    id INTEGER PRIMARY KEY,
    candidate_id INTEGER,
    ord INTEGER,
    title TEXT,
    body TEXT
);
CREATE INDEX IF NOT EXISTS idx_narr_cand ON narration(candidate_id);
CREATE TABLE IF NOT EXISTS era_caption (
    id INTEGER PRIMARY KEY,
    candidate_id INTEGER,
    year INTEGER,
    caption TEXT
);
CREATE INDEX IF NOT EXISTS idx_era_cand ON era_caption(candidate_id);
""")
cur.execute("DELETE FROM poi")
cur.execute("DELETE FROM narration")
cur.execute("DELETE FROM era_caption")
con.commit()

# OSM tag -> (poi_type, default label) for named-feature promotion
TAG_MAP = {
    ('amenity', 'casino'):   ('casino', 'カジノ'),
    ('tourism', 'hotel'):    ('hotel', 'ホテル'),
    ('leisure', 'resort'):   ('resort', 'リゾート/総合施設'),
    ('landuse', 'industrial'): ('industrial', '工業区画'),
    ('amenity', 'place_of_worship'): ('worship', '宗教施設'),
    ('amenity', 'bank'):     ('bank', '銀行'),
    ('amenity', 'marketplace'): ('market', '市場'),
    ('amenity', 'fuel'):     ('fuel', '給油所'),
    ('amenity', 'bus_station'): ('transit', 'バスターミナル'),
    ('amenity', 'public_building'): ('admin', '公的施設'),
    ('amenity', 'fire_station'): ('admin', '消防署'),
    ('amenity', 'restaurant'): ('food', '飲食'),
}

# --- guided-tour narration (direction B). Hedged to public OSINT reporting. ---
NARRATION = {
    'KK Park': [
        ("いま見ているのは — KK Park / Shwe Kokko",
         "ミャンマー・カイン州、モエイ川をはさんでタイ・メーソットの対岸。2017年ごろから"
         "急速に建ち上がった大規模開発で、Reuters・AFP・GI-TOCがオンライン詐欺の一大拠点として"
         "繰り返し名指ししてきた場所です。生身では渡れない川の向こう側を、上空から覗いています。"),
        ("時間をさかのぼると",
         "タイムマシンを2014年へ戻すと、ここはほぼ農地と低層の集落です。スライダーを進めると"
         "高層棟・カジノ風の建物・外周が数年で出現する——その『建設の速さ』そのものが、"
         "この場所の性格を物語っています。"),
    ],
    'Jin Bei': [
        ("いま見ているのは — Jin Bei コンパウンド",
         "カンボジア・シハヌークビル。Jin Bei Groupが運営するカジノ・ホテル複合体で、"
         "2025年10月、米財務省OFACがPrince Group関連の制裁の中で名指し指定しました。"),
        ("制裁地図の上の一点",
         "右の OFAC SDN リストとウォレット欄は、この建物群と地続きの『金の流れ』です。"
         "観光地のような外観の裏で何が動いていたか——衛星と制裁データを重ねて読みます。"),
    ],
    'Chinatown': [
        ("いま見ているのは — Chinatown コンパウンド (Otres)",
         "シハヌークビル郊外オトレス地区。GI-TOC、Humanity Research Consultancy、Reuters が"
         "詐欺コンパウンドとして記録してきた区画です。海沿いリゾート開発の外形をまといます。"),
        ("ビーチ・リゾートの隣で",
         "観光ビーチのすぐ背後にこの密集ブロックがあります。タイムマシンで数年分を早回しすると、"
         "リゾート開発と一体で立ち上がっていく様子が見えます。"),
    ],
    'Dara Sakor': [
        ("いま見ているのは — Dara Sakor / UDG",
         "カンボジア・コッコン州。中国系 Union Development Group による巨大経済特区(SEZ)。"
         "カンボジア海岸線の相当部分を99年リースし、空港・港・カジノを含む複合開発として"
         "報じられてきました。"),
        ("『建たなかった都市』",
         "衛星フレームが他候補より少ないことに注目してください。撮影頻度が低いだけでなく、"
         "計画規模に対して実際の建設がまばら——広大な区画に空白が残る『ゴースト開発』として"
         "観察できます。観光気分のはずが、無人の滑走路と空き地が広がります。"),
    ],
    "O'Smach": [
        ("いま見ているのは — O'Smach 国境ゾーン",
         "カンボジア・オッダーミァンチェイ州、タイとの国境。国境カジノが集積する地帯で、"
         "現状の評価は speculative(推測段階)。確証より『状況証拠の集まり』として見る場所です。"),
        ("国境線という見世物",
         "地図のすぐ向こうがタイ側。国境のこちら側にだけカジノが密集する——その非対称性が、"
         "規制の裏側を可視化しています。"),
    ],
    'Poipet': [
        ("いま見ているのは — Poipet / O'Neang 回廊",
         "カンボジア・バンテイミアンチェイ州、タイ国境最大級のカジノ集積地。"
         "2025年2月、タイ政府が詐欺センター対策として国境一帯への電力・燃料・通信遮断に"
         "踏み切った、その対象エリアです。"),
        ("最も建物が濃い場所",
         "この候補は観測建物数が最多。タイムマシンとMS建物レイヤを重ねると、"
         "国境のすぐ内側にどれだけ密に構造物が積み上がったかが分かります。"),
    ],
    'Bavet': [
        ("いま見ているのは — Bavet 国境ゾーン",
         "カンボジア・スヴァイリエン州、ベトナムとの国境。Poipetと同様に国境カジノが集積し、"
         "詐欺関連の報道が続く回廊です。"),
        ("もう一つの国境カジノ回廊",
         "Poipet(タイ国境)と Bavet(ベトナム国境)を見比べると、カンボジアが"
         "両側の国境にカジノ回廊を抱える構造が見えてきます。"),
    ],
}


# --- era captions: timeline-synced commentary for the time machine (storytelling) ---
# (year, caption) — the dashboard shows the caption for the latest year <= current frame.
ERA = {
    'KK Park': [
        (2014, "モエイ川沿いの農地と低層の集落。国境の『ありふれた風景』。まだ何もない。"),
        (2018, "Yatai系の開発が着工。直線の区画と建物の基礎が、農地を上書きしていく。"),
        (2021, "高層棟群が立ち上がる。Reuters・GI-TOCが詐欺拠点として名指しを強める頃。"),
        (2024, "外周が閉じ、内部が埋まる。摘発・送還報道のさなかも、構造物はそのまま残る。"),
    ],
    'Jin Bei': [
        (2014, "シハヌークビルはまだ静かな海辺の町。海岸線に空き地が目立つ。"),
        (2018, "中国系投資ブーム。カジノ・ホテルが一斉に増え、建設クレーンの森になる。"),
        (2021, "コロナでカジノ景気が崩落。骨組みのまま止まった未完成ビルが残る。"),
        (2024, "Jin Bei複合体が稼働。翌2025年10月、OFAC制裁の対象として名指しされる。"),
    ],
    'Chinatown': [
        (2014, "オトレス・ビーチ周辺は、リゾート開発前の素朴な海岸。"),
        (2018, "リゾート開発と一体で、密集した区画が一気に造成されていく。"),
        (2021, "ブロックが埋まり、外に開かない閉鎖的な複合体の輪郭ができる。"),
        (2024, "GI-TOC等が詐欺コンパウンドとして記録。観光地の隣に閉じた一画。"),
    ],
    'Dara Sakor': [
        (2014, "コッコンの海岸線と原生林。UDGが99年リースを得た広大な区域。"),
        (2017, "滑走路と幹線道路だけが森を貫く。都市計画の『骨格』が先に現れる。"),
        (2020, "空港も道路もあるのに、市街は埋まらない——『建たなかった都市』。"),
    ],
    "O'Smach": [
        (2014, "タイ国境の小さな通関集落。畑と数本の道路があるだけ。"),
        (2018, "国境のカンボジア側に、カジノらしき建物が点在し始める。"),
        (2021, "国境カジノの集積が進む。それでも評価はなお speculative(推測段階)。"),
        (2024, "国境線をはさんだ非対称——こちら側だけが、不自然に賑わう。"),
    ],
    'Poipet': [
        (2014, "タイ国境最大の通関町。すでにカジノ街の原型がある。"),
        (2018, "O'Neang回廊に高密度の構造物が積み上がっていく。"),
        (2021, "観測される建物密度は、7候補の中で最大に達する。"),
        (2024, "2025年2月、タイが電力・燃料・通信の遮断に踏み切った、その対象エリア。"),
    ],
    'Bavet': [
        (2014, "ベトナム国境の通関町。国境ゲート周辺に空き地が広がる。"),
        (2018, "国境カジノの回廊が形づくられていく。"),
        (2021, "Poipet(タイ国境)と対をなす、もう一方の国境カジノ回廊。"),
        (2024, "詐欺関連の報道が続く。カンボジアが両国境にカジノ回廊を抱える構図。"),
    ],
}


def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


cands = cur.execute(
    "SELECT id, canonical_id, label, rep_lat, rep_lon FROM compound_candidate ORDER BY id").fetchall()

poi_total = 0
narr_total = 0
era_total = 0
for cand_id, can_id, label, lat, lon in cands:
    # ---- POI source 1: OSM-attested named features in radius ----
    named = 0
    for r in cur.execute("""SELECT obs_lat, obs_lon, payload_json FROM observation o
                            JOIN obs_link l ON l.observation_id=o.id
                            WHERE l.target_canonical_id=? AND o.kind='osm'""", (can_id,)):
        olat, olon, pj = r
        tags = json.loads(pj).get('tags', {})
        nm = tags.get('name:en') or tags.get('name')
        if not nm:
            continue
        hit = None
        for (k, v), (ptype, deflabel) in TAG_MAP.items():
            if tags.get(k) == v:
                hit = (ptype, deflabel)
                break
        if not hit:
            continue
        ptype, deflabel = hit
        cur.execute("""INSERT INTO poi(candidate_id, canonical_id, lat, lon, poi_type,
                       name, descr, confidence, source)
                       VALUES(?,?,?,?,?,?,?,?,?)""",
                    (cand_id, can_id, olat, olon, ptype, nm,
                     f"{deflabel}(OSMタグ {[k for (k, v) in TAG_MAP if tags.get(k) == v][0]})",
                     'osm_attested', 'osm'))
        named += 1
        poi_total += 1

    # ---- POI source 2: density clusters of observed building footprints ----
    pts = []
    for r in cur.execute("""SELECT obs_lat, obs_lon FROM observation o
                            JOIN obs_link l ON l.observation_id=o.id
                            WHERE l.target_canonical_id=? AND o.kind IN ('osm','ms_building')""",
                         (can_id,)):
        if r[0] is not None and r[1] is not None:
            pts.append((r[0], r[1]))
    CELL = 0.0015  # ~150 m grid
    grid = defaultdict(list)
    for plat, plon in pts:
        grid[(round(plat / CELL), round(plon / CELL))].append((plat, plon))
    cells = sorted(grid.items(), key=lambda kv: len(kv[1]), reverse=True)
    clusters = 0
    for ci, (_, members) in enumerate(cells[:10]):
        if len(members) < 12:
            break
        clat = sum(m[0] for m in members) / len(members)
        clon = sum(m[1] for m in members) / len(members)
        name = '中心建物群' if ci == 0 else f'建物群 #{ci + 1}'
        cur.execute("""INSERT INTO poi(candidate_id, canonical_id, lat, lon, poi_type,
                       name, descr, confidence, source)
                       VALUES(?,?,?,?,?,?,?,?,?)""",
                    (cand_id, can_id, clat, clon, 'building_cluster', name,
                     f"観測建物フットプリント {len(members)} 件が集中する区画(~150mセル重心)",
                     'derived_density', 'osm+ms_cluster'))
        clusters += 1
        poi_total += 1

    # ---- narration + era captions ----
    key = next((k for k in NARRATION if k in label), None)
    if key:
        for ord_i, (title, body) in enumerate(NARRATION[key]):
            cur.execute("INSERT INTO narration(candidate_id, ord, title, body) VALUES(?,?,?,?)",
                        (cand_id, ord_i, title, body))
            narr_total += 1
    era_key = next((k for k in ERA if k in label), None)
    eras = 0
    if era_key:
        for year, caption in ERA[era_key]:
            cur.execute("INSERT INTO era_caption(candidate_id, year, caption) VALUES(?,?,?)",
                        (cand_id, year, caption))
            eras += 1
            era_total += 1

    con.commit()
    print(f"  [POI] {label[:34]:34s}: {named:2d} named + {clusters} clusters | "
          f"narration {'ok' if key else 'NO':2s} | {eras} era captions")

print(f"[POI] done. {poi_total} POIs, {narr_total} narration cards, "
      f"{era_total} era captions across {len(cands)} candidates.")
con.close()
