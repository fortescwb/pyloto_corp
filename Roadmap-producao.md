# Roadmap para Produção

## Introdução

Este documento lista etapas concretas para levar o projeto `pyloto_corp` à produção. Ele foi elaborado com base nos documentos de Fonte de Verdade na raiz do repositório (especialmente `Funcionamento.md`, `regras_e_padroes.md` e os relatórios de auditoria) e na análise do código existente.

As seções abaixo destacam a coerência atual do código com as definições do produto e as oportunidades de melhoria identificadas, além de um roteiro detalhado de tarefas até o deploy em ambiente de produção.

---

## 1. Conformidade com os Documentos de Fonte de Verdade

### Produtos e Fluxos

O código implementa as principais entidades e fluxos descritos em `Funcionamento.md`. Os intents e outcomes definidos em `domain/enums.py` abrangem todos os estados previstos pelo produto, como:

- `HANDOFF_HUMAN`
- `SELF_SERVE_INFO`
- `ROUTE_EXTERNAL`
- `AWAITING_USER`
- `DUPLICATE_OR_SPAM`
- `UNSUPPORTED`
- `FAILED_INTERNAL`

Além disso, inclui tipos de mensagem e interações: `text`, `image`, `video`, `audio`, `document`, `sticker`, `location`, `contacts`, `address`, `interactive`, `template`, `reaction`.

O `IntentQueue` limita a sessão a três intenções, conforme as regras de fluxo de `Funcionamento.md`.

### Padrões e Segurança

Os arquivos seguem as diretrizes de `regras_e_padroes.md`:

- Funções curtas
- Divisão em camadas: `domain`, `application`, `adapters`, `infra`
- Comentários em português
- Ausência de PII nos logs

O módulo `observability/logging.py` injeta `correlation_id` e evita registrar payloads brutos. Constantes de tamanho e limitações (por exemplo `max_message_length_chars`) estão definidas em `Settings`.

### Auditoria e Exportação

O use case de exportação (`application/export.py`) implementa:

- Histórico de conversas
- Trilha de auditoria encadeada com hashing
- Registro em audit log

O processo considera PII apenas quando permitido e utiliza `derive_user_key` para anonimizar usuários. O relatório de auditoria indica que a classe de exportação está estruturada, mas recomenda extrair partes de `execute()` em métodos menores.

### Validações e Outbound

O `WhatsAppMessageValidator` valida:

- Comprimento de mensagens
- Tipos de mídia
- Interações
- Evita envios inválidos

O `WhatsAppOutboundClient` constrói payloads para envio de mensagens, mas carece de implementação do cliente HTTP e de deduplicação persistente. Esses componentes foram sinalizados pela auditoria por concentração excessiva de responsabilidades e linhas longas.

### Módulos Esqueléticos

Alguns módulos são apenas esqueletos:

- `ai/orchestrator.py`
- `application/pipeline.py`
- `infra/dedupe.py`

Eles cumprem a estrutura prevista, mas requerem implementação real para produção.

---

## 2. Oportunidades de Melhoria e Ajustes

As auditorias (`AUDITORIA_SUMARIO.md` e `RELATORIO_AUDITORIA_COMPLETO.md`) apontaram que **84% dos arquivos estão conformes** e que as violações encontradas são de natureza não crítica.

### Principais Oportunidades

1. **Refatorar validadores**: Dividir `WhatsAppMessageValidator` em classes menores por tipo de mensagem ou categoria, respeitando o princípio de responsabilidade única (SRP). Também separar limites e constantes em um módulo específico. Esta mudança melhora a legibilidade e facilita testes.

2. **Extrair métodos em exportação**: O método `execute()` em `application/export.py` possui mais de 100 linhas; embora bem documentado, pode ser dividido em sub-funções ou use cases menores para facilitar a manutenção e testes.

3. **Dividir cliente outbound**: `WhatsAppOutboundClient` engloba construção de payloads, validação, idempotência e envio. Criar classes/serviços especializados (ex. `MediaUploader`, `FlowSender`, `TemplateManager`) e mover a lógica de re-intentos, deduplicação e registro para camadas próprias.

4. **Persistência de sessão e dedupe**: Implementar `session.py` para persistir sessões em Firestore ou Redis, incluindo timeouts e multi-intents descritos em `Funcionamento.md`. Implementar `RedisDedupeStore` (ou Firestore) com TTL e fail-closed para evitar processar mensagens duplicadas.

