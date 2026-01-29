# 🏗️ Arquitetura FSM + LLM Inteligente para pyloto_corp

**Objetivo:** Implementar sistema de estados (FSM) similar a `pyloto_lab`, com seleção inteligente de tipos de mensagens via LLM  
**Data:** 26 de janeiro de 2025  
**Status:** 📋 Documento de Design e Implementação  
**Escopo:** pyloto_corp (serviço de atendimento inicial WhatsApp)

---

## 📑 Índice

1. [Análise Comparativa](#1-análise-comparativa)
2. [Padrão FSM em pyloto_lab](#2-padrão-fsm-em-pyloto_lab)
3. [Estrutura Proposta para pyloto_corp](#3-estrutura-proposta-para-pyloto_corp)
4. [Uso de LLM — 3 Pontos Críticos](#4-uso-de-llm--3-pontos-críticos)
5. [Seleção Inteligente de Tipo de Mensagem](#5-seleção-inteligente-de-tipo-de-mensagem)
6. [Exemplos Práticos](#6-exemplos-práticos)
7. [Roadmap de Implementação](#7-roadmap-de-implementação)

---

## 1. Análise Comparativa

### 1.1 pyloto_lab — Estado Atual

**Força:** Arquitetura FSM bem definida e modular

```
pyloto_lab/modules/fsm/
├── engine.py                 # Dispatcher puro (sem side effects)
├── pedido/
│   ├── states.py            # Enum de estados (DRAFT → COMPLETED)
│   ├── events.py            # Enum de eventos
│   ├── transitions.py       # Tabela de transições (state + event → next_state)
│   └── validators.py        # Validadores de campo/contexto
├── subfsm/                  # Sub-máquinas (sub-fluxos)
│   ├── collecting_data.py
│   ├── pricing.py
│   ├── payment.py
│   └── dispatching.py
└── contracts/               # Schemas Pydantic
    ├── context_schema.py
    └── event_schema.py
```

**Características:**
- ✅ Estados: 11 estados canonicais (DRAFT, COLLECTING_DATA, PRICING, etc.)
- ✅ Transições: Tabela explícita (state + event → next_state)
- ✅ Validadores: Schema validation antes de transição
- ✅ Ações: Mapping (event → [actions])
- ✅ Dispatcher puro: Sem side effects, 100% determinístico

**Fraquezas:**
- ❌ Sem LLM para ajuda contextual
- ❌ Respostas hardcoded por assistente
- ❌ Sem seleção automática de tipo de mensagem
- ❌ Sem adaptação dinâmica a contexto novo

---

### 1.2 pyloto_corp — Estado Atual

**Força:** Tipos de mensagens completos e testados

```
pyloto_corp/
├── src/pyloto_corp/
│   ├── domain/
│   │   ├── whatsapp_message_types.py  # 16 tipos (TEXT, VIDEO, etc.)
│   │   ├── constants.py
│   │   └── models.py
│   ├── application/
│   │   ├── message_sender.py          # Envio de mensagens
│   │   └── webhook_handler.py         # Recebimento
│   ├── ai/
│   │   ├── orquestrador.py
│   │   └── prompts/
│   └── infra/
│       └── meta_client.py
├── Funcionamento.md                   # Outcomes canônicos
└── regras_e_padroes.md               # 7 seções de padrões
```

**Características:**
- ✅ Tipos de mensagens: 12 tipos validados (TEXT, IMAGE, VIDEO, INTERACTIVE_BUTTONS, etc.)
- ✅ Outcomes canônicos: HANDOFF_HUMAN, SELF_SERVE_INFO, ROUTE_EXTERNAL, SCHEDULED_FOLLOWUP
- ✅ Regras de código: Rigorosas e bem documentadas
- ✅ Testes: Abrangentes para cada tipo

**Fraquezas:**
- ❌ Sem FSM explícito
- ❌ Sem estados canônicos
- ❌ Sem tabela de transições
- ❌ Sem coordenação entre turnos de conversa
- ❌ Respostas geradas ad-hoc (sem estrutura)

---

### 1.3 Oportunidade: Combinar Padrões

| Aspecto | pyloto_lab | pyloto_corp | Proposta |
|---------|-----------|-----------|----------|
| **FSM Explícito** | ✅ Completo | ❌ Ausente | Adaptar states + transitions |
| **Tipos de Mensagem** | ❌ Genérico | ✅ 12 tipos | Manter + usar inteligentemente |
| **LLM** | ⚠️ Aux. básico | ⚠️ Ad-hoc | **Novo: 3 pontos críticos** |
| **Seleção de Tipo** | ❌ Não | ❌ Não | **Novo: Dinâmica via LLM** |

---

## 2. Padrão FSM em pyloto_lab

### 2.1 Estrutura Core

**engine.py:** Dispatcher puro
```python
def dispatch(
    current_state: PedidoState | str,
    event: PedidoEvent | str,
    payload: dict | None = None,
    context: FSMContext | None = None,
) -> dict[str, Any]:
    """
    Entrada: Estado atual, evento, payload, contexto
    Saída: {next_state, actions, errors}
    Sem side effects.
    """
```

**pedido/transitions.py:** Tabela de transições
```python
TRANSITIONS = {
    PedidoState.DRAFT: {
        PedidoEvent.START_ORDER_DELIVERY: PedidoState.COLLECTING_DATA,
        PedidoEvent.START_ORDER_SERVICE: PedidoState.COLLECTING_DATA,
    },
    PedidoState.COLLECTING_DATA: {
        PedidoEvent.DATA_COLLECTED: PedidoState.PRICING,
    },
    # ... mais transições
}
```

**pedido/events.py:** Catálogo de eventos
```python
class PedidoEvent(str, Enum):
    START_ORDER_DELIVERY = "START_ORDER_DELIVERY"
    START_ORDER_SERVICE = "START_ORDER_SERVICE"
    DATA_COLLECTED = "DATA_COLLECTED"
    REQUEST_PRICING = "REQUEST_PRICING"
    CONFIRM_ORDER = "CONFIRM_ORDER"
    PAYMENT_CONFIRMED = "PAYMENT_CONFIRMED"
    # ...
```

### 2.2 Fluxo de Decisão

```
user_input
  ↓
[webhook handler]
  ↓
[extract intent] ← LLM: "Qual evento disparou?"
  ↓
[load context] ← Redis/Firestore
  ↓
[dispatch(current_state, event, payload, context)]
  ↓
[validate] ← Schema + business rules
  ↓
{next_state, actions, errors}
  ↓
[execute actions] ← Enviar mensagem, etc.
  ↓
[save new_state] ← Redis/Firestore
  ↓
[send response] ← Mensagem ao usuário
```

### 2.3 Vantagens da Abordagem

- ✅ **Determinístico:** Transições explícitas, sem "mágica"
- ✅ **Testável:** Cada transição pode ser unitariamente testada
- ✅ **Auditável:** Log de eventos = histórico completo
- ✅ **Escalável:** Fácil adicionar novos estados/eventos
- ✅ **Modular:** Cada responsabilidade em seu arquivo

---

## 3. Estrutura Proposta para pyloto_corp

### 3.1 Hierarquia de Pastas

```
src/pyloto_corp/
├── domain/
│   ├── whatsapp_message_types.py       # [MANTER] 12 tipos validados
│   ├── session/                        # [NOVO]
│   │   ├── states.py                   # Estados de conversa
│   │   ├── events.py                   # Eventos possíveis
│   │   └── transitions.py              # Tabela de transições
│   ├── constants.py
│   ├── errors.py
│   └── models.py
│
├── application/
│   ├── fsm_engine.py                   # [NOVO] Dispatcher (similar engine.py)
│   ├── message_sender.py               # [MODIFICAR] Integrar tipo de mensagem
│   └── webhook_handler.py              # [MODIFICAR] Extrair evento
│
├── ai/                                 # [NOVO] IA para 3 pontos
│   ├── orchestrator.py                 # Coordena chamadas de LLM
│   ├── assistant_event_detector.py     # Ponto 1: Qual evento?
│   ├── assistant_response_generator.py # Ponto 2: Qual resposta?
│   ├── assistant_message_type.py       # Ponto 3: Qual tipo de mensagem?
│   ├── config/
│   │   ├── prompts.yaml               # Prompts versionados
│   │   └── assistants.yaml            # Config de assistentes
│   └── contracts/
│       ├── event_detection.py
│       ├── response_generation.py
│       └── message_type_selection.py
│
└── infra/
    ├── meta_client.py
    └── storage.py                      # [MODIFICAR] Salvar estado
```

### 3.2 Estados de Conversa (Session States)

**domain/session/states.py**

```python
from enum import Enum

class SessionState(str, Enum):
    """Estados de uma sessão de atendimento inicial."""
    
    # Fase 1: Entrada
    INITIAL = "INITIAL"                    # Recém-chegou
    AWAITING_INTENT = "AWAITING_INTENT"    # Esperando intenção
    
    # Fase 2: Coleta
    TRIAGE = "TRIAGE"                      # Identificando tipo
    COLLECTING_INFO = "COLLECTING_INFO"    # Coletando dados
    
    # Fase 3: Resposta
    GENERATING_RESPONSE = "GENERATING_RESPONSE"
    
    # Fase 4: Encerramento
    HANDOFF_HUMAN = "HANDOFF_HUMAN"        # Terminal
    SELF_SERVE_INFO = "SELF_SERVE_INFO"    # Terminal
    ROUTE_EXTERNAL = "ROUTE_EXTERNAL"      # Terminal
    SCHEDULED_FOLLOWUP = "SCHEDULED_FOLLOWUP"  # Terminal
    
    # Exceções
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"

TERMINAL_STATES = {
    SessionState.HANDOFF_HUMAN,
    SessionState.SELF_SERVE_INFO,
    SessionState.ROUTE_EXTERNAL,
    SessionState.SCHEDULED_FOLLOWUP,
}
```

### 3.3 Eventos de Conversa

**domain/session/events.py**

```python
from enum import Enum

class SessionEvent(str, Enum):
    """Eventos que disparam transições de estado."""
    
    # Intenção
    USER_SENT_TEXT = "USER_SENT_TEXT"
    USER_SELECTED_BUTTON = "USER_SELECTED_BUTTON"
    USER_SELECTED_LIST_ITEM = "USER_SELECTED_LIST_ITEM"
    
    # Resposta
    RESPONSE_GENERATED = "RESPONSE_GENERATED"
    MESSAGE_SENT = "MESSAGE_SENT"
    
    # Conclusão
    HUMAN_HANDOFF_READY = "HUMAN_HANDOFF_READY"
    SELF_SERVE_COMPLETE = "SELF_SERVE_COMPLETE"
    EXTERNAL_ROUTE_READY = "EXTERNAL_ROUTE_READY"
    FOLLOWUP_SCHEDULED = "FOLLOWUP_SCHEDULED"
    
    # Exceções
    CONTEXT_ERROR = "CONTEXT_ERROR"
    SESSION_TIMEOUT = "SESSION_TIMEOUT"
    LLM_FAILURE = "LLM_FAILURE"
```

### 3.4 Tabela de Transições

**domain/session/transitions.py**

```python
from .states import SessionState
from .events import SessionEvent

TRANSITIONS = {
    SessionState.INITIAL: {
        SessionEvent.USER_SENT_TEXT: SessionState.TRIAGE,
    },
    
    SessionState.TRIAGE: {
        SessionEvent.RESPONSE_GENERATED: SessionState.COLLECTING_INFO,
    },
    
    SessionState.COLLECTING_INFO: {
        SessionEvent.USER_SENT_TEXT: SessionState.GENERATING_RESPONSE,
        SessionEvent.USER_SELECTED_BUTTON: SessionState.GENERATING_RESPONSE,
        SessionEvent.USER_SELECTED_LIST_ITEM: SessionState.GENERATING_RESPONSE,
    },
    
    SessionState.GENERATING_RESPONSE: {
        SessionEvent.MESSAGE_SENT: SessionState.COLLECTING_INFO,
        SessionEvent.HUMAN_HANDOFF_READY: SessionState.HANDOFF_HUMAN,
        SessionEvent.SELF_SERVE_COMPLETE: SessionState.SELF_SERVE_INFO,
        SessionEvent.EXTERNAL_ROUTE_READY: SessionState.ROUTE_EXTERNAL,
        SessionEvent.FOLLOWUP_SCHEDULED: SessionState.SCHEDULED_FOLLOWUP,
    },
    
    # Terminal states não têm transições
}

# Ações por evento
ACTION_BY_EVENT = {
    SessionEvent.USER_SENT_TEXT: ["DETECT_EVENT", "CHECK_CONTEXT"],
    SessionEvent.RESPONSE_GENERATED: ["SEND_MESSAGE"],
    SessionEvent.MESSAGE_SENT: ["SAVE_STATE"],
    SessionEvent.HUMAN_HANDOFF_READY: ["NOTIFY_HUMAN", "SAVE_STATE"],
}
```

---

## 4. Uso de LLM — 3 Pontos Críticos

### 4.1 Ponto 1: Detecção de Evento (Event Detection)

**Objetivo:** Dado o input do usuário, qual evento disparou?

**Entrada:**
- Mensagem de texto (ou tipo de interação)
- Contexto anterior (histórico, estado atual)
- Intenção conhecida (se houver)

**Saída:**
```json
{
  "event": "USER_SENT_TEXT",
  "detected_intent": "solicitar_delivery",
  "confidence": 0.95,
  "requires_followup": false
}
```

**Prompt Versionado:**
```yaml
# ai/config/prompts.yaml
event_detection:
  v1:
    system: |
      Você é um detector de intenção em conversas de atendimento.
      Dado um input de usuário, identifique qual EVENTO foi disparado.
      
      Eventos válidos: {EVENTS}
      Contexto anterior: {CONTEXT}
      
      Responda em JSON com: {event, detected_intent, confidence}
    
    model: "gpt-4-turbo"
    temperature: 0.3
    max_tokens: 200
```

**Implementação:**
```python
# ai/assistant_event_detector.py

from typing import Any
from pydantic import BaseModel

class EventDetectionResult(BaseModel):
    event: str
    detected_intent: str
    confidence: float
    requires_followup: bool

async def detect_event(
    user_input: str,
    context: dict[str, Any],
    llm_client: Any,  # OpenAI, Anthropic, etc.
) -> EventDetectionResult:
    """
    Chamar LLM para detectar evento.
    
    Fluxo:
    1. Carregar prompt de config
    2. Substituir variáveis (context, eventos válidos)
    3. Chamar LLM
    4. Parse resposta em EventDetectionResult
    5. Validar confiança (se < threshold, escalable error)
    """
    prompt = get_prompt("event_detection", version="v1")
    prompt = prompt.format(
        EVENTS=",".join([e.value for e in SessionEvent]),
        CONTEXT=json.dumps(context),
        USER_INPUT=user_input,
    )
    
    response = await llm_client.create_message(
        model="gpt-4-turbo",
        system="...",
        user_message=prompt,
        temperature=0.3,
    )
    
    result = EventDetectionResult.model_validate_json(response.content)
    
    if result.confidence < 0.7:
        logger.warning(f"Low confidence event detection: {result}")
    
    return result
```

---

### 4.2 Ponto 2: Geração de Resposta (Response Generation)

**Objetivo:** Dado o evento e contexto, qual deve ser a resposta?

**Entrada:**
- Evento detectado
- Contexto (histórico, estado da conversa)
- Intenção do usuário
- Perfil do usuário (se disponível)

**Saída:**
```json
{
  "text_content": "Qual é o tipo de serviço que você procura?",
  "suggested_next_state": "COLLECTING_INFO",
  "requires_human_review": false
}
```

**Prompt Versionado:**
```yaml
response_generation:
  v1:
    system: |
      Você é um assistente de atendimento Pyloto.
      Gere uma resposta natural, profissional e concisa.
      
      CONTEXTO: {CONTEXT}
      EVENTO: {EVENT}
      INTENÇÃO DETECTADA: {INTENT}
      
      Responda com JSON: {text_content, suggested_next_state, requires_human_review}
    
    model: "gpt-4-turbo"
    temperature: 0.7
    max_tokens: 500
```

**Implementação:**
```python
# ai/assistant_response_generator.py

from typing import Any
from pydantic import BaseModel

class ResponseGenerationResult(BaseModel):
    text_content: str
    suggested_next_state: str
    requires_human_review: bool
    confidence: float

async def generate_response(
    event: str,
    context: dict[str, Any],
    user_input: str,
    llm_client: Any,
) -> ResponseGenerationResult:
    """
    Chamar LLM para gerar resposta contextualizada.
    """
    prompt = get_prompt("response_generation", version="v1")
    prompt = prompt.format(
        CONTEXT=json.dumps(context),
        EVENT=event,
        INTENT=context.get("detected_intent", "unknown"),
        USER_INPUT=user_input,
    )
    
    response = await llm_client.create_message(
        model="gpt-4-turbo",
        system="...",
        user_message=prompt,
        temperature=0.7,
    )
    
    result = ResponseGenerationResult.model_validate_json(response.content)
    
    if result.requires_human_review:
        logger.info(f"Response flagged for human review: {result}")
    
    return result
```

---

### 4.3 Ponto 3: Seleção de Tipo de Mensagem (Message Type Selection)

**⭐ NOVO E CRUCIAL: Inteligência Dinâmica**

**Objetivo:** Dado o contexto e resposta, qual tipo de mensagem usar?

**Exemplos:**
- Pergunta Sim/Não → `InteractiveButtonMessage` (botões "Sim" / "Não")
- Pergunta com múltiplas opções → `InteractiveListMessage` (lista com seções)
- Informação simples → `TextMessage`
- Link importante → `InteractiveCTAURLMessage`
- Endereço para delivery → `LocationMessage`
- Contato para suporte → `ContactMessage`

**Entrada:**
```json
{
  "text_content": "Qual é o tipo de serviço?",
  "response_type": "question_with_options",
  "options": ["Delivery", "Serviço no Local", "Consultoria"],
  "context": {
    "user_profile": "new_client",
    "conversation_turn": 2
  }
}
```

**Saída:**
```json
{
  "message_type": "InteractiveListMessage",
  "parameters": {
    "body": "Qual é o tipo de serviço que você procura?",
    "button": "Ver Opções",
    "sections": [
      {
        "title": "Serviços",
        "rows": [
          {"id": "delivery", "title": "Delivery", "description": "Entrega de produtos"},
          {"id": "service", "title": "Serviço no Local", "description": "Atendimento presencial"},
          {"id": "consulting", "title": "Consultoria", "description": "Orientação especializada"}
        ]
      }
    ],
    "footer": "Escolha uma opção para continuar"
  },
  "confidence": 0.92,
  "rationale": "Pergunta com 3+ opções: InteractiveListMessage melhora UX"
}
```

**Prompt Versionado:**
```yaml
message_type_selection:
  v1:
    system: |
      Você é um seletor de tipos de mensagem WhatsApp.
      Dado um contexto e uma resposta, escolha o MELHOR tipo de mensagem.
      
      Tipos disponíveis:
      - TextMessage: Texto simples
      - ImageMessage: Imagem
      - VideoMessage: Vídeo (H.264 + AAC)
      - InteractiveButtonMessage: Botões (1-3)
      - InteractiveListMessage: Lista com seções (1-10 seções)
      - InteractiveCTAURLMessage: URL com botão
      - LocationMessage: Localização geográfica
      - ContactMessage: Cartão de contato
      - TemplateMessage: Template pré-aprovado
      - ReactionMessage: Emoji de reação
      
      CONTEXTO: {CONTEXT}
      RESPOSTA: {RESPONSE}
      OPÇÕES (se houver): {OPTIONS}
      
      Responda com JSON:
      {message_type, parameters, confidence, rationale}
    
    model: "gpt-4-turbo"
    temperature: 0.5
    max_tokens: 800
```

**Implementação:**
```python
# ai/assistant_message_type.py

from typing import Any
from pydantic import BaseModel
from domain.whatsapp_message_types import (
    TextMessage,
    InteractiveButtonMessage,
    InteractiveListMessage,
    # ... outros tipos
)

class MessageTypeSelectionResult(BaseModel):
    message_type: str  # Nome da classe
    parameters: dict[str, Any]  # Parâmetros para instanciar
    confidence: float
    rationale: str

async def select_message_type(
    response_content: str,
    context: dict[str, Any],
    options: list[str] | None = None,
    llm_client: Any = None,
) -> MessageTypeSelectionResult:
    """
    Chamar LLM para selecionar melhor tipo de mensagem.
    
    Fluxo:
    1. Carregar prompt de config
    2. Analisar response_content (tipo de pergunta?)
    3. Chamar LLM com contexto
    4. Parse em MessageTypeSelectionResult
    5. Validar contra schema do tipo (via Pydantic)
    6. Retornar instância pronta para enviar
    """
    prompt = get_prompt("message_type_selection", version="v1")
    prompt = prompt.format(
        CONTEXT=json.dumps(context),
        RESPONSE=response_content,
        OPTIONS=json.dumps(options or []),
    )
    
    response = await llm_client.create_message(
        model="gpt-4-turbo",
        system="...",
        user_message=prompt,
        temperature=0.5,
    )
    
    result = MessageTypeSelectionResult.model_validate_json(response.content)
    
    # Validar que o tipo existe
    if result.message_type not in get_available_message_types():
        raise ValueError(f"Unknown message type: {result.message_type}")
    
    # Instanciar e validar parâmetros
    message_class = get_message_class(result.message_type)
    message_instance = message_class(**result.parameters)
    
    logger.info(
        f"Selected {result.message_type} with confidence {result.confidence}",
        extra={"rationale": result.rationale}
    )
    
    return result, message_instance
```

---

## 5. Seleção Inteligente de Tipo de Mensagem

### 5.1 Matriz de Decisão (Heurística + LLM)

```
Tipo de Resposta          | Tipo de Mensagem         | Validação
────────────────────────────────────────────────────────────────────
Sim/Não                   | InteractiveButtonMessage | 2 botões exatos
2-3 opções                | InteractiveButtonMessage | max_items=3
4+ opções                 | InteractiveListMessage   | max_items=10
Pergunta aberta           | TextMessage              | apenas texto
URL importante            | InteractiveCTAURLMessage | URL validada
Endereço/Mapa             | LocationMessage          | lat/lon corretos
Contato do suporte        | ContactMessage           | vCard válido
Informação com imagem     | ImageMessage + TextMsg   | imagem acessível
Vídeo tutorial            | VideoMessage             | H.264 + AAC
Template (newsletter)     | TemplateMessage          | template aprovado
```

### 5.2 Exemplos Práticos

#### Exemplo 1: Pergunta Sim/Não

**Contexto:**
```json
{
  "user_intent": "solicitar_delivery",
  "conversation_turn": 2,
  "next_question": "Você é cliente Pyloto?",
  "expected_answer_type": "boolean"
}
```

**LLM Decision Process:**
```
1. Detectar: resposta_type = "yes_no_question"
2. Gerar: "Já é cliente Pyloto ou é sua primeira vez?"
3. Selecionar tipo:
   - Input: {"type": "yes_no", "text": "Já é cliente Pyloto..."}
   - LLM: "Esta é uma pergunta sim/não → InteractiveButtonMessage"
   - Output:
     {
       "message_type": "InteractiveButtonMessage",
       "parameters": {
         "body": "Já é cliente Pyloto ou é sua primeira vez?",
         "buttons": [
           {"id": "btn_yes", "title": "Sou cliente"},
           {"id": "btn_no", "title": "Primeira vez"}
         ],
         "footer": "Escolha uma opção"
       }
     }
```

**Resultado Esperado:**
```
┌─────────────────────────────────────┐
│ Já é cliente Pyloto ou é sua        │
│ primeira vez?                       │
├─────────────────────────────────────┤
│ [Sou cliente]  [Primeira vez]       │
├─────────────────────────────────────┤
│ Escolha uma opção                   │
└─────────────────────────────────────┘
```

#### Exemplo 2: Pergunta com Múltiplas Opções

**Contexto:**
```json
{
  "user_intent": "solicitar_delivery",
  "conversation_turn": 3,
  "next_question": "Qual tipo de serviço?",
  "options": ["Delivery de alimentos", "Delivery de compras", "Serviço de limpeza"],
  "expected_answer_type": "single_choice_from_list"
}
```

**LLM Decision Process:**
```
1. Detectar: resposta_type = "multiple_choice"
2. Gerar: "Qual tipo de serviço você procura?"
3. Selecionar tipo:
   - Input: {
       "type": "multiple_choice",
       "text": "Qual tipo de serviço...",
       "options": [...3 opções]
     }
   - LLM: "Mais de 3 opções → InteractiveListMessage com seções"
   - Output:
     {
       "message_type": "InteractiveListMessage",
       "parameters": {
         "body": "Qual tipo de serviço você procura?",
         "button": "Ver Opções",
         "sections": [
           {
             "title": "Categorias",
             "rows": [
               {
                 "id": "food_delivery",
                 "title": "Alimentos",
                 "description": "Entrega de restaurantes"
               },
               {
                 "id": "shopping_delivery",
                 "title": "Compras",
                 "description": "Entrega de lojas"
               },
               {
                 "id": "cleaning_service",
                 "title": "Limpeza",
                 "description": "Serviço de limpeza"
               }
             ]
           }
         ]
       }
     }
```

**Resultado Esperado:**
```
┌─────────────────────────┐
│ Qual tipo de serviço    │
│ você procura?           │
├─────────────────────────┤
│ [Ver Opções ▼]          │
│                         │
│ CATEGORIAS              │
│ • Alimentos             │
│   Entrega de           │
│   restaurantes         │
│ • Compras               │
│   Entrega de lojas     │
│ • Limpeza               │
│   Serviço de limpeza   │
├─────────────────────────┤
│ Pyloto - Menu          │
└─────────────────────────┘
```

#### Exemplo 3: URL com CTA

**Contexto:**
```json
{
  "message_type": "offer_link",
  "content": "Veja nosso catálogo completo",
  "url": "https://example.com/catalog",
  "user_profile": "new_client"
}
```

**LLM Decision:**
```
- Input: {"type": "url_with_cta", "text": "Veja nosso catálogo..."}
- LLM: "Link importante com call-to-action → InteractiveCTAURLMessage"
- Output:
  {
    "message_type": "InteractiveCTAURLMessage",
    "parameters": {
      "body": "Conheça todos os nossos serviços!",
      "cta_url": "https://example.com/catalog",
      "cta_display_text": "Ver Catálogo",
      "footer": "Clique para explorar"
    }
  }
```

---

## 6. Exemplos Práticos

### 6.1 Fluxo Completo: Do Input ao Output

**Turno 1: Usuário entra na conversa**

```
INPUT:
  user_message: "Olá, preciso fazer um pedido"
  
STEP 1 (Event Detection):
  LLM: "O que é evento?"
  OUTPUT: {event: "USER_SENT_TEXT", intent: "start_order"}
  
STEP 2 (FSM Dispatch):
  current_state: INITIAL
  event: USER_SENT_TEXT
  → next_state: TRIAGE
  → actions: [DETECT_EVENT, CHECK_CONTEXT]
  
STEP 3 (Response Generation):
  LLM: "O que responder?"
  OUTPUT: {text_content: "Bem-vindo! Para melhor atendê-lo, qual tipo de serviço você procura?"}
  
STEP 4 (Message Type Selection):
  LLM: "Qual tipo de mensagem?"
  INPUT: {
    response: "Bem-vindo! Para melhor...",
    options: ["Delivery", "Serviço", "Consultoria"],
    context: {turn: 1, is_first_contact: true}
  }
  OUTPUT: {
    message_type: "InteractiveListMessage",
    parameters: {...}
  }
  
STEP 5 (Send):
  send_whatsapp_message(message_type_instance)
  
STEP 6 (Save State):
  save_session_context({
    state: COLLECTING_INFO,
    last_sent_message_type: InteractiveListMessage,
    turn: 1
  })

OUTPUT (To User):
  ┌─────────────────────────┐
  │ Bem-vindo à Pyloto!     │
  │                         │
  │ Qual tipo de serviço    │
  │ você procura?           │
  ├─────────────────────────┤
  │ [Ver Opções ▼]          │
  │                         │
  │ SERVIÇOS                │
  │ • Delivery              │
  │ • Serviço no Local      │
  │ • Consultoria           │
  ├─────────────────────────┤
  │ Pyloto - Bem-vindo      │
  └─────────────────────────┘
```

---

### 6.2 Arquivo de Configuração Versionado

**ai/config/prompts.yaml**

```yaml
# Prompts versionados por responsabilidade

event_detection:
  v1:
    system: |
      Você é detector de intenção em conversas de atendimento Pyloto.
      Seu trabalho é identificar qual EVENTO foi disparado pelo usuário.
      
      Eventos válidos: {EVENTS}
      
      Histórico da conversa:
      {HISTORY}
      
      Input do usuário:
      {USER_INPUT}
      
      Responda SEMPRE em JSON com este formato:
      {{
        "event": "<EventName>",
        "detected_intent": "<intent_description>",
        "confidence": <0.0-1.0>,
        "requires_followup": <true|false>
      }}
    
    model: "gpt-4-turbo"
    temperature: 0.3
    max_tokens: 200
    
  v2:
    # Versão melhorada com mais contexto
    system: |
      [versão melhorada do v1]
    model: "gpt-4"
    temperature: 0.2

response_generation:
  v1:
    system: |
      Você é um assistente de atendimento Pyloto.
      Seu objetivo é gerar uma resposta natural, profissional e concisa
      que avance a conversa de forma eficiente.
      
      REGRAS:
      1. Máximo 2-3 frases
      2. Tom profissional mas amigável
      3. Sempre forneça próximo passo claro
      4. Sem jargão técnico
      
      Contexto atual:
      {CONTEXT}
      
      Evento detectado:
      {EVENT}
      
      Responda em JSON:
      {{
        "text_content": "<resposta_para_enviar>",
        "suggested_next_state": "<próximo_estado>",
        "requires_human_review": <true|false>
      }}
    
    model: "gpt-4-turbo"
    temperature: 0.7
    max_tokens: 500

message_type_selection:
  v1:
    system: |
      Você é um seletor de tipos de mensagem WhatsApp.
      
      Tipos disponíveis:
      - TextMessage
      - ImageMessage
      - VideoMessage
      - InteractiveButtonMessage (1-3 botões)
      - InteractiveListMessage (1-10 seções)
      - InteractiveCTAURLMessage (URL + botão)
      - LocationMessage
      - ContactMessage
      - TemplateMessage
      - ReactionMessage
      
      Escolha o MELHOR tipo para esta situação.
      
      Resposta a enviar:
      {RESPONSE}
      
      Contexto:
      {CONTEXT}
      
      Responda em JSON:
      {{
        "message_type": "<TypeName>",
        "parameters": {{<parâmetros_específicos>}},
        "confidence": <0.0-1.0>,
        "rationale": "<explicação>"
      }}
    
    model: "gpt-4-turbo"
    temperature: 0.5
    max_tokens: 800
```

---

## 7. Roadmap de Implementação

### Fase 1: Fundação FSM (Semana 1-2)

**Tarefas:**
- [ ] Criar `domain/session/states.py` com 10+ estados
- [ ] Criar `domain/session/events.py` com 10+ eventos
- [ ] Criar `domain/session/transitions.py` com tabela completa
- [ ] Criar `application/fsm_engine.py` (dispatcher puro, similar a `engine.py` de pyloto_lab)
- [ ] Testes unitários para cada transição
- [ ] Documentação no README

**Entregáveis:**
- FSM funcionando end-to-end
- Testes com 95%+ cobertura
- Arquivo de estados congelado em `regras_e_padroes.md`

---

### Fase 2: LLM — Event Detection (Semana 2-3)

**Tarefas:**
- [ ] Criar `ai/assistant_event_detector.py`
- [ ] Criar contrato `ai/contracts/event_detection.py`
- [ ] Versionar prompt em `ai/config/prompts.yaml`
- [ ] Testar com casos reais (usuários de teste)
- [ ] Medir confiança (threshold >= 0.7)
- [ ] Logging estruturado com correlationId

**Entregáveis:**
- Event detector funcionando
- Teste com 20+ tipos de input
- Métrica de confiança rastreada

---

### Fase 3: LLM — Response Generation (Semana 3-4)

**Tarefas:**
- [ ] Criar `ai/assistant_response_generator.py`
- [ ] Criar contrato `ai/contracts/response_generation.py`
- [ ] Versionar prompt v1
- [ ] Integrar com contexto de conversa
- [ ] Testar com contextos variados
- [ ] Implementar flagging de "requires_human_review"

**Entregáveis:**
- Response generator funcionando
- Teste com 30+ scenarios
- Human review metrics

---

### Fase 4: LLM — Message Type Selection ⭐ (Semana 4-5)

**Tarefas:**
- [ ] Criar `ai/assistant_message_type.py`
- [ ] Criar contrato `ai/contracts/message_type_selection.py`
- [ ] Versionar prompt v1
- [ ] Mapear resposta_type → message_type (heurísticas)
- [ ] Testar seleção com 50+ scenarios
- [ ] Validar parâmetros de mensagem (Pydantic)
- [ ] Implementar fallback (se LLM falhar, usar heurística)

**Entregáveis:**
- Message type selector funcionando
- Teste com todos os 12 tipos
- Confidence metrics

---

### Fase 5: Integração Completa (Semana 5-6)

**Tarefas:**
- [ ] Criar `ai/orchestrator.py` que coordena 3 pontos de LLM
- [ ] Atualizar `application/webhook_handler.py` para usar FSM + LLM
- [ ] Atualizar `application/message_sender.py` para instanciar tipo correto
- [ ] Integração com Redis/Firestore para persisting estado
- [ ] E2E testing com fluxos reais
- [ ] Load testing (capacidade de requisições/s)

**Entregáveis:**
- Sistema end-to-end funcionando
- 10+ fluxos testados
- Documentação de uso

---

### Fase 6: Otimização + Monitoramento (Semana 6-7)

**Tarefas:**
- [ ] Análise de logs (confusão em eventos, fallbacks)
- [ ] Iteração v2 de prompts (baseado em feedback)
- [ ] Caching de decisões (Redis)
- [ ] Métricas Prometheus (latência, erros, confiança)
- [ ] Dashboard de monitoramento
- [ ] A/B test de prompts

**Entregáveis:**
- Sistema otimizado
- Dashboard de health
- Runbook de troubleshooting

---

## 8. Estrutura de Arquivos Resumida

```
src/pyloto_corp/
├── domain/session/
│   ├── __init__.py
│   ├── states.py           # 10+ estados canônicos
│   ├── events.py           # 10+ eventos possíveis
│   └── transitions.py      # Tabela FSM
│
├── application/
│   ├── fsm_engine.py       # Dispatcher puro (novo)
│   ├── message_sender.py   # Modificado: integra tipo
│   └── webhook_handler.py  # Modificado: extrai evento
│
├── ai/
│   ├── __init__.py
│   ├── orchestrator.py                    # Orquestra 3 LLMs
│   ├── assistant_event_detector.py        # Ponto 1
│   ├── assistant_response_generator.py    # Ponto 2
│   ├── assistant_message_type.py          # Ponto 3 ⭐
│   ├── config/
│   │   └── prompts.yaml                  # Versionado
│   └── contracts/
│       ├── event_detection.py
│       ├── response_generation.py
│       └── message_type_selection.py
│
└── infra/
    ├── storage.py          # Modificado: salva estado
    └── meta_client.py
```

---

## 9. Validação e Testes

### 9.1 Testes Unitários (por camada)

**FSM:**
```python
def test_state_transition_from_initial_to_triage():
    result = dispatch(
        current_state=SessionState.INITIAL,
        event=SessionEvent.USER_SENT_TEXT,
        payload={"user_input": "Olá"}
    )
    assert result["next_state"] == SessionState.TRIAGE
    assert "DETECT_EVENT" in result["actions"]
```

**Event Detection:**
```python
async def test_event_detection_yes_no_question():
    result = await detect_event(
        user_input="Sim, quero fazer um pedido",
        context={},
        llm_client=mock_llm
    )
    assert result.event == "USER_SENT_TEXT"
    assert result.confidence >= 0.8
```

**Message Type Selection:**
```python
async def test_message_type_for_boolean_question():
    result, message = await select_message_type(
        response_content="Você é cliente Pyloto?",
        context={"question_type": "boolean"},
        llm_client=mock_llm
    )
    assert result.message_type == "InteractiveButtonMessage"
    assert len(message.buttons) == 2
```

### 9.2 Testes E2E (fluxos reais)

```python
async def test_complete_flow_new_client_delivery():
    """Fluxo real: cliente novo solicita delivery."""
    
    # 1. Cliente entra
    input_1 = "Olá, preciso fazer um pedido"
    result_1 = await run_session_turn(input_1, session_id="new_123")
    assert "InteractiveListMessage" in str(result_1.message)
    
    # 2. Cliente seleciona Delivery
    input_2 = "Delivery"  # Clique em botão
    result_2 = await run_session_turn(input_2, session_id="new_123")
    assert result_2.state == SessionState.COLLECTING_INFO
    
    # 3. Cliente fornece endereço
    input_3 = "Rua X, número 123"
    result_3 = await run_session_turn(input_3, session_id="new_123")
    assert result_3.message_type in ["TextMessage", "LocationMessage"]
    
    # 4. Conversa encerra
    # ...
    assert result_n.state in TERMINAL_STATES
```

---

## 10. Conclusão

### Por que esse design?

1. **FSM explícito:** Estados claro, sem "mágica" de fluxo
2. **LLM em 3 pontos:** Detecção, Geração, Seleção (responsabilidades isoladas)
3. **Seleção dinâmica de tipo:** Adapta UX ao contexto (Sim/Não → Botões, Múltipla escolha → Lista)
4. **Prompts versionados:** Fácil iterar sem quebrar produção
5. **Determinístico + Inteligente:** Combina o melhor dos dois mundos

### Próximos Passos Recomendados

1. **Validar design:** Code review com arquitetura do banco
2. **Prototipar Fase 1:** Ter FSM funcional em 1 semana
3. **Implementar iterativamente:** Fases 2-4 em paralelo, Fase 5 após integração
4. **Monitorar:** Dashboard de confiança e erros desde dia 1

---

**Documento Preparado Por:** GitHub Copilot (Executor Mode)  
**Data:** 26 de janeiro de 2025  
**Status:** 📋 Design Completo — Pronto para Implementação  
**Próxima Revisão:** Após Prototype (Fase 1)

