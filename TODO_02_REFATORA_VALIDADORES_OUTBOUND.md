# TODO List — Refatorar e Completar Módulos (Parte 1: Validadores e Outbound)

## ⚠️ IMPORTANTE: Fontes de Verdade

Todas as alterações neste documento devem estar **alinhadas com as fontes de verdade** do projeto:

- **[Funcionamento.md](Funcionamento.md)** — Especificações do produto, fluxos, outcomes e contrato de handoff
- **[README.md](README.md)** — Visão geral, status e documentação
- **[regras_e_padroes.md](regras_e_padroes.md)** — Padrões de código, segurança e organização

**Ao completar cada tarefa**, atualize os arquivos acima conforme necessário para refletir as mudanças implementadas.

---

## 3.2.1 Refatorar Validadores

### ☐ Criar módulo centralizado de constantes WhatsApp

**Descrição:**
Consolidar todos os limites, tamanhos máximos e constantes de validação em módulo único.

**Arquivo:**
`src/pyloto_corp/adapters/whatsapp/limits.py`

**Constantes a Definir:**
- `MAX_MESSAGE_LENGTH_CHARS` — Comprimento máximo da mensagem de texto
- `MAX_IMAGE_SIZE_MB` — Tamanho máximo de imagem
- `MAX_VIDEO_SIZE_MB` — Tamanho máximo de vídeo
- `MAX_AUDIO_SIZE_MB` — Tamanho máximo de áudio
- `MAX_DOCUMENT_SIZE_MB` — Tamanho máximo de documento
- `SUPPORTED_IMAGE_TYPES` — Lista de tipos MIME aceitos
- `SUPPORTED_VIDEO_TYPES` — Lista de tipos MIME aceitos
- `SUPPORTED_AUDIO_TYPES` — Lista de tipos MIME aceitos
- `SUPPORTED_DOCUMENT_TYPES` — Lista de tipos MIME aceitos
- `MAX_INTERACTIVE_BUTTONS` — Número máximo de botões interativos
- `MAX_LIST_ITEMS` — Número máximo de itens em lista
- `MAX_TEMPLATE_PARAMETERS` — Número máximo de parâmetros em template

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

### ☐ Criar TextMessageValidator

**Descrição:**
Classe responsável por validar mensagens de texto.

**Arquivo:**
`src/pyloto_corp/adapters/whatsapp/validators/text.py`

**Responsabilidades:**
- Validar comprimento (≤ `MAX_MESSAGE_LENGTH_CHARS`)
- Validar caracteres especiais (conforme Meta API)
- Validar variáveis de template (${1}, ${2}, etc.)
- Retornar resultado estruturado com detalhes de erro

**Critério de Aceitação:**
- Classe implementada com método `validate() -> ValidationResult`
- Testes unitários com cobertura >90%
- Rejeita mensagens acima do limite
- Aceita variáveis de template válidas

**Notas de Implementação:**
- Usar `pydantic` para `ValidationResult`
- Mensagens de erro em português (conforme `regras_e_padroes.md`)
- Considerar logs estruturados para rejeições

---

### ☐ Criar MediaMessageValidator

**Descrição:**
Classe responsável por validar mensagens com mídia (imagem, vídeo, áudio, documento).

**Arquivo:**
`src/pyloto_corp/adapters/whatsapp/validators/media.py`

**Responsabilidades:**
- Validar tipo MIME do arquivo
- Validar tamanho do arquivo
- Validar duração (vídeo, áudio)
- Validar resolução mínima (imagem, vídeo)
- Retornar resultado estruturado com detalhes de erro

**Critério de Aceitação:**
- Classe implementada com método `validate(file_info) -> ValidationResult`
- Testes unitários com cobertura >90%
- Rejeita tipos MIME não suportados
- Rejeita arquivos acima do tamanho limite

**Notas de Implementação:**
- Importar constantes de `limits.py`
- Validar metadados de arquivo (sem necessidade de download completo)
- Logs estruturados em caso de rejeição

---

### ☐ Criar InteractiveMessageValidator

**Descrição:**
Classe responsável por validar mensagens interativas (botões, listas, flows).

**Arquivo:**
`src/pyloto_corp/adapters/whatsapp/validators/interactive.py`

**Responsabilidades:**
- Validar número de botões (≤ `MAX_INTERACTIVE_BUTTONS`)
- Validar número de itens em lista (≤ `MAX_LIST_ITEMS`)
- Validar estrutura de resposta (id, title, description)
- Validar payload máximo de resposta
- Retornar resultado estruturado

**Critério de Aceitação:**
- Classe implementada com método `validate(interactive_msg) -> ValidationResult`
- Testes unitários com cobertura >90%
- Rejeita botões em excesso
- Rejeita estruturas malformadas

**Notas de Implementação:**
- Suportar botões de ação, listas, flows
- Validar IDs únicos dentro da mensagem
- Logs estruturados para debug

---

### ☐ Criar TemplateMessageValidator

**Descrição:**
Classe responsável por validar mensagens de template.

**Arquivo:**
`src/pyloto_corp/adapters/whatsapp/validators/template.py`

**Responsabilidades:**
- Validar namespace do template
- Validar nome do template
- Validar número de parâmetros (≤ `MAX_TEMPLATE_PARAMETERS`)
- Validar tipos de parâmetros
- Validar idioma (opcional)
- Retornar resultado estruturado

**Critério de Aceitação:**
- Classe implementada com método `validate(template_msg) -> ValidationResult`
- Testes unitários com cobertura >90%
- Rejeita templates não registradas
- Rejeita parâmetros inválidos

