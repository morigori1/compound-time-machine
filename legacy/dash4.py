"""Dashboard v4: v3 layers + Wayback time-machine (historical satellite scrub).

Adds a per-candidate imagery timeline: click a candidate -> map flies in, base map
switches to Esri Wayback satellite, and a time slider (with play button) lets you
watch the compound being built out, frame by frame.
"""
import sqlite3, json, os, shutil, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, 'compounds.db')
OUT_HTML = os.path.join(HERE, 'dashboard.html')

con = sqlite3.connect(DB)
cur = con.cursor()


def leaflet_url(tmpl):
    """Esri Wayback itemURL uses {level}/{row}/{col}; Leaflet wants {z}/{y}/{x}."""
    return (tmpl.replace('{level}', '{z}')
                .replace('{row}', '{y}')
                .replace('{col}', '{x}'))


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
    if osm_count > 1500:
        step = osm_count // 1500
        osm_obs = osm_obs_raw[::step][:1500]
    else:
        osm_obs = osm_obs_raw
    c2.execute("""SELECT o.obs_lat, o.obs_lon FROM observation o
                  JOIN obs_link l ON l.observation_id=o.id
                  WHERE l.target_canonical_id=? AND o.kind='ms_building'""", (can_id,))
    ms_obs_raw = [(r[0], r[1]) for r in c2.fetchall()]
    ms_count = len(ms_obs_raw)
    ms_obs = ms_obs_raw[:800] if ms_count > 800 else ms_obs_raw
    c2.execute("""SELECT o.payload_json FROM observation o
                  JOIN obs_link l ON l.observation_id=o.id
                  WHERE l.target_canonical_id=? AND o.kind='domain_cert'""", (can_id,))
    domains = [json.loads(r[0]) for r in c2.fetchall()]
    c2.execute("""SELECT o.payload_json FROM observation o
                  JOIN obs_link l ON l.observation_id=o.id
                  WHERE l.target_canonical_id=? AND o.kind='dns_liveness'""", (can_id,))
    dns = [json.loads(r[0]) for r in c2.fetchall()]
    c2.execute("""SELECT o.payload_json FROM observation o
                  JOIN obs_link l ON l.observation_id=o.id
                  WHERE l.target_canonical_id=? AND o.kind='sanction_entry'""", (can_id,))
    sanctions = [json.loads(r[0]) for r in c2.fetchall()]
    c2.execute("SELECT kind, happened_on, summary FROM event WHERE candidate_id=? ORDER BY happened_on", (cid,))
    events_local = [{'kind': r[0], 'date': r[1], 'summary': r[2]} for r in c2.fetchall()]
    c2.execute("SELECT surface, lang FROM alias WHERE canonical_id=?", (can_id,))
    aliases = c2.fetchall()
    # Wayback time-machine frames (distinct imagery only, oldest -> newest)
    c2.execute("""SELECT release_date, release_num, tile_url FROM imagery_release
                  WHERE candidate_id=? AND is_distinct=1 ORDER BY release_date""", (cid,))
    imagery = [{'date': r[0], 'num': r[1], 'url': leaflet_url(r[2])} for r in c2.fetchall()]
    candidates.append({'id': cid, 'label': label, 'lat': lat, 'lon': lon, 'kind': kind,
                       'status': status, 'notes': notes, 'country': country, 'state': state,
                       'osm_count': osm_count, 'osm_sample': osm_obs,
                       'ms_count': ms_count, 'ms_sample': ms_obs,
                       'domains': domains, 'dns': dns, 'sanctions': sanctions,
                       'events': events_local, 'aliases': aliases, 'imagery': imagery})

global_events = [{'kind': r[0], 'date': r[1], 'summary': r[2]}
                 for r in cur.execute("SELECT kind, happened_on, summary FROM event WHERE candidate_id IS NULL ORDER BY happened_on")]
top_legals = [{'name': r[0], 'jurisdiction': r[1], 'programs': r[2]}
              for r in cur.execute("""SELECT name, jurisdiction, programs FROM legal_entity
                                      WHERE jurisdiction LIKE '%Cambodia%' OR jurisdiction LIKE '%Burma%'
                                      ORDER BY id DESC LIMIT 30""")]
