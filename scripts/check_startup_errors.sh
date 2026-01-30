#!/bin/bash
# Script para buscar erros de startup do container no Cloud Run

set -e

PROJECT_ID="atendimento-inicial-pyloto"
SERVICE_NAME="pyloto-inbound-api-staging"
REGION="us-central1"

echo "🔍 Buscando logs de erro da última revisão..."
echo ""

# Buscar erro de startup
echo "=== ERROS DE STARTUP (Container failed to start) ==="
gcloud logging read \
  "resource.type=cloud_run_revision
   AND resource.labels.service_name=$SERVICE_NAME
   AND (textPayload=~'Traceback' OR textPayload=~'Error' OR textPayload=~'Exception' OR severity>=ERROR)" \
  --project="$PROJECT_ID" \
  --limit=20 \
  --freshness=10m \
  --format="table(timestamp,severity,textPayload)"

echo ""
echo "=== LOGS DE IMPORT ERRORS ==="
gcloud logging read \
  "resource.type=cloud_run_revision
   AND resource.labels.service_name=$SERVICE_NAME
   AND textPayload=~'ImportError|ModuleNotFoundError'" \
  --project="$PROJECT_ID" \
  --limit=10 \
  --freshness=10m \
  --format="value(textPayload)"

echo ""
echo "=== LOGS RAW DA ÚLTIMA REVISÃO ==="
gcloud logging read \
  "resource.type=cloud_run_revision
   AND resource.labels.service_name=$SERVICE_NAME" \
  --project="$PROJECT_ID" \
  --limit=30 \
  --freshness=5m \
  --format=json > /tmp/cloudrun_startup_logs.json

echo "Logs salvos em: /tmp/cloudrun_startup_logs.json"
echo ""
echo "Exibindo primeiros 10 logs:"
jq -r '.[] | "[\(.timestamp)] \(.severity): \(.textPayload // .jsonPayload.message // "<no message>")"' /tmp/cloudrun_startup_logs.json | head -20
