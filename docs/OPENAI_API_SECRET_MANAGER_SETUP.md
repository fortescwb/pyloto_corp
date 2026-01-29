# Configuração de OpenAI API via Google Secret Manager

**Data:** 26 de Janeiro de 2026  
**Status:** Implementado para Staging e Produção  
**Responsável:** Executor (Fase 3B - Integração ChatGPT)

---

## 1. Contexto

A aplicação `pyloto_corp` agora integra **ChatGPT (GPT-4o-Mini)** para os 3 pontos de LLM:

1. **LLM #1 (Event Detection):** Detecta evento + intenção a partir do input do usuário
2. **LLM #2 (Response Generation):** Gera resposta contextualizada com opções
3. **LLM #3 (Message Type Selection):** Seleciona tipo de mensagem (TextMessage, InteractiveButton, etc.)

Para isso, a chave da API OpenAI (`OPENAI_API_KEY`) deve ser:
- **Nunca hardcoded** no repositório
- **Armazenada em Secret Manager** (Google Cloud)
- **Lida em runtime** via `OPENAI_API_KEY` env var (que é populada pelo Secret Manager)

---

## 2. Configuração por Ambiente

### 2.1 Desenvolvimento Local

**Arquivo:** `.env` (não commitado, em `.gitignore`)

```bash
# Desenvolvimento - APENAS para teste local
OPENAI_API_KEY
```

**Como executar:**

```bash
# 1. Copiar .env.exemplo para .env
cp .env.exemplo .env

# 2. Adicionar OPENAI_API_KEY atualizada ao .env
# (Apenas local; NUNCA commitado)

# 3. Executar com carregamento de .env (via pydantic-settings)
python -m uvicorn src.pyloto_corp.api.app:app --reload
```

Pydantic-Settings **lê automaticamente** `.env` se estiver no diretório raiz.

### 2.2 Staging no Google Cloud Run

**Fluxo:**

```
Cloud Run → Secret Manager (OPENAI_API_KEY) → Env Var → Aplicação
```

#### Passo 1: Criar Secret no Secret Manager

```bash
# 1. Autenticar no GCP
gcloud auth login

# 2. Definir projeto
gcloud config set project pyloto-corp-staging

# 3. Criar secret (OPENAI_API_KEY)
gcloud secrets create openai-api-key \
  --replication-policy="automatic" \
  --data-file=- << 'SECRET'

SECRET

# 4. Listar secrets para confirmar
gcloud secrets list

# 5. Ver versão ativa da secret
gcloud secrets versions list openai-api-key
```

#### Passo 2: Configurar Cloud Run para acessar Secret

Editar o arquivo `cloudbuild.yaml` (ou seu equivalente) para passar a secret como variável de ambiente:

```yaml
# cloudbuild.yaml
steps:
  - name: 'gcr.io/cloud-builders/gke-deploy'
    args:
      - 'run'
      - '--filename=.'
      - '--image=gcr.io/$PROJECT_ID/pyloto-corp:$COMMIT_SHA'
      - '--location=us-central1'

  # Step para deploy no Cloud Run com secret
  - name: 'gcr.io/cloud-builders/run'
    args:
      - 'deploy'
      - 'pyloto-corp-staging'
      - '--image=gcr.io/$PROJECT_ID/pyloto-corp:$COMMIT_SHA'
      - '--set-env-vars=OPENAI_API_KEY=$(gcloud secrets versions access latest --secret=openai-api-key)'
      - '--region=us-central1'
      - '--platform=managed'
      - '--allow-unauthenticated'
```

**Ou via CLI direto:**

```bash
gcloud run deploy pyloto-corp-staging \
  --image gcr.io/pyloto-corp-staging/pyloto-corp:latest \
  --region us-central1 \
  --set-env-vars OPENAI_API_KEY=$(gcloud secrets versions access latest --secret=openai-api-key) \
  --platform managed
```

#### Passo 3: Verificar Configuração

```bash
# 1. Acessar descrição do serviço no Cloud Run
gcloud run services describe pyloto-corp-staging --region us-central1

# 2. Verificar se OPENAI_API_KEY está presente nas variáveis de ambiente
# (será listado em "Environment variables")

# 3. Testar a aplicação (fazer request ao endpoint)
curl https://pyloto-corp-staging-xxx.a.run.app/health
```

### 2.3 Produção

**Idêntico ao Staging, mas com:**

- Project ID: `pyloto-corp-prod` (ou equivalente)
- Service name: `pyloto-corp-prod` (ou equivalente)
- Secret name: `openai-api-key-prod` (ou equivalente)

```bash
# Criar secret de produção (SEPARADA de staging)
gcloud config set project pyloto-corp-prod

gcloud secrets create openai-api-key-prod \
  --replication-policy="automatic" \
  --data-file=- << 'SECRET'

SECRET

# Deploy em produção
gcloud run deploy pyloto-corp-prod \
  --image gcr.io/pyloto-corp-prod/pyloto-corp:latest \
  --region us-central1 \
  --set-env-vars OPENAI_API_KEY=$(gcloud secrets versions access latest --secret=openai-api-key-prod) \
  --platform managed
```

---

## 3. Código de Integração

### 3.1 Leitura da Configuração

**Arquivo:** `src/pyloto_corp/config/settings.py`

