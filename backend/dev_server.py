"""Loopback-only development entry point. Never used by Cloud Run."""
import argparse, base64, json, secrets, uuid, threading, time, logging
from pathlib import Path
from wsgiref.simple_server import make_server
from app import Application, OWNER
from core import workbook_info
from storage import SQLiteStore, LocalObjects
import accounts, reminders

parser = argparse.ArgumentParser()
parser.add_argument('--data', type=Path, required=True)
parser.add_argument('--seed-folder', type=Path, required=True)
args = parser.parse_args()
args.data.mkdir(parents=True, exist_ok=True)
store = SQLiteStore(str(args.data / 'quotes.db'))
objects = LocalObjects(args.data / 'pdfs')
if not (args.data / 'quotes.db').exists():
    book = (args.seed_folder / 'Trident-Quote-Settings.xlsx').read_bytes()
    workbook_info(book)
    state = {'workbook': base64.b64encode(book).decode(), 'quotes': {}, 'pdfs': {}}
    for path in (args.seed_folder / 'Quote Records').glob('quote-*.json'):
        quote = json.loads(path.read_text(encoding='utf-8-sig'))
        state['quotes'][str(int(quote['data']['fields']['number']))] = quote
    known = {f'Trident-quote-{number}.json' for number in state['quotes']}
    known.update(q.get('sourceDraftName', '') for q in state['quotes'].values())
    if any(path.name not in known for path in (args.seed_folder / 'Drafts').glob('*.json')):
        raise SystemExit('Open Version B Home to migrate older drafts first, then start local development.')
    for path in (args.seed_folder / 'Generated Quotes').glob('*.pdf'):
        key = 'quotes/' + str(uuid.uuid4()) + '.pdf'
        objects.put(key, path.read_bytes())
        state['pdfs'][path.name] = key
    store.initialise(state)

token = secrets.token_urlsafe(32)
origin = 'http://127.0.0.1:18780'
api = Application(store, objects, lambda value: accounts.FIRST_ADMIN if secrets.compare_digest(value, token) else '', origin, local=True)

def local_app(env, start_response):
    if env.get('REMOTE_ADDR') != '127.0.0.1':
        start_response('403 Forbidden', [('Content-Type', 'application/json')])
        return [b'{"error":"Local access only."}']
    if env['PATH_INFO'] == '/api/dev-session':
        if env.get('HTTP_ORIGIN') != origin or env['REQUEST_METHOD'] != 'GET':
            start_response('403 Forbidden', [('Content-Type', 'application/json')])
            return [b'{"error":"Open the local development page."}']
        data = json.dumps({'token': token, **accounts.public(accounts.users(store.read()[1])[accounts.FIRST_ADMIN])}).encode()
        start_response('200 OK', [('Content-Type', 'application/json'), ('Cache-Control', 'no-store'), ('Access-Control-Allow-Origin', origin), ('Vary', 'Origin')])
        return [data]
    if env['PATH_INFO'] == '/api/health':
        data = json.dumps({'ok': True, 'version': 'C', 'mode': 'local-development', 'data': str(args.data.resolve())}).encode()
        start_response('200 OK', [('Content-Type', 'application/json')])
        return [data]
    return api(env, start_response)

def reminder_worker():
    while True:
        time.sleep(60)
        try:
            revision, state = store.read()
            result, count = reminders.due_reminders(state)
            if count and store.commit(revision, result): reminders.deliver(store, local=True)
        except Exception: logging.exception('Local reminder preview job failed')

threading.Thread(target=reminder_worker, daemon=True).start()
make_server('127.0.0.1', 18782, local_app).serve_forever()
