"""Render multi-layer dashboard (OSM/satellite/dark + events + domain stub)."""
import sqlite3, json, os, shutil, sys, datetime
DB='/tmp/compounds.db'
OUT='/sessions/quirky-trusting-archimedes/mnt/outputs'
SS ='/sessions/quirky-trusting-archimedes/mnt/SS'
con=sqlite3.connect(DB); cur=con.cursor()

candidates=[]
for row in cur.execute("""SELECT c.id, c.canonical_id, c.label, c.rep_lat, c.rep_lon,
                                 c.kind_hypothesis, c.status, c.notes,
                                 p.admin_country, p.admin_state
                          FROM compound_candidate c JOIN place p ON c.place_id=p.id ORDER BY c.id"""):
    cid, can_id, label, lat, lon, kind, status, notes, country, state = row
    c2=con.cursor()
    c2.execute("""SELECT o.obs_lat, o.obs_lon, o.payload_json FROM observation o
                  JOIN obs_link l ON l.observation_id=o.id
                  WHERE l.target_canonical_id=? AND o.kind='osm'""", (can_id,))
    osm_obs=[(r[0], r[1], json.loads(r[2])) for r in c2.fetchall()]
    c2.execute("""SELECT o.payload_json FROM observation o
                  JOIN obs_link l ON l.observation_id=o.id
                  WHERE l.target_canonical_id=? AND o.kind='domain_cert'""", (can_id,))
    domains=[json.loads(r[0]) for r in c2.fetchall()]
    c2.execute("SELECT kind, happened_on, summary FROM event WHERE candidate_id=? ORDER BY happened_on", (cid,))
    events_local=[{'kind':r[0],'date':r[1],'summary':r[2]} for r in c2.fetchall()]
    c2.execute("SELECT surface, lang FROM alias WHERE canonical_id=?", (can_id,))
    aliases=c2.fetchall()
    candidates.append({'id':cid,'label':label,'lat':lat,'lon':lon,'kind':kind,'status':status,'notes':notes,
                      'country':country,'state':state,'obs_count':len(osm_obs),'observations':osm_obs,
                      'domains':domains,'events':events_local,'aliases':aliases})

global_events=[{'kind':r[0],'date':r[1],'summary':r[2]}
               for r in cur.execute("SELECT kind, happened_on, summary FROM event WHERE candidate_id IS NULL ORDER BY happened_on")]
meta = {
  'generated_at': datetime.datetime.utcnow().isoformat()+'Z',
  'totals': {
    'candidates': cur.execute("SELECT COUNT(*) FROM compound_candidate").fetchone()[0],
    'observations_osm': cur.execute("SELECT COUNT(*) FROM observation WHERE kind='osm'").fetchone()[0],
    'observations_domain': cur.execute("SELECT COUNT(*) FROM observation WHERE kind='domain_cert'").fetchone()[0],
    'events': cur.execute("SELECT COUNT(*) FROM event").fetchone()[0],
    'sources': cur.execute("SELECT COUNT(*) FROM source").fetchone()[0],
    'aliases': cur.execute("SELECT COUNT(*) FROM alias").fetchone()[0],
  },
  'unavailable_layers': [r[0] for r in cur.execute("SELECT kind FROM source WHERE kind LIKE '%_unavailable'").fetchall()],
}

