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
