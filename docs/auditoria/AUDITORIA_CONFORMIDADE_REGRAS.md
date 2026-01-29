# 📋 Auditoria de Conformidade - Regras e Padrões

**Data**: 27 de janeiro de 2026  
**Objetivo**: Verificar que módulos de alto risco (< 80% coverage) seguem [regras_e_padroes.md](regras_e_padroes.md)  
**Severidade**: CRÍTICO - Bloqueia aceite de PR

---

## 🚨 Executive Summary

### Violações Encontradas: **5 CRÍTICAS (§7.3)**

**Módulos sem testes (0% coverage):**
1. ❌ `message_builder.py` - 108 linhas - HTTP/orquestração
2. ❌ `outbound.py` - 80 linhas - HTTP layer crítica
3. ❌ `context_loader.py` - 92 linhas - AI pipeline
4. ❌ `fsm_engine.py` - 43 linhas - Máquina de estado
5. ❌ `openai_client.py` - 52 linhas - Cliente OpenAI

### Critério de Aceite (§10 - Definition of Done)

> "Um código só é considerado pronto quando:
> - Cumpre todos os limites estruturais
> - **Passa em lint, testes e cobertura mínima** ✗ FALHA
> - Possui testes cobrindo happy path, bordas e erros ✗ FALHA
> - Não introduz PII em logs
> - Não degrada métricas existentes

**Status: NÃO PRONTO PARA MERGE**

---

## 📊 Detalhes por Severidade

### 🔴 CRÍTICO (§7.3 - Cobertura de Código)

Seção aplicável:
> "Cobertura mínima global: **90%**  
> Alvo recomendado: **90–100%**  
> PRs **não podem reduzir** cobertura existente"

#### Violação 1: `message_builder.py`

| Aspecto | Status | Detalhe |
|---------|--------|---------|
| **Linhas** | ⚠️ 329 | Ao limite de 200 (§2.1) |
| **Cobertura** | ❌ 0% | Violação de §7.3 (requer ≥80%) |
| **Responsabilidades** | ❌ 8 funções | Possível violação de §2.2 (SRP) |
| **Testes** | ❌ 0 | Sem happy path, bordas ou erros |
| **Camada** | ⚠️ Orquestração | Interface crítica |

**Impacto**: Bloqueia aceite. Qualquer PR com este arquivo precisa de ≥80% coverage.

**Solução**: Criar `test_message_builder.py` com ~30 testes cobrindo:
- Happy path: envelope assembly
- Edge cases: invalid builders, missing fields
- Error handling: exceptions

---

#### Violação 2: `outbound.py`

| Aspecto | Status | Detalhe |
|---------|--------|---------|
| **Linhas** | ✅ 80 | Dentro do limite (§2.1) |
| **Cobertura** | ❌ 0% | Violação de §7.3 (requer ≥80%) |
| **Responsabilidade** | ✅ 1 (HTTP) | SRP OK |
| **Testes** | ❌ 0 | Sem testes |
| **Camada** | 🔴 Critical | HTTP layer (interface com WhatsApp) |

**Impacto**: Layer crítica. Falhas aqui afetam produção.

**Solução**: Criar `test_outbound.py` com ~25 testes cobrindo:
- Happy path: send_message success
- Error cases: Meta API errors, timeouts, retries
- Mock: `unittest.mock` para WhatsApp API

---

#### Violação 3: `context_loader.py`

| Aspecto | Status | Detalhe |
|---------|--------|---------|
| **Linhas** | ⚠️ 221 | Ao limite (§2.1) |
| **Cobertura** | ❌ 0% | Violação de §7.3 (requer ≥80%) |
| **Responsabilidade** | ⚠️ 3 métodos | Carregamento + transformação |
| **Testes** | ❌ 0 | Sem testes |
| **Camada** | ⚠️ Application | Orquestração AI |

**Impacto**: Crítica para AI pipeline.

**Solução**: Criar `test_context_loader.py` com ~20 testes cobrindo:
- Loading: Firestore, Redis, memory contexts
- Transformations: field mapping, filtering
- Error handling: missing data, corrupted entries

---

#### Violação 4: `fsm_engine.py`

| Aspecto | Status | Detalhe |
|---------|--------|---------|
| **Linhas** | ✅ 43 | Dentro do limite (§2.1) |
| **Cobertura** | ❌ 0% | Violação de §7.3 (requer ≥80%) |
| **Responsabilidade** | ✅ 1 (FSM) | SRP OK |
| **Testes** | ❌ 0 | Sem testes |
| **Camada** | 🔴 Critical | Estado machine (sessão) |

**Impacto**: Máquina de estado. Bugs aqui causam perda de sessão.

**Solução**: Criar `test_fsm_engine.py` com ~15 testes cobrindo:
- State transitions: valid paths
- Invalid transitions: error cases
- Constraints: terminal states, guardrails

---

#### Violação 5: `openai_client.py`

