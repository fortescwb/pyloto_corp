# Debug: Fluxo Inbound Não Responde

## Problema

Mensagens recebidas via webhook do WhatsApp são processadas mas **nenhuma resposta é enviada**.

## Causa Raiz Identificada

**Orchestrator LLM não estava sendo injetado** no endpoint `/internal/process_inbound`, causando:
- Tasks processadas sem erro visível
- `outcome: null` nos logs
- Zero mensagens outbound enfileiradas

## Correções Aplicadas

### 1. Logs Diagnósticos Adicionados

**Arquivo**: `src/pyloto_corp/application/whatsapp_async.py`

Logs adicionados em cada etapa crítica:

```python
- handle_inbound_task_started
- messages_extracted (count)
- processing_message (has_from, has_text)
- calling_orchestrator
- orchestrator_response (has_reply, intent, outcome)
- message_skipped_* (com razão)
- outbound_job_prepared
- enqueuing_outbound
- outbound_enqueued
- handle_inbound_task_completed
```

### 2. Script de Teste Local

**Arquivo**: `scripts/test_inbound_flow.py`

Testa localmente sem dependências externas:

```bash
python scripts/test_inbound_flow.py
```

**Validações**:
- ✅ Extração de mensagens do payload
- ✅ Orquestrador gera resposta
- ✅ `outbound_job` construído corretamente
- ✅ Número tem prefixo `+`

---

## Deploy e Verificação

### Passo 1: Deploy

```bash
git pull origin main
./QUICKSTART_DEPLOY.sh staging
```

### Passo 2: Monitorar Logs em Tempo Real

```bash
# Terminal 1: Logs gerais
gcloud logging tail \
  "resource.type=cloud_run_revision
   AND resource.labels.service_name=pyloto-inbound-api-staging" \
  --project=atendimento-inicial-pyloto \
  --format=json

# Terminal 2: Logs específicos de processamento
gcloud logging tail \
  "resource.type=cloud_run_revision
   AND resource.labels.service_name=pyloto-inbound-api-staging
   AND (jsonPayload.message=~'.*inbound.*' OR jsonPayload.message=~'.*outbound.*')" \
  --project=atendimento-inicial-pyloto
```

### Passo 3: Enviar Mensagem Teste

Envie `oi` via WhatsApp para o número configurado.

### Passo 4: Validar Logs (OBRIGATÓRIO)

Buscar nos logs:

#### ✅ **Webhook Recebido**
```json
{
  "message": "webhook_enqueued",
  "signature_validated": true
}
```

#### ✅ **Task Inbound Iniciada**
```json
{
  "message": "handle_inbound_task_started",
  "inbound_event_id": "wamid..."
}
```

#### ✅ **Mensagens Extraídas**
```json
{
  "message": "messages_extracted",
  "count": 1
}
```

#### ✅ **Orchestrator Chamado**
```json
{
  "message": "calling_orchestrator",
  "text_preview": "oi"
}
```

#### ✅ **Orchestrator Respondeu** (CRÍTICO)
```json
{
  "message": "orchestrator_response",
  "has_reply": true,
  "intent": "ENTRY_UNKNOWN",
  "outcome": "AWAITING_USER",
  "reply_preview": "Olá! Bem-vindo à Pyloto..."
}
```

#### ✅ **Outbound Job Preparado**
```json
{
  "message": "outbound_job_prepared",
  "recipient_has_plus": true,
  "text_len": 120
}
```

#### ✅ **Outbound Enfileirado**
```json
{
  "message": "outbound_enqueued",
  "task_name": "projects/.../tasks/..."
}
```

#### ✅ **Mensagem Enviada**
```json
{
  "message": "message_sent_to_whatsapp_api",
  "message_id": "wamid..."
}
```

---

## Diagnóstico de Problemas

### Problema 1: `messages_extracted count: 0`

**Causa**: Payload do webhook não tem formato esperado.

**Solução**:
```bash
# Ver payload raw recebido
gcloud logging read \
  "resource.type=cloud_run_revision
   AND jsonPayload.message='webhook_enqueued'" \
  --project=atendimento-inicial-pyloto \
  --limit=1 \
  --format=json | jq '.[] | .jsonPayload.payload'
```

### Problema 2: `orchestrator_response has_reply: false`

**Causa**: Orchestrator decidiu não responder (ex: `DUPLICATE_OR_SPAM`).

**Solução**: Verificar `outcome` nos logs.

