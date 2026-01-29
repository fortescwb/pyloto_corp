# Guia de Deploy em Staging — pyloto_corp

**Data:** 26 de janeiro de 2026  
**Status:** Pronto para deploy  
**Ambiente:** Google Cloud Run (us-central1)  
**Projeto GCP:** atendimento-inicial-pyloto

---

## 1. Pré-requisitos

✅ **Verificado:**
- gcloud CLI instalado e autenticado
- Projeto GCP: `atendimento-inicial-pyloto`
- Secrets criadas no Secret Manager:
  - `openai-api-key` (versão 2)
  - `openai-model` (gpt-4o-mini)
  - `openai-timeout-seconds` (10)
  - `internal-task-token`
  - `redis-url`

---

## 2. Variáveis de Ambiente (Cloud Run)

### Set para staging:

```bash
OPENAI_ENABLED=true
OPENAI_API_KEY=[via Secret Manager: openai-api-key:latest]
OPENAI_MODEL=gpt-4o-mini
OPENAI_TIMEOUT_SECONDS=10
CLOUD_TASKS_ENABLED=true
QUEUE_BACKEND=cloud_tasks
GCP_PROJECT=atendimento-inicial-pyloto
GCP_LOCATION=us-central1
INTERNAL_TASK_BASE_URL=https://pyloto-inbound-api-staging-xxxxx.a.run.app
INTERNAL_TASK_TOKEN=[via Secret Manager: internal-task-token:latest]
INBOUND_TASK_QUEUE_NAME=whatsapp-inbound
OUTBOUND_TASK_QUEUE_NAME=whatsapp-outbound
DEDUPE_BACKEND=redis
REDIS_URL=[via Secret Manager: redis-url:latest]
LOG_LEVEL=INFO
ENVIRONMENT=staging
```

---

## 3. Cloud Tasks Queues (create/update)

Comandos idempotentes (create ou update) para garantir rate/concurrency e retries:

```bash
# INBOUND — alta vazão, concorrência alta (>=50)
gcloud tasks queues create whatsapp-inbound \
  --location=us-central1 \
  --project=atendimento-inicial-pyloto \
  --max-dispatches-per-second=50 \
  --max-concurrent-dispatches=50 \
  --max-attempts=10 \
  --min-backoff=5s \
  --max-backoff=600s || \
gcloud tasks queues update whatsapp-inbound \
  --location=us-central1 \
  --project=atendimento-inicial-pyloto \
  --max-dispatches-per-second=50 \
  --max-concurrent-dispatches=50 \
  --max-attempts=10 \
  --min-backoff=5s \
  --max-backoff=600s

# OUTBOUND — mais restrita para evitar 429 na API Meta (5–20)
gcloud tasks queues create whatsapp-outbound \
  --location=us-central1 \
  --project=atendimento-inicial-pyloto \
  --max-dispatches-per-second=10 \
  --max-concurrent-dispatches=10 \
  --max-attempts=8 \
  --min-backoff=5s \
  --max-backoff=600s || \
gcloud tasks queues update whatsapp-outbound \
  --location=us-central1 \
  --project=atendimento-inicial-pyloto \
  --max-dispatches-per-second=10 \
  --max-concurrent-dispatches=10 \
  --max-attempts=8 \
  --min-backoff=5s \
  --max-backoff=600s
```

Nota: Outbound é propositalmente mais restrita para reduzir chance de 429/Rate Limit da API Meta.

---

## 4. Build & Deploy (Cloud Run)

### Opção 1: Usar Cloud Build (automatizado)

```bash
gcloud run deploy pyloto-inbound-api-staging \
  --source . \
  --platform managed \
  --region us-central1 \
  --project atendimento-inicial-pyloto \
  --set-env-vars="OPENAI_ENABLED=true,OPENAI_MODEL=gpt-4o-mini,OPENAI_TIMEOUT_SECONDS=10,ENVIRONMENT=staging,LOG_LEVEL=INFO" \
  --update-secrets="OPENAI_API_KEY=openai-api-key:latest" \
  --allow-unauthenticated \
  --cpu=1 \
  --memory=512Mi \
  --timeout=300 \
  --max-instances=10 \
  --concurrency=100
```

### Opção 2: Build local + push

```bash
# Build Docker localmente
docker build -t gcr.io/atendimento-inicial-pyloto/pyloto-inbound-api:staging .

# Push para Google Container Registry
docker push gcr.io/atendimento-inicial-pyloto/pyloto-inbound-api:staging

# Deploy da imagem
gcloud run deploy pyloto-inbound-api-staging \
  --image gcr.io/atendimento-inicial-pyloto/pyloto-inbound-api:staging \
  --platform managed \
  --region us-central1 \
  --project atendimento-inicial-pyloto \
  --set-env-vars="OPENAI_ENABLED=true" \
  --update-secrets="OPENAI_API_KEY=openai-api-key:latest"
```

---

## 5. Validação Pós-Deploy

### Health Check

