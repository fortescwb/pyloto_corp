# TODO Master Index — Roadmap para Produção

## 📋 Visão Geral

Este documento índice organiza todos os TODO lists para implementação do `pyloto_corp` em produção. Cada arquivo de TODO contém tarefas granulares organizadas por tema e critérios de aceitação claros.

---

## ⚠️ IMPORTANTE: Sempre Consulte as Fontes de Verdade

Todas as alterações em qualquer TODO list devem estar **alinhadas com**:

- **[Funcionamento.md](Funcionamento.md)** — Especificações do produto, fluxos de atendimento, outcomes e contrato de handoff (LeadProfile, ConversationHandoff)
- **[README.md](README.md)** — Visão geral do projeto, status e documentação de deploy
- **[regras_e_padroes.md](regras_e_padroes.md)** — Padrões de código, organização em camadas, segurança e observabilidade
- **[Roadmap-producao.md](Roadmap-producao.md)** — Roadmap detalhado de produção, etapas, conformidade e oportunidades de melhoria

**Regra de Ouro:** Ao **completar cada tarefa** em qualquer TODO list, **atualize os arquivos acima** conforme necessário para refletir as mudanças implementadas.

---

## 📁 Estrutura de TODO Lists

### 1️⃣ [TODO_01_INFRAESTRUTURA_E_SERVICOS.md](TODO_01_INFRAESTRUTURA_E_SERVICOS.md) — 🚀 EM ANDAMENTO

**Objetivo:** Preparar infraestrutura em nuvem (GCP) e pipeline CI/CD

**Status:** Código implementado, provisionamento GCP pendente

**Implementado (Janeiro 2026):**
- ✅ `config/settings.py` — Graph API v24.0, collections, buckets, validação
- ✅ `infra/secrets.py` — SecretManagerProvider com factory
- ✅ `infra/dedupe.py` — RedisDedupeStore com fail-closed
- ✅ `infra/http.py` — HttpClient com retry exponencial
- ✅ `docs/firestore/schema.md` — Schema completo
- ✅ `docs/api-migration.md` — Guia de migração
- ✅ `.github/workflows/ci.yml` — Pipeline expandido
- ✅ 84 novos testes unitários (155 total)

**Pendente (Provisionamento DevOps):**
- ☐ Projeto GCP criado
- ☐ Firestore habilitado
- ☐ Cloud Storage buckets
- ☐ Redis/Memorystore
- ☐ Secrets no Secret Manager

**Dependências:** Nenhuma (primeiro a iniciar)

**Duração Estimada:** 3-5 dias (código) + 1-2 dias (provisionamento)

---

### 2️⃣ [TODO_02_REFATORA_VALIDADORES_OUTBOUND.md](TODO_02_REFATORA_VALIDADORES_OUTBOUND.md)

**Objetivo:** Refatorar validadores e implementar componentes de envio (outbound)

**Seções:**

- ✅ Refatorar Validadores
  - `limits.py` — Módulo centralizado de constantes
  - `TextMessageValidator` — Validação de texto
  - `MediaMessageValidator` — Validação de mídia
  - `InteractiveMessageValidator` — Validação de interativos
  - `TemplateMessageValidator` — Validação de templates
  - Orquestrador principal
  - Testes unitários (>90% cobertura)

- ✅ Refatorar Outbound
  - `WhatsAppHttpClient` — Chamadas HTTP com retry/backoff
  - `MediaUploader` — Upload em GCS
  - `TemplateManager` — Gerenciamento de templates
  - `FlowSender` — Envio de Flows com criptografia
  - Integração com deduplicação persistente

**Dependências:**

- TODO_01 (infraestrutura + secrets)

**Duração Estimada:** 5-7 dias

---

### 3️⃣ [TODO_03_PERSISTENCIA_SESSAO_PIPELINE.md](TODO_03_PERSISTENCIA_SESSAO_PIPELINE.md)

**Objetivo:** Implementar camada de persistência, sessão e pipeline de processamento

**Seções:**

- ✅ Refatorar Exportação
  - Extrair métodos de `execute()` em `ExportConversationUseCase`
  - Implementar `GcsHistoryExporter` com URLs assinadas

