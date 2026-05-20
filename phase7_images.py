"""Phase 7: collect freely-licensed location images and save them locally with attribution.

Per-event news photos are copyright-protected and unreliable to hotlink, so this pulls
freely-licensed images from Wikimedia Commons (one or two per compound), downloads them
into images/, and records full attribution (author, license, source URL) in the DB.
The dashboard displays them in the guided-tour panel and the event toasts.

Idempotent: re-running clears image_resource and re-downloads.
"""
import sqlite3, os, json, re, time, urllib.request, urllib.parse, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, 'compounds.db')
IMG_DIR = os.path.join(HERE, 'images')
os.makedirs(IMG_DIR, exist_ok=True)
UA = 'compounds-poc/0.7 (local OSINT research dashboard)'

# (candidate_label_substring, Commons File: title, japanese caption)
IMAGES = [
    ('KK Park',    'File:KKPark.jpg',
     'KK Park(タイ国境側から見たコンパウンド)'),
    ('KK Park',    'File:Shwe Kokko Scam City, Myawaddy, Myanmar.jpg',
     'Shwe Kokko — モエイ川沿いに建ち上がった「新都市」'),
    ('Jin Bei',    'File:Jin Bei Casino.jpg',
     'Jin Bei カジノ(シハヌークビル)'),
    ('Chinatown',  'File:Otres Beach, Sihanoukville.jpg',
     'オトレス・ビーチ — 「チャイナタウン」コンパウンド周辺'),
    ('Chinatown',  'File:New Macao Casino Sihanoukville (cropped).jpg',
     'シハヌークビルのカジノ(開発バブル期の象徴)'),
    ("O'Smach",    'File:Chong Chom border crossing seen from airliner.jpg',
     'O’Smach / Chong Chom 国境(上空から)'),
    ('Poipet',     'File:Border checkpoint, Poipet, Cambodia.jpg',
     'Poipet 国境チェックポイント'),
    ('Bavet',      'File:Moc bai-bavet border.jpg',
     'Bavet / Moc Bai — カンボジア・ベトナム国境'),
]


def http(url, timeout=40):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    return urllib.request.urlopen(req, timeout=timeout).read()


def http_retry(url, timeout=60, tries=5):
    """Download with backoff — Wikimedia rate-limits (HTTP 429) bursty thumbnail fetches."""
    for attempt in range(tries):
        try:
            return http(url, timeout=timeout)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < tries - 1:
                wait = 6 * (attempt + 1)
                print(f"    (429 — waiting {wait}s)", file=sys.stderr)
                time.sleep(wait)
                continue
            raise


def commons_imageinfo(title):
    """Return (thumb_url, license_short, author_text, description_url)."""
    params = {'action': 'query', 'format': 'json', 'titles': title,
              'prop': 'imageinfo', 'iiprop': 'url|extmetadata', 'iiurlwidth': '1000'}
    url = 'https://commons.wikimedia.org/w/api.php?' + urllib.parse.urlencode(params)
    data = json.loads(http(url, timeout=30))
    page = next(iter(data['query']['pages'].values()))
    ii = page['imageinfo'][0]
    meta = ii.get('extmetadata', {})
    lic = meta.get('LicenseShortName', {}).get('value', 'unknown')
    author_html = meta.get('Artist', {}).get('value', 'unknown')
    author = re.sub('<[^>]+>', '', author_html).strip()
    author = re.sub(r'\s+', ' ', author)
    return ii.get('thumburl') or ii['url'], lic, author, ii.get('descriptionurl', '')


con = sqlite3.connect(DB)
cur = con.cursor()
cur.executescript("""
CREATE TABLE IF NOT EXISTS image_resource (
    id INTEGER PRIMARY KEY,
    candidate_id INTEGER,
    local_path TEXT,
    title TEXT,
    caption TEXT,
    credit TEXT,
    license TEXT,
    source_url TEXT
);
CREATE INDEX IF NOT EXISTS idx_imgres_cand ON image_resource(candidate_id);
""")
cur.execute("DELETE FROM image_resource")
con.commit()

cands = {lbl: cid for cid, lbl in cur.execute("SELECT id, label FROM compound_candidate")}

added = 0
for idx, (substr, file_title, caption) in enumerate(IMAGES):
    match = next((lbl for lbl in cands if substr in lbl), None)
    if not match:
        print(f"  [P7 SKIP] no candidate for '{substr}'")
        continue
    cid = cands[match]
    try:
        thumb_url, lic, author, desc_url = commons_imageinfo(file_title)
    except Exception as e:
        print(f"  [P7 ERR] imageinfo {file_title}: {e}", file=sys.stderr)
        continue
    slug = re.sub(r'[^a-z0-9]+', '_', substr.lower()).strip('_')
    fname = f"{slug}_{idx}.jpg"
    fpath = os.path.join(IMG_DIR, fname)
    try:
        body = http_retry(thumb_url, timeout=60)
        with open(fpath, 'wb') as f:
            f.write(body)
    except Exception as e:
        print(f"  [P7 ERR] download {file_title}: {e}", file=sys.stderr)
        continue
    time.sleep(3)   # be polite to Wikimedia between downloads
    credit = f"{author} / {lic} (Wikimedia Commons)"
    cur.execute("""INSERT INTO image_resource
        (candidate_id, local_path, title, caption, credit, license, source_url)
        VALUES(?,?,?,?,?,?,?)""",
        (cid, f"images/{fname}", file_title, caption, credit, lic, desc_url))
    added += 1
    print(f"  [P7] {match[:26]:26s} <- {fname} ({len(body)//1024} KB) | {lic} | {author[:40]}")

con.commit()
print(f"[P7] saved {added} images with attribution.")
print("--- images per candidate ---")
for label, n in cur.execute("""SELECT c.label, COUNT(i.id) FROM compound_candidate c
                                LEFT JOIN image_resource i ON i.candidate_id=c.id
                                GROUP BY c.id ORDER BY c.id"""):
    print(f"  {n}  {label}")
con.close()
