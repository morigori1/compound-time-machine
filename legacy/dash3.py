"""Final dashboard v3: OSM + MS Buildings + DNS/Cert + OFAC SDN."""
import sqlite3, json, os, shutil, datetime
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
    # OSM obs (cap 1500 for HTML size; sample if more)
    c2.execute("""SELECT o.obs_lat, o.obs_lon, o.payload_json FROM observation o
                  JOIN obs_link l ON l.observation_id=o.id
                  WHERE l.target_canonical_id=? AND o.kind='osm'""", (can_id,))
    osm_obs_raw=[(r[0], r[1], json.loads(r[2])) for r in c2.fetchall()]
    osm_count = len(osm_obs_raw)
    if osm_count > 1500:
        step = osm_count // 1500
        osm_obs = osm_obs_raw[::step][:1500]
    else:
        osm_obs = osm_obs_raw
    # MS buildings
    c2.execute("""SELECT o.obs_lat, o.obs_lon, o.payload_json FROM observation o
                  JOIN obs_link l ON l.observation_id=o.id
                  WHERE l.target_canonical_id=? AND o.kind='ms_building'""", (can_id,))
    ms_obs_raw=[(r[0], r[1], {}) for r in c2.fetchall()]
    ms_count = len(ms_obs_raw)
    ms_obs = ms_obs_raw[:800] if ms_count > 800 else ms_obs_raw
    # Domain certs
    c2.execute("""SELECT o.payload_json FROM observation o
                  JOIN obs_link l ON l.observation_id=o.id
                  WHERE l.target_canonical_id=? AND o.kind='domain_cert'""", (can_id,))
    domains=[json.loads(r[0]) for r in c2.fetchall()]
    # DNS liveness
    c2.execute("""SELECT o.payload_json FROM observation o
                  JOIN obs_link l ON l.observation_id=o.id
                  WHERE l.target_canonical_id=? AND o.kind='dns_liveness'""", (can_id,))
    dns=[json.loads(r[0]) for r in c2.fetchall()]
    # Sanction entries (legal entities matched to candidate)
    c2.execute("""SELECT o.payload_json FROM observation o
                  JOIN obs_link l ON l.observation_id=o.id
                  WHERE l.target_canonical_id=? AND o.kind='sanction_entry'""", (can_id,))
    sanctions=[json.loads(r[0]) for r in c2.fetchall()]
    # Events
    c2.execute("SELECT kind, happened_on, summary FROM event WHERE candidate_id=? ORDER BY happened_on", (cid,))
    events_local=[{'kind':r[0],'date':r[1],'summary':r[2]} for r in c2.fetchall()]
    # Aliases
    c2.execute("SELECT surface, lang FROM alias WHERE canonical_id=?", (can_id,))
    aliases=c2.fetchall()
    candidates.append({'id':cid,'label':label,'lat':lat,'lon':lon,'kind':kind,'status':status,'notes':notes,
                      'country':country,'state':state,
                      'osm_count':osm_count, 'osm_sample':osm_obs,
                      'ms_count':ms_count, 'ms_sample':ms_obs,
                      'domains':domains,'dns':dns,'sanctions':sanctions,
                      'events':events_local,'aliases':aliases})

global_events=[{'kind':r[0],'date':r[1],'summary':r[2]}
               for r in cur.execute("SELECT kind, happened_on, summary FROM event WHERE candidate_id IS NULL ORDER BY happened_on")]

# Global wallet & legal entity summary
top_legals = [{'name':r[0],'jurisdiction':r[1],'programs':r[2]}
              for r in cur.execute("""SELECT name, jurisdiction, programs FROM legal_entity
                                      WHERE jurisdiction LIKE '%Cambodia%' OR jurisdiction LIKE '%Burma%'
                                      ORDER BY id DESC LIMIT 30""")]
wallets_summary = [{'chain':r[0],'count':r[1]} for r in cur.execute("SELECT chain, COUNT(*) FROM wallet GROUP BY chain ORDER BY 2 DESC")]
wallet_samples = [{'chain':r[0],'address':r[1],'label':r[2][:50] if r[2] else ''} 
                  for r in cur.execute("SELECT chain, address, label FROM wallet LIMIT 20")]

