# 📦 Índice de Deliverables — FSM + LLM Architecture

**Data:** 26 de janeiro de 2025  
**Repositório:** pyloto_corp  
**Status:** ✅ Completo — Pronto para Implementação  

---

## 📋 Arquivos Entregues

### 1️⃣ Documento Principal (36KB, 1253 linhas)

**Arquivo:** `FSM_LLM_ARCHITECTURE_PYLOTO_CORP.md`

**Conteúdo:**
- ✅ Análise comparativa (pyloto_lab vs pyloto_corp)
- ✅ Padrão FSM explicado
- ✅ Estrutura proposta com 10 estados
- ✅ **3 Pontos de LLM:**
  1. Event Detection (qual evento disparou?)
  2. Response Generation (qual resposta gerar?)
  3. **Message Type Selection** ⭐ (qual tipo de mensagem?)
- ✅ Matriz de decisão para seleção de tipo
- ✅ 3 exemplos práticos completos
- ✅ Arquivo de configuração versionado (prompts.yaml)
- ✅ Roadmap de 6 semanas
- ✅ Estratégia de testes (unit + E2E)

**Para Quem:** Arquitetos, tech leads, desenvolvedores  
**Tempo de Leitura:** 45-60 minutos  
**Uso:** Guia de implementação técnica

---

### 2️⃣ Quick Start (3KB, 120 linhas)

**Arquivo:** `QUICK_START_FSM_LLM.md`

**Conteúdo:**
- ✅ Visão geral antes/depois
- ✅ Explicação dos 3 pontos de LLM (5 min)
- ✅ Estados FSM (visual)
- ✅ Estrutura de pastas resumida
- ✅ Exemplo real de 2 turnos
- ✅ Roadmap simplificado (6 linhas)

**Para Quem:** Product managers, stakeholders, quem quer entender rápido  
**Tempo de Leitura:** 10-15 minutos  
**Uso:** Onboarding rápido da arquitetura

---

## 🏗️ Estrutura da Solução

### Estados (domain/session/states.py)

```python
class SessionState(Enum):
    INITIAL                    # Entrada
    TRIAGE                     # Classificação
    COLLECTING_INFO            # Coleta de dados
    GENERATING_RESPONSE        # Preparação
    
    HANDOFF_HUMAN              # Terminal: escalar para humano
    SELF_SERVE_INFO            # Terminal: informação pronta
    ROUTE_EXTERNAL             # Terminal: rota externa
    SCHEDULED_FOLLOWUP         # Terminal: followup agendado
    
    ERROR, TIMEOUT             # Exceções
```

### Eventos (domain/session/events.py)

```python
class SessionEvent(Enum):
    USER_SENT_TEXT
    USER_SELECTED_BUTTON
    USER_SELECTED_LIST_ITEM
    
    RESPONSE_GENERATED
    MESSAGE_SENT
    
    HUMAN_HANDOFF_READY
    SELF_SERVE_COMPLETE
    EXTERNAL_ROUTE_READY
    FOLLOWUP_SCHEDULED
```

### Transições (domain/session/transitions.py)

```python
TRANSITIONS = {
    SessionState.INITIAL: {
        SessionEvent.USER_SENT_TEXT: SessionState.TRIAGE,
    },
    SessionState.TRIAGE: {
        SessionEvent.RESPONSE_GENERATED: SessionState.COLLECTING_INFO,
    },
    # ... mais 20+ transições
}
```

---

## 🤖 Os 3 Pontos de LLM

### Ponto 1: Event Detection
**Arquivo:** `ai/assistant_event_detector.py`  
**Entrada:** Texto do usuário + contexto  
**Saída:** `{event, detected_intent, confidence}`  
**Modelo:** gpt-4-turbo, temp=0.3  

**Exemplo:**
```
Input:  "Oi, quero fazer um pedido"
Output: {
  event: "USER_SENT_TEXT",
  detected_intent: "start_order",
  confidence: 0.95
}
```

---

### Ponto 2: Response Generation
**Arquivo:** `ai/assistant_response_generator.py`  
**Entrada:** Evento + histórico + contexto  
**Saída:** `{text_content, suggested_next_state, requires_human_review}`  
**Modelo:** gpt-4-turbo, temp=0.7  

**Exemplo:**
```
Input:  {event: "USER_SENT_TEXT", intent: "start_order"}
Output: {
  text_content: "Qual tipo de serviço você procura?",
  suggested_next_state: "COLLECTING_INFO"
}
```

---

### Ponto 3: Message Type Selection ⭐ **[NOVO]**
**Arquivo:** `ai/assistant_message_type.py`  
**Entrada:** Resposta + contexto + opções (se houver)  
**Saída:** `{message_type, parameters, confidence, rationale}`  
**Modelo:** gpt-4-turbo, temp=0.5  

**Exemplos:**

| Resposta | Tipo Selecionado | Por Quê |
|----------|------------------|--------|
| "Você é cliente?" | `InteractiveButtonMessage` | 2 botões (Sim/Não) |
| "Qual serviço de 5 opções?" | `InteractiveListMessage` | Lista com seções |
| "Visite nosso site" | `InteractiveCTAURLMessage` | URL + botão |
| "Olá, bem-vindo!" | `TextMessage` | Apenas texto |

**Output para Sim/Não:**
```json
{
  "message_type": "InteractiveButtonMessage",
  "parameters": {
    "body": "Você é cliente Pyloto?",
    "buttons": [
      {"id": "yes", "title": "Sou cliente"},
      {"id": "no", "title": "Primeira vez"}
    ],
    "footer": "Escolha uma opção"
  },
  "confidence": 0.92,
  "rationale": "Pergunta binária → 2 botões melhor UX"
}
```

---

## 📂 Estrutura de Pastas (O Que Criar)

