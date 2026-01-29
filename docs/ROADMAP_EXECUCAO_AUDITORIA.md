# ROADMAP DE EXECUÇÃO — Auditoria pyloto_corp

**Documento:** Plano de Ação Incremental  
**Data:** 29 de janeiro de 2026  
**Público:** Tech Lead, Arquitetura, Executor

---

## 1. MATRIX DE RISCOS × BENEFÍCIOS

### Por Iniciativa

| Iniciativa | Risco | Benefício | ROI | Prioritário? |
|-----------|-------|----------|-----|-------------|
| **Consolidar 3 pipelines** | Médio (async/sync mismatch) | Alto (-1243 dup lines) | **9/10** | ✅ SIM |
| **PipelineConfig (18→1 param)** | Baixo (refactor puro) | Alto (testabilidade) | **9/10** | ✅ SIM |
| **Domain/protocols** | Baixo (novo código) | Alto (boundaries) | **8/10** | ✅ SIM |
| **SessionManager/DedupeManager** | Médio (novo contrato) | Médio (simplicidade) | **7/10** | ⚠️ Depois |
| **Split normalizer/secrets/dedupe** | Baixo (refactor puro) | Médio (SRP) | **6/10** | ⚠️ Depois |
| **Circuit Breaker** | Médio (nova dependência) | Médio (resiliência) | **5/10** | ⚠️ Depois |
| **Otto validation** | Baixo (adição simples) | Baixo (completude) | **6/10** | ⚠️ Nice-to-have |

---

## 2. TIMELINE DETALHADO

### Sprint N (Preparação)

**Objetivo:** Setup seguro para refatoração. Zero impacto em produção.

#### Tarefas

| ID | Tarefa | Owner | Esforço | Blocker | Gate |
|----|--------|-------|--------|---------|------|
| **P1-1** | Criar `domain/protocols/dedupe.py` | Dev-A | 2h | Nenhum | pytest |
| **P1-2** | Criar `domain/protocols/session.py` | Dev-A | 2h | P1-1 | pytest |
| **P1-3** | Criar `domain/protocols/secret_provider.py` | Dev-B | 2h | Nenhum | pytest |
| **P1-4** | Atualizar `infra/__init__.py` (shims) | Dev-A | 1h | P1-1,P1-2,P1-3 | import check |
| **P1-5** | Criar `docs/TARGET_ARCHITECTURE.md` | Tech-Lead | 4h | Nenhum | Revisão |
| **P1-6** | Escrever testes de import (import_test.py) | Dev-C | 2h | Nenhum | pytest |

**Resultado esperado:**
```
✅ domain/protocols/ com 3 abstrações
✅ infra/ com re-exports (shims)
✅ Nenhuma mudança no fluxo vivo
✅ Testes passam: pytest, ruff, mypy
```

**Risco:** Nenhum (código novo, não toca runtime)  
**Timeline:** 1 dia de dev puro

---

### Sprint N+1 (Consolidação Pipeline)

**Objetivo:** 1 pipeline em lugar de 3. Async-first, sync wrapper.

#### Tarefas

| ID | Tarefa | Owner | Esforço | Blocker | Gate |
|----|--------|-------|--------|---------|------|
| **P2-1** | Criar `application/pipeline_config.py` | Dev-A | 3h | P1-4 | pytest |
| **P2-2** | Refatorar `pipeline.py`: async-first | Dev-A | 8h | P2-1 | pytest, cov 90% |
| **P2-3** | Merge logic de `pipeline_v2.py` → `pipeline.py` | Dev-B | 6h | P2-2 | pytest, diff review |
| **P2-4** | Merge logic de `pipeline_async.py` → `pipeline.py` | Dev-B | 4h | P2-3 | pytest, diff review |
| **P2-5** | Wrapper sync: `asyncio.run()` | Dev-A | 1h | P2-4 | pytest |
| **P2-6** | Atualizar testes (consolidar 3 → 1) | Dev-C | 6h | P2-5 | coverage 90% |
| **P2-7** | Update `api/routes.py` (imports) | Dev-A | 1h | P2-4 | ruff, pytest |
| **P2-8** | Update `app.py` (factories) | Dev-A | 1h | P2-1 | ruff, pytest |
| **P2-9** | Deprecar `pipeline_v2.py`, `pipeline_async.py` | Dev-A | 0.5h | P2-8 | manual check |

**Resultado esperado:**
```
✅ application/pipeline.py: versão única (async-first)
✅ pipeline_v2.py, pipeline_async.py: deprecated (com warning)
✅ Testes: consolidados, coverage ≥90%
✅ Ruff, mypy, pytest: 100% pass
```

**Risco:** Médio (consolidação de lógica)
- Mitigação: Branch separado, testes ao lado (antigos + novos)
- Validação: E2E com Cloud Run staging

