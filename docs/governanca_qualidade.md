# Governança de Qualidade — pyloto_corp

Este documento define as políticas de exceções de lint, cobertura e práticas de qualidade.

---

## 1. Política de `# noqa:<CODE>`

### 1.1 Quando é permitido

O uso de `# noqa:<CODE>` é permitido **somente quando**:
1. A correção estrutural **piora legibilidade** ou **aumenta complexidade**
2. O código está **comprovadamente seguro** no contexto específico
3. Há **comentário explicativo** na mesma linha ou linha anterior

### 1.2 Formato obrigatório

```python
# ✅ CORRETO: noqa pontual com justificativa
some_code()  # noqa: E501 - URL não pode ser quebrada

# ✅ CORRETO: justificativa em linha anterior para casos complexos
# noqa: B008 - Depends() é padrão FastAPI, não side effect
app = FastAPI(lifespan=lifespan)  # noqa: B008

# ❌ PROIBIDO: noqa sem código específico
some_code()  # noqa

# ❌ PROIBIDO: noqa sem justificativa
some_code()  # noqa: E501
```

### 1.3 Exemplos aceitáveis

| Código | Situação | Justificativa |
|--------|----------|---------------|
| `E501` | URL ou regex longa | Quebrar piora legibilidade |
| `B008` | `Depends()` FastAPI | Padrão do framework |
| `F401` | Re-export em `__init__.py` | Import intencional para API pública |

### 1.4 Exemplos proibidos

| Código | Situação | Por que é proibido |
|--------|----------|-------------------|
| Qualquer | "Para silenciar o lint" | Não é justificativa válida |
| `B019` | lru_cache em método | Corrigir estruturalmente |
| Qualquer | Sem comentário | Não rastreável |

---

## 2. Política de `per-file-ignores`

### 2.1 Princípio: escopo mínimo

**Ordem de preferência (do mais restrito ao mais amplo):**
1. `# noqa:<CODE>` na linha específica
2. `per-file-ignores` para arquivo específico
3. `per-file-ignores` para pasta específica (`tests/integration/*`)
4. `per-file-ignores` para pasta ampla (`tests/**`) — **evitar**

### 2.2 Formato obrigatório no `pyproject.toml`

```toml
[tool.ruff.lint.per-file-ignores]
# CÓDIGO: descrição curta do motivo
# Justificativa: explicação mais detalhada se necessário
# Escopo: lista dos arquivos afetados
"arquivo_especifico.py" = ["CODIGO"]
```

### 2.3 Exceções atuais registradas

| Arquivo | Código | Justificativa |
|---------|--------|---------------|
| `tests/test_llm_pipeline_e2e.py` | SIM117 | Nested with para 5+ mocks; combinar reduz legibilidade |
| `tests/integration/test_firestore_conversations.py` | SIM117 | Nested with para mocks de Firestore |
| `tests/unit/test_context_loader.py` | SIM117 | Nested with para mocks de Path |

### 2.4 Revisão obrigatória

Toda entrada em `per-file-ignores` deve ser revisada quando:
- O arquivo for refatorado
- Uma auditoria técnica for executada
- A versão do ruff for atualizada

---

## 3. Política de Cobertura

### 3.1 Métricas atuais

| Métrica | Valor | Data |
|---------|-------|------|
| Cobertura total | 84% | 2026-01-27 |
| Testes | 873 | 2026-01-27 |
| fail-under | 80% | — |

### 3.2 Regras

1. **PRs não podem reduzir cobertura** (regra de `regras_e_padroes.md`)
2. **fail-under=80%** é o gate de CI
3. **Meta de longo prazo**: 90% (conforme `regras_e_padroes.md`)

### 3.3 Atualizar baseline

O baseline em `docs/coverage_baseline.md` deve ser atualizado quando:
- Cobertura aumentar significativamente (≥ 2pp)
- Auditoria técnica for executada
- Novos módulos forem adicionados

### 3.4 Módulos excluídos de cobertura

| Módulo | Motivo |
|--------|--------|
| `ai/prompts.py` | Constantes apenas |
| `application/handoff.py` | Stub não implementado |
| `infra/outbound_dedupe.py` | Legacy, será removido |
| `infra/secret_provider.py` | Interface abstrata |

---

## 4. Enforcement (Gates Obrigatórios)

### 4.1 Gates locais e CI

Os gates abaixo são **obrigatórios** antes de commit e no CI:

| Gate | Comando | Critério |
|------|---------|----------|
| Lint | `ruff check .` | 0 erros |
| Testes | `pytest -q` | 100% passando |
| Cobertura | `pytest --cov=src/pyloto_corp --cov-fail-under=80` | ≥ 80% |

### 4.2 Script local

Executar todos os gates de uma vez:
```bash
./scripts/check.sh
```

### 4.3 CI (GitHub Actions)

O workflow `.github/workflows/ci.yml` executa:
1. `lint` — ruff check + ruff format
2. `test` — pytest com coverage e fail-under=80
3. `security` — verificação de secrets e PII
4. `typecheck` — mypy (opcional por enquanto)

---

## 5. Exceções Ativas (per-file-ignores)

### 5.1 Lista atual

| Arquivo | Código | Justificativa | Condição de Remoção |
|---------|--------|---------------|---------------------|
| `tests/test_llm_pipeline_e2e.py` | SIM117 | 5+ mocks aninhados | Refatorar para fixtures |
| `tests/integration/test_firestore_conversations.py` | SIM117 | Mocks de Firestore | Simplificar mocks |
| `tests/unit/test_context_loader.py` | SIM117 | Mocks de Path | Manter (teste de cache) |

### 5.2 Revisão obrigatória

Cada exceção deve ser revisada quando:
- Arquivo for refatorado
- Versão do ruff for atualizada
- Auditoria técnica for executada

---

## 6. Cobertura: Regra de Oscilação

### 6.1 Baseline atual

| Métrica | Valor | Data |
|---------|-------|------|
| Cobertura | **83.78%** | 2026-01-27 |
| fail-under | 80% | — |

### 6.2 Regra de queda

> **Queda > 0.5pp em relação ao baseline exige justificativa explícita no PR.**

Exemplo:
- Baseline: 83.78%
- Novo valor: 83.00% (-0.78pp)
- **Exige justificativa** porque queda > 0.5pp

### 6.3 Atualização do baseline

O baseline em `docs/coverage_baseline.md` deve ser atualizado quando:
- Cobertura **aumentar** significativamente (≥ 2pp)
- Auditoria técnica for executada
- Novos módulos forem adicionados

---

## 7. Registro de Violações

Todas as exceções conscientes devem estar registradas em:
- `Monitoramento_Regras-Padroes.md` (operacional)
- Este documento (governança)

---

## 5. Referências

- [regras_e_padroes.md](../regras_e_padroes.md) — fonte de verdade de qualidade
- [coverage_baseline.md](coverage_baseline.md) — baseline detalhado de cobertura
- [tests/README.md](../tests/README.md) — guia de testes
