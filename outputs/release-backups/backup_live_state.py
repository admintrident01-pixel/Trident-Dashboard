import json
import hashlib
import datetime
import subprocess

from google.cloud import bigquery, storage


PROJECT = 'trident-dashboard-511203'
TABLE = f'{PROJECT}.trident_quotes.app_state'
BUCKET = f'{PROJECT}-quote-pdfs'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def read_table(name):
    rows = list(bq.query(f"SELECT revision, TO_JSON_STRING(state) AS state FROM `{name}` WHERE id='main'").result())
    if len(rows) != 1:
        raise RuntimeError(f'Expected one live register row, got {len(rows)}')
    state = json.loads(rows[0].state)
    data = canonical(state)
    return int(rows[0].revision), state, data, hashlib.sha256(data).hexdigest()


def service_revision():
    output = subprocess.run(
        ['gcloud', 'run', 'services', 'describe', 'trident-quote-api', '--region=australia-southeast1', '--project=' + PROJECT, '--format=json'],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    service = json.loads(output)
    traffic = service.get('status', {}).get('traffic', [])
    active = next((row for row in traffic if int(row.get('percent', 0)) == 100), traffic[0] if traffic else {})
    containers = service.get('spec', {}).get('template', {}).get('spec', {}).get('containers', [])
    env = containers[0].get('env', []) if containers else []
    commit = next((item.get('value', '') for item in env if item.get('name') == 'COMMIT_SHA'), '')
    return active.get('revisionName', ''), int(active.get('percent', 0) or 0), commit


stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
tag = f'oncall-days_{stamp}'
snapshot = f'{PROJECT}.trident_quotes.app_state_before_oncall_days_{stamp}'
prefix = f'release-backups/{tag}/'
bq = bigquery.Client(project=PROJECT)
bucket = storage.Client(project=PROJECT).bucket(BUCKET)

revision, state, state_bytes, state_sha = read_table(TABLE)
bq.query(f"CREATE TABLE `{snapshot}` AS SELECT * FROM `{TABLE}`").result()
clone_revision, _, _, clone_sha = read_table(snapshot)
if (clone_revision, clone_sha) != (revision, state_sha):
    raise RuntimeError('BigQuery clone does not match the live register')

referenced = set()
for value in state.get('pdfs', {}).values():
    if isinstance(value, str) and value:
        referenced.add(value)
for row in state.get('officeFiles', {}).values():
    if isinstance(row, dict) and row.get('key'):
        referenced.add(row['key'])
for row in state.get('jobImports', {}).values():
    if isinstance(row, dict) and row.get('objectKey'):
        referenced.add(row['objectKey'])

live = [blob for blob in bucket.list_blobs() if not blob.name.startswith('release-backups/')]
live_names = {blob.name for blob in live}
missing = sorted(referenced - live_names)
if missing:
    raise RuntimeError('Register references missing uploads: ' + ', '.join(missing))

inventory = []
for blob in sorted(live, key=lambda item: item.name):
    if not blob.md5_hash or not blob.crc32c:
        raise RuntimeError('No stored checksum for ' + blob.name)
    destination = bucket.copy_blob(blob, bucket, prefix + blob.name)
    if destination is None:
        raise RuntimeError('Copy failed for ' + blob.name)
    destination.reload()
    if (destination.size, destination.md5_hash, destination.crc32c) != (blob.size, blob.md5_hash, blob.crc32c):
        raise RuntimeError('Checksum mismatch for ' + blob.name)
    inventory.append({
        'name': blob.name,
        'bytes': int(blob.size),
        'md5': blob.md5_hash,
        'crc32c': blob.crc32c,
        'contentType': blob.content_type or '',
        'backupGeneration': int(destination.generation),
    })

inventory_bytes = canonical(inventory)
inventory_sha = hashlib.sha256(inventory_bytes).hexdigest()
last_revision, _, _, last_sha = read_table(TABLE)
if last_revision != revision or last_sha != state_sha:
    raise RuntimeError(f'Live register changed during backup: {revision}->{last_revision}')

api_revision, traffic_percent, commit_sha = service_revision()
summary = {
    'phase': 'before',
    'project': PROJECT,
    'tag': tag,
    'registerSnapshot': snapshot,
    'registerRevision': revision,
    'stateSha256': state_sha,
    'canonicalStateUri': f'gs://{BUCKET}/{prefix}register/app_state_canonical.json',
    'liveUploadObjects': len(live),
    'referencedUploadObjects': len(referenced),
    'missingReferencedUploads': len(missing),
    'uploadBackupPrefix': f'gs://{BUCKET}/{prefix}',
    'uploadInventorySha256': inventory_sha,
    'uploadsChecksumVerified': True,
    'checksumMethod': 'GCS stored MD5 and CRC32C source/destination match',
    'apiRevision': api_revision,
    'trafficPercent': traffic_percent,
    'commitSha': commit_sha,
}
bucket.blob(prefix + 'register/app_state_canonical.json').upload_from_string(state_bytes, content_type='application/json')
bucket.blob(prefix + 'register/upload-inventory.json').upload_from_string(inventory_bytes, content_type='application/json')
bucket.blob(prefix + 'register/backup-summary.json').upload_from_string(canonical(summary), content_type='application/json')
print('TRIDENT_BACKUP_BEFORE=' + json.dumps(summary, separators=(',', ':'), sort_keys=True))
