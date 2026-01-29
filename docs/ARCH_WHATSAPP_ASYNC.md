# Arquitetura WhatsApp Async — Cloud Run + Cloud Tasks

## Fluxo ponta a ponta
- Webhook `/webhooks/whatsapp` valida assinatura HMAC e calcula `inbound_event_id` (mensagem Meta ou hash SHA-256 do payload ordenado).
- Se `mark_if_new` no dedupe persistente retornar **True**, enfileira task HTTP na fila inbound (`INBOUND_TASK_QUEUE_NAME`) chamando `INTERNAL_TASK_BASE_URL/internal/process_inbound` com `X-Internal-Token` e `correlation_id`.
- Cloud Tasks entrega para `/internal/process_inbound`, que registra rastro (`inbound_processing_started/finished` + persistência com TTL), normaliza mensagens e cria **1 task outbound por mensagem** na fila outbound (`OUTBOUND_TASK_QUEUE_NAME`), sempre com o token interno.
- `/internal/process_outbound` consome a task outbound, aplica idempotência outbound (Redis/Firestore) e envia via `WhatsAppOutboundClient`.
- Respostas são idempotentes: dedupe inbound evita múltiplos enqueues; dedupe outbound evita múltiplos envios mesmo com retries do Cloud Tasks.

## Idempotência, dedupe e rastro
- **Inbound (dedupe)**: chave preferencial `messages[0].id`; fallback hash SHA-256 do payload JSON ordenado e sem campos voláteis. `mark_if_new` (Redis/Firestore; TTL padrão 7 dias) retorna False para duplicados e bloqueia novo enqueue. Em staging/prod, indisponibilidade do backend falha fechado (HTTP 500).
- **Inbound (rastro)**: `/internal/process_inbound` marca início e fim em backend persistente (Redis/Firestore; TTL 7 dias) com `inbound_event_id`, `correlation_id`, `task_name`, timestamps e status de enfileiramento outbound. Logs estruturados acompanham o mesmo contexto.
- **Outbound**: `OutboundDedupeStore` marca idempotency_key como pending/sent/failed em backend persistente (Redis/Firestore). Retries usam a mesma chave, evitando mensagens duplicadas.

## Retries e classificação de erros
- Cloud Tasks reexecuta em 5xx/429. `/internal/process_inbound` retorna 503 se não conseguir registrar rastro ou enfileirar outbound. `/internal/process_outbound` retorna 503 para erros retryable (429, 5xx, timeout HTTP); 4xx permanentes retornam 400/502 com `whatsapp_permanent_error`.
- `schedule_time` opcional disponível no dispatcher para backoff customizado se necessário.

## Segurança dos endpoints internos
- Todos os handlers internos exigem header `X-Internal-Token` (configurável por `INTERNAL_TASK_TOKEN`). Base URL interna deve ser **https** em staging/prod.
- Payloads das tasks são JSON; sem PII em logs. `correlation_id` é propagado e logado em todas as etapas.

## Rate limit e concorrência
- Controle de vazão/concurrency fica na configuração das filas Cloud Tasks:
  - Inbound (sugerido): `maxDispatchesPerSecond >= 50`, `maxConcurrentDispatches >= 50`.
  - Outbound (sugerido): `maxDispatchesPerSecond` e `maxConcurrentDispatches` entre 5 e 20 para evitar 429 na API Meta.
  - Retry policy: `min-backoff >= 5s`, `max-backoff <= 10m`, `max-attempts` definido.
- Cada task = 1 mensagem; não agrupar em lote dentro do worker. Nenhum paralelismo extra é criado na aplicação além do fornecido pelo Cloud Tasks.