**Notas de Implementação:**
- Integrar com `TemplateManager` (quando disponível)
- Validar contra cache local de templates
- Logs estruturados para falhas

---

### ☐ Atualizar WhatsAppMessageValidator (orquestrador)

**Descrição:**
Refatorar classe existente para orquestrar os validadores especializados.

**Arquivo:**
`src/pyloto_corp/adapters/whatsapp/validators/__init__.py`

**Responsabilidades:**
- Receber mensagem normalizada
- Determinar tipo (text, image, video, audio, document, interactive, template)
- Delegar para validador apropriado
- Agregar resultados
- Retornar `ValidationResult` combinado

**Critério de Aceitação:**
- Classe refatorada para orquestrar validadores
- Todos os testes existentes continuam passando
- Novo método `validate() -> ValidationResult` implementado
- Backward compatibility mantida onde necessário

**Notas de Implementação:**
- Usar injeção de dependência para validadores
- Considerar cache de resultados
- Facilitar adição de novos tipos de mensagem

---

### ☐ Adicionar testes unitários para validadores

**Descrição:**
Criar suite completa de testes para todos os validadores.

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

### ☐ Criar MediaUploader

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

### ☐ Criar TemplateManager

**Descrição:**
Classe responsável por gerenciamento de templates (carregar, validar, sincronizar).

**Arquivo:**
`src/pyloto_corp/adapters/whatsapp/template_manager.py`

**Responsabilidades:**
- Carregar templates do Firestore (cache local)
- Sincronizar templates da Graph API periodicamente
- Validar estrutura de template
- Retornar metadados de template (parâmetros, categoria)
- Implementar cache com TTL

**Interface:**
```python
class TemplateManager:
    async def get_template(
        self,
        namespace: str,
        name: str
    ) -> TemplateMetadata:
        """Busca template do cache"""
        pass

    async def sync_templates(self) -> int:
        """Sincroniza templates da API Meta"""
        pass
```

**Critério de Aceitação:**
- Classe implementada com métodos principais
- Cache local em Firestore funcionando
- Sincronização automática implementada
- Testes com templates reais (mocks)
- Logs de sincronização estruturados

**Notas de Implementação:**
- Usar store `TemplateStore` (a criar)
- Cache TTL: 24 horas
- Sincronizar automaticamente a cada 12 horas
- Tratar templates deletadas
- Logs de mudanças detectadas

---

### ☐ Criar FlowSender

**Descrição:**
Classe responsável por envio de mensagens Flow com criptografia/decriptografia conforme Meta.

**Arquivo:**
`src/pyloto_corp/adapters/whatsapp/flow_sender.py`

**Responsabilidades:**
- Construir mensagem Flow para envio
- Implementar validação de assinatura (`flow_token_signature`)
- Implementar resposta com criptografia AES-GCM
- Responder a health checks
- Registrar logs estruturados

**Interface:**
```python
class FlowSender:
    async def send_flow(
        self,
        recipient_id: str,
        flow_id: str,
        flow_data: Dict
    ) -> FlowResponse:
        """Envia flow ao cliente"""
        pass

    async def handle_flow_response(
        self,
        flow_token: str,
        encrypted_data: str,
        signature: str
    ) -> Dict:
        """Processa resposta decriptada do flow"""
        pass

    async def health_check(self) -> bool:
        """Health check para Meta"""
        pass
```

**Critério de Aceitação:**
- Classe implementada com métodos principais
- Criptografia AES-GCM funcionando
- Validação de assinatura implementada
- Health check respondendo
- Testes com flows reais (mocks)

**Notas de Implementação:**
- Usar `cryptography` library para AES-GCM
- Chaves RSA armazenadas em Secret Manager
- Renovar chaves conforme Meta recomenda
- Documentar processo em `docs/flows/encryption.md`
- Logs sem expor dados criptografados

---

## 3.2.3 Integração Outbound com Dedupli cação

### ☐ Implementar dedup de mensagens outbound

**Descrição:**
Garantir que mensagens outbound não sejam enviadas duplicadas via idempotência persistente.

**Critério de Aceitação:**
- Store de `OutboundDedupeKey` criado em Firestore
- `idempotency_key` incluído em todas as chamadas de envio
- Retry de mesma mensagem com mesmo `idempotency_key` não causa envio duplicado
- TTL configurável para cleanup de chaves antigas

**Notas de Implementação:**
- Usar `OutboundDedupeStore` (criar em Persistência e Stores)
- Gerar `idempotency_key` consistente: hash(recipient_id + message_content + timestamp)
- TTL: 24 horas (cobrir retries + reconciliação)
- Logs de dedupe hit/miss

---

## Checklist Final

- [ ] Módulo `limits.py` criado com todas as constantes
- [ ] `TextMessageValidator` implementado e testado
- [ ] `MediaMessageValidator` implementado e testado
- [ ] `InteractiveMessageValidator` implementado e testado
- [ ] `TemplateMessageValidator` implementado e testado
- [ ] `WhatsAppMessageValidator` refatorado como orquestrador
- [ ] Testes unitários completos (cobertura >90%)
- [ ] `WhatsAppHttpClient` implementado com retry/backoff
- [ ] `MediaUploader` implementado com GCS integration
- [ ] `TemplateManager` implementado com cache e sync
- [ ] `FlowSender` implementado com criptografia
- [ ] Dedup de outbound integrado
- [ ] [README.md](README.md) atualizado com novo módulo WhatsApp
- [ ] Testes de integração com Graph API v24.0 passando

---

**Status:** ⏳ Não iniciado | 🚀 Em andamento | ✅ Completo
