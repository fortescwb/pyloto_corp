# TODO List — Refatorar e Completar Módulos (Parte 3: Flows, Testes e Observabilidade)

## ⚠️ IMPORTANTE: Fontes de Verdade

Todas as alterações neste documento devem estar **alinhadas com as fontes de verdade** do projeto:

- **[Funcionamento.md](Funcionamento.md)** — Especificações do produto, fluxos, outcomes e contrato de handoff
- **[README.md](README.md)** — Visão geral, status e documentação
- **[regras_e_padroes.md](regras_e_padroes.md)** — Padrões de código, segurança e organização

**Ao completar cada tarefa**, atualize os arquivos acima conforme necessário para refletir as mudanças implementadas.

---

## 3.2.8 WhatsApp Flows e Templates

### ☐ Criar endpoint /flows/data para processamento de Flow

**Descrição:**
Implementar roteador dedicado que recebe eventos de Flow do WhatsApp e responde com dados criptografados.

**Arquivo:**
`src/pyloto_corp/api/routes/flows.py`

**Endpoint:**
```python
@app.post("/flows/data")
async def handle_flow_data(
    request: Request,
    settings: Settings
) -> JSONResponse:
    """
    Processa request de Flow do WhatsApp:
    1. Valida assinatura (X-Hub-Signature-256)
    2. Valida flow_token_signature
    3. Descriptografa dados (AES-GCM)
    4. Processa lógica (ex.: listar produtos)
    5. Criptografa resposta
    6. Retorna com assinatura
    """
    pass

@app.get("/flows/data")
async def health_check() -> JSONResponse:
    """Health check para Meta"""
    pass
```

**Critério de Aceitação:**
- Endpoint implementado e testado
- Validação de assinatura funcional
- Criptografia/decriptografia AES-GCM
- Health check respondendo
- Testes com payloads reais (Meta docs)

**Notas de Implementação:**
- Usar `cryptography.hazmat` para AES-GCM
- Chaves armazenadas em Secret Manager
- Logs sem expor dados sensíveis
- Timeout: 10 segundos
- Tratar erros com mensagem neutra ao Meta

---

### ☐ Implementar criptografia e decriptografia de Flow

**Descrição:**
Classe utilitária para operações criptográficas AES-GCM conforme Meta Flows specification.

**Arquivo:**
`src/pyloto_corp/adapters/whatsapp/flow_crypto.py`

**Responsabilidades:**
- Descriptografar payload recebido do Meta
- Criptografar resposta para Meta
- Validar IV e salt
- Registrar logs estruturados (sem PII)

**Interface:**
```python
class FlowCrypto:
    async def decrypt(
        self,
        encrypted_data: str,
        iv: str,
        salt: str,
        signature: str
    ) -> Dict:
        """Descriptografa dados recebidos"""
        pass

    async def encrypt(
        self,
        response_data: Dict
    ) -> Dict:  # {encrypted_data, iv, salt, signature}
        """Criptografa resposta"""
        pass

    async def validate_flow_token_signature(
        self,
        flow_token: str,
        signature: str
    ) -> bool:
        """Valida assinatura do flow token"""
        pass
```

**Critério de Aceitação:**
- Criptografia/decriptografia funcionando
- Testes com vectors do Meta
- Validação de assinatura funcionando
- Logs estruturados

**Notas de Implementação:**
- Algoritmo: AES-256-GCM
- Derivação de chave: PBKDF2 com salt
- IV: 12 bytes (recomendado para GCM)
- Authentication tag: 16 bytes
- Referência: Meta docs "Implementing Endpoints for Flows"

---

### ☐ Criar FlowDataHandler para lógica de negócio

**Descrição:**
Classe que processa requisições de Flow e retorna dados (ex.: listar produtos, coletar informações).

**Arquivo:**
`src/pyloto_corp/application/flow_handler.py`

**Responsabilidades:**
- Processar tipos de screen (data, request, etc.)
- Executar ações (fetch dados, atualizar, etc.)
- Retornar resposta conforme Meta API
- Tratar erros com mensagem amigável

**Interface:**
```python
class FlowDataHandler:
    async def handle_data_request(
        self,
        flow_id: str,
        screen: str,
        data: Dict
    ) -> FlowDataResponse:
        """Processa requisição de dados de Flow"""
        pass
```

**Critério de Aceitação:**
- Handler implementado para main flows
- Testes com flows reais (mocks)
- Resposta conforme Meta API
- Logs estruturados

**Notas de Implementação:**
- Suportar ENTRY, LIST, FORM screens
- Retornar: `ACTION: "next"`, `NEXT_SCREEN`, `DATA`
- Ou retornar: `ACTION: "complete"`, `DATA`
- Ou retornar: `ACTION: "error"`, `ERROR_MSG`

