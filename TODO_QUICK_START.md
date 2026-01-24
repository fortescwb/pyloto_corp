# 📋 Guia Rápido dos TODO Lists

## Estrutura Criada

Foram criados **6 documentos TODO** organizados hierarquicamente para guiar a implementação do `pyloto_corp` em produção:

---

## 📑 Documentos Criados

### 🎯 **[TODO_00_MASTER_INDEX.md](TODO_00_MASTER_INDEX.md)** — COMECE AQUI
**Arquivo de índice e planejamento geral**

- Visão geral de todos os TODO lists
- Dependências entre fases
- Cronograma sugerido (6 semanas)
- Oportunidades de paralelização
- Template de status para acompanhamento

👉 **Primeiro documento a ler**

---

### 🏗️ **[TODO_01_INFRAESTRUTURA_E_SERVICOS.md](TODO_01_INFRAESTRUTURA_E_SERVICOS.md)**
**Preparar infraestrutura em GCP e pipeline CI/CD**

**Conteúdo:**
- Configurar Ambiente de Nuvem (projeto GCP, Firestore, Cloud Storage, Redis, Pub/Sub)
- Gerenciar Segredos (Secret Manager, refresh de token, validação de Graph API v24.0)
- Configurar CI/CD (linting, testing, gate de auditoria, deploy automático)

**Tarefas:** 12 principais
**Duração Estimada:** 3-5 dias
**Dependências:** Nenhuma

---

### ✅ **[TODO_02_REFATORA_VALIDADORES_OUTBOUND.md](TODO_02_REFATORA_VALIDADORES_OUTBOUND.md)**
**Refatorar validadores e implementar cliente de envio**

**Conteúdo:**
- Refatorar Validadores (módulo de constantes, 5 validadores especializados, orquestrador, testes >90%)
- Refatorar Outbound (WhatsAppHttpClient com retry/backoff, MediaUploader, TemplateManager, FlowSender)
- Integração com deduplicação

**Tarefas:** 15 principais
**Duração Estimada:** 5-7 dias
**Dependências:** TODO_01

---

### 💾 **[TODO_03_PERSISTENCIA_SESSAO_PIPELINE.md](TODO_03_PERSISTENCIA_SESSAO_PIPELINE.md)**
**Implementar persistência, sessão e pipeline completo**

**Conteúdo:**
- Refatorar Exportação (extrair métodos, implementar GcsHistoryExporter)
- Persistência e Stores (ConversationStore, UserProfileStore, AuditLogStore com hash encadeado, RedisDedupeStore)
- Sessão e Pipeline (SessionManager com timeouts, pipeline.py completo, webhook refatorado)
- IA e Orquestração (prompts, AIOrchestrator com LLM + fallback, lead scoring)

**Tarefas:** 18 principais
**Duração Estimada:** 7-10 dias
**Dependências:** TODO_01, TODO_02

---

### 🧪 **[TODO_04_FLOWS_TESTES_OBSERVABILIDADE.md](TODO_04_FLOWS_TESTES_OBSERVABILIDADE.md)**
**Implementar Flows, testes abrangentes e observabilidade completa**

**Conteúdo:**
- WhatsApp Flows (endpoint `/flows/data`, criptografia AES-GCM, FlowDataHandler, TemplateStore)
- Testes e Qualidade (unitários >90%, integração de pipeline, carga com p95<2s, assinatura)
- Observabilidade (logging estruturado, métricas, alertas, dashboards, CORS, rate limiting, criptografia, LGPD/GDPR)

**Tarefas:** 20+ principais
**Duração Estimada:** 8-12 dias
**Dependências:** TODO_02, TODO_03

---

### 🚀 **[TODO_05_DEPLOY_E_POS_DEPLOY.md](TODO_05_DEPLOY_E_POS_DEPLOY.md)**
**Deploy em staging/produção e manutenção contínua**

**Conteúdo:**
- Deploy Inicial em Staging (config, Cloud Run, webhook, E2E, carga, validações)
- Ajustes Finais (documentação, pentest, LGPD/GDPR, auditoria)
- Deploy em Produção (replicar config, webhook, manutenção, monitoramento)
- Manutenção Contínua (atualizar API, novas features, feedback loop, IA tuning, KPIs)

