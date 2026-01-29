# Coverage Baseline — pyloto_corp

## Metadados

| Campo | Valor |
|-------|-------|
| Data/Hora | 2026-01-27 15:31 (America/Sao_Paulo) |
| Comando | `pytest --cov=src/pyloto_corp --cov-report=term-missing --cov-report=html` |
| Testes | 873 passed |
| **Cobertura Total** | **84%** (4110 stmts, 656 miss) |

## Top 15 Arquivos com Menor Cobertura

| Arquivo | Cov% | Observação |
|---------|------|------------|
| `ai/prompts.py` | 0% | Módulo de constantes, não testável |
| `application/handoff.py` | 0% | Stub/placeholder, não implementado |
| `infra/outbound_dedupe.py` | 0% | Legacy, substituído por `outbound_dedup_*.py` |
| `infra/secret_provider.py` | 0% | Interface abstrata |
| `ai/openai_parser.py` | 26% | Parsing de LLM, exige mock de resposta estruturada |
| `ai/openai_prompts.py` | 30% | Templates de prompts |
| `ai/openai_client.py` | 35% | Cliente OpenAI real, exige mock |
| `ai/context_loader.py` | 42% | Leitura de arquivos estáticos |
| `application/pipeline_v2.py` | 48% | Pipeline principal com LLM, complexo de mockar |
| `infra/outbound_dedup_firestore.py` | 59% | Firestore real, exige emulador |
| `infra/outbound_dedup_redis.py` | 71% | Redis real, exige emulador |
| `infra/session_store.py` | 71% | Factory, branches de provider |
| `ai/orchestrator.py` | 74% | Orquestrador LLM |
| `domain/intent_queue.py` | 74% | Fila de intents |
| `infra/flood_detector_factory.py` | 77% | Factory com branches de provider |

## Observações

1. **Módulos não testáveis** (0%):
   - `ai/prompts.py` — contém apenas constantes/strings
   - `application/handoff.py` — stub para feature futura
   - `infra/outbound_dedupe.py` — módulo legacy, será removido
   - `infra/secret_provider.py` — interface abstrata sem lógica

2. **Módulos de integração real** (< 50%):
   - `ai/openai_*.py` — requerem mock de OpenAI ou chamada real
   - `pipeline_v2.py` — orquestra LLM, difícil de cobrir sem end-to-end

3. **Cobertura saudável** (≥ 80%):
   - Maioria dos módulos de domínio, infra e adapters

## Meta de Cobertura

- **Baseline atual**: 84%
- **Meta sugerida**: manter ≥ 80%
- **fail-under recomendado**: `--cov-fail-under=80`

## Comando Recomendado (CI)

```bash
pytest --cov=src/pyloto_corp --cov-report=term-missing --cov-fail-under=80
```
