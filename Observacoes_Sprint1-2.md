# Revisão final da Sprint 1-2 **CONCLUIDO**

## Pontos de revisão referentes à PR-01

1.**Confirmação objetiva do boundary (runtime)**

    * Revalidar no fim da Sprint 1–2 que **nenhum import runtime** em `src/pyloto_corp/application/**` aponta para `pyloto_corp.infra.*`.
    * Atenção especial para imports “indiretos” via `TYPE_CHECKING` que eventualmente viram runtime por engano.

2.**Compatibilidade real de exports em `infra`**

    * Validar que nomes históricos (ex.: `DedupeStore`, `SessionStore`, `DecisionAuditStore`) continuam resolvendo **sem circular import** e sem regressão.
    * O teste `tests/unit/test_protocols_compat.py` cobre o básico; no final da Sprint 1–2, confirmar também em **path de inicialização real** (factory do pipeline).

3.**`whatsapp_async.py`: tratamento genérico de exceções**

    * Revisar se o ajuste para evitar dependência direta de `HttpError`/Cloud Tasks preserva:

      * códigos de retorno esperados
      * logging/correlation-id
      * comportamento de retry/backoff e falha segura
    * Se o projeto quiser rigor maior, isso sugere um **Protocol futuro** para `CloudTasksDispatcher`/HTTP client (fica fora da PR-01, mas registrar como item de auditoria).

4.**Gates de lint no monorepo**

    * A PR-01 rodou `ruff` focado no pacote `src/pyloto_corp`. Ao final da Sprint 1–2:
    
      * registrar formalmente o “scope gate” (ruff/pytest do pacote) vs “gate global”
      * garantir que isso está alinhado ao processo do repositório para evitar divergência entre times.

5.**Nomenclatura e consistência de protocolos async**

    * Foi introduzido `AsyncSessionStoreProtocol`. No final da Sprint 1–2, confirmar:

      * coerência de nomes entre sync/async
      * se há chance de consolidar contrato mantendo clareza (sem refatorar agora).

Esses pontos são de **verificação**, não bloqueiam a PR-01 (ela cumpriu objetivo), mas ajudam a evitar “drift” até o final da Sprint 1–2.

---

## Pontos de revisão referentes à PR-02

### Seção — PR-02: PipelineConfig (18 parâmetros → 1)

Abaixo estão as **observações e pontos de atenção** que devem ser **verificados ao final da Sprint 1–2**, especificamente sobre a PR-02.

### 1) Compatibilidade real de inicialização do pipeline

* Confirmar que **todos os entrypoints reais** (handlers HTTP, workers, Cloud Tasks, testes de integração) continuam inicializando o pipeline **sem alteração de assinatura percebida**.
* Verificar que **nenhum ponto externo** ainda tenta instanciar diretamente o construtor antigo sem passar pelo `from_dependencies`.

**Motivo:**
A compatibilidade foi garantida via *classmethod shim*, mas isso precisa ser validado no fluxo real completo, não apenas em testes unitários.

---

### 2) PipelineConfig como DTO puro (não virar “service locator”)

* Garantir que `PipelineConfig` permaneça:

  * imutável (`frozen=True`)
  * sem lógica
  * sem side effects
* Evitar, nas próximas PRs, adicionar métodos ou lógica dentro do config.

**Motivo (Regra 2.3 — SRP):**
Config é **dados**, não comportamento. Qualquer lógica adicionada aqui cria acoplamento oculto.

---

### 3) Consistência entre pipelines paralelos (até Sprint 2 acabar)

* Confirmar que:

  * `pipeline.py`
  * `pipeline_async.py`
  * `pipeline_v2.py`
    usam **exatamente o mesmo padrão de construção** (config + shim), mesmo que ainda existam em paralelo.

**Motivo:**
Antes da consolidação (Sprint 2), divergências aqui geram bugs difíceis de rastrear.

---

### 4) Tipagem e TYPE_CHECKING

* Revisar no final da Sprint 1–2:

  * se `TYPE_CHECKING` continua sendo usado apenas para **typing**
  * se nenhum import “inocente” virou runtime import acidental

**Motivo:**
Esse é o ponto mais comum onde boundaries quebram silenciosamente.

---

### 5) Factory futura (nota arquitetural, não ação)

* Registrar explicitamente que:

  * `PipelineConfig` **não deve** ser instanciado em handlers
  * A criação centralizada ficará para a **PR-05 (factory)**

**Motivo:**
Evita que o time comece a criar configs “na mão” em vários lugares.

---

### 6) Métrica de sucesso da PR-02

Ao final da Sprint 1–2, considerar a PR-02 **100% validada** se:

* nenhum pipeline recebe mais de **1 argumento**
* não há regressão de testes
* não há dependência infra → application reintroduzida
* o fluxo WhatsApp funciona sem alteração perceptível