| Aspecto | Status | Detalhe |
|---------|--------|---------|
| **Linhas** | ✅ 52 | Dentro do limite (§2.1) |
| **Cobertura** | ❌ 0% | Violação de §7.3 (requer ≥80%) |
| **Responsabilidade** | ✅ 1 (OpenAI) | SRP OK |
| **Testes** | ❌ 0 | Sem testes |
| **Camada** | ⚠️ Adapter | Integração externa |

**Impacto**: Crítica para IA. Falhas degradam qualidade de resposta.

**Solução**: Criar `test_openai_client.py` com ~20 testes cobrindo:
- API calls: completion, parsing
- Error handling: rate limits, timeouts
- Mock: `unittest.mock` para OpenAI client

---

### 🟠 ALTO (§2.1-2.3 - Estrutura e Separação de Camadas)

#### Violação A: `message_builder.py` - SRP

| Regra | Texto | Status |
|-------|-------|--------|
| §2.2 | "Cada arquivo deve responder claramente... Qual problema específico?" | ❌ FALHA |
| Detalhado | "Múltiplas responsabilidades:" | 8 funções sem agrupamento claro |

**Impacto**: Dificulta testes unitários e manutenção.

**Ação**: Refatorar para separar concerns (builders vs orchestration) ou adicionar testes muito detalhados.

---

#### Violação B: `whatsapp_message_types.py` - SRP

| Regra | Texto | Status |
|-------|-------|--------|
| §2.2 | "Responsabilidade única" | ❌ FALHA |
| Detalhado | "19 classes de modelos (Pydantic)" | Contém múltiplos tipos de domínio |

**Impacto**: Difícil testar isoladamente. Mais de 200 linhas de modelos.

**Ação**: Manter estrutura, mas garantir testes para cada tipo.

---

## 📋 Matriz de Conformidade

| Módulo | §2.1 | §2.2 | §2.3 | §7.3 | §10 DoD | Status |
|--------|------|------|------|------|---------|---------|
| message_builder.py | ⚠️ | ❌ | ✅ | ❌ | ❌ | 🔴 FAIL |
| outbound.py | ✅ | ✅ | ✅ | ❌ | ❌ | 🔴 FAIL |
| context_loader.py | ⚠️ | ✅ | ⚠️ | ❌ | ❌ | 🔴 FAIL |
| fsm_engine.py | ✅ | ✅ | ✅ | ❌ | ❌ | 🔴 FAIL |
| openai_client.py | ✅ | ✅ | ✅ | ❌ | ❌ | 🔴 FAIL |

---

## 🔧 Plano de Remediação

### PRIORITY 1: Criar Testes (§7.3)

**Deadline**: ANTES de qualquer merge destes módulos

| Módulo | Testes | Effort | Bloqueador |
|--------|--------|--------|-----------|
| message_builder.py | ~30 | 3h | SIM |
| outbound.py | ~25 | 2-3h | SIM |
| context_loader.py | ~20 | 2h | SIM |
| fsm_engine.py | ~15 | 1-2h | SIM |
| openai_client.py | ~20 | 2h | SIM |
| **TOTAL** | **~110** | **10-12h** | **CRÍTICO** |

### PRIORITY 2: Refatoração (§2.1-2.3)

**Não bloqueia**, mas melhora qualidade:

1. `message_builder.py`: Considerar split se funções crescerem
2. `whatsapp_message_types.py`: Manter, mas cobrir com testes

---

## ✅ Checklist de Validação

Para cada módulo listado acima:

- [ ] Arquivo de teste criado (`test_*.py`)
- [ ] Testes covering happy path (≥1 teste)
- [ ] Testes covering edge cases (≥1 teste por tipo)
- [ ] Testes covering error cases (≥1 teste)
- [ ] Coverage ≥80% validado via `pytest --cov`
- [ ] Linting passa (`ruff check`)
- [ ] Sem introdução de PII em logs
- [ ] Sem redução de cobertura existente
- [ ] Documentação atualizada

---

## 📌 Observações Finais

### Conformidade Atual

```
Global Coverage:    54% (meta: 90%) ❌
Critical Modules:   0% (meta: 80%) ❌
Definition of Done: NOT MET ❌
```

### Impacto

- **Risco de produção**: ALTO (HTTP layer, AI pipeline, FSM sem cobertura)
- **Custo de manutenção**: ALTO (código sem testes é débito técnico)
- **Velocidade de bug-fix**: LENTA (sem testes, sem segurança de refactoring)

### Próximos Passos

1. ✅ Criar testes para 5 módulos críticos (10-12h)
2. ✅ Validar coverage ≥80% por módulo
3. ✅ Atualizar `Monitoramento_Regras-Padroes.md`
4. 📋 Considerar refactoring estrutural (fase 2)

---

**Relatório gerado**: 27 jan 2026  
**Responsável**: Auditoria Automática  
**Próxima revisão**: Após implementação dos testes
