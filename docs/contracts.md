# Contratos de domínio (pyloto_corp)

## Outcomes terminais (canônicos)
- HANDOFF_HUMAN
- SELF_SERVE_INFO
- ROUTE_EXTERNAL
- SCHEDULED_FOLLOWUP
- AWAITING_USER
- DUPLICATE_OR_SPAM
- UNSUPPORTED
- FAILED_INTERNAL

## Intents (alto nível)
- ENTRY_UNKNOWN
- CUSTOM_SOFTWARE
- SAAS_COMMUNICATION
- PYLOTO_ENTREGA_REQUEST
- PYLOTO_ENTREGA_DRIVER_SIGNUP
- PYLOTO_ENTREGA_MERCHANT_SIGNUP
- INSTITUTIONAL
- UNSUPPORTED

## LeadProfile
Campos esperados:
- name
- phone
- city
- is_business
- business_name
- role

## ConversationHandoff
Campos esperados:
- intent_primary
- intents_detected[]
- resolved_intents[]
- open_intents[]
- summary
- requirements
- deadline
- routing
- confidence
- qualification_level (low|medium|high)
- qualification_reasons[]

## Regras essenciais
- Uma sessão deve terminar com exatamente 1 outcome terminal.
- Até 3 intenções por sessão, apenas 1 ativa por vez.
- Contexto detalhado apenas para a intenção ativa.

## Conversation History (armazenamento)
### user_key
- user_key = base64url(HMAC_SHA256(PEPPER_SECRET, phone_e164)) sem padding.
- Nunca armazenar phone_e164 no documento.

### Firestore (fonte de verdade)
- Coleção: `conversations/{user_key}`
- Subcoleção: `messages/{provider_message_id}`
- tenant_id fica no documento do header (campo opcional).

### Idempotência
- Inserção via `create()` em `messages/{provider_message_id}`.
- Se já existir, retornar sucesso sem duplicar.
- Header atualiza `updated_at` e `last_message_at` em transação.

### Sanitização
- `text_max_len = 4000`
- Normalizar whitespace e truncar com marcador `…[truncated]`.
- Não armazenar anexos nem payload bruto (usar `payload_ref` quando necessário).

## Auditoria (append-only)
- Coleção: `conversations/{user_key}/audit/{event_id}`
- Campos: `event_id`, `user_key`, `tenant_id?`, `timestamp`, `actor`, `action`, `reason`, `prev_hash`, `hash`, `correlation_id?`
- Integridade: `hash = SHA256(canonical_json(event_sem_hash) + prev_hash)`
- Conflitos: append condicional com `expected_prev_hash`; retries curtos.
- Ações previstas: `USER_CONTACT`, `EXPORT_GENERATED`, `PROFILE_UPDATED`, `NOTE_ADDED`.

## Export forense/jurídico
- Gerado via `ExportConversationUseCase`.
- Inclui: cabeçalho, dados coletados, mensagens (ordenadas), trilha de auditoria.
- Formatos: TXT/MD; data em America/Sao_Paulo.
- PII (telefone) só aparece se `include_pii=true`.
- Persistência: `gs://<EXPORT_BUCKET>/exports/conversations/<user_key>/<timestamp>_history.txt` com versionamento.
