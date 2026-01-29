# TODO List — Preparar Infraestrutura e Serviços

## ⚠️ IMPORTANTE: Fontes de Verdade

Todas as alterações neste documento devem estar **alinhadas com as fontes de verdade** do projeto:

- **[Funcionamento.md](Funcionamento.md)** — Especificações do produto, fluxos, outcomes e contrato de handoff
- **[README.md](README.md)** — Visão geral, status e documentação de deploy
- **[regras_e_padroes.md](regras_e_padroes.md)** — Padrões de código, segurança e organização

**Ao completar cada tarefa**, atualize os arquivos acima conforme necessário para refletir as mudanças implementadas.

---

## ✅ Código de Infraestrutura Implementado (Janeiro 2026)

As seguintes implementações de código foram concluídas:

- ✅ **config/settings.py** — Constantes Graph API v24.0, collections, buckets, validação
- ✅ **infra/secrets.py** — SecretManagerProvider, EnvSecretProvider, factory
- ✅ **infra/dedupe.py** — RedisDedupeStore, InMemoryDedupeStore, fail-closed
- ✅ **infra/http.py** — HttpClient com retry exponencial e backoff
- ✅ **docs/firestore/schema.md** — Schema completo do Firestore
- ✅ **docs/api-migration.md** — Guia de migração Graph API
- ✅ **.github/workflows/ci.yml** — Pipeline expandido (lint, typecheck, test, security)
- ✅ **Testes** — 84 novos testes unitários (155 total passando)

---

## 3.1 Configurar Ambiente de Nuvem (Provisionamento)

> ⚠️ As tarefas abaixo são de **operações/DevOps** e requerem acesso ao console GCP ou CLI.

### ☐ Criar projeto no Google Cloud

**Descrição:**
Estabelecer novo projeto GCP para hospedar o serviço `pyloto_corp`.

**Critério de Aceitação:**

- Projeto GCP criado e ativo
- Billing habilitado
- Equipe de engenharia tem acesso adequado

**Notas de Implementação:**

- Usar naming convention: `pyloto-corp-prod` ou `pyloto-corp-staging`
- Documentar ID do projeto
- Configurar permissões de acesso com princípio de menor privilégio

---

### ☐ Habilitar Firestore em modo nativo

**Descrição:**
Provisionar banco de dados Firestore para armazenar conversas, perfis de usuário e trilha de auditoria.

**Critério de Aceitação:**

- Firestore criado em modo nativo (não Datastore)
- Collection `conversations` disponível
- Collection `user_profiles` disponível
- Collection `audit_logs` disponível
- Índices necessários criados

**Notas de Implementação:**

- Definir região (ex.: `us-east1` ou `south-america-east1`)
- Criar índices composite para queries de filtro + ordenação
- Documentar schema das collections em `docs/firestore/schema.md`
- Testar paginação com cursores

---

### ☐ Criar buckets Cloud Storage

**Descrição:**
Provisionar buckets para uploads de mídia e exportações.

#### Bucket 1: Uploads de Mídia

- Nome: `whatsapp_media_store_bucket` (ou variante com projeto ID)
- Visibilidade: Privado
- Políticas: Retenção (ex.: 90 dias), criptografia GCP-managed
- Versioning: Desabilitado

#### Bucket 2: Exportações

- Nome: `export_bucket` (ou variante com projeto ID)
- Visibilidade: Privado
- Políticas: Retenção (ex.: 180 dias), criptografia GCP-managed
- Signed URLs habilitado (para compartilhamento)

**Critério de Aceitação:**

- Ambos os buckets criados e acessíveis
- Testes de upload e download bem-sucedidos
- Políticas de retenção configuradas
- CORS configurado para acesso autorizado

**Notas de Implementação:**

- Documentar nomes dos buckets em `config/settings.py`
- Testar acesso via Application Default Credentials
- Implementar retry e fallback para falhas

---

### ☐ Provisionar Redis para deduplicação

**Descrição:**
Criar instância Redis (ou Cloud Memorystore) para cache de deduplicação com TTL configurável.

**Critério de Aceitação:**

- Instância Redis/Memorystore criada
- TTL configurado (ex.: 3600 segundos = 1 hora)
- Testes de set/get bem-sucedidos
- Conectividade verificada a partir do Cloud Run

**Notas de Implementação:**

- Memorystore é recomendado para GCP (gerenciado)
- Configurar política de evicção: `allkeys-lru` ou `volatile-lru`
- Documentar `REDIS_URL` em `Settings`
- Implementar fallback para `InMemoryDedupeStore` em desenvolvimento

---

### ☐ Criar tópicos e assinaturas Pub/Sub

**Descrição:**
Provisionar Pub/Sub para processamento assíncrono e integração com outros sistemas (opcional, conforme demanda).

**Tópicos Recomendados:**

- `whatsapp-inbound-messages`
- `whatsapp-outbound-responses`
- `handoff-human`
- `audit-events`

**Critério de Aceitação:**

- Tópicos criados
- Assinaturas configuradas
- Testes de publish/subscribe funcionando

**Notas de Implementação:**

- Usar deadletter queues para mensagens que falham N vezes
- Documentar nomes dos tópicos em `config/settings.py`
- Implementar apenas se necessário (pode ser adicionado incrementalmente)

---

## 3.2 Gerenciar Segredos

### ☐ Armazenar segredos no Secret Manager

**Descrição:**
Guardar tokens, chaves e credenciais sensíveis no GCP Secret Manager.

**Segredos a Armazenar:**

