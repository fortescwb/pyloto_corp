# TODO List — Refatorar e Completar Módulos (Parte 2: Persistência, Sessão e Pipeline)

## ⚠️ IMPORTANTE: Fontes de Verdade

Todas as alterações neste documento devem estar **alinhadas com as fontes de verdade** do projeto:

- **[Funcionamento.md](Funcionamento.md)** — Especificações do produto, fluxos, outcomes e contrato de handoff
- **[README.md](README.md)** — Visão geral, status e documentação
- **[regras_e_padroes.md](regras_e_padroes.md)** — Padrões de código, segurança e organização

**Ao completar cada tarefa**, atualize os arquivos acima conforme necessário para refletir as mudanças implementadas.

---

## 3.2.4 Refatorar Exportação

### ✅ Extrair métodos de ExportConversationUseCase

**Status:** CONCLUÍDO (25/01/2026 15:20)

**Descrição:**
Dividir método `execute()` de 100+ linhas em sub-funções e classes auxiliares.

**Arquivo:**
`src/pyloto_corp/application/export.py`

**Implementação:**
- Método `execute()` refatorado para ~35 linhas (orquestração pura)
- Sub-métodos implementados:
  - `_collect_export_data()` — Coleta conversas, perfis, logs
  - `_render_export_text()` — Renderiza dados em texto
  - `_persist_export_and_audit()` — Persiste e registra auditoria
  - `_compile_export_result()` — Compila resultado final
  - `_get_messages()` — Recupera mensagens paginadas
  - `_render_messages()` — Renderiza mensagens com timezone
  - `_render_audit()` — Renderiza trilha de auditoria
  - `_render_profile()` — Renderiza perfil do usuário
  - `_build_header()` — Constrói cabeçalho do export
  - `_format_export_text()` — Formata partes em texto único
  - `_record_export_event()` — Registra evento de auditoria

**Critério de Aceitação:** ✅ ATENDIDO
- ✅ Método `execute()` com ~35 linhas (orquestração)
- ✅ Cada sub-método com responsabilidade única
- ✅ Testes expandidos para >90% cobertura
- ✅ Documentação de fluxo clara

**Testes Criados:**
- ✅ `tests/unit/test_export.py` — 15 testes unitários
- ✅ `tests/integration/test_export_integration.py` — 10 testes E2E

---

### ✅ Implementar HistoryExporterProtocol concreto

**Status:** CONCLUÍDO (25/01/2026 20:00)

**Implementação:**
- Arquivo: `src/pyloto_corp/infra/gcs_exporter.py` (290 linhas, expandido)
- Classe: `GCSHistoryExporter`
- Métodos:
  - `save(user_key, content, content_type) -> str` - Upload básico
  - `save_with_metadata(...) -> ExportMetadata` - Com URL assinada
  - `generate_signed_url(object_name, days) -> str` - URL assinada v4
  - `cleanup_old_exports(retention_days) -> int` - Remove antigos
- Funcionalidades:
  - Upload para bucket GCS com path organizado por data
  - Geração de URL assinada (v4) com expiração configurável
  - Persistência de metadados em Firestore (opcional)
  - Cleanup de exports antigos com retention policy
  - Limpeza de metadados do Firestore no cleanup
  - Factory: `create_gcs_exporter()`

**Dataclasses:**
- `ExportMetadata` - gcs_uri, signed_url, user_key, created_at, expires_at, size_bytes

**Testes:** `tests/unit/test_gcs_exporter.py` (320 linhas, 22 testes)
- Save básico e com metadados
- Geração de URL assinada (v4, GET, expiração)
- Cleanup (deleta antigos, mantém recentes)
- Cleanup de metadados Firestore
- Factory e edge cases (vazio, grande, Unicode)

---

## 3.2.5 Persistência e Stores

### ✅ Criar ConversationStore em Firestore

**Status:** CONCLUÍDO (25/01/2026 15:25)

**Descrição:**
Implementação concreta de `ConversationStore` usando Firestore.

**Arquivo:**
`src/pyloto_corp/infra/firestore_conversations.py`

