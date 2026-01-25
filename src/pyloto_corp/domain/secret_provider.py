"""Protocolo de Provedor de Segredos — Injeção de Dependência.

Responsabilidades:
- Definir contrato para obter pepper_secret
- Desacoplar Application de Infra (secrets)
- Permitir injeção de mock em testes

Conforme regras_e_padroes.md (contratos, injeção de dependência).
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class SecretProvider(ABC):
    """Contrato abstrato para provisão de segredos.

    A camada Application nunca deve importar diretamente de infra.secrets.
    Sempre injetar via interface.
    """

    @abstractmethod
    def get_pepper_secret(self) -> str:
        """Retorna pepper_secret para derivação de user_key.

        Returns:
            String pepper_secret (não deve ser vazia)

        Raises:
            ValueError: Se secret não puder ser obtido
        """
        ...