5. **Integração de IA**: Completar `AIOrchestrator` com pipeline de classificação de mensagens, utilização de LLM (prompt + contexto) e regras determinísticas. Esse componente deve analisar mensagens normalizadas e definir intent, outcome e resposta ou encaminhamento apropriado.

6. **Implementar pipeline**: `process_whatsapp_webhook` atualmente apenas deduplica e encaminha para o orquestrador. Deve lidar com sessão, intents, outcomes e acionar o módulo outbound para respostas conforme fluxos definidos em `Funcionamento.md`.

7. **Implantar dedupe persistente**: Substituir `InMemoryDedupeStore` por `RedisDedupeStore` ou implementação Firestore; adicionar lógica de fail-closed em produção (não processar quando falha).

8. **Upload de mídia e gestão de templates**: `WHATSAPP_MODULE_REFACTORING.md` lista tarefas pendentes:
   - Integrar upload de mídia em GCS
   - Implementar cliente HTTP com backoff e retry
   - Gerenciar templates
   - Integração com Graph API v24.0
   - Deduplicação via Firestore
   - Testes de integração

9. **Refinar normalizador**: Garantir que todos os campos suportados pela API Meta v24.0 sejam mapeados; incluir suporte a novos tipos de flow e template quando lançados.

10. **Testes**: Adicionar testes unitários e de integração para:
    - Validadores
    - Normalizador
    - Orchestrator
    - Exportação
    - Dedupe
    - Outbound

    Incluir testes de carga para validar performance com lote máximo de 100 mensagens, conforme `Settings`.

11. **Observabilidade e monitoramento**: Expandir logs estruturados com métricas de desempenho, métricas de sucesso/erro nas chamadas à API Meta, monitoramento de filas e sessões. Configurar alertas de saúde e dashboards.

12. **CI/CD e gate de auditoria**: Integrar `AUDITORIA_DADOS.json` ao pipeline de CI/CD para verificar se novas mudanças respeitam as regras e não introduzem violações críticas. Rodar `ruff`, `mypy`, `pytest` e auditoria automática em cada PR, bloqueando merges em caso de falha.

13. **Documentação**: Atualizar `README.md` com:
    - Instruções de deploy
    - Configuração de variáveis de ambiente
    - Explicação dos módulos e dependências
    - Link para o guia de integração com WhatsApp Flows
    - Documentação de endpoints de webhook, exportação e endpoints internos (ex. para Flows)

14. **Segurança**:
    - Assegurar que todos os dados sensíveis estejam mascarados nos logs e exports
    - Validar assinaturas dos webhooks com `verify_meta_signature` sempre que `zero_trust_mode` estiver ativo
    - Implementar criptografia de payloads de Flow conforme o guia de end-to-end encryption da Meta
    - Ajustar cabeçalhos CORS e autenticação conforme políticas da empresa

---

## 3. Roteiro para Conclusão e Deploy em Produção

A lista abaixo apresenta as etapas recomendadas, organizadas em categoria e ordem aproximada. Algumas podem ser executadas em paralelo por equipes diferentes.

### 3.1 Preparar Infraestrutura e Serviços

#### Configurar Ambiente de Nuvem

- Criar projeto no Google Cloud (ou plataforma equivalente) para hospedar o serviço
- Habilitar Firestore (modo nativo) para armazenar conversas, perfis de usuário e trilha de auditoria
- Criar buckets no Cloud Storage para:
  - Uploads de mídia: `whatsapp_media_store_bucket`
  - Exportações: `export_bucket`
  - Definir políticas de retenção e criptografia
- Provisionar Redis (ou Memorystore) para deduplicação, com TTL configurado conforme `dedupe_ttl_seconds`
- Criar tópicos e assinaturas no Pub/Sub, se houver necessidade de processar mensagens assíncronas ou integrar a outros sistemas

#### Gerenciar Segredos

- Armazenar no Secret Manager:
  - `whatsapp_access_token`
  - `whatsapp_webhook_secret`
  - Chaves RSA para Flow encryption
  - Demais segredos
- Garantir que não sejam commitados no repositório
- Definir rota para obtenção e refresh do access token (ex. agendar job para renovação)
- Validar a versão da Graph API (v24.0 em `Funcionamento.md`)

#### Configurar CI/CD

- Integrar pipeline com `ruff`, `mypy` e `pytest`
- Incluir etapa que carrega `AUDITORIA_DADOS.json` e falha se:
  - Houver arquivos marcados com violações críticas
  - A porcentagem de conformidade cair abaixo de 80%
  - Ler o JSON e verificar a lista de arquivos com `attention`
