# Este plano **assume como pré-requisito** que **Sprint 1 e 2 já foram concluídas e mergeadas**, ou seja

* pipeline único
* `PipelineConfig`
* boundaries com `domain/protocols`
* garantia determinística do “Otto”

---

## 📌 PLANO DE EXECUÇÃO TÉCNICO — SPRINT 3 & 4

**Repositório:** `pyloto_corp`
**Objetivo macro:** consolidar SRP, reduzir tamanho de arquivos, eliminar duplicações e preparar remoções futuras
**Perfil da sprint:** refatoração estrutural controlada (LOW–MEDIUM RISK)

---

## 🔁 CONTEXTO GLOBAL (por que Sprint 3 e 4 existem)

Após Sprint 1 e 2, o sistema:

* ✅ Tem **pipeline único**
* ✅ Tem **boundaries corretos**
* ✅ Tem **configuração explícita**
* ❌ Ainda possui arquivos grandes e multifuncionais
* ❌ Ainda possui duplicação conceitual (dedupe inbound/outbound)
* ❌ Ainda mistura responsabilidades operacionais no pipeline

Sprint 3 e 4 **não alteram o fluxo funcional**, mas:

* tornam o código **manutenível**
* reduzem custo de evolução
* deixam o repositório pronto para:

  * novos canais
  * novos LLMs
  * remoção do orquestrador determinístico no futuro

---

## 📜 Regras reforçadas (trechos de `regras_e_padroes.md`)

> **Regra 2.1 — Limite de tamanho**
> “Arquivos devem ter no máximo 200 linhas. Exceções devem ser justificadas.”
> **Regra 2.3 — SRP (Responsabilidade Única)**
> “Um módulo deve ter um único motivo para mudar.”
> **Regra 3.1 — Boundaries**
> “Infraestrutura não deve vazar para application nem domain.”
> **Regra 5.4 — Refatoração progressiva**
> “Mudanças estruturais devem ser incrementais, testáveis e reversíveis.”

---

## 🟦 SPRINT 3 — SRP, MANAGERS E MODULARIZAÇÃO

## 🎯 Objetivo da Sprint 3

Eliminar **módulos inchados** e **centralização excessiva** no pipeline, introduzindo *Managers* especializados.

---

## PR-06 — Extração de `SessionManager`

### 📌 Problema atual

Pipeline ainda:

* cria sessão
* carrega histórico
* atualiza estado
* persiste mensagens

➡️ **Múltiplos motivos para mudar**.

---

### 🎯 Objetivo

Extrair toda a lógica de sessão para um **componente dedicado**.

---

### 🛠️ Mudanças técnicas

#### 1. Criar módulo

```tree
application/session/
├── manager.py
├── models.py
└── __init__.py
```

#### 2. Responsabilidades do `SessionManager`

* load_or_create_session
* append_message
* update_state
* persist_session
* helpers: `is_first_message_of_day`

```python
class SessionManager:
    def get_or_create(...)
    def append_user_message(...)
    def append_system_message(...)
    def apply_state_transition(...)
```

#### 3. Pipeline passa a **delegar**

```python
session = session_manager.get_or_create(...)
```

---

### 📜 Regra reforçada

> “Pipeline orquestra. Ele não executa lógica de negócio.”

---

### ✅ Critérios de aceite

* Pipeline perde ≥30% de linhas
* Testes de sessão isolados
* Nenhuma mudança de comportamento

---

## PR-07 — Extração de `DedupeManager` (Inbound + Outbound)

### 📌 Problema atual PR-07

* Dedupe inbound ≠ dedupe outbound
* Protocolos duplicados
* Implementações duplicadas

---

### 🎯 Objetivo PR-07

Criar **um único conceito de deduplicação**, com uso parametrizado.

---

### 🛠️ Mudanças técnicas PR-07

#### 1. Criar protocolo unificado

```path
domain/protocols/dedupe.py
```

```python
class DedupeProtocol(ABC):
    def seen(self, key: str, ttl: int) -> bool: ...
```

#### 2. Criar manager

```path
application/dedupe/manager.py
```

```python
class DedupeManager:
    def inbound(self, message_id) -> bool
    def outbound(self, payload_hash) -> bool
```

#### 3. Infra implementa **uma vez**

* Memory
* Redis
* Firestore

---

### 📜 Regra reforçada PR-07

> “Duplicação conceitual é dívida técnica.”

---

### ✅ Critérios de aceite PR-07

