# pyloto_corp

Atendimento inicial institucional/comercial da Pyloto via WhatsApp (API oficial da Meta). Este serviço **não é CRM** e **não executa operação final** — ele explica a Pyloto, identifica intenção, coleta dados mínimos, qualifica o lead e encerra com 1 outcome terminal canônico.

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

## Rodar local
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
uvicorn pyloto_corp.api.app:app --reload --port 8080
```

## Variáveis principais
- `WHATSAPP_VERIFY_TOKEN`
- `WHATSAPP_WEBHOOK_SECRET`
- `WHATSAPP_ACCESS_TOKEN`
- `WHATSAPP_PHONE_NUMBER_ID`
- `REDIS_URL`

## Endpoints mínimos
- `GET /health`
- `GET /webhooks/whatsapp` (verificação Meta)
- `POST /webhooks/whatsapp` (inbound)