**Implementação:**
- ✅ Classe `FirestoreConversationStore` implementada
- ✅ CRUD básico:
  - `append_message()` — Insere com idempotência (transacional)
  - `get_messages()` — Recupera com paginação por cursor
  - `get_header()` — Recupera cabeçalho da conversa
- ✅ Paginação com cursores funcionando
- ✅ Ordenação por timestamp (descendente)
- ✅ Transações Firestore garantindo atomicidade
- ✅ Soft delete via status (CLOSED)

**Schema Implementado:**
```
/conversations/{user_key}  <- header
  ├── channel: "whatsapp"
  ├── tenant_id: str | null
  ├── created_at: timestamp
  ├── updated_at: timestamp
  ├── last_message_at: timestamp

/conversations/{user_key}/messages/{provider_message_id}  <- mensagens
  ├── provider: "whatsapp"
  ├── direction: "in" | "out"
  ├── actor: "USER" | "PYLOTO" | "HUMAN"
  ├── timestamp: timestamp
  ├── text: str
  ├── intent: str | null
  ├── outcome: str | null
```

**Critério de Aceitação:** ✅ ATENDIDO
- ✅ Store implementado com CRUD completo
- ✅ Paginação com cursores funcionando
- ✅ Ordenação por timestamp
- ✅ Testes integração implementados (25 testes)
- ✅ Logs estruturados

**Testes Criados:**
- ✅ `tests/integration/test_firestore_conversations.py` — 25 testes
  - CRUD: `append_message()`, `get_messages()`, `get_header()`
  - Paginação com cursores
  - Edge cases (vazios, duplicatas, timeouts)

---

### ✅ Criar UserProfileStore em Firestore

**Status:** CONCLUÍDO (25/01/2026 18:30)

**Implementação:**
- Arquivo domínio: `src/pyloto_corp/domain/profile.py` (expandido para 110 linhas)
  - `UserProfile` com campos adicionais (city, is_business, lead_score, etc.)
  - `QualificationLevel` enum (COLD, WARM, HOT, QUALIFIED)
  - `ProfileUpdateEvent` dataclass para histórico
  - `UserProfileStore` protocol expandido

- Arquivo infra: `src/pyloto_corp/infra/firestore_profiles.py` (220 linhas)
- Classe: `FirestoreUserProfileStore`
- Métodos:
  - `get_profile(user_key) -> UserProfile | None`
  - `get_by_phone(phone_e164) -> UserProfile | None` (dedup)
  - `upsert_profile(profile) -> None`
  - `update_field(user_key, field, value, actor) -> bool` (com histórico)
  - `get_update_history(user_key, limit) -> list[ProfileUpdateEvent]`
  - `forget(user_key) -> bool` (LGPD)

**Schema Firestore:**
```
/user_profiles/{user_key}
  ├── phone_e164, display_name, city
  ├── is_business, business_name, role
  ├── lead_score, qualification_level
  ├── collected_fields (map)
  ├── created_at, updated_at, last_interaction
  └── /history/{event_id}
        ├── timestamp, field_changed
        ├── old_value, new_value (mascarados)
        └── actor
```

**Funcionalidades:**
- CRUD completo com validação
- Busca por phone (dedup de contatos)
- Histórico de atualizações em subcollection
- LGPD forget: remove perfil e histórico
- Mascaramento de PII em logs e histórico

**Testes:** `tests/integration/test_user_profile_store.py` (380 linhas, 25 testes)
- CRUD: get, upsert, get_by_phone
- Update com histórico
- LGPD forget
- Edge cases (negócios, lead_score, qualificação)

---

### ✅ Criar AuditLogStore em Firestore

**Status:** CONCLUÍDO (25/01/2026 17:12)

**Implementação:**
- Arquivo: `src/pyloto_corp/infra/firestore_audit.py` (220 linhas)
- Classe: `FirestoreAuditLogStore` (implementa `AuditLogStore`)
- Métodos:
  - `get_latest_event(user_key) -> AuditEvent | None`
  - `list_events(user_key, limit=500) -> list[AuditEvent]`
  - `append_event(event, expected_prev_hash) -> bool`
  
