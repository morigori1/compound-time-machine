"""Phase 8: collect a preview image URL for each event's source article.

Individual-event news photos are copyright-protected, so we do NOT download them.
Instead we fetch each source article's og:image (the social-card image, intended to be
linked) and store the URL. The dashboard's event viewer shows it as a hot-linked
preview alongside a link to the article — a "viewer", not a local copy.

og:image fails for some sites (bot blocks, no tag); those events simply show the
article link with no preview. Wikipedia pages fall back to the REST summary thumbnail.
Idempotent.
"""
import sqlite3, os, re, time, html, json, sys
import urllib.request, urllib.parse, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, 'compounds.db')
UA = 'Mozilla/5.0 (compounds-poc/0.8; local OSINT research dashboard)'

con = sqlite3.connect(DB)
cur = con.cursor()

# add og_image column if missing
cols = [r[1] for r in cur.execute("PRAGMA table_info(source)")]
if 'og_image' not in cols:
    cur.execute("ALTER TABLE source ADD COLUMN og_image TEXT")
    con.commit()


def fetch(url, timeout=22):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'text/html,*/*'})
    return urllib.request.urlopen(req, timeout=timeout).read().decode('utf-8', 'ignore')


def og_image(htmltext):
    for pat in (r'<meta[^>]+(?:property|name)=["\']og:image(?::secure_url)?["\'][^>]*>',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\']og:image["\']'):
        m = re.search(pat, htmltext, re.I)
        if m:
            c = re.search(r'content=["\']([^"\']+)["\']', m.group(0))
            if c:
                return html.unescape(c.group(1)).strip()
    return ''


def wikipedia_thumb(url):
    m = re.search(r'/wiki/([^?#]+)', url)
    if not m:
        return ''
    title = m.group(1)
    api = f'https://en.wikipedia.org/api/rest_v1/page/summary/{title}'
    try:
        d = json.loads(fetch(api, timeout=20))
        return (d.get('originalimage') or d.get('thumbnail') or {}).get('source', '')
    except Exception:
        return ''


# distinct source URLs referenced by events
urls = [r[0] for r in cur.execute("""SELECT DISTINCT s.url FROM source s
                                      JOIN event e ON e.source_id=s.id
                                      WHERE s.url LIKE 'http%'""")]
print(f"[P8] {len(urls)} distinct source URLs to probe for preview images")

ok = fail = 0
for i, url in enumerate(urls, 1):
    img = ''
    try:
        if 'wikipedia.org' in url:
            img = wikipedia_thumb(url)
        else:
            img = og_image(fetch(url))
    except Exception as e:
        print(f"  [P8 ERR] {url[:60]} : {e}", file=sys.stderr)
    if img:
        cur.execute("UPDATE source SET og_image=? WHERE url=?", (img, url))
        ok += 1
        tag = 'OK '
    else:
        fail += 1
        tag = 'no '
    print(f"  [{i:3d}/{len(urls)}] {tag} {url.split('/')[2][:26]:26s} {img[:64]}")
    con.commit()
    time.sleep(0.7)

print(f"[P8] done. preview image found for {ok} / {len(urls)} sources ({fail} without).")
con.close()
