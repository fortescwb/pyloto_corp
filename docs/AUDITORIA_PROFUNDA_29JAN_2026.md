# AUDITORIA PROFUNDA — pyloto_corp (29 JAN 2026)

**Status:** ✅ Relatório READ-ONLY | **Auditor:** Modo Auditoria Global  
**Data:** 29 de janeiro de 2026 | **Escopo:** Legado vs Essencial + Reorganização Modular  
**Bases:** regras_e_padroes.md, Funcionamento.md, README.md + Análise de Código

---

## 1. ESCOPO AUDITADO

Auditoria completa do repositório **`pyloto_corp`** — serviço FastAPI de atendimento inicial via WhatsApp.

**O que foi analisado:**
- ✅ Fontes normativas (3 documentos raízes)
- ✅ Fluxo real de código (entrypoint → pipeline → LLMs → outbound)
- ✅ Mapeamento de dependências e acoplamentos
- ✅ Inventário de "legado" vs "essencial"
- ✅ Boundaries arquiteturais (domain/application/adapters/infra)
- ✅ Robustez, escala, idempotência, proteção contra abuso
- ✅ Logs estruturados e proteção de PII

**O que NÃO foi alterado:** Nenhuma linha de código foi modificada (auditoria read-only).

---

## 2. MAPA DO FLUXO REAL (Ponta-a-Ponta)

### 2.1 Sequência Completa de Execução