```
src/pyloto_corp/

domain/session/                        ← NOVO (FSM)
├── __init__.py
├── states.py                          # 10 estados
├── events.py                          # 10+ eventos
└── transitions.py                     # Tabela de transições

application/
├── fsm_engine.py                      ← NOVO (dispatcher)
├── message_sender.py                  # MODIFICAR (integrar tipo)
├── webhook_handler.py                 # MODIFICAR (extrair evento)
└── orchestrator_whatsapp.py

ai/                                    ← NOVO (3 LLMs)
├── __init__.py
├── orchestrator.py                    # Coordena tudo
├── assistant_event_detector.py        # Ponto 1
├── assistant_response_generator.py    # Ponto 2
├── assistant_message_type.py          # Ponto 3 ⭐
├── config/
│   ├── __init__.py
│   └── prompts.yaml                  # Prompts versionados
└── contracts/
    ├── __init__.py
    ├── event_detection.py
    ├── response_generation.py
    └── message_type_selection.py

infra/
├── storage.py                         # MODIFICAR (salva estado)
└── meta_client.py
```

---

## 🚀 Roadmap (6 Semanas)

| Semana | Fase | Arquivos a Criar | Status |
|--------|------|------------------|--------|
| 1-2 | **FSM Core** | states.py, events.py, transitions.py, fsm_engine.py | 📋 Especificado |
| 2-3 | **LLM 1** | assistant_event_detector.py + contracts | 📋 Especificado |
| 3-4 | **LLM 2** | assistant_response_generator.py + contracts | 📋 Especificado |
| 4-5 | **LLM 3** | assistant_message_type.py + contracts | 📋 Especificado ⭐ |
| 5-6 | **Integração** | orchestrator.py + atualizar handlers | 📋 Especificado |
| 6-7 | **Otimização** | Monitoring + v2 de prompts | 📋 Especificado |

---

## ✅ Validação e Testes

### Testes Unitários (Exemplo FSM)

```python
def test_state_transition_initial_to_triage():
    result = dispatch(
        current_state=SessionState.INITIAL,
        event=SessionEvent.USER_SENT_TEXT,
        payload={"user_input": "Olá"}
    )
    assert result["next_state"] == SessionState.TRIAGE
    assert "DETECT_EVENT" in result["actions"]
```

### Testes Unitários (LLM 3 - Message Type)

```python
async def test_message_type_boolean_question():
    result, message = await select_message_type(
        response_content="Você é cliente Pyloto?",
        context={"question_type": "boolean"},
        llm_client=mock_llm
    )
    assert result.message_type == "InteractiveButtonMessage"
    assert len(message.buttons) == 2
```

### Testes E2E (Fluxo Completo)

```python
async def test_full_flow_new_client():
    # Turno 1: Entrada
    result_1 = await session_turn("Olá", session_id="123")
    assert result_1.message_type == "InteractiveListMessage"
    
    # Turno 2: Seleção
    result_2 = await session_turn("Delivery", session_id="123")
    assert result_2.state == SessionState.COLLECTING_INFO
    
    # Turno N: Terminal
    # ... convergir para TERMINAL_STATE
```

---

## 📊 Métricas de Sucesso

| Métrica | Baseline | Target | Medição |
|---------|----------|--------|---------|
| **Confiança de Eventos** | N/A | >= 0.90 | % de eventos com confidence >= threshold |
| **Tipo Correto** | N/A | >= 0.85 | % mensagens com type apropriado |
| **Latência E2E** | N/A | < 2s | Tempo webhook → resposta |
| **Taxa de Fallback** | N/A | < 5% | % vezes que fallback para TextMessage |
| **Cobertura de Testes** | N/A | >= 90% | % linhas testadas (unit + integration) |

---

## 🔗 Como Começar?

### Passo 1: Leitura (15-60 min)
- **Rápido:** QUICK_START_FSM_LLM.md (15 min)
- **Completo:** FSM_LLM_ARCHITECTURE_PYLOTO_CORP.md (45-60 min)

### Passo 2: Aprovação
- Code review com arquiteto/tech lead
- Validar design contra regras de código (regras_e_padroes.md)
- Confirmar roadmap

### Passo 3: Prototipagem (Semana 1-2)
- Criar domain/session/states.py
- Criar domain/session/events.py
- Criar domain/session/transitions.py
- Criar application/fsm_engine.py
- Testes unitários

### Passo 4: Implementação LLM
- Semana 2-3: LLM 1 (Event Detection)
- Semana 3-4: LLM 2 (Response Generation)
- Semana 4-5: LLM 3 (Message Type Selection)

### Passo 5: Integração
- Semana 5-6: Juntar tudo
- Semana 6-7: Monitoramento + otimização

---

## 🎯 Próximos Passos Imediatos

1. **Validar design** com arquitetura (30 min)
2. **Ler QUICK_START** (15 min)
3. **Ler documento completo** (60 min)
4. **Criar branch** para prototipar Fase 1
5. **Iniciar domain/session/** (estados + eventos)

---

## 📞 Referências

**Dentro do repo:**
- `Funcionamento.md` — Outcomes de negócio
- `regras_e_padroes.md` — Padrões de código obrigatórios
- `src/pyloto_corp/domain/whatsapp_message_types.py` — 12 tipos de mensagem

**Análise de pyloto_lab:**
- `../pyloto_lab/pyloto/modules/fsm/engine.py` — Dispatcher puro (referência)
- `../pyloto_lab/pyloto/modules/fsm/pedido/states.py` — Estados (referência)

---

**Documento Consolidado**  
**Status:** ✅ Pronto para Implementação  
**Preparado Por:** GitHub Copilot (Executor Mode)  
**Data:** 26 de janeiro de 2025