---

Esses pontos **não bloqueiam** a PR-02 (ela está correta), mas **blindam** a sprint contra regressões silenciosas.

---

## Pontos de revisão referentes à PR-03

### Seção — PR-03: Garantia determinística do “Otto”

Abaixo estão os **pontos de atenção que devem ser verificados ao final da Sprint 1–2**, específicos da PR-03.

---

### 1) Fonte de verdade temporal (timezone)

* Confirmar que o critério de “primeira mensagem do dia” está **claramente documentado como UTC**.
* Avaliar, ao final da Sprint 1–2, se existe necessidade futura de:

  * timezone por tenant
  * timezone por número/país

**Status atual:**
✔️ Correto e consistente (UTC).
⚠️ Apenas documentar como decisão arquitetural.

---

### 2) Crescimento do `message_history`

* A PR adiciona uma entrada mínima (`received_at`) por mensagem recebida.
* Verificar ao final da Sprint:

  * se existe TTL/limpeza de histórico
  * se há risco de crescimento não controlado em sessões longas

**Importante:**
Isso **não é bug**, mas precisa ser observado antes de produção em larga escala.

---

### 3) Escopo do prefixo do Otto

* Atualmente o prefixo:

  * ✔️ é aplicado apenas em `ai_response.reply_text`
  * ❌ não é aplicado em `master_decision.selected_response_text`

**Motivo correto agora:** preservar compatibilidade e evitar surpresas.

**Ponto de revisão futura:**
Decidir se:

* respostas decididas explicitamente pelo master decider também devem receber o Otto (opt-in).

---

### 4) Não duplicação do prefixo

* O código atual **assume** que:

  * apenas a primeira mensagem do dia passa pelo helper
* Validar ao final da Sprint:

  * se há algum cenário de replay/retry onde o prefixo possa duplicar

**Risco:** baixo
**Ação agora:** nenhuma (apenas observação).

---

### 5) Separação correta de responsabilidades (PASS)

Confirmar que continua verdadeiro:

* helper → decisão determinística
* domain/constants → texto institucional
* pipeline → aplicação da regra
* LLM → geração de conteúdo

✔️ A PR respeita SRP e boundaries.
✔️ Nenhuma lógica institucional foi empurrada para prompt.

---

### 6) Métrica de sucesso da PR-03

Ao final da Sprint 1–2, considerar a PR-03 **validada** se:

* toda primeira mensagem do dia apresenta Otto
* mensagens seguintes não reapresentam
* fallback determinístico também recebe Otto
* nenhum teste de integração foi afetado

---

Esses pontos **não bloqueiam** a PR-03.
Eles garantem que a regra institucional continue **determinística, auditável e evolutiva**.

---
Perfeito. Mantendo **o mesmo rigor, formato e governança**, segue:

---

## Pontos de revisão referentes à PR-04

### Seção — PR-04: Bootstrap explícito do estado inicial (FSM)

Abaixo estão as **observações e pontos de atenção** que devem ser **verificados ao final da Sprint 1–2**, especificamente sobre a PR-04.

---

### 1) Dupla representação de estados (FSM vs ConversationState)

Atualmente coexistem:

* `domain.fsm_states.ConversationState` (FSM interna)
* `domain.conversation_state.ConversationState` (contrato do State Selector)

**Status atual:**
✔️ A PR-04 **não agravou** o problema.
⚠️ O problema **continua existindo** e agora ficou mais visível.

**Ponto de atenção:**
Ao final da Sprint 1–2, confirmar que:

* há entendimento claro de qual enum é:

  * **estado interno da FSM**
  * **estado conversacional exposto à LLM**
* nenhuma conversão implícita ocorre fora de locais controlados (`initial_state.py`, pipeline).

➡️ **Ação futura planejada (Sprint 3)**: criar um **mapa explícito FSM → ConversationState**.

---

### 2) Fonte única do estado inicial (PASS)

* `INITIAL_STATE` agora é:

  * explícito
  * centralizado
  * independente de LLM

✔️ Isso atende diretamente às regras:

> “FSM deve ter estado inicial explícito.”
> “Estados não são decididos por IA.”

**Verificação final da sprint:**
Garantir que **nenhum outro arquivo** redefine ou assume estado inicial implicitamente.

---

### 3) Normalização defensiva de estado em pipeline

A PR adicionou lógica defensiva para:

* corrigir estado ausente ou inválido para `INITIAL_STATE`

**Risco:** baixo
**Benefício:** alto (resiliência contra dados legados/corrompidos)

**Ponto de atenção:**
Confirmar que essa normalização:

* ocorre **antes** de qualquer chamada à LLM
* não mascara bugs silenciosamente (logs continuam suficientes para debug)

---

