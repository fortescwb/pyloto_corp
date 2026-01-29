"""Sanitização de conteúdo com PII (mascaramento de dados sensíveis).

Responsabilidade:
- Mascarar CPF, CNPJ, e-mails, telefones BR e chaves Pix
- Aplicar defesa em profundidade (múltiplos pontos no pipeline)
- Garantir determinismo (mesma entrada = mesma saída)

Conforme regras_e_padroes.md: logs sem PII, defesa em profundidade.
"""

from __future__ import annotations

import re
from re import Pattern

# Compilar patterns uma vez (performance + determinismo)
_PATTERNS: dict[str, Pattern[str]] = {
    # CPF: 123.456.789-10 ou 12345678910
    "cpf": re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"),
    # CNPJ: 12.345.678/0001-90 ou 12345678000190
    "cnpj": re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b"),
    # E-mail
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    # Telefone BR: +55 11 98765-4321, (11) 98765-4321, 11 98765-4321, etc
    "phone": re.compile(
        r"\+?55\s*\(?(\d{2})\)?\s*(?:98|99)?\d{3,4}-?\d{4}|"
        r"\(?(\d{2})\)?\s*(?:98|99)?\d{3,4}-?\d{4}|"
        r"\b9\d{3,4}-?\d{4}\b"
    ),
    # Chaves Pix por CPF ou CNPJ (identificáveis no padrão acima, já mascaradas)
    # Pix por e-mail (mascarado acima)
    # Pix por telefone (mascarado acima)
}


def sanitize_response_content(text: str) -> str:
    """Mascara PII em texto de resposta.

    Substitui padrões identificados por máscaras determinísticas.

    Args:
        text: Texto potencialmente contendo PII

    Returns:
        Texto com PII mascarado (determinístico: mesma entrada = mesma saída)

    Exemplos:
        >>> sanitize_response_content("Meu CPF é 123.456.789-10")
        'Meu CPF é [CPF]'

        >>> sanitize_response_content("Contate em john@example.com")
        'Contate em [EMAIL]'
    """
    if not text:
        return text

    result = text

    # Aplicar máscaras na ordem: específico → genérico
    # Mascarar CPF
    result = _PATTERNS["cpf"].sub("[CPF]", result)

    # Mascarar CNPJ
    result = _PATTERNS["cnpj"].sub("[CNPJ]", result)

    # Mascarar e-mail
    result = _PATTERNS["email"].sub("[EMAIL]", result)

    # Mascarar telefone
    result = _PATTERNS["phone"].sub("[PHONE]", result)

    return result


def mask_pii_in_history(messages: list[str]) -> list[str]:
    """Mascara PII em histórico de mensagens antes de enviar para LLM.

    Trunca para últimas N mensagens (minimização de dados) e mascara cada uma.

    Args:
        messages: Lista de strings com histórico de conversa

    Returns:
        Lista mascarada e truncada (últimas 5 mensagens no máx)

    Exemplos:
        >>> mask_pii_in_history(["Meu CPF: 123.456.789-10", "Ok"])
        ['Meu CPF: [CPF]', 'Ok']
    """
    if not messages:
        return []

    # Truncar para últimas 5 mensagens (determinístico, limite de tokens)
    max_history = 5
    truncated = messages[-max_history:] if len(messages) > max_history else messages

    # Sanitizar cada mensagem
    return [sanitize_response_content(msg) for msg in truncated]


# Teste determinismo (usado em testes, não em produção)
def _get_sanitize_fingerprint(text: str) -> str:
    """Gera fingerprint determinístico de sanitização para validar idempotência.

    Uso: validar que sanitize_response_content(x) sempre produz mesmo resultado.
    """
    import hashlib

    sanitized = sanitize_response_content(text)
    return hashlib.sha256(sanitized.encode()).hexdigest()
