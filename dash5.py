"""Dashboard v5: time machine + POI + guided tour, with an experience-focused UI.

Builds dashboard.html. Highlights:
  - View centering: flies to the observed building-density cluster, not the reported
    coordinate (which can be ~1-1.5 km off the actual compound).
  - Splash screen + decluttered "tour mode" (analyst sidebar hides during a tour).
  - Load-synced satellite playback with cinematic slow zoom-in and a big year watermark.
  - Before/After swipe: drag a divider to compare the oldest frame vs the latest.
  - Animated structure counter per stop.
"""
import sqlite3, json, os, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, 'compounds.db')
OUT_HTML = os.path.join(HERE, 'index.html')

con = sqlite3.connect(DB)
cur = con.cursor()


def leaflet_url(tmpl):
    return tmpl.replace('{level}', '{z}').replace('{row}', '{y}').replace('{col}', '{x}')


def has_table(name):
    return cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


HAS_IMG = has_table('imagery_release')
HAS_POI = has_table('poi')
HAS_NARR = has_table('narration')
HAS_ERA = has_table('era_caption')
HAS_IMGRES = has_table('image_resource')
HAS_TESTIMONY = has_table('testimony')
HAS_SPOT = has_table('local_spot')
HAS_LIFE = has_table('life_snippet')