```
┌─────────────────────────────────────────────────────────────┐
│ 1. WEBHOOK INBOUND (HTTP POST)                              │
│    Route: POST /webhooks/whatsapp                           │
│    Handler: api/routes.py::whatsapp_webhook()               │
│    ✅ Valida assinatura Meta (signature.py::verify)         │
│    ✅ Extrai payload JSON                                   │
│    ✅ Gera correlation_id (middleware.py)                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. ENFILEIRAMENTO (Cloud Tasks ou Mock)                     │
│    Função: routes.py::whatsapp_webhook()                    │
│    Dispatcher: CloudTasksDispatcher                         │
│    Queue: inbound_task_queue                                │
│    ✅ Idempotência da fila: inbound_event_id (webhook hash) │
│    ✅ Retorna 202 Accepted imediatamente                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. PROCESSAMENTO ASSÍNCRONO (Worker Task)                   │
│    Route: POST /tasks/whatsapp/inbound                      │
│    Handler: routes.py::handle_inbound_task()                │
│    Token: internal_task_token (validado)                    │
│    ✅ Desserializa payload                                  │
│    ✅ Chama: application/whatsapp_async.py::handle_..()     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. EXTRAÇÃO DE MENSAGENS (normalização)                     │
│    Função: adapters/whatsapp/normalizer.py::extract_msgs() │
│    DTOs: NormalizedWhatsAppMessage (domain/model)           │
│    Tipos suportados: text, image, video, audio, location,   │
│                     contacts, address, interactive, etc.    │
│    ✅ Sem PII em logs                                       │
│    ✅ Sanitiza URLs sensíveis                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. DEDUPLICAÇÃO (Inbound)                                   │
│    Store: infra/dedupe.py (Redis/Firestore/Memory)          │
│    Chave: message_id ou hash(correlationId + timestamp)     │
│    ✅ Set-if-not-exists atômico                             │
│    ✅ TTL 7 dias                                            │
│    ✅ Fail-closed em erro                                   │
│    Outcome se duplo: DUPLICATE_OR_SPAM                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. DETECÇÃO DE ABUSO                                        │
│    Camada 1: FloodDetector (domain/abuse_detection.py)      │
│      - Threshold: 10 msg / 60s                              │
│      - Backend: Memory (dev) ou Redis (prod)                │
│    Camada 2: SpamDetector (regras heurísticas)              │
│      - Conteúdo vazio, repetido, padrões suspeitos          │
│    Camada 3: AbuseChecker (limite de intenções)             │
│      - Max 3 intenções por sessão                           │
│    Outcome se abuso: DUPLICATE_OR_SPAM ou SCHEDULED_FOLLOWUP│
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 7. GESTÃO DE SESSÃO                                         │
│    Store: infra/session_store_firestore.py (Firebase)       │
│    Recuperação ou criação: SessionState                     │
│    Campos: session_id, current_state, intent_queue,         │
│             outcome, history, timestamps                    │
│    ✅ TTL 2 horas (AWAITING_USER)                           │
│    ✅ Atomic writes via Firestore transactions              │
│    ✅ Async-first (anyio.to_thread)                         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 8. ORQUESTRAÇÃO DE IA                                       │
│    Handler: application/pipeline.py::WhatsAppInboundPipeline│
│    Sequência:                                               │
│                                                              │
│    ┌─────────────────────────────────────┐                 │
│    │ LLM #1: Seletor de Estado            │                 │
│    │ (state_selector.py)                  │                 │
│    │                                      │                 │
│    │ Input:  current_state,               │                 │
│    │         possible_next_states,        │                 │
│    │         message_text,                │                 │
│    │         history_summary              │                 │
│    │                                      │                 │
│    │ Output: StateSelectorOutput          │                 │
│    │         ├─ selected_state            │                 │
│    │         ├─ confidence [0..1]         │                 │
│    │         ├─ status (done/in_progress) │                 │
│    │         ├─ response_hint              │                 │
│    │         └─ open_items/fulfilled      │                 │
│    │                                      │                 │
│    │ ⏱️ Timeout: 10s                       │                 │
│    │ Fallback: determinístico (heurístico)│                 │
│    └─────────────────────────────────────┘                 │
│                    ↓                                         │
│    ┌─────────────────────────────────────┐                 │
│    │ LLM #2: Gerador de Respostas         │                 │
│    │ (response_generator.py)              │                 │
│    │                                      │                 │
│    │ Input:  current_state,               │                 │
│    │         next_state (candidato),      │                 │
│    │         response_hint (de LLM#1),    │                 │
│    │         last_user_message,           │                 │
│    │         history_summary              │                 │
│    │                                      │                 │
│    │ Output: ResponseGeneratorOutput      │                 │
│    │         ├─ responses: list[str] x3+  │                 │
│    │         ├─ chosen_index              │                 │
│    │         └─ safety_notes              │                 │
│    │                                      │                 │
│    │ ⏱️ Timeout: 10s                       │                 │
│    │ Fallback: sempre ≥3 opções           │                 │
│    └─────────────────────────────────────┘                 │
│                    ↓                                         │
│    ┌─────────────────────────────────────┐                 │
│    │ LLM #3: Decisor Mestre               │                 │
│    │ (master_decider.py)                  │                 │
│    │                                      │                 │
│    │ Input:  state_decision (LLM#1),      │                 │
│    │         response_options (LLM#2),    │                 │
│    │         message_type,                │                 │
│    │         confidence (consolidada)     │                 │
│    │                                      │                 │
│    │ Output: MasterDecisionOutput         │                 │
│    │         ├─ final_state               │                 │
│    │         ├─ apply_state: bool         │                 │
│    │         ├─ selected_response_text    │                 │
│    │         ├─ message_type              │                 │
│    │         └─ reason (auditável)        │                 │
│    │                                      │                 │
│    │ ⏱️ Timeout: 10s                       │                 │
│    │ Fallback: regras determinísticas     │                 │
│    └─────────────────────────────────────┘                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 9. PERSISTÊNCIA DE SESSÃO E AUDITORIA                       │
│    Ação: session_store.save(session)                        │
│    Logs: Estruturados JSON (correlation_id, decisão)        │
│    Outcome: Atualizado com o estado final                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 10. CONSTRUÇÃO E ENVIO OUTBOUND                             │
│    Verificação: Outcome é terminal? Enviar resposta?        │
│    Se sim:                                                  │
│    ├─ Construir payload (payload_builders/)                 │
│    ├─ Validar (WhatsAppMessageValidator)                    │
│    ├─ Gerar idempotency_key (dedup outbound)                │
│    ├─ Chamar Graph API via HTTP client                      │
│    ├─ Marcar como enviado (outbound_dedupe_store)           │
│    ├─ Retry com backoff exponencial se erro                 │
│    └─ Log de resultado (sem PII)                            │
│                                                              │
│    Routes: routes.py::handle_outbound_task()                │
│    Client: adapters/whatsapp/outbound.py::WhatsApp...       │
│    Backend: infra/http.py::HttpClient (async)               │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Mapa de Responsabilidades por Camada

| Camada | Módulo | Responsabilidade |
|--------|--------|-----------------|
| **API** | `routes.py` | Rotas HTTP, validação de assinatura, enfileiramento |
| **API** | `dependencies.py` | Injeção de dependência, factories |
| **Adapters** | `normalizer.py` | Extração/normalização de payload (306 linhas) |
| **Adapters** | `outbound.py` | Cliente de envio, validação de payload |
| **Adapters** | `payload_builders/` | Construção de payloads por tipo |
| **Adapters** | `validators/` | Validação de mensagens |
| **Domain** | `enums.py` | Outcome, Intent, MessageType (tipos) |
| **Domain** | `conversation_state.py` | Contratos de LLM (StateSelectorInput/Output) |
| **Domain** | `abuse_detection.py` | Detecção de flood/spam (260 linhas) |
| **Domain** | `whatsapp_message_types.py` | DTOs de tipos de mensagem (239 linhas) |
| **Application** | `pipeline.py` | Orquestração completa inbound (463 linhas) |
| **Application** | `state_selector.py` | Chamada ao LLM #1 + fallback |
| **Application** | `response_generator.py` | Chamada ao LLM #2 + fallback |
| **Application** | `master_decider.py` | Chamada ao LLM #3 + fallback |
| **Application** | `session.py` | Model SessionState (dataclass) |
| **Application** | `whatsapp_async.py` | Helpers de fila + outbound (219 linhas) |
| **Infra** | `session_store_firestore.py` | Persistência de sessão (Firebase) |
| **Infra** | `session_store_redis.py` | Alternativa Redis |
| **Infra** | `dedupe.py` | Deduplicação inbound (386 linhas) |
| **Infra** | `outbound_dedup_factory.py` | Factory para dedup outbound |
| **Infra** | `secrets.py` | Acesso a segredos (268 linhas) |
| **Infra** | `http.py` | Cliente HTTP com retry/backoff |
| **Infra** | `cloud_tasks.py` | Dispatcher para Cloud Tasks |
| **AI** | `orchestrator.py` | IntentClassifier + OutcomeDecider (271 linhas) |
| **Observability** | `logging.py` | JSON estruturado, correlation_id |
| **Observability** | `middleware.py` | Middleware de correlation_id |

---

## 3. LEGADO IDENTIFICADO

### 3.1 Classificação Operacional

**Legado = módulo que:**
1. ✗ Não é mais referenciado (dead code)
2. ✗ Foi substituído por implementação mais nova
3. ✗ Existe apenas para compatibilidade histórica
4. ✗ Viola boundaries (domínio em infra, etc.)
5. ✗ É fallback antigo conflitante com o fluxo LLM

### 3.2 Legado Encontrado

#### **❌ outbound_dedupe.DEPRECATED** (MARCADO EXPLICITAMENTE)

- **Path:** `infra/outbound_dedupe.DEPRECATED`
- **Razão:** Refatorado em 25/01/2026 para cumprir limite de 200 linhas
- **Divisão:**
  - `domain/outbound_dedup.py` — Protocolo
  - `infra/outbound_dedup_*.py` — Implementações (memory, redis, firestore)
  - `infra/outbound_dedup_factory.py` — Factory
- **Status atual:** ✅ Novo código em lugar, sem importações ao .DEPRECATED
- **Ação:** Remover arquivo (seguro)

#### **⚠️ outbound.py.bak** (BACKUP HISTÓRICO)

- **Path:** `adapters/whatsapp/outbound.py.bak`
- **Razão:** Backup antes de refatoração
- **Uso:** Nenhum
- **Ação:** Remover (seguro)

#### **✓ Classificadores Determinísticos (NÃO LEGADO)**

- **Path:** `ai/orchestrator.py::IntentClassifier`, `OutcomeDecider`
- **Aparência legada:** Usa regras fixas (palavras-chave), não LLM
- **Realidade:** **Ainda é necessário** — o pipeline depende
  - `pipeline.py:221` chama `orchestrator.classify_intent(message, session)`
  - Preenche `intent_queue` usado por state_selector
  - Determina outcome inicial antes de LLMs
- **Risco de remoção:** Pipeline falharia
- **Status:** ✅ Essencial até que LLM substitua (ver recomendação P0)
- **Ação:** Manter, documentar como "será removido em v2.0"

---

## 4. ESTRUTURA ATUAL ESSENCIAL

### 4.1 Módulos Críticos ao Fluxo

| Camada | Módulo | Responsabilidade | Criticalidade | Dependências |
|--------|--------|-----------------|---------------|--------------|
| **API** | `routes.py` | Webhook + enfileiramento | 🔴 CRÍTICA | dedupe, tasks |
| **API** | `dependencies.py` | DI + factories | 🔴 CRÍTICA | config, infra |
| **Adapters** | `normalizer.py` | Extração de mensagens | 🔴 CRÍTICA | domínio |
| **Adapters** | `outbound.py` | Cliente Graph API | 🔴 CRÍTICA | validators |
| **Domain** | `enums.py` | Tipos de outcome/intent | 🟠 ALTA | nenhuma |
| **Domain** | `conversation_state.py` | Contratos LLM | 🟠 ALTA | nenhuma |
| **Domain** | `abuse_detection.py` | Flood/spam | 🟠 ALTA | nenhuma |
| **Domain** | `whatsapp_message_types.py` | DTOs de tipos | 🟠 ALTA | nenhuma |
| **Application** | `pipeline.py` | Orquestração | 🔴 CRÍTICA | orchestrator, state_selector, response_generator, master_decider |
| **Application** | `state_selector.py` | LLM #1 | 🟠 ALTA | orchestrator (fallback) |
| **Application** | `response_generator.py` | LLM #2 | 🟠 ALTA | fallback determinístico |
| **Application** | `master_decider.py` | LLM #3 | 🟠 ALTA | fallback determinístico |
| **Application** | `session.py` | SessionState | 🟠 ALTA | domain models |
| **Application** | `whatsapp_async.py` | Fila + outbound | 🔴 CRÍTICA | outbound, dedupe |
| **Infra** | `session_store_firestore.py` | Persistência | 🔴 CRÍTICA | session.py |
| **Infra** | `dedupe.py` | Dedup inbound | 🔴 CRÍTICA | nenhuma (abstração) |
| **Infra** | `secrets.py` | Config segredos | 🔴 CRÍTICA | config |
| **Infra** | `http.py` | HTTP + retry | 🟠 ALTA | outbound |
| **Infra** | `cloud_tasks.py` | Dispatcher | 🟠 ALTA | config |
| **AI** | `orchestrator.py` | Intent + outcome | 🟠 ALTA | domain enums |
| **Observability** | `logging.py` | JSON logs | 🟠 ALTA | nenhuma |

### 4.2 Dependências Críticas (Fluxo Essencial)

```
webhook (routes.py)
    ↓
