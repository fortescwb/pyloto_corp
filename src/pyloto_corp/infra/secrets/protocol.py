from __future__ import annotations

from typing import Protocol


class SecretProvider(Protocol):
    """Porta para leitura de segredos.

    Implementações devem:
    - Nunca logar o valor do secret
    - Levantar RuntimeError se secret não encontrado
    - Suportar versionamento quando aplicável
    """

    def get_secret(self, name: str, version: str = "latest") -> str:
        """Obtém o valor do segredo."""

    def secret_exists(self, name: str) -> bool:
        """Verifica se um secret existe sem retornar seu valor."""