- ✅ Persistência e Stores
  - `ConversationStore` — Firestore (conversas com paginação)
  - `UserProfileStore` — Firestore (perfis de usuário)
  - `AuditLogStore` — Firestore (trilha encadeada com hash)
  - `RedisDedupeStore` — Redis (deduplicação com TTL)
  - Factory function `create_dedupe_store()`

- ✅ Sessão e Pipeline
  - `SessionManager` — Persistência de sessão com timeouts
  - `application/pipeline.py` — Orquestração completa
  - Refatoração de `process_whatsapp_webhook`

- ✅ IA e Orquestração
  - Prompts base em `prompts.py`
  - `AIOrchestrator` completo com LLM + fallback
  - Lead scoring (opcional)

**Dependências:**

- TODO_01 (infraestrutura)
- TODO_02 (validadores)

**Duração Estimada:** 7-10 dias

---

### 4️⃣ [TODO_04_FLOWS_TESTES_OBSERVABILIDADE.md](TODO_04_FLOWS_TESTES_OBSERVABILIDADE.md)

**Objetivo:** Implementar Flows, testes abrangentes e observabilidade

**Seções:**

- ✅ WhatsApp Flows e Templates
  - Endpoint `/flows/data` com validação de assinatura
  - Criptografia/decriptografia AES-GCM
  - `FlowDataHandler` para lógica de negócio
  - `TemplateStore` em Firestore
  - Integração de uploads de mídia

- ✅ Testes e Qualidade
  - Testes unitários para validadores (>90%)
  - Testes unitários para stores (>85%)
  - Testes de integração de pipeline
  - Testes de carga (100 msg, p95 < 2s)
  - Testes de assinatura de webhook

- ✅ Observabilidade e Segurança
  - Logging estruturado em todos os componentes
  - Métricas de desempenho (Prometheus/Cloud Monitoring)
  - Alertas e dashboards
  - Middleware de log de requisição/resposta
  - CORS e rate limiting
  - Validação de criptografia
  - Conformidade LGPD/GDPR

**Dependências:**

- TODO_02 (validadores)
- TODO_03 (stores + pipeline)

**Duração Estimada:** 8-12 dias

---

### 5️⃣ [TODO_05_DEPLOY_E_POS_DEPLOY.md](TODO_05_DEPLOY_E_POS_DEPLOY.md)

**Objetivo:** Deploy em staging/produção e manutenção contínua

**Seções:**

- ✅ Deploy Inicial em Staging
  - Configuração de variáveis de ambiente
  - Deploy em Cloud Run
  - Registro de webhook no Meta
  - Testes E2E
  - Testes de carga
  - Validação de deduplicação
  - Acompanhamento de logs/métricas

- ✅ Ajustes Finais Antes da Produção
  - Revisão e atualização de documentação
  - Documentação de integração externa
  - Pentest de segurança
  - Validação de conformidade LGPD/GDPR
  - Aprovação de auditoria final

- ✅ Deploy em Produção
  - Replicação de configuração
  - Registro de webhook em produção
  - Agendamento de janelas de manutenção
  - Monitoramento intensivo (7 dias)

- ✅ Manutenção Contínua
  - Atualização de versão da Graph API
  - Acompanhamento de novas features
  - Feedback loop com usuários
  - Manutenção do classificador de IA
  - Ajustes de fluxos
  - Monitoramento de KPIs

**Dependências:**

- TODO_01 (infraestrutura)
- TODO_02 (outbound)
- TODO_03 (pipeline)
- TODO_04 (testes + observabilidade)

**Duração Estimada:** 5-8 dias (staging) + 3-5 dias (produção)

---

## 🎯 Cronograma Sugerido

### Fase 1: Infraestrutura — 🚀 EM ANDAMENTO

- [x] TODO_01 — Código de infraestrutura (Settings, Secrets, Dedupe, HTTP)
- [ ] TODO_01 — Provisionamento GCP (DevOps)
- **Milestone:** Aplicação básica rodando em Cloud Run staging

### Fase 2: Componentes Core

