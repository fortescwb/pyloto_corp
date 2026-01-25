# pyloto_corp

Atendimento inicial institucional/comercial da Pyloto via WhatsApp (API oficial da Meta). Este serviço **não é CRM** e **não executa operação final** — ele explica a Pyloto, identifica intenção, coleta dados mínimos, qualifica o lead e encerra com 1 outcome terminal canônico.

## Arquivos Fonte de Verdade

-`pyloto_corp/README.md`
-`pyloto_corp/regras_e_padroes.md`
-`pyloto_corp/Funcionamento.md`
-`pyloto_corp/Monitoramento_Regras-Padroes.md`

## Status atual

- Módulo WhatsApp cobre 16 tipos oficiais (incluindo templates, flows, CTA URL, location request) — ver [docs/whatsapp/README.md](docs/whatsapp/README.md)
- **Infraestrutura TODO_01 implementada** — Settings, Secrets, Dedupe, HTTP Client
- Auditoria técnica 2025: 84% conformidade, nenhum bloqueador — ver [docs/auditoria/README.md](docs/auditoria/README.md)
- Produto e regras: fontes de verdade em [Funcionamento.md](Funcionamento.md) e [regras_e_padroes.md](regras_e_padroes.md)
- **155 testes unitários passando** (cobertura em expansão)

## Princípios não-negociáveis

- Batch-safe e idempotência por mensagem
- Logs estruturados (JSON) e sem PII
- Segredos fora do repositório (Secret Manager)
- Cloud Run stateless e escalável

## Estrutura (src layout)

- `src/pyloto_corp/api`: FastAPI, rotas e dependências
- `src/pyloto_corp/domain`: entidades, enums e contratos
- `src/pyloto_corp/application`: use-cases e pipeline
- `src/pyloto_corp/infra`: clientes externos e dedupe
- `src/pyloto_corp/adapters/whatsapp`: inbound/outbound e normalização
- `src/pyloto_corp/ai`: orquestrador e prompts
- `src/pyloto_corp/observability`: logging e correlation-id
- `docs/`: conhecimento e contratos
- `deploy/`: Cloud Run

## Documentação

- Produto: [Funcionamento.md](Funcionamento.md)
- Regras de código: [regras_e_padroes.md](regras_e_padroes.md)
- **Schema Firestore**: [docs/firestore/schema.md](docs/firestore/schema.md)
- **Migração Graph API**: [docs/api-migration.md](docs/api-migration.md)
- Auditoria: [docs/auditoria/README.md](docs/auditoria/README.md)
- Módulo WhatsApp: [docs/whatsapp/README.md](docs/whatsapp/README.md)
- Referências Meta/WhatsApp: [docs/reference/meta/README.md](docs/reference/meta/README.md)

## Rodar local

    python -m venv .venv
    source .venv/bin/activate
    pip install -e .[dev]
    uvicorn pyloto_corp.api.app:app --reload --port 8080

## Variáveis principais

Configuração completa em [.env.exemplo](.env.exemplo). Principais:

**WhatsApp/Meta API:**

- `WHATSAPP_VERIFY_TOKEN` — Token de verificação do webhook
- `WHATSAPP_WEBHOOK_SECRET` — HMAC SHA-256 para validação
- `WHATSAPP_ACCESS_TOKEN` — Bearer token (usar Secret Manager em prod)
- `WHATSAPP_PHONE_NUMBER_ID` — ID do número registrado

**Infraestrutura:**

- `ENVIRONMENT` — development | staging | production
- `DEDUPE_BACKEND` — memory | redis
- `REDIS_URL` — URL de conexão Redis (se dedupe_backend=redis)
- `FIRESTORE_PROJECT_ID` — ID do projeto GCP
- `GCS_BUCKET_MEDIA` — Bucket para mídia WhatsApp
- `GCS_BUCKET_EXPORT` — Bucket para exportações

**Segurança:**

- `ZERO_TRUST_MODE` — Validar assinatura sempre (default: true)
- `PEPPER_SECRET` — Para derivar user_key via HMAC

## Endpoints mínimos

- `GET /health`
- `GET /webhooks/whatsapp` (verificação Meta)
- `POST /webhooks/whatsapp` (inbound)