meta = {
  'generated_at': datetime.datetime.utcnow().isoformat()+'Z',
  'totals': {
    'candidates': cur.execute("SELECT COUNT(*) FROM compound_candidate").fetchone()[0],
    'observations_total': cur.execute("SELECT COUNT(*) FROM observation").fetchone()[0],
    'observations_osm': cur.execute("SELECT COUNT(*) FROM observation WHERE kind='osm'").fetchone()[0],
    'observations_ms_building': cur.execute("SELECT COUNT(*) FROM observation WHERE kind='ms_building'").fetchone()[0],
    'observations_domain_cert': cur.execute("SELECT COUNT(*) FROM observation WHERE kind='domain_cert'").fetchone()[0],
    'observations_dns_liveness': cur.execute("SELECT COUNT(*) FROM observation WHERE kind='dns_liveness'").fetchone()[0],
    'observations_sanction_entry': cur.execute("SELECT COUNT(*) FROM observation WHERE kind='sanction_entry'").fetchone()[0],
    'events': cur.execute("SELECT COUNT(*) FROM event").fetchone()[0],
    'legal_entities': cur.execute("SELECT COUNT(*) FROM legal_entity").fetchone()[0],
    'wallets': cur.execute("SELECT COUNT(*) FROM wallet").fetchone()[0],
    'sources': cur.execute("SELECT COUNT(*) FROM source").fetchone()[0],
    'aliases': cur.execute("SELECT COUNT(*) FROM alias").fetchone()[0],
  },
}

