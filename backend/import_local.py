import argparse,base64,json,os,uuid
from pathlib import Path
from core import workbook_info
from storage import BigQueryStore,CloudObjects
p=argparse.ArgumentParser(description='Initialise empty cloud storage from a local Version B folder, once.');p.add_argument('folder',type=Path);args=p.parse_args()
book=(args.folder/'Trident-Quote-Settings.xlsx').read_bytes();workbook_info(book)
store=BigQueryStore();objects=CloudObjects();state={'workbook':base64.b64encode(book).decode(),'quotes':{},'pdfs':{}}
# Must only be run against an empty table, before the app is deployed.
if list(store.client.query(f'SELECT id FROM `{store.table}` LIMIT 1').result()):raise SystemExit('Storage already initialised. Nothing imported.')
for path in (args.folder/'Quote Records').glob('quote-*.json'):
 entry=json.loads(path.read_text(encoding='utf-8-sig'));state['quotes'][str(int(entry['data']['fields']['number']))]=entry
# Existing old drafts are intentionally not silently renumbered online.
known={f'Trident-quote-{n}.json' for n in state['quotes']}
unknown=[p.name for p in (args.folder/'Drafts').glob('*.json') if p.name not in known]
if unknown:raise SystemExit('Open Version B Home first to migrate older drafts, then retry: '+', '.join(unknown))
for path in (args.folder/'Generated Quotes').glob('*.pdf'):
 key='quotes/'+str(uuid.uuid4())+'.pdf';objects.put(key,path.read_bytes());state['pdfs'][path.name]=key
store.initialise(state);print('Workbook, quote records and PDFs imported. Keep the original local files as backup.')