wallets_summary = [{'chain': r[0], 'count': r[1]} for r in cur.execute("SELECT chain, COUNT(*) FROM wallet GROUP BY chain ORDER BY 2 DESC")]
wallet_samples = [{'chain': r[0], 'address': r[1], 'label': r[2][:50] if r[2] else ''}
                  for r in cur.execute("SELECT chain, address, label FROM wallet LIMIT 20")]

imagery_total = cur.execute("SELECT COUNT(*) FROM imagery_release WHERE is_distinct=1").fetchone()[0] \
    if cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='imagery_release'").fetchone() else 0

meta = {
  'generated_at': datetime.datetime.now(datetime.timezone.utc).isoformat()[:19] + 'Z',
  'totals': {
    'candidates': cur.execute("SELECT COUNT(*) FROM compound_candidate").fetchone()[0],
    'observations_total': cur.execute("SELECT COUNT(*) FROM observation").fetchone()[0],
    'observations_osm': cur.execute("SELECT COUNT(*) FROM observation WHERE kind='osm'").fetchone()[0],
    'observations_ms_building': cur.execute("SELECT COUNT(*) FROM observation WHERE kind='ms_building'").fetchone()[0],
    'observations_domain_cert': cur.execute("SELECT COUNT(*) FROM observation WHERE kind='domain_cert'").fetchone()[0],
    'observations_dns_liveness': cur.execute("SELECT COUNT(*) FROM observation WHERE kind='dns_liveness'").fetchone()[0],
    'observations_sanction_entry': cur.execute("SELECT COUNT(*) FROM observation WHERE kind='sanction_entry'").fetchone()[0],
    'imagery_frames': imagery_total,
    'events': cur.execute("SELECT COUNT(*) FROM event").fetchone()[0],
    'legal_entities': cur.execute("SELECT COUNT(*) FROM legal_entity").fetchone()[0],
    'wallets': cur.execute("SELECT COUNT(*) FROM wallet").fetchone()[0],
    'sources': cur.execute("SELECT COUNT(*) FROM source").fetchone()[0],
    'aliases': cur.execute("SELECT COUNT(*) FROM alias").fetchone()[0],
  },
}

