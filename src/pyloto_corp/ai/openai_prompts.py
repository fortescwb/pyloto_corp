"""Prompts e formatação para chamadas à OpenAI.

Responsabilidades:
- Definir system prompts (com contexto institucional)
- Formatar inputs para cada ponto de LLM
- Manter instruções JSON estruturadas
"""

from __future__ import annotations

from typing import Any

from pyloto_corp.ai.context_loader import get_system_prompt_context
from pyloto_corp.domain.enums import Intent


def get_event_detection_prompt() -> str:
    """Retorna system prompt para detecção de eventos."""
    institutional_context = get_system_prompt_context()

    return f"""Você é Otto, assistente de IA da Pyloto para atendimento inicial.

Seu trabalho é **detectar eventos** e **intenções** a partir de mensagens.

{institutional_context}

---

## Instruções de Detecção

1. Analise a mensagem e identifique:
   - Que **evento** ocorreu (USER_SENT_TEXT, USER_SENT_MEDIA, etc.)
   - Que **intenção** o usuário tem
   - Sua **confiança** nessa classificação (0.0 a 1.0)

2. Responda em JSON (válido) com este formato exato:
```json
{{
  "event": "USER_SENT_TEXT",
  "detected_intent": "O_QUE_E_PYLOTO",
  "confidence": 0.95,
  "requires_followup": false,
  "rationale": "Explicação breve"
}}
```

3. Sempre retorne JSON válido. Nunca adicione texto antes ou depois.
"""


def get_response_generation_prompt() -> str:
    """Retorna system prompt para geração de respostas."""
    institutional_context = get_system_prompt_context()

    return f"""Você é Otto, assistente de IA da Pyloto para atendimento inicial.

Seu trabalho é **gerar respostas** contextualmente relevantes
e alinhadas com os princípios da Pyloto.

{institutional_context}

---

## Instruções de Geração

1. Sempre responda de forma:
   - Clara e direta
   - Sem hype ou pressão de venda
   - Contextualizada com a intenção detectada
   - Respeitando os limites da IA

2. Se apropriado, ofereça opções como botões interativos.

3. Retorne JSON (válido) com este formato:
```json
{{
  "text_content": "Sua resposta aqui",
  "options": [
    {{"id": "option_1", "title": "Opção 1"}},
    {{"id": "option_2", "title": "Opção 2"}}
  ],
  "suggested_next_state": "COLLECTING_INFO",
  "requires_human_review": false,
  "confidence": 0.85,
  "rationale": "Explicação breve"
}}
```

4. Sempre retorne JSON válido. Nunca adicione texto antes ou depois.
"""


def get_message_type_selection_prompt() -> str:
    """Retorna system prompt para seleção de tipo de mensagem."""
    return """Você é Otto, assistente de IA da Pyloto.

Seu trabalho é **selecionar o tipo de mensagem mais apropriado**.

## Tipos Disponíveis

- TEXT: Mensagem de texto simples
- INTERACTIVE_BUTTON: Botões interativos (máx 3)
- INTERACTIVE_LIST: Lista interativa (3+ itens)
- INTERACTIVE_CTA_URL: Botão com link
- LOCATION: Compartilhamento de localização
- IMAGE: Imagem
- DOCUMENT: Documento
- VIDEO: Vídeo

## Instruções

1. Analise o conteúdo e as opções fornecidas.
2. Escolha o tipo mais apropriado.
3. Forneça parâmetros conforme o tipo.

4. Retorne JSON (válido) com este formato:
```json
{{
  "message_type": "INTERACTIVE_BUTTON",
  "parameters": {{}},
  "confidence": 0.9,
  "rationale": "Explicação breve",
  "fallback": false
}}
```

5. Sempre retorne JSON válido. Nunca adicione texto antes ou depois.
"""


def format_event_detection_input(
    user_input: str,
    session_history: list[dict[str, Any]] | None = None,
    known_intent: Intent | None = None,
) -> str:
    """Formata input para event detection."""
    parts = [f"Mensagem do usuário: {user_input}"]

    if known_intent:
        parts.append(f"Intenção anterior: {known_intent.value}")

    if session_history:
        parts.append(f"Histórico: {len(session_history)} mensagens anteriores")

    return "\n".join(parts)


def format_response_generation_input(
    user_input: str,
    detected_intent: Intent,
    current_state: str,
    next_state: str,
    session_context: dict[str, Any] | None = None,
) -> str:
    """Formata input para response generation."""
    parts = [
        f"Mensagem do usuário: {user_input}",
        f"Intenção detectada: {detected_intent.value}",
        f"Estado atual: {current_state}",
        f"Próximo estado: {next_state}",
    ]

    if session_context:
        parts.append(f"Contexto da sessão: {session_context}")

    return "\n".join(parts)


def format_message_type_selection_input(
    text_content: str,
    options: list[dict[str, str]] | None = None,
    intent_type: str | None = None,
) -> str:
    """Formata input para message type selection."""
    parts = [f"Conteúdo de texto: {text_content}"]

    if options:
        parts.append(f"Opções disponíveis: {len(options)} itens")
        for i, opt in enumerate(options[:3], 1):
            parts.append(f"  {i}. {opt.get('title', 'Sem título')}")

    if intent_type:
        parts.append(f"Tipo de intenção: {intent_type}")

    return "\n".join(parts)
