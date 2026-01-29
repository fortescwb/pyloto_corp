# TODO — WhatsApp: Inbound/Outbound + FSM + IA + Segurança (PII/LGPD) + Testes

## 0) Contexto e objetivo (1 intenção ativa)

Corrigir todos os achados do relatório de auditoria relacionados a:

* Recebimento (webhook), validação, normalização e dedupe
* Sessão e FSM (estado, transições, outcomes)
* Uso de IA (LLM#1 detecção, LLM#2 geração, LLM#3 seleção de tipo) na ordem correta
* Envio (payload builder, validação, outbound idempotência, retries)
* Segurança (PII/LGPD), observabilidade e testes

**Meta:** ficar “production-ready” em Cloud Run (stateless), com zero-trust, sem PII em logs e com testes verdes.

---

## 1) Bloqueadores de produção (CRÍTICO) — fazer primeiro

### 1.1 C4 — Consertar testes de outbound (7 falhas)

**Problema:** testes falham por `phone_number_id=None`, mocks incompletos e validação de envio inexistente de fato.
**Impacto:** não há garantia de regressão no envio; quebra confiança do pipeline outbound.

**Ações:**

* Ajustar fixtures/env de testes para sempre ter `WHATSAPP_PHONE_NUMBER_ID` fake válido (ex. `"1234567890"`).
* Corrigir mocks do cliente HTTP/Meta API para não construir URL com `None`.
* Garantir que os testes realmente exercitam:

  * build do payload por tipo
  * POST com headers corretos (sem token em logs)
  * interpretação de resposta `{message_id, error}`

**Critério de aceite:**

* `pytest` passa 100%.
* Testes de outbound validam que a URL nunca contém `None`.
* Snapshot/asserções não incluem PII/tokens.

---

### 1.2 C1 — Sanitização pós-LLM#2 (resposta gerada) antes de qualquer uso

**Problema:** LLM#2 pode produzir conteúdo com PII se o contexto/histórico tiver PII; a resposta segue para LLM#3 e outbound sem “pós-sanitização”.
**Impacto:** violação LGPD e vazamento de PII ao usuário final.

**Ações:**

* Implementar `sanitize_response_content(text: str) -> str` (centralizado, reutilizável) para mascarar ao menos:

  * CPF (com e sem pontuação)
  * CNPJ (com e sem pontuação)
  * e-mails
  * telefones BR (com variações)
  * chaves Pix comuns (e-mail/telefone/CPF/CNPJ) quando identificáveis
* Aplicar sanitização:

  1. imediatamente após `LLM#2` retornar `text_content`
  2. antes de enviar `generated_response` para `LLM#3`
  3. antes de construir payload final (defesa em profundidade)

**Testes obrigatórios:**

* Fixture com histórico contendo CPF/e-mail/telefone → LLM#2 mock devolve resposta ecoando PII → sanitização remove/mascara.
* Teste garantindo que logs não armazenam `text_content` bruto se contiver padrões PII.

**Critério de aceite:**

* Nenhuma resposta outbound contém CPF/e-mail/telefone em claro quando presente no histórico.
* Sanitização é determinística e coberta por testes.

---

### 1.3 C2 — Session store não pode ser Memory em produção (Cloud Run stateless)

**Problema:** session store em memória quebra em múltiplas instâncias.
**Impacto:** perda de estado/histórico, FSM inconsistente, respostas erradas.

**Ações:**

* Tornar `SESSION_STORE_BACKEND` obrigatório por ambiente (prod/staging).
* Default seguro:

  * `memory` apenas para dev/test local
  * `firestore` (ou `redis`) para staging/prod (conforme docs do repo)
* Validar startup: se `ENV in {staging,prod}` e backend `memory`, falhar rápido com erro claro (sem segredos).

**Testes obrigatórios:**

* Teste de settings: `ENV=prod` + `SESSION_STORE_BACKEND=memory` → erro/exception controlada no boot.

**Critério de aceite:**

* Em staging/prod, nunca inicia com `memory`.

---

### 1.4 C3 — Feature flag OPENAI_ENABLED: validação + fallback previsível

**Problema:** flag mal definida vira comportamento confuso; faltam testes cobrindo o fluxo fallback total.
**Impacto:** produção instável quando OpenAI indisponível / env quebrada.

**Ações:**

* Garantir parsing estrito de boolean (ex.: `"true/false"`, `"1/0"`).
* Default: `OPENAI_ENABLED=false` se ausente (fail-safe).
* Criar testes E2E-ish do pipeline com:

  * `OPENAI_ENABLED=false` → templates determinísticos
  * `OPENAI_ENABLED=true` e OpenAI timeout → fallback determinístico em cada LLM

**Critério de aceite:**

* Pipeline funciona com OpenAI desligada sem degradar contrato (outcome e tipo de msg coerentes).

---

## 2) Alto risco (ALTO) — após bloqueadores

### 2.1 A2 — Sanitizar histórico/contexto antes de enviar para LLM (LGPD)

**Problema:** `session_history` vai para LLM#1/LLM#2 sem máscara.
**Impacto:** PII sai do sistema para terceiros (OpenAI) e pode contaminar respostas.

**Decisão recomendada (do relatório):** Sanitização “mid-level” (antes de cada chamada LLM), centralizada.

**Ações:**

* Implementar `mask_pii_in_history(messages: list[str]) -> list[str]`.
* Aplicar em todos os pontos que montam contexto para IA:

  * LLM#1 (event detection)
  * LLM#2 (response generation)
  * LLM#3 (message type selection), se receber trechos livres
* Truncar histórico (ex.: últimas 5 mensagens ou conforme regra do repo), garantindo:

  * determinismo
  * limite de tokens
  * minimização de dados

**Testes obrigatórios:**

* `mask_pii_in_history()` cobre formatos reais (CPF com/sem pontuação, e-mail, telefone, etc.).
* Teste que garante que payload enviado ao OpenAI não contém PII (mock capturando input).

**Critério de aceite:**

* Nenhuma chamada LLM recebe PII em claro.

---

### 2.2 A3 — Validar outcome terminal antes de persistir sessão

**Problema:** sessão pode ser salva com `outcome=None`, violando contrato do repo.
**Impacto:** roteamento/handoff ambíguo; sessões “presas”.

**Ações:**

* Adicionar validação antes de `session_store.save()`:

  * se `outcome is None`: logar evento estruturado (sem PII) + setar outcome explícito de falha controlada (ex.: `FAILED_INTERNAL`) OU abortar persistência conforme regra do repo (seguir docs).
* Garantir que cada caminho do pipeline define outcome.

**Testes obrigatórios:**

* Teste: caminho que não define outcome → validação dispara.
* Teste: cada outcome terminal canônico é alcançável por ao menos 1 cenário.

**Critério de aceite:**

* 0 sessões persistidas com `outcome=None`.

---

### 2.3 A4 — Flood/rate-limit em ambiente distribuído (Redis)

**Problema:** detector em memória não funciona com múltiplas instâncias Cloud Run.
**Impacto:** abuso passa.

**Ações:**

* Implementar `RedisFloodDetector` com:

  * chave baseada em `session_id` (ou hash do telefone, se permitido) + janela (TTL 60s)
  * `INCR` + TTL
* Definir thresholds configuráveis via env.
* Logar somente IDs truncados/hashed.

**Testes obrigatórios:**

* Teste unit com fake redis (ou stub) validando contagem e TTL.
* Teste de integração (quando aplicável) com redis real em CI opcional.

**Critério de aceite:**

* Flood detectado de forma consistente em múltiplas instâncias.

---

### 2.4 A1 — Eliminar duplicação e risco em `infra/dedupe.py` (god module / imports ambíguos)

**Problema:** módulo grande e duplicado vs módulos novos.
**Impacto:** manutenção perigosa, imports inconsistentes.

**Ações:**

* Fazer inventário de imports: `from ...infra.dedupe import ...`
* Migrar tudo para o(s) módulo(s) canônicos (ex.: outbound_dedupe_*), mantendo compatibilidade interna.
* Remover/aposentar arquivo legado apenas quando não houver dependências.

**Critério de aceite:**

* 0 imports do módulo legado.
* Testes de dedupe continuam cobrindo cenários críticos.

---

## 3) Médio (MÉDIO) — quando acima estiver sólido

### 3.1 M2 — Correlation ID propagado fim-a-fim (inclui async)

**Ações:**

* Garantir que logs em funções async mantenham `correlation_id` via contexto (contextvars/structlog).
* Padronizar campos de log: `correlation_id`, `session_id_prefix`, `msg_id_prefix`, `component`, `elapsed_ms`.

**Aceite:**

* Um request gera logs correlacionáveis ponta-a-ponta.

---

### 3.2 M1 — normalizer.py acima do limite (288 linhas)

**Ações:**

* Só refatorar se continuar crescendo ou se violar regras do repo.
* Se refatorar: mover extractors para submódulos (`normalizers/text.py`, `media.py`, etc.) mantendo API.

**Aceite:**

* Sem regressões nos tipos suportados.

---

### 3.3 M3 — Ordenação/contratos do IntentQueue com testes

**Ações:**

* Criar testes de ordenação e limite de intenções.
* Validar regras de “1 intenção ativa” + “máx 3” conforme docs.

**Aceite:**

* Ordem e capacidade fixadas por testes.

---

## 4) Baixo (BAIXO) — observabilidade e UX de operação

### 4.1 L1 — Fallbacks em INFO (não DEBUG)

**Ações:**

* Subir nível de log quando fallback for usado (sem PII) com `fallback_used=true`.

### 4.2 L2 — Métricas de latência por componente

**Ações:**

* Instrumentar tempos (ms) para: dedupe, fsm, llm1/2/3, outbound, total.
* Reportar em log estruturado e/ou métricas (Cloud Monitoring).

---

## 5) Itens adicionais de segurança (não ignorar)

### 5.1 Assinatura: não aceitar “secret None → skipped válido”

**Ações:**

* Em staging/prod: assinatura é obrigatória (se secret ausente, rejeitar).
* Em dev/test: permitir skip, mas logar explicitamente.

**Aceite:**

* Produção nunca processa webhook sem assinatura validada.

### 5.2 Validar batch size para evitar DoS

**Ações:**

* Impor limite (ex.: 100 mensagens) antes de processar.
* Se exceder: responder 400/413 com log seguro.

---

## 6) Ordem do pipeline (garantia por teste)

Mesmo que “pareça correto”, travar por teste:

**Ações:**

* Criar teste que prova a ordem:

  1. FSM define estado/contexto
  2. LLM#1 detecta evento/intenção (ou fallback)
  3. LLM#2 gera resposta (ou fallback)
  4. LLM#3 escolhe tipo com base na resposta gerada
  5. builder monta payload e valida

**Aceite:**

* Teste falha se alguém inverter ordem.

---

## 7) Gates obrigatórios

Rodar (e registrar output):

* `ruff`
* `pytest`
* `pytest-cov` (meta sugerida: ≥95% após correções críticas)

---

## 8) Checklist de entrega (para cada PR)

* [ ] Mudança mínima que resolve o item
* [ ] Testes novos cobrindo risco
* [ ] Logs sem PII (inclui histórico e respostas LLM)
* [ ] Sem secrets hardcoded
* [ ] Cloud Run stateless respeitado
* [ ] Outcome terminal sempre definido

---

### Referências normativas

* System Instructions Global — EXECUTOR
* System Instructions Global — GUARDIÃO
* System Instructions Global — AUDITOR
* Agente do repositório `pyloto_corp`

---
