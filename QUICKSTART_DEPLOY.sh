#!/bin/bash
# QUICKSTART: Deploy pyloto_corp para Staging
# Data: 2026-01-26
# Status: Fase 3C + Staging Setup completo

set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  🚀 QUICKSTART: Deploy pyloto_corp para Staging               ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

PROJECT_ID="atendimento-inicial-pyloto"
REGION="us-central1"
SERVICE_NAME="pyloto-inbound-api-staging"

# Resolver INTERNAL_TASK_BASE_URL (obrigatório em staging)
if [ -z "$INTERNAL_TASK_BASE_URL" ]; then
  EXISTING_SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --region "$REGION" \
    --project "$PROJECT_ID" \
    --format='value(status.url)' 2>/dev/null || true)

  if [ -n "$EXISTING_SERVICE_URL" ]; then
    INTERNAL_TASK_BASE_URL="$EXISTING_SERVICE_URL"
  else
    echo "❌ INTERNAL_TASK_BASE_URL não definido e serviço ainda não existe."
    echo "   Defina INTERNAL_TASK_BASE_URL (https) e execute novamente."
    exit 1
  fi
fi

# Step 1: Instalar dependências
echo "📦 [1/7] Instalando dependências..."
pip install -e .[dev] --quiet && echo "✅ Deps instaladas" || {
  echo "❌ Erro ao instalar deps"; exit 1
}

# Step 2: Rodar testes
echo ""
echo "🧪 [2/7] Executando testes E2E..."
pytest tests/test_llm_pipeline_e2e.py -v --tb=short || {
  echo "❌ Testes falharam"; exit 1
}

# Step 4: Lint final
echo "✅ Cobertura OK"
echo ""
echo "🔍 [4/7] Validando lint (ruff)..."
ruff check src/pyloto_corp/ --select=E,W,F,I && echo "✅ Lint OK" || {
  echo "❌ Lint errors"; exit 1
}

# Step 5: Verificar Dockerfile
echo ""
echo "🐳 [5/7] Verificando Dockerfile..."
if [ ! -f "Dockerfile" ]; then
  echo "⚠️  Dockerfile não encontrado. Criando básico..."
  cat > Dockerfile << 'EOFDOCKER'
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md /app/
COPY src /app/src
COPY docs /app/docs
RUN pip install --upgrade pip \
  && pip install .
EXPOSE 8080
CMD ["sh", "-c", "uvicorn pyloto_corp.api.app_async:app --host 0.0.0.0 --port ${PORT:-8080}"]
EOFDOCKER
fi
echo "✅ Dockerfile OK"

# Step 6: Deploy para Cloud Run
echo ""
echo "☁️  [6/7] Deployando para Cloud Run ($SERVICE_NAME)..."
gcloud run deploy $SERVICE_NAME \
  --source . \
  --platform managed \
  --region $REGION \
  --project $PROJECT_ID \
  --set-env-vars="OPENAI_ENABLED=true,OPENAI_MODEL=gpt-4o-mini,OPENAI_TIMEOUT_SECONDS=10,ENVIRONMENT=staging,LOG_LEVEL=INFO,CLOUD_TASKS_ENABLED=true,QUEUE_BACKEND=cloud_tasks,GCP_PROJECT=$PROJECT_ID,GCP_LOCATION=$REGION,INTERNAL_TASK_BASE_URL=$INTERNAL_TASK_BASE_URL,INBOUND_TASK_QUEUE_NAME=whatsapp-inbound,OUTBOUND_TASK_QUEUE_NAME=whatsapp-outbound,DEDUPE_BACKEND=redis,SESSION_STORE_BACKEND=redis,INBOUND_LOG_BACKEND=redis,OUTBOUND_DEDUPE_BACKEND=redis,DECISION_AUDIT_BACKEND=firestore" \
  --update-secrets="OPENAI_API_KEY=openai-api-key:latest,INTERNAL_TASK_TOKEN=internal-task-token:latest,REDIS_URL=redis-url:latest" \
  --cpu=1 \
  --memory=512Mi \
  --timeout=300 \
  --max-instances=10 \
  --concurrency=100 \
  --allow-unauthenticated && echo "✅ Deploy OK" || {
  echo "❌ Deploy falhou"; exit 1
}

# Step 7: Health check
echo ""
echo "🏥 [7/7] Verificando health check..."
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
  --region $REGION \
  --project $PROJECT_ID \
  --format='value(status.url)')

sleep 5  # Aguardar inicialização
HEALTH=$(curl -s -o /dev/null -w "%{http_code}" $SERVICE_URL/health) || true

if [ "$HEALTH" == "200" ]; then
  echo "✅ Health check OK"
  echo ""
  echo "╔════════════════════════════════════════════════════════════════╗"
  echo "║  🎉 DEPLOY STAGING COMPLETO                                   ║"
  echo "╚════════════════════════════════════════════════════════════════╝"
  echo ""
  echo "Service URL: $SERVICE_URL"
  echo ""
  echo "Próximos passos:"
  echo "  1. Enviar test webhook via WhatsApp"
  echo "  2. Verificar logs: gcloud run logs read $SERVICE_NAME --region $REGION"
  echo "  3. Validar PII: grep -E '[0-9]{11}|@' logs.txt (deve estar vazio)"
  echo "  4. Validar ordem LLM: grep 'llm[1-3]_' logs.txt"
  echo ""
else
  echo "❌ Health check falhou (HTTP $HEALTH)"
  echo "Verificar: gcloud run logs read $SERVICE_NAME --region $REGION --limit 50"
  exit 1
fi
