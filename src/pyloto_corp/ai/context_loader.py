"""Carregador de contexto institucional para prompts da IA.

Fornece contexto sobre a Pyloto, suas vertentes, princípios e responses
canônicas que devem orientar as respostas da LLM.

Este módulo garante que a IA tenha acesso ao conhecimento correto sobre
a empresa e respeite os limites de escopo definidos em docs/institucional/.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from pyloto_corp.observability.logging import get_logger

logger: logging.Logger = get_logger(__name__)


class InstitucionalContextLoader:
    """Carregador de contexto institucional da Pyloto.
    
    Responsabilidades:
    - Carregar documentos de contexto (vertentes, princípios, intents)
    - Formatar como system prompt para LLM
    - Garantir que contexto está atualizado
    """

    def __init__(self) -> None:
        """Inicializa o loader com caminhos dos documentos."""
        self._docs_dir = Path(__file__).parent.parent.parent.parent / "docs" / "institucional"
        self._cached_context: dict[str, str] = {}

    @lru_cache(maxsize=1)
    def load_vertentes(self) -> str:
        """Carrega documento de vertentes (estrutura do ecossistema).
        
        Returns:
            Conteúdo do arquivo vertentes.md como string.
            
        Raises:
            FileNotFoundError: Se arquivo não existir.
        """
        vertentes_path = self._docs_dir / "vertentes.md"
        if not vertentes_path.exists():
            msg = f"Arquivo de vertentes não encontrado: {vertentes_path}"
            logger.error(msg)
            raise FileNotFoundError(msg)
        
        try:
            content = vertentes_path.read_text(encoding="utf-8")
            logger.debug("Vertentes carregadas com sucesso")
            return content
        except Exception as e:
            logger.error(f"Erro ao carregar vertentes: {e}", exc_info=True)
            raise

    @lru_cache(maxsize=1)
    def load_visao_principios(self) -> str:
        """Carrega documento de visão e princípios.
        
        Returns:
            Conteúdo do arquivo visao_principios-e-posicionamento.md como string.
            
        Raises:
            FileNotFoundError: Se arquivo não existir.
        """
        visao_path = self._docs_dir / "visao_principios-e-posicionamento.md"
        if not visao_path.exists():
            msg = f"Arquivo de visão/princípios não encontrado: {visao_path}"
            logger.error(msg)
            raise FileNotFoundError(msg)
        
        try:
            content = visao_path.read_text(encoding="utf-8")
            logger.debug("Visão e princípios carregados com sucesso")
            return content
        except Exception as e:
            logger.error(f"Erro ao carregar visão/princípios: {e}", exc_info=True)
            raise

    @lru_cache(maxsize=1)
    def load_contexto_llm(self) -> str:
        """Carrega documento de contexto LLM (taxonomy, intents, responses).
        
        Returns:
            Conteúdo do arquivo contexto_llm/doc.md como string.
            
        Raises:
            FileNotFoundError: Se arquivo não existir.
        """
        contexto_path = self._docs_dir / "contexto_llm" / "doc.md"
        if not contexto_path.exists():
            msg = f"Arquivo de contexto LLM não encontrado: {contexto_path}"
            logger.error(msg)
            raise FileNotFoundError(msg)
        
        try:
            content = contexto_path.read_text(encoding="utf-8")
            logger.debug("Contexto LLM carregado com sucesso")
            return content
        except Exception as e:
            logger.error(f"Erro ao carregar contexto LLM: {e}", exc_info=True)
            raise

    def get_system_prompt_context(self) -> str:
        """Retorna contexto formatado para usar em system prompt.
        
        Combina todos os documentos institucionais em um único texto
        pronto para ser incluído no system prompt da LLM.
        
        Returns:
            String formatada com todo contexto institucional.
            Estrutura: vertentes + princípios + taxonomy/intents
        """
        try:
            parts = [
                "# CONTEXTO INSTITUCIONAL DA PYLOTO",
                "## VERSÃO 1 - 26 de Janeiro de 2026",
                "",
                "Este contexto define a identidade, princípios e modo de operação da Pyloto.",
                "Todas as respostas devem estar alinhadas com este contexto.",
                "",
                "---",
                "",
                "## SEÇÃO 1: PRINCÍPIOS E VISÃO",
                "",
                self.load_visao_principios(),
                "",
                "---",
                "",
                "## SEÇÃO 2: ESTRUTURA DO ECOSSISTEMA (VERTENTES)",
                "",
                self.load_vertentes(),
                "",
                "---",
                "",
                "## SEÇÃO 3: TAXONOMY, INTENTS E RESPOSTAS CANÔNICAS",
                "",
                self.load_contexto_llm(),
                "",
            ]
            
            context = "\n".join(parts)
            logger.debug(f"System prompt context gerado com sucesso ({len(context)} caracteres)")
            return context
        except Exception as e:
            logger.error(f"Erro ao gerar system prompt context: {e}", exc_info=True)
            raise

    def get_resposta_canonica(self, intent_id: str) -> str | None:
        """Busca resposta canônica para um intent específico.
        
        Extrai a resposta canônica documentada para um dado intent
        a partir do arquivo de contexto LLM.
        
        Args:
            intent_id: Identificador do intent (ex: "O_QUE_E_PYLOTO")
            
        Returns:
            Resposta canônica como string, ou None se intent não encontrado.
            Nota: Esta é uma busca simples baseada em padrão de texto.
        """
        try:
            contexto = self.load_contexto_llm()
            # Busca padrão: "### INTENT: `{intent_id}`"
            pattern = f'### INTENT: `{intent_id}`'
            if pattern in contexto:
                # Extrai bloco de resposta canônica após o padrão
                start_idx = contexto.find(pattern)
                # Procura por "**Resposta Canônica**" após o intent
                resposta_marker = "**Resposta Canônica**"
                resposta_start = contexto.find(resposta_marker, start_idx)
                if resposta_start > 0:
                    # Captura texto após o marcador até próximo "###" ou EOF
                    content_start = resposta_start + len(resposta_marker)
                    next_section = contexto.find("\n###", content_start)
                    if next_section < 0:
                        next_section = len(contexto)
                    
                    resposta = contexto[content_start:next_section].strip()
                    # Remove marcação de bloco quote se presente
                    if resposta.startswith("> "):
                        resposta = resposta[2:].strip()
                    
                    logger.debug(f"Resposta canônica encontrada para intent: {intent_id}")
                    return resposta
            
            logger.debug(f"Resposta canônica não encontrada para intent: {intent_id}")
            return None
        except Exception as e:
            logger.error(f"Erro ao buscar resposta canônica para {intent_id}: {e}")
            return None


# Instância global do loader (lazy init para evitar erro se docs não existem)
_loader_instance: InstitucionalContextLoader | None = None


def get_context_loader() -> InstitucionalContextLoader:
    """Retorna instância global do loader de contexto.
    
    Implementa padrão Singleton lazy para garantir que o loader
    é inicializado apenas uma vez e reutilizado.
    """
    global _loader_instance
    if _loader_instance is None:
        _loader_instance = InstitucionalContextLoader()
    return _loader_instance


def get_system_prompt_context() -> str:
    """Função de conveniência para obter system prompt com contexto.
    
    Returns:
        String formatada com contexto institucional pronto para usar em prompts.
    """
    loader = get_context_loader()
    return loader.get_system_prompt_context()