- Automatizar deploy para Cloud Run com rollback em caso de erro, definindo variáveis de ambiente via `Settings`

### 3.2 Refatorar e Completar Módulos

#### Validators

- Criar classes especializadas:
  - `TextMessageValidator`
  - `MediaMessageValidator`
  - `InteractiveMessageValidator`
  - etc.
- Cada classe responsável por validar um tipo específico
- Consolidar constantes de limites em módulo comum (ex. `whatsapp_limits.py`)
- Atualizar `WhatsAppOutboundClient` para usar os novos validadores

#### Outbound

Dividir `WhatsAppOutboundClient` em componentes especializados:

- **`WhatsAppHttpClient`**: Responsável por chamadas HTTP ao Graph API
  - Retry exponencial
  - Backoff
  - Idempotência utilizando `idempotency_key`

- **`MediaUploader`**: Para upload de mídia em GCS e retorno de IDs

- **`TemplateManager`**: Para gerenciamento de templates
  - Carregar namespace
  - Parâmetros e versões

- **`FlowSender`**: Para envio de mensagens Flow
  - Implementar criptografia e decriptografia conforme o arquivo `flows_impl.txt`
  - Gerar par de chaves
  - Responder a health checks
  - Validar `flow_token_signature`
  - Assinar/responder com AES-GCM

- Implementar integração com Firestore/Redis para:
  - Deduplicação de mensagens outbound
  - Persistência de idempotency keys
  - Garantir que mensagens não sejam enviadas duas vezes em caso de retries

#### Exportação

- Extrair os passos de `execute()` em `ExportConversationUseCase` em:
  - Métodos menores
  - Classes auxiliares (coleta de dados, renderização, persistência, auditoria)
- Manter a assinatura do use case e ajustar testes
- Implementar `HistoryExporterProtocol` concreto para:
  - Salvar exportações no bucket configurado (`export_bucket`)
  - Usar bibliotecas da nuvem
  - Retornar o path interno
  - Gerar URL assinado caso o export precise ser compartilhado

#### Persistência e Stores

- Criar implementações concretas de:
  - `ConversationStore`
  - `UserProfileStore`
  - `AuditLogStore`
  
  Usando Firestore com:
  - Práticas de paginação (via cursores)
  - Ordenação por timestamp
  - Mecanismos de concurrency control para `AuditLogStore`
  - Condição de append com `expected_prev_hash`
  - Preservação da cadeia de hashes

- Implementar `RedisDedupeStore` (ou `FirestoreDedupeStore`) com:
  - TTL configurável
  - Lógica fail-closed (não processar mensagem se o cache estiver indisponível)
  - Atualizar `create_dedupe_store` em `api/app.py` para usar o backend configurado
  - Retornar erro 5xx se o dedupe falhar em produção

#### Sessão e Pipeline

- Implementar `application/session.py` para:
  - Persistir informações de sessão em Firestore ou Redis
  - Rastrear: última interação, lista de intents, status
  - Respeitar timeouts: 30 min e 2 h para encerramento automático
  - Incluir método para recuperar e atualizar a sessão sem expor PII

- Completar `application/pipeline.py` para:
  - Recuperar sessão e lista de intents ao receber webhook
  - Chamar `AIOrchestrator` com mensagens normalizadas
  - Classificar intenções e outcomes
  - Atualizar `IntentQueue`
  - Decidir se envia resposta automática via outbound ou encaminha para humano/external
  - Conforme regras de `Funcionamento.md`
  - Registrar eventos de auditoria para cada transição relevante (ex. `USER_CONTACT`, `HANDOFF_HUMAN`)

#### IA e Orquestração

- Definir prompts e knowledge base para `AIOrchestrator`
  - Incorporar instruções em `ai_knowledge.md` (se existir)
  - Incluir fluxos de negócio
- Criar integração com modelo de linguagem:
  - Local ou via API
  - Fallback para regras determinísticas quando a IA não for conclusiva
- Implementar pipeline de classificação que retorna estrutura `AIResponse` contendo:
  - `intent`
  - `outcome`
  - `reply_text`
- Considerar:
  - Controle de temperatura
  - Stop words
  - Context window
- Incluir mecanismos de lead scoring ou qualificação se necessário, usando campos do `LeadProfile` definidos em `Funcionamento.md`

