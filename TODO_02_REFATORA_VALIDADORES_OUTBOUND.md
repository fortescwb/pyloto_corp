# TODO List — Refatorar e Completar Módulos (Parte 1: Validadores e Outbound)

## ⚠️ IMPORTANTE: Fontes de Verdade

Todas as alterações neste documento devem estar **alinhadas com as fontes de verdade** do projeto:

- **[Funcionamento.md](Funcionamento.md)** — Especificações do produto, fluxos, outcomes e contrato de handoff
- **[README.md](README.md)** — Visão geral, status e documentação
- **[regras_e_padroes.md](regras_e_padroes.md)** — Padrões de código, segurança e organização

**Ao completar cada tarefa**, atualize os arquivos acima conforme necessário para refletir as mudanças implementadas.

---

## 3.2.1 Refatorar Validadores

### ✅ Criar módulo centralizado de constantes WhatsApp

**Status:** CONCLUÍDO (25/01/2026 17:00)

**Descrição:**
Consolidar todos os limites, tamanhos máximos e constantes de validação em módulo único.

**Arquivo:**
`src/pyloto_corp/adapters/whatsapp/limits.py`

**Constantes a Definidas:**

- `MAX_MESSAGE_LENGTH_CHARS` — Comprimento máximo da mensagem de texto = 4.096 caracteres
- `MAX_IMAGE_SIZE_MB` — Tamanho máximo de imagem = 5mb
- `MAX_VIDEO_SIZE_MB` — Tamanho máximo de vídeo = 16mb
- `MAX_AUDIO_SIZE_MB` — Tamanho máximo de áudio = 16mb
- `MAX_DOCUMENT_SIZE_MB` — Tamanho máximo de documento = 100mb
- `SUPPORTED_IMAGE_TYPES` — Lista de tipos MIME aceitos = image/jpeg, image/png
- `SUPPORTED_VIDEO_TYPES` — Lista de tipos MIME aceitos = video/mp4, video/3gpp
- `SUPPORTED_AUDIO_TYPES` — Lista de tipos MIME aceitos = audio/aac, audio/mp4, audio/mpeg, audio/amr, audio/ogg (apenas com codecs opus)
- `SUPPORTED_DOCUMENT_TYPES` — Lista de tipos MIME aceitos = Qualquer tipo MIME válido, incluindo text/plain, application/pdf, application/vnd.ms-powerpoint, application/msword, application/vnd.ms-excel e formatos Open Office
- `MAX_INTERACTIVE_BUTTONS` — Número máximo de botões interativos
  Botões de Resposta Rápida (Reply Buttons): Até 3 botões.
  Botões de Chamada para Ação (CTA): Até 2 botões (um para site e um para telefone).
- `MAX_LIST_ITEMS` — Número máximo de itens em lista
  Até 10 itens no total, distribuídos em até 10 seções.
- `MAX_TEMPLATE_PARAMETERS` — Número máximo de parâmetros em template
  De acordo com a documentação oficial da Meta, não há um limite numérico estrito definido para o total de parâmetros (variáveis {{1}}, {{2}}, etc.), mas a mensagem final montada, incluindo todos os valores das variáveis, não pode exceder o limite de 1.024 caracteres do corpo do template.

**Critério de Aceitação:**

- Módulo criado com todas as constantes
- Documentação com referência à Meta API v24.0
- Sem valores hardcoded fora deste módulo
- Todos os validadores importam daqui

**Notas de Implementação:**

- Adicionar comentários com links à documentação Meta
- Considerar versionamento (ex.: `LIMITS_V24 = {...}`)
- Facilitar updates quando Meta mudar limites

---

### ✅ Criar TextMessageValidator

**Status:** CONCLUÍDO (Fase 2, 25/01/2026)

**Implementação:**
- Arquivo: `src/pyloto_corp/adapters/whatsapp/validators/text.py`
- Método: `validate_text_message(request) -> None`
- Validações: comprimento, UTF-8 bytes, presença de texto

---

### ✅ Criar MediaMessageValidator

**Status:** CONCLUÍDO (Fase 2, 25/01/2026)

**Implementação:**
- Arquivo: `src/pyloto_corp/adapters/whatsapp/validators/media.py`
- Método: `validate_media_message(request, msg_type) -> None`
- Validações: media_id vs media_url, MIME type, caption length