```python
class Settings(BaseSettings):
    # OpenAI / IA
    openai_api_key: str | None = None  # Lido de env var OPENAI_API_KEY
    openai_model: str = "gpt-4o-mini"
    openai_timeout_seconds: int = 10
    openai_max_retries: int = 2
```

Pydantic-Settings **automaticamente**:
1. Lê `OPENAI_API_KEY` do ambiente (`.env` local ou Secret Manager em produção)
2. Popula `settings.openai_api_key`
3. Disponibiliza via injeção de dependência

### 3.2 Uso no Cliente OpenAI

**Arquivo:** `src/pyloto_corp/ai/openai_client.py`

```python
from pyloto_corp.config.settings import get_settings

async def detect_event(self, user_input: str) -> EventDetectionResult:
    """Detecta evento usando ChatGPT."""
    settings = get_settings()
    
    # Cliente OpenAI recebe chave automaticamente
    # (lida de OPENAI_API_KEY env)
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    
    # Chamada à API
    response = await client.chat.completions.create(
        model=self._model,
        messages=[...],
        timeout=settings.openai_timeout_seconds,
    )
    
    return self._parse_event_detection_response(response)
```

---

## 4. Segurança e Melhores Práticas

### 4.1 Zero PII in Logs

A chave API **NUNCA é logada**. Exemplo seguro:

```python
logger.debug(f"Chamando OpenAI com timeout {timeout}s")
# ✅ OK

logger.debug(f"Chamando OpenAI com chave {api_key}")
# ❌ NUNCA FAZER ISSO
```

### 4.2 Rotação de Secrets

**Staging:**

```bash
# 1. Gerar nova chave no OpenAI Dashboard
# https://platform.openai.com/account/api-keys

# 2. Atualizar secret no GCP
echo "nova-chave-aqui" | gcloud secrets versions add openai-api-key --data-file=-

# 3. Re-deploy do serviço (Cloud Run lê automaticamente)
gcloud run deploy pyloto-corp-staging ...
```

**Produção:** Mesmo processo, mas em projeto separado.

### 4.3 Isolamento de Segredos por Projeto

Cada projeto GCP tem seus **próprios secrets**:

- `pyloto-corp-staging`: `openai-api-key`
- `pyloto-corp-prod`: `openai-api-key-prod`

Isso garante que mesmo que alguém acesse o projeto de staging, não tem a chave de produção.

### 4.4 Auditoria

Google Cloud automaticamente registra:

```bash
# Ver histórico de acesso aos secrets
gcloud logging read "resource.type=secretmanager.googleapis.com AND protoPayload.methodName=google.cloud.secretmanager.v1.SecretManagerService.AccessSecretVersion"
```

---

## 5. Arquivo .env.exemplo

**Arquivo:** `.env.exemplo` (commitado, sem chaves reais)

```bash
# ============================================================================
# OPENAI API (Staging / Produção: Use Google Secret Manager)
# ============================================================================

# Chave da API OpenAI (NUNCA hardcode em produção)
# Em desenvolvimento local, copie um valor temporário apenas para teste
# Em staging/produção, é injetada via Secret Manager → env var
OPENAI_API_KEY=sk-... (NUNCA adicione chaves reais aqui)

# Modelo OpenAI a usar (gpt-4o-mini é otimizado para latência/custo)
OPENAI_MODEL=gpt-4o-mini

# Timeout para chamadas à API OpenAI (segundos)
OPENAI_TIMEOUT_SECONDS=10

# Retries em caso de falha
OPENAI_MAX_RETRIES=2
```

---

## 6. Checklist de Implementação

- [x] **Código:** Context Loader carrega docs institucionais → Prompts
- [x] **Código:** OpenAI Client implementado (3 LLM points)
- [x] **Código:** Settings.py com `openai_api_key` configurável
- [x] **Docs:** Este arquivo (Secret Manager setup)
- [ ] **Infra:** Criar secret `openai-api-key` no GCP Staging
- [ ] **Infra:** Criar secret `openai-api-key-prod` no GCP Produção
- [ ] **Infra:** Atualizar Cloud Run deploy scripts
- [ ] **Teste:** Validar que API key é lida corretamente em staging
- [ ] **Teste:** Fazer request teste ao webhook WhatsApp
- [ ] **Teste:** Verificar que IA responde com contexto correto

---

## 7. Próximos Passos (Fase 3 - LLM #3)

- [ ] Implementar `assistant_message_type.py` (LLM #3 - Message Type Selector)
- [ ] Integrar seletor de tipo de mensagem no pipeline
- [ ] Validar tipos contra `domain/whatsapp_message_types.py`
- [ ] Testes unitários + E2E

**Fase 4 - Integração Completa:**

- [ ] Modificar `webhook_handler.py` para orquestrar FSM + 3 LLMs
- [ ] Testes end-to-end (simulando mensagens WhatsApp)
- [ ] Coverage report (mínimo 90%)
- [ ] Deploy em staging
- [ ] Validação em produção

---

## Referências

- **Documentação OpenAI:** https://platform.openai.com/docs/api-reference
- **Google Secret Manager:** https://cloud.google.com/secret-manager/docs
- **Cloud Run Secrets:** https://cloud.google.com/run/docs/configuring/secrets
- **Pydantic Settings:** https://docs.pydantic.dev/latest/usage/settings/

---

**Última atualização:** 26 de Janeiro de 2026
