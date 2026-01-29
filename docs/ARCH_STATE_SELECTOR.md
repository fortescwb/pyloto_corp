# State Selector (LLM #1)

## Objetivo
Decidir o próximo estado conversacional antes de qualquer geração de resposta, aplicando gate de confiança e fallback seguro para evitar transições indevidas.

## Contrato I/O
- **Input (`StateSelectorInput`)**
  - `current_state`: estado atual (ConversationState)
  - `possible_next_states`: lista de estados candidatos
  - `message_text`, `history_summary`, `open_items`, `fulfilled_items`, `detected_requests`
- **Output (`StateSelectorOutput`)**
  - `selected_state`, `confidence`, `accepted`, `next_state`
  - `response_hint` (obrigatório quando `accepted=false`)
  - `status`: `done | in_progress | needs_clarification | new_request_detected`
  - listas `open_items`, `fulfilled_items`, `detected_requests`

Regra: `accepted = confidence >= 0.7`; se não aceito, `next_state = current_state`.

## Deterministic Precheck
- Detecta encerramento (“ok”, “entendi”, “obrigado”, etc.) → `status=needs_clarification`, `confidence` máx 0.69, gera `response_hint` pedindo confirmação.
- Detecta nova solicitação (“agora”, “outra coisa”, “além disso”, “também”) → `status=new_request_detected`, `confidence` máx 0.69, `response_hint` pede confirmação de novo pedido.

## Confidence Gate e Fallback
- Saída do LLM é limitada pelo precheck (`confidence <= 0.69` quando ambíguo).
- LLM inválido/erro → fallback seguro: `accepted=false`, `confidence=0.0`, `next_state=current_state`, `response_hint` pedindo confirmação objetiva.

## Integração no Pipeline
- `WhatsAppInboundPipeline` chama `select_next_state` antes de qualquer resposta.
- Se `accepted=true`, atualiza `session.current_state`; caso contrário, mantém estado e registra `response_hint` em `message_history`.
- `state_decision` é retornado no `ProcessedMessage` para consumo posterior (LLM #2 usará `response_hint` na Fase 2B).

## Próximos Passos (Fase 2B)
- Gerador de resposta usará `state_decision.response_hint` para solicitar confirmação quando `accepted=false`.
- Persistência/analytics podem registrar `state_decision` para auditoria.
