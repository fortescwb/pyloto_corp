# Esse documento existe para monitorar arquivos mencionados em Relatórios de Auditoria

> **Última atualização:** 24/01/2026 - Auditoria de validação pós-refatoração.

## Possíveis status

  -Atenção
  -Alerta
  -Violação Crítica
**ESSE ARQUIVO DEVE SER MANTIDO SEMPRE ATUALIZADO**

## ✅ Arquivos CORRIGIDOS (anteriormente ALERTA)

### src/pyloto_corp/infra/http.py

- **Status anterior:** 🚨 ALERTA
- **Status atual:** ✅ CORRIGIDO
- **Alterações realizadas:**
  - `_request_with_retry()`: **132 → ~46 linhas** (limite: 60)
  - Helpers extraídos para funções de módulo:
    - `_sanitize_url()`, `_is_retryable_status()`, `_calculate_backoff()`
    - `_log_request_start()`, `_log_request_success()`, `_log_non_retryable_error()`
    - `_log_transient_error()`, `_log_unexpected_error()`
    - `_handle_transient_exception()`, `_process_response()`, `_wait_backoff_if_needed()`
  - Separação clara de responsabilidades

### src/pyloto_corp/adapters/whatsapp/outbound.py

- **Status anterior:** 🚨 ALERTA
- **Status atual:** ✅ CORRIGIDO
- **Alterações realizadas:**
  - `_build_payload()` **removido** → delegado para `payload_builders/`
  - `_build_interactive_object()` **removido** → delegado para `payload_builders/`
  - Arquivo reduzido de **331 → ~186 linhas**
  - Novo package `payload_builders/` criado com builders por tipo
  - SRP restaurado: cliente apenas orquestra

### src/pyloto_corp/adapters/whatsapp/validators.py

- **Status anterior:** 🚨 ALERTA
- **Status atual:** ✅ CONVERTIDO PARA PACKAGE
- **Alterações realizadas:**
  - Arquivo convertido em package `validators/` com arquivos especializados:
    - `__init__.py` - Exports públicos, backward-compatible
    - `errors.py` - `ValidationError` exception
    - `limits.py` - Constantes de limite (MAX_TEXT_LENGTH, etc.)
    - `orchestrator.py` - `WhatsAppMessageValidator` (dispatch)
    - `text.py` - Validação de mensagens de texto
    - `media.py` - Validação de mídia (image, video, audio, document)
    - `interactive.py` - Validação de mensagens interativas
    - `template.py` - Validação de templates
  - Funções de validação com **≤40 linhas**
  - SRP restaurado por tipo de mensagem

---

## ⚠️ Arquivos com ATENÇÃO

### src/pyloto_corp/domain/whatsapp_message_types.py

- **Linhas:** 239
- **Regra violada:** Tamanho do arquivo (200-400 linhas = Bom/Atenção)
- **Evidência:** ~239 linhas, na faixa de atenção
- **Impacto:** Arquivo de modelos Pydantic, coeso para tipos de mensagem. Aceitável, mas monitorar crescimento.

### src/pyloto_corp/infra/secrets.py

- **Linhas:** 268
- **Regra violada:** Tamanho do arquivo (200-400 linhas)
- **Evidência:** ~268 linhas
- **Impacto:** Contém 2 providers distintos (Env e SecretManager). Coeso, mas pode crescer.

### src/pyloto_corp/adapters/whatsapp/normalizer.py

- **Linhas:** 287
- **Regra violada:** Tamanho do arquivo (200-400 linhas)
- **Evidência:** ~287 linhas, composto por funções de extração pequenas
- **Impacto:** Boa modularidade interna, aceitável.

### src/pyloto_corp/infra/firestore_conversations.py

- **Linhas:** 116
- **Regra violada:** Largura de linha
- **Evidência:** 5 linhas excedem 79 caracteres
- **Impacto:** Menor, mas viola PEP 8 conforme regras_e_padroes.md.

### src/pyloto_corp/application/export.py

- **Linhas:** 409
- **Regra violada:** Tamanho do arquivo (400-500 = Atenção)
- **Evidência:**
  - Arquivo com 409 linhas (limite de atenção)
  - Método `execute()` com **36 linhas de código** (≤50, OK)
  - Já refatorado com helpers: `_collect_export_data()`, `_render_export_text()`,
    `_persist_export_and_audit()`, `_compile_export_result()`
- **Impacto:** Classe bem estruturada, limite de funções respeitado.

### src/pyloto_corp/infra/dedupe.py

- **Linhas:** 352
- **Regra violada:** Tamanho do arquivo, função grande
- **Evidência:**
  - ~352 linhas
  - `create_dedupe_store()` com 51 linhas
- **Impacto:** Contém 2 implementações + factory. Aceitável para módulo de infraestrutura.

---

## 🚨 Arquivos com ALERTA

**Nenhum arquivo apresenta ALERTA.**

---

## ❌ Arquivos com VIOLAÇÃO CRÍTICA

**Nenhum arquivo apresenta VIOLAÇÃO CRÍTICA.**

---

## 📊 Resumo das Correções

| Módulo | Antes | Depois | Ação |
|--------|-------|--------|------|
| `http.py` `_request_with_retry()` | 132 linhas | ~46 linhas | Helpers extraídos |
| `outbound.py` | 331 linhas | ~186 linhas | Delegação para package |
| `validators.py` | 358 linhas monolítico | Package 8 arquivos | Separação por tipo |
| `export.py` `execute()` | 64 linhas (incl. docstring) | 36 linhas código | Já estava OK |

---

## 📋 Última Auditoria de Validação (24/01/2026)

### Arquivos Refatorados - Status Atual

| Arquivo | Linhas | Maior Função | Status |
|---------|--------|--------------|--------|
| `infra/http.py` | 376 | `_request_with_retry`: 45 linhas | ✅ OK |
| `adapters/whatsapp/outbound.py` | 186 | `send_message`: ~35 linhas | ✅ OK |
| `adapters/whatsapp/validators/` | 522 (8 arquivos) | Todas <40 linhas | ✅ OK |
| `adapters/whatsapp/payload_builders/` | 443 (7 arquivos) | Todas <50 linhas | ✅ OK |

### Arquivos em ATENÇÃO - Status Confirmado

| Arquivo | Linhas | Linhas >79 chars | Status |
|---------|--------|------------------|--------|
| `domain/whatsapp_message_types.py` | 239 | 1 | ⚠️ ATENÇÃO |
| `infra/secrets.py` | 268 | 2 | ⚠️ ATENÇÃO |
| `adapters/whatsapp/normalizer.py` | 287 | 3 | ⚠️ ATENÇÃO |
| `infra/firestore_conversations.py` | 116 | 5 | ⚠️ ATENÇÃO |
| `infra/dedupe.py` | 352 | 5 | ⚠️ ATENÇÃO |
| `application/export.py` | 409 | 5 | ⚠️ ATENÇÃO |

### Validação de Funcionamento

- **Testes:** 155 passando ✅
- **Ruff (src/ + tests/):** 0 erros ✅
- **Backward compatibility:** Mantida (mesmas assinaturas públicas)
