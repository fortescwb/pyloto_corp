# Pipeline LLM — Arquitetura Completa v2

**Versão:** 1.0  
**Data:** 2026-01-26  
**Status:** Produção (staging-ready)  
**Responsável:** pyloto_corp/application/pipeline_v2.py

---

## 1. Visão Geral

O **Pipeline v2** é o orquestrador central do `pyloto_corp`. Recebe mensagens de webhook (WhatsApp via Meta API),
executa 3 pontos LLM em ordem estruturada, valida e deduplica, retorna resposta normalizada ou fallback.

**Características:**
- ✅ **Ordem garantida**: FSM → LLM#1 → LLM#2 → LLM#3 (estrutural, não lógica)
- ✅ **PII Safety**: Zero telefone/email/CPF em logs (mascaramento obrigatório)
- ✅ **Fallback determinístico**: Sem crash em timeouts/erros
- ✅ **Feature flag**: `OPENAI_ENABLED` para controlar ativação de LLM
- ✅ **Dedupe + Abuse check**: Prevenção de flood/spam
- ✅ **Stateless**: Cloud Run compatible

---

## 2. Arquitetura — Fluxo Completo

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ WEBHOOK (WhatsApp via Meta API)                                             │
│ POST /webhook                                                               │
│ Payload: {messages: [{from, id, text, media_type?, ...}], ...}             │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ [1] EXTRACT & VALIDATE                                                      │
│ • Extrair array de messages                                                 │
│ • Validar estrutura (message_id, chat_id obrigatórios)                     │
│ • Sanitizar para logs (antes de log interno)                               │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ [2] DEDUPE CHECK (Redis)                                                    │
│ • Chave: app:prod:chat_id:message_id                                       │
│ • TTL: 3600s                                                                │
│ • Se duplicado: skip mensagem                                              │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 ↓ (unique)
┌─────────────────────────────────────────────────────────────────────────────┐
│ [3] GET/CREATE SESSION                                                      │
│ • Chave: app:prod:chat_id:session                                          │
│ • Recuperar ou criar SessionState                                          │
│ • Inicializar: state='init', intenção=None, etc                           │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ [4] ABUSE DETECTION                                                         │
│ • Flood: > 10 msgs / minuto                                                │
│ • Spam pattern: keywords conhecidas                                        │
│ • Intent capacity: > 3 intenções ativas por sessão                         │
│ • Se abusivo: block (log error, retorna early)                             │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 ↓ (clean)
┌─────────────────────────────────────────────────────────────────────────────┐
│ [5] FSM: DETERMINE STATE                                                    │
│ • Input: current_state (init/qualifying/details/closing/ended)             │
│ • Input: message text                                                       │
│ • Output: (current_state, next_state)                                      │
│ • Determinístico: baseado em keywords/patterns                             │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ [6] FEATURE FLAG: OPENAI_ENABLED?                                           │
│ ├─ FALSE: Usar fallback (skip LLM, resposta templates)                     │
│ └─ TRUE: Executar 3 LLM points (abaixo)                                    │
└────────────────────────────────┬────────────────────────────────────────────┘
         ┌──────────────────────┴──────────────────────┐
         │ (if OPENAI_ENABLED=True)                   │ (if False)
         ↓                                            ↓
    [7] LLM#1                              [FALLBACK PATH]
    EVENT DETECTION                        (MessageBuilder)
    ────────────────                       (Template)
    Input: message text                    ↓
    Output: EventDetectionResult           [12] FALLBACK
           (event_type,                    MESSAGE
            confidence,                    (determinístico)
            reasoning)                     ↓
         ↓                                 │
    [8] LLM#2                              │
    RESPONSE GENERATION                    │
    ─────────────────────                  │
    Input: event_type,                     │
           current_state,                  │
           next_state                      │
    Output: ResponseGenerationResult       │
            (generated_response,           │
             intent_clarity,               │
             reasoning)                    │
         ↓                                 │
    [9] LLM#3                              │
    MESSAGE TYPE SELECTION                 │
    ──────────────────────────             │
    Input: current_state,                  │
           event_type,                     │
           llm2_result ← REQUIRED          │
    Output: MessagePlan                    │
            (message_type,                 │
             message_content,              │
             send_immediately)             │
         └──────────────┬────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ [10] MESSAGE BUILDER                                                        │
│ • Input: MessagePlan (type + content)                                       │
│ • Output: WhatsApp payload (dict)                                           │
│ • Funções: text/media/template/reaction/reply builders                      │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ [11] PAYLOAD VALIDATION & SANITIZE                                          │
│ • validate_payload(): verificar obrigatórios                               │
│ • sanitize_payload(): mascara telefone, email, CPF                         │
│ • Preparar para log (NENHUM PII visível)                                   │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ [13] SEND (Placeholder)                                                     │
│ • Atualmente: log only                                                      │
│ • Futuro: HTTP POST para WhatsApp API                                      │
│ • Retry logic: exponential backoff (3x)                                    │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ [14] PERSIST SESSION + OUTCOME                                              │
│ • Update session: state = next_state                                       │
│ • Log outcome: sent/failed/fallback                                        │
│ • TTL: 604800s (7 dias)                                                    │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ [15] RETURN SUMMARY                                                         │
│ WebhookProcessingSummary {                                                  │
│   processed_count: int,                                                     │
│   success_count: int,                                                       │
│   failed_count: int,                                                        │
│   fallback_count: int,                                                      │
│   errors: [...]                                                             │
│ }                                                                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Componentes Chave

