import datetime
import hashlib
import json
import subprocess

from google.cloud import bigquery, storage


PROJECT = 'trident-dashboard-511203'
TABLE = f'{PROJECT}.trident_quotes.app_state'
BUCKET = f'{PROJECT}-quote-pdfs'
PRE_TAG = 'oncall-days_20261114T042223Z'
PREFIX = f'release-backups/{PRE_TAG}/'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def section_diff(before, after):
    keys = sorted(set(before) | set(after))
    return [key for key in keys if canonical(before.get(key)) != canonical(after.get(key))]


def referenced_keys(state):
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
    return referenced


def inventory_row(blob):
    return {
        'name': blob.name,
        'bytes': int(blob.size),
        'md5': blob.md5_hash,
        'crc32c': blob.crc32c,
        'contentType': blob.content_type or '',
    }


def service_details():
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
    image = containers[0].get('image', '') if containers else ''
    return active.get('revisionName', ''), int(active.get('percent', 0) or 0), image, image.rsplit(':', 1)[-1]


bq = bigquery.Client(project=PROJECT)
bucket = storage.Client(project=PROJECT).bucket(BUCKET)
rows = list(bq.query(f"SELECT revision, TO_JSON_STRING(state) AS state FROM `{TABLE}` WHERE id='main'").result())
if len(rows) != 1:
    raise RuntimeError(f'Expected one live register row, got {len(rows)}')
revision = int(rows[0].revision)
state = json.loads(rows[0].state)
state_bytes = canonical(state)
state_sha = hashlib.sha256(state_bytes).hexdigest()

pre_summary = json.loads(bucket.blob(PREFIX + 'register/backup-summary.json').download_as_text())
pre_state = json.loads(bucket.blob(PREFIX + 'register/app_state_canonical.json').download_as_bytes())
pre_inventory = json.loads(bucket.blob(PREFIX + 'register/upload-inventory.json').download_as_text())
pre_revision = int(pre_summary['registerRevision'])
pre_state_sha = pre_summary['stateSha256']

live = [blob for blob in bucket.list_blobs() if not blob.name.startswith('release-backups/')]
live_inventory = sorted((inventory_row(blob) for blob in live), key=lambda item: item['name'])
pre_business_inventory = sorted(
    (
        {
            'name': row['name'],
            'bytes': int(row['bytes']),
            'md5': row['md5'],
            'crc32c': row['crc32c'],
            'contentType': row.get('contentType', ''),
        }
        for row in pre_inventory
    ),
    key=lambda item: item['name'],
)
inventory_matches = digest(live_inventory) == digest(pre_business_inventory)
referenced = referenced_keys(state)
live_names = {blob.name for blob in live}
missing = sorted(referenced - live_names)
api_revision, traffic_percent, image, image_commit = service_details()

summary = {
    'phase': 'after',
    'verifiedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'project': PROJECT,
    'preReleaseTag': PRE_TAG,
    'preRegisterRevision': pre_revision,
    'preStateSha256': pre_state_sha,
    'liveRegisterRevision': revision,
    'liveStateSha256': state_sha,
    'registerStateChanged': (pre_revision, pre_state_sha) != (revision, state_sha),
    'changedStateSections': section_diff(pre_state, state),
    'liveUploadObjects': len(live),
    'preProfileUploadObjects': len(pre_inventory),
    'uploadBusinessInventoryMatches': inventory_matches,
    'uploadBusinessInventorySha256': digest(live_inventory),
    'missingReferencedUploads': len(missing),
    'apiRevision': api_revision,
    'trafficPercent': traffic_percent,
    'apiImage': image,
    'deployedCommitSha': image_commit,
}
verification_prefix = PREFIX + 'post-release/'
bucket.blob(verification_prefix + 'live-state-canonical.json').upload_from_string(state_bytes, content_type='application/json')
bucket.blob(verification_prefix + 'upload-inventory.json').upload_from_string(canonical(live_inventory), content_type='application/json')
bucket.blob(verification_prefix + 'verification-summary.json').upload_from_string(canonical(summary), content_type='application/json')
print('TRIDENT_POST_RELEASE_VERIFY=' + json.dumps(summary, separators=(',', ':'), sort_keys=True))