### Problema 3: `message_skipped_no_reply`

**Causa**: Orchestrator retornou `reply_text: None`.

**Ação**: Verificar lógica em `src/pyloto_corp/ai/orchestrator.py` método `_generate_reply()`.

### Problema 4: `enqueue_outbound_failed`

**Causa**: Falha ao criar task no Cloud Tasks.

**Solução**:
```bash
# Verificar permissões Cloud Tasks
gcloud projects get-iam-policy atendimento-inicial-pyloto \
  --flatten="bindings[].members" \
  --filter="bindings.role:cloudtasks"

# Verificar filas existem
gcloud tasks queues list \
  --project=atendimento-inicial-pyloto \
  --location=us-central1
```

### Problema 5: `whatsapp_send_failed`

**Causa**: Erro na API do WhatsApp.

**Solução**:
```bash
# Ver erro detalhado
gcloud logging read \
  "resource.type=cloud_run_revision
   AND jsonPayload.message='whatsapp_send_failed'" \
  --project=atendimento-inicial-pyloto \
  --limit=5 \
  --format=json | jq '.[] | .jsonPayload'

# Testar credenciais manualmente
PHONE_ID=$(gcloud secrets versions access latest \
  --secret=whatsapp-phone-number-id \
  --project=atendimento-inicial-pyloto)

ACCESS_TOKEN=$(gcloud secrets versions access latest \
  --secret=whatsapp-access-token \
  --project=atendimento-inicial-pyloto)

curl -X POST \
  "https://graph.facebook.com/v21.0/$PHONE_ID/messages" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "messaging_product": "whatsapp",
    "to": "5511999999999",
    "type": "text",
    "text": {"body": "Teste manual"}
  }'
```

---

## Teste Manual de Endpoint Interno

```bash
# Obter token
INTERNAL_TOKEN=$(gcloud secrets versions access latest \
  --secret="internal-task-token" \
  --project=atendimento-inicial-pyloto)

# Payload de teste
cat > /tmp/test_payload.json <<EOF
{
  "payload": {
    "entry": [{
      "changes": [{
        "value": {
          "messages": [{
            "id": "test_$(date +%s)",
            "from": "5511999999999",
            "text": {"body": "teste manual"},
            "timestamp": "$(date +%s)",
            "type": "text"
          }]
        }
      }]
    }]
  },
  "inbound_event_id": "manual_test_$(date +%s)",
  "correlation_id": "manual_corr_$(date +%s)"
}
EOF

# Chamar endpoint
curl -X POST \
  "https://pyloto-inbound-api-staging-88092668443.us-central1.run.app/internal/process_inbound" \
  -H "Content-Type: application/json" \
  -H "X-Internal-Token: $INTERNAL_TOKEN" \
  -d @/tmp/test_payload.json \
  -v
```

**Resposta esperada**:
```json
{
  "ok": true,
  "result": {
    "processed": 1,
    "skipped": 0,
    "outbound_tasks": ["projects/.../tasks/..."]
  }
}
```

---

## Checklist Pós-Deploy

- [ ] Deploy concluído sem erros
- [ ] Logs em tempo real configurados
- [ ] Mensagem teste enviada via WhatsApp
- [ ] Log `webhook_enqueued` apareceu
- [ ] Log `messages_extracted count: 1` apareceu
- [ ] Log `orchestrator_response has_reply: true` apareceu
- [ ] Log `outbound_job_prepared` apareceu
- [ ] Log `outbound_enqueued` apareceu
- [ ] Log `message_sent_to_whatsapp_api` apareceu
- [ ] **Resposta recebida no WhatsApp**

---

## Recursos

- [Logs Cloud Run (staging)](https://console.cloud.google.com/logs/query?project=atendimento-inicial-pyloto&query=resource.type%3D%22cloud_run_revision%22%0Aresource.labels.service_name%3D%22pyloto-inbound-api-staging%22)
- [Cloud Tasks Queues](https://console.cloud.google.com/cloudtasks?project=atendimento-inicial-pyloto)
- [Webhook Meta](https://developers.facebook.com/apps/YOUR_APP_ID/whatsapp-business/wa-settings/)

---

## Contato

Se problema persistir após seguir este guia:

1. Coletar outputs de **todos** os comandos acima
2. Exportar logs: `gcloud logging read ... --format=json > debug_logs.json`
3. Abrir issue no repositório com logs anexados