extract_messages (normalizer.py) ← domain enums
    ↓
dedupe (infra/dedupe.py)
    ↓
get_or_create_session (infra/session_store.py)
    ↓
orchestrator.classify (ai/orchestrator.py) ← domain/enums.py
    ↓
pipeline._orchestrate_and_save()
    ├─ state_selector (LLM #1)
    ├─ response_generator (LLM #2)
    └─ master_decider (LLM #3)
        ↓
    outbound_client.send_message()
        ↓
    outbound_dedupe (infra/outbound_dedup_*.py)
        ↓
    http_client (infra/http.py)
        ↓
    Meta Graph API
```

---

## 5. ACHADOS POR SEVERIDADE

### 5.1 🔴 CRÍTICO

#### **1. Acoplamento: Application Importa Direto de Infra**

- **Violação:** `application/pipeline.py`, `whatsapp_async.py` importam `infra/dedupe.py`, `infra/session_store.py`
- **Impacto:** Application não é "orquestração pura"; contém conhecimento de persistência
- **Evidência:**
  ```python
  # application/pipeline.py:25
  from pyloto_corp.infra.dedupe import DedupeStore
  from pyloto_corp.infra.session_store import SessionStore
  
  # application/pipeline.py:102
  self._dedupe = dedupe_store
  self._sessions = session_store
  ```
- **Risco:** Mudança em estratégia de dedupe/session força redesign de pipeline
- **Recomendação:** ✅ Use protocolos abstratos (já parcialmente feito via `DedupeStore` ABC)

#### **2. 3 Pipelines Duplicados: 1243 Linhas de Código Paralelo**

- **Arquivos:**
  - `application/pipeline.py` — 463 linhas (fluxo síncrono + 3 LLMs)
  - `application/pipeline_v2.py` — 391 linhas (alternativa com 3 pontos LLM)
  - `application/pipeline_async.py` — 389 linhas (versão assíncrona)
- **Problema:** Três implementações não sincronizadas
  - Mudança em dedupe afeta **3 arquivos**
  - Mudança em abuse detection afeta **3 arquivos**
  - Mudança em contrato de session afeta **3 arquivos**
- **Impacto:** Inconsistência, custo de manutenção 3x
- **Recomendação:** P0 — Consolidar em 1 pipeline.py com suporte a sync/async/fallback

#### **3. Constructor de Pipeline com 18 Parâmetros**

- **Arquivo:** `application/pipeline.py:90–120`
- **Problema:**
  ```python
  def __init__(
      self,
      dedupe_store,              # 1
      session_store,             # 2
      orchestrator,              # 3
      flood_detector,            # 4
      state_selector_client,     # 5
      state_selector_model,      # 6
      state_selector_threshold,  # 7
      state_selector_enabled,    # 8
      response_generator_client, # 9
      # ... (10–18 mais parâmetros)
  )
  ```
- **Impacto:** Quebra a regra de máx. 50 linhas (construtor tem 30 linhas); frágil a mudanças
- **Recomendação:** P1 — Usar `dataclass PipelineConfig` com 1 parâmetro

---

### 5.2 🟠 ALTO

#### **1. Normalizer.py Excede 200 Linhas (306 linhas)**

- **Path:** `adapters/whatsapp/normalizer.py`
- **Violação:** Regra 2.1 (máx. 200 linhas)
- **Problema:** Mistura 3 responsabilidades
  1. Extração de conteúdo (linhas 1–100)
  2. Normalização (linhas 101–250)
  3. Sanitização de PII (linhas 251–306)
- **Impacto:** Difícil testar partes isoladamente
- **Recomendação:** P2 — Splittar em:
  - `normalizer.py` — Extração
  - `normalizer_sanitizer.py` — Sanitização
  - Funções <50 linhas

#### **2. Dedupe.py Excede 200 Linhas (386 linhas)**

- **Path:** `infra/dedupe.py`
- **Violação:** Regra 2.1 (máx. 200 linhas)
- **Problema:** Contém 3 classes + contrato + factory
  - `DedupeStore` (abstrato)
  - `InMemoryDedupeStore`
  - `RedisDedupeStore`
  - Factory (20 linhas)
- **Impacto:** Arquivo monolítico, difícil de manter
- **Recomendação:** P2 — Já existe refatoração parcial:
  - Mover `RedisDedupeStore` → `dedupe_redis.py`
  - Mover factory → `dedupe_factory.py`
  - Manter protocolo em `dedupe.py`

#### **3. Secrets.py Excede 200 Linhas (268 linhas)**

- **Path:** `infra/secrets.py`
- **Violação:** Regra 2.1
- **Problema:** Contém protocolos + 2 implementações
  - `SecretProvider` (abstrato)
  - `EnvSecretProvider`
  - `SecretManagerProvider` (GCP)
- **Recomendação:** P2 — Split:
  - `secrets.py` — Protocolo
  - `secrets_env.py` — Env provider
  - `secrets_gcp.py` — GCP provider

#### **4. WhatsAppMessageTypes.py Excede 200 Linhas (239 linhas)**

- **Path:** `domain/whatsapp_message_types.py`
- **Violação:** Regra 2.1 (19% acima do limite)
- **Problema:** 15+ tipos em 1 arquivo (verboso mas necessário)
- **Impacto:** Baixo (crescimento inevitável); justificável via comentário
- **Recomendação:** P3 — Monitore; se crescer >250, extraia tipos genéricos

#### **5. Sem Protocolo Genérico para Dedupe**

- **Problema:** `DedupeStore` (inbound) vs `OutboundDedupeStore` (outbound)
  - Mesma semântica, interfaces diferentes
  - Duplicação de implementações (memory, redis, firestore)
- **Impacto:** Mudança de estratégia (ex.: TTL) afeta 2 protocolos
- **Recomendação:** P2 — Criar `DedupeProtocol` genérico:
  ```python
  class DedupeStore(ABC):
      def mark_if_new(self, key: str, ttl_seconds: int | None = None) -> bool: ...
  ```

---

### 5.3 🟡 MÉDIO

#### **1. Application com Lógica de Persistência**

- **Problema:** `pipeline.py`, `whatsapp_async.py` contêm lógica de session.save() e dedupe.mark_if_new()
- **Impacto:** Mistura orquestração com IO
- **Recomendação:** P1 — Criar `SessionManager` e `DedupeManager` em `application/` que encapsule IO

#### **2. PII em Adapters Outbound**

- **Path:** `adapters/whatsapp/outbound.py:61`
- **Problema:**
  ```python
  class WhatsAppOutboundClient:
      def __init__(self, phone_number_id: str):
          self.phone_number_id = phone_number_id  # ⚠️ Pode vazar em __dict__
  ```
- **Risco:** Se excepthook() logar `__dict__`, expõe telefone
- **Recomendação:** P2 — Adicionar `__repr__()` seguro:
  ```python
  def __repr__(self) -> str:
      return f"WhatsAppOutboundClient(phone_number_id=***)"
  ```

#### **3. Acoplamento via Múltiplos Imports de Config**

- **Problema:** 5+ lugares importam `config/settings.py`
- **Impacto:** Difícil testar com config alternativa
- **Recomendação:** P3 — Usar `Depends(get_settings)` consistentemente (FastAPI patterns)

---

### 5.4 🟢 BAIXO

#### **1. Fallback Determinístico em LLMs Não Testado**

- **Paths:** `state_selector.py::_deterministic_precheck()`, `response_generator.py::_deterministic_fallback()`, `master_decider.py::_deterministic_rules()`
- **Problema:** Fallback lógico sem testes específicos de timeout
- **Recomendação:** P3 — Adicionar testes com mock de timeout LLM

#### **2. Correlação ID Não Propagado para Outbound**

- **Problema:** `correlation_id` é criado no webhook, mas não propagado ao outbound task
- **Impacto:** Traçabilidade quebrada entre inbound e outbound
- **Recomendação:** P3 — Adicionar `correlation_id` a `OutboundMessageRequest`

---

## 6. GAPS vs FLUXO ESPERADO

### 6.1 Fluxo Esperado (de Funcionamento.md + prompt)

```
1. Recebe mensagem Graph API ✅
2. Cria histórico rastreável ✅
3. Determina estado inicial ✅ (orchestrator)
4. LLM de estado recebe histórico, escolhe próximo estado ✅
5. LLM de resposta gera resposta (menciona "Otto" na primeira do dia) ⚠️ PARCIAL
6. LLM final confirma coerência, decide tipo de mensagem ✅
7. Aplica estado e envia resposta ✅
8. Suporta centenas de mensagens simultâneas ✅
```

### 6.2 Gaps Identificados

#### **⚠️ 5. LLM de Resposta não implementa "Otto" explicitamente**

- **Problema:** `response_generator.py` não tem lógica específica de "primeira mensagem do dia"
- **Status:** Delegado ao LLM (prompt); sem validação no código
- **Impacto:** Se LLM falhar, fallback pode não mencionar Otto
- **Recomendação:** P1 — Adicionar `_is_first_message_of_day()` helper e garantir fallback com "Otto"

#### **✅ Todos os demais pontos estão cobertos**

---

## 7. PLANO DE REORGANIZAÇÃO MODULAR

### 7.1 Target Architecture (Proposta)

```
src/pyloto_corp/
├── api/                    # HTTP entry points (não contém lógica)
│   ├── __init__.py
│   ├── app.py             # FastAPI factory
│   ├── routes.py          # GET /health, POST /webhooks/whatsapp
│   ├── routes_async.py    # POST /tasks/whatsapp/{inbound|outbound}
│   ├── dependencies.py    # DI + factories
│   └── error_handlers.py  # (novo) Tratamento de erros HTTP
│
├── application/           # Use-cases e orquestração
│   ├── __init__.py
│   ├── pipeline.py        # Consolidado (async-first, sync wrapper)
│   ├── pipeline_config.py # (novo) PipelineConfig dataclass
│   ├── session.py         # SessionState
│   ├── session_manager.py # (novo) Abstração de session store
│   ├── dedupe_manager.py  # (novo) Abstração de dedupe store
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── state_selector.py
│   │   ├── response_generator.py
│   │   ├── master_decider.py
│   │   └── fallback.py    # (novo) Helpers de fallback compartilhado
│   └── outbound_orchestrator.py # (novo) Encapsula envio outbound
│
├── domain/                # Regras de negócio (sem IO, sem infra)
│   ├── __init__.py
│   ├── enums.py
│   ├── conversation_state.py
│   ├── abuse_detection.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── message_types.py     # (refatorado de whatsapp_message_types.py)
│   │   ├── session.py           # (novo) Modelos de domínio (sem Pydantic)
│   │   └── outcome.py           # (novo) Outcome + validação
│   └── protocols/               # (novo) Contratos abstratos
│       ├── __init__.py
│       ├── dedupe.py           # DedupeStore genérico
│       ├── session.py          # SessionStore genérico
│       └── secret_provider.py  # SecretProvider
│
├── adapters/              # Conversão ext <-> int (sem lógica de domínio)
│   ├── __init__.py
│   └── whatsapp/
│       ├── __init__.py
│       ├── models.py          # NormalizedWhatsAppMessage
│       ├── normalizer/        # (novo) Extração de payload
│       │   ├── __init__.py
│       │   ├── extractor.py   # Extração de conteúdo
│       │   └── sanitizer.py   # Sanitização de PII
│       ├── outbound/          # (novo) Envio
│       │   ├── __init__.py
│       │   ├── client.py      # WhatsAppOutboundClient
│       │   ├── payload_builders/
│       │   └── validators/
│       ├── signature.py
│       ├── flow_crypto.py
│       ├── flow_sender.py
│       ├── media_helpers.py
│       ├── media_uploader.py
│       ├── template_manager.py
│       └── http_client.py
│
├── infra/                 # Adaptadores para serviços externos
│   ├── __init__.py
│   ├── factories/         # (novo) Consolidar factories
│   │   ├── __init__.py
│   │   ├── dedupe_factory.py
│   │   ├── session_factory.py
│   │   ├── secrets_factory.py
│   │   └── http_factory.py
│   ├── dedupe/            # (novo) Organizar por tipo
│   │   ├── __init__.py
│   │   ├── store.py       # DedupeStore abstrato (do domain/)
│   │   ├── memory.py
│   │   ├── redis.py
│   │   └── firestore.py
│   ├── session/           # (novo) Reorganizar
│   │   ├── __init__.py
│   │   ├── store.py       # SessionStore abstrato (do domain/)
│   │   ├── memory.py
│   │   ├── redis.py
│   │   ├── firestore_sync.py
│   │   └── firestore_async.py
│   ├── secrets/           # (novo)
│   │   ├── __init__.py
│   │   ├── provider.py    # SecretProvider (do domain/)
│   │   ├── env.py
│   │   └── gcp.py
│   ├── http/              # (novo)
│   │   ├── __init__.py
│   │   └── client.py      # HttpClient com retry
│   ├── cloud_tasks.py     # Cloud Tasks dispatcher
│   ├── gcs_exporter.py
│   ├── decision_audit_store.py
│   ├── inbound_processing_log.py
│   └── outbound_dedup_factory.py
│
├── ai/                    # Clientes e schemas de LLM
│   ├── __init__.py
│   ├── orchestrator.py    # IntentClassifier, OutcomeDecider (a remover em v2.0)
│   ├── prompts/           # (novo) Prompts para 3 LLMs
│   │   ├── __init__.py
│   │   ├── state_selector.py
│   │   ├── response_generator.py
│   │   └── master_decider.py
│   └── openai_client.py   # Client LLM (ou alternativa)
│
├── observability/         # Logs, métricas, tracing
│   ├── __init__.py
│   ├── logging.py         # JSON structured logging
│   ├── middleware.py      # correlation_id middleware
│   └── metrics.py         # (novo) Métricas Prometheus/CloudMonitoring
│
├── config/                # Configuração e setup
│   ├── __init__.py
│   ├── settings.py        # Settings via Pydantic
│   └── dev.env            # Dev env example
│
├── utils/                 # Utilitários puros (sem IO)
│   ├── __init__.py
│   ├── ids.py             # Geração de IDs
│   └── dates.py
│
└── legacy/                # (novo) Código que será removido
    ├── __init__.py
    └── ai_orchestrator_v1.py # Será removido quando LLM #1 for completo
```

### 7.2 Regras de Dependência (Import Rules)

```
┌─────────────────────────────────────────────────────────────────┐
│ REGRAS DE IMPORTAÇÃO (Enforce via ruff/pylint)                  │
├─────────────────────────────────────────────────────────────────┤
│ domain/       → Não importa: adapters, infra, application, api  │
│ adapters/     → Pode importar: domain; não importa: infra, app  │
│ application/  → Pode importar: domain, adapters (via interface) │
│               → Depende de: infra/protocols/* (abstrações)      │
│ infra/        → Pode importar: domain/protocols, config          │
│               → Implementa protocolos de domain                  │
│ api/          → Pode importar: application (use-cases), config   │
│ ai/           → Pode importar: domain, config                   │
│ observability/→ Independente (usado em qualquer lugar)          │
└─────────────────────────────────────────────────────────────────┘
```

### 7.3 Estratégia de Migração Incremental

#### **Fase 1: Preparação (1 sprint, LOW RISK)**

1. ✅ Criar arquitetura de pastas (sem mover código)
   - Criar `domain/protocols/`, `application/ai/`, etc.
   - Adicionar `__init__.py` com exports

2. ✅ Criar abstrações (protocolos)
   - `domain/protocols/dedupe.py` ← copiado de `infra/dedupe.py` (classe abstrata)
   - `domain/protocols/session.py` ← copiado de `infra/session_contract.py`
   - `domain/protocols/secret_provider.py` ← copiado de `infra/secret_provider.py`

3. ✅ Atualizar imports em infra/ (shims de compatibilidade)
   ```python
   # infra/__init__.py
   from pyloto_corp.domain.protocols.dedupe import DedupeStore
   from pyloto_corp.domain.protocols.session import SessionStore
   # Mantem compatibility
   __all__ = ["DedupeStore", "SessionStore", ...]
   ```

4. **Gates:** `pytest`, `ruff check` (deve passar)

#### **Fase 2: Consolidação do Pipeline (1–2 sprints, MEDIUM RISK)**

1. ✅ Refatorar `pipeline.py` → `PipelineConfig`
   ```python
   @dataclass
   class PipelineConfig:
       dedupe: DedupeStore
       session: SessionStore
       orchestrator: AIOrchestrator
       flood_detector: FloodDetector | None = None
       llm_config: LLMConfig = field(default_factory=LLMConfig)
       abuse_config: AbuseConfig = field(default_factory=AbuseConfig)
   
   class WhatsAppInboundPipeline:
       def __init__(self, config: PipelineConfig):
           self._config = config
   ```

2. ✅ Consolidar 3 pipelines em 1
   - Mover lógica de `pipeline_v2.py` e `pipeline_async.py` → `pipeline.py`
   - Usar `async def` como base, wrapper síncrono via `asyncio.run()`
   - Garantir compatibilidade com testes existentes

3. **Gates:**
   - `pytest tests/application/test_pipeline*.py` (tudo passa)
   - `coverage --threshold 90` (mantém)
   - `ruff check` (sem warnings)

#### **Fase 3: Separação de Responsabilidades (1–2 sprints, MEDIUM RISK)**

1. ✅ Extrair `SessionManager` de `pipeline.py`
   ```python
   class SessionManager:
       def __init__(self, store: SessionStore): ...
       async def get_or_create(self, phone, sender_id) -> SessionState: ...
       async def save(self, session: SessionState): ...
   ```

2. ✅ Extrair `DedupeManager` de `pipeline.py`
   ```python
   class DedupeManager:
       def __init__(self, store: DedupeStore): ...
       def mark_if_new(self, key: str) -> bool: ...
   ```

3. ✅ Mover `ai/*.py` (estado_selector, response_gen, master) → `application/ai/`

4. **Gates:** Testes de unidade passam + integração

#### **Fase 4: Modularização de Adapters (1–2 sprints, LOW RISK)**

1. ✅ Split `normalizer.py` → `normalizer/` (extractor, sanitizer)
2. ✅ Split `secrets.py` → `secrets/` (provider, env, gcp)
3. ✅ Split `dedupe.py` → `dedupe/` (store, memory, redis, firestore)
4. ✅ Atualizar imports (manter shims em `__init__.py`)

**Gates:** Testes passam + imports funcionam

#### **Fase 5: Migração de Infra (1 sprint, LOW RISK)**

1. ✅ Reorganizar `infra/` conforme target tree
2. ✅ Criar `infra/factories/` com factories de dedupe, session, secrets
3. ✅ Consolidar Cloud Tasks, GCS, etc.

**Gates:** Testes passam

#### **Fase 6: Limpeza (1 sprint, TRIVIAL)**

1. ✅ Remover `.DEPRECATED`, `.bak`
2. ✅ Atualizar imports em CI/CD
3. ✅ Atualizar docs (README, arquitetura)
4. ✅ Marcar `ai/orchestrator.py` como "depreciar em v2.0"

**Gates:** CI/CD passa

---

### 7.4 Riscos de Breaking Change

| Fase | Risco | Mitigação | Severidade |
|------|-------|-----------|-----------|
| 1 | Imports quebram em `__init__.py` | Shims de compatibilidade + re-exports | Baixo |
| 2 | Pipeline não inicializa com novo config | Testes de integração ao lado de testes antigos | Médio |
| 2 | Async/sync mismatch | Wrapper asyncio.run() + testes paralelos | Médio |
| 3 | SessionManager/DedupeManager incompleto | Feature flags (usar antiga se nova falhar) | Baixo |
| 4 | Imports de normalizer quebram | Manter `from adapters.whatsapp import extract_messages` | Baixo |
| 5 | Factory não cria cliente correto | Testes de factory antes de remover antigo | Baixo |
| 6 | Legacy imports ainda funcionam | Remover shims em v2.0 (comunicar com deprecation warning) | Baixo |

---

## 8. CHECKLIST DE VALIDAÇÃO

### 8.1 Validação Pós-Implementação

- [ ] **Sintaxe:**
  ```bash
  ruff check src/pyloto_corp --select E,F,C901
  mypy src/pyloto_corp --strict
  ```

- [ ] **Testes:**
  ```bash
  pytest tests/ --cov=src/pyloto_corp --cov-threshold=90 --verbose
  ```

- [ ] **Imports:**
  ```bash
  python -c "from pyloto_corp import *; print('OK')"
  # Testar cada módulo:
  python -c "from pyloto_corp.application import pipeline; print('OK')"
  python -c "from pyloto_corp.infra import create_dedupe_store; print('OK')"
  ```

- [ ] **Performance (benchmarks):**
  ```bash
  pytest tests/benchmarks/test_pipeline_throughput.py
  # Esperado: <100ms por mensagem em single-thread
  ```

- [ ] **Compatibilidade:**
  - [ ] Webhook antigo ainda funciona? (GET /webhooks/whatsapp)
  - [ ] Cloud Tasks antigo funciona? (POST /tasks/whatsapp/inbound)
  - [ ] Outbound funciona? (envio de mensagens)
  - [ ] Testes E2E passam?

### 8.2 Validação de Boundaries

- [ ] Nenhum `import` de `infra/` em `domain/`
  ```bash
  grep -r "from pyloto_corp.infra" src/pyloto_corp/domain/
  # Esperado: nenhuma linha
  ```

- [ ] `application/` importa apenas `domain` e `protocols`
  ```bash
  grep -r "^from pyloto_corp" src/pyloto_corp/application/*.py | grep -v "domain\|protocols\|config"
  # Esperado: apenas config, ai (submodule)
  ```

- [ ] `adapters/` não contém lógica de negócio
  ```bash
  # Verificar funções por complexidade (McCabe <10)
  radon cc src/pyloto_corp/adapters/
  ```

### 8.3 Validação de Qualidade

- [ ] Sem PII em logs
  ```bash
  grep -rE "phone|email|address|name|user_id" src/pyloto_corp/observability/logging.py
  # Esperado: nenhuma referência direta (apenas como placeholders)
  ```

- [ ] Sem secrets hardcoded
  ```bash
  grep -rE "WHATSAPP.*=|FIREBASE.*=|GCP.*=" src/pyloto_corp/ | grep -v ".env"
  # Esperado: nenhuma
  ```

- [ ] Arquivo <200 linhas (exceto justified)
  ```bash
  find src/pyloto_corp -name "*.py" -type f | while read f; do
    lines=$(wc -l < "$f")
    if [ $lines -gt 200 ]; then
      echo "$f: $lines linhas"
    fi
  done
  ```

- [ ] Funções <50 linhas
  ```bash
  radon mi src/pyloto_corp --min B  # Maintainability Index >= B
  ```

---

## 9. RECOMENDAÇÕES PRIORIZADAS

### P0 — CRÍTICO (1–2 sprints)

| # | Ação | Impacto | Esforço |
|---|------|--------|--------|
| **P0-1** | Consolidar 3 pipelines → 1 (pipeline.py async + wrapper sync) | -1243 linhas duplicadas, consistência | Alto |
| **P0-2** | Refatorar WhatsAppInboundPipeline: use `PipelineConfig` | 18 params → 1, testabilidade | Médio |
| **P0-3** | Criar `domain/protocols/*`: abstrair dedupe, session, secrets | Respeita boundaries, testabilidade | Médio |

### P1 — ALTO (1–2 sprints)

| # | Ação | Impacto | Esforço |
|---|------|--------|--------|
| **P1-1** | Extrair `SessionManager` e `DedupeManager` da application | Simplifica pipeline | Médio |
| **P1-2** | Adicionar validação "Otto" na primeira mensagem do dia | Cumpre fluxo esperado | Baixo |
| **P1-3** | Unifical `DedupeStore` (remove `OutboundDedupeStore`) | Elimina duplicação | Médio |
| **P1-4** | Split `secrets.py`, `dedupe.py`: <200 linhas (SRP) | Manutenibilidade | Médio |

### P2 — MÉDIO (próximo sprint)

| # | Ação | Impacto | Esforço |
|---|------|--------|--------|
| **P2-1** | Adicionar `__repr__()` seguro a Outbound/HttpClient | Reduz risco PII leak | Baixo |
| **P2-2** | Implementar Circuit Breaker (pybreaker) | Resiliência a cascatas | Médio |
| **P2-3** | Split `normalizer.py` → `extractor + sanitizer` | Modularidade | Médio |
| **P2-4** | Adicionar correlation_id ao outbound task | Rastreabilidade end-to-end | Baixo |

### P3 — BAIXO (quando tempo permitir)

| # | Ação | Impacto | Esforço |
|---|------|--------|--------|
| **P3-1** | Adicionar testes de timeout para fallback LLM | Confiabilidade | Baixo |
| **P3-2** | Consolidar factories em `infra/factories/` | Organização | Baixo |
| **P3-3** | Documentar como remover `ai/orchestrator.py` em v2.0 | Roteiro claro | Trivial |

---

## 10. CONCLUSÃO

### 10.1 Síntese dos Achados

**pyloto_corp é um sistema bem estruturado que cumpre os objetivos funcionais**, mas apresenta:

- ✅ **Fluxo robusto:** Dedupe, session, timeout, abuse detection, logging implementados corretamente
- ✅ **Suporta centenas de mensagens simultâneas:** Firestore async, Redis dedupe, protocolos abstratos
- ✅ **Zero-trust e PII safe:** Logs estruturados, sanitização de payload, fail-closed em infra
- ❌ **Arquitetura frágil:** 3 pipelines duplicados, 18 parâmetros, aplicação acoplada a infra
- ❌ **SRP violado:** Arquivos >200 linhas (normalizer 306, dedupe 386, secrets 268)
- ⚠️ **Gaps menores:** Otto não validado em código, circuit breaker ausente

### 10.2 Risco Atual

**Sem mudanças:**
- Manutenção cara (3x linhas de código paralelo)
- Novos desenvolvedores confusos (qual pipeline usar?)
- Refatoração de ai/orchestrator afeta 3 arquivos
- Mudança em dedupe/session exige edições multiplas

**Com mudanças (Fases 1–3):**
- 2–3 meses de esforço incremental
- Zero risco de downtime (shims de compatibilidade)
- Custo de manutenção reduz 40–50%
- Novo fluxo de LLM implementa-se mais rápido

### 10.3 Recomendação Final

**Implementar Fase 1 (Preparação) e Fase 2 (Consolidação) no próximo sprint** para:
1. Eliminar duplicação de código
2. Preparar ground para LLM #1 substituto de IntentClassifier
3. Reduzir fricção em manutenção

Fases 3–6 podem ser incrementais sem bloqueios críticos.

---

## APÊNDICES

### A. Mapeamento Detalhado de Arquivos >200 Linhas

| Arquivo | Linhas | Exceção? | Motivo | Ação |
|---------|--------|----------|--------|------|
| `normalizer.py` | 306 | ❌ Não | 3 responsabilidades | P2: Split |
| `dedupe.py` | 386 | ❌ Não | 3 classes + factory | P2: Split |
| `secrets.py` | 268 | ❌ Não | 2 impls | P2: Split |
| `whatsapp_message_types.py` | 239 | ✅ Sim | Tipos verbosos, necessário | Monitor |
| `abuse_detection.py` | 260 | ✅ Sim | 3 detectores interconectados | Monitor |
| `pipeline.py` | 463 | ❌ Não | Consolidar 3 pipelines | P0: Merge |
| `orchestrator.py` | 271 | ✅ Sim | Classificador + decider | Monitor (removível v2.0) |
| `master_decider.py` | 250 | ✅ Sim | LLM #3 + fallback | Monitor |

### B. Testes Recomendados (Novo)

```python
# tests/application/test_pipeline_config.py
def test_pipeline_config_initialization():
    config = PipelineConfig(dedupe=..., session=..., ...)
    pipeline = WhatsAppInboundPipeline(config)
    assert pipeline is not None

# tests/application/test_session_manager.py
def test_session_manager_get_or_create():
    manager = SessionManager(session_store=...)
    session = await manager.get_or_create("5511987654321", "msg123")
    assert session.session_id is not None

# tests/application/ai/test_fallback_deterministic.py
def test_state_selector_timeout_fallback():
    # Mock timeout em LLM
    output = select_next_state(input, client=TimeoutClient(), timeout=0.1)
    assert output.selected_state == input.current_state  # Fallback

# tests/boundaries/test_import_rules.py
def test_domain_does_not_import_infra():
    """Ensure domain/ never imports from infra/"""
    import ast
    # Parse all domain/*.py files, check imports
    pass
```

### C. Matriz de Dependências (ASCII)

```
API (routes.py)
  ├─ Config
  ├─ DependencyInjection → Factories
  └─ handlers (normalize → pipeline → outbound)
      └─ pipeline.py (WhatsAppInboundPipeline)
          ├─ DedupeStore (abstract, impl: Redis/Firestore/Memory)
          ├─ SessionStore (abstract, impl: Firestore/Redis/Memory)
          ├─ AIOrchestrator (IntentClassifier, OutcomeDecider)
          ├─ state_selector.py (LLM #1) → llm_client
          ├─ response_generator.py (LLM #2) → llm_client
          └─ master_decider.py (LLM #3) → llm_client
              └─ outbound_client (WhatsAppOutboundClient)
                  └─ HttpClient (retry, backoff)
                      └─ Meta Graph API

Domain (independente)
  ├─ enums (Outcome, Intent, MessageType)
  ├─ conversation_state (contratos LLM)
  └─ abuse_detection (FloodDetector, SpamDetector, AbuseChecker)

Adapters (conversão ext ↔ int)
  ├─ normalizer (extrator payload → NormalizedWhatsAppMessage)
  ├─ outbound (WhatsAppOutboundClient → Graph API)
  └─ payload_builders (DTOs → payloads JSON)

Infra (implementações de protocolos)
  ├─ dedupe (DedupeStore impl)
  ├─ session (SessionStore impl)
  ├─ secrets (SecretProvider impl)
  ├─ http (HttpClient)
  ├─ cloud_tasks (CloudTasksDispatcher)
  └─ gcs/firestore/... (clients)

AI (orchestração de LLMs)
  └─ orchestrator (intent classifier, outcome decider)
      └─ openai_client (ou outro LLM provider)
```

---

**Fim do Relatório de Auditoria Profunda**
