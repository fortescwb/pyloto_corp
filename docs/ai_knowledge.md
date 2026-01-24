# Base de conhecimento da IA (pyloto_corp)

## Objetivo
Orientar o agente de IA para atendimento inicial institucional/comercial da Pyloto.

## Conteúdo mínimo que a IA deve dominar
- O que é a Pyloto e suas vertentes de atuação.
- Diferença entre Pyloto CRM, Connectors, sistemas sob medida e Pyloto Entrega.
- Limites de escopo: não é CRM, não fecha contrato, não executa operação final.

## Regras de conversa
- Identificar intenção principal e manter apenas uma ativa por vez.
- Máximo de 3 intenções por sessão (fila leve).
- Conter contexto: intenções não ativas guardam apenas metadados.
- Encerrar sempre com 1 outcome terminal canônico.

## Segurança
- Nunca expor dados sensíveis em logs.
- Não repetir payloads do usuário em logs ou respostas internas.
- Evitar coleta excessiva fora da intenção ativa.

## Fontes de verdade
- Documento "Produto — pyloto_corp".
- README do repositório pyloto_corp.

## Conversation History
- Armazenamento em Firestore (fonte de verdade).
- user_key derivado via HMAC (sem expor telefone).
- Textos sanitizados, no máximo 4000 caracteres.
- Sem payload bruto ou anexos no histórico.