#### WhatsApp Flows e Templates

- Implementar suporte a mensagens Flow (faça/resultado) no outbound e no processamento inbound
- Utilizar o guia de `flows_impl.txt` para implementar:
  - Endpoint de dados com criptografia AES-GCM
  - Validação de assinatura: `X-Hub-Signature-256` e `flow_token_signature`
  - Resposta `SUCCESS` ou próximo screen conforme a API Meta
- Criar roteador dedicado `/flows/data` para:
  - Receber e processar eventos de Flow
  - Retornar resposta criptografada
  - Armazenar as chaves no Secret Manager
  - Trocar chaves quando necessário
- Adicionar suporte à criação e atualização de templates via Graph API
  - Armazenamento em banco local
  - Sincronização periódica

#### Testes e Qualidade

- Criar suíte de testes unitários com cobertura para:
  - Validadores
  - Normalizador
  - Dedupe
  - Stores
  - Exportação
  - Outbound
  - Utilizar `pytest` e `pytest-asyncio` para rotas assíncronas

- Montar testes de integração que simulam:
  - Chamadas de webhook
  - Deduplication
  - Orchestrator
  - Envio de mensagens com Graph API
  - Pode-se usar mock server
  - Incluir casos de erro: assinatura inválida, JSON malformado, duplicidade

- Implementar testes de carga:
  - Lotes de 100 mensagens
  - Múltiplas sessões
  - Avaliar escala horizontal no Cloud Run

#### Observabilidade e Segurança

- Configurar Logging para incluir:
  - `level`
  - `message`
  - `correlation_id`
  - `service`
- Implementar middleware para log de:
  - Requisições e respostas (sem payload)
  - Quando `enable_request_logging` estiver ativado

- Adicionar métricas (ex. via Prometheus ou Cloud Monitoring) para:
  - Tempo de processamento
  - Taxa de erros
  - Contagem de deduplicações
  - Latência do Graph API
  - Tempo de exportação
  - Uso de recursos

- Configurar dashboards e alertas para anomalias:
  - Picos de erro 5xx
  - Latência alta
  - Dedupe falhando
  - Utilizar health endpoint já implementado para monitorar instâncias

- Revisar políticas de:
  - CORS
  - Autenticação
  - Rate limiting na FastAPI
  - Exemplos: configurar API Key ou OIDC para rotas internas

### 3.3 Deploy e Pós-Deploy

#### Deploy Inicial em Ambiente de Staging

1. Configurar variáveis de ambiente de acordo com `Settings` e criar secrets correspondentes
2. Subir a aplicação no Cloud Run com:
   - Autoscaling (definir `min_instances` e `max_instances`)
   - Monitorar consumo
   - Ajustar alocação de CPU e memória
3. Validar webhooks:
   - Registrar URL de webhook no Facebook/Meta
   - Verificar a assinatura com `whatsapp_verify_token`
   - Realizar testes de ponta a ponta enviando mensagens de diferentes tipos
   - Verificar a resposta
4. Executar testes de carga:
   - Validar deduplicação e tempo de resposta
   - Ajustar a configuração de TTL do Redis
   - Ajustar configuração de lotes (até 100 mensagens) conforme necessário

#### Revisar Logs e Métricas

1. Acompanhar logs estruturados para garantir que nenhuma informação sensível seja registrada
2. Verificar se correlation IDs estão sendo propagados
3. Acompanhar métricas de latência e taxa de erro
4. Ajustar backoff e número de retries de acordo com os resultados

#### Ajustes Finais Antes da Produção

1. Revisar e atualizar documentação:
   - Do repositório
   - De integração externa
   - Manual de uso para equipe de atendimento
   - Manual de uso para equipe de engenharia

2. Conduzir revisão de segurança (pentest) e conformidade com LGPD/GDPR:
   - Anonimização de dados
   - Encriptação em trânsito
   - Encriptação em repouso

3. Obter aprovação final da auditoria interna usando `GUIA_LEITURA_AUDITORIA.md` como checklist

#### Deploy em Produção

1. Replicar a configuração de staging em ambiente de produção
   - Ajustar quotas e chaves

2. Agendar janelas de manutenção para:
   - Migração de dados
   - Caso existam conversas/usuários de versões anteriores

3. Monitorar intensivamente as primeiras horas/dias:
   - Utilizar dashboards e alertas configurados

#### Manutenção Contínua

1. Atualizar a versão do Graph API quando necessário:
   - Conforme `Funcionamento.md`
   - Ajustar endpoints e parâmetros

