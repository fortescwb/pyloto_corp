## 1) Armazenar informações coletadas (quando não é entrega/serviço)

Sim, armazene. E não “só pode” — você **precisa** se quiser ter CRM, handoff humano decente e métrica de funil.

### Melhor caminho (prático + alinhado com seu stack atual)

**Firestore como fonte principal** (porque você já está nele com sessão/auditoria) + **estrutura explícita de “Lead/Atendimento”** separada de SessionState.

* **SessionState**: é estado operacional (curto prazo, mutable, TTL).
* **Lead/Case (Atendimento)**: é histórico/negócio (longo prazo, consultável por UI, relatórios).

Você não quer misturar “estado de conversa” com “registro comercial”.

### Modelo de dados recomendado

**collections:**

* `sessions/{session_id}` → estado atual, TTL e pointers
* `messages/{session_id}/{message_id}` → log append-only (inbound/outbound)
* `leads/{lead_id}` → o “cadastro comercial” consolidado
* `lead_events/{lead_id}/{event_id}` → mudanças e eventos (auditável)
* `decision_audit/{session_id}/{event_id}` → você já tem (mantenha)

**lead mínimo:**

* `lead_id` (UUID)
* `from_hash` (hash do telefone com salt do projeto, para indexar sem PII exposta)
* `from_e164_encrypted` (opcional; se precisar do número, armazene **criptografado**; não em texto puro)
* `status`: `OPEN | QUALIFYING | READY_FOR_HUMAN | IN_HUMAN | CLOSED`
* `service_interest`: enum (`CUSTOM_SOFTWARE`, `SAAS_ADAPTABLE`, `TRAFFIC_PROFILE`, etc.)
* `collected`: objeto com campos normalizados (ex.: `company_name`, `city`, `budget_range`, `deadline`, `pain_points`)
* `confidence_fields`: mapa de confiança por campo (0–1)
* `last_session_id`, `last_activity_at`
* `handoff_reason`, `priority`

**Regra objetiva de persistência**

* Tudo que for “campo de negócio” vai para `leads.collected` **somente se**:

  * veio do usuário diretamente **ou**
  * veio da LLM, mas marcado como `inferred=true` + `confidence>=threshold` (ex.: 0.8) **e** com trilha de auditoria em `lead_events`.

Se você gravar inferências fracas como verdade, sua UI vira um lixo.

### Firestore ou Postgres?

* **Firestore**: melhor agora (velocidade de implementação, streaming fácil pra UI, já está no teu core).
* **Postgres**: só vale migrar quando você precisar de **BI pesado**, joins complexos, relatórios financeiros/comerciais avançados. Até lá, Firestore segura.

> Decisão: **comece com Firestore**, mas projete o modelo como “event + snapshot” para migrar depois sem dor.

---

## 2) Flood/Spam: enviar mensagem de encerramento + cooldown

Sim. Mas com duas condições:

1. **Não responda** a floods massivos (vira amplificador de spam).
2. Responda **no primeiro gatilho** (ou quando cruzar limiar) com uma mensagem curta + cooldown.

### Comportamento recomendado

* Se `flood_score` cruzou limiar:

  * marque sessão como `DUPLICATE_OR_SPAM`
  * grave `cooldown_until = now + X minutes` num store rápido (Redis/Firestore)
  * **envie 1 mensagem** de aviso se ainda não enviou para aquele usuário no cooldown atual.

### Texto sugerido (neutro, sem “brigar”)

> “Detectei muitas mensagens em sequência e pausei este atendimento por segurança. Aguarde **X minutos** e envie uma nova mensagem para continuar.”

### Regras de cooldown

* flood leve: 5 min
* flood médio: 15 min
* flood pesado / padrão spam: 60 min
* reincidência em 24h: dobra cooldown (com teto, ex.: 6h)

E crie um estado explícito: `COOLDOWN_ACTIVE`. Isso evita a sessão ficar “encerrada” mas reabrindo sem controle.

---

## 3) Preparar interface gráfica (painel humano + controles)

Você descreveu um **Contact Center mínimo**. A LLM vira “operador automático”, e o humano precisa ter **controle soberano**.

### O que você precisa implementar no core para viabilizar a UI