* Nenhuma duplicação de store
* TTL configurável
* Testes cobrindo inbound/outbound

---

## PR-08 — Split de `normalizer.py`

### 📌 Problema atual PR-08

`normalizer.py`:

* extrai payload
* normaliza
* sanitiza
* valida

➡️ 300+ linhas, 4 responsabilidades.

---

### 🎯 Objetivo PR-08

Separar claramente cada etapa.

---

### 🛠️ Estrutura proposta

```tree
adapters/whatsapp/normalizer/
├── extractor.py
├── sanitizer.py
├── normalizer.py
├── validator.py
└── __init__.py
```

* **extractor**: payload bruto → estrutura interna
* **sanitizer**: remove PII / dados inúteis
* **normalizer**: mapeia para modelos internos
* **validator**: regras Meta/WhatsApp

---

### 🔒 Compatibilidade

```python
from adapters.whatsapp.normalizer import normalize_message
```

mantido via re-export.

---

### 📜 Regra reforçada PR-08

> “Arquivos grandes escondem responsabilidades.”

---

### ✅ Critérios de aceite PR-08

* Nenhum arquivo >200 linhas
* Imports antigos continuam funcionando
* Testes inalterados

---

## 🟦 SPRINT 4 — INFRA LIMPA, RESILIÊNCIA E PREPARAÇÃO FUTURA

## 🎯 Objetivo da Sprint 4

Consolidar infraestrutura, melhorar resiliência e **preparar remoções futuras** sem executá-las ainda.

---

## PR-09 — Split de `infra/secrets.py`

### 📌 Problema atual PR-09

`secrets.py`:

* define protocolo
* implementa Env
* implementa GCP

---

### 🛠️ Estrutura proposta PR-09

```tree
infra/secrets/
├── protocol.py
├── env_provider.py
├── gcp_provider.py
├── factory.py
└── __init__.py
```

---

### 📜 Regra reforçada PR-09

> “Protocolos não implementam infraestrutura.”

---

### ✅ Critérios de aceite PR-09

* Providers isolados
* Factory única
* Zero mudança de comportamento

---

## PR-10 — Circuit Breaker no HTTP Client

### 📌 Problema atual PR-10

* Retry existe
* Sem proteção contra cascata

---

### 🎯 Objetivo PR-10

Adicionar **circuit breaker** para:

* Graph API
* Providers externos

---

### 🛠️ Mudanças técnicas PR-10

* Introduzir `pybreaker` ou equivalente
* Configuração via settings
* Estados: closed / open / half-open

---

### 📜 Regra reforçada PR-10

> “Fail fast > retry infinito.”

---

### ✅ Critérios de aceite PR-10

* Circuit breaker testado
* Logs claros sem PII
* Fallback seguro

---

## PR-11 — Marcação formal de legado futuro

### 📌 Contexto

`ai/orchestrator.py` ainda é essencial, mas **tem data de validade**.

---

### 🎯 Objetivo PR-11

Documentar e preparar remoção futura **sem remover agora**.

---

### 🛠️ Ações

* Adicionar docstring clara:

```python
"""
LEGACY — Planned removal in v2.0
Depends on deterministic fallback until LLM stability >= threshold
"""
```

* Adicionar TODO técnico
* Atualizar docs

---

### 📜 Regra reforçada PR-11

> “Legado deve ser explícito, nunca implícito.”

---

### ✅ Critérios de aceite PR-11

* Nenhuma mudança funcional
* Documentação clara
* Auditoria futura facilitada

---

## 📦 Estado do sistema após Sprint 3 & 4

## ✅ Resultado técnico

* Pipeline fino e orquestrador puro
* Managers dedicados
* Infra modular
* SRP respeitado
* Boundaries claros

## ✅ Resultado estratégico

* Base pronta para:

  * novos canais
  * novos LLMs
  * remoção segura do determinístico
  * time maior sem perda de qualidade

---

## 🚦 O que **não** é feito ainda (intencional)

* Remoção do `ai/orchestrator.py`
* Mudanças de fluxo funcional
* Otimizações prematuras

➡️ Isso fica para **Sprint 5+**, quando métricas de LLM estiverem maduras.

---

## ▶️ Próximo passo natural

Se quiser, o próximo movimento pode ser:

* gerar **checklist de PR** (template GitHub)
* gerar **issues por PR**
* ou já montar o **plano da Sprint 5 (remoções e evolução)**

Quando decidir, seguimos.