**Funcionalidades:**
- Append-only: eventos nunca modificados
- Encadeamento por hash: SHA256(canonical_json(event) + prev_hash)
- Transacional: Firestore transactions garantem atomicidade
- Concorrência: tolerante (retry no app layer via `RecordAuditEventUseCase`)
- Logging: estruturado sem PII

**Schema Firestore:**
```
/conversations/{user_key}/audit/{event_id}
├── event_id: str
├── user_key: str
├── tenant_id: str | None
├── timestamp: datetime
├── actor: str (SYSTEM | HUMAN)
├── action: str (USER_CONTACT | EXPORT_GENERATED | ...)
├── reason: str
├── prev_hash: str | None
├── hash: str (SHA256)
└── correlation_id: str | None
```

**Testes:** `tests/integration/test_firestore_audit.py` (280 linhas, 13 testes)
- Get latest event (existe, vazio, malformado)
- List events (ordenação, limite, malformados)
- Append com sucesso
- Append com conflito de cadeia (race condition)
- Integridade: hash muda se evento modificado
- Tampering detection via hash mismatch

---

### ☐ Criar AuditLogStore em Firestore (ADICIONAL)

**Arquivo:**
`src/pyloto_corp/infra/stores/audit_log_store.py`

**Responsabilidades:**

- Salvar evento de auditoria com hash encadeado
- Validar integridade da cadeia
- Recuperar trilha de auditoria de conversa
- Implementar append-only com concurrency control
- Gerar relatório de auditoria

**Schema:**

```schema sugerido
/audit_logs/{log_id}
  ├── timestamp: timestamp
  ├── conversation_id: str
  ├── event_type: str (USER_CONTACT, HANDOFF_HUMAN, etc.)
  ├── actor: str (system, user_id, or agent_id)
  ├── changes: map
  ├── previous_hash: str
  ├── current_hash: str
  ├── metadata: map
  └── signature: str (opcional, para validação externa)
```

**Critério de Aceitação:**

- Store implementado com append-only semantics
- Hash encadeado funcionando (SHA256)
- Validação de cadeia implementada
- Concurrency control (expected_prev_hash)
- Testes com Firestore emulador

**Notas de Implementação:**

- Hash anterior deve corresponder ao último log
- Falha se hash anterior inválido (concurrency)
- Eventos sem PII em plaintext
- PII criptografado se necessário guardar

---

### ☐ Implementar RedisDedupeStore

**Descrição:**
Implementação de store de deduplicação usando Redis com TTL e fail-closed.

**Arquivo:**
`src/pyloto_corp/infra/stores/dedupe_store.py`

**Responsabilidades:**

- Armazenar `dedupe_key` em Redis com TTL
- Verificar se chave já foi processada
- Implementar fail-closed (não processar se cache indisponível)
- Registrar hit/miss de dedup

**Interface:**

```python
class RedisDedupeStore(DedupeStoreProtocol):
    async def is_processed(self, dedupe_key: str) -> bool:
        """Verifica se já foi processado"""
        pass

    async def mark_as_processed(
        self,
        dedupe_key: str,
        ttl_seconds: int
    ) -> bool:
        """Marca como processado, com TTL"""
        pass
```

**Critério de Aceitação:**

- Store implementado com Redis
- TTL configurável (padrão: 3600 segundos)
- Fail-closed em produção (erros = não processar)
- Testes com Redis emulador (ou mock)
- Logs estruturados

**Notas de Implementação:**

- Dedupe_key: hash(message_id + timestamp)
- TTL padrão: 1 hora (cobrir webhook retries)
- Fail-closed: se Redis indisponível, erro 5xx
- Monitore hit rate para tuning de TTL

---

### ☐ Atualizar create_dedupe_store em api/app.py

**Descrição:**
Refatorar factory function para usar backend configurável (Redis ou Firestore).

**Arquivo:**
`src/pyloto_corp/api/app.py`

**Lógica:**

```python
def create_dedupe_store(settings: Settings) -> DedupeStoreProtocol:
    if settings.dedupe_backend == "redis":
        return RedisDedupeStore(settings.redis_url)
    elif settings.dedupe_backend == "firestore":
        return FirestoreDedupeStore()
    else:
        raise ValueError(f"Unknown dedupe backend: {settings.dedupe_backend}")
```