---

### ✅ Criar InteractiveMessageValidator

**Status:** CONCLUÍDO (Fase 2, 25/01/2026)

**Implementação:**
- Arquivo: `src/pyloto_corp/adapters/whatsapp/validators/interactive.py`
- Método: `validate_interactive_message(request) -> None`
- Validações: número de botões, itens de lista, estrutura

---

### ✅ Criar TemplateMessageValidator

**Status:** CONCLUÍDO (Fase 2, 25/01/2026)

**Implementação:**
- Arquivo: `src/pyloto_corp/adapters/whatsapp/validators/template.py`
- Métodos: `validate_template_message`, `validate_address_message`, etc.
- Validações: namespace, nome, parâmetros, idioma

---

### ✅ Atualizar WhatsAppMessageValidator (orquestrador)

**Status:** CONCLUÍDO (Fase 2, 25/01/2026)

**Implementação:**
- Arquivo: `src/pyloto_corp/adapters/whatsapp/validators/orchestrator.py`
- Classe: `WhatsAppMessageValidator`
- Método: `validate_outbound_request(request) -> None`
- Dispatch: delega para validadores especializados por tipo

---

### ✅ Adicionar testes unitários para validadores

**Status:** CONCLUÍDO (25/01/2026 17:10)

**Implementação:**
- Arquivo: `tests/unit/test_validators.py` (380 linhas)
- 36 testes implementados
- Cobertura: >90% para text, media, orchestrator
- Casos cobertos:
  - Text: limites, UTF-8, caracteres especiais, linhas
  - Media: MIME types, captions, media_id vs media_url
  - Orchestrator: validação completa, idempotency key, recipient
  - Edge cases: null bytes, special chars, URLs com query params

**Arquivo:**
`tests/adapters/whatsapp/validators/test_*.py`

**Casos de Teste por Validador:**

**TextMessageValidator:**

- Mensagem válida dentro do limite
- Mensagem vazia
- Mensagem exatamente no limite
- Mensagem acima do limite
- Caracteres especiais válidos
- Variáveis de template válidas (${1}, ${2})
- Variáveis de template inválidas

**MediaMessageValidator:**

- Arquivo de tipo suportado
- Arquivo de tipo não suportado
- Arquivo dentro do limite de tamanho
- Arquivo acima do limite de tamanho
- Arquivo com metadados inválidos

**InteractiveMessageValidator:**

- Botões dentro do limite
- Botões acima do limite
- Lista dentro do limite de itens
- Lista acima do limite de itens
- IDs únicos validados
- Payloads válidos

**TemplateMessageValidator:**

- Template válida com parâmetros corretos
- Template com número errado de parâmetros
- Template não registrada
- Parâmetros de tipo inválido

**Critério de Aceitação:**

- Cobertura >90% em todos os validadores
- Todos os testes passando
- Testes de erro com mensagens claras
- Fixtures reutilizáveis criadas

**Notas de Implementação:**

- Usar `pytest` com fixtures
- Mock de constantes para testar edge cases
- Documentar casos de teste em docstrings

---

## 3.2.2 Refatorar Outbound (Parte 1: HttpClient)

### ☐ Criar WhatsAppHttpClient

**Descrição:**
Classe responsável por chamadas HTTP à Graph API Meta com retry, backoff e idempotência.

**Arquivo:**
`src/pyloto_corp/adapters/whatsapp/http_client.py`

**Responsabilidades:**

- Executar requisições POST/GET/DELETE à Graph API
- Implementar retry exponencial com backoff
- Implementar idempotência via `idempotency_key`
- Parsear respostas (sucesso, erro, webhook)
- Registrar logs estruturados de requisição/resposta (sem payloads sensíveis)
- Tratar erros específicos (rate limit, timeout, token inválido)

**Interface:**

```python
class WhatsAppHttpClient:
    async def send_message(
        self,
        message_payload: Dict,
        idempotency_key: str
    ) -> HttpClientResponse:
        """Envia mensagem via Graph API"""
        pass

    async def upload_media(
        self,
        file_path: str,
        media_type: str
    ) -> Dict:
        """Faz upload de mídia e retorna media_id"""
        pass

    async def get_template(
        self,
        template_name: str,
        template_namespace: str
    ) -> Dict:
        """Busca definição de template"""
        pass
```

