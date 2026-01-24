# TODO List — Deploy e Pós-Deploy

## ⚠️ IMPORTANTE: Fontes de Verdade

Todas as alterações neste documento devem estar **alinhadas com as fontes de verdade** do projeto:

- **[Funcionamento.md](Funcionamento.md)** — Especificações do produto, fluxos, outcomes e contrato de handoff
- **[README.md](README.md)** — Visão geral, status e documentação
- **[regras_e_padroes.md](regras_e_padroes.md)** — Padrões de código, segurança e organização

**Ao completar cada tarefa**, atualize os arquivos acima conforme necessário para refletir as mudanças implementadas.

---

## 3.3 Deploy e Pós-Deploy

### ☐ Preparar configuração de staging

**Descrição:**
Configurar variáveis de ambiente e secrets para ambiente de staging.

**Variáveis de Ambiente (Settings):**
- `ENVIRONMENT` = "staging"
- `WHATSAPP_PHONE_NUMBER_ID` = (ID de teste)
- `WHATSAPP_ACCESS_TOKEN` = (token de teste do Meta)
- `WHATSAPP_WEBHOOK_SECRET` = (secret de teste)
- `WHATSAPP_VERIFY_TOKEN` = (token de verificação)
- `FIRESTORE_PROJECT_ID` = "pyloto-corp-staging"
- `REDIS_URL` = "redis://...staging..."
- `GCS_BUCKET_MEDIA` = "whatsapp-media-staging"
- `GCS_BUCKET_EXPORT` = "export-staging"
- `ZERO_TRUST_MODE` = true
- `ENABLE_REQUEST_LOGGING` = true
- `DEDUPE_BACKEND` = "redis"
- `DEDUPE_TTL_SECONDS` = 3600
- `LOG_LEVEL` = "INFO"

**Critério de Aceitação:**
- Variáveis definidas em `config/settings.py`
- Secrets em Secret Manager
- Cloud Run environment variables configurados
- Testes de conectividade passando

**Notas de Implementação:**
- Usar números de teste do Meta para staging
- Firestore staging separado de produção
- Redis staging dedicado
- Documentar em `DEPLOYMENT_GUIDE.md`

---

### ☐ Fazer deploy para Cloud Run

**Descrição:**
Fazer deploy da aplicação em Cloud Run com configurações de staging.

**Critério de Aceitação:**
- Imagem Docker buildada
- Deployada em Cloud Run
- Revisão automática criada
- Health check passando
- URL acessível

**Configurações Cloud Run:**
- `min_instances` = 1
- `max_instances` = 10
- `memory` = 512MB
- `cpu` = 1
- `timeout` = 60s
- `concurrency` = 50

**Notas de Implementação:**
- Usar Dockerfile otimizado
- Multi-stage build para reduzir tamanho
- Health check em `/health`
- Startup probe padrão

---

### ☐ Registrar webhook no Facebook/Meta

**Descrição:**
Registrar URL de webhook no console de desenvolvedor do Meta.

**Passos:**
1. Ir para Meta App Dashboard
2. Selecionar aplicação
3. Ir para WhatsApp → Configuration
4. Configurar Webhook URL: `https://<cloud-run-url>/webhooks/whatsapp`
5. Configurar Verify Token: valor de `WHATSAPP_VERIFY_TOKEN`
6. Subscribe to events: `messages`, `message_status`, `message_template_status_update`

**Critério de Aceitação:**
- Webhook registrado e validado pelo Meta
- Teste de envio de mensagem funcional
- Status de webhook mostra ativo
- Logs mostram webhook recebido

**Notas de Implementação:**
- Documentar URL do webhook
- Testar com webhook.site primeiro (opcional)
- Verificar que assinatura está sendo validada

---

### ☐ Realizar testes de ponta a ponta

**Descrição:**
Validar fluxo completo enviando mensagens de diferentes tipos.

**Cenários de Teste:**
1. Mensagem de texto simples
   - Enviar: "Olá"
   - Esperado: Resposta com vertentes da Pyloto

2. Escolher vertente
   - Enviar: "Quero usar Sistemas sob Medida"
   - Esperado: Início de coleta de informações

3. Fornecer informações
   - Enviar: Informações conforme fluxo
   - Esperado: Reconhecimento e pergunta seguinte