- [ ] TODO_02 — Refatorar validadores e outbound
- [ ] TODO_03 (parcial) — Implementar stores base
- **Milestone:** Pipeline básico funcional com persistência

### Fase 3: Completar Pipeline

- [ ] TODO_03 (completo) — Sessão, pipeline e IA
- [ ] TODO_04 (parcial) — Testes unitários
- **Milestone:** Pipeline completo com fluxos operacionais

### Fase 4: Qualidade e Observabilidade

- [ ] TODO_04 (completo) — Flows, testes de carga, observabilidade
- **Milestone:** Sistema com observabilidade completa e testes validados

### Fase 5: Deploy

- [ ] TODO_05 (parcial) — Deploy em staging, validação
- [ ] Aprovações de segurança/compliance
- [ ] Deploy em produção
- [ ] Monitoramento inicial
- **Milestone:** Em produção com operações estáveis

### Fase 6: Manutenção

- [ ] TODO_05 (continuar) — Feedback loop, melhorias contínuas
- **Milestone:** Sistema evoluindo conforme feedback

---

## 📊 Dependências e Paralelização

```Roadmap de tarefas
TODO_01 (Infraestrutura)
    ↓
    ├─→ TODO_02 (Validadores + Outbound)
    │       ↓
    │   TODO_03 (Persistência + Pipeline)
    │       ↓
    │   TODO_04 (Flows + Testes + Observabilidade)
    │       ↓
    │   TODO_05 (Deploy + Manutenção)
    │
    └─→ [CI/CD Pipeline configurado]
```

**Oportunidades de Paralelização:**
  -TODO_02 e TODO_03 podem ser parcialmente paralelos (após TODO_01)
  -TODO_04 (testes) pode começar assim que TODO_03 tiver stores básicos
  -Documentação (README, guias) pode ser feita em paralelo com implementação

---

## 🔍 Verificação de Conformidade

Antes de considerar uma tarefa **COMPLETA**, valide:

1. **Alinhamento com Fontes de Verdade:**
   - [ ] Atende especificações de `Funcionamento.md`
   - [ ] Segue padrões de `regras_e_padroes.md`
   - [ ] Sem conflitos com `README.md`
   - [ ] Coerente com `Roadmap-producao.md`

2. **Critérios de Aceitação:**
   - [ ] Todos os critérios listados no TODO foram cumpridos
   - [ ] Testes associados passando
   - [ ] Code review aprovado

3. **Documentação:**
   - [ ] Código documentado (docstrings em português)
   - [ ] README.md ou seção relevante atualizada
   - [ ] Arquivo de TODO marcado como "✅ Completo"

4. **Segurança e Qualidade:**
   - [ ] `ruff` rodou sem violations
   - [ ] `mypy` passou (type checking)
   - [ ] Sem exposição de PII em logs/docs
   - [ ] Secrets não commitados

---

## 📞 Suporte e Escalação

Caso encontre **bloqueadores** durante a implementação:

1. **Bloqueador Técnico:** Documentar em issue GitHub + comunicar lead de engenharia
2. **Requisito Não Claro:** Verificar `Funcionamento.md` + contatar product
3. **Recurso Indisponível:** Documentar impacto + propor alternativa
4. **Conflito com Padrões:** Revisar `regras_e_padroes.md` + escalate para arquitetura

---

## 📝 Template de Status

Mantenha atualizado:

```markdown
## Status Geral

- [ ] TODO_01 — 0%
- [ ] TODO_02 — 0%
- [ ] TODO_03 — 0%
- [ ] TODO_04 — 0%
- [ ] TODO_05 — 0%

**Overall:** 0%

### Última Atualização
[Data] — [Responsável] — [Progresso]
```

---

## 🚀 Próximos Passos

1. **Agora:** Revisar este documento e validar planejamento
2. **Próximo:** Iniciar TODO_01 — Preparar infraestrutura
3. **Acompanhamento:** Atualizar status semanalmente
4. **Comunicação:** Briefing semanal de progresso com stakeholders

---

**Versão:** 1.0
**Última Atualização:** Janeiro de 2026
**Responsável:** Arquitetura / Liderança Técnica

Para mais detalhes, consulte cada arquivo TODO específico.