---

### ☐ Implementar TemplateStore em Firestore

**Descrição:**
Store para armazenar metadados de templates sincronizados da Meta.

**Arquivo:**
`src/pyloto_corp/infra/stores/template_store.py`

**Schema:**
```
/templates/{template_id}
  ├── namespace: str
  ├── name: str
  ├── category: str
  ├── language: str
  ├── status: str
  ├── parameters: array
  ├── components: array
  ├── created_at: timestamp
  ├── synced_at: timestamp
  └── ...
```

**Critério de Aceitação:**
- Store implementado com CRUD
- Testes com Firestore emulador
- Índices criados para busca rápida

---

### ☐ Integrar uploads de mídia em MediaUploader

**Descrição:**
Completar `MediaUploader` para fazer upload via WhatsApp API após salvar em GCS.

**Critério de Aceitação:**
- Upload para GCS + WhatsApp API funcionando
- media_id retornado e salvo em Firestore
- Deduplicação por hash funcionando
- Logs de sucesso/falha

---

## 3.2.9 Testes e Qualidade

### ☐ Criar testes unitários para validadores

**Descrição:**
Suite completa de testes para todos os validadores (criados em TODO_02).

**Arquivo:**
`tests/adapters/whatsapp/test_validators.py`

**Casos de Teste:**
- TextMessageValidator: limites, caracteres especiais, variáveis
- MediaMessageValidator: tipos MIME, tamanhos
- InteractiveMessageValidator: botões, listas, payloads
- TemplateMessageValidator: templates válidas, parâmetros

**Critério de Aceitação:**
- Cobertura >90% de validadores
- Todos os testes passando
- Edge cases cobertos
- Fixtures reutilizáveis

---

### ☐ Criar testes unitários para stores

**Descrição:**
Testes para ConversationStore, UserProfileStore, AuditLogStore, RedisDedupeStore.

**Arquivo:**
`tests/infra/stores/test_*.py`

**Casos de Teste:**
- CRUD básico (create, read, update, delete)
- Paginação com cursores
- Timeouts (sessão)
- Hash encadeado (auditoria)
- Dedup funcionando

**Critério de Aceitação:**
- Cobertura >85% de stores
- Todos os testes passando
- Usando Firestore emulador / Redis mock
- Testes de concurrency

---

### ☐ Criar testes de integração de pipeline

**Descrição:**
Testes que cobrem fluxo completo: webhook → normalizador → pipeline → outbound.

**Arquivo:**
`tests/application/test_pipeline_integration.py`

**Cenários:**
1. Usuário novo → Classificação ENTRY_UNKNOWN → Resposta com vertentes
2. Usuário escolhe vertente → Fluxo específico → Coleta dados
3. Lead qualificado → Outcome HANDOFF_HUMAN → Resposta com resumo
4. Duplicado → Outcome DUPLICATE_OR_SPAM → Sem resposta
5. Erro interno → Outcome FAILED_INTERNAL → Resposta neutra

**Critério de Aceitação:**
- Cenários principais cobertos
- Mocks de LLM, Firestore, Redis, WhatsApp API
- Assertions em outcomes esperados
- Logs verificados

---

### ☐ Criar testes de carga

**Descrição:**
Testes de performance com lotes de 100 mensagens e múltiplas sessões paralelas.

**Arquivo:**
`tests/load/test_load.py`

**Cenários:**
- 100 mensagens sequenciais
- 50 sessões paralelas
- Picos de 1000 msg/min
- Validar latência (p95 < 2s)
- Validar throughput (>100 msg/s)

**Critério de Aceitação:**
- Testes rodando em ambiente simulado
- Relatório de latência e throughput
- Bottlenecks identificados
- Documentado em `docs/performance.md`

**Notas de Implementação:**
- Usar `locust` ou `pytest-benchmark`
- Testar em Cloud Run (ambiente de produção)
- Monitorar CPU/memória
- Considerar auto-scaling

---

### ☐ Criar testes de assinatura de webhook

**Descrição:**
Validar que apenas webhooks assinados corretamente são processados.

**Arquivo:**
`tests/api/test_webhook_signature.py`

**Casos:**
- Assinatura válida → Processado
- Assinatura inválida → 403 Forbidden
- Sem assinatura → 403 Forbidden
- zero_trust_mode desabilitado → Processado mesmo sem assinatura

**Critério de Aceitação:**
- Testes passando
- Segurança validada
- Logs de rejeição registrados

---

## 3.2.10 Observabilidade e Segurança

### ☐ Implementar logging estruturado completo

**Descrição:**
Expandir módulo `observability/logging.py` com logs em todos os componentes críticos.