4. Duplicação
   - Enviar: Mesma mensagem 2x em 5 segundos
   - Esperado: Segunda mensagem ignorada (dedupe)

5. Timeout
   - Enviar: Mensagem
   - Aguardar: 2+ horas sem resposta
   - Esperado: Sessão encerrada com outcome

**Critério de Aceitação:**
- Todos os cenários passando
- Fluxo de conversa natural
- Deduplicação funcionando
- Timeouts respeitados
- Testes documentados

**Notas de Implementação:**
- Usar número de teste do Meta
- Enviar de dispositivo real ou Postman
- Capturar logs de processamento
- Documentar em `docs/testing/e2e.md`

---

### ☐ Executar testes de carga em staging

**Descrição:**
Simular volume esperado em produção para validar escala.

**Parâmetros:**
- Pico esperado: 1000 mensagens/minuto
- Duração do teste: 10 minutos
- Ramp-up: 2 minutos
- Verificar: Latência p95 < 2s, Taxa de erro < 0.1%

**Critério de Aceitação:**
- Teste rodado com sucesso
- Métricas de latência documentadas
- Relatório de bottlenecks
- Ajustes de scaling implementados

**Notas de Implementação:**
- Usar ferramenta (locust, Apache JMeter, etc.)
- Usar dados reais de conversa
- Monitorar recursos de Cloud Run
- Capturar logs e métricas
- Documentar em `docs/performance/load-test.md`

---

### ☐ Validar deduplicação

**Descrição:**
Confirmar que deduplicação está funcionando e não duplica mensagens.

**Teste:**
1. Enviar mensagem X
2. Imediatamente enviar mensagem X novamente
3. Verificar que segunda foi dedupada
4. Checkar logs de dedup hit
5. Aguardar TTL expirar (ex.: 1h)
6. Enviar novamente
7. Verificar que foi processada

**Critério de Aceitação:**
- Dedup hit registrado em logs
- Mensagem não foi processada 2x
- TTL respeitado
- Redis operacional

---

### ☐ Acompanhar logs estruturados

**Descrição:**
Revisar logs para garantir que nenhuma informação sensível está sendo registrada.

**Verificações:**
- [ ] Sem phone number em plaintext
- [ ] Sem email em plaintext
- [ ] Sem PII de usuário
- [ ] Sem access tokens
- [ ] Sem payloads brutos de webhook
- [ ] Correlation IDs propagados
- [ ] Timestamps corretos
- [ ] Levels apropriados (INFO, WARN, ERROR)

**Critério de Aceitação:**
- Auditoria completa de logs
- Relatório de violações corrigidas
- Aprovação de segurança

**Notas de Implementação:**
- Usar Cloud Logging para buscar patterns
- Exemplo: search "phone" para encontrar exposes
- Usar regex para validar masking
- Documentar política em `docs/logging.md`

---

### ☐ Verificar correlation IDs

**Descrição:**
Validar que correlation IDs estão sendo gerados e propagados em toda requisição.

**Teste:**
1. Enviar requisição de webhook
2. Procurar correlation_id nos logs
3. Seguir mesmo ID em múltiplos logs
4. Verificar que está em resposta (se aplicável)

**Critério de Aceitação:**
- Correlation ID gerado por requisição
- Propagado em todo o contexto
- Rastreável em logs
- Documentado em `docs/observability/correlation-ids.md`

---

### ☐ Acompanhar métricas de latência

**Descrição:**
Monitorar latência de processamento e identificar gargalos.

**Métricas a Acompanhar:**
- Latência webhook → webhook_return: p50, p95, p99
- Latência normalização: ms
- Latência classificação (IA): ms
- Latência outbound (Graph API): ms
- Total end-to-end: ms

**Critério de Aceitação:**
- Métricas visíveis em dashboard
- P95 < 2s em condições normais
- Gargalos identificados
- Relatório de findings

**Notas de Implementação:**
- Usar Cloud Monitoring ou Prometheus
- Criar dashboard customizado
- Configurar alertas para anomalias
- Documentar em `docs/performance/metrics.md`

---

### ☐ Acompanhar taxa de erro

**Descrição:**
Monitorar taxa de erro e tipos de erro mais comuns.