HTML = r"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<title>Compound Candidate POC v2 — Mekong</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
body{margin:0;font-family:system-ui,-apple-system,sans-serif;background:#0e1116;color:#e6e6e6}
#app{display:grid;grid-template-columns:400px 1fr;height:100vh}
#side{overflow-y:auto;padding:14px;border-right:1px solid #222}
#map{height:100vh}
h1{font-size:14px;margin:0 0 4px;color:#9cd}
h2{font-size:11px;color:#888;margin:18px 0 6px;text-transform:uppercase;letter-spacing:.08em}
small{color:#777;font-size:11px;line-height:1.5}
.meta{font-size:11px;color:#999;line-height:1.6;background:#161a22;padding:8px;border-radius:5px;border:1px solid #222;margin-top:6px}
.meta b{color:#cef}
.card{background:#161a22;border:1px solid #2a3140;border-radius:6px;padding:10px;margin-bottom:8px;cursor:pointer}
.card:hover{border-color:#4a82c4}
.card .label{font-weight:600;color:#fff;font-size:13px}
.card .meta-row{font-size:11px;color:#9aa;margin-top:3px}
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
.layers .stub{color:#f96}
.tl{font-size:11px;border-left:2px solid #335;padding-left:8px;margin:6px 0}
.tl .d{color:#9cd}
.tl .k{color:#fc8;display:inline-block;margin:0 4px}
.tl .s{color:#aab}
.legend{font-size:11px;background:rgba(20,20,30,.85);padding:8px;border-radius:6px;color:#bbb;border:1px solid #333}
.legend i{width:10px;height:10px;display:inline-block;margin-right:4px;border-radius:50%}
.leaflet-control-layers{background:#1a1f2a !important;color:#ddd !important}
.leaflet-control-layers-list label{color:#ddd}
</style></head>
<body><div id="app"><div id="side">
<h1>Compound Candidate POC v2 — Mekong border zones</h1>
<small>Public OSINT only. 座標は近似(報道エリア中心)。観測=OSM proximity + 報道events。</small>
<div class="meta" id="meta-box"></div>

<h2>Global Events (timeline)</h2>
<div id="global-events"></div>

<h2>Candidates</h2>
<div id="list"></div>

<h2>Schema layers (POC v2状態)</h2>
<div class="layers">
<div class="impl">● canonical_entity / alias (4言語)</div>
<div class="impl">● compound_candidate (7件, notes付き)</div>
<div class="impl">● observation / obs_link (osm=多, domain_cert=0)</div>
<div class="impl">● source (archive_sha256付き)</div>
<div class="impl">● event (12件, グローバル+候補別)</div>
<div class="stub">○ capacity_estimate (空)</div>
<div class="stub">○ legal_entity / role_tenure</div>
<div class="stub">○ wallet (オンチェーン未取り込み)</div>
<div class="stub">○ rescue_record / sanction_action (構造化未)</div>
<div class="stub">! ct_logs (crt.sh) 取得不能 — meta_unavailable記録済</div>
</div>
<h2>Caveats</h2>
<div class="layers stub">
座標は±800m近似。obs_linkは 'co_located' 仮説、用途確定ではない。<br>
OSM空白 (Dara/O'Smach/Bavet) は弱いシグナル: 編集回避/管理外。<br>
Poipet/Jin Bei は out=500 上限ヒット、真値はもっと多い。<br>
events日付は公開報道準拠。AP 80% 閉鎖は政治数字。
</div>
</div><div id="map"></div></div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const CANDIDATES = __CANDIDATES__;
const GLOBAL_EVENTS = __GEVENTS__;
const META = __META__;

// meta
document.getElementById('meta-box').innerHTML = `
  generated: <b>${META.generated_at.slice(0,19)}</b><br>
  candidates=<b>${META.totals.candidates}</b>
  osm=<b>${META.totals.observations_osm}</b>
  domain=<b>${META.totals.observations_domain}</b>
  events=<b>${META.totals.events}</b><br>
  sources=<b>${META.totals.sources}</b>
  aliases=<b>${META.totals.aliases}</b><br>
  ${META.unavailable_layers.length ? '<span style="color:#f96">unavailable: '+META.unavailable_layers.join(', ')+'</span>' : ''}`;

// Base layers
const osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
  {attribution:'© OpenStreetMap',maxZoom:19});
const esriSat = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
  {attribution:'Tiles © Esri',maxZoom:19});
const cartoDark = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
  {attribution:'© CARTO',maxZoom:19,subdomains:'abcd'});
const esriLabels = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
  {attribution:'',maxZoom:19});

const map = L.map('map',{layers:[cartoDark]}).setView([12.5,104.0], 6);

// Overlay groups
const candLayer = L.layerGroup().addTo(map);
const obsLayer  = L.layerGroup().addTo(map);
const uncLayer  = L.layerGroup().addTo(map);

const colors = {scam:'#e44',sez:'#48c',mixed:'#fc4',casino:'#aaa',hotel:'#9c9',unknown:'#888'};

CANDIDATES.forEach(c=>{
  L.circle([c.lat,c.lon],{radius:800, color:colors[c.kind]||'#888', weight:1, fillOpacity:0.05}).addTo(uncLayer);
  const m = L.circleMarker([c.lat,c.lon],{
    radius:9, color:colors[c.kind]||'#888', weight:2,
    fillColor:colors[c.kind]||'#888', fillOpacity:0.7}).addTo(candLayer);
  const aliasHtml = c.aliases.map(a=>`<span><b>${a[0]}</b> <small>(${a[1]||'?'})</small></span>`).join('');
  const evHtml = c.events.length ? c.events.map(e=>`<div class="tl"><span class="d">${e.date}</span><span class="k">${e.kind}</span><br><span class="s">${e.summary}</span></div>`).join('') : '<small>no candidate-local events</small>';
  m.bindPopup(`<div style="font:13px system-ui;max-width:340px">
    <b>${c.label}</b><br>
    <span style="color:#888">${c.country}/${c.state}</span><br>
    kind: <b>${c.kind}</b> · status: <b>${c.status}</b><br>
    OSM obs: <b>${c.obs_count}</b><br>
    <div style="margin-top:6px;font-size:11px">${aliasHtml}</div>
    <div style="margin-top:6px;font-size:11px;color:#555">${c.notes||''}</div>
    <div style="margin-top:8px">${evHtml}</div></div>`);
  c.observations.forEach(o=>{
    const tags = o[2].tags||{};
    let lab='';
    if(tags.building) lab='building';
    if(tags.tourism==='hotel') lab='hotel';
    if(tags.amenity==='casino') lab='casino';
    if(tags.landuse==='industrial') lab='industrial';
    if(tags.landuse==='commercial') lab='commercial';
    if(tags.leisure==='resort') lab='resort';
    let col = '#5af';
    if(tags.amenity==='casino') col='#f8a';
    else if(tags.tourism==='hotel') col='#fc8';
    else if(tags.landuse==='industrial') col='#bd9';
    L.circleMarker([o[0],o[1]],{radius:2.5,color:col,weight:0,fillColor:col,fillOpacity:0.6})
      .addTo(obsLayer).bindTooltip(`${lab}<br>${JSON.stringify(tags)}`,{direction:'top'});
  });
});

L.control.layers(
  {'OSM':osmLayer, 'Satellite (Esri)':esriSat, 'Dark (Carto)':cartoDark},
  {'Candidates':candLayer, 'OSM observations':obsLayer, 'Uncertainty radius':uncLayer, 'Place labels':esriLabels},
  {collapsed:false}
).addTo(map);

// Legend
const legend = L.control({position:'bottomleft'});
legend.onAdd = function(){
  const div = L.DomUtil.create('div','legend');
  div.innerHTML = `<b>Candidate kind</b><br>
    <i style="background:#e44"></i>scam <i style="background:#48c"></i>sez <i style="background:#fc4"></i>mixed<br>
    <b>OSM obs</b><br>
    <i style="background:#5af"></i>building <i style="background:#fc8"></i>hotel <i style="background:#f8a"></i>casino <i style="background:#bd9"></i>industrial`;
  return div;
};
legend.addTo(map);

// Sidebar: candidate cards
const list = document.getElementById('list');
CANDIDATES.forEach(c=>{
  const div=document.createElement('div'); div.className='card';
  div.innerHTML = `<div class="label">${c.label}</div>
    <div class="meta-row">
      <span class="badge b-${c.kind}">${c.kind}</span>
      <span class="badge b-${c.status}">${c.status}</span>
      <span class="stat">OSM:${c.obs_count}</span>
      ${c.events.length?`<span class="stat">EV:${c.events.length}</span>`:''}</div>
    <div class="meta-row">${c.country} · ${c.state}</div>
    <div class="alias">${c.aliases.map(a=>a[0]).join(' / ')}</div>`;
  div.onclick=()=>{ map.setView([c.lat,c.lon],15); };
  list.appendChild(div);
});

// Sidebar: global events
const ge = document.getElementById('global-events');
GLOBAL_EVENTS.forEach(e=>{
  const div=document.createElement('div'); div.className='tl';
  div.innerHTML = `<span class="d">${e.date}</span><span class="k">${e.kind}</span><br><span class="s">${e.summary}</span>`;
  ge.appendChild(div);
});
</script></body></html>"""

html = HTML.replace('__CANDIDATES__', json.dumps(candidates, ensure_ascii=False)) \
           .replace('__GEVENTS__',   json.dumps(global_events, ensure_ascii=False)) \
           .replace('__META__',      json.dumps(meta, ensure_ascii=False))

with open('/tmp/dashboard.html','w',encoding='utf-8') as f:
    f.write(html)
print(f"[HTML] /tmp/dashboard.html ({os.path.getsize('/tmp/dashboard.html')//1024} KB)")

# publish
for src, dst in [
    ('/tmp/dashboard.html', os.path.join(OUT,'dashboard.html')),
    ('/tmp/compounds.db',   os.path.join(OUT,'compounds.db')),
    ('/tmp/dashboard.html', os.path.join(SS,'dashboard.html')),
    ('/tmp/compounds.db',   os.path.join(SS,'compounds.db')),
    ('/tmp/build_poc.py',   os.path.join(SS,'build_poc.py')),
    ('/tmp/phase2.py',      os.path.join(SS,'phase2.py')),
    ('/tmp/dash.py',        os.path.join(SS,'dash.py')),
]:
    try:
        shutil.copyfile(src, dst)
        print(f"[PUB] {dst}")
    except Exception as e:
        print(f"[PUB ERR] {dst}: {e}")
con.close()
