"""Configurações centralizadas do pyloto_corp.

Este módulo exporta:
- Settings: classe de configuração via variáveis de ambiente
- get_settings: função cacheada para obter instância única
- Constantes da Graph API Meta (GRAPH_API_VERSION, etc.)

Uso típico:
    from pyloto_corp.config import get_settings, GRAPH_API_VERSION

Conforme TODO_01_INFRAESTRUTURA_E_SERVICOS.md e regras_e_padroes.md.
"""

from pyloto_corp.config.settings import (
    GRAPH_API_BASE_URL,
    GRAPH_API_VERSION,
    GRAPH_VIDEO_BASE_URL,
    Settings,
    get_settings,
)

__all__ = [
    "Settings",
    "get_settings",
    "GRAPH_API_VERSION",
    "GRAPH_API_BASE_URL",
    "GRAPH_VIDEO_BASE_URL",
]