**Métricas:**
- Erro rate total: %
- Erro rate por tipo de mensagem: %
- Erro rate por tipo (4xx, 5xx, timeout): %
- Distribuição de erros top 10

**Critério de Aceitação:**
- Taxa de erro < 0.1% em staging
- Principais causas identificadas
- Correções implementadas

**Notas de Implementação:**
- Usar alertas: rate > 1% → Aviso
- Revisar logs de erro
- Implementar retry onde apropriado
- Documentar em post-mortem

---

### ☐ Ajustar configurações baseado em metrics

**Descrição:**
Fazer fine-tuning de parâmetros baseado em observations em staging.

**Parâmetros a Ajustar:**
- `dedupe_ttl_seconds` — Se muitos duplicados mesmo com TTL alto, aumentar
- `session_timeout_inactive_minutes` — Se muitas timeouts prematuros, aumentar
- `ai_classification_timeout_seconds` — Se muitos timeouts de IA, aumentar
- `http_client_max_retries` — Se muitas falhas, aumentar retries
- `cloud_run_concurrency` — Se latência alta, aumentar
- `cloud_run_max_instances` — Se fila acumulando, aumentar

**Critério de Aceitação:**
- Ajustes documentados
- Métricas re-verificadas pós-ajuste
- Performance melhorada

---

## 3.3.2 Ajustes Finais Antes da Produção

### ☐ Revisar e atualizar documentação

**Descrição:**
Assegurar que toda documentação está atualizada e pronta para produção.

**Documentação a Revisar:**
- [ ] `README.md` — Instruções atualizadas
- [ ] `DEPLOYMENT_GUIDE.md` — Guia de deploy completo
- [ ] `docs/whatsapp/README.md` — Especificação de tipos de mensagem
- [ ] `docs/api/` — Documentação de endpoints
- [ ] `docs/flows/` — Documentação de Flows
- [ ] `docs/ai/prompts.md` — Prompts documentados
- [ ] `docs/security.md` — Políticas de segurança
- [ ] `docs/logging.md` — Política de logs
- [ ] `docs/performance/` — Documentação de performance

**Critério de Aceitação:**
- Toda documentação relevante atualizada
- Links válidos
- Exemplos funcionais
- Revisão por technical writer (se disponível)

---

### ☐ Documentação de integração externa

**Descrição:**
Criar guias para equipes que integram com pyloto_corp.

**Documentação:**
- Manual de uso para equipe de atendimento (handoff, contexto)
- Manual de uso para equipe de engenharia (integração, troubleshoot)
- FAQ de problemas comuns
- Troubleshooting guide

**Critério de Aceitação:**
- Documentação completa e clara
- Exemplos reais
- Contatos de suporte documentados

---

### ☐ Conduzir revisão de segurança (pentest)

**Descrição:**
Executar pentest para identificar vulnerabilidades antes de produção.

**Escopo:**
- OWASP Top 10
- Injeção SQL (se aplicável)
- XSS (se aplicável)
- CSRF (se aplicável)
- Validação de entrada
- Autenticação/autorização
- Criptografia
- Tratamento de erro

**Critério de Aceitação:**
- Pentest executado
- Relatório gerado
- Vulnerabilidades críticas corrigidas
- Aprovação de segurança

**Notas de Implementação:**
- Contratar pentest externo (recomendado)
- Ou usar ferramentas (ZAP, Burp)
- Documentar achados
- Criar tickets para correções

---

### ☐ Validar conformidade LGPD/GDPR

**Descrição:**
Auditoria completa de conformidade com regulações.

**Checklist LGPD/GDPR:**
- [ ] Consentimento documentado
- [ ] Direito ao esquecimento implementado
- [ ] Dados mascarados em logs
- [ ] Retenção de dados documentada (ex.: 180 dias)
- [ ] Criptografia em repouso (GCP-managed ou CMEK)
- [ ] Criptografia em trânsito (TLS 1.3+)
- [ ] DPA assinado com processadores
- [ ] Incident response plan
- [ ] Data Processing Agreement com GCP

**Critério de Aceitação:**
- Auditoria completa
- Não-conformidades corrigidas
- Aprovação de jurídico/compliance