HTML = r"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<title>Compound Time Machine v4 — Mekong</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
body{margin:0;font-family:system-ui,-apple-system,sans-serif;background:#0e1116;color:#e6e6e6}
#app{display:grid;grid-template-columns:420px 1fr;height:100vh}
#side{overflow-y:auto;padding:14px;border-right:1px solid #222}
#map{height:100vh;position:relative}
h1{font-size:14px;margin:0 0 4px;color:#9cd}
h2{font-size:11px;color:#888;margin:18px 0 6px;text-transform:uppercase;letter-spacing:.08em;border-bottom:1px solid #222;padding-bottom:3px}
small{color:#777;font-size:11px;line-height:1.5}
.meta{font-size:11px;color:#bbb;line-height:1.7;background:#161a22;padding:8px;border-radius:5px;border:1px solid #222;margin-top:6px}
.meta b{color:#cef}
.meta .row{display:flex;justify-content:space-between;padding:1px 0}
.meta .row .k{color:#888}
.card{background:#161a22;border:1px solid #2a3140;border-radius:6px;padding:10px;margin-bottom:8px;cursor:pointer}
.card.active{border-color:#5af;background:#1a2030}
.card .label{font-weight:600;color:#fff;font-size:13px}
.card .meta-row{font-size:11px;color:#9aa;margin-top:3px}
.badge{display:inline-block;font-size:10px;padding:2px 6px;border-radius:3px;margin-right:4px;line-height:1.4}
.b-scam{background:#5a1a1a;color:#fbb}
.b-sez{background:#1a3a5a;color:#bcf}
.b-mixed{background:#3a3a1a;color:#fec}
.b-corroborated{background:#1a4a5a;color:#bdf}
.b-circumstantial{background:#5a4a1a;color:#fec}
.b-speculative{background:#3a2a3a;color:#fbe}
.stat{color:#7cf;font-size:10px;margin-left:4px}
.stat.live{color:#7fa}
.stat.dead{color:#c66}
.stat.cam{color:#fc8}
.alias{font-size:11px;color:#aaa;margin-top:4px}
.layers{font-size:11px;color:#9aa;line-height:1.7}
.layers .impl{color:#9fc}
.layers .stub{color:#f96}
.tl{font-size:11px;border-left:2px solid #335;padding-left:8px;margin:6px 0}
.tl .d{color:#9cd}
.tl .k{color:#fc8;display:inline-block;margin:0 4px;font-family:ui-monospace,monospace;font-size:10px}
.tl .s{color:#aab}
.dom-row{font-size:11px;color:#bfb;margin:3px 0;font-family:ui-monospace,monospace}
.dom-row.dead{color:#977}
.legend{font-size:11px;background:rgba(20,20,30,.9);padding:8px;border-radius:6px;color:#bbb;border:1px solid #333}
.legend i{width:10px;height:10px;display:inline-block;margin-right:4px;border-radius:50%}
.leaflet-control-layers{background:#1a1f2a !important;color:#ddd !important}
.leaflet-control-layers-list label{color:#ddd}
.sanc{font-size:11px;color:#fcb;margin:2px 0}
.wallet-row{font-family:ui-monospace,monospace;font-size:10px;color:#cdf}

/* --- Time machine --- */
#tm{position:absolute;left:50%;bottom:22px;transform:translateX(-50%);
   width:min(720px,80%);background:rgba(14,17,22,.94);border:1px solid #2a3550;
   border-radius:10px;padding:12px 16px;box-shadow:0 6px 24px rgba(0,0,0,.6);
   z-index:1000;display:none}
#tm.on{display:block}
#tm .hd{display:flex;align-items:center;gap:10px;margin-bottom:8px}
#tm .ttl{font-size:13px;font-weight:600;color:#fff;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#tm .yr{font-family:ui-monospace,monospace;font-size:22px;color:#7cf;font-weight:700}
#tm .frame{font-size:10px;color:#888;margin-left:6px}
#tm .ctl{display:flex;align-items:center;gap:10px}
#tm button{background:#1f2942;color:#cde;border:1px solid #3a4a6a;
   border-radius:6px;width:34px;height:30px;font-size:14px;cursor:pointer}
#tm button:hover{background:#2a3a5a}
#tm input[type=range]{flex:1;accent-color:#5af;height:4px}
#tm .scale{display:flex;justify-content:space-between;font-size:9px;color:#667;margin-top:3px}
#tm .hint{font-size:10px;color:#778;margin-top:6px}
#tm .close{background:none;border:none;color:#889;font-size:16px;width:auto;height:auto}
.tm-badge{position:absolute;left:12px;top:12px;background:rgba(14,17,22,.9);
   border:1px solid #2a3550;border-radius:6px;padding:5px 9px;font-size:11px;color:#9cd;z-index:900}
</style></head>
<body><div id="app"><div id="side">
<h1>Compound Time Machine v4 — Mekong border zones</h1>
<small>Public OSINT only. 候補をクリック → 衛星タイムマシンが起動し、空き地→コンパウンドの建設過程を再生できます。</small>
<div class="meta" id="meta-box"></div>

<h2>Global Timeline</h2>
<div id="global-events"></div>

<h2>Candidates — クリックでタイムマシン起動</h2>
<div id="list"></div>

<h2>OFAC SDN (Cambodia/Burma) — recent</h2>
<div id="legals"></div>

<h2>Wallets (SDN-listed)</h2>
<div id="wallets"></div>

<h2>Schema layers (POC v4)</h2>
<div class="layers">
<div class="impl">● canonical_entity / alias (multilingual)</div>
<div class="impl">● compound_candidate (7)</div>
<div class="impl">● observation: osm + ms_building + dns + domain_cert + sanction_entry</div>
<div class="impl">● imagery_release — Wayback時系列タイル (NEW)</div>
<div class="impl">● event (12) / legal_entity / wallet</div>
<div class="stub">○ capacity_estimate (空)</div>
<div class="stub">○ poi — コンパウンド内スポット注釈 (未)</div>
<div class="stub">○ testimony — 救出者証言 (未)</div>
</div>
<h2>Caveats</h2>
<div class="layers stub">
衛星フレームは z15 タイルのハッシュ差分で抽出。雲・季節差も差分に含まれ得る。<br>
Dara Sakor は変化フレームが少ない(撮影頻度低)。<br>
座標は報道エリア中心 ±800m、コンパウンド境界とは一致しない。
</div>
</div><div id="map">
  <div class="tm-badge" id="tm-badge">候補をクリックして時間遡行を開始</div>
  <div id="tm">
    <div class="hd">
      <span class="ttl" id="tm-ttl">—</span>
      <span class="yr" id="tm-yr">—</span>
      <span class="frame" id="tm-frame"></span>
      <button class="close" id="tm-close" title="閉じる">✕</button>
    </div>
    <div class="ctl">
      <button id="tm-play" title="再生/停止">▶</button>
      <input type="range" id="tm-range" min="0" max="0" value="0" step="1">
    </div>
    <div class="scale"><span id="tm-first"></span><span id="tm-last"></span></div>
    <div class="hint">スライダーをドラッグ、または ▶ で建設過程を早回し再生。背景はEsri Wayback衛星。</div>
  </div>
</div></div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const CANDIDATES=__CANDIDATES__;
const GLOBAL_EVENTS=__GEVENTS__;
const META=__META__;
const TOP_LEGALS=__LEGALS__;
const WALLETS=__WALLETS__;
const WALLETS_SUM=__WSUM__;

const t=META.totals;
document.getElementById('meta-box').innerHTML=`
<div class="row"><span class="k">generated</span><b>${META.generated_at}</b></div>
<div class="row"><span class="k">candidates</span><b>${t.candidates}</b></div>
<div class="row"><span class="k">total obs</span><b>${t.observations_total}</b></div>
<div class="row"><span class="k">&nbsp;&nbsp;osm</span><b>${t.observations_osm}</b></div>
<div class="row"><span class="k">&nbsp;&nbsp;ms_building</span><b>${t.observations_ms_building}</b></div>
<div class="row"><span class="k">imagery frames</span><b>${t.imagery_frames}</b></div>
<div class="row"><span class="k">events</span><b>${t.events}</b></div>
<div class="row"><span class="k">legal_entities</span><b>${t.legal_entities}</b></div>
<div class="row"><span class="k">wallets</span><b>${t.wallets}</b></div>`;

const osmLayer=L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OSM',maxZoom:19});
const esriSat =L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',{attribution:'Esri',maxZoom:19});
const cartoDark=L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',{attribution:'CARTO',maxZoom:19,subdomains:'abcd'});

const map=L.map('map',{layers:[cartoDark]}).setView([12.5,104.0],6);
const candLayer=L.layerGroup().addTo(map);
const osmLayerObs=L.layerGroup().addTo(map);
const msLayerObs =L.layerGroup().addTo(map);
const uncLayer=L.layerGroup().addTo(map);

// Wayback time-machine layer — URL swapped as the slider moves
const waybackLayer=L.tileLayer('',{attribution:'Esri Wayback',maxZoom:19,maxNativeZoom:18});

const colors={scam:'#e44',sez:'#48c',mixed:'#fc4',casino:'#aaa',hotel:'#9c9',unknown:'#888'};

CANDIDATES.forEach(c=>{
  L.circle([c.lat,c.lon],{radius:1200,color:colors[c.kind]||'#888',weight:1,fillOpacity:0.04}).addTo(uncLayer);
  const m=L.circleMarker([c.lat,c.lon],{radius:10,color:colors[c.kind]||'#888',weight:2,fillColor:colors[c.kind]||'#888',fillOpacity:0.7}).addTo(candLayer);
  c._marker=m;
  const aliasHtml=c.aliases.map(a=>`<span><b>${a[0]}</b> <small>(${a[1]||'?'})</small></span>`).join(' ');
  const evHtml=c.events.length?c.events.map(e=>`<div class="tl"><span class="d">${e.date}</span><span class="k">${e.kind}</span><br><span class="s">${e.summary}</span></div>`).join(''):'<small>no candidate-local events</small>';
  m.bindPopup(`<div style="font:12px system-ui;max-width:340px">
    <b style="font-size:13px">${c.label}</b><br>
    <span style="color:#888">${c.country}/${c.state}</span> · kind <b>${c.kind}</b><br>
    OSM=<b>${c.osm_count}</b> MS=<b>${c.ms_count}</b> 衛星フレーム=<b>${c.imagery.length}</b><br>
    <div style="margin-top:6px;font-size:11px">${aliasHtml}</div>
    <div style="margin-top:6px;font-size:11px;color:#666">${c.notes||''}</div>
    <div style="margin-top:8px">${evHtml}</div></div>`,{maxWidth:360});
  m.on('click',()=>startTimeMachine(c));
  c.osm_sample.forEach(o=>{
    const tags=o[2].tags||{};let col='#5af';
    if(tags.amenity==='casino')col='#f8a';
    else if(tags.tourism==='hotel')col='#fc8';
    else if(tags.landuse==='industrial')col='#bd9';
    L.circleMarker([o[0],o[1]],{radius:2,color:col,weight:0,fillColor:col,fillOpacity:0.55}).addTo(osmLayerObs);
  });
  c.ms_sample.forEach(o=>{
    L.circleMarker([o[0],o[1]],{radius:2,color:'#9d6',weight:0,fillColor:'#9d6',fillOpacity:0.5}).addTo(msLayerObs);
  });
});

L.control.layers(
  {'Dark (Carto)':cartoDark,'Satellite (Esri current)':esriSat,'OSM':osmLayer},
  {'Candidates':candLayer,'OSM buildings':osmLayerObs,'MS buildings':msLayerObs,'Uncertainty (1.2km)':uncLayer},
  {collapsed:true}
).addTo(map);

const legend=L.control({position:'bottomright'});
legend.onAdd=function(){
  const div=L.DomUtil.create('div','legend');
  div.innerHTML=`<b>Candidate kind</b><br>
    <i style="background:#e44"></i>scam <i style="background:#48c"></i>sez <i style="background:#fc4"></i>mixed<br>
    <b>Buildings</b><br>
    <i style="background:#5af"></i>OSM <i style="background:#fc8"></i>hotel <i style="background:#f8a"></i>casino <i style="background:#9d6"></i>MS ML`;
  return div;
};
legend.addTo(map);

/* ---------- Time machine ---------- */
const tm=document.getElementById('tm');
const tmBadge=document.getElementById('tm-badge');
const range=document.getElementById('tm-range');
const playBtn=document.getElementById('tm-play');
let tmCand=null, tmFrames=[], playTimer=null;

function setFrame(i){
  if(!tmCand||!tmFrames.length)return;
  i=Math.max(0,Math.min(tmFrames.length-1,i));
  range.value=i;
  const f=tmFrames[i];
  waybackLayer.setUrl(f.url);
  document.getElementById('tm-yr').textContent=f.date.slice(0,4);
  document.getElementById('tm-frame').textContent=`${f.date}  ·  ${i+1}/${tmFrames.length}`;
}
function stopPlay(){ if(playTimer){clearInterval(playTimer);playTimer=null;playBtn.textContent='▶';} }
function startPlay(){
  if(!tmFrames.length)return;
  if(+range.value>=tmFrames.length-1)setFrame(0);
  playBtn.textContent='⏸';
  playTimer=setInterval(()=>{
    let n=+range.value+1;
    if(n>=tmFrames.length){stopPlay();return;}
    setFrame(n);
  },1100);
}
function startTimeMachine(c){
  tmCand=c; tmFrames=c.imagery||[]; stopPlay();
  document.querySelectorAll('.card').forEach(el=>el.classList.toggle('active',+el.dataset.id===c.id));
  if(!tmFrames.length){
    tmBadge.style.display='block';
    tmBadge.textContent=`${c.label}: 履歴衛星フレームなし`;
    tm.classList.remove('on');
    map.flyTo([c.lat,c.lon],15);
    return;
  }
  tmBadge.style.display='none';
  document.getElementById('tm-ttl').textContent=c.label;
  document.getElementById('tm-first').textContent=tmFrames[0].date;
  document.getElementById('tm-last').textContent=tmFrames[tmFrames.length-1].date;
  range.max=tmFrames.length-1;
  if(!map.hasLayer(waybackLayer))waybackLayer.addTo(map);
  waybackLayer.bringToFront();
  tm.classList.add('on');
  setFrame(tmFrames.length-1);          // start at latest
  map.flyTo([c.lat,c.lon],16,{duration:1.2});
}
range.addEventListener('input',()=>{stopPlay();setFrame(+range.value);});
playBtn.addEventListener('click',()=>{ playTimer?stopPlay():startPlay(); });
document.getElementById('tm-close').addEventListener('click',()=>{
  stopPlay(); tm.classList.remove('on');
  if(map.hasLayer(waybackLayer))map.removeLayer(waybackLayer);
  tmBadge.style.display='block';
  tmBadge.textContent='候補をクリックして時間遡行を開始';
  document.querySelectorAll('.card').forEach(el=>el.classList.remove('active'));
});

/* ---------- Sidebar ---------- */
const list=document.getElementById('list');
CANDIDATES.forEach(c=>{
  const div=document.createElement('div');div.className='card';div.dataset.id=c.id;
  const liveDNS=c.dns.filter(d=>(d.A_records||[]).length>0).length;
  div.innerHTML=`<div class="label">${c.label}</div>
    <div class="meta-row">
      <span class="badge b-${c.kind}">${c.kind}</span>
      <span class="badge b-${c.status}">${c.status}</span>
      <span class="stat">OSM:${c.osm_count}</span>
      <span class="stat">MS:${c.ms_count}</span>
      ${c.imagery.length?`<span class="stat cam">◷${c.imagery.length}frames</span>`:'<span class="stat dead">no imagery</span>'}
      ${c.sanctions.length?`<span class="stat" style="color:#fcb">⚖${c.sanctions.length}</span>`:''}
    </div>
    <div class="meta-row">${c.country} · ${c.state}${c.imagery.length?` · 衛星 ${c.imagery[0].date.slice(0,4)}–${c.imagery[c.imagery.length-1].date.slice(0,4)}`:''}</div>
    <div class="alias">${c.aliases.map(a=>a[0]).join(' / ')}</div>`;
  div.onclick=()=>startTimeMachine(c);
  list.appendChild(div);
});

const ge=document.getElementById('global-events');
GLOBAL_EVENTS.forEach(e=>{
  const div=document.createElement('div');div.className='tl';
  div.innerHTML=`<span class="d">${e.date}</span><span class="k">${e.kind}</span><br><span class="s">${e.summary}</span>`;
  ge.appendChild(div);
});
const lg=document.getElementById('legals');
TOP_LEGALS.forEach(le=>{
  const div=document.createElement('div');div.className='sanc';
  div.innerHTML=`⚖ ${le.name} <small style="color:#888">(${le.jurisdiction||'-'}) ${le.programs||''}</small>`;
  lg.appendChild(div);
});
const wl=document.getElementById('wallets');
const ws=document.createElement('div');ws.className='meta';
ws.innerHTML=WALLETS_SUM.map(w=>`<div class="row"><span class="k">${w.chain}</span><b>${w.count}</b></div>`).join('')
          +WALLETS.slice(0,8).map(w=>`<div class="wallet-row">${w.chain}: ${w.address}</div>`).join('');
wl.appendChild(ws);
</script></body></html>"""

html = (HTML.replace('__CANDIDATES__', json.dumps(candidates, ensure_ascii=False))
            .replace('__GEVENTS__', json.dumps(global_events, ensure_ascii=False))
            .replace('__META__', json.dumps(meta, ensure_ascii=False))
            .replace('__LEGALS__', json.dumps(top_legals, ensure_ascii=False))
            .replace('__WALLETS__', json.dumps(wallet_samples, ensure_ascii=False))
            .replace('__WSUM__', json.dumps(wallets_summary, ensure_ascii=False)))

with open(OUT_HTML, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"[HTML] {OUT_HTML} ({os.path.getsize(OUT_HTML)//1024} KB)")
con.close()