**Critério de Aceitação:**

- Factory implementado
- Backend configurável via `Settings.dedupe_backend`
- Testes de ambos backends
- Logs de inicialização

---

## 3.2.6 Sessão e Pipeline

### ☐ Implementar SessionStore em Firestore

**Descrição:**
Nova classe para persistir informações de sessão com timeouts e multi-intents.

**Arquivo:**
`src/pyloto_corp/application/session.py`

**Responsabilidades:**

- Salvar/recuperar sessão em Firestore
- Rastrear última interação, lista de intents, status
- Implementar timeouts (30 min de inatividade, 2h hard limit)
- Atualizar sessão sem expor PII
- Registrar encerramento de sessão

**Interface:**

```python
class SessionManager:
    async def get_or_create_session(
        self,
        user_id: str
    ) -> Session:
        """Recupera ou cria nova sessão"""
        pass

    async def add_intent(
        self,
        session_id: str,
        intent: Intent
    ) -> Session:
        """Adiciona intent à fila"""
        pass

    async def close_session(
        self,
        session_id: str,
        outcome: Outcome
    ) -> None:
        """Encerra sessão com outcome"""
        pass

    async def check_timeouts(self) -> int:
        """Valida timeouts e encerra expiradas"""
        pass
```

**Critério de Aceitação:**

- Store implementado com timeouts funcionando
- Testes com Firestore emulador
- Timeout de inatividade (30 min) implementado
- Hard limit de 2h implementado
- Logs de encerramento por timeout

**Notas de Implementação:**

- Schema: `/sessions/{session_id}`
- Timeout de inatividade: 30 minutos (Funcionamento.md)
- Hard limit: 2 horas
- Cloud Scheduler job para validar timeouts a cada 5 min
- Outcome ao timeout: `AWAITING_USER` → `SCHEDULED_FOLLOWUP`

---

### ☐ Completar application/pipeline.py

**Descrição:**
Implementar pipeline completo que orquestra session, intenção, orchestrador, e outbound.

**Arquivo:**
`src/pyloto_corp/application/pipeline.py`

**Responsabilidades:**

- Recuperar sessão existente ou criar nova
- Recuperar lista de intents e ativar próxima
- Chamar `AIOrchestrator` com mensagem normalizada
- Decidir outcome (resposta automática vs handoff)
- Chamar `WhatsAppOutboundClient` para resposta
- Registrar eventos de auditoria

**Fluxo:**

1. Receber webhook (inbound normalizado)
2. `SessionManager.get_or_create_session(user_id)`
3. `IntentQueue.add_intent(intent)`
4. Ativar intent ativo
5. `AIOrchestrator.classify(message, context)`
6. Decidir: HANDOFF_HUMAN vs SELF_SERVE_INFO vs outro outcome
7. Se SELF_SERVE_INFO: `WhatsAppOutboundClient.send_response(...)`
8. `AuditLogStore.record_event(...)`
9. `SessionManager.update_session(...)`

**Critério de Aceitação:**

- Pipeline implementado com fluxo completo
- Testes com mocks de dependências
- Auditoria registrada em cada passo
- Logs estruturados de decisão
- Tratamento de erros em cascata

**Notas de Implementação:**

- Respeitar regra de 3 intents por sessão (Funcionamento.md)
- Validar contexto antes de chamar IA
- Tratar falhas do IA com fallback (regras determinísticas)
- Logs sem expor PII de usuário

---

### ☐ Refatorar processo_whatsapp_webhook

**Descrição:**
Integrar pipeline completo ao endpoint de webhook.

**Arquivo:**
`src/pyloto_corp/api/routes.py` (ou similar)

**Endpoint:**

```python
@app.post("/webhooks/whatsapp")
async def process_whatsapp_webhook(
    request: Request,
    settings: Settings
) -> JSONResponse:
    """
    Processa webhook do WhatsApp:
    1. Verifica assinatura
    2. Deduplica mensagem
    3. Normaliza
    4. Executa pipeline
    5. Retorna 200 imediatamente
    """
    pass
```