**Notas de Implementação:**
- Envolver jurídico/compliance desde início
- Documentar tudo em `docs/compliance/`
- Preparar para auditorias externas

---

### ☐ Obter aprovação final de auditoria

**Descrição:**
Validar que código está em conformidade com relatórios de auditoria técnica.

**Referência:**
- `GUIA_LEITURA_AUDITORIA.md` — Checklist de auditoria
- `AUDITORIA_DADOS.json` — Dados de auditoria anterior

**Critério de Aceitação:**
- Todas as findings da auditoria anterior corrigidas
- Novo scan de auditoria executado
- Conformidade >85%
- Aprovação assinada

**Notas de Implementação:**
- Rodar `ruff`, `mypy` novamente
- Revisar `AUDITORIA_DADOS.json`
- Documentar exceções aprovadas
- Preparar relatório final

---

## 3.3.3 Deploy em Produção

### ☐ Replicar configuração em produção

**Descrição:**
Fazer deploy em produção com mesma configuração de staging.

**Passos:**
1. Criar projeto GCP de produção separado
2. Copiar infraestrutura (Firestore, Redis, GCS, Secrets)
3. Atualizar variáveis (ENVIRONMENT=production, etc.)
4. Deploy de imagem Docker em Cloud Run produção
5. Validar health check

**Critério de Aceitação:**
- Aplicação rodando em produção
- Health check passando
- URL de webhook funcional
- Integração com números reais de WhatsApp

**Notas de Implementação:**
- Usar terraform/IaC se possível
- Documentar processo em runbook
- Preparar rollback plan

---

### ☐ Registrar webhook em produção

**Descrição:**
Registrar URL de produção no Meta App Dashboard.

**Critério de Aceitação:**
- Webhook registrado
- Validação do Meta bem-sucedida
- Eventos começam a chegar

---

### ☐ Agendar janelas de manutenção

**Descrição:**
Preparar plano de migração de dados (se houver) e comunicar para stakeholders.

**Cenários:**
1. Primeira vez sem dados legados → Apenas deploy
2. Com dados legados → Migração de conversas/usuários

**Critério de Aceitação:**
- Janela agendada
- Stakeholders notificados
- Rollback plan pronto
- Time de on-call designado

---

### ☐ Monitorar primeiras horas/dias em produção

**Descrição:**
Acompanhar intensamente os primeiros dias de produção.

**Atividades:**
- [ ] Monitorar dashboards continuamente
- [ ] Revisar logs a cada 30 minutos
- [ ] Verificar alertas em tempo real
- [ ] Testes manuais periódicos (enviar mensagem)
- [ ] Comunicação com equipe de atendimento
- [ ] Documentar issues encontrados

**Critério de Aceitação:**
- 7 dias sem issues críticos
- Taxa de erro < 0.1%
- Latência p95 < 2s
- Aprovação para diminuir monitoramento

**Notas de Implementação:**
- Ter runbook de troubleshooting à mão
- Contatos de suporte GCP/Meta disponíveis
- Escalation path definido

---

## 3.3.4 Manutenção Contínua

### ☐ Atualizar versão da Graph API

**Descrição:**
Acompanhar releases da Meta e atualizar quando necessário.

**Processo:**
1. Meta anuncia nova versão
2. Revisar breaking changes
3. Testar em staging com v nova
4. Atualizar endpoints/parâmetros
5. Deploy em produção

**Critério de Aceitação:**
- Versão atual documentada em `Funcionamento.md`
- Breaking changes documentados
- Testes passando com nova versão

**Notas de Implementação:**
- Acompanhar Meta Release Notes
- Manter suporte a versões anteriores (3+ meses)
- Documentar compatibility matrix

---

### ☐ Acompanhar novas features de WhatsApp

**Descrição:**
Implementar novos tipos de mensagem, templates ou features conforme Meta lança.

**Exemplos:**
- Novos tipos de Flow
- Novas templatette variables
- Novas button types
- Shopping/product features

**Processo:**
1. Meta anuncia feature
2. Avaliar relevância para pyloto_corp
3. Implementar em staging
4. Testar com clientes piloto
5. Deploy em produção

**Critério de Aceitação:**
- Feature implementada
- Documentada em `docs/whatsapp/`
- Testada em staging

