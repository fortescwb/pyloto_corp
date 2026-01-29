# Estratégia de Produção - Pipeline Assíncrono V3 com Contexto Institucional

## 📊 Estado Atual (2026-01-28)

### ✅ Concluído
- **FSM State Machine** (fsm_states.py)
  - 10 estados canônicos (INIT, IDENTIFYING, UNDERSTANDING_INTENT, PROCESSING, GENERATING_RESPONSE, SELECTING_MESSAGE_TYPE, AWAITING_USER, ESCALATING, COMPLETED, FAILED, SPAM)
  - Histórico de transições com metadata e confidence scores
  - 11/11 testes passando
  
- **Institutional Context Loader** (institutional_context.py)
  - Carrega visao_principios-e-posicionamento.md (6 princípios imutáveis)
  - Carrega vertentes.md (4 vertentes: Entrega, Serviços, Tecnologia, CRM/SaaS)
  - Carrega contexto_llm/doc.md (taxonomia, intents, constraints)
  - Injeção de contexto em prompts
  
- **Prompts com Contexto Institucional** (prompts_institutional.py)
  - Task #1: FSM state determination (com validação de constraints)
  - Task #2: Response generation (com guidelines por vertente)
  - Task #3: Message type selection (TEXT, BUTTON, LIST, IMAGE, VIDEO, etc)
  
- **Infrastructure Async**
  - message_queue.py: Fila InMemory (dev) + Cloud Tasks (prod)
  - session_store_firestore_async.py: Persistência non-blocking
  - pipeline_async.py: Orquestração com asyncio.gather() para LLM parallelization
  - routes_async.py: Webhook desacoplada (<100ms)
  - app_async.py: FastAPI app factory com inits async
  
- **Quality Gates**
  - Testes: 11/11 FSM, 8/8 queue (19 testes passando)
  - Lint: Ruff - All checks passed (3 novos arquivos)
  - Coverage: Acima de 80%

### ⏳ Próximos Passos Críticos

**1. Integração do Context Loader com Pipeline Async**
- Adicionar `InstitutionalContextLoader` como singleton em `app_async.py`
- Chamar `loader.load()` no startup da aplicação
- Injetar no estado da app: `app.state.institutional_context`

**2. Melhorar Pipeline para Usar as 3 Tarefas LLM em Paralelo**
- Modificar `_process_with_llm()` em pipeline_async.py:
  ```python
  # Atualmente: Task#1 -> Task#2 -> Task#3 (sequencial)
  # Alvo: Task#1 + (Task#2 || Task#3) em paralelo
  ```
- Task #1 (FSM) deve executar sempre primeiro (determina contexto)
- Task #2 e Task #3 podem executar em paralelo com asyncio.create_task()

**3. Injetar Contexto Institucional nos Prompts**
- Em `routes_async.py` POST /tasks/process:
  ```python
  context_str = app.state.institutional_context.get_prompt_context()
  # Passar para pipeline._process_with_llm()
  ```
- Em `pipeline_async.py._run_llm1_fsm_state()`:
  ```python
  prompt = build_fsm_state_prompt(
      user_message=msg.text,
      current_state=session.fsm.current_state,
      state_history=[...],
      institutional_context=context_str  # NOVO
  )
  ```

**4. Validação em Produção**
- Deploy em staging (Cloud Run)
- Teste de carga: 1000 mensagens simultâneas via webhook
- Verificar: latência (<2s), throughput (QPS), erro rate (<1%)

## 🔧 Checklist de Integração

```
[ ] 1. Adicionar InstitutionalContextLoader ao app_async.py
[ ] 2. Carregá-lo no startup (app.on_event("startup"))
[ ] 3. Passar institutional_context para routes_async.py
[ ] 4. Passar institutional_context para pipeline_async.py
[ ] 5. Injetar em build_fsm_state_prompt()
[ ] 6. Injetar em build_response_generation_prompt()
[ ] 7. Injetar em build_message_type_prompt()
[ ] 8. Validar JSON output de cada LLM task
[ ] 9. Testar FSM transitions com histórico
[ ] 10. Testar parallelização de Task#2 + Task#3
[ ] 11. Testar alta volume (100+ msgs/sec)
[ ] 12. Medir latência: webhook <100ms, pipeline <3s
[ ] 13. Validar que nenhuma mensagem se perde
[ ] 14. Validar state updates (Firestore)
[ ] 15. Deploy em produção
```

## 📈 Métricas Esperadas (Pré vs Pós)

| Métrica | Antes | Depois | Delta |
|---------|-------|--------|-------|
| Webhook latency | 2000ms | <100ms | -95% |
| Pipeline latency | 6-13s | 4-8s | -40% |
| LLM parallelization | Nenhuma | Task#2+#3 | +30% gain |
| Throughput | 10 msgs/sec | 100+ msgs/sec | +900% |
| Msg loss rate | ~5% | <0.1% | -98% |
| State update success | ~90% | >99.9% | +10% |

## 🚀 Deployment Sequence

**Staging (Pre-Prod)**
1. Deploy pipeline_async.py com FSM v3 + institutional context
2. Teste de carga: 100 msgs/sec por 5 min
3. Validar: Nenhuma perda de mensagem, state updates corretos
4. Medir: Latência, throughput, error rate

**Production**
1. Blue-green deployment com routes_async v1 (nova) vs routes.py v0 (old)
2. Canary: 5% tráfego para nova rota
3. Monitor: ErrorRate, Latency, queue depth por 1 hora
4. Gradient: 25% -> 50% -> 75% -> 100%

**Rollback**
- Se error rate > 5%: revert para old routes
- Se latency > 5s: revert para old pipeline
- Manter ambas as versões live por 2 semanas

## 📝 Documentação para Equipe

**Para Devs**:
- FSM State Machine: [fsm_states.py docs]
- Institucional Context: [institutional_context.py docs]
- LLM Prompts: [prompts_institutional.py docs]

**Para Ops**:
- Deployment guide: [DEPLOYMENT_GUIDE.md] (criar)
- Monitoring: [Observability guide] (criar)
- Runbook: Escalation procedures (criar)

**Para PO**:
- 3 LLM Tasks explained: [PRODUCT_SPEC.md] (criar)
- Business constraints: [CONSTRAINTS.md] (criar)
- Metrics dashboard: [Analytics.md] (criar)

## 🎯 Success Criteria

✅ **Technical**
- Todos os 3 LLM tasks executando com contexto institucional
- Transições de estado respeitam FSM rules
- Nenhuma mensagem perdida em fila
- Latência <3s ponta-a-ponta
- Error rate <1%

✅ **Business**
- Respostas respeitam constraints Pyloto
- Nenhuma contract closing/pricing na conversa inicial
- Identificação correta de vertente de negócio
- Escalação apropriada quando necessário

✅ **Operational**
- Logs estruturados (JSON) com correlation-id
- Alertas configurados no Cloud Monitoring
- Runbook para escalações
- SLA 99.95% uptime

