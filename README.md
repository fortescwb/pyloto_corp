# pyloto_corp

Atendimento inicial institucional/comercial da Pyloto via WhatsApp (API oficial da Meta). Este serviço **não é CRM** e **não executa operação final** — ele explica a Pyloto, identifica intenção, coleta dados mínimos, qualifica o lead e encerra com 1 outcome terminal canônico.

## Sobre Detalhes de Versão da Graph API

A URL base da API da Meta (Graph API) mais atual em
janeiro de 2026 é:
`https://graph.facebook.com`

Para o envio de mensagens via WhatsApp Cloud API, a estrutura do endpoint utiliza o ID do seu número de telefone da seguinte forma:

`https://graph.facebook.com{phone-number-id}/messages`

Detalhes Importantes:

    Versão Atual: A versão v24.0 foi lançada em 8 de outubro de 2025 e é a versão estável mais recente disponível no início de 2026.
    Protocolo: Todas as chamadas devem ser feitas obrigatoriamente via HTTPS.

Exceção de Vídeos: Para uploads de arquivos de vídeo, a URL base muda ligeiramente para `https://graph-video.facebook.com`.

## Status atual

- Módulo WhatsApp cobre 16 tipos oficiais (incluindo templates, flows, CTA URL, location request) — ver [docs/whatsapp/README.md](docs/whatsapp/README.md)
- Auditoria técnica 2025: 84% conformidade, nenhum bloqueador — ver [docs/auditoria/README.md](docs/auditoria/README.md)
- Produto e regras: fontes de verdade em [Funcionamento.md](Funcionamento.md) e [regras_e_padroes.md](regras_e_padroes.md)

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
- Auditoria: [docs/auditoria/README.md](docs/auditoria/README.md)
- Módulo WhatsApp: [docs/whatsapp/README.md](docs/whatsapp/README.md)
- Referências Meta/WhatsApp: [docs/reference/meta/README.md](docs/reference/meta/README.md)

## Rodar local

    python -m venv .venv
    source .venv/bin/activate
    pip install -e .[dev]
    uvicorn pyloto_corp.api.app:app --reload --port 8080

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