### 4) Testes de bootstrap (PASS)

* Testes unitários cobrem:

  * sessão nova
  * sessão existente
  * payload correto para o state selector

✔️ Cobertura adequada para Sprint 1–2.

**Nota:**
Não é necessário teste de integração adicional neste momento.

---

### 5) Métrica de sucesso da PR-04

Ao final da Sprint 1–2, considerar a PR-04 **validada** se:

* toda sessão nova inicia com `INITIAL_STATE`
* a LLM nunca recebe `None` ou estado implícito
* nenhuma decisão de estado inicial depende de prompt
* nenhum teste de integração que envolva FSM foi afetado

---

Esses pontos **não bloqueiam** a PR-04.
Eles garantem que a base da FSM esteja **sólida antes da consolidação do pipeline** (Sprint 2).

---
Perfeito. Seguindo **exatamente o mesmo padrão** das PRs anteriores, abaixo está o conteúdo para ser incluído no arquivo **`Observacoes_Sprint1-2.md`**, referente **exclusivamente à PR-05**.

---

## Pontos de revisão referentes à PR-05

### Seção — PR-05: Centralização da construção do Pipeline (Factory)

Abaixo estão as **observações e pontos de atenção** que devem ser **verificados ao final da Sprint 1–2**, especificamente sobre a PR-05.

---

### 1) Múltiplos caminhos de construção do Pipeline (intencional, mas temporário)

Atualmente coexistem:

* Factory canônica: `build_whatsapp_pipeline(...)`
* Compatibilidade: `WhatsAppInboundPipeline.from_dependencies(...)`
* Construtor direto via `WhatsAppInboundPipeline(config)`

**Status atual:**
✔️ Intencional e correto para Sprint 1–2 (compatibilidade total).
⚠️ **Não deve permanecer indefinidamente.**

**Ponto de atenção:**
Ao final da Sprint 1–2, confirmar que:

* **nenhum novo código** está criando pipeline fora da factory
* a factory é claramente comunicada como **caminho preferencial**

➡️ **Ação futura (Sprint 3):**
Planejar descontinuação gradual de `from_dependencies`.

---

### 2) Boundary respeitado (PASS)

A factory:

* ✔️ conhece `infra`
* ✔️ conhece `settings`
* ❌ não executa lógica de negócio
* ❌ não decide estado
* ❌ não chama LLM

Isso está **100% alinhado** com a regra:

> “Factories conhecem detalhes. Pipelines orquestram.”

**Verificação final da sprint:**
Garantir que **nenhuma lógica adicional** tenha sido adicionada à factory.

---

### 3) PipelineConfig como ponto único de injeção (PASS)

Com a PR-05:

* `PipelineConfig` deixou de ser instanciado “solto”
* a factory se tornou a **fonte primária de criação**

**Ponto de atenção:**
Confirmar que:

* nenhum handler/test cria `PipelineConfig` manualmente fora da factory
* novos campos futuros sejam adicionados **somente** via factory

---

### 4) Acoplamento implícito via Settings

A factory lê `Settings` diretamente para decidir:

* stores
* backends
* configurações padrão

**Risco:** baixo
**Impacto:** aceitável (por definição, factory pode conhecer infra e settings)

**Ponto de atenção:**
Documentar claramente que:

* `Settings` → infra/factory
* `Settings` ❌ pipeline/application core

---

### 5) Testes da factory (PASS)

* Testes unitários garantem:

  * construção válida do pipeline
  * funcionamento com defaults

✔️ Cobertura suficiente para Sprint 1–2.

**Nota:**
Não é necessário teste de integração adicional neste momento.

---

### 6) Ponto de corte arquitetural (importante)

A PR-05 **fecha oficialmente** a fase de “preparação sem risco”.

Após esta PR:

* refatorações estruturais passam a ser seguras
* consolidação de pipelines não depende mais de caça a dependências espalhadas

**Ponto de atenção:**
Registrar explicitamente que:

* **Sprint 3 pode assumir a factory como única porta de entrada**

---

### 7) Métrica de sucesso da PR-05

Ao final da Sprint 1–2, considerar a PR-05 **validada** se:

* pipeline é criado majoritariamente via factory
* nenhuma regressão funcional foi observada
* boundaries continuam respeitados
* não houve duplicação de lógica de construção

---

## ✅ Conclusão da Sprint 1–2 (visão consolidada)

Com a PR-05 concluída, a Sprint 1–2 entrega:

* Boundaries claros (domain ↔ application ↔ infra)
* Pipeline com:

  * config única
  * estado inicial explícito
  * regra institucional determinística (Otto)
  * construção centralizada
* Base **segura e estável** para refatoração estrutural

📌 **Nada mudou em runtime. Tudo mudou em controle.**

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

## **CONCLUÍDO**
