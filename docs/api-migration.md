# Guia de Migração da Graph API — pyloto_corp

Este documento descreve a versão da Graph API Meta em uso e
procedimentos para migrações futuras.

## Versão Atual

| Propriedade       | Valor                           |
| ----------------- | ------------------------------- |
| Versão            | **v24.0**                       |
| Data de lançamento| 8 de outubro de 2025            |
| Data de depreciação| ~Outubro 2027 (estimado)       |
| Documentação      | [Meta Graph API](https://developers.facebook.com/docs/graph-api) |

## URLs Base

```python
# URL padrão para chamadas API
GRAPH_API_BASE_URL = "https://graph.facebook.com"

# URL para uploads de vídeo
GRAPH_VIDEO_BASE_URL = "https://graph-video.facebook.com"

# Endpoint de mensagens
MESSAGES_ENDPOINT = f"{GRAPH_API_BASE_URL}/v24.0/{phone_number_id}/messages"
```

## Endpoints Utilizados

### WhatsApp Cloud API

| Endpoint                                      | Descrição                    |
| --------------------------------------------- | ---------------------------- |
| `POST /{phone_id}/messages`                   | Envio de mensagens           |
| `GET /{phone_id}/media/{media_id}`            | Download de mídia            |
| `POST /{phone_id}/media`                      | Upload de mídia              |
| `GET /{waba_id}/message_templates`            | Lista templates              |
| `POST /{waba_id}/message_templates`           | Criar template               |

### Webhooks

| Evento                        | Descrição                        |
| ----------------------------- | -------------------------------- |
| `messages`                    | Mensagens recebidas              |
| `message_status`              | Status de entrega                |
| `message_template_status_update` | Status de templates          |

## Ciclo de Vida das Versões

A Meta segue um ciclo previsível:

1. **Nova versão** lançada ~2x ao ano
2. **Versão anterior** suportada por ~2 anos
3. **Depreciação** anunciada com 90 dias de antecedência
4. **Remoção** após período de depreciação

## Procedimento de Migração

### 1. Monitorar Anúncios

- Acompanhar [Meta Developer Blog](https://developers.facebook.com/blog/)
- Verificar [Changelog da Graph API](https://developers.facebook.com/docs/graph-api/changelog)
- Inscrever-se em alertas de depreciação

### 2. Avaliar Breaking Changes

Verificar se a nova versão afeta:

- [ ] Estrutura de payloads de mensagem
- [ ] Campos obrigatórios/opcionais
- [ ] Formatos de resposta
- [ ] Limites de rate
- [ ] Novos campos de webhook

### 3. Atualizar Código

1. Atualizar constante em `config/settings.py`:
   ```python
   GRAPH_API_VERSION = "v25.0"  # Nova versão
   ```

2. Atualizar testes de integração

3. Validar em ambiente de staging

### 4. Deploy Gradual

1. Deploy em staging
2. Testes de ponta a ponta
3. Deploy em produção (canary)
4. Monitorar métricas
5. Rollout completo

## Breaking Changes Conhecidos

### v24.0 (Atual)

- Nenhum breaking change significativo para WhatsApp Cloud API
- Novos campos opcionais em templates

### v23.0 → v24.0

- Formato de `biz_opaque_callback_data` alterado
- Novos tipos de interactive message

## Fallback e Compatibilidade

O código suporta override da versão via variável de ambiente:

```bash
# Forçar versão específica (emergência)
WHATSAPP_API_VERSION=v23.0
```

## Referências

- [Graph API Changelog](https://developers.facebook.com/docs/graph-api/changelog)
- [WhatsApp Cloud API Docs](https://developers.facebook.com/docs/whatsapp/cloud-api)
- [Meta for Developers](https://developers.facebook.com/)

---

**Última atualização:** Janeiro 2026
**Versão do documento:** 1.0.0
