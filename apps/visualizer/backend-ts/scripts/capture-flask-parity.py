"""Capture Flask responses on the real catalog as a parity baseline.

Regenerates ``tests/fixtures/flask-catalog-parity.json``, which
``tests/catalog-parity.test.ts`` replays against the TypeScript backend and
requires to match field for field. This is the only thing that proves the ported
SQL returns the same rows in the same order on 43k real images rather than on a
seven-row fixture.

Every request is a GET, so this cannot modify the catalog. Even so, point
LIBRARY_DB at a *copy*: the Flask app opens the database read-write and would
apply pending schema migrations to it.

Usage, from the repo root::

    cp library.db /tmp/library-parity.db
    cd apps/visualizer/backend
    LIBRARY_DB=/tmp/library-parity.db ../../../.venv/bin/python \
        ../backend-ts/scripts/capture-flask-parity.py

Delete this script and its fixture at cutover, when the Flask backend goes away.
"""
import json, os, sys

# The Flask backend is not a package; it expects its own directory on sys.path.
BACKEND_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'backend')
)
sys.path.insert(0, BACKEND_DIR)
os.environ.setdefault('FLASK_DEBUG', 'true')

if not os.environ.get('LIBRARY_DB'):
    raise SystemExit('LIBRARY_DB must point at a copy of the real library.db')

from app import create_app

app = create_app()
client = app.test_client()

# Pick real keys and ids out of the database so the requests exercise real rows
# rather than hard-coded ones that rot when the catalog is re-synced.
from lightroom_tagger.core.database import init_database
conn = init_database(os.environ['LIBRARY_DB'])
key_scored = conn.execute(
    "SELECT image_key FROM image_scores WHERE is_current=1 GROUP BY image_key "
    "HAVING COUNT(*) >= 2 ORDER BY image_key LIMIT 1"
).fetchone()['image_key']
key_stacked = conn.execute(
    "SELECT m.image_key FROM image_stack_members m ORDER BY m.image_key LIMIT 1"
).fetchone()['image_key']
stack_id = conn.execute("SELECT stack_id FROM image_stacks ORDER BY stack_id LIMIT 1").fetchone()['stack_id']
key_clip = conn.execute(
    "SELECT image_key FROM image_clip_embeddings ORDER BY image_key LIMIT 1"
).fetchone()['image_key']
perspective = conn.execute("SELECT slug FROM perspectives WHERE active=1 ORDER BY slug LIMIT 1").fetchone()['slug']
month = conn.execute(
    "SELECT strftime('%Y%m', date_taken) m FROM images WHERE date_taken IS NOT NULL "
    "GROUP BY m ORDER BY m DESC LIMIT 1"
).fetchone()['m']
conn.close()

REQUESTS = [
    '/api/images/catalog?limit=3',
    '/api/images/catalog/?limit=3',
    '/api/images/catalog?limit=3&offset=7',
    '/api/images/catalog?limit=3&sort_by_date=oldest',
    f'/api/images/catalog?limit=3&score_perspective={perspective}&sort_by_score=desc',
    f'/api/images/catalog?limit=3&score_perspective={perspective}&sort_by_score=asc',
    f'/api/images/catalog?limit=3&score_perspective={perspective}&min_score=8',
    '/api/images/catalog?limit=3&min_rating=1',
    '/api/images/catalog?limit=3&burst_stack=true',
    '/api/images/catalog?limit=3&burst_stack=false',
    '/api/images/catalog?limit=3&flagged=true',
    '/api/images/catalog?limit=3&flagged=false',
    '/api/images/catalog?limit=3&analyzed=true',
    '/api/images/catalog?limit=3&analyzed=false',
    '/api/images/catalog?limit=3&posted=true',
    f'/api/images/catalog?limit=3&month={month}',
    '/api/images/catalog?limit=3&keyword=street',
    '/api/images/catalog?limit=3&description_search=night%20street',
    '/api/images/catalog?limit=3&min_score_on_active=9',
    '/api/images/catalog/months',
    f'/api/images/catalog/{key_scored}',
    f'/api/images/catalog/{key_stacked}',
    f'/api/images/catalog/{key_clip}/similar?limit=3',
    f'/api/images/catalog/{key_clip}/similar?limit=3&min_rating=1',
    '/api/images/catalog-similarity-groups?limit=2',
    '/api/images/catalog-similarity-groups?limit=2&offset=3',
    '/api/images/stacks/suggestions?limit=2',
    '/api/images/stacks/suggestions?limit=2&offset=5',
    f'/api/images/stacks/{stack_id}/members',
    '/api/descriptions/?limit=3',
    f'/api/descriptions/{key_scored}',
    f'/api/scores/{key_scored}',
    '/api/perspectives/',
]

out = {'_note': ('Flask responses captured against the real 43k-image library.db, as a '
                 'parity baseline for tests/catalog-parity.test.ts. Regenerate with '
                 'scripts/capture-flask-parity.py when the Flask behaviour legitimately '
                 'changes; delete at cutover.'),
       'keys': {'scored': key_scored, 'stacked': key_stacked, 'stack_id': stack_id,
                'clip': key_clip, 'perspective': perspective, 'month': month},
       'responses': {}}
for path in REQUESTS:
    r = client.get(path)
    out['responses'][path] = {'status': r.status_code, 'json': r.get_json()}
FIXTURE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'tests', 'fixtures',
    'flask-catalog-parity.json',
)
with open(FIXTURE, 'w') as fh:
    json.dump(out, fh, indent=1, sort_keys=True)
    fh.write('\n')
print(f'captured {len(REQUESTS)} responses to {os.path.relpath(FIXTURE)}')
