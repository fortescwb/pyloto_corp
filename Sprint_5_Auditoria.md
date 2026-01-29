# Esta sprint é **deliberadamente mais estratégica**: ela fecha ciclos iniciados antes, remove legado **com segurança comprovada** e prepara o sistema para evolução contínua sem regressão

---

## 📌 PLANO DE EXECUÇÃO TÉCNICO — SPRINT 5

**Repositório:** `pyloto_corp`
**Objetivo macro:** remoção controlada de legado + endurecimento definitivo do fluxo LLM
**Perfil da sprint:** limpeza estrutural + evolução consciente (MEDIUM RISK, CONTROLADO)

---

## 🔁 CONTEXTO GLOBAL (por que Sprint 5 existe)

Após Sprint 1–4, o sistema está:

* ✅ Arquiteturalmente organizado
* ✅ Pipeline único, fino e orquestrador
* ✅ SRP respeitado
* ✅ Infra modular e testável
* ✅ Boundaries corretos
* ⚠️ Ainda carrega **legado proposital** (determinístico)
* ⚠️ Ainda depende excessivamente de “boa resposta” da LLM
* ⚠️ Ainda não mede qualidade do fluxo LLM como sistema

A Sprint 5 **fecha esse gap**.

---

## 📜 Regras reforçadas (trechos de `regras_e_padroes.md`)

> **Regra 4.1 — Código legado**
> “Código legado deve ser explícito, isolado e ter plano de remoção.”
> **Regra 5.1 — Segurança funcional**
> “Nenhuma decisão crítica pode depender exclusivamente de comportamento probabilístico.”
> **Regra 6.2 — Observabilidade**
> “Sistemas devem ser auditáveis, mensuráveis e explicáveis.”

---

## 🟦 SPRINT 5 — REMOÇÃO CONTROLADA DE LEGADO + MATURIDADE LLM

## 🎯 Objetivo da Sprint 5

1. **Remover código legado que já cumpriu seu papel**
2. **Endurecer o pipeline LLM como sistema confiável**
3. **Introduzir métricas reais de qualidade e segurança**
4. **Preparar o sistema para evolução sem “grandes refactors”**

---

## PR-12 — Introdução de Métricas de Qualidade LLM (Observabilidade)

### 📌 Problema atual

Hoje sabemos que:

* a LLM responde
* o sistema funciona

Mas **não sabemos**:

* quando a LLM erra
* quando cai em fallback
* quando gera resposta insegura
* quando decide estado incorreto

---

### 🎯 Objetivo

Instrumentar o pipeline para **medir qualidade**, não só sucesso técnico.

---

### 🛠️ Mudanças técnicas

#### 1. Criar modelo de métricas

```path
domain/metrics/llm_decision.py
```

Campos:

* decision_type (state / response / fallback)
* confidence
* applied_state (bool)
* fallback_used (bool)
* latency_ms
* model_name
* correlation_id

---

#### 2. Emitir métricas no pipeline

* Após LLM #1
* Após LLM #2
* Após LLM #3

Destino:

* Logs estruturados
* Firestore / BigQuery (se configurado)

---

### 📜 Regra reforçada

> “O que não é medido não pode ser confiável.”

---

### ✅ Critérios de aceite

* Métricas emitidas sem PII
* Correlação completa request → decisão
* Nenhum impacto em latência perceptível

---

## PR-13 — Thresholds reais para decisões LLM (Fail-Safe)

### 📌 Problema atual PR-13

Mesmo com confiança baixa, a LLM pode:

* aplicar estado
* enviar resposta final

---

### 🎯 Objetivo PR-13

Introduzir **governança de decisão**, não confiança cega.

---

### 🛠️ Mudanças técnicas PR-13

#### 1. Definir thresholds explícitos

```thresholds
settings.py
LLM_STATE_MIN_CONFIDENCE=0.75
LLM_RESPONSE_MIN_CONFIDENCE=0.70
```

#### 2. Pipeline passa a decidir

```python
if decision.confidence < threshold:
    fallback()
```

Fallbacks possíveis:

* resposta neutra
* encaminhamento humano
* manutenção de estado

---

### 📜 Regra reforçada PR-13

> “LLM decide. Sistema governa.”

---

### ✅ Critérios de aceite PR-13

* Fallback determinístico testado
* Nenhuma decisão aplicada abaixo do threshold
* Testes cobrindo edge cases

---

## PR-14 — Remoção do `ai/orchestrator.py` (LEGADO)

> ⚠️ **PR mais sensível da sprint**

---

### 📌 Pré-requisitos (obrigatórios)

* Métricas coletadas ≥ 1 sprint
* LLM #1 com taxa de fallback aceitável
* Zero incidentes críticos

---

### 🎯 Objetivo PR-14

Remover o **classificador determinístico legado**, deixando:

* Estados decididos pela LLM
* Fallbacks explícitos no pipeline

---

### 🛠️ Estratégia segura

1. Feature flag:

    ```python
    USE_LEGACY_ORCHESTRATOR = False
    ```

2. Pipeline passa a ignorar o módulo
3. Testes de regressão completos
4. Remoção do código + imports
5. Atualização da documentação

---

### 📜 Regra reforçada PR-14

> “Legado não é removido por fé, mas por evidência.”

---

### ✅ Critérios de aceite PR-14

* Todos os testes verdes
* Métricas estáveis
* Nenhuma mudança de comportamento perceptível

---

## PR-15 — Limpeza final de legado e artefatos históricos

### 📌 Escopo

Remoção definitiva de:

* `.bak`
* `.DEPRECATED`
* imports não usados
* comentários obsoletos
* flags temporárias

---

### 🛠️ Ações

* `ruff --fix`
* `vulture` (dead code)
* revisão manual orientada pela auditoria

---

### 📜 Regra reforçada PR-15

> “Código morto é risco vivo.”

---

### ✅ Critérios de aceite PR-15

* Repo sem warnings
* Nenhuma referência a código removido
* Histórico limpo e legível

---

## 📦 Estado do sistema após Sprint 5

## ✅ Resultado técnico

* Zero legado funcional
* Pipeline 100% governado
* Decisões explicáveis
* Métricas reais de qualidade
* Sistema auditável de ponta a ponta

## ✅ Resultado estratégico

* Base pronta para:

  * múltiplos canais
  * múltiplos modelos LLM
  * melhoria contínua baseada em dados
  * compliance e auditorias externas

---

## 🚦 O que **não** será feito nesta sprint

* Otimizações prematuras de custo LLM
* Treinamento fino (fine-tuning)
* A/B testing automático

➡️ Esses entram numa **Sprint 6 (Evolução Inteligente)**, se desejado.

---