- `WHATSAPP_ACCESS_TOKEN` — Token de autenticação da API Meta
- `WHATSAPP_WEBHOOK_SECRET` — Secret para validação de webhooks
- `WHATSAPP_VERIFY_TOKEN` — Token de verificação de webhook
- `WHATSAPP_PHONE_NUMBER_ID` — ID do número de telefone
- `RSA_PRIVATE_KEY` — Chave privada para Flow encryption (se aplicável)
- `RSA_PUBLIC_KEY` — Chave pública para Flow encryption (se aplicável)
- `FIRESTORE_CREDENTIALS` — JSON com credenciais (ou usar ADC)
- `REDIS_PASSWORD` — Senha do Redis (se aplicável)

**Critério de Aceitação:**

- Todos os segredos criados no Secret Manager
- Nenhum secret commitado no repositório
- Cloud Run pode acessar os segredos via `secret-id:latest`
- Auditoria de acesso configurada

**Notas de Implementação:**

- Usar versionamento automático do Secret Manager
- Documentar rotação de tokens (ex.: refresh token a cada 60 dias)
- Testar recuperação de segredos via Application Default Credentials
- Implementar alertas para acessos indevidos

---

### ☐ Definir rota de refresh do access token

**Descrição:**
Implementar job automático ou endpoint para renovar o `WHATSAPP_ACCESS_TOKEN` antes de expiração.

**Critério de Aceitação:**

- Job agendado (Cloud Tasks ou Cloud Scheduler) executa a cada 55 dias
- Script renova o token via Meta API
- Token atualizado no Secret Manager
- Logs estruturados registram renovação (sem expor token)

**Notas de Implementação:**

- Usar Cloud Scheduler para trigger periódico
- Implementar exponential backoff em caso de falha
- Documentar procedimento manual de emergency rotation
- Testar fallback para token antigo se renovação falhar

---

### ☐ Validar versão da Graph API

**Descrição:**
Confirmar que a versão da Graph API Meta está alinhada com `Funcionamento.md` (v24.0 em jan/2026).

**Critério de Aceitação:**

- Documentado em código qual versão está em uso
- Testes validam compatibilidade com v24.0
- Endpoints em uso (messages, templates, flows) mapeados na documentação

**Notas de Implementação:**

- Criar constant `GRAPH_API_VERSION = "v24.0"` em `config/settings.py`
- Manter compatibilidade com versões futuras (ex.: v25.0)
- Documentar breaking changes em `docs/api-migration.md`

---

## 3.3 Configurar CI/CD

### ☐ Integrar verificações de linting e type-checking

**Descrição:**
Configurar pipeline para executar `ruff`, `mypy` e `pytest` em cada push.

**Ferramentas:**

- **`ruff`** — Linting Python (style, imports, complexity)
- **`mypy`** — Type checking estático
- **`pytest`** — Testes unitários

**Critério de Aceitação:**

- GitHub Actions (ou equivalente) executa ruff, mypy, pytest
- Pipeline falha se houver erros críticos
- Relatório de cobertura de testes gerado (target: >80%)

**Notas de Implementação:**

- Arquivo: `.github/workflows/lint-and-test.yml`
- Configurar fail-fast para acelerar feedback
- Armazenar relatórios em artifacts

---

### ☐ Integrar gate de auditoria

**Descrição:**
Adicionar etapa que carrega `AUDITORIA_DADOS.json` e falha se novos issues críticos forem introduzidos.

**Critério de Aceitação:**

- Pipeline lê `AUDITORIA_DADOS.json`
- Falha se arquivos com violações críticas forem modificados
- Falha se conformidade cair abaixo de 80%
- Relatório de auditoria disponível em artifacts

**Notas de Implementação:**

- Criar script `scripts/check_audit_gate.py` que:
  - Carrega JSON
  - Compara arquivos modificados vs arquivo `attention` ou `critical`
  - Retorna exit code 1 se critério não atender
- Documentar política de aceitação de exceções

---

### ☐ Automatizar deploy para Cloud Run

**Descrição:**
Implementar deploy automático após passar testes, com rollback em caso de erro.

**Critério de Aceitação:**

- Novo push para `main` dispara deploy automático
- Deploy segue para Cloud Run com revisão automática
- Health check inicial valida aplicação
- Rollback automático se health check falhar
- Variáveis de ambiente carregadas de Secret Manager

**Notas de Implementação:**

- Arquivo: `.github/workflows/deploy.yml`
- Configurar `min_instances`, `max_instances` em variáveis
- Testar estratégia blue-green ou canary
- Documentar procedure de rollback manual

---

## Checklist Final

**Código Implementado:**
- [x] Settings com Graph API v24.0 e validação
- [x] SecretManagerProvider para Secret Manager
- [x] RedisDedupeStore com fail-closed
- [x] HttpClient com retry exponencial
- [x] Schema Firestore documentado
- [x] Guia de migração de API criado
- [x] CI/CD pipeline rodando com linting + testes
- [x] 155 testes passando

**Provisionamento Pendente (DevOps):**
- [ ] Projeto GCP criado e ativo
- [ ] Firestore habilitado com collections base
- [ ] Cloud Storage buckets criados (mídia + exportações)
- [ ] Redis/Memorystore provisionado
- [ ] Pub/Sub tópicos criados (se necessário)
- [ ] Todos os segredos no Secret Manager
- [ ] Job de refresh de token configurado
- [ ] Deploy automático para Cloud Run funcional

---

**Status:** 🚀 Em andamento (código completo, provisionamento pendente)