A UI não “lê SessionState e pronto”. Você precisa de um **log de mensagens e eventos** (append-only) com streaming.

#### A) Message Log (obrigatório)

Gravar cada inbound/outbound como documento imutável:

`messages/{session_id}/{seq_or_message_id}`

* `direction`: `IN | OUT`
* `channel`: `WHATSAPP`
* `type`: `text | interactive | reaction | ...`
* `body_sanitized` (para UI; sem anexar PII bruto)
* `raw_pointer` (opcional, se quiser guardar raw criptografado)
* `created_at`
* `correlation_id`
* `actor`: `USER | LLM | HUMAN | SYSTEM`

#### B) Conversation Control Flags (obrigatório)

Um documento por sessão/lead controlado por humano:

`session_controls/{session_id}`

* `mode`: `LLM_ACTIVE | HUMAN_TAKEOVER | PAUSED_GLOBAL | PAUSED_SESSION`
* `human_assignee`: user_id
* `reason`
* `updated_at`
* `version` (para CAS / concorrência)

**Regra de ouro:** pipeline só responde se `mode == LLM_ACTIVE`.

#### C) Comandos (eventos)

A UI não “muda sessão”, ela dispara **comandos**:

`commands/{command_id}`

* `type`: `TAKEOVER | RELEASE | CLOSE | MARK_READY_FOR_HUMAN | PAUSE_ALL | RESUME_ALL`
* `target_session_id`
* `requested_by`
* `requested_at`
* `status`: `PENDING | APPLIED | REJECTED`
* `result`

O worker aplica o comando e escreve `command_events`/audit. Isso te dá rastreabilidade e evita gambiarra.

---

## 4) Semântica das ações que você pediu (definições objetivas)

### “Assumir conversa” (takeover)

* set `session_controls.mode = HUMAN_TAKEOVER`
* pipeline **não chama LLM** e **não envia outbound automático**
* UI passa a permitir enviar mensagens como HUMANO (outbound manual)
* loga evento: takeover + usuário responsável

### “Aceitar atendimento” (handoff)

Isso é diferente de takeover:

* set `lead.status = READY_FOR_HUMAN`
* opcional: mantém LLM ativa, mas sem “conversar demais”, só coleta último dado
* quando humano pegar: vira takeover

### “Encerrar definitivamente”

* set `lead.status = CLOSED`
* set `session.outcome = SELF_SERVE_INFO` (ou outro)
* set `cooldown_until` opcional (ex.: 24h) se quiser evitar reabertura imediata
* cria nota de fechamento (motivo)

### “Parar completamente a resposta da LLM” (kill switch global)

* `system_controls/global.mode = PAUSED_GLOBAL`
* pipeline checa antes de qualquer LLM/outbound
* necessário para incidentes (prompt injection, bug, custo explodindo)

E sim: você precisa também do `RESUME_ALL`.

---

## 5) Prioridade real (ordem de implementação)

1. **Persistir Lead/Case separado da sessão** (senão você não tem “CRM” nem handoff).
2. **Message Log append-only** (sem isso sua UI é cega).
3. **Session Controls + Kill switch** (sem isso você não controla o bot).
4. **Flood/spam com cooldown + mensagem única**.
5. UI: lista de sessões/leads, detalhe do chat, botões de comando.
6. Métricas: tempo de resposta, taxa de handoff, intents, falhas, spam.

---

## 6) Armadilhas que você deve evitar (porque vão te custar caro)

* **Salvar inferência como fato** sem “inferred/confidence/source”.
* **Guardar telefone em claro** espalhado em logs/docs. Se a UI precisa mostrar, mostre para operadores autorizados e guarde criptografado.
* **Misturar session state com CRM**: você vai quebrar histórico, auditoria e relatórios.
* **Implementar takeover “no susto” sem controle transacional**: vai mandar mensagem duplicada ou a LLM vai responder junto do humano.

---

Se você quiser, eu te devolvo uma proposta de “contratos” (Pydantic/dataclasses) para:

* `Lead`
* `LeadCollectedField`
* `SessionControl`
* `MessageLogEntry`
* `Command`

E as regras exatas no pipeline: **onde checar kill switch, onde checar takeover, e como garantir que NUNCA sai outbound automático quando humano assumiu**.
