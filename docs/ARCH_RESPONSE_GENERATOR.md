## Response Generator (Fase 2B)

Fluxo: state selector → response generator → (futuro) message type selector.

### Inputs
- `last_user_message`, `day_history`
- `state_decision` (StateSelectorOutput)
- `current_state`, `candidate_next_state`, `confidence`, `response_hint`

### Comportamento
- Se `confidence < threshold` ou `state_decision` não aceito: prioriza perguntas de confirmação/checklist usando `response_hint`.
- Se aceito: respostas diretas para avançar de estado.
- Sempre retorna ≥3 respostas, `response_style_tags`, `chosen_index`, `safety_notes`.

### Fallback
- Em erro/timeout do LLM, produz 3 respostas determinísticas e seguras (sem PII), escolhendo index 0.

### Integração
- Pipeline já executa state selector; em seguida chama response generator e anexa em `ProcessedMessage.response_options`. Não envia outbound ainda.

### Segurança
- Nada de PII, tom institucional Pyloto, logs estruturados (`correlation_id`, estado, confiança, had_hint).