**Timeline:** 2–3 dias de dev + 1 dia validação

---

### Sprint N+2 (Config & Dependency Injection)

**Objetivo:** `PipelineConfig` dataclass (18 params → 1).

#### Tarefas

| ID | Tarefa | Owner | Esforço | Blocker | Gate |
|----|--------|-------|--------|---------|------|
| **P3-1** | Criar `@dataclass PipelineConfig` | Dev-A | 2h | P2-1 | pytest |
| **P3-2** | Refatorar `WhatsAppInboundPipeline.__init__()` | Dev-A | 3h | P3-1 | pytest |
| **P3-3** | Update `api/dependencies.py` (builder) | Dev-A | 2h | P3-2 | pytest |
| **P3-4** | Update `app.py` (factory) | Dev-A | 1h | P3-2 | ruff |
| **P3-5** | Testes de `PipelineConfig` | Dev-C | 3h | P3-1 | pytest |

**Resultado esperado:**
```python
# Antes (18 parâmetros)
pipeline = WhatsAppInboundPipeline(
    dedupe, session, orchestrator, flood_detector,
    state_selector_client, state_selector_model, ..., # 14 mais
)

# Depois (1 parâmetro)
config = PipelineConfig(...)
pipeline = WhatsAppInboundPipeline(config)
```

**Risco:** Baixo (refactor puro)  
**Timeline:** 1 dia de dev

---

### Sprint N+3 (Extras: SessionManager, DedupeManager)

**Opcional.** Se houver tempo depois de P0.

#### Tarefas

| ID | Tarefa | Owner | Esforço | Blocker | Gate |
|----|--------|-------|--------|---------|------|
| **P4-1** | Criar `application/managers/session_manager.py` | Dev-B | 4h | P2-4 | pytest |
| **P4-2** | Criar `application/managers/dedupe_manager.py` | Dev-B | 3h | P2-4 | pytest |
| **P4-3** | Refatorar `pipeline.py` (usar managers) | Dev-A | 5h | P4-1,P4-2 | pytest, cov 90% |
| **P4-4** | Testes de managers | Dev-C | 4h | P4-1,P4-2 | pytest |

**Resultado esperado:**
```
✅ SessionManager: encapsula session_store
✅ DedupeManager: encapsula dedupe_store
✅ Pipeline mais simples (usar managers em lugar de direto)
```

**Risco:** Médio (novo contrato)  
**Timeline:** 2 dias (opcional)

---

### Sprint N+4–N+6 (SRP Splits)

**Opcional.** Após P0–P1.

#### Tarefas (Alta Nível)

| Arquivo | Split | Esforço | Risk |
|---------|-------|--------|------|
| `normalizer.py` (306→2×150) | extractor + sanitizer | 4h | Baixo |
| `secrets.py` (268→3×90) | provider + env + gcp | 4h | Baixo |
| `dedupe.py` (386→4×100) | store + memory + redis + firestore | 6h | Baixo |
| `whatsapp_message_types.py` | monitorar (239 OK por enquanto) | — | — |

**Gate:** pytest, ruff, coverage 90%

---

## 3. CRITÉRIOS DE "DONE" POR FASE

### Fase 1 (Preparação)

- [ ] `domain/protocols/dedupe.py` existe (cópia de contrato abstrato)
- [ ] `domain/protocols/session.py` existe
- [ ] `domain/protocols/secret_provider.py` existe
- [ ] `infra/__init__.py` re-exporta protocols (shims)
- [ ] `pytest tests/` passa (228+ testes)
- [ ] `ruff check src/pyloto_corp` — OK
- [ ] `mypy src/pyloto_corp --strict` — OK
- [ ] Docs: `TARGET_ARCHITECTURE.md` criado

### Fase 2 (Consolidação)

- [ ] `application/pipeline_config.py` existe
- [ ] `application/pipeline.py` é async-first
- [ ] `pipeline_v2.py`, `pipeline_async.py` marcadas como deprecated
- [ ] Todos 3 fluxos (sync, async, v2) testados e passing
- [ ] `pytest tests/application/test_pipeline.py` — 100% pass
- [ ] `coverage` — ≥90%
- [ ] E2E test em staging — ✅ PASS
- [ ] `api/routes.py` e `app.py` atualizados

### Fase 3 (Config & DI)

- [ ] `PipelineConfig` dataclass criada
- [ ] `WhatsAppInboundPipeline.__init__()` refatorado (1 param)
- [ ] `api/dependencies.py` atualizado
- [ ] Testes de config — ✅ PASS
- [ ] Sem impacto no comportamento vivo (testes E2E passam)

### Fase 4 (Managers) — Opcional