### 3.1 FSM (Finite State Machine)

**Estados:**
- `init`: Primeira mensagem da sessão
- `qualifying`: Qualificando intenção
- `details`: Coletando detalhes
- `closing`: Encerrando
- `ended`: Sessão finalizada

**Transições:**
- Determinísticas baseadas em keywords (ex: "cancela" → closing)
- Input: texto da mensagem
- Output: (current_state, next_state)

### 3.2 LLM#1: Event Detection

**Prompt:** Detecta tipo de evento (pergunta, reclamação, elogio, etc)

**Input:**
```python
message_text: str
```

**Output:**
```python
EventDetectionResult(
    event_type: str,            # "question" | "complaint" | "praise" | etc
    confidence: float,          # 0.0-1.0
    reasoning: str              # Explicação do raciocínio
)
```

**Timeout:** 10s (default) → Fallback se exceder

### 3.3 LLM#2: Response Generation

**Prompt:** Gera resposta baseada no evento e estado

**Input:**
```python
event_type: str                 # De LLM#1
current_state: str
next_state: str
message: WhatsAppMessage
```

**Output:**
```python
ResponseGenerationResult(
    generated_response: str,    # Texto da resposta
    intent_clarity: float,      # 0.0-1.0
    reasoning: str
)
```

**Timeout:** 15s (default) → Fallback se exceder

### 3.4 LLM#3: Message Type Selection

**Prompt:** Seleciona tipo de mensagem (text/template/media/reply)

**Input:**
```python
current_state: str
event_type: str
llm2_result: ResponseGenerationResult  # ← OBRIGATÓRIO
```

**Output:**
```python
MessagePlan(
    message_type: str,          # "text" | "template" | "media" | "reply"
    message_content: dict,      # Payload específico do tipo
    send_immediately: bool
)
```

**Garantia Estrutural:** LLM#3 recebe `llm2_result` como argumento → ordem verificada em compile-time.

---

## 4. Tratamento de Erros & Fallback

### Cadeia de Fallback

```
LLM Error (timeout/api_error/parsing_error)
    ↓
ImportError (fallback função não existe)
    ↓
Template Response (genérico: "Deixe-me verificar...")
    ↓
Return bool (processado, sim/não)
```

### Exemplo: Timeout LLM#1

```python
try:
    result = asyncio.run(llm1_event_detection(...), timeout=10)
except asyncio.TimeoutError:
    logger.warning("llm1_timeout", extra={"chat_id": msg.chat_id})
    result = from_fallback_event_detection()  # MessageType.INFO
    return result
```

### Exemplo: API Error LLM#2

```python
try:
    result = openai_client.call_gpt4omini(...)
except openai.APIError as e:
    logger.error("llm2_api_error", extra={"error": str(e)})
    result = from_fallback_response_generation()  # Template
    return result
```

---

## 5. Logging & PII Safety

### Regras Obrigatórias

1. **NUNCA log bruto de payload** — sempre sanitizar antes de log
2. **Mascaramento:** 
   - Telefone: "5511987654321" → "***7654"
   - Email: "user@example.com" → "[EMAIL]"
   - CPF: "123.456.789-10" → "[DOCUMENT]"
3. **Headers sensíveis:** Nunca logar Authorization, tokens
4. **Exemplo de payload sanitizado:**

```python
sanitized_payload = {
    "id": "wamid.***1234",
    "from": "***7654",  # Mascarado
    "text": "Olá, tudo bem?",
    "timestamp": "1705950000"
}
```

### Estrutura de Logs

```json
{
  "timestamp": "2026-01-26T10:30:45.123Z",
  "service": "pyloto_corp",
  "env": "staging",
  "version": "2.0.0",
  "request_id": "req-xyz-123",
  "tenant_id": "tenant-001",
  "event_type": "webhook_processed",
  "message": "llm1_event_detected",
  "metadata": {
    "chat_id": "***7654",
    "detected_event": "question",
    "confidence": 0.95,
    "llm_model": "gpt-4o-mini"
  }
}
```

---

## 6. Feature Flag: OPENAI_ENABLED

### Setup em Staging

**Environment Variable:**
```bash
export OPENAI_ENABLED=true
export OPENAI_MODEL=gpt-4o-mini
export OPENAI_TIMEOUT_SECONDS=10
```

