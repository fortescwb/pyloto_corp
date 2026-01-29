# O plano foi escrito como **documento de execução técnica**, não como auditoria, e respeita integralmente

* o fluxo funcional já validado
* os achados da auditoria
* as regras de `regras_e_padroes.md`
* o princípio de **zero downtime + zero breaking change**

> ⚠️ **Importante**
> Nenhuma etapa abaixo remove código em uso.
> Tudo é feito com **shims, re-exports e compatibilidade retroativa**.

---

## 📌 PLANO DE EXECUÇÃO TÉCNICO — SPRINT 1 & 2

**Repositório:** `pyloto_corp`
**Objetivo macro:** eliminar fragilidade arquitetural sem alterar comportamento funcional
**Resultado esperado:** base sólida para evolução (Sprint 3 e 4)

---

## 🔁 CONTEXTO GLOBAL (por que essas sprints existem)

Hoje o sistema:

* ✅ Funciona corretamente
* ❌ Possui **3 pipelines paralelos**
* ❌ Pipeline com **18 parâmetros**
* ❌ Application depende diretamente de Infra
* ❌ Dificulta testes, evolução e onboarding

Essas duas sprints **não adicionam features**.
Elas **reduzem risco estrutural** e **preparam o terreno**.

---

## 📜 Regras que guiam TODAS as mudanças (trechos de `regras_e_padroes.md`)

> **Regra 2.1 — Tamanho de arquivos**
> “Arquivos devem ter no máximo 200 linhas. Arquivos maiores indicam múltiplas responsabilidades.”
> **Regra 2.3 — Responsabilidade Única (SRP)**
> “Uma classe ou módulo deve ter apenas um motivo para mudar.”
> **Regra 3.1 — Boundaries arquiteturais**
> “Camada de domínio e aplicação não devem depender de infraestrutura.”
> **Regra 5.2 — Mudanças seguras**
> “Refatorações devem preservar contratos públicos e comportamento observável.”

Essas regras **não são negociáveis** e serão citadas nos PRs.

---

## 🟦 SPRINT 1 — PREPARAÇÃO ARQUITETURAL (SEM RISCO)

## 🎯 Objetivo da Sprint 1

Preparar o repositório para a consolidação futura **sem alterar o fluxo atual**.

Nada muda em runtime.
Nada quebra.
Nada é removido.

---

## PR-01 — Introdução de Protocolos de Domínio (Boundaries)

### 📌 Problema atual

`application/*` importa diretamente `infra/*`.

Exemplo real:

```python
from pyloto_corp.infra.dedupe import DedupeStore
```

Isso **viola** Regra 3.1.

---

### 🎯 Objetivo do PR

Criar **contratos abstratos** para que:

* Application dependa apenas de **interfaces**
* Infra passe a ser **plugável**
* Testes fiquem simples

---

### 🛠️ Mudanças técnicas

#### 1. Criar novo módulo

```tree
src/pyloto_corp/domain/protocols/
├── dedupe.py
├── session_store.py
├── decision_audit_store.py
└── __init__.py
```

#### 2. Exemplo de protocolo

```python
# domain/protocols/dedupe.py
from abc import ABC, abstractmethod

class DedupeProtocol(ABC):
    @abstractmethod
    def is_duplicate(self, key: str) -> bool: ...
```

#### 3. Infra passa a implementar

```python
class FirestoreDedupeStore(DedupeProtocol):
    ...
```

#### 4. Application passa a importar apenas protocolo

```python
from pyloto_corp.domain.protocols.dedupe import DedupeProtocol
```

---

### 🔒 Compatibilidade

* Infra mantém exports antigos
* Nenhuma assinatura pública muda
* Testes continuam passando

---

### ✅ Critérios de aceite

* Nenhum `application/*` importa `infra/*`
* `ruff` sem warnings
* `pytest` 100% verde

---

## PR-02 — PipelineConfig (18 parâmetros → 1)

### 📌 Problema atual PR-02

Construtor do pipeline tem **18 parâmetros**, violando SRP e testabilidade.

---

### 🎯 Objetivo do PR PR-02

Introduzir um **objeto de configuração explícito**.

---

### 🛠️ Mudanças técnicas PR-02

#### 1. Criar dataclass

