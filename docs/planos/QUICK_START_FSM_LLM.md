# ⚡ Quick Start — FSM + LLM para pyloto_corp

**Documento:** Guia de 15 minutos para entender a arquitetura  
**Para:** Desenvolvedores, product managers, arquitetos  
**Status:** 📋 Pronto para Implementação

---

## O Que Será Construído?

**Antes:**
```
INPUT: Usuário manda "Olá"
  ↓
[sem FSM, sem LLM]
  ↓
OUTPUT: Resposta fixa de texto
```

**Depois:**
```
INPUT: Usuário manda "Olá"
  ↓
[LLM 1: Qual é o evento?] → "start_order"
  ↓
[FSM: current_state=INITIAL + event=USER_SENT_TEXT]
  ↓
[LLM 2: Qual é a resposta?] → "Qual serviço?"
  ↓
[LLM 3: Qual tipo de mensagem?] → InteractiveListMessage com opções
  ↓
OUTPUT: Mensagem inteligente, formatada dinamicamente
```

---

## 3 Pontos de LLM Explicados Rapidamente

### Ponto 1: Event Detection
**O que faz:** Converte input do usuário em evento do FSM  
**Entrada:** "Oi, quero fazer um pedido"  
**LLM Responde:** `{event: "USER_SENT_TEXT", intent: "start_order", confidence: 0.95}`  
**Usa FSM para:** Saber próximo estado

### Ponto 2: Response Generation
**O que faz:** Gera resposta contextualizada  
**Entrada:** Evento + histórico + perfil do usuário  
**LLM Responde:** `{text_content: "Qual tipo de serviço?", suggested_next_state: "COLLECTING_INFO"}`  
**Usa FSM para:** Validar próximo estado

### Ponto 3: Message Type Selection ⭐ **[NOVO]**
**O que faz:** Escolhe melhor tipo de mensagem  
**Entrada:** Resposta gerada + contexto  
**Exemplos:**
- "Você é cliente?" → `InteractiveButtonMessage` (2 botões: Sim/Não)
- "Qual serviço?" com 5 opções → `InteractiveListMessage` (lista)
- "Visite nosso site" → `InteractiveCTAURLMessage` (link)
- Simples → `TextMessage`

**LLM Responde:**
```json
{
  "message_type": "InteractiveButtonMessage",
  "parameters": {
    "body": "Você é cliente Pyloto?",
    "buttons": [
      {"id": "yes", "title": "Sou cliente"},
      {"id": "no", "title": "Primeira vez"}
    ]
  },
  "confidence": 0.92
}
```

---

## Estados FSM (10 Estados)

```
INITIAL (início)
  ↓
TRIAGE (classificar intenção)
  ↓
COLLECTING_INFO (coletar dados)
  ↓
GENERATING_RESPONSE (preparar resposta)
  ↓
HANDOFF_HUMAN      ← Terminal (encerramento)
SELF_SERVE_INFO    ← Terminal
ROUTE_EXTERNAL     ← Terminal
SCHEDULED_FOLLOWUP ← Terminal

+ ERROR, TIMEOUT (exceções)
```

---

## Estrutura de Pastas (O Que Criar)

```
src/pyloto_corp/
├── domain/session/              ← NOVO (FSM core)
│   ├── states.py               # Estados enum
│   ├── events.py               # Eventos enum
│   └── transitions.py          # Tabela de transições
│
├── application/
│   ├── fsm_engine.py           # ← NOVO: Dispatcher puro
│   ├── message_sender.py       # Modificado
│   └── webhook_handler.py      # Modificado
│
├── ai/                          ← NOVO (3 LLMs)
│   ├── orchestrator.py         # Coordena tudo
│   ├── assistant_event_detector.py       # Ponto 1
│   ├── assistant_response_generator.py   # Ponto 2
│   ├── assistant_message_type.py         # Ponto 3 ⭐
│   ├── config/
│   │   └── prompts.yaml        # Prompts versionados
│   └── contracts/
│       ├── event_detection.py
│       ├── response_generation.py
│       └── message_type_selection.py
│
└── infra/
    └── storage.py              # Salva estado
```

---

## Exemplo Real: Fluxo Completo

**Turno 1:**
```
USER → WhatsApp: "Olá, preciso fazer um pedido"

[FSM Engine]
  current_state: INITIAL
  event: USER_SENT_TEXT
  → next_state: TRIAGE
  
[LLM 1: Event Detection]
  Detects: intent = "start_order"
  
[LLM 2: Response Generation]
  Generates: "Qual tipo de serviço?"
  
[LLM 3: Message Type Selection]
  Selects: InteractiveListMessage
  With sections:
    • Delivery
    • Serviço no Local
    • Consultoria
  
PYLOTO → WhatsApp: (Mensagem com 3 botões)
```

**Turno 2:**
```
USER → WhatsApp: (Clica em "Delivery")

[LLM 1: Event Detection]
  Detects: event = "USER_SELECTED_LIST_ITEM"
  
[FSM: State transition]
  COLLECTING_INFO → GENERATING_RESPONSE
  
[LLM 2: Response Generation]
  Generates: "Qual seu endereço?"
  
[LLM 3: Message Type Selection]
  Selects: TextMessage (ou LocationMessage)
  
PYLOTO → WhatsApp: (Pergunta endereço)
```

---

## Por Que Funciona?

| Aspecto | Vantagem |
|---------|----------|
| **FSM Explícito** | Sem "mágica", tudo auditável |
| **LLM Modular** | Cada responsabilidade isolada |
| **Seleção Dinâmica** | UX adapta ao contexto |
| **Prompts Versionados** | Iteração sem quebrar produção |
| **Determinístico** | Transições previsíveis |

---

## Roadmap (6 Semanas)

| Semana | Fase | O Que Fazer |
|--------|------|-----------|
| 1-2 | **FSM Core** | Criar states.py, events.py, transitions.py, fsm_engine.py |
| 2-3 | **LLM 1** | Event detector funcional |
| 3-4 | **LLM 2** | Response generator funcional |
| 4-5 | **LLM 3** | Message type selector ⭐ |
| 5-6 | **Integração** | Juntar tudo, E2E testing |
| 6-7 | **Otimização** | Monitoring, v2 de prompts |

---

## Documento Completo

👉 **Leia:** `FSM_LLM_ARCHITECTURE_PYLOTO_CORP.md` (36KB, 1253 linhas)

Contém:
- ✅ Análise comparativa pyloto_lab ↔ pyloto_corp
- ✅ Implementação passo-a-passo de cada arquivo
- ✅ Prompts versionados completos
- ✅ 3 exemplos práticos
- ✅ Testes unitários
- ✅ Roadmap detalhado

---

**Preparado Por:** GitHub Copilot  
**Data:** 26 de janeiro de 2025  
**Status:** ✅ Pronto para Implementação  

