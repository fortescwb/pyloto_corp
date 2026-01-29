# M2 + L1 — Correlation-ID Async + Fallback INFO Logging

**Status:** ✅ COMPLETED  
**Date:** 2026-01-27  
**Execução:** Propagação de `correlation_id` em async + Elevar fallbacks para INFO com `fallback_used=true`

---

## 1) Executive Summary

Implementação de **M2** (propagação de correlation-id em fluxos async) e **L1** (fallbacks em INFO com flag `fallback_used`) com mudanças mínimas:

- ✅ **Correlation-ID**: Já propagava via ContextVar (existia). Confirmado para async.
- ✅ **Fallback Logging**: Criado helper `log_fallback()` em observabilidade. Atualizado `openai_client.py` para usar INFO + metadados.
- ✅ **Testes**: 7 testes novos cobrindo log_fallback + correlation-id async.
- ✅ **Gates**: Ruff ✓, Pytest ✓ (36/36 testes relevantes passando).

---

## 2) Mudanças Implementadas

### 2.1 Helper para Fallback Logging

**Arquivo:** [src/pyloto_corp/observability/logging.py](src/pyloto_corp/observability/logging.py#L52-L80)

```python
def log_fallback(
    logger: logging.Logger,
    component: str,
    reason: str | None = None,
    elapsed_ms: float | None = None,
) -> None:
    """Log observável de fallback usado (sem PII).

    Args:
        logger: Logger instance
        component: Nome do componente (ex: "event_detection", "response_generation")
        reason: Razão do fallback (ex: "timeout", "parse_error") — sem PII
        elapsed_ms: Tempo decorrido em ms (quando aplicável)
    """
```

**Características:**
- Nível **INFO** (antes era WARNING)
- Campos estruturados: `fallback_used=True`, `component`, `reason` (opcional), `elapsed_ms` (opcional)
- Sem PII (apenas componente e tipo de erro)

**Exemplo:**
```python
log_fallback(logger, "response_generation", reason="api_timeout", elapsed_ms=5230)
```

Output:
```json
{
  "level": "INFO",
  "message": "Fallback applied for response_generation",
  "fallback_used": true,
  "component": "response_generation",
  "reason": "api_timeout",
  "elapsed_ms": 5230,
  "correlation_id": "uuid-here",
  "service": "pyloto_corp"
}
```

### 2.2 Atualização de OpenAI Client

**Arquivo:** [src/pyloto_corp/ai/openai_client.py](src/pyloto_corp/ai/openai_client.py)

**Mudanças:**
- Importa `log_fallback` do módulo de observabilidade
- Substitui `logger.warning(...)` por `log_fallback(logger, component, reason=...)`
- Aplicado em 3 pontos:
  1. `detect_event()` — fallback para event detection
  2. `generate_response()` — fallback para response generation
  3. `select_message_type()` — fallback para message type selection

**Antes:**
```python
except (APIError, APITimeoutError) as e:
    logger.warning(
        "event_detection_error",
        extra={"error": str(e), "error_type": type(e).__name__},
    )
    return openai_parser._fallback_event_detection()
```

**Depois:**
```python
except (APIError, APITimeoutError) as e:
    log_fallback(
        logger,
        "event_detection",
        reason=type(e).__name__,
    )
    return openai_parser._fallback_event_detection()
```

### 2.3 Correlation-ID em Async (M2)

**Arquivo:** [src/pyloto_corp/observability/middleware.py](src/pyloto_corp/observability/middleware.py#L12)

**Status:** ✅ Já implementado e funcionando.

- ContextVar `_correlation_id` propagada automaticamente em contexto async
- Middleware injeta em cada request
- CorrelationIdFilter adiciona em cada log

**Teste de Comprovação:**
```python
@pytest.mark.asyncio
async def test_correlation_id_in_async_context():
    """correlation_id deve propagar em contexto async."""
    token = _correlation_id.set("async-test-id")
    try:
        async def inner_async():
            return get_correlation_id()
        result = await inner_async()
        assert result == "async-test-id"
    finally:
        _correlation_id.reset(token)
```

---

## 3) Campos Padronizados de Log

Toda saída de log estruturado agora inclui:

| Campo | Origem | Exemplo |
|-------|--------|---------|
| `correlation_id` | ContextVar via Middleware | `"uuid-12345"` |
| `service` | CorrelationIdFilter | `"pyloto_corp"` |
| `level` | Logger | `"INFO"`, `"WARNING"` |
| `logger` | JsonFormatter rename | `"pyloto_corp.ai.openai_client"` |
| `message` | Log statement | `"Fallback applied for event_detection"` |
| `component` | log_fallback (L1) | `"event_detection"` |
| `fallback_used` | log_fallback (L1) | `true`, `false` |
| `reason` | log_fallback (L1, opcional) | `"APITimeoutError"`, `"parse_error"` |
| `elapsed_ms` | log_fallback (L1, opcional) | `125.5`, `5230` |

---

## 4) Testes Adicionados

**Arquivo:** [tests/unit/test_observability_fallback.py](tests/unit/test_observability_fallback.py)

### TestLogFallback (4 testes)
- `test_log_fallback_basic` — Nivel INFO, message correto
- `test_log_fallback_with_reason` — Razão incluída em extra
- `test_log_fallback_with_elapsed_ms` — Tempo decorrido incluído
- `test_log_fallback_no_reason_no_elapsed` — Funciona sem opcionais

### TestCorrelationIdContextVar (3 testes)
- `test_correlation_id_retrieval` — Get/set funciona
- `test_correlation_id_default_empty` — Default é ""
- `test_correlation_id_in_async_context` — Propaga em async ✅

**Resultado:** 7/7 passando ✅

---

## 5) Gates de Qualidade

### Ruff (Lint)
```
src/pyloto_corp/observability/logging.py — All checks passed ✓
src/pyloto_corp/ai/openai_client.py — All checks passed ✓
```

### Pytest
```
tests/unit/test_dedupe.py                      — 23 passed
tests/unit/test_observability_fallback.py      — 7 passed
tests/application/test_pipeline_fallback.py    — 6 passed
───────────────────────────────────────────────────────────
Total: 36/36 PASSED ✓
```

---

## 6) Riscos Residuais

### Baixo
- **PII em logs**: Mitigado — `component` e `reason` são genéricos (nomes de exceções, não payloads)
- **Async context propagation**: ✓ Testado, ContextVar é thread-safe e async-safe por design

### Nenhum bloqueador encontrado

---

## 7) Próximos Passos (Recomendação)

1. **Monitorar em staging/prod**: Validar que fallback_used=true aparece quando esperado
2. **Adicionar métrica**: Contar occurrências de fallback por componente (ex.: "fallbacks_event_detection_total")
3. **Documentar em runbooks**: "Se ver fallback_used=true em logs, OpenAI pode estar down ou timeout"

---

## 8) Checklist de Encerramento

- [x] Helper `log_fallback()` implementado (sem PII)
- [x] OpenAI client atualizado para usar INFO + log_fallback
- [x] Correlation-ID async confirmado (ContextVar)
- [x] Testes novos cobrindo ambos (7/7 ✓)
- [x] Ruff clean
- [x] Pytest suite passando (36/36 relevantes ✓)
- [x] Documentação entregue

**Status Final: ✅ M2 + L1 COMPLETE**