```bash
curl https://pyloto-inbound-api-staging-xxxxx.a.run.app/health
# Esperado: 200 OK + JSON com status
```

### Test Webhook

```bash
curl -X POST https://pyloto-inbound-api-staging-xxxxx.a.run.app/webhook \
  -H "Content-Type: application/json" \
  -H "X-Hub-Signature-256: sha256=..." \
  -d '{
    "entry": [{
      "changes": [{
        "value": {
          "messages": [{
            "from": "5541988991078",
            "id": "wamid.test.123",
            "text": {"body": "Olá, teste!"},
            "timestamp": "1705950000"
          }]
        }
      }]
    }]
  }'
```

### Verificar Logs

```bash
# Logs em tempo real
gcloud run logs read pyloto-inbound-api-staging \
  --limit 50 \
  --region us-central1 \
  --project atendimento-inicial-pyloto

# Grep para verificar PII (deve estar vazio)
gcloud run logs read pyloto-inbound-api-staging \
  --limit 100 \
  --region us-central1 \
  --project atendimento-inicial-pyloto | grep -E "5541|@.*\.com|[0-9]{3}\.[0-9]{3}"

# Grep para verificar ordem de LLM
gcloud run logs read pyloto-inbound-api-staging \
  --limit 100 \
  --region us-central1 \
  --project atendimento-inicial-pyloto | grep -E "llm1_event_detected|llm2_response_generated|llm3_message_type_selected"
```

---

## 6. Testes E2E Locais (Antes de Deploy)

```bash
# Instalar dependências (uma vez)
pip install -e .[dev]

# Rodar testes E2E
pytest tests/test_llm_pipeline_e2e.py -v

# Rodar com cobertura
pytest --cov=src/pyloto_corp/ai --cov=src/pyloto_corp/application \
       tests/test_llm_pipeline_e2e.py

# Esperado: 8 testes passando, cobertura >= 85%
```

---

## 7. Feature Flags (Gradual Rollout)

### Staging: Teste com OpenAI ativado

```bash
OPENAI_ENABLED=true
# → LLM#1, LLM#2, LLM#3 executados normalmente
# → Fallback em caso de timeout/erro
```

### Produção (Fase 1): Apenas fallback (teste de baseline)

```bash
OPENAI_ENABLED=false
# → Nenhuma chamada OpenAI
# → Respostas templates determinísticas
# → Validar: nenhum crash, logs sanitizados
```

### Produção (Fase 2): 10% traffic com OpenAI

```bash
OPENAI_ENABLED=true
# → Ativar para 10% dos webhooks (via sampler ou customer ID)
# → Monitorar: latência, erros, PII em logs
# → Se OK → aumentar para 50%
```

### Produção (Fase 3): 100% com OpenAI

```bash
OPENAI_ENABLED=true
# → Rollout completo
# → Monitorar: métricas de qualidade, cost vs. benefit
```

---

## 8. Monitoramento em Produção

### Métricas Críticas

```
• Latência: p50, p95, p99 (target: < 2s)
• Taxa de erro: < 1% (target: < 0.5%)
• Timeouts LLM: trend (target: 0.1% de calls)
• PII em logs: 0 matches (regex: telefone, email, CPF)
• Dedupe rate: ~5% (expected: duplicatas normais)
```

### Alerts

- ❌ PII detectada em logs → Page oncall
- ❌ Taxa de erro > 2% → Alert
- ⚠️ Latência p95 > 5s → Warning
- ⚠️ Timeouts LLM > 5% → Warning

---

## 8. Rollback

### Se algo der errado:

```bash
# Desativar OpenAI (fallback mode)
gcloud run services update pyloto-inbound-api-staging \
  --set-env-vars=OPENAI_ENABLED=false \
  --region us-central1 \
  --project atendimento-inicial-pyloto

# Ou reverter para versão anterior
gcloud run services update-traffic pyloto-inbound-api-staging \
  --to-revisions LATEST=0,old-revision=100 \
  --region us-central1
```

---

## 9. Checklist de Deploy

- [ ] Todas 6 commits (Fase 3C) integradas
- [ ] `pytest tests/test_llm_pipeline_e2e.py -v` → 8 testes passando
- [ ] `ruff check src/` → 0 errors
- [ ] pyproject.toml atualizado com `openai>=1.45`
- [ ] Secrets criadas no GCP Secret Manager (3/3)
- [ ] Cloud Run policy permite pull de secrets
- [ ] Dockerfile contém setup de dependências
- [ ] Health check endpoint está respondendo
- [ ] Log sanitization ativo (nenhum PII visível)
- [ ] Staging webhook testado com mensagem real
- [ ] Alertas configurados (error rate, PII, latência)

---

## 10. Contato & Suporte

**Responsável:** pyloto_corp devops  
**Canal:** #deployments Slack  
**Runbook:** Este arquivo (DEPLOYMENT_STAGING.md)  
**Rollback:** 5 min para fallback, 15 min para versão anterior
