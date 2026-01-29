"""Prompts para LLM com injeção de contexto institucional.

Reúne os 3 prompts das 3 tarefas LLM:
1. FSM State determination (qual próximo estado)
2. Response generation (gerar resposta baseada em contexto)
3. Message type selection (qual tipo de mensagem usar)
"""

from __future__ import annotations

from pyloto_corp.domain.fsm_states import ConversationState


def build_fsm_state_prompt(
    user_message: str,
    current_state: ConversationState,
    state_history: list[str],
    institutional_context: str,
) -> str:
    """Build prompt para Task #1: FSM state determination.

    Args:
        user_message: Mensagem recebida do usuário
        current_state: Estado atual da conversa
        state_history: Histórico de estados anteriores
        institutional_context: Contexto institucional Pyloto

    Returns:
        Prompt para ChatGPT determinar próximo estado
    """
    history_str = " -> ".join(state_history[-5:]) if state_history else "INIT"

    return f"""
# Tarefa 1: Determinar Próximo Estado da Conversa

{institutional_context}

## Contexto Atual
- Estado Atual: {current_state}
- Histórico de Estados: {history_str}
- Mensagem do Usuário: "{user_message}"

## Estados Válidos para Transição
Estados possíveis que você pode indicar:
- IDENTIFYING: Se precisa coletar informações do usuário
- UNDERSTANDING_INTENT: Se precisa entender melhor a intenção
- PROCESSING: Se está processando a solicitação
- GENERATING_RESPONSE: Se está gerando resposta
- SELECTING_MESSAGE_TYPE: Se está escolhendo tipo de mensagem
- AWAITING_USER: Se aguarda nova mensagem do usuário
- ESCALATING: Se precisa encaminhar para humano
- COMPLETED: Se conversa foi concluída com sucesso
- FAILED: Se algo deu errado
- SPAM: Se é spam/abuso

## Restrições Obrigatórias
- NUNCA feche contrato na conversa inicial
- NUNCA cotize preços
- NUNCA faça negociação
- Respeite os princípios Pyloto (zero-trust, dignity, sustainability)
- Identifique qual vertente de negócio (Entregas, Serviços, Tecnologia, CRM)

## Saída Esperada
```json
{{
    "next_state": "<ProximoEstado>",
    "reasoning": "Explicação breve por que transicionar para este estado",
    "confidence": 0.95,
    "detected_intent_category": "ENTREGAS|SERVICOS|TECNOLOGIA|CRM|IA|COMERCIAL|SUPORTE|LEGAL",
    "vertente": "qual vertente de negócio identificou"
}}
```

Responda APENAS com JSON válido.
"""


def build_response_generation_prompt(
    user_message: str,
    current_state: ConversationState,
    detected_intent_category: str,
    vertente: str,
    institutional_context: str,
    previous_context: str = "",
) -> str:
    """Build prompt para Task #2: Response generation.

    Args:
        user_message: Mensagem do usuário
        current_state: Estado atual
        detected_intent_category: Categoria de intent detectada
        vertente: Qual vertente de negócio
        institutional_context: Contexto institucional
        previous_context: Contexto de mensagens anteriores

    Returns:
        Prompt para ChatGPT gerar resposta
    """
    return f"""
# Tarefa 2: Gerar Resposta Context-Aware

{institutional_context}

## Contexto da Conversa
- Estado Atual: {current_state}
- Intent Detectado: {detected_intent_category}
- Vertente de Negócio: {vertente}
- Mensagem do Usuário: "{user_message}"

{f'- Contexto Anterior: {previous_context}' if previous_context else ''}

## Diretrizes de Resposta
1. Seja claro, conciso e empático
2. Use linguagem apropriada para a vertente ({vertente})
3. Responda EXATAMENTE o que o usuário perguntou
4. NÃO prometa nada fora do escopo da conversa inicial

## Restrições Críticas
- NUNCA feche contrato
- NUNCA cotize ou discuta preços
- NUNCA negocie termos
- NUNCA colete dados pessoais sem necessidade
- Se é uma pergunta fora do escopo, ofereça encaminhar para especialista

## Saída Esperada
```json
{{
    "response": "Sua resposta aqui para a mensagem do usuário",
    "requires_escalation": false,
    "escalation_reason": "Se escalação necessária, qual o motivo",
    "tone": "amigável|profissional|técnico",
    "vertente_specific_guidance": "Qualquer direcionamento específico da vertente"
}}
```

Responda APENAS com JSON válido.
"""


def build_message_type_prompt(
    response: str,
    current_state: ConversationState,
    user_message: str,
    vertente: str,
    institutional_context: str,
) -> str:
    """Build prompt para Task #3: Message type selection.

    Args:
        response: Resposta gerada na Task #2
        current_state: Estado atual
        user_message: Mensagem original do usuário
        vertente: Vertente de negócio
        institutional_context: Contexto institucional

    Returns:
        Prompt para ChatGPT escolher tipo de mensagem
    """
    return f"""
# Tarefa 3: Escolher Tipo de Mensagem WhatsApp

{institutional_context}

## Resposta a Enviar
"{response}"

## Contexto
- Estado: {current_state}
- Vertente: {vertente}
- Mensagem Original: "{user_message}"

## Tipos de Mensagem Disponíveis
- TEXT: Mensagem de texto simples
- IMAGE: Imagem + legenda
- VIDEO: Vídeo + descrição
- DOCUMENT: Documento (PDF, etc)
- BUTTON: Mensagem com botões (máx 3 botões)
- LIST: Menu com opções
- TEMPLATE: Template pré-aprovado (usar com cuidado)

## Regras de Seleção
1. Se resposta é simples e curta (<100 chars): usar TEXT
2. Se contém links ou CTA forte: usar BUTTON (máx 3 botões)
3. Se precisa mostrar múltiplas opções: usar LIST
4. Se há conteúdo visual: usar IMAGE ou VIDEO
5. Se é documento importante: usar DOCUMENT

## Restrições
- Templates requerem aprovação prévia da Meta
- Não use imagens/vídeos sem validação
- Botões devem ser ação clara (não criar confusão)
- Listas máximo 10 itens

## Saída Esperada
```json
{{
    "message_type": "TEXT|IMAGE|VIDEO|DOCUMENT|BUTTON|LIST|TEMPLATE",
    "message_content": "Conteúdo/título da mensagem",
    "buttons": [
        {{"id": "btn_1", "text": "Botão 1", "action": "url|phone|reply"}},
        ...
    ],
    "media_url": "URL da imagem/vídeo/documento (se aplicável)",
    "reasoning": "Por que escolheu este tipo"
}}
```

Responda APENAS com JSON válido.
"""
