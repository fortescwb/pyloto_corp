# Revisão final da Sprint 1-2

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