**Tarefas:** 20+ principais
**Duração Estimada:** 5-8 dias (staging) + 3-5 dias (produção) + ongoing
**Dependências:** TODO_01-04

---

## ⚠️ IMPORTANTE: Regra de Ouro

**Toda alteração em qualquer TODO list deve ser alinhada com:**

### Fontes de Verdade (sempre consultar):
1. **[Funcionamento.md](Funcionamento.md)** — Especificações de produto, fluxos, outcomes, contrato de handoff
2. **[README.md](README.md)** — Visão geral e status do projeto
3. **[regras_e_padroes.md](regras_e_padroes.md)** — Padrões de código, segurança, arquitetura

### Ao Completar Cada Tarefa:
✅ Atualize os arquivos acima para refletir as mudanças implementadas
✅ Valide conformidade com critérios de aceitação
✅ Execute testes e validações
✅ Atualize a tarefa para "✅ Completo"

---

## 🎯 Como Usar

### Para Gerente/Lead:
1. Abra [TODO_00_MASTER_INDEX.md](TODO_00_MASTER_INDEX.md)
2. Use cronograma sugerido + template de status
3. Acompanhe progresso com reuniões semanais

### Para Desenvolvedor:
1. Escolha próximo TODO em ordem (TODO_01 → TODO_05)
2. Leia seções inteiras (não só tarefas individuais)
3. Antes de começar tarefa, leia critério de aceitação
4. Ao terminar, marque como "✅ Completo" e atualize fontes de verdade

### Para Arquiteto/Tech Lead:
1. Revisar dependências em [TODO_00_MASTER_INDEX.md](TODO_00_MASTER_INDEX.md)
2. Validar conformidade com padrões em cada TODO
3. Approvar pull requests antes de merge
4. Manter fontes de verdade atualizadas

---

## 📊 Estatísticas

| Documento | Tarefas Principais | Duração Estimada | Status |
|-----------|-------------------|------------------|--------|
| TODO_01   | 12                | 3-5 dias         | ⏳ |
| TODO_02   | 15                | 5-7 dias         | ⏳ |
| TODO_03   | 18                | 7-10 dias        | ⏳ |
| TODO_04   | 20+               | 8-12 dias        | ⏳ |
| TODO_05   | 20+               | 8-13 dias        | ⏳ |
| **TOTAL** | **~85 tarefas**   | **~6 semanas**   | ⏳ |

---

## 🔄 Fluxo de Trabalho Recomendado

```
1. Revisar TODO_00_MASTER_INDEX.md
         ↓
2. Iniciar TODO_01 (em paralelo com setup GCP)
         ↓
3. Aguardar TODO_01 → Iniciar TODO_02
         ↓
4. Paralelo: TODO_02 + TODO_03 (com dependências)
         ↓
5. Paralelo: TODO_03 + TODO_04 (testes desde cedo)
         ↓
6. TODO_05 (staging) após TODO_04 completo
         ↓
7. Aprovações de segurança + conformidade
         ↓
8. TODO_05 (produção) + manutenção contínua
```

---

## 📝 Próximos Passos Imediatos

### Semana 1:
- [ ] Ler [TODO_00_MASTER_INDEX.md](TODO_00_MASTER_INDEX.md) completamente
- [ ] Ler [TODO_01_INFRAESTRUTURA_E_SERVICOS.md](TODO_01_INFRAESTRUTURA_E_SERVICOS.md)
- [ ] Criar projeto GCP
- [ ] Provisionar Firestore, Cloud Storage, Redis

### Semana 2:
- [ ] Completar TODO_01
- [ ] Iniciar TODO_02 — Refatorar validadores
- [ ] Setup de CI/CD

---

## 📞 Dúvidas e Esclarecimentos?

Se encontrar alguma **tarefa ambígua**, **bloqueador técnico** ou **conflito com Funcionamento.md**:

1. ✅ Consulte as fontes de verdade primeiro
2. ✅ Documente a dúvida em comentário no TODO
3. ✅ Comunique para arquitetura/product
4. ✅ Não bloqueie — procure tarefa alternativa enquanto esclarece

---

**Status:** 📋 Documentação de TODO Lists Completa
**Data:** Janeiro de 2026
**Próximo:** Iniciar TODO_01 — Preparar Infraestrutura

🚀 Boa sorte com a implementação!
