"""Loopback-only development entry point. Never used by Cloud Run."""
import argparse, base64, json, secrets, uuid, threading, time, logging
from pathlib import Path
from wsgiref.simple_server import make_server
from app import Application, OWNER
from core import workbook_info
from storage import SQLiteStore, LocalObjects
import accounts, reminders, os

parser = argparse.ArgumentParser()
parser.add_argument('--data', type=Path, required=True)
parser.add_argument('--seed-folder', type=Path, required=True)
args = parser.parse_args()
args.data.mkdir(parents=True, exist_ok=True)
os.environ['TRIDENT_LOCAL_DATA']=str(args.data.resolve())
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

# The supplied workbook is the one-time starting dataset, not an ongoing upload workflow.
stock_path = args.data / 'stock-source.xlsx'
if stock_path.exists():
    import stock_import
    revision, state = store.read()
    raw_stock = stock_path.read_bytes()
    candidate = stock_import.preview(raw_stock, 'Trident Community Equipment SOH 09.10.2026.xlsx')
    if not state.get('stock', {}).get('products'):
        seeded = stock_import.apply(state, candidate, 'Local starting workbook', raw_stock)
        if not store.commit(revision, seeded):raise SystemExit('Stock changed during setup. Restart to retry safely.')
    elif not state['stock'].get('workbookTemplate') and any(i['fingerprint'] == candidate['fingerprint'] for i in state['stock'].get('imports', [])):
        state['stock']['workbookTemplate'] = base64.b64encode(raw_stock).decode()
        if not store.commit(revision, state):raise SystemExit('Stock changed while saving its export format. Restart to retry safely.')

# User confirmed on 14 October: column E is the opening stock quantity.
revision, state = store.read()
confirmed_stock = stock_import.confirm_quantities(state, 'User confirmation: column E quantity') if stock_path.exists() else state
if confirmed_stock != state and not store.commit(revision, confirmed_stock):raise SystemExit('Stock changed during quantity confirmation. Restart to retry safely.')

token = os.environ.get('TRIDENT_DEV_TOKEN') or secrets.token_urlsafe(32)
origin = 'http://127.0.0.1:18780'
api = Application(store, objects, lambda value: accounts.FIRST_ADMIN if secrets.compare_digest(value, token) else '', origin, local=True, stock_source=(args.data / "stock-source.xlsx").read_bytes() if (args.data / "stock-source.xlsx").exists() else None)

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