**Google Cloud Secret Manager:**
```bash
gcloud secrets create openai-api-key --replication-policy="automatic"
gcloud secrets versions add openai-api-key --data-file=- <<< "$OPENAI_API_KEY"

# Bind to Cloud Run:
gcloud run services update pyloto-inbound-api \
  --set-env-vars=OPENAI_ENABLED=true \
  --update-secrets=OPENAI_API_KEY=openai-api-key:latest
```

### Verificação em Runtime

```python
from pyloto_corp.config.settings import get_settings

settings = get_settings()

if not settings.openai_enabled:
    logger.info("openai_disabled: using fallback", 
                extra={"reason": "feature_flag_off"})
    return self._process_with_fallback(msg, session)

# Ativa LLM pipeline
openai_client = get_openai_client()
result_llm1 = await llm1_event_detection(msg, openai_client)
```

### Rollout Gradual

1. **Staging (OPENAI_ENABLED=true):** Teste com dados reais (mas sanado)
2. **Prod (OPENAI_ENABLED=true, 10% traffic):** Gradual A/B
3. **Prod (OPENAI_ENABLED=true, 100% traffic):** Full rollout

---

## 7. Exemplo: Fluxo Completo

### Input Webhook

```json
{
  "messages": [
    {
      "from": "5511987654321",
      "id": "wamid.HBEUIkZmXFY1234567890",
      "text": "Olá, quero saber sobre automação de atendimento",
      "timestamp": "1705950045"
    }
  ]
}
```

### Processamento (com logs sanitizados)

```
[1] Extract: ✅ Validado
[2] Dedupe: ✅ Unique (hash: abc123)
[3] Session: ✅ Created (chat_id=***7654)
[4] Abuse: ✅ Clean (1 msg/min)
[5] FSM: init → qualifying (keyword: automação)
[6] Feature flag: OPENAI_ENABLED=true ✅
[7] LLM#1: event_type="question", conf=0.92
[8] LLM#2: response="Perfeito! Posso ajudar com..."
[9] LLM#3: type="text", content="Perfeito! Posso ajudar..."
[10] Builder: ✅ Payload criado
[11] Validate: ✅ Obrigatórios presentes
[12] Sanitize: ✅ Sem PII em log
[13] Send: [PLACEHOLDER] → Future HTTP POST
[14] Persist: ✅ Session updated (state=qualifying)
[15] Return: {processed: 1, success: 1, failed: 0, fallback: 0}
```

### Output (Sanitizado para Cliente)

```json
{
  "messaging_product": "whatsapp",
  "to": "***7654",
  "type": "text",
  "text": {
    "body": "Perfeito! Posso ajudar com automação de atendimento via WhatsApp."
  }
}
```

---

## 8. Staging Deployment Checklist

- [ ] **Env Vars Setup**
  - [ ] `OPENAI_ENABLED=true`
  - [ ] `OPENAI_API_KEY` (via Secret Manager)
  - [ ] `OPENAI_MODEL=gpt-4o-mini`
  - [ ] `OPENAI_TIMEOUT_SECONDS=10`

- [ ] **Code Validation**
  - [ ] `ruff check src/pyloto_corp/ --select=E,W,F,I` → 0 errors
  - [ ] `python -m pytest tests/test_llm_pipeline_e2e.py -v` → 8 tests passing
  - [ ] `pytest --cov=src/pyloto_corp/ai --cov=src/pyloto_corp/application` → >= 85%

- [ ] **Deployment**
  - [ ] Build Docker image com pipeline_v2.py
  - [ ] Deploy para Cloud Run staging region
  - [ ] Verify health check endpoint: `GET /health` → 200 OK

- [ ] **Manual Testing**
  - [ ] Send test message via WhatsApp staging webhook
  - [ ] Verify logs contain: `llm1_event_detected`, `llm2_response_generated`, `llm3_message_type_selected`
  - [ ] Grep logs for unmasked PII (phone/email/CPF) → 0 matches
  - [ ] Verify `generated_response` in session store updated

- [ ] **Load Test**
  - [ ] 10 requests/sec × 60s (600 total)
  - [ ] Verify: no timeouts, fallback working, all logs sanitized

- [ ] **Regression Test**
  - [ ] Disable `OPENAI_ENABLED=false` → fallback template resposta
  - [ ] Verify: no crash, deterministic response

---

## 9. Troubleshooting

| Problema | Causa | Solução |
|----------|-------|---------|
| LLM timeout (> 10s) | API OpenAI lenta | Aumentar timeout ou usar fallback |
| PII em logs | sanitize_payload() não chamado | Verificar antes de logger.info() |
| Ordem não respeitada | LLM#3 chamado sem LLM#2 result | Conferir assinatura função (é obrigatório) |
| Session não persiste | Redis unavailable | Verificar Upstash connection |
| Feature flag não ativa | env var não setada | Verify: `echo $OPENAI_ENABLED` |

---

## 10. Próximas Releases

- **v2.1**: Implementar HTTP POST real para WhatsApp Send API
- **v2.2**: Add retry logic com exponential backoff
- **v2.3**: Integrar observabilidade completa (Cloud Trace)
- **v3.0**: Async pipeline (performance +50%)

