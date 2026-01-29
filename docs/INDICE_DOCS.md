# Índice de Documentação — pyloto_corp

**Data de Reorganização:** 29 de janeiro de 2026

---

## 📍 Estrutura da Raiz (Apenas Essencial)

**Documentação Normativa Ativa:**
- `regras_e_padroes.md` — Padrões de qualidade, estrutura, SRP
- `Funcionamento.md` — Fluxo funcional, estados, outcomes, validações
- `README.md` — Overview do projeto
- `Monitoramento_Regras-Padroes.md` — Compliance e observabilidade
- `Sprint_1-2_Auditoria.md` — Plano de execução Sprint 1-2 (NO RISK)

**Configuração & Build:**
- `.env`, `.env.exemplo` — Variáveis de ambiente
- `Dockerfile`, `.dockerignore` — Build e deploy
- `.gitignore` — Exclusões git
- `pyproject.toml` — Dependências Python
- `QUICKSTART_DEPLOY.sh` — Deploy script

---

## 📚 Estrutura em `/docs/`

### 📊 `auditoria/`
Documentação técnica da auditoria profunda (29/01/2026):
- `AUDITORIA_PROFUNDA_29JAN_2026.md` — Audit técnico completo
- `SUMARIO_EXECUTIVO_AUDITORIA_29JAN.md` — Executive summary
- `ROADMAP_EXECUCAO_AUDITORIA.md` — Roadmap de execução
- `README_AUDITORIA_29JAN.md` — Quick-start auditoria
- `INDICE_AUDITORIA_FINAL_29JAN.md` — Navegação auditoria
- `ENTREGA_AUDITORIA_29JAN_2026.md` — Delivery report
- Achados específicos: A1_*.md, A4_*.md
- Relatórios anteriores: auditoria_*.md, AUDITORIA_CONFORMIDADE_*.md

### 📋 `planos/`
Planos, roadmaps e TODOs:
- `ROADMAP_FASE6_E_ALEM.md` — Roadmap pós-sprint 2
- `QUICK_START_FSM_LLM.md` — FSM/LLM integration guide
- `PRODUCAO_FINAL_STRATEGY.md` — Production strategy
- `TODO_*.md` — Tarefas planejadas
- `DEPLOYMENT_STAGING.md` — Staging checklist
- `whatsapp_tests_fixed.sh` — Test scripts

### 📈 `relatorios/`
Relatórios de progresso, cobertura e testes:
- `COBERTURA_PROGRESSO.md` — Coverage tracking
- `RELATORIO_COBERTURA_*.md` — Coverage reports
- `RELATORIO_TESTES_WHATSAPP_API.md` — WhatsApp API test results

### ⚙️ `implementacao/`
Documentação de implementações completadas:
- `FASE_1_2_COMPLETADA.md` — Fase 1-2 recap
- `FASE_3A_3B_COMPLETADA.md` — Fase 3A-3B recap
- `RESUMO_EXECUCAO_C*.md` — Execution summaries per commit
- `IMPLEMENTACAO_PIPELINE_ASYNC.md` — Async pipeline docs
- `GUARDIAO_REFATORACOES_25JAN.md` — Boundary refactoring docs

### 🔍 `investigacao/`
Análises, arquitetura, conclusões:
- `FSM_LLM_ARCHITECTURE_PYLOTO_CORP.md` — Architecture deep-dive
- `M2_L1_CORRELATION_FALLBACK.md` — Correlation fallback analysis
- `CONCLUSAO_*.md` — Conclusões de investigações

### 📁 Subdiretórios Adicionais
- `firestore/` — Schema e diagrama Firestore
- `institucional/` — Contexto institucional, vertentes Pyloto
- Outros: configs, análises de integração, etc.

---

## 🎯 Recomendação de Leitura

### Para Novos Contribuidores
1. Leia na raiz: `README.md` → `Funcionamento.md` → `regras_e_padroes.md`
2. Entenda o Sprint atual: `/docs/auditoria/README_AUDITORIA_29JAN.md`

### Para Refatoração (Sprint 1-2)
1. Referência: `/docs/auditoria/AUDITORIA_PROFUNDA_29JAN_2026.md` (Achados)
2. Plano detalhado: `/docs/auditoria/ROADMAP_EXECUCAO_AUDITORIA.md`
3. Execução: `Sprint_1-2_Auditoria.md` (raiz)

### Para Troubleshooting
1. Arquitetura: `/docs/investigacao/FSM_LLM_ARCHITECTURE_PYLOTO_CORP.md`
2. Cobertura: `/docs/relatorios/COBERTURA_PROGRESSO.md`
3. Testes: `/docs/relatorios/RELATORIO_TESTES_WHATSAPP_API.md`

---

## ✅ Checklist de Limpeza Realizada

- ✅ Documentos de auditoria movidos para `docs/auditoria/`
- ✅ Planos/roadmaps movidos para `docs/planos/`
- ✅ Relatórios movidos para `docs/relatorios/`
- ✅ Implementações movidas para `docs/implementacao/`
- ✅ Análises movidas para `docs/investigacao/`
- ✅ Raiz mantém apenas 5 docs normativos + config
- ✅ Estrutura clara e navegável

---

## 📞 Próximos Passos

**Sprint 1-2 Execution:** Seguir `Sprint_1-2_Auditoria.md` na raiz