candidates = []
for row in cur.execute("""SELECT c.id, c.canonical_id, c.label, c.rep_lat, c.rep_lon,
                                 c.kind_hypothesis, c.status, c.notes,
                                 p.admin_country, p.admin_state
                          FROM compound_candidate c JOIN place p ON c.place_id=p.id ORDER BY c.id"""):
    cid, can_id, label, lat, lon, kind, status, notes, country, state = row
    c2 = con.cursor()
    c2.execute("""SELECT o.obs_lat, o.obs_lon, o.payload_json FROM observation o
                  JOIN obs_link l ON l.observation_id=o.id
                  WHERE l.target_canonical_id=? AND o.kind='osm'""", (can_id,))
    osm_obs_raw = [(r[0], r[1], json.loads(r[2])) for r in c2.fetchall()]
    osm_count = len(osm_obs_raw)
    osm_obs = osm_obs_raw[::max(1, osm_count // 1500)][:1500] if osm_count > 1500 else osm_obs_raw
    c2.execute("""SELECT o.obs_lat, o.obs_lon FROM observation o
                  JOIN obs_link l ON l.observation_id=o.id
                  WHERE l.target_canonical_id=? AND o.kind='ms_building'""", (can_id,))
    ms_obs_raw = [(r[0], r[1]) for r in c2.fetchall()]
    ms_count = len(ms_obs_raw)
    ms_obs = ms_obs_raw[:800] if ms_count > 800 else ms_obs_raw
    c2.execute("""SELECT o.payload_json FROM observation o JOIN obs_link l ON l.observation_id=o.id
                  WHERE l.target_canonical_id=? AND o.kind='sanction_entry'""", (can_id,))
    sanctions = [json.loads(r[0]) for r in c2.fetchall()]
    c2.execute("""SELECT e.kind, e.happened_on, e.summary, COALESCE(e.resolution,'day'),
                          s.url, s.og_image
                   FROM event e LEFT JOIN source s ON e.source_id=s.id
                   WHERE e.candidate_id=? ORDER BY e.happened_on""", (cid,))
    events_local = [{'kind': r[0], 'date': r[1], 'summary': r[2], 'res': r[3],
                     'url': r[4], 'img': r[5]} for r in c2.fetchall()]
    c2.execute("SELECT surface, lang FROM alias WHERE canonical_id=?", (can_id,))
    aliases = c2.fetchall()
    imagery = []
    if HAS_IMG:
        c2.execute("""SELECT release_date, release_num, tile_url FROM imagery_release
                      WHERE candidate_id=? AND is_distinct=1 ORDER BY release_date""", (cid,))
        imagery = [{'date': r[0], 'url': leaflet_url(r[2])} for r in c2.fetchall()]
    poi = []
    view_lat, view_lon = lat, lon
    if HAS_POI:
        c2.execute("""SELECT lat, lon, poi_type, name, descr, confidence FROM poi
                      WHERE candidate_id=? ORDER BY poi_type""", (cid,))
        poi = [{'lat': r[0], 'lon': r[1], 'type': r[2], 'name': r[3],
                'descr': r[4], 'conf': r[5]} for r in c2.fetchall()]
        # view center = observed building-density cluster, when available
        for p in poi:
            if p['name'] == '中心建物群':
                view_lat, view_lon = p['lat'], p['lon']
                break
    narration = []
    if HAS_NARR:
        c2.execute("SELECT title, body FROM narration WHERE candidate_id=? ORDER BY ord", (cid,))
        narration = [{'title': r[0], 'body': r[1]} for r in c2.fetchall()]
    eras = []
    if HAS_ERA:
        c2.execute("SELECT year, caption FROM era_caption WHERE candidate_id=? ORDER BY year", (cid,))
        eras = [{'year': r[0], 'caption': r[1]} for r in c2.fetchall()]
    images = []
    if HAS_IMGRES:
        c2.execute("""SELECT local_path, caption, credit, license, source_url
                      FROM image_resource WHERE candidate_id=? ORDER BY id""", (cid,))
        images = [{'path': r[0], 'caption': r[1], 'credit': r[2],
                   'license': r[3], 'src': r[4]} for r in c2.fetchall()]
    testimony = []
    if HAS_TESTIMONY:
        c2.execute("""SELECT role, speaker, year, quote, source_url
                      FROM testimony WHERE candidate_id=? ORDER BY id""", (cid,))
        testimony = [{'role': r[0], 'speaker': r[1], 'year': r[2],
                      'quote': r[3], 'src': r[4]} for r in c2.fetchall()]
    spots = []
    if HAS_SPOT:
        c2.execute("""SELECT lat, lon, category, kind, name FROM local_spot
                      WHERE candidate_id=?""", (cid,))
        spots = [{'lat': r[0], 'lon': r[1], 'cat': r[2], 'kind': r[3], 'name': r[4]}
                 for r in c2.fetchall()]
    life = []
    if HAS_LIFE:
        c2.execute("""SELECT topic, text, source_label, source_url FROM life_snippet
                      WHERE candidate_id=? ORDER BY ord""", (cid,))
        life = [{'topic': r[0], 'text': r[1], 'src_label': r[2], 'src': r[3]}
                for r in c2.fetchall()]
    candidates.append({'id': cid, 'label': label, 'lat': lat, 'lon': lon,
                       'view_lat': view_lat, 'view_lon': view_lon,
                       'kind': kind, 'status': status, 'notes': notes,
                       'country': country, 'state': state,
                       'osm_count': osm_count, 'osm_sample': osm_obs,
                       'ms_count': ms_count, 'ms_sample': ms_obs,
                       'bld_count': osm_count + ms_count,
                       'sanctions': sanctions, 'events': events_local, 'aliases': aliases,
                       'imagery': imagery, 'poi': poi, 'narration': narration,
                       'eras': eras, 'images': images, 'testimony': testimony,
                       'spots': spots, 'life': life})

global_events = [{'kind': r[0], 'date': r[1], 'summary': r[2], 'res': r[3], 'url': r[4], 'img': r[5]}
                 for r in cur.execute("""SELECT e.kind, e.happened_on, e.summary,
                                                COALESCE(e.resolution,'day'), s.url, s.og_image
                                         FROM event e LEFT JOIN source s ON e.source_id=s.id
                                         WHERE e.candidate_id IS NULL ORDER BY e.happened_on""")]
top_legals = [{'name': r[0], 'jurisdiction': r[1], 'programs': r[2]}
              for r in cur.execute("""SELECT name, jurisdiction, programs FROM legal_entity
                                      WHERE jurisdiction LIKE '%Cambodia%' OR jurisdiction LIKE '%Burma%'
                                      ORDER BY id DESC LIMIT 24""")]
wallets_summary = [{'chain': r[0], 'count': r[1]} for r in cur.execute("SELECT chain, COUNT(*) FROM wallet GROUP BY chain ORDER BY 2 DESC")]

meta = {
  'generated_at': datetime.datetime.now(datetime.timezone.utc).isoformat()[:19] + 'Z',
  'totals': {
    'candidates': cur.execute("SELECT COUNT(*) FROM compound_candidate").fetchone()[0],
    'observations_total': cur.execute("SELECT COUNT(*) FROM observation").fetchone()[0],
    'imagery_frames': cur.execute("SELECT COUNT(*) FROM imagery_release WHERE is_distinct=1").fetchone()[0] if HAS_IMG else 0,
    'pois': cur.execute("SELECT COUNT(*) FROM poi").fetchone()[0] if HAS_POI else 0,
    'events': cur.execute("SELECT COUNT(*) FROM event").fetchone()[0],
    'legal_entities': cur.execute("SELECT COUNT(*) FROM legal_entity").fetchone()[0],
    'wallets': cur.execute("SELECT COUNT(*) FROM wallet").fetchone()[0],
  },
}

HTML = r"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Compound Time Machine — Mekong</title>
<meta name="description" content="公開OSINTで作る、メコン地域のオンライン詐欺コンパウンド7地点を衛星のタイムマシン・ガイドツアー・証言で巡る可視化。">
<meta property="og:type" content="website">
<meta property="og:url" content="https://morigori1.github.io/compound-time-machine/">
<meta property="og:title" content="Compound Time Machine — メコン詐欺コンパウンドを衛星で巡る">
<meta property="og:description" content="ジャーナリストでさえ生身では近づけない7つの「閉じた都市」を、衛星のタイムマシンで時間ごと巡るOSINTダッシュボード。">
<meta property="og:image" content="https://upload.wikimedia.org/wikipedia/commons/f/f6/ShweKokko.jpg">
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="vendor/leaflet/leaflet.css">
<style>
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,-apple-system,sans-serif;background:#0b0e13;color:#e6e6e6}
#app{display:grid;grid-template-columns:400px 1fr;height:100vh}
#side{overflow-y:auto;padding:14px;border-right:1px solid #222;background:#0e1116}
#map{height:100vh;position:relative;background:#0b0e13}
body.touring #side{display:none}
body.touring #app{grid-template-columns:1fr}
h1{font-size:14px;margin:0 0 4px;color:#9cd}
h2{font-size:11px;color:#888;margin:18px 0 6px;text-transform:uppercase;letter-spacing:.08em;border-bottom:1px solid #222;padding-bottom:3px}
small{color:#777;font-size:11px;line-height:1.5}
.meta{font-size:11px;color:#bbb;line-height:1.7;background:#161a22;padding:8px;border-radius:5px;border:1px solid #222;margin-top:6px}
.meta b{color:#cef}.meta .row{display:flex;justify-content:space-between;padding:1px 0}.meta .row .k{color:#888}
.tourbtn{display:block;width:100%;margin:10px 0 4px;padding:11px;background:linear-gradient(90deg,#1d3a5c,#2a5a8a);
   color:#dff;border:1px solid #3a6a9a;border-radius:7px;font-size:13px;font-weight:600;cursor:pointer}
.tourbtn:hover{background:linear-gradient(90deg,#244a72,#3370a8)}
.card{background:#161a22;border:1px solid #2a3140;border-radius:6px;padding:10px;margin-bottom:8px;cursor:pointer}
.card.active{border-color:#5af;background:#1a2030}
.card .label{font-weight:600;color:#fff;font-size:13px}
.card .meta-row{font-size:11px;color:#9aa;margin-top:3px}
.badge{display:inline-block;font-size:10px;padding:2px 6px;border-radius:3px;margin-right:4px;line-height:1.4}
.b-scam{background:#5a1a1a;color:#fbb}.b-sez{background:#1a3a5a;color:#bcf}.b-mixed{background:#3a3a1a;color:#fec}
.b-corroborated{background:#1a4a5a;color:#bdf}.b-circumstantial{background:#5a4a1a;color:#fec}.b-speculative{background:#3a2a3a;color:#fbe}
.stat{color:#7cf;font-size:10px;margin-left:4px}.stat.cam{color:#fc8}.stat.poi{color:#9d6}
.alias{font-size:11px;color:#aaa;margin-top:4px}
.layers{font-size:11px;color:#9aa;line-height:1.7}.layers .impl{color:#9fc}.layers .stub{color:#f96}
.tl{font-size:11px;border-left:2px solid #335;padding-left:8px;margin:6px 0}
.tl .d{color:#9cd}.tl .k{color:#fc8;margin:0 4px;font-family:ui-monospace,monospace;font-size:10px}.tl .s{color:#aab}
.sanc{font-size:11px;color:#fcb;margin:2px 0}
.leaflet-control-layers{background:#1a1f2a !important;color:#ddd !important}

/* splash */
#splash{position:fixed;inset:0;background:radial-gradient(ellipse at 50% 38%,#16202e,#070a0e);
   z-index:5000;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:24px}
#splash.hidden{display:none}
#splash .kicker{color:#5a7a9a;font-size:12px;letter-spacing:.22em;text-transform:uppercase;margin-bottom:14px}
#splash h1{font-size:32px;color:#dceaff;margin:0 0 12px;font-weight:800;letter-spacing:.01em}
#splash p{color:#8ba0b4;font-size:14px;margin:0 0 30px;line-height:1.8;max-width:540px}
#splash .btns{display:flex;gap:14px;flex-wrap:wrap;justify-content:center}
#splash button{padding:14px 24px;border-radius:9px;font-size:14px;font-weight:700;cursor:pointer}
#sp-tour{background:linear-gradient(90deg,#2a5a8a,#3f82bd);color:#fff;border:1px solid #4f93cc}
#sp-tour:hover{background:linear-gradient(90deg,#336aa0,#4d93cf)}
#sp-explore{background:#141c28;color:#bcd;border:1px solid #34425a}
#sp-explore:hover{background:#1c2738}
#splash .fine{color:#4a5666;font-size:11px;margin-top:30px;letter-spacing:.04em}

/* big year watermark */
#bigyear{position:absolute;left:20px;top:6px;font-size:76px;font-weight:800;font-family:ui-monospace,monospace;
   color:rgba(120,200,255,.10);z-index:600;pointer-events:none;letter-spacing:-.04em;transition:color .35s}
body.tm-on #bigyear{color:rgba(120,200,255,.30)}

/* tour panel */
#tour{position:absolute;left:50%;top:14px;transform:translateX(-50%);width:min(560px,80%);
   background:rgba(13,16,24,.96);border:1px solid #34507a;border-radius:11px;padding:14px 17px;
   box-shadow:0 10px 34px rgba(0,0,0,.7);z-index:1200;display:none;max-height:92vh;overflow-y:auto}
#tour.on{display:block}
#tour .thd{display:flex;align-items:baseline;gap:9px;margin-bottom:4px}
#tour .tname{font-size:16px;font-weight:800;color:#fff;flex:1}
#tour .stop{font-size:10px;color:#7cf;font-family:ui-monospace,monospace;letter-spacing:.06em}
#tour .counter{font-size:11px;color:#9aa;margin:6px 0 2px}
#tour .counter b{color:#ffd24a;font-size:15px;font-family:ui-monospace,monospace}
#tour-img{margin:9px 0 2px;border-radius:7px;overflow:hidden;position:relative;display:none}
#tour-img.on{display:block}
#tour-img img{width:100%;height:120px;object-fit:cover;display:block}
#tour-img .cap{position:absolute;left:0;right:0;bottom:0;padding:5px 9px 4px;font-size:10px;
   color:#e0e8f0;background:linear-gradient(transparent,rgba(8,10,14,.94))}
#tour-img .cap .cred{color:#8794a4;font-size:8.5px}
#tour .ntitle{font-size:12px;color:#9cf;font-weight:700;margin-top:9px}
#tour .nbody{font-size:12px;color:#cdd;line-height:1.7;margin-top:3px}
#tour .nav{display:flex;gap:8px;margin-top:11px;align-items:center}
#tour .nav .sp{flex:1}
#tour button{background:#1f2942;color:#cde;border:1px solid #3a4a6a;border-radius:6px;
   min-width:34px;height:31px;font-size:12px;cursor:pointer;padding:0 11px}
#tour button:hover{background:#2a3a5a}
#tour button:disabled{opacity:.35;cursor:default}
#tour .close{background:none;border:none;color:#889;font-size:15px;min-width:auto;padding:0}
#tour-life{margin-top:11px;border-top:1px solid #243044;padding-top:9px;display:none}
#tour-life .lh{font-size:11px;font-weight:700;color:#9cf;margin-bottom:7px}
.life-card{background:#141a24;border:1px solid #2a3344;border-radius:8px;padding:7px 10px 8px;margin-bottom:7px}
.life-card .lc-hd{display:flex;align-items:center;gap:6px;margin-bottom:3px}
.life-card .lc-av{width:21px;height:21px;border-radius:50%;background:#2a3a52;display:flex;
   align-items:center;justify-content:center;font-size:11px;flex:none}
.life-card .lc-topic{font-size:10.5px;font-weight:700;color:#cde}
.life-card .lc-src{font-size:9px;color:#7a8696;margin-left:auto}
.life-card .lc-text{font-size:11.5px;color:#dde;line-height:1.7}
.life-card .lc-link{font-size:9px;color:#7f88a4;text-decoration:none}
.life-card .lc-link:hover{color:#9cf}
.life-ico{font-size:13px;filter:drop-shadow(0 1px 2px #000)}

/* time machine panel */
#tm{position:absolute;left:50%;bottom:20px;transform:translateX(-50%);width:min(680px,82%);
   background:rgba(13,16,22,.95);border:1px solid #2a3550;border-radius:11px;padding:11px 16px;
   box-shadow:0 8px 28px rgba(0,0,0,.65);z-index:1200;display:none}
#tm.on{display:block}
#tm .hd{display:flex;align-items:center;gap:9px;margin-bottom:7px}
#tm .ttl{font-size:12px;font-weight:700;color:#fff;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#tm .frame{font-size:10px;color:#8aa;font-family:ui-monospace,monospace}
#tm .ctl{display:flex;align-items:center;gap:10px}
#tm button,#tm select{background:#1f2942;color:#cde;border:1px solid #3a4a6a;border-radius:6px;
   height:28px;font-size:12px;cursor:pointer;padding:0 8px}
#tm button.wide{padding:0 10px}
#tm button:hover{background:#2a3a5a}
#tm button.act{background:#2a5a8a;border-color:#4a8ac0;color:#fff}
#tm input[type=range]{flex:1;accent-color:#5af;height:4px}
#tm .scale{display:flex;justify-content:space-between;font-size:9px;color:#667;margin-top:3px}
#tm .era{font-size:12.5px;color:#e6ecf4;line-height:1.65;margin-top:8px;padding-top:8px;
   border-top:1px solid #28324a;min-height:38px}
#tm .ctl.dim{opacity:.32;pointer-events:none}
#tm .close{background:none;border:none;color:#889;font-size:15px;height:auto;padding:0}

/* before/after swipe */
#sw-divider{position:absolute;top:0;bottom:0;width:2px;background:#fff;box-shadow:0 0 8px #000;
   z-index:1100;display:none;cursor:ew-resize}
#sw-handle{position:absolute;top:50%;left:-20px;width:40px;height:40px;margin-top:-20px;background:#fff;
   color:#1a2030;border-radius:50%;display:flex;align-items:center;justify-content:center;
   font-size:17px;font-weight:700;cursor:ew-resize;box-shadow:0 2px 8px #000}
.sw-lab{position:absolute;top:12px;background:rgba(13,16,22,.92);border:1px solid #2a3550;border-radius:6px;
   padding:6px 11px;font-size:14px;font-weight:800;color:#cde;z-index:1100;display:none;font-family:ui-monospace,monospace}
#sw-lab-l{left:12px}#sw-lab-r{right:12px}
body.swiping #sw-divider,body.swiping .sw-lab{display:block}

.tm-badge{position:absolute;left:12px;bottom:12px;background:rgba(14,17,22,.9);border:1px solid #2a3550;
   border-radius:6px;padding:5px 10px;font-size:11px;color:#9cd;z-index:900}

/* fixed per-scene event panel — events stay pinned, never scroll away */
#scene-events{position:absolute;left:14px;top:88px;width:322px;z-index:850;
   background:rgba(11,14,20,.94);border:1px solid #2a3550;border-radius:9px;
   box-shadow:0 6px 22px rgba(0,0,0,.6);display:none;overflow:hidden}
#scene-events.on{display:block}
#scene-events .sh{display:flex;align-items:baseline;gap:8px;padding:8px 11px 6px;
   border-bottom:1px solid #232c3e}
#scene-events .sh .st{font-size:11px;font-weight:700;color:#cde;flex:1}
#scene-events .sh .sc{font-size:10px;color:#7a8696;font-family:ui-monospace,monospace}
#scene-list{max-height:60vh;overflow-y:auto;padding:7px}
#scene-list .empty{font-size:10px;color:#667;padding:10px 4px;text-align:center}
.ev-card{display:flex;gap:8px;background:#161b26;border:1px solid #2a3344;
   border-left:3px solid #5a7;border-radius:6px;padding:6px;margin-bottom:6px;cursor:pointer}
.ev-card:last-child{margin-bottom:0}
.ev-card:hover{border-color:#5a7aaa;background:#1b2230}
.ev-card.local{border-left-color:#fc6}
.ev-card.global{border-left-color:#4a8ac0}
.ev-card.fresh{animation:evflash 1.1s ease}
@keyframes evflash{0%{background:#2a3a52}100%{background:#161b26}}
.ev-card .ev-img{width:74px;height:74px;flex:none;object-fit:cover;border-radius:4px;
   background:#0a0d12;border:1px solid #2a3344}
.ev-card .ev-noimg{width:74px;height:74px;flex:none;border-radius:4px;background:#0e1218;
   border:1px solid #2a3344;display:flex;align-items:center;justify-content:center;
   font-size:8px;color:#566;text-align:center;line-height:1.3}
.ev-card .ev-body{flex:1;min-width:0}
.ev-card .ev-hd{display:flex;gap:6px;align-items:baseline;flex-wrap:wrap}
.ev-card .ev-date{color:#9cd;font-family:ui-monospace,monospace;font-size:11px;font-weight:700}
.ev-card .ev-kind{color:#fc8;font-family:ui-monospace,monospace;font-size:9px}
.ev-card .ev-scope{font-size:9px;color:#7a8696;margin-left:auto}
.ev-card .ev-sum{font-size:11px;color:#dde;line-height:1.55;margin-top:3px}
.ev-card .ev-go{font-size:9px;color:#7ab8d8;margin-top:3px}
.tl.clickable{cursor:pointer}
.tl.clickable:hover{border-left-color:#5af}

/* testimony panel — the human voices of the place */
#testimony{position:absolute;right:14px;top:88px;width:334px;z-index:850;
   background:rgba(11,13,19,.95);border:1px solid #3a2e3a;border-radius:9px;
   box-shadow:0 6px 22px rgba(0,0,0,.6);display:none;overflow:hidden}
#testimony.on{display:block}
#testimony .th{display:flex;align-items:baseline;gap:8px;padding:8px 11px 6px;border-bottom:1px solid #322833}
#testimony .th .tt{font-size:11px;font-weight:700;color:#e6c6d2;flex:1}
#testimony .th .tc{font-size:10px;color:#8a7a86;font-family:ui-monospace,monospace}
#testimony-list{max-height:62vh;overflow-y:auto;padding:8px}
.tq{background:#1a1620;border:1px solid #342a36;border-left:3px solid #c97;
   border-radius:6px;padding:7px 10px 8px;margin-bottom:7px}
.tq:last-child{margin-bottom:0}
.tq .tq-mark{color:#c97;font-size:17px;font-weight:700;line-height:0.4}
.tq .tq-text{font-size:11.5px;color:#e8e0e4;line-height:1.75;margin:2px 0 6px}
.tq .tq-by{font-size:10px;color:#b69aa6}
.tq .tq-role{font-size:9px;border-radius:3px;padding:1px 5px;margin-left:5px}
.tq-role.survivor{background:#4a2030;color:#f9bccb}
.tq-role.worker{background:#4a3a20;color:#fcc99a}
.tq-role.rescuer{background:#1f4030;color:#9ee0b4}
.tq-role.witness{background:#23344a;color:#9bc6e6}
.tq-role.family{background:#342848;color:#c9b0e6}
.tq .tq-src{font-size:9px;color:#7f88a4;text-decoration:none;margin-left:6px}
.tq .tq-src:hover{color:#9cf}

/* event viewer (link-based image viewer) */
#viewer{position:fixed;inset:0;background:rgba(6,8,12,.88);z-index:3000;display:none;
   align-items:center;justify-content:center;padding:24px}
#viewer.on{display:flex}
#viewer .vbox{background:#11151e;border:1px solid #34425a;border-radius:10px;max-width:860px;
   width:100%;max-height:92vh;overflow-y:auto;position:relative}
#viewer .vclose{position:absolute;right:8px;top:8px;z-index:2;background:rgba(0,0,0,.55);
   border:none;color:#dde;font-size:17px;width:32px;height:32px;border-radius:6px;cursor:pointer}
#v-img{background:#070a0e;min-height:220px;display:flex;align-items:center;justify-content:center}
#v-img img{max-width:100%;max-height:58vh;display:block}
#v-img.failed img,#v-img.noimg img{display:none}
#v-img.failed::after,#v-img.noimg::after{color:#7a8696;font-size:12px;padding:48px 30px;text-align:center;line-height:1.7}
#v-img.failed::after{content:'プレビュー画像を表示できませんでした — 下の「記事を開く」から確認してください'}
#v-img.noimg::after{content:'この事件にはプレビュー画像がありません — 記事リンクをご利用ください'}
#viewer .vmeta{padding:13px 17px 17px}
#viewer .vhd{display:flex;gap:9px;align-items:baseline;margin-bottom:6px}
#viewer .vdate{font-family:ui-monospace,monospace;color:#9cd;font-size:14px;font-weight:700}
#viewer .vkind{font-family:ui-monospace,monospace;color:#fc8;font-size:10px}
#viewer .vscope{font-size:10px;color:#7a8696;margin-left:auto}
#viewer .vsum{font-size:13.5px;color:#e2e8f0;line-height:1.75}
#viewer .vlink{display:inline-block;margin-top:11px;color:#bcd;font-size:12px;text-decoration:none;
   border:1px solid #34507a;border-radius:6px;padding:7px 13px}
#viewer .vlink:hover{background:#1a2740}
#viewer .vnav{display:flex;align-items:center;gap:12px;margin-top:13px}
#viewer .vnav button{background:#1f2942;color:#cde;border:1px solid #3a4a6a;border-radius:6px;
   width:40px;height:31px;font-size:13px;cursor:pointer}
#viewer .vnav button:disabled{opacity:.35;cursor:default}
#viewer .vnav #v-pos{font-size:11px;color:#889;font-family:ui-monospace,monospace}
#viewer .vcred{font-size:9px;color:#566;margin-top:8px}
.legend{font-size:11px;background:rgba(20,20,30,.92);padding:8px;border-radius:6px;color:#bbb;border:1px solid #333}
.legend i{width:10px;height:10px;display:inline-block;margin-right:4px;border-radius:50%}
.poi-ico{border-radius:50%;border:2px solid #fff;box-shadow:0 0 4px #000}
.poi-lbl{font-size:10px;color:#fff;background:rgba(10,12,18,.78);padding:1px 5px;border-radius:3px;white-space:nowrap;border:1px solid #3a4560}

/* per-panel fold buttons (works on desktop too — lets users hide individual panels) */
.fold-btn{background:none;border:none;color:#7a8696;cursor:pointer;font-size:14px;
   padding:0 5px;line-height:1;height:auto;min-width:auto}
.fold-btn:hover{color:#cde}
#tour.folded > :not(.thd),
#tm.folded > :not(.hd),
#scene-events.folded > :not(.sh),
#testimony.folded > :not(.th){display:none}
#scene-events.folded,#testimony.folded{max-height:none}

/* mobile: panels become a bottom sheet that covers ~60% of the screen so the map
   stays partly visible. Tab bar at the bottom switches between sheets. */
#mobile-tabs{display:none}
@media (max-width: 760px){
  #app{grid-template-columns:1fr}
  #side{display:none}
  #bigyear{display:none}
  .tm-badge,.legend{display:none}
  .leaflet-control-zoom{display:none}
  .leaflet-control-attribution{font-size:9px !important}

  #tour, #scene-events, #testimony, #tm{
    position:fixed !important;
    left:0 !important; right:0 !important; top:auto !important; bottom:46px !important;
    width:auto !important; max-width:none !important;
    transform:none !important;
    max-height:62vh; overflow-y:auto;
    z-index:1400; margin:0;
    border-radius:14px 14px 0 0;
    padding:9px 15px 16px;
    box-shadow:0 -6px 22px rgba(0,0,0,.65);
    display:none !important;
    background:rgba(11,14,20,.985);
    -webkit-overflow-scrolling:touch;
  }
  /* small drag-handle indicator at the top of each drawer */
  #tour.mob-open::before,#scene-events.mob-open::before,
  #testimony.mob-open::before,#tm.mob-open::before{
    content:""; display:block; width:36px; height:4px; margin:1px auto 8px;
    background:#3a4560; border-radius:2px;
  }
  #tour.mob-open, #scene-events.mob-open, #testimony.mob-open, #tm.mob-open{
    display:block !important;
  }
  #tour.folded.mob-open,#tm.folded.mob-open,
  #scene-events.folded.mob-open,#testimony.folded.mob-open{max-height:70px}

  /* readable typography inside the sheets */
  #tour .tname{font-size:17px}
  #tour .ntitle{font-size:13px;margin-top:11px}
  #tour .nbody{font-size:13.5px;line-height:1.78}
  #tour-img img{height:80px}
  #tour .nav{margin-top:14px}
  #tour .nav button{padding:0 12px;height:34px;font-size:12.5px;min-width:44px}
  #tour-life .lh{font-size:12.5px;margin-bottom:8px}
  .life-card{padding:8px 11px}
  .life-card .lc-topic{font-size:11.5px}
  .life-card .lc-text{font-size:12.5px;line-height:1.78}
  #scene-events .sh .st,#testimony .th .tt{font-size:12.5px}
  .ev-card .ev-img,.ev-card .ev-noimg{width:64px;height:64px}
  .ev-card .ev-date{font-size:12px}
  .ev-card .ev-sum{font-size:12.5px;line-height:1.7}
  .tq .tq-text{font-size:13px;line-height:1.85}
  .tq .tq-by{font-size:11px}
  #tm .ttl{font-size:13px}
  #tm .frame{font-size:11px}
  #tm .era{font-size:13px;line-height:1.7}

  /* compact tab bar at the very bottom */
  #mobile-tabs{
    display:flex !important;
    position:fixed; left:0; right:0; bottom:0;
    z-index:1500; gap:0;
    background:rgba(8,11,17,.98); border-top:1px solid #2a3550;
    padding:4px 4px 5px;
    box-shadow:0 -2px 12px rgba(0,0,0,.5);
  }
  #mobile-tabs button{
    flex:1; background:transparent; color:#bcc8d6;
    border:none; border-radius:6px;
    padding:5px 2px; font-size:10.5px; cursor:pointer; line-height:1.25;
    -webkit-tap-highlight-color:rgba(74,138,192,.35);
  }
  #mobile-tabs button.active{background:#2a5a8a;color:#fff}
  #mobile-tabs button.disabled{opacity:.32}

  #splash h1{font-size:22px;line-height:1.4}
  #splash p{font-size:13.5px;line-height:1.9}
  #splash button{padding:13px 22px;font-size:14px}
  #splash .kicker{font-size:11px}
}
</style></head>
<body>

<div id="splash">
  <div class="kicker">Public OSINT · Mekong border zones</div>
  <h1>メコン詐欺コンパウンド・タイムマシン</h1>
  <p>ジャーナリストや調査機関でさえ生身では近づけない7つの「閉じた都市」を、
     公開された衛星画像だけを使って上空から、そして時間をさかのぼって巡ります。</p>
  <div class="btns">
    <button id="sp-tour">▶ ガイドツアーを始める</button>
    <button id="sp-explore">自由に探索する</button>
  </div>
  <div class="fine">衛星: Esri Wayback ／ 制裁: OFAC SDN ／ 地図: OpenStreetMap・MS Buildings</div>
</div>

<div id="app"><div id="side">
<h1>Compound Time Machine — Mekong</h1>
<small>公開OSINTのみ。座標は観測建物クラスタ重心。</small>
<div class="meta" id="meta-box"></div>
<button class="tourbtn" id="start-tour">▶ ガイドツアーを開始（全${TOURLEN}地点）</button>
<small>各候補カードのクリックで個別タイムマシンが起動します。</small>
<h2>Global Timeline</h2><div id="global-events"></div>
<h2>Candidates</h2><div id="list"></div>
<h2>OFAC SDN (Cambodia/Burma)</h2><div id="legals"></div>
<h2>Schema layers (POC v5)</h2>
<div class="layers">
<div class="impl">● compound_candidate / observation / alias</div>
<div class="impl">● imagery_release — Wayback時系列タイル</div>
<div class="impl">● poi — OSM地物 + 建物密度クラスタ</div>
<div class="impl">● narration / era_caption — ツアー原稿</div>
<div class="impl">● event / legal_entity / wallet</div>
<div class="stub">○ capacity_estimate (空) / testimony (未)</div>
</div>
<h2>Caveats</h2>
<div class="layers stub">
flyTo中心は観測建物クラスタ重心(報道座標は最大1.5kmずれる)。<br>
衛星フレームは z15 タイルのハッシュ差分抽出、雲・季節差も含む。<br>
KK Park / Dara Sakor / O'Smach はOSM整備が薄くPOI希薄。<br>
ナレーション/イベントは公開報道に基づく編集テキスト、現地確認ではない。<br>
画像はWikimedia Commonsの自由ライセンス画像(地点の写真で個別事件の写真ではない)。出典・ライセンスを各画像に併記。
</div>
</div><div id="map">
  <div id="bigyear">—</div>
  <div id="scene-events">
    <div class="sh"><span class="st">この地点の出来事</span><span class="sc" id="scene-yr"></span>
      <button class="fold-btn" data-fold="scene-events" title="折りたたみ">▾</button></div>
    <div id="scene-list"></div>
  </div>
  <div id="testimony">
    <div class="th"><span class="tt">証言 — ここにいた人々の声</span><span class="tc" id="testimony-n"></span>
      <button class="fold-btn" data-fold="testimony" title="折りたたみ">▾</button></div>
    <div id="testimony-list"></div>
  </div>
  <div class="tm-badge" id="tm-badge">▶ でガイドツアー / 候補クリックで個別起動</div>

  <div id="sw-divider"><div id="sw-handle">⇄</div></div>
  <div class="sw-lab" id="sw-lab-l">—</div>
  <div class="sw-lab" id="sw-lab-r">—</div>

  <div id="tour">
    <div class="thd">
      <span class="tname" id="tour-name">—</span>
      <span class="stop" id="tour-stop"></span>
      <button class="fold-btn" data-fold="tour" title="折りたたみ">▾</button>
      <button class="close" id="tour-close" title="ツアー終了">✕</button>
    </div>
    <div id="tour-img"></div>
    <div class="counter" id="tour-counter" style="display:none">観測された構造物フットプリント <b id="tour-count">0</b> 件</div>
    <div id="tour-narr"></div>
    <div id="tour-life"></div>
    <div class="nav">
      <button id="tour-prev">◀ 前へ</button>
      <span class="sp"></span>
      <button id="tour-replay" title="この地点の建設過程をもう一度">⟳ 建設を再生</button>
      <button id="tour-next">次へ ▶</button>
    </div>
  </div>

  <div id="tm">
    <div class="hd">
      <span class="ttl" id="tm-ttl">—</span>
      <span class="frame" id="tm-frame"></span>
      <button id="tm-swipe" class="wide" title="2014年と現在を並べて比較">◫ 比較</button>
      <select id="tm-speed" title="再生速度">
        <option value="3600">ゆっくり</option>
        <option value="2400" selected>ふつう</option>
        <option value="1500">はやい</option>
      </select>
      <button class="fold-btn" data-fold="tm" title="折りたたみ">▾</button>
      <button class="close" id="tm-close" title="閉じる">✕</button>
    </div>
    <div class="ctl" id="tm-ctl">
      <button id="tm-play" title="再生 / 停止">▶</button>
      <input type="range" id="tm-range" min="0" max="0" value="0" step="1">
    </div>
    <div class="scale"><span id="tm-first"></span><span id="tm-last"></span></div>
    <div class="era" id="tm-era"></div>
  </div>
</div></div>

<div id="viewer">
  <div class="vbox">
    <button class="vclose" id="v-close" title="閉じる">✕</button>
    <div id="v-img"></div>
    <div class="vmeta">
      <div class="vhd">
        <span class="vdate" id="v-date"></span>
        <span class="vkind" id="v-kind"></span>
        <span class="vscope" id="v-scope"></span>
      </div>
      <div class="vsum" id="v-sum"></div>
      <a class="vlink" id="v-link" target="_blank" rel="noopener noreferrer">記事を開く ↗</a>
      <div class="vcred">画像は出典記事の og:image をリンク表示(報道写真・著作権は各媒体に帰属)。表示できない場合は記事リンクから。</div>
      <div class="vnav">
        <button id="v-prev" title="前の事件">◀</button>
        <span id="v-pos"></span>
        <button id="v-next" title="次の事件">▶</button>
      </div>
    </div>
  </div>
</div>

<div id="mobile-tabs">
  <button data-tab="tour">📖<br>ツアー</button>
  <button data-tab="scene-events">📰<br>出来事</button>
  <button data-tab="testimony">🗣<br>証言</button>
  <button data-tab="tm">🕒<br>時間</button>
</div>

<script src="vendor/leaflet/leaflet.js"></script>
<script>
const CANDIDATES=__CANDIDATES__,GLOBAL_EVENTS=__GEVENTS__,META=__META__;
const TOP_LEGALS=__LEGALS__,WALLETS_SUM=__WSUM__;
const TOUR_Z0=15.2,TOUR_Z1=16.7;   // cinematic zoom range during a tour stop

const t=META.totals;
document.getElementById('meta-box').innerHTML=`
<div class="row"><span class="k">generated</span><b>${META.generated_at}</b></div>
<div class="row"><span class="k">candidates</span><b>${t.candidates}</b></div>
<div class="row"><span class="k">total obs</span><b>${t.observations_total}</b></div>
<div class="row"><span class="k">imagery frames</span><b>${t.imagery_frames}</b></div>
<div class="row"><span class="k">POIs</span><b>${t.pois}</b></div>
<div class="row"><span class="k">events</span><b>${t.events}</b></div>
<div class="row"><span class="k">legal_entities</span><b>${t.legal_entities}</b></div>
<div class="row"><span class="k">wallets</span><b>${t.wallets}</b></div>`;

const osmLayer=L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OSM',maxZoom:19});
const esriSat =L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',{attribution:'Esri',maxZoom:19});
const cartoDark=L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',{attribution:'CARTO',maxZoom:19,subdomains:'abcd'});
const map=L.map('map',{layers:[cartoDark],zoomSnap:0,zoomDelta:0.5,zoomControl:true}).setView([12.5,104.0],6);
const candLayer=L.layerGroup().addTo(map);
const osmLayerObs=L.layerGroup(),msLayerObs=L.layerGroup();
const uncLayer=L.layerGroup().addTo(map);
const poiLayer=L.layerGroup().addTo(map);
const lifeLayer=L.layerGroup().addTo(map);
const waybackLayer=L.tileLayer('',{attribution:'Esri Wayback',maxZoom:19,maxNativeZoom:18,zIndex:200});
// international borders + place labels (transparent reference tiles), kept above imagery
const bordersLayer=L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
   {attribution:'Esri Reference',maxZoom:19,zIndex:400}).addTo(map);

const colors={scam:'#e44',sez:'#48c',mixed:'#fc4'};
const POI_COL={casino:'#f48ab0',hotel:'#fcb86a',resort:'#86c8ff',building_cluster:'#ffd24a',
  worship:'#c79cff',bank:'#9adf9a',market:'#9adf9a',admin:'#9aa6b8',fuel:'#9aa6b8',
  transit:'#9aa6b8',food:'#9aa6b8',industrial:'#bdd99a'};

CANDIDATES.forEach(c=>{
  L.circle([c.view_lat,c.view_lon],{radius:1200,color:colors[c.kind]||'#888',weight:1,fillOpacity:0.04}).addTo(uncLayer);
  const m=L.circleMarker([c.view_lat,c.view_lon],{radius:10,color:colors[c.kind]||'#888',weight:2,
     fillColor:colors[c.kind]||'#888',fillOpacity:0.7}).addTo(candLayer);
  c._marker=m;
  m.bindTooltip(c.label,{direction:'top'});
  m.on('click',()=>{ tour.active?gotoStop(CANDIDATES.indexOf(c)):startTimeMachine(c); });
  c.osm_sample.forEach(o=>{
    const tg=o[2].tags||{};let col='#5af';
    if(tg.amenity==='casino')col='#f8a';else if(tg.tourism==='hotel')col='#fc8';
    else if(tg.landuse==='industrial')col='#bd9';
    L.circleMarker([o[0],o[1]],{radius:2,weight:0,fillColor:col,fillOpacity:0.55}).addTo(osmLayerObs);
  });
  c.ms_sample.forEach(o=>L.circleMarker([o[0],o[1]],{radius:2,weight:0,fillColor:'#9d6',fillOpacity:0.5}).addTo(msLayerObs));
  c.poi.forEach(p=>{
    const col=POI_COL[p.type]||'#9aa6b8';
    const popup=`<b>${p.name}</b><br><small>${p.descr}</small><br><small style="color:#888">confidence: ${p.conf}</small>`;
    if(p.type==='building_cluster'){
      L.circleMarker([p.lat,p.lon],{radius:9,color:col,weight:2,fill:false,dashArray:'3 3'})
        .addTo(poiLayer).bindTooltip(p.name,{direction:'top'}).bindPopup(popup);
    }else{
      const ico=L.divIcon({html:`<div class="poi-ico" style="width:13px;height:13px;background:${col}"></div>`,iconSize:[13,13],iconAnchor:[7,7]});
      L.marker([p.lat,p.lon],{icon:ico}).addTo(poiLayer)
        .bindTooltip(`<span class="poi-lbl">${p.name}</span>`,{permanent:true,direction:'right',offset:[8,0]}).bindPopup(popup);
    }
  });
  // local-life spots — everyday places around the compound (OSM)
  (c.spots||[]).forEach(s=>{
    const emo=s.cat==='food'?'🍜':s.cat==='market'?'🛒':'🏨';
    const ico=L.divIcon({html:`<span class="life-ico">${emo}</span>`,iconSize:[16,16],iconAnchor:[8,8],className:''});
    L.marker([s.lat,s.lon],{icon:ico}).addTo(lifeLayer)
      .bindTooltip(`${emo} ${s.name}`,{direction:'top'});
  });
});

L.control.layers(
  {'Dark (Carto)':cartoDark,'Satellite (Esri current)':esriSat,'OSM':osmLayer},
  {'国境線・地名':bordersLayer,'Candidates':candLayer,'POIs':poiLayer,
   '生活拠点(食堂・市場ほか)':lifeLayer,
   'OSM buildings':osmLayerObs,'MS buildings':msLayerObs,'Uncertainty':uncLayer},
  {collapsed:true}
).addTo(map);
const legend=L.control({position:'bottomright'});
legend.onAdd=function(){
  const d=L.DomUtil.create('div','legend');
  d.innerHTML=`<b>POI</b><br><i style="background:#f48ab0"></i>casino <i style="background:#fcb86a"></i>hotel
   <i style="background:#86c8ff"></i>resort <i style="background:#ffd24a"></i>建物クラスタ`;
  return d;
};
legend.addTo(map);

/* ---------- Time machine (load-synced playback + cinematic zoom) ---------- */
const tm=document.getElementById('tm'),tmBadge=document.getElementById('tm-badge');
const range=document.getElementById('tm-range'),playBtn=document.getElementById('tm-play');
const speedSel=document.getElementById('tm-speed'),eraBox=document.getElementById('tm-era');
const bigYear=document.getElementById('bigyear');
let tmCand=null,tmFrames=[],playing=false,waitingLoad=false,loadWatch=null;

function eraFor(c,year){ let p='';(c&&c.eras||[]).forEach(e=>{if(e.year<=year)p=e.caption;});return p; }

/* fixed per-scene event panel — cards stay pinned and accumulate, never scroll away */
const sceneEvents=document.getElementById('scene-events');
const sceneList=document.getElementById('scene-list');
const testimonyEl=document.getElementById('testimony');
const testimonyList=document.getElementById('testimony-list');
let evtList=[],evtFired=0,lastFrameIdx=-1;
const ROLE_JA={survivor:'生還者',worker:'労働者',rescuer:'救出者',witness:'目撃者',family:'家族'};
function renderTestimony(c){
  const ts=(c&&c.testimony)||[];
  testimonyList.innerHTML='';
  document.getElementById('testimony-n').textContent=ts.length?ts.length+'件の声':'';
  if(!ts.length){ testimonyEl.classList.remove('on'); return; }
  ts.forEach(t=>{
    const d=document.createElement('div');d.className='tq';
    d.innerHTML='<span class="tq-mark">❝</span>'
      +`<div class="tq-text">${t.quote}</div>`
      +`<div class="tq-by">— ${t.speaker}・${t.year}`
      +`<span class="tq-role ${t.role}">${ROLE_JA[t.role]||t.role}</span>`
      +(t.src?`<a class="tq-src" href="${t.src}" target="_blank" rel="noopener noreferrer">出典 ↗</a>`:'')
      +'</div>';
    testimonyList.appendChild(d);
  });
  testimonyEl.classList.add('on');
}
function evtObj(e,scope){
  return {date:e.date,kind:e.kind,summary:e.summary,res:e.res||'day',
          url:e.url||'',img:e.img||'',scope:scope};
}
function buildEventList(c){
  const loc=(c.events||[]).map(e=>evtObj(e,'local'));
  const glo=GLOBAL_EVENTS.map(e=>evtObj(e,'global'));
  return loc.concat(glo).sort((a,b)=>a.date<b.date?-1:a.date>b.date?1:0);
}
function fmtDate(d,res){ return res==='year'?d.slice(0,4):res==='month'?d.slice(0,7):d; }
const SCENE_EMPTY='<div class="empty">この年代にはまだ記録された出来事がありません</div>';
function clearScene(){ sceneList.innerHTML=SCENE_EMPTY; evtFired=0; }
function eventCard(e,idx,fresh){
  const d=document.createElement('div');
  d.className='ev-card '+e.scope+(fresh?' fresh':'');
  const img=e.img
    ? `<img class="ev-img" src="${e.img}" alt="" referrerpolicy="no-referrer" `
      +`onerror="this.style.display='none'">`
    : '<div class="ev-noimg">プレビュー<br>画像なし</div>';
  d.innerHTML=img+'<div class="ev-body"><div class="ev-hd">'
    +`<span class="ev-date">${fmtDate(e.date,e.res)}</span>`
    +`<span class="ev-kind">${e.kind}</span>`
    +`<span class="ev-scope">${e.scope==='local'?'この地点':'地域全体'}</span></div>`
    +`<div class="ev-sum">${e.summary}</div>`
    +`<div class="ev-go">${e.img?'🔍 クリックで写真・記事':'🔗 クリックで記事'}</div></div>`;
  d.onclick=()=>openViewer(evtList,idx);
  return d;
}
function rebuildScene(upto){
  sceneList.innerHTML='';
  for(let k=upto-1;k>=0;k--)sceneList.appendChild(eventCard(evtList[k],k,false));
  if(!upto)sceneList.innerHTML=SCENE_EMPTY;
}
// "scene" = the current satellite frame. Events reached at this frame are pinned in;
// they accumulate (newest on top) and never auto-dismiss, so they stay readable.
function syncEvents(i){
  if(i>lastFrameIdx){
    const fd=tmFrames[i].date,isLast=i>=tmFrames.length-1;
    while(evtFired<evtList.length){
      const e=evtList[evtFired];
      if(isLast||e.date<=fd){
        const em=sceneList.querySelector('.empty'); if(em)em.remove();
        sceneList.insertBefore(eventCard(e,evtFired,true),sceneList.firstChild);
        sceneList.scrollTop=0;
        evtFired++;
      } else break;
    }
  }else if(i<lastFrameIdx){
    const fd=tmFrames[i].date;
    evtFired=(i>=tmFrames.length-1)?evtList.length:evtList.filter(e=>e.date<=fd).length;
    rebuildScene(evtFired);
  }
}
function setFrame(i){
  if(!tmFrames.length)return;
  i=Math.max(0,Math.min(tmFrames.length-1,i));range.value=i;
  const f=tmFrames[i];waybackLayer.setUrl(f.url);
  bigYear.textContent=f.date.slice(0,4);
  document.getElementById('tm-frame').textContent=`${f.date} · ${i+1}/${tmFrames.length}`;
  eraBox.textContent=eraFor(tmCand,+f.date.slice(0,4));
  document.getElementById('scene-yr').textContent=`〜 ${f.date.slice(0,4)}`;
  syncEvents(i);
  lastFrameIdx=i;
}

/* ---------- event viewer (link-based image viewer) ---------- */
const viewer=document.getElementById('viewer');
let viewerList=[],viewerIdx=0;
function renderViewer(){
  const e=viewerList[viewerIdx];
  if(!e)return;
  const vi=document.getElementById('v-img');
  vi.className='';
  if(e.img){
    vi.innerHTML=`<img src="${e.img}" alt="" referrerpolicy="no-referrer" `
      +`onerror="document.getElementById('v-img').className='failed'">`;
  }else{ vi.innerHTML=''; vi.className='noimg'; }
  document.getElementById('v-date').textContent=fmtDate(e.date,e.res);
  document.getElementById('v-kind').textContent=e.kind;
  document.getElementById('v-scope').textContent=
    e.scope==='local'?'この地点の事件':(e.scope==='global'?'地域全体の出来事':'');
  document.getElementById('v-sum').textContent=e.summary;
  const lk=document.getElementById('v-link');
  if(e.url){ lk.href=e.url; lk.style.display=''; } else { lk.style.display='none'; }
  document.getElementById('v-pos').textContent=`${viewerIdx+1} / ${viewerList.length}`;
  document.getElementById('v-prev').disabled=viewerIdx<=0;
  document.getElementById('v-next').disabled=viewerIdx>=viewerList.length-1;
}
function openViewer(list,idx){
  viewerList=list||[]; viewerIdx=idx||0;
  if(!viewerList.length)return;
  renderViewer(); viewer.classList.add('on');
}
function closeViewer(){ viewer.classList.remove('on'); }
function viewerStep(d){
  const n=viewerIdx+d;
  if(n>=0&&n<viewerList.length){ viewerIdx=n; renderViewer(); }
}
document.getElementById('v-close').addEventListener('click',closeViewer);
document.getElementById('v-prev').addEventListener('click',()=>viewerStep(-1));
document.getElementById('v-next').addEventListener('click',()=>viewerStep(1));
viewer.addEventListener('click',e=>{ if(e.target===viewer)closeViewer(); });
document.addEventListener('keydown',e=>{
  if(!viewer.classList.contains('on'))return;
  if(e.key==='Escape')closeViewer();
  else if(e.key==='ArrowLeft')viewerStep(-1);
  else if(e.key==='ArrowRight')viewerStep(1);
});

function clearWatch(){ if(loadWatch){clearTimeout(loadWatch);loadWatch=null;} }
function stopPlay(){ playing=false;waitingLoad=false;clearWatch();playBtn.textContent='▶'; }
// never advance until the current frame's tiles are loaded, then dwell for the speed setting
function showAndContinue(idx){
  if(!playing)return;
  waitingLoad=true;
  setFrame(idx);
  if(tour.active&&tmCand&&tmFrames.length>1){          // cinematic slow zoom-in
    const z=TOUR_Z0+(TOUR_Z1-TOUR_Z0)*idx/(tmFrames.length-1);
    map.setView([tmCand.view_lat,tmCand.view_lon],z,{animate:true,duration:0.8});
  }
  clearWatch();
  loadWatch=setTimeout(()=>onFrameLoaded(idx),6500);   // watchdog if 'load' never fires
}
function onFrameLoaded(idx){
  if(!waitingLoad||!playing)return;
  waitingLoad=false;clearWatch();
  loadWatch=setTimeout(()=>{
    if(!playing)return;
    if(idx>=tmFrames.length-1){ stopPlay(); return; }
    showAndContinue(idx+1);
  },+speedSel.value);
}
waybackLayer.on('load',()=>{ if(waitingLoad)onFrameLoaded(+range.value); });
function startPlay(){
  if(tmFrames.length<2||swipe.on)return;
  playing=true;playBtn.textContent='⏸';
  let s=+range.value; if(s>=tmFrames.length-1)s=0;
  showAndContinue(s);
}
function armTimeMachine(c,atOldest){
  tmCand=c;tmFrames=c.imagery||[];stopPlay();exitSwipe();
  evtList=buildEventList(c);lastFrameIdx=-1;clearScene();
  if(!tmFrames.length){tm.classList.remove('on');document.body.classList.remove('tm-on');
    sceneEvents.classList.remove('on');testimonyEl.classList.remove('on');return false;}
  sceneEvents.classList.add('on');
  renderTestimony(c);
  document.getElementById('tm-ttl').textContent=c.label;
  document.getElementById('tm-first').textContent=tmFrames[0].date;
  document.getElementById('tm-last').textContent=tmFrames[tmFrames.length-1].date;
  range.max=tmFrames.length-1;
  if(!map.hasLayer(waybackLayer))waybackLayer.addTo(map);
  waybackLayer.bringToFront();tm.classList.add('on');document.body.classList.add('tm-on');
  setFrame(atOldest?0:tmFrames.length-1);
  return true;
}
function startTimeMachine(c){
  document.querySelectorAll('.card').forEach(el=>el.classList.toggle('active',+el.dataset.id===c.id));
  if(armTimeMachine(c,false))tmBadge.style.display='none';
  else{tmBadge.style.display='block';tmBadge.textContent=`${c.label}: 履歴衛星フレームなし`;}
  map.flyTo([c.view_lat,c.view_lon],16,{duration:1.2});
}
range.addEventListener('input',()=>{stopPlay();setFrame(+range.value);});
playBtn.addEventListener('click',()=>{playing?stopPlay():startPlay();});
speedSel.addEventListener('pointerdown',e=>e.stopPropagation());
document.getElementById('tm-close').addEventListener('click',()=>{
  stopPlay();exitSwipe();clearScene();sceneEvents.classList.remove('on');
  testimonyEl.classList.remove('on');
  tm.classList.remove('on');document.body.classList.remove('tm-on');
  if(map.hasLayer(waybackLayer))map.removeLayer(waybackLayer);
  tmBadge.style.display='block';tmBadge.textContent='▶ でガイドツアー / 候補クリックで個別起動';
  document.querySelectorAll('.card').forEach(el=>el.classList.remove('active'));
});

/* ---------- Before/After swipe (inline side-by-side) ---------- */
const swDivider=document.getElementById('sw-divider'),swHandle=document.getElementById('sw-handle');
const swipe={on:false,old:null,neu:null,x:0};
function swClip(){
  if(!swipe.on)return;
  const nw=map.containerPointToLayerPoint([0,0]),se=map.containerPointToLayerPoint(map.getSize());
  const clipX=nw.x+swipe.x;
  if(swipe.old)swipe.old.getContainer().style.clip=`rect(${nw.y}px,${clipX}px,${se.y}px,${nw.x}px)`;
  if(swipe.neu)swipe.neu.getContainer().style.clip=`rect(${nw.y}px,${se.x}px,${se.y}px,${clipX}px)`;
  swDivider.style.left=swipe.x+'px';
}
function enterSwipe(){
  if(swipe.on||!tmCand||tmFrames.length<2)return;
  stopPlay();swipe.on=true;document.body.classList.add('swiping');
  document.getElementById('tm-ctl').classList.add('dim');
  document.getElementById('tm-swipe').classList.add('act');
  const o=tmFrames[0],n=tmFrames[tmFrames.length-1];
  swipe.old=L.tileLayer(o.url,{maxZoom:19,maxNativeZoom:18,zIndex:200}).addTo(map);
  swipe.neu=L.tileLayer(n.url,{maxZoom:19,maxNativeZoom:18,zIndex:201}).addTo(map);
  if(map.hasLayer(waybackLayer))map.removeLayer(waybackLayer);
  document.getElementById('sw-lab-l').textContent='◀ '+o.date.slice(0,4);
  document.getElementById('sw-lab-r').textContent=n.date.slice(0,4)+' ▶';
  swipe.x=map.getSize().x/2;
  map.on('move',swClip);swClip();
}
function exitSwipe(){
  if(!swipe.on){document.getElementById('tm-swipe').classList.remove('act');return;}
  swipe.on=false;document.body.classList.remove('swiping');
  document.getElementById('tm-ctl').classList.remove('dim');
  document.getElementById('tm-swipe').classList.remove('act');
  map.off('move',swClip);
  if(swipe.old)map.removeLayer(swipe.old);
  if(swipe.neu)map.removeLayer(swipe.neu);
  swipe.old=swipe.neu=null;
  if(tmFrames.length){ if(!map.hasLayer(waybackLayer))waybackLayer.addTo(map); waybackLayer.bringToFront(); setFrame(+range.value); }
}
document.getElementById('tm-swipe').addEventListener('click',()=>{ swipe.on?exitSwipe():enterSwipe(); });
let swDrag=false;
function swMove(e){
  if(!swDrag)return;
  const r=document.getElementById('map').getBoundingClientRect();
  const cx=(e.touches?e.touches[0].clientX:e.clientX);
  swipe.x=Math.max(24,Math.min(r.width-24,cx-r.left));
  swClip();
}
swHandle.addEventListener('pointerdown',e=>{swDrag=true;map.dragging.disable();e.preventDefault();});
window.addEventListener('pointermove',swMove);
window.addEventListener('pointerup',()=>{ if(swDrag){swDrag=false;map.dragging.enable();} });

/* ---------- Guided tour ---------- */
const tour={active:false,i:-1};
const tourPanel=document.getElementById('tour');
let stepToken=0;
const TOUR_INTRO=[
  {title:'ようこそ',body:'これから巡る7地点は、メコン地域の国境に点在する詐欺コンパウンド候補です。'
    +'ジャーナリストや調査機関でさえ生身では容易に近づけません。あなたは公開された衛星画像だけを使い、'
    +'上空から——そして時間をさかのぼって——これらの「閉じた都市」がどう生まれたかを見ます。'},
  {title:'歩き方',body:'各停留所では地図がその場所へ降下し、衛星のタイムマシンが自動再生されます。'
    +'空き地が建物群へ変わる数年間を、下の年代キャプションと一緒に追ってください。'
    +'「次へ」で移動、「⟳ 建設を再生」でもう一度、「◫ 比較」で2014年と現在を並べられます。'},
];
function renderCards(cards){
  return cards.map(n=>`${n.title?`<div class="ntitle">${n.title}</div>`:''}<div class="nbody">${n.body}</div>`).join('');
}
function countUp(el,target){
  const t0=performance.now(),dur=1100;
  (function tick(now){
    const p=Math.min(1,(now-t0)/dur);
    el.textContent=Math.round(target*(1-Math.pow(1-p,3))).toLocaleString();
    if(p<1)requestAnimationFrame(tick);
  })(performance.now());
}
function renderIntro(){
  stepToken++;stopPlay();exitSwipe();
  document.getElementById('tour-name').textContent='メコン詐欺コンパウンド・タイムマシン';
  document.getElementById('tour-stop').textContent='はじめに';
  document.getElementById('tour-counter').style.display='none';
  document.getElementById('tour-img').classList.remove('on');
  document.getElementById('tour-life').style.display='none';
  document.getElementById('tour-narr').innerHTML=renderCards(TOUR_INTRO);
  document.getElementById('tour-prev').disabled=true;
  document.getElementById('tour-next').textContent='▶ 出発';
  document.getElementById('tour-replay').style.display='none';
  tm.classList.remove('on');document.body.classList.remove('tm-on');
  document.querySelectorAll('.card').forEach(el=>el.classList.remove('active'));
  map.flyTo([12.5,104.0],6,{duration:1.4});
}
function renderStop(){
  const my=++stepToken;
  const c=CANDIDATES[tour.i];
  document.getElementById('tour-name').textContent=c.label;
  document.getElementById('tour-stop').textContent=`STOP ${tour.i+1} / ${CANDIDATES.length}`;
  const ti=document.getElementById('tour-img');
  if(c.images&&c.images.length){
    const im=c.images[0];
    ti.innerHTML=`<img src="${im.path}" alt=""><div class="cap">${im.caption}`
      +`<span class="cred"> ／ 📷 ${im.credit}</span></div>`;
    ti.classList.add('on');
  }else{ ti.classList.remove('on'); ti.innerHTML=''; }
  document.getElementById('tour-narr').innerHTML=
    renderCards(c.narration&&c.narration.length?c.narration:[{title:'',body:'(ナレーション未登録)'}]);
  const lf=document.getElementById('tour-life');
  if(c.life&&c.life.length){
    lf.innerHTML='<div class="lh">📱 現地の生活 — この街の空気</div>'
      +c.life.map(s=>'<div class="life-card"><div class="lc-hd">'
        +`<span class="lc-av">📍</span><span class="lc-topic">${s.topic}</span>`
        +`<span class="lc-src">— ${s.src_label}</span></div>`
        +`<div class="lc-text">${s.text}</div>`
        +(s.src?`<a class="lc-link" href="${s.src}" target="_blank" rel="noopener noreferrer">出典 ↗</a>`:'')
        +'</div>').join('');
    lf.style.display='';
  }else{ lf.style.display='none'; lf.innerHTML=''; }
  const cnt=document.getElementById('tour-counter');
  cnt.style.display='';countUp(document.getElementById('tour-count'),c.bld_count);
  document.getElementById('tour-prev').disabled=false;
  document.getElementById('tour-next').textContent=tour.i===CANDIDATES.length-1?'完了 ✓':'次へ ▶';
  document.getElementById('tour-replay').style.display='';
  document.querySelectorAll('.card').forEach(el=>el.classList.toggle('active',+el.dataset.id===c.id));
  const armed=armTimeMachine(c,true);
  tmBadge.style.display=armed?'none':'block';
  if(!armed)tmBadge.textContent=`${c.label}: 履歴衛星フレームなし`;
  map.flyTo([c.view_lat,c.view_lon],TOUR_Z0,{duration:1.6});
  if(armed)setTimeout(()=>{ if(tour.active&&my===stepToken)startPlay(); },2100);
}
function gotoStop(i){
  if(i<-1||i>=CANDIDATES.length)return;
  tour.i=i;
  (i<0?renderIntro:renderStop)();
}
function startTour(){
  tour.active=true;tour.i=-1;
  document.body.classList.add('touring');
  tourPanel.classList.add('on');
  setTimeout(()=>map.invalidateSize(),60);
  renderIntro();
}
function endTour(){
  tour.active=false;stepToken++;
  tourPanel.classList.remove('on');
  document.body.classList.remove('touring');
  stopPlay();exitSwipe();clearScene();sceneEvents.classList.remove('on');
  testimonyEl.classList.remove('on');
  setTimeout(()=>map.invalidateSize(),60);
}
document.getElementById('start-tour').addEventListener('click',startTour);
document.getElementById('tour-close').addEventListener('click',endTour);
document.getElementById('tour-prev').addEventListener('click',()=>gotoStop(tour.i-1));
document.getElementById('tour-next').addEventListener('click',()=>{
  if(tour.i>=CANDIDATES.length-1)endTour();else gotoStop(tour.i+1);
});
document.getElementById('tour-replay').addEventListener('click',()=>{
  exitSwipe();stopPlay();range.value=0;setFrame(0);startPlay();
});

/* ---------- Splash ---------- */
document.getElementById('sp-tour').addEventListener('click',()=>{
  document.getElementById('splash').classList.add('hidden');
  map.invalidateSize();startTour();
});
document.getElementById('sp-explore').addEventListener('click',()=>{
  document.getElementById('splash').classList.add('hidden');
  map.invalidateSize();
});

/* ---------- Sidebar ---------- */
const list=document.getElementById('list');
CANDIDATES.forEach(c=>{
  const div=document.createElement('div');div.className='card';div.dataset.id=c.id;
  div.innerHTML=`<div class="label">${c.label}</div>
    <div class="meta-row">
      <span class="badge b-${c.kind}">${c.kind}</span>
      <span class="badge b-${c.status}">${c.status}</span>
      ${c.imagery.length?`<span class="stat cam">◷${c.imagery.length}frames</span>`:'<span class="stat" style="color:#c66">no imagery</span>'}
      ${c.poi.length?`<span class="stat poi">⚑${c.poi.length}POI</span>`:''}
    </div>
    <div class="meta-row">${c.country} · ${c.state}${c.imagery.length?` · 衛星 ${c.imagery[0].date.slice(0,4)}–${c.imagery[c.imagery.length-1].date.slice(0,4)}`:''}</div>
    <div class="alias">${c.aliases.map(a=>a[0]).join(' / ')}</div>`;
  div.onclick=()=>{ tour.active?gotoStop(CANDIDATES.indexOf(c)):startTimeMachine(c); };
  list.appendChild(div);
});
const ge=document.getElementById('global-events');
GLOBAL_EVENTS.forEach((e,i)=>{
  const d=document.createElement('div');d.className='tl';
  d.innerHTML=`<span class="d">${e.date}</span><span class="k">${e.kind}</span><br><span class="s">${e.summary}</span>`;
  if(e.url||e.img){ d.classList.add('clickable'); d.onclick=()=>openViewer(GLOBAL_EVENTS,i); }
  ge.appendChild(d);
});
const lg=document.getElementById('legals');
TOP_LEGALS.forEach(le=>{
  const d=document.createElement('div');d.className='sanc';
  d.innerHTML=`⚖ ${le.name} <small style="color:#888">(${le.jurisdiction||'-'}) ${le.programs||''}</small>`;
  lg.appendChild(d);
});

/* ---------- per-panel fold buttons + mobile drawer / tab bar ---------- */
const MOB_PANELS=['tour','scene-events','testimony','tm'];
const isMobile=()=>window.matchMedia('(max-width: 760px)').matches;

document.querySelectorAll('.fold-btn').forEach(btn=>{
  btn.addEventListener('click',e=>{
    e.stopPropagation();
    const id=btn.dataset.fold;
    const panel=document.getElementById(id);
    panel.classList.toggle('folded');
    btn.textContent=panel.classList.contains('folded')?'▴':'▾';
  });
});

function updateMobileTabs(){
  MOB_PANELS.forEach(id=>{
    const panel=document.getElementById(id);
    const btn=document.querySelector(`#mobile-tabs button[data-tab="${id}"]`);
    if(!panel||!btn)return;
    btn.classList.toggle('disabled', !panel.classList.contains('on'));
    btn.classList.toggle('active', panel.classList.contains('mob-open'));
  });
}
function mobToggle(id){
  if(!isMobile())return;
  const panel=document.getElementById(id);
  if(!panel||!panel.classList.contains('on'))return;
  const opening=!panel.classList.contains('mob-open');
  MOB_PANELS.forEach(o=>document.getElementById(o).classList.remove('mob-open'));
  if(opening)panel.classList.add('mob-open');
  updateMobileTabs();
}
document.querySelectorAll('#mobile-tabs button').forEach(b=>{
  b.addEventListener('click',()=>mobToggle(b.dataset.tab));
});

/* watch panel .on changes — refresh tab availability. Only react to the .on
   false->true transition for the tour auto-open, so that other tab taps (which
   transiently strip every panel's .mob-open) don't trigger a feedback re-open. */
const _wasOn={};
MOB_PANELS.forEach(id=>{ const p=document.getElementById(id); _wasOn[id]=!!(p&&p.classList.contains('on')); });
MOB_PANELS.forEach(id=>{
  const panel=document.getElementById(id);
  if(!panel)return;
  new MutationObserver(()=>{
    const nowOn=panel.classList.contains('on');
    updateMobileTabs();
    if(id==='tour' && isMobile() && nowOn && !_wasOn[id]){
      setTimeout(()=>mobToggle('tour'),140);
    }
    _wasOn[id]=nowOn;
  }).observe(panel,{attributes:true,attributeFilter:['class']});
});
updateMobileTabs();
window.addEventListener('resize',()=>{
  if(!isMobile()) MOB_PANELS.forEach(o=>document.getElementById(o).classList.remove('mob-open'));
  updateMobileTabs();
  if(map && map.invalidateSize) map.invalidateSize();
});

/* belt-and-suspenders: also open the tour drawer directly from the splash button on mobile,
   so it does not depend on the observer firing in time. */
const _spTour=document.getElementById('sp-tour');
if(_spTour){
  _spTour.addEventListener('click',()=>{
    if(window.matchMedia('(max-width: 760px)').matches){
      setTimeout(()=>{
        const t=document.getElementById('tour');
        if(t && t.classList.contains('on') && !t.classList.contains('mob-open')){
          mobToggle('tour');
        }
      },220);
    }
  });
}
</script></body></html>"""

html = (HTML.replace('${TOURLEN}', str(len(candidates)))
            .replace('__CANDIDATES__', json.dumps(candidates, ensure_ascii=False))
            .replace('__GEVENTS__', json.dumps(global_events, ensure_ascii=False))
            .replace('__META__', json.dumps(meta, ensure_ascii=False))
            .replace('__LEGALS__', json.dumps(top_legals, ensure_ascii=False))
            .replace('__WSUM__', json.dumps(wallets_summary, ensure_ascii=False)))

with open(OUT_HTML, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"[HTML] {OUT_HTML} ({os.path.getsize(OUT_HTML)//1024} KB)")
con.close()
