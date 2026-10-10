#!/usr/bin/env bash
set -euo pipefail
: "${GOOGLE_CLIENT_ID:=1087455515042-ql715veu24peb1hhfrp69sj31t8sahaf.apps.googleusercontent.com}"
PROJECT=trident-dashboard-511019
REGION=australia-southeast1
# Application requests are checked using Google tokens and the owner's email.
# --allow-unauthenticated is required for browser tokens to reach the API;
# it does not grant access to workbook, quote or PDF endpoints.
gcloud run deploy trident-quote-api --project="$PROJECT" --region="$REGION" --source=backend --allow-unauthenticated --service-account="quote-api@$PROJECT.iam.gserviceaccount.com" --min-instances=0 --max-instances=2 --concurrency=8 --memory=512Mi --timeout=120 --set-env-vars="GOOGLE_CLIENT_ID=$GOOGLE_CLIENT_ID,FRONTEND_ORIGIN=https://trident.nikita-trident2024.workers.dev,BIGQUERY_TABLE=$PROJECT.trident_quotes.app_state,PDF_BUCKET=$PROJECT-quote-pdfs"
gcloud run services describe trident-quote-api --project="$PROJECT" --region="$REGION" --format='value(status.url)'
