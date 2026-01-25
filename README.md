# pyloto_corp

## Apresentação do Projeto

O `pyloto_corp` é um serviço de atendimento automatizado responsável pelo **contato inicial institucional e comercial da Pyloto**, operando principalmente via **WhatsApp (API oficial do WhatsApp/META)**. Ele atua como **porta de entrada do ecossistema Pyloto**, identificando a intenção do cliente, apresentando as diferentes vertentes de solução da Pyloto e coletando informações iniciais de forma estruturada. Com base nesses dados, o sistema qualifica o lead e realiza o roteamento adequado do atendimento.

Este serviço **não é um CRM nem executa operações finais** do negócio – ele **não finaliza vendas, não fecha contratos e não gerencia pedidos** diretamente. Seu papel é exclusivamente organizar o primeiro contato, cadastrando leads iniciais e entregando o contexto necessário para continuidade. **Toda sessão é finalizada com exatamente um _outcome_ terminal canônico**, representando o desfecho único daquela interação.

## Funcionalidades

- **Identificação de intenção**
- **Qualificação de lead**
- **Roteamento automático**
- **Coleta mínima de dados**
- **Encerramento com _outcome_ canônico**

## Tecnologias e Arquitetura

- **Linguagem:** Python 3
- **Framework:** FastAPI
- **Mensageria:** WhatsApp Cloud API (Graph API v24.0)
- **Armazenamento:** Firestore (GCP), Cloud Storage
- **Dedupe:** Redis ou memória
- **Deploy:** Google Cloud Run
- **Observabilidade:** Logs estruturados com `correlation_id`, sem PII
- **Arquitetura:** Camadas (api, domain, application, infra, adapters)

## Guia de Instalação Local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.exemplo .env
uvicorn pyloto_corp.api.app:app --reload --port 8080
```

## Configurações Importantes

- `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_WEBHOOK_SECRET`
- `FIRESTORE_PROJECT_ID`, `GCS_BUCKET_MEDIA`, `GCS_BUCKET_EXPORT`
- `DEDUPE_BACKEND`, `REDIS_URL`
- `ZERO_TRUST_MODE`, `PEPPER_SECRET`

## Padrões de Código e Qualidade

[regras_e_padroes.md]

- Máximo 200 linhas por arquivo, 50 por função
- Separação estrita de camadas
- Nenhum vazamento de PII
- Zero-trust em todo input externo
- Cobertura mínima de testes: 90%
- Linters e testes em CI obrigatórios (`ruff`, `pytest`, `coverage`)

## Monitoramento e Auditoria

- Arquivo `Monitoramento_Regras-Padroes.md` mantém rastreio de violações
- Auditoria técnica 2026: 84% conformidade, 0 violações críticas
- 227+ testes automatizados passando

## Documentação Complementar

- `Funcionamento.md`: visão de produto e fluxos
- `regras_e_padroes.md`: estilo, arquitetura, segurança
- `docs/whatsapp/`, `docs/auditoria/`, `docs/firestore/`

## Licença e Contribuição

Projeto **privado e proprietário**. Contribuições externas não são aceitas. Código mantido por equipe interna sob políticas de confidencialidade da Pyloto.

## Status atual do projeto

99% concluído
informação atualizada em 25 de janeiro de 2026 às 20:15