```python
# application/pipeline_config.py
from dataclasses import dataclass

@dataclass
class PipelineConfig:
    dedupe: DedupeProtocol
    session_store: SessionStoreProtocol
    state_selector: StateSelectorClient
    response_generator: ResponseGeneratorClient
    master_decider: MasterDeciderClient
    decision_audit_store: DecisionAuditStoreProtocol
```

#### 2. Pipeline passa a receber **1 parâmetro**

```python
class Pipeline:
    def __init__(self, config: PipelineConfig):
        self.config = config
```

#### 3. Factory constrói o config

```python
Pipeline(config=build_pipeline_config())
```

---

### 🔒 Compatibilidade PR-02

* Criar wrapper temporário que aceita assinatura antiga
* Deprecar assinatura antiga com comentário claro

---

### 📜 Regra reforçada no PR

> “Construtores com muitos parâmetros indicam violação de responsabilidade.”

---

### ✅ Critérios de aceite PR-02

* Nenhum pipeline recebe mais de 1 argumento
* Testes existentes inalterados
* Novo pipeline instanciável em testes unitários

---

## PR-03 — Garantia Determinística do “Otto”

### 📌 Problema atual PR-03

Apresentação do “Otto” depende apenas do prompt.

---

### 🎯 Objetivo

Garantir **no código**, não no LLM, que:

> “Se for a primeira mensagem do dia, apresentar-se como Otto.”

---

### 🛠️ Mudanças técnicas PR-03

* Criar helper:

```python
def should_introduce_otto(session) -> bool:
    return session.is_first_message_of_day()
```

* Prefixar resposta **antes** do envio, se necessário

---

### 📜 Regra reforçada

> “Regras institucionais não podem depender exclusivamente de LLM.”

---

### ✅ Critérios de aceite PR-03

* Teste unitário cobrindo primeira mensagem do dia
* Nenhuma alteração no prompt necessária

---

## 🟦 SPRINT 2 — CONSOLIDAÇÃO DO PIPELINE

> ⚠️ Sprint 2 **só começa após todos os PRs da Sprint 1 estarem mergeados**

---

## 🎯 Objetivo da Sprint 2

Eliminar duplicação estrutural mantendo comportamento idêntico.

---

## PR-04 — Pipeline Único (async-first)

### 📌 Problema atual PR-04

Existem 3 pipelines:

* `pipeline.py`
* `pipeline_v2.py`
* `pipeline_async.py`

---

### 🎯 Objetivo PR-04

Ter **1 pipeline canônico**, async-first.

---

### 🛠️ Estratégia (sem risco)

1. Escolher `pipeline_async.py` como base
2. Refatorar para `pipeline.py`
3. Criar wrappers

    ```python
    def process_sync(...):
        return asyncio.run(self.process_async(...))
    ```

4. Re-exportar nomes antigos

```python
# pipeline_v2.py
from .pipeline import Pipeline
```

---

### 📜 Regra reforçada PR-04

> “Duplicação é dívida técnica ativa.”

---

### ✅ Critérios de aceite PR-04

* Nenhuma mudança de output
* Todos os testes existentes passam
* Linhas duplicadas eliminadas

---

## PR-05 — Unificação da Inicialização do Pipeline

### 🎯 Objetivo PR-05

Centralizar criação de dependências.

---

### 🛠️ Mudanças

Criar:

```path
infra/factories/pipeline_factory.py
```

Responsável por:

* Instanciar dedupe
* Session store
* Clients LLM
* PipelineConfig

---

### 📜 Regra reforçada PR-05

> “Application não cria infraestrutura.”

---

### ✅ Critérios de aceite PR-05

* Pipeline criado por factory única
* Testes conseguem mockar factory

---

## 📦 Estado do sistema após Sprint 1 & 2

## ✅ O que continua funcionando

* Fluxo WhatsApp completo
* Três LLMs
* Sessão, dedupe, auditoria
* Escala e concorrência

## ✅ O que melhora drasticamente

* Arquitetura limpa
* Testabilidade
* Redução de duplicação
* Evolução segura

## 🚦 O que ainda NÃO será feito

* Split de arquivos grandes
* Unificação de dedupe inbound/outbound
* Remoção do `ai/orchestrator.py`

➡️ **Isso fica para Sprint 3 e 4**, agora com base sólida.

---