- [ ] `SessionManager` criada
- [ ] `DedupeManager` criada
- [ ] Pipeline usa managers em lugar de direto
- [ ] Testes de managers — ✅ PASS

### Fase 5–6 (Splits) — Opcional

- [ ] Arquivos <200 linhas (exceto justificados)
- [ ] Testes de novos módulos — ✅ PASS
- [ ] Imports reexportados em `__init__.py`

---

## 4. GATES DE QUALIDADE (CI/CD)

```bash
# Gate 1: Sintaxe e tipos
ruff check src/ tests/
mypy src/ --strict
pylint src/ --threshold 8.0

# Gate 2: Testes
pytest tests/ -v --cov=src/pyloto_corp --cov-report=html --cov-fail-under=90

# Gate 3: Boundaries (imports)
python scripts/check_imports.py  # Ensure domain/ ≠ infra/

# Gate 4: Tamanho
python scripts/check_line_counts.py --max-lines 200 --exclude justifications.txt

# Gate 5: E2E (staging)
pytest tests/e2e/ -v -m "not slow"
```

---

## 5. BACKOUT STRATEGY

**Se algo quebrar:**

1. **Rollback imediato:**
   ```bash
   git revert <commit>
   push --force
   ```

2. **Feature flag (contingência):**
   ```python
   if settings.use_old_pipeline:
       pipeline = OldPipelineV2()
   else:
       pipeline = NewConsolidatedPipeline()
   ```

3. **Shims mantêm compatibilidade:**
   - `from pyloto_corp.application.pipeline_v2 import WhatsAppInboundPipeline`
   - Still works (delegação para nova impl)

---

## 6. COMUNICAÇÃO

### Para Dev Team
- [ ] Kick-off meeting: Explain roadmap, risks, timeline
- [ ] Weekly sync: Status updates, blockers
- [ ] Code review: Duplo-check de consolidação

### Para Ops/DevOps
- [ ] Prepare staging canário (nova pipeline)
- [ ] Rollback plan documentado
- [ ] Alerting configurado (se novo pipeline em prod)

### Para Product
- [ ] Impacto zero em UX (interno)
- [ ] Timeline: 3–4 sprints total
- [ ] Benefit: -40% manutenção, ground para LLM v2

---

## 7. MÉTRICAS DE SUCESSO

| Métrica | Baseline | Target | Timeline |
|---------|----------|--------|----------|
| **Linhas duplicadas** | 1243 | <50 | Fase 2 |
| **Arquivos >200 linhas** | 4 | 0–1 | Fase 5–6 |
| **Parâmetros pipeline** | 18 | 1 | Fase 3 |
| **Test coverage** | 92% | ≥92% | Contínuo |
| **CI/CD time** | ~8min | <6min | Fase 5–6 |
| **Custo manutenção** | 100% | ~60% | Post-execução |

---

## 8. RISKS & MITIGATIONS

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| **Async/sync mismatch** | Medium | High | Branch + testes paralelos |
| **Pipeline não inicia** | Low | High | Feature flag + shims |
| **Import cycle** | Low | High | Static analysis (ruff) |
| **Performance regression** | Low | Medium | Benchmarks pré/pós |
| **Timeout LLM não tesado** | Low | Low | Adicionar testes mock |

---

## 9. PRÓXIMOS PASSOS

### Imediato (Esta semana)

- [ ] Tech Lead: Revisar este documento
- [ ] Dev Lead: Aprovar timeline
- [ ] Kick-off meeting: Explicar a time

### Sprint N (Próxima semana)

- [ ] Comece Fase 1 (Preparação)
- [ ] Dev-A cria `domain/protocols/`
- [ ] Dev-C escreve testes de import

### Sprint N+1 (2 semanas depois)

- [ ] Comece Fase 2 (Consolidação)
- [ ] Dev-A refactora `pipeline.py` em branch
- [ ] Daily standups (blockers, risks)

---

## APÊNDICE A: Verificação de Imports (Script)

```python
# scripts/check_imports.py
import ast
import os
from pathlib import Path

DOMAIN_PATH = "src/pyloto_corp/domain/"
INFRA_PATH = "src/pyloto_corp/infra/"

def check_domain_imports():
    """Ensure domain/ never imports from infra/ or adapters/"""
    for py_file in Path(DOMAIN_PATH).rglob("*.py"):
        with open(py_file) as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and (
                    "infra" in node.module or
                    "adapters" in node.module or
                    "application" in node.module
                ):
                    print(f"❌ VIOLATION: {py_file} imports {node.module}")
                    return False
    print("✅ OK: domain/ clean")
    return True

if __name__ == "__main__":
    exit(0 if check_domain_imports() else 1)
```

---

**Fim do Roadmap de Execução**

**Status:** Pronto para aprovação e início (Fase 1)