2. Acompanhar novas features de WhatsApp Business:
   - Novos tipos de mensagens
   - Melhorias em Flows
   - Atualizar o código conforme a documentação oficial

3. Incorporar feedback:
   - Dos usuários
   - Da equipe de vendas
   - Ajustar o classificatório de intenções
   - Ajustar os fluxos de atendimento

---

## Resumo

O projeto está bem alinhado com os documentos de referência e aprovado para produção conforme o relatório de auditoria, mas requer:

- ✅ A implementação de módulos esqueléticos
- ✅ Refatorações de classes monolíticas
- ✅ Integração com serviços externos (Graph API, Redis, Firestore, GCS)
- ✅ Criação de testes abrangentes
- ✅ Implementação de pipeline de CI/CD

Seguindo o roteiro acima, será possível entregar uma solução robusta, segura e escalável em ambiente de produção.

---

## Referências

[1-2] [enums.py](https://github.com/fortescwb/pyloto_corp/blob/44bcc103cfb2cc2eb8f7de886f1dd09ddc6dea80/src/pyloto_corp/domain/enums.py)

[3] [intent_queue.py](https://github.com/fortescwb/pyloto_corp/blob/44bcc103cfb2cc2eb8f7de886f1dd09ddc6dea80/src/pyloto_corp/domain/intent_queue.py)

[4, 26] [logging.py](https://github.com/fortescwb/pyloto_corp/blob/main/src/pyloto_corp/observability/logging.py)

[5, 18] [settings.py](https://github.com/fortescwb/pyloto_corp/blob/main/src/pyloto_corp/config/settings.py)

[6-7] [export.py](https://github.com/fortescwb/pyloto_corp/blob/main/src/pyloto_corp/application/export.py)

[8] [RELATORIO_AUDITORIA_COMPLETO.md](https://github.com/fortescwb/pyloto_corp/blob/44bcc103cfb2cc2eb8f7de886f1dd09ddc6dea80/RELATORIO_AUDITORIA_COMPLETO.md)

[9] [validators.py](https://github.com/fortescwb/pyloto_corp/blob/44bcc103cfb2cc2eb8f7de886f1dd09ddc6dea80/src/pyloto_corp/adapters/whatsapp/validators.py)

[10] [outbound.py](https://github.com/fortescwb/pyloto_corp/blob/44bcc103cfb2cc2eb8f7de886f1dd09ddc6dea80/src/pyloto_corp/adapters/whatsapp/outbound.py)

[11] [AUDITORIA_SUMARIO.md](https://github.com/fortescwb/pyloto_corp/blob/44bcc103cfb2cc2eb8f7de886f1dd09ddc6dea80/AUDITORIA_SUMARIO.md)

[12, 16] [orchestrator.py](https://github.com/fortescwb/pyloto_corp/blob/main/src/pyloto_corp/ai/orchestrator.py)

[13] [pipeline.py](https://github.com/fortescwb/pyloto_corp/blob/main/src/pyloto_corp/application/pipeline.py)

[14] [dedupe.py](https://github.com/fortescwb/pyloto_corp/blob/main/src/pyloto_corp/infra/dedupe.py)

[15, 21, 24-25] [Funcionamento.md](https://github.com/fortescwb/pyloto_corp/blob/44bcc103cfb2cc2eb8f7de886f1dd09ddc6dea80/Funcionamento.md)

[17] [WHATSAPP_MODULE_REFACTORING.md](https://github.com/fortescwb/pyloto_corp/blob/44bcc103cfb2cc2eb8f7de886f1dd09ddc6dea80/WHATSAPP_MODULE_REFACTORING.md)

[19] [GUIA_LEITURA_AUDITORIA.md](https://github.com/fortescwb/pyloto_corp/blob/44bcc103cfb2cc2eb8f7de886f1dd09ddc6dea80/GUIA_LEITURA_AUDITORIA.md)

[20] [signature.py](https://github.com/fortescwb/pyloto_corp/blob/main/src/pyloto_corp/adapters/whatsapp/signature.py)

[22] [AUDITORIA_DADOS.json](https://github.com/fortescwb/pyloto_corp/blob/44bcc103cfb2cc2eb8f7de886f1dd09ddc6dea80/AUDITORIA_DADOS.json)

[23] [audit.py](https://github.com/fortescwb/pyloto_corp/blob/main/src/pyloto_corp/application/audit.py)