**Critério de Aceitação:**

- Endpoint integrado com pipeline
- Assinatura verificada (zero_trust_mode)
- Deduplicação funcionando
- Pipeline executado (pode ser assíncrono)
- Retorna 200 imediatamente (não aguarda processamento)

**Notas de Implementação:**

- Usar Pub/Sub ou Cloud Tasks para async (opcional)
- Retornar 200 OK imediatamente ao Meta
- Processar em background job
- Logs com correlation_id

---

## 3.2.7 IA e Orquestração

### ☐ Definir prompts base para AIOrchestrator

**Descrição:**
Criar conjunto de prompts e knowledge base para classificação de intenção.

**Arquivo:**
`src/pyloto_corp/ai/prompts.py`

**Prompts:**

- `CLASSIFY_INTENT_SYSTEM` — System prompt para classificação
- `CLASSIFY_INTENT_USER` — Template de user message
- `EXTRACT_ENTITIES` — Prompt para extração de entidades
- `GENERATE_RESPONSE` — Prompt para gerar resposta

**Critério de Aceitação:**

- Prompts criados em português
- Documentação de contexto (intents, outcomes, fluxos)
- Estrutura com variáveis (não hardcoded)
- Versionamento de prompts (para A/B testing)

**Notas de Implementação:**

- Baseado em `Funcionamento.md` (vertentes, fluxos)
- Incluir few-shots para main flows
- Considerar temperature e stop_words
- Documentar em `docs/ai/prompts.md`

---

### ☐ Implementar AIOrchestrator completo

**Descrição:**
Classe que orquestra classificação via LLM com fallback a regras determinísticas.

**Arquivo:**
`src/pyloto_corp/ai/orchestrator.py`

**Responsabilidades:**

- Receber mensagem normalizada + contexto
- Chamar LLM com prompt (local ou via API)
- Parsear resposta em `AIResponse` (intent, outcome, reply_text)
- Fallback a regras determinísticas se confiança baixa
- Registrar classificação para feedback futuro

**Interface:**

```python
class AIOrchestrator:
    async def classify(
        self,
        message: NormalizedMessage,
        context: SessionContext
    ) -> AIResponse:
        """Classifica intenção e outcome"""
        pass
```

**Critério de Aceitação:**

- Classe implementada com LLM integration
- Fallback a regras funcional
- Testes com mensagens reais (dataset)
- Accuracy de classificação documentada
- Logs estruturados

**Notas de Implementação:**

- Usar OpenAI API ou modelo local (ex.: llama2)
- Timeout: 5 segundos
- Retry com backoff se falha
- Cache de classificações (por message content)
- Feedback loop para melhoria contínua

---

### ☐ Implementar lead scoring (opcional)

**Descrição:**
Mecanismo para qualificar leads conforme campos de `LeadProfile` (Funcionamento.md).

**Critério de Aceitação:**

- Score calculado baseado em critérios documentados
- Qualificação (low, medium, high) atribuída
- Testes com casos típicos
- Documentação em `docs/lead-scoring.md`

---

## Checklist Final

- [ ] Métodos em export.py extraídos e refatorados
- [ ] HistoryExporterProtocol implementado com GCS
- [ ] ConversationStore criado com paginação
- [ ] UserProfileStore criado com dedup de phone
- [ ] AuditLogStore criado com trilha encadeada
- [ ] RedisDedupeStore implementado com fail-closed
- [ ] create_dedupe_store refatorado
- [ ] SessionManager implementado com timeouts
- [ ] application/pipeline.py completo
- [ ] Webhook refatorado com pipeline integrado
- [ ] Prompts base definidos
- [ ] AIOrchestrator implementado
- [ ] Lead scoring implementado (opcional)
- [ ] Testes de integração completos
- [ ] [Funcionamento.md](Funcionamento.md) atualizado se houver mudanças de fluxo
- [ ] [README.md](README.md) atualizado com novo pipeline

---

**Status:** ⏳ Não iniciado | 🚀 Em andamento | ✅ Completo
