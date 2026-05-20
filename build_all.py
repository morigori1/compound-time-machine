"""Rebuild every derived data layer and the dashboard, from the base compounds.db.

Run order matters:
  - phase5 builds the building-density clusters that phase4 and phase10 center on.
  - phase6 builds the event source rows that phase8 enriches with preview images.

Each phase is idempotent (re-running replaces its own rows) and hits public APIs, so a
full run takes several minutes and needs an internet connection. compounds.db (the base
dataset: candidates, observations, sanctions, base events) must already exist — this
script only regenerates the derived layers on top of it.

Usage:
  python build_all.py          # run every phase, then rebuild dashboard.html
  python build_all.py dash     # only rebuild dashboard.html from current DB
"""
import subprocess, sys, os, time

HERE = os.path.dirname(os.path.abspath(__file__))
PHASES = [
    ('phase5_poi.py',          'POI + narration + era captions'),
    ('phase4_wayback.py',      'Wayback historical-satellite frames'),
    ('phase6_events.py',       'curated news events'),
    ('phase7_images.py',       'Wikimedia Commons location images'),
    ('phase8_event_images.py', 'per-event preview images (og:image)'),
    ('phase9_testimony.py',    'survivor / rescuer testimony'),
    ('phase10_local_life.py',  'local-life spots + daily-life snippets'),
    ('dash5.py',               'render dashboard.html'),
]

if not os.path.exists(os.path.join(HERE, 'compounds.db')):
    sys.exit('ERROR: compounds.db not found — the base dataset is required.')

steps = [PHASES[-1]] if (len(sys.argv) > 1 and sys.argv[1] == 'dash') else PHASES
start = time.time()
for i, (script, desc) in enumerate(steps, 1):
    print(f'\n=== [{i}/{len(steps)}] {script} — {desc} ===', flush=True)
    t = time.time()
    result = subprocess.run([sys.executable, os.path.join(HERE, script)], cwd=HERE)
    if result.returncode != 0:
        sys.exit(f'ERROR: {script} failed (exit code {result.returncode}).')
    print(f'--- {script} done in {time.time() - t:.0f}s ---', flush=True)

print(f'\nAll done in {time.time() - start:.0f}s. Open dashboard.html in a browser.')