---

### ☐ Coletar feedback de usuários e equipe

**Descrição:**
Feedback loop para melhorias contínuas.

**Fontes de Feedback:**
- Equipe de atendimento (usabilidade, bugs)
- Equipe de vendas (features pedidas)
- Análise de logs (gargalos, errors)
- Métricas (performance, utilização)
- Usuários finais (via enquetes, etc.)

**Processo:**
1. Coletar feedback periodicamente
2. Priorizar por impacto
3. Implementar em sprint
4. Deploy em staging para validação
5. Deploy em produção

**Critério de Aceitação:**
- Feedback loop estabelecido
- Melhorias implementadas regularmente
- Documentadas em changelog

---

### ☐ Manter classificador de intenções atualizado

**Descrição:**
Treinar/ajustar modelo de IA baseado em feedbacks e novos padrões.

**Processo:**
1. Coletar conversations do Firestore
2. Marcar intenções/outcomes corretos (dataset)
3. Retreinar modelo ou ajustar prompts
4. Validar accuracy
5. Deploy em staging
6. A/B test em produção (se aplicável)
7. Deploy completo

**Critério de Aceitação:**
- Accuracy melhorando
- Feedback loop funcionando
- Documentação de prompts atualizada

---

### ☐ Ajustar fluxos de atendimento

**Descrição:**
Refinar fluxos conforme aprendizado operacional.

**Exemplos de Ajustes:**
- Adicionar nova pergunta que esclarece intent
- Remover pergunta redundante
- Ajustar mensagens (clareza, tom)
- Adicionar novo fluxo (nova vertente, caso de uso)

**Processo:**
1. Identificar oportunidade (feedback, metrics)
2. Desenhar novo fluxo
3. Implementar em `AIOrchestrator` ou rules
4. Testar em staging com sample data
5. Deploy com feature flag (opcional)
6. Monitor de results
7. Documentar em `Funcionamento.md`

**Critério de Aceitação:**
- Fluxo implementado
- Testado
- Documentado em `Funcionamento.md`
- Aprovado por product/operações

---

### ☐ Monitorar tendências e KPIs

**Descrição:**
Acompanhar métricas de negócio para garantir alignment com objetivos.

**KPIs:**
- Conversão a HANDOFF_HUMAN: % de mensagens
- Lead qualification: % de high/medium vs low
- Session completion rate: % com outcome válido
- Customer satisfaction: CSAT (se houver survey)
- Cost per lead: $ (vs custo manual)
- Time to lead: minutos

**Frequência:**
- Diária: Taxa de erro, latência
- Semanal: Conversion, qualification
- Mensal: KPIs, ROI, roadmap updates

**Critério de Aceitação:**
- Dashboard de KPIs criado
- Reviews agendados regularmente
- Ações baseadas em dados

---

## Checklist Final

### Deploy em Staging
- [ ] Configuração de staging criada
- [ ] Deploy em Cloud Run bem-sucedido
- [ ] Webhook registrado no Meta
- [ ] Testes E2E completos
- [ ] Testes de carga executados
- [ ] Deduplicação validada
- [ ] Logs revisados (sem PII)
- [ ] Correlation IDs verificados
- [ ] Métricas de latência acompanhadas
- [ ] Taxa de erro aceitável

### Pré-Produção
- [ ] Documentação atualizada
- [ ] Guias de integração criados
- [ ] Pentest realizado
- [ ] Conformidade LGPD/GDPR validada
- [ ] Aprovação de auditoria obtida
- [ ] Runbooks de troubleshooting criados

### Deploy em Produção
- [ ] Configuração de produção criada
- [ ] Imagem Docker deployada
- [ ] Webhook registrado no Meta
- [ ] Health check passando
- [ ] Monitoramento intensivo ativado
- [ ] Escalation path definido

### Manutenção Contínua
- [ ] Processo de atualização de API documentado
- [ ] Acompanhamento de features Meta iniciado
- [ ] Feedback loop estabelecido
- [ ] Modelo de IA com manutenção agendada
- [ ] Fluxos com revisão periódica
- [ ] KPIs com dashboard e reviews

---

**Status:** ⏳ Não iniciado | 🚀 Em andamento | ✅ Completo