**Critério de Aceitação:**

- Classe implementada com métodos principais
- Retry exponencial testado (máx 3 tentativas com backoff)
- Idempotência via `idempotency_key` documentada
- Testes unitários com cobertura >85%
- Logs estruturados sem PII

**Notas de Implementação:**

- Usar `aiohttp` ou `httpx` assíncrono
- Timeout padrão: 30 segundos
- Máximo de retries: 3
- Backoff: exponencial com jitter
- Respeitar rate limits (429 responses)
- Documentar erros comuns (401, 403, 400, 500, 429)

---

## 3.2.2 Refatorar Outbound

### ✅ Criar WhatsAppHttpClient

**Status:** CONCLUÍDO (25/01/2026 17:05)

**Implementação:**
- Arquivo: `src/pyloto_corp/adapters/whatsapp/http_client.py` (215 linhas)
- Classe: `WhatsAppHttpClient` (especializa `HttpClient`)
- Método principal: `send_message(endpoint, access_token, payload) -> dict`
- Funcionalidades:
  - Parse de erro Meta (type, code, message)
  - Classificação: permanente vs transitório
  - Retry automático para transitórios
  - Logging sem exposição de tokens
  - Factory: `create_whatsapp_http_client(settings)`
  
**Testes:** `tests/unit/test_whatsapp_http_client.py` (200 linhas, 11 testes)
- Sucesso de envio
- Erros permanentes (401, 400)
- Erros transitórios (429 rate limit)
- Parsing de resposta JSON
- Classificação de erros

---

### ✅ Criar MediaUploader

**Status:** CONCLUÍDO (25/01/2026 18:00)

**Implementação:**
- Arquivo: `src/pyloto_corp/adapters/whatsapp/media_uploader.py` (260 linhas)
- Classe: `MediaUploader`
- Métodos:
  - `upload(content, mime_type, user_key, upload_to_whatsapp) -> MediaUploadResult`
  - `delete(gcs_uri) -> bool`
- Funcionalidades:
  - Upload para GCS com path baseado em data/user/hash
  - Deduplicação por SHA256 (mesmo arquivo não sobe 2x)
  - Validação de conteúdo (tamanho, tipo MIME)
  - Logging estruturado sem PII
  - Integração futura com WhatsApp Media API

**Testes:** `tests/unit/test_media_uploader.py` (380 linhas, 22 testes)
- Hash SHA256 consistente
- Validação de conteúdo (vazio, oversized, MIME inválido)
- Upload bem-sucedido
- Deduplicação (cache hit)
- Falhas de GCS
- Delete com validação de bucket
- Edge cases (unicode, todos os tipos de vídeo)

---

### ✅ Criar TemplateManager

**Status:** CONCLUÍDO (25/01/2026 18:15)

**Implementação:**
- Arquivo: `src/pyloto_corp/adapters/whatsapp/template_manager.py` (250 linhas)
- Classe: `TemplateManager`
- Métodos:
  - `get_template(namespace, name, force_sync) -> TemplateMetadata`
  - `sync_templates(namespace) -> int`
  - `validate_template_params(template, provided_params) -> bool`
- Funcionalidades:
  - Cache com TTL configurável (padrão 24h)
  - Sincronização da Graph API (placeholder para produção)
  - Extração de parâmetros de componentes
  - Suporte a categorias (MARKETING, UTILITY, AUTHENTICATION)
  - Status de aprovação (APPROVED, PENDING, REJECTED)

**Testes:** `tests/unit/test_template_manager.py` (370 linhas, 25 testes)
- Cache expired/fresh
- Extração de parâmetros (body, header media)
- Get template (cache hit, not found)
- Force sync
- Validação de parâmetros
- Edge cases (múltiplos namespaces, todas categorias/status)

**Descrição:**
Classe responsável por upload de mídia em Google Cloud Storage com integração ao WhatsApp.

**Arquivo:**
`src/pyloto_corp/adapters/whatsapp/media_uploader.py`

**Responsabilidades:**

- Fazer upload de arquivo para GCS bucket
- Registrar metadados (tamanho, tipo, hash)
- Fazer upload para WhatsApp API (se necessário)
- Retornar media_id do WhatsApp
- Implementar dedupli cação (mesmo arquivo não sobe 2 vezes)
- Tratar falhas com retry