**Critério de Aceitação:**
- Todos os componentes registram events estruturados
- JSON format com `level`, `message`, `correlation_id`, `service`
- Sem PII em logs (mascarar phone, email, etc.)
- Logs de erro incluem stack trace
- Sampling de verbose logs em produção

**Notas de Implementação:**
- Usar `pythonjsonlogger` ou similar
- Context var para `correlation_id`
- Structured logging em cada handler crítico
- Considerar Stackdriver Logging (GCP)

---

### ☐ Adicionar métricas de desempenho

**Descrição:**
Implementar métricas via Prometheus ou Cloud Monitoring.

**Métricas:**
- `whatsapp_message_processing_time_ms` — Latência por tipo
- `whatsapp_api_call_duration_ms` — Latência de Graph API
- `whatsapp_message_error_rate` — Taxa de erro por tipo
- `dedupe_hit_rate` — Percentual de deduplicações
- `pipeline_decision_latency_ms` — Tempo de decisão (IA)
- `session_active_count` — Sessões ativas no momento
- `handoff_human_count` — Total de handoffs

**Critério de Aceitação:**
- Métricas coletadas
- Expostas em endpoint `/metrics` ou enviadas a backend
- Dashboards criados
- Alertas configurados

**Notas de Implementação:**
- Usar `prometheus-client` ou `opentelemetry`
- Histogramas para latência (buckets: 100ms, 500ms, 1s, 5s, 10s)
- Contadores para eventos
- Gauges para estado

---

### ☐ Configurar alertas e dashboards

**Descrição:**
Criar alertas para anomalias e dashboards para monitoramento.

**Alertas:**
- Taxa de erro > 1% → Aviso
- Latência p95 > 5s → Aviso
- Dedupe indisponível → Crítico
- Sessão sem outcome terminal → Verificar
- Tokens próximo de expiração → Lembrete

**Dashboards:**
- Overview: msgs processadas, latência, erro rate
- Detalhado: por tipo de mensagem, vertente, outcome
- Operacional: sessões ativas, handoffs, dedupe hits
- Saúde: Redis, Firestore, Graph API

**Critério de Aceitação:**
- Alertas configurados no Cloud Monitoring
- Notificações para Slack/email
- Dashboards criados (Cloud Console ou Grafana)

---

### ☐ Implementar middleware de log de requisição/resposta

**Descrição:**
Adicionar middleware FastAPI que loga requisição/resposta (sem payload sensível).

**Critério de Aceitação:**
- Middleware implementado
- Logs estruturados de req/resp
- Sem exposição de PII
- Condicionado por `enable_request_logging`

---

### ☐ Configurar CORS e rate limiting

**Descrição:**
Revisar políticas de CORS e implementar rate limiting.

**Critério de Aceitação:**
- CORS configurado (apenas domínios autorizados)
- Rate limiting por IP/user
- Endpoints internos protegidos
- Documentação de segurança em `docs/security.md`

---

### ☐ Validar criptografia de payloads

**Descrição:**
Assegurar que payloads em repouso e em trânsito estejam criptografados.

**Critério de Aceitação:**
- HTTPS obrigatório (TLS 1.3+)
- Payloads em Firestore criptografados (GCP-managed ou CMEK)
- Flow data criptografado com AES-GCM
- Secrets não expostos em logs

---

### ☐ Validar conformidade LGPD/GDPR

**Descrição:**
Revisar fluxo completo para conformidade com regulações.

**Checklist:**
- Consentimento para coleta de dados
- Direito ao esquecimento (delete em Firestore)
- Dados mascarados em logs
- Retenção de dados documentada
- Criptografia em repouso e trânsito
- DPA com fornecedores (GCP, etc.)

**Critério de Aceitação:**
- Análise completa documentada
- Falhas corrigidas
- Aprovação de jurídico/compliance

---

## Checklist Final

- [ ] Endpoint /flows/data implementado
- [ ] Criptografia AES-GCM funcionando
- [ ] FlowDataHandler implementado
- [ ] TemplateStore criado
- [ ] Uploads de mídia integrados
- [ ] Testes unitários para validadores (>90%)
- [ ] Testes unitários para stores (>85%)
- [ ] Testes de integração de pipeline
- [ ] Testes de carga implementados
- [ ] Testes de assinatura funcionando
- [ ] Logging estruturado em todos os componentes
- [ ] Métricas de desempenho coletadas
- [ ] Alertas e dashboards configurados
- [ ] Middleware de log implementado
- [ ] CORS e rate limiting configurados
- [ ] Validação de criptografia completa
- [ ] Conformidade LGPD/GDPR validada
- [ ] [README.md](README.md) atualizado com observabilidade
- [ ] Documentação de segurança em `docs/security.md`

---

**Status:** ⏳ Não iniciado | 🚀 Em andamento | ✅ Completo
