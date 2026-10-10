#!/usr/bin/env bash
set -euo pipefail
# Run from Online in Google Cloud Shell, after reviewing the setup guide.
PROJECT=trident-dashboard-511019
REGION=australia-southeast1
DATASET=trident_quotes
TABLE="$PROJECT.$DATASET.app_state"
BUCKET="$PROJECT-quote-pdfs"
SERVICE=trident-quote-api
ACCOUNT="quote-api@$PROJECT.iam.gserviceaccount.com"
: "${GOOGLE_CLIENT_ID:=1087455515042-ql715veu24peb1hhfrp69sj31t8sahaf.apps.googleusercontent.com}"
gcloud config set project "$PROJECT"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com bigquery.googleapis.com storage.googleapis.com iam.googleapis.com
if ! gcloud iam service-accounts describe "$ACCOUNT" >/dev/null 2>&1; then
 gcloud iam service-accounts create quote-api --display-name='Trident Quote API'
fi
gcloud projects add-iam-policy-binding "$PROJECT" --member="serviceAccount:$ACCOUNT" --role=roles/bigquery.jobUser --condition=None
bq --location="$REGION" query --use_legacy_sql=false "CREATE SCHEMA IF NOT EXISTS \`$PROJECT.$DATASET\` OPTIONS(location='$REGION'); CREATE TABLE IF NOT EXISTS \`$TABLE\` (id STRING, revision INT64, state JSON); GRANT \`roles/bigquery.dataEditor\` ON SCHEMA \`$PROJECT.$DATASET\` TO 'serviceAccount:$ACCOUNT';"
if ! gcloud storage buckets describe "gs://$BUCKET" >/dev/null 2>&1; then
 gcloud storage buckets create "gs://$BUCKET" --location="$REGION" --uniform-bucket-level-access --public-access-prevention
fi
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" --member="serviceAccount:$ACCOUNT" --role=roles/storage.objectAdmin
printf '\nResources prepared. Initialise storage before deployment:\n'
printf 'export BIGQUERY_TABLE=%s\nexport PDF_BUCKET=%s\n' "$TABLE" "$BUCKET"
printf 'cd backend && pip install -r requirements.txt && python import_local.py /path/to/uploaded/local-version-b\n'
printf '\nNo private keys are needed. Cloud Run uses its service identity.\n'
