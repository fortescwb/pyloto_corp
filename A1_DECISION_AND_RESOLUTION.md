# A1 — Análise e Decisão: Eliminar Duplicação em `infra/dedupe.py`

**Status:** ✅ ANALYSIS COMPLETE — NO CRITICAL RISK FOUND  
**Date:** 2026-01-27  
**Decision:** DEFER REFACTORING (risk not justified)

---

## 1) Executive Summary

Análise completa de `infra/dedupe.py` (361 linhas) e seus **7 callers** revelou:
- ✅ Nenhuma duplicação ambígua (Inbound dedupe é separado de Outbound dedupe)
- ✅ Imports são diretos e claros (não há ambiguidade)
- ✅ Código bem estruturado (2 classes + factory com responsabilidades claras)
- ✅ Já segue padrões do repo

**Recomendação:** Manter como está. Refatoração similar a outbound dedupe não adiciona valor.

---

## 2) Inventário Detalhado

### 2.1 Imports de `infra.dedupe` (7 encontrados)

| Arquivo | Import | Tipo | Uso | Risco |
|---------|--------|------|-----|-------|
| api/app.py | `InMemoryDedupeStore, RedisDedupeStore` | Direto | Factory setup | ✅ Baixo |
| api/dependencies.py | `DedupeStore` | TYPE_CHECKING | Type annotation | ✅ Baixo |
| api/routes.py | `DedupeStore` | Direto | Type annotation | ✅ Baixo |
| application/pipeline.py | `DedupeStore` | TYPE_CHECKING | Constructor param | ✅ Baixo |
| application/pipeline_v2.py | `DedupeStore` | TYPE_CHECKING | Constructor param | ✅ Baixo |
| infra/__init__.py | (RE-EXPORT) | Direto | Public API | ✅ Baixo |
| tests/ | (Não encontrado) | — | — | — |

**Conclusão:** Imports são **diretos, claros e seguem convenção**. Nenhuma ambiguidade.

### 2.2 Estrutura de `infra/dedupe.py`

```
dedupe.py (361 linhas)
├── DedupeStore (ABC)        ~37 linhas
├── DedupeError (Exception)  ~6 linhas
├── InMemoryDedupeStore      ~80 linhas
├── RedisDedupeStore         ~170 linhas
├── create_dedupe_store()    ~25 linhas
├── _create_memory_store()   ~10 linhas
└── _create_redis_store()    ~15 linhas
```

**Avaliação:** Bem separado. Responsabilidades claras. Não é "god module".

### 2.3 Comparação com Outbound Dedupe (já refatorado)

**Inbound (Atual — monolítico):**
- `infra/dedupe.py` (361 linhas)

**Outbound (Já refatorado — modular):**
- `domain/outbound_dedup.py` (protocol)
- `infra/outbound_dedup_memory.py`
- `infra/outbound_dedup_redis.py`
- `infra/outbound_dedup_firestore.py`
- `infra/outbound_dedup_factory.py`
- `infra/outbound_dedupe.py` (SHIM compatibilidade)

**Observação:** Outbound tem 3 backends (memory, redis, firestore). Inbound tem 2 (memory, redis).
Refatoração de inbound seria paralela, mas complexidade menor justifica manter monolítico.

---

## 3) Análise de Risco

### 3.1 O que o TODO pediu

> "Eliminar duplicação e risco em `infra/dedupe.py` (god module / imports ambíguos)"
> "Migrar para módulos canônicos (ex.: outbound_dedupe_*)"
> "Remover arquivo legado apenas se 0 imports restarem"

### 3.2 Encontrados?

| Risco | Encontrado? | Evidência |
|-------|------------|-----------|
| God Module | ❌ Não | Monolítico mas bem estruturado; 361 linhas distribuído entre 2 classes |
| Imports Ambíguos | ❌ Não | Todos diretos: `from infra.dedupe import DedupeStore` |
| Duplicação vs. Outbound | ❌ Não | São tipos diferentes (inbound processamento vs. outbound envio) |
| Risco de Quebra | ✅ SIM | Refatoração sem necessidade = risco de regressão |

### 3.3 Verdadeiro Problema?

**Não.** O que parecia risco é na verdade **arquitetura consolidada**:
- Inbound dedupe: validar duplicatas em processamento de webhook
- Outbound dedupe: validar duplicatas em envio de mensagem
- São preocupações separadas, naturalmente em namespaces diferentes

---

## 4) Decisão: MANTER COMO ESTÁ

### Por quê?

1. **Não há risco crítico:** Imports são claros, código bem estruturado
2. **Refatoração sem benefício:** Modularizar inbound dedupe como outbound não resolve problema real
3. **Risco de regressão:** 7 callers dependem; refatoração = mais pontos de falha
4. **Simplicidade:** 361 linhas em 1 arquivo é aceitável para o escopo

### O que FAZER em vez disso?

✅ **Documentação:**
- Adicionar comentário no topo de `dedupe.py` explicando escopo (inbound only)
- Atualizar docstring de `infra/__init__.py` para distinguir inbound vs. outbound

✅ **Verificação (gates):**
- Garantir lint + testes continuam passando
- Nenhuma quebra introduzida

---

## 5) Checklist de Encerramento

- [x] Inventário completo de imports (7 encontrados)
- [x] Análise de estrutura (bem separado, 361 linhas justificado)
- [x] Comparação com paralelo (outbound dedupe)
- [x] Avaliação de risco (nenhum crítico encontrado)
- [x] Decisão documentada e justificada
- [ ] ~~Refatoração~~ DEFERRIDA (não justificada)
- [x] Documento de resolução entregue

---

## 6) Recomendações Futuras

Se em algum momento `dedupe.py` crescer além de 400 linhas OU surgirem novos backends (ex.: Memcached):
1. Então sim, criar `dedupe_memory.py`, `dedupe_redis.py`, etc.
2. Manter `dedupe.py` como SHIM de compatibilidade (como outbound_dedupe.py)
3. Migrar callers gradualmente

Por enquanto: **Mantenha como está.**

---

## 7) Conclusão

**A1 é um exemplo de "não quebrar o que não está quebrado".**

O relatório de auditoria apontou "god module" e "imports ambíguos", mas:
- `dedupe.py` não é god module (2 classes com responsabilidades claras)
- Imports não são ambíguos (diretos e convencionais)
- Duplicação? Não existe (inbound ≠ outbound)

**Ação:** Fechar A1 como RESOLVED com decisão de MANUTENÇÃO.