HTML = r"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<title>Compound Candidate POC v3 — Mekong</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
body{margin:0;font-family:system-ui,-apple-system,sans-serif;background:#0e1116;color:#e6e6e6}
#app{display:grid;grid-template-columns:420px 1fr;height:100vh}
#side{overflow-y:auto;padding:14px;border-right:1px solid #222}
#map{height:100vh}
h1{font-size:14px;margin:0 0 4px;color:#9cd}
h2{font-size:11px;color:#888;margin:18px 0 6px;text-transform:uppercase;letter-spacing:.08em;border-bottom:1px solid #222;padding-bottom:3px}
small{color:#777;font-size:11px;line-height:1.5}
.meta{font-size:11px;color:#bbb;line-height:1.7;background:#161a22;padding:8px;border-radius:5px;border:1px solid #222;margin-top:6px}
.meta b{color:#cef}
.meta .row{display:flex;justify-content:space-between;padding:1px 0}
.meta .row .k{color:#888}
.card{background:#161a22;border:1px solid #2a3140;border-radius:6px;padding:10px;margin-bottom:8px;cursor:pointer}
.card.active{border-color:#5af}
.card .label{font-weight:600;color:#fff;font-size:13px}
.card .meta-row{font-size:11px;color:#9aa;margin-top:3px}
.badge{display:inline-block;font-size:10px;padding:2px 6px;border-radius:3px;margin-right:4px;line-height:1.4}
.b-scam{background:#5a1a1a;color:#fbb}
.b-sez{background:#1a3a5a;color:#bcf}
.b-mixed{background:#3a3a1a;color:#fec}
.b-verified{background:#1a5a2a;color:#bfb}
.b-corroborated{background:#1a4a5a;color:#bdf}
.b-circumstantial{background:#5a4a1a;color:#fec}
.b-speculative{background:#3a2a3a;color:#fbe}
.stat{color:#7cf;font-size:10px;margin-left:4px}
.stat.live{color:#7fa}
.stat.dead{color:#c66}
.alias{font-size:11px;color:#aaa;margin-top:4px}
.alias span{margin-right:6px}
.layers{font-size:11px;color:#9aa;line-height:1.7}
.layers .impl{color:#9fc}
.layers .stub{color:#f96}
.tl{font-size:11px;border-left:2px solid #335;padding-left:8px;margin:6px 0}
.tl .d{color:#9cd}
.tl .k{color:#fc8;display:inline-block;margin:0 4px;font-family:ui-monospace,monospace;font-size:10px}
.tl .s{color:#aab}
.dom-row{font-size:11px;color:#bfb;margin:3px 0;font-family:ui-monospace,monospace}
.dom-row.dead{color:#977}
.dom-row .ip{color:#888;font-size:10px;margin-left:6px}
.legend{font-size:11px;background:rgba(20,20,30,.9);padding:8px;border-radius:6px;color:#bbb;border:1px solid #333}
.legend i{width:10px;height:10px;display:inline-block;margin-right:4px;border-radius:50%}
.leaflet-control-layers{background:#1a1f2a !important;color:#ddd !important}
.leaflet-control-layers-list label{color:#ddd}
.sanc{font-size:11px;color:#fcb;margin:2px 0}
.wallet-row{font-family:ui-monospace,monospace;font-size:10px;color:#cdf}
</style></head>
<body><div id="app"><div id="side">
<h1>Compound Candidate POC v3 — Mekong border zones</h1>
<small>Public OSINT only. 6 layers: OSM + MS Buildings + Events + Domains + DNS + OFAC SDN.</small>
<div class="meta" id="meta-box"></div>

<h2>Global Timeline</h2>
<div id="global-events"></div>

<h2>Candidates</h2>
<div id="list"></div>

<h2>OFAC SDN (Cambodia/Burma) — recent</h2>
<div id="legals"></div>

<h2>Wallets (SDN-listed)</h2>
<div id="wallets"></div>

<h2>Schema layers (POC v3)</h2>
<div class="layers">
<div class="impl">● canonical_entity / alias (multilingual)</div>
<div class="impl">● compound_candidate (7)</div>
<div class="impl">● observation: osm + ms_building + dns_liveness + domain_cert + sanction_entry</div>
<div class="impl">● obs_link (proximity/name_match/attributes)</div>
<div class="impl">● source (sha256 archive)</div>
<div class="impl">● event (12)</div>
<div class="impl">● legal_entity (OFAC SDN extract)</div>
<div class="impl">● wallet (SDN digital currency addresses)</div>
<div class="stub">○ capacity_estimate (空)</div>
<div class="stub">○ role_tenure (空)</div>
<div class="stub">○ rescue_record (構造化未)</div>
</div>
<h2>Caveats</h2>
<div class="layers stub">
Dara Sakor (UDG) は OSM + MS両方で空白 = 一貫した不在シグナル。<br>
Poipet 4012点はOverpass 3x3で取得、まだ更に高密度の可能性。<br>
domain_cert name_matchは候補にバイアスがかかる(false positive多)。<br>
"Prince Yormie JOHNSON" 等のfalse name match残存。
</div>
</div><div id="map"></div></div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const CANDIDATES=__CANDIDATES__;
const GLOBAL_EVENTS=__GEVENTS__;
const META=__META__;
const TOP_LEGALS=__LEGALS__;
const WALLETS=__WALLETS__;
const WALLETS_SUM=__WSUM__;

// meta render
const t = META.totals;
document.getElementById('meta-box').innerHTML = `
<div class="row"><span class="k">generated</span><b>${META.generated_at.slice(0,19)}</b></div>
<div class="row"><span class="k">candidates</span><b>${t.candidates}</b></div>
<div class="row"><span class="k">total obs</span><b>${t.observations_total}</b></div>
<div class="row"><span class="k">  osm</span><b>${t.observations_osm}</b></div>
<div class="row"><span class="k">  ms_building</span><b>${t.observations_ms_building}</b></div>
<div class="row"><span class="k">  dns_liveness</span><b>${t.observations_dns_liveness}</b></div>
<div class="row"><span class="k">  domain_cert</span><b>${t.observations_domain_cert}</b></div>
<div class="row"><span class="k">  sanction_entry</span><b>${t.observations_sanction_entry}</b></div>
<div class="row"><span class="k">events</span><b>${t.events}</b></div>
<div class="row"><span class="k">legal_entities</span><b>${t.legal_entities}</b></div>
<div class="row"><span class="k">wallets</span><b>${t.wallets}</b></div>
<div class="row"><span class="k">sources</span><b>${t.sources}</b></div>`;

// Base / overlay layers
const osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OSM',maxZoom:19});
const esriSat  = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',{attribution:'Esri',maxZoom:19});
const cartoDark= L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',{attribution:'CARTO',maxZoom:19,subdomains:'abcd'});
const esriLabels=L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',{maxZoom:19});

const map = L.map('map',{layers:[cartoDark]}).setView([12.5,104.0], 6);
const candLayer=L.layerGroup().addTo(map);
const osmLayerObs=L.layerGroup().addTo(map);
const msLayerObs =L.layerGroup().addTo(map);
const uncLayer=L.layerGroup().addTo(map);

const colors={scam:'#e44',sez:'#48c',mixed:'#fc4',casino:'#aaa',hotel:'#9c9',unknown:'#888'};

CANDIDATES.forEach(c=>{
  L.circle([c.lat,c.lon],{radius:1200,color:colors[c.kind]||'#888',weight:1,fillOpacity:0.04}).addTo(uncLayer);
  const m = L.circleMarker([c.lat,c.lon],{radius:10,color:colors[c.kind]||'#888',weight:2,fillColor:colors[c.kind]||'#888',fillOpacity:0.7}).addTo(candLayer);
  const aliasHtml = c.aliases.map(a=>`<span><b>${a[0]}</b> <small>(${a[1]||'?'})</small></span>`).join('');
  const evHtml = c.events.length ? c.events.map(e=>`<div class="tl"><span class="d">${e.date}</span><span class="k">${e.kind}</span><br><span class="s">${e.summary}</span></div>`).join('') : '<small>no candidate-local events</small>';
  const dnsHtml = c.dns.length ? c.dns.map(d=>{
    const live = d.A_records && d.A_records.length;
    return `<div class="dom-row ${live?'':'dead'}">${live?'●':'○'} ${d.domain}<span class="ip">${(d.A_records||[]).join(', ')}</span></div>`;
  }).join('') : '';
  const certHtml = c.domains.slice(0,12).map(d=>`<div class="dom-row">▣ ${d.common_name||''}</div>`).join('');
  const sancHtml = c.sanctions.slice(0,8).map(s=>`<div class="sanc">⚖ ${s.name||'?'} <small>(${(s.countries||[]).join(',')}) ${(s.programs||[]).join(',')}</small></div>`).join('');
  m.bindPopup(`<div style="font:12px system-ui;max-width:360px;max-height:500px;overflow-y:auto">
    <b style="font-size:13px">${c.label}</b><br>
    <span style="color:#888">${c.country}/${c.state}</span><br>
    kind: <b>${c.kind}</b> · status: <b>${c.status}</b><br>
    OSM=<b>${c.osm_count}</b> MS=<b>${c.ms_count}</b> DNS=<b>${c.dns.length}</b> CERT=<b>${c.domains.length}</b> SDN=<b>${c.sanctions.length}</b><br>
    <div style="margin-top:6px;font-size:11px">${aliasHtml}</div>
    <div style="margin-top:6px;font-size:11px;color:#666">${c.notes||''}</div>
    ${dnsHtml?'<div style="margin-top:8px"><b style="color:#888;font-size:10px">DNS LIVENESS</b>'+dnsHtml+'</div>':''}
    ${certHtml?'<div style="margin-top:6px"><b style="color:#888;font-size:10px">CERTS</b>'+certHtml+'</div>':''}
    ${sancHtml?'<div style="margin-top:6px"><b style="color:#888;font-size:10px">OFAC SDN</b>'+sancHtml+'</div>':''}
    <div style="margin-top:8px">${evHtml}</div>
  </div>`,{maxWidth:380,maxHeight:560});
  // OSM dots
  c.osm_sample.forEach(o=>{
    const tags=o[2].tags||{};
    let col='#5af';
    if(tags.amenity==='casino') col='#f8a';
    else if(tags.tourism==='hotel') col='#fc8';
    else if(tags.landuse==='industrial') col='#bd9';
    L.circleMarker([o[0],o[1]],{radius:2,color:col,weight:0,fillColor:col,fillOpacity:0.55}).addTo(osmLayerObs);
  });
  // MS building dots
  c.ms_sample.forEach(o=>{
    L.circleMarker([o[0],o[1]],{radius:2,color:'#9d6',weight:0,fillColor:'#9d6',fillOpacity:0.5}).addTo(msLayerObs);
  });
});

L.control.layers(
  {'Dark (Carto)':cartoDark, 'Satellite (Esri)':esriSat, 'OSM':osmLayer},
  {'Candidates':candLayer, 'OSM buildings':osmLayerObs, 'MS buildings':msLayerObs, 'Uncertainty (1.2km)':uncLayer, 'Place labels':esriLabels},
  {collapsed:false}
).addTo(map);

const legend = L.control({position:'bottomleft'});
legend.onAdd = function(){
  const div = L.DomUtil.create('div','legend');
  div.innerHTML = `<b>Candidate kind</b><br>
    <i style="background:#e44"></i>scam <i style="background:#48c"></i>sez <i style="background:#fc4"></i>mixed<br>
    <b>Buildings</b><br>
    <i style="background:#5af"></i>OSM building <i style="background:#fc8"></i>hotel <i style="background:#f8a"></i>casino <i style="background:#bd9"></i>industrial<br>
    <i style="background:#9d6"></i>MS ML building`;
  return div;
};
legend.addTo(map);

// Sidebar
const list=document.getElementById('list');
CANDIDATES.forEach(c=>{
  const div=document.createElement('div'); div.className='card';
  const liveDNS = c.dns.filter(d=>(d.A_records||[]).length>0).length;
  const deadDNS = c.dns.length - liveDNS;
  div.innerHTML = `<div class="label">${c.label}</div>
    <div class="meta-row">
      <span class="badge b-${c.kind}">${c.kind}</span>
      <span class="badge b-${c.status}">${c.status}</span>
      <span class="stat">OSM:${c.osm_count}</span>
      <span class="stat">MS:${c.ms_count}</span>
      ${c.dns.length?`<span class="stat live">●${liveDNS}</span>`:''}
      ${deadDNS?`<span class="stat dead">○${deadDNS}</span>`:''}
      ${c.sanctions.length?`<span class="stat" style="color:#fcb">⚖${c.sanctions.length}</span>`:''}
      ${c.events.length?`<span class="stat">EV:${c.events.length}</span>`:''}
    </div>
    <div class="meta-row">${c.country} · ${c.state}</div>
    <div class="alias">${c.aliases.map(a=>a[0]).join(' / ')}</div>`;
  div.onclick=()=>{ map.setView([c.lat,c.lon],14); };
  list.appendChild(div);
});

const ge=document.getElementById('global-events');
GLOBAL_EVENTS.forEach(e=>{
  const div=document.createElement('div'); div.className='tl';
  div.innerHTML = `<span class="d">${e.date}</span><span class="k">${e.kind}</span><br><span class="s">${e.summary}</span>`;
  ge.appendChild(div);
});

const lg=document.getElementById('legals');
TOP_LEGALS.forEach(le=>{
  const div=document.createElement('div'); div.className='sanc';
  div.innerHTML = `⚖ ${le.name} <small style="color:#888">(${le.jurisdiction||'-'}) ${le.programs||''}</small>`;
  lg.appendChild(div);
});

const wl=document.getElementById('wallets');
const ws=document.createElement('div'); ws.className='meta';
ws.innerHTML = WALLETS_SUM.map(w=>`<div class="row"><span class="k">${w.chain}</span><b>${w.count}</b></div>`).join('')
            + WALLETS.slice(0,8).map(w=>`<div class="wallet-row">${w.chain}: ${w.address}</div>`).join('');
wl.appendChild(ws);
</script></body></html>"""

html = (HTML.replace('__CANDIDATES__', json.dumps(candidates, ensure_ascii=False))
            .replace('__GEVENTS__',   json.dumps(global_events, ensure_ascii=False))
            .replace('__META__',      json.dumps(meta, ensure_ascii=False))
            .replace('__LEGALS__',    json.dumps(top_legals, ensure_ascii=False))
            .replace('__WALLETS__',   json.dumps(wallet_samples, ensure_ascii=False))
            .replace('__WSUM__',      json.dumps(wallets_summary, ensure_ascii=False)))

with open('/tmp/dashboard.html','w',encoding='utf-8') as f: f.write(html)
print(f"[HTML] /tmp/dashboard.html ({os.path.getsize('/tmp/dashboard.html')//1024} KB)")

# Publish to SS + outputs
import shutil
for src, dst in [
    ('/tmp/dashboard.html', os.path.join(OUT,'dashboard.html')),
    ('/tmp/compounds.db',   os.path.join(OUT,'compounds.db')),
    ('/tmp/dashboard.html', os.path.join(SS,'dashboard.html')),
    ('/tmp/compounds.db',   os.path.join(SS,'compounds.db')),
    ('/tmp/build_poc.py',   os.path.join(SS,'build_poc.py')),
    ('/tmp/phase2.py',      os.path.join(SS,'phase2.py')),
    ('/tmp/dash.py',        os.path.join(SS,'dash.py')),
    ('/tmp/phase3_overpass.py', os.path.join(SS,'phase3_overpass.py')),
    ('/tmp/phase3_msbuild.py',  os.path.join(SS,'phase3_msbuild.py')),
    ('/tmp/phase3_ct.py',       os.path.join(SS,'phase3_ct.py')),
    ('/tmp/phase3_ofac.py',     os.path.join(SS,'phase3_ofac.py')),
    ('/tmp/dash3.py',           os.path.join(SS,'dash3.py')),
]:
    try:
        shutil.copyfile(src, dst); print(f"[PUB] {dst}")
    except Exception as e:
        print(f"[PUB ERR] {dst}: {e}")
con.close()