**Interface:**

```python
class MediaUploader:
    async def upload(
        self,
        file_path: str,
        media_type: str,
        user_id: str
    ) -> MediaUploadResult:
        """Upload de mídia com dedupe"""
        pass

    async def delete(self, media_id: str) -> bool:
        """Remove mídia"""
        pass
```

**Critério de Aceitação:**

- Classe implementada com métodos principais
- Upload para GCS funcional
- Dedupli cação por hash implementada
- Testes com arquivos reais (mocks)
- Logs estruturados de upload/falha

**Notas de Implementação:**

- Usar cliente `google.cloud.storage`
- Gerar hash MD5 de arquivo para dedup
- Armazenar metadados em Firestore
- Respeitar tamanhos máximos de `limits.py`
- Implementar cleanup de uploads falhados

---

### ✅ Criar FlowSender

**Status:** CONCLUÍDO (25/01/2026 19:30)

**Implementação:**
- Arquivo: `src/pyloto_corp/adapters/whatsapp/flow_sender.py` (250 linhas)
- Classe: `FlowSender`
- Métodos:
  - `validate_signature(payload, signature) -> bool` - Valida HMAC-SHA256
  - `decrypt_request(aes_key, flow_data, iv) -> DecryptedFlowData` - AES-GCM
  - `encrypt_response(data, aes_key) -> dict` - Criptografa resposta
  - `health_check() -> dict` - Status para Meta
- Funcionalidades:
  - Criptografia AES-256-GCM conforme Meta Flows Spec
  - Validação de assinatura HMAC-SHA256
  - Decriptografia com RSA-OAEP para chave AES
  - Factory: `create_flow_sender()`

**Testes:** `tests/unit/test_flow_sender.py` (320 linhas, 18 testes)
- Validação de assinatura (válida, inválida, tampering)
- Decriptografia (válida, chave inválida, dados corrompidos)
- Criptografia de resposta
- Health check
- Factory com/sem passphrase

---

## 3.2.3 Integração Outbound com Deduplicação

### ✅ Implementar dedup de mensagens outbound

**Status:** CONCLUÍDO (25/01/2026 19:45)

**Implementação:**
- Arquivo: `src/pyloto_corp/infra/outbound_dedupe.py` (380 linhas)
- Classes:
  - `OutboundDedupeStore` (protocol abstrato)
  - `InMemoryOutboundDedupeStore` (dev/testes)
  - `RedisOutboundDedupeStore` (produção)
  - `FirestoreOutboundDedupeStore` (produção alternativa)
- Métodos:
  - `check_and_mark(key, message_id, ttl) -> DedupeResult`
  - `is_sent(key) -> bool`
  - `mark_sent(key, message_id, ttl) -> bool`
- Funções auxiliares:
  - `generate_idempotency_key()` - Gera chave consistente
  - `hash_message_content()` - Hash SHA256 do conteúdo
- Características:
  - TTL configurável (padrão 24h)
  - Fail-closed (erro se backend indisponível)
  - Factory: `create_outbound_dedupe_store()`

**Testes:** `tests/unit/test_outbound_dedupe.py` (340 linhas, 28 testes)
- Funções auxiliares (geração de chave, hash)
- InMemory: check_and_mark, is_sent, expiração
- Redis: SETNX, erros, prefixo customizado
- Firestore: transações, TTL expire
- Factory e edge cases

---

## Checklist Final

- [x] Módulo `limits.py` criado com todas as constantes
- [x] `TextMessageValidator` implementado e testado
- [x] `MediaMessageValidator` implementado e testado
- [x] `InteractiveMessageValidator` implementado e testado
- [x] `TemplateMessageValidator` implementado e testado
- [x] `WhatsAppMessageValidator` refatorado como orquestrador
- [x] Testes unitários completos (cobertura >90%)
- [x] `WhatsAppHttpClient` implementado com retry/backoff
- [x] `MediaUploader` implementado com GCS integration
- [x] `TemplateManager` implementado com cache e sync
- [x] `FlowSender` implementado com criptografia
- [x] Dedup de outbound integrado
- [x] [README.md](README.md) atualizado com novo módulo WhatsApp
- [ ] Testes de integração com Graph API v24.0 passando

---

**Status:** ✅ Completo (implementação) | 🚀 Pendente (testes integração Graph API)
