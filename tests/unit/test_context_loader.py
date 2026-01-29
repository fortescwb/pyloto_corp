"""Testes unitários para InstitucionalContextLoader.

Valida que o cache interno funciona corretamente e é determinístico.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from pyloto_corp.ai.context_loader import (
    InstitucionalContextLoader,
    get_context_loader,
)


class TestContextLoaderCacheInternals:
    """Testes para validar que o cache interno evita re-leitura de arquivos."""

    def test_cache_evita_re_leitura(self) -> None:
        """Cache interno deve evitar leitura repetida do mesmo arquivo.
        
        Chama load_contexto_llm() duas vezes e valida que Path.read_text()
        é chamado apenas uma vez.
        """
        loader = InstitucionalContextLoader()
        
        # Mock do Path.read_text para capturar chamadas
        mock_read = MagicMock(return_value="# Conteúdo de teste LLM")
        
        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", mock_read),
        ):
            # Primeira chamada - deve ler do "arquivo"
            result1 = loader.load_contexto_llm()
            
            # Segunda chamada - deve usar cache interno
            result2 = loader.load_contexto_llm()
        
        # Assert: read_text chamado apenas 1 vez (cache funcionou)
        assert mock_read.call_count == 1, (
            f"read_text deveria ser chamado 1x, foi chamado {mock_read.call_count}x"
        )
        
        # Assert: retorno idêntico
        assert result1 == result2
        assert result1 == "# Conteúdo de teste LLM"

    def test_cache_deterministic_sem_dados_variaveis(self) -> None:
        """Cache deve retornar conteúdo determinístico sem dados variáveis.
        
        Valida que múltiplas chamadas retornam o mesmo conteúdo e que
        o cache não inclui timestamps, request IDs ou outros dados variáveis.
        """
        loader = InstitucionalContextLoader()
        
        # Conteúdos fixos de teste (sem PII, sem dados variáveis)
        vertentes_content = "# Vertentes da Pyloto\n- Sistemas\n- SaaS\n- Entrega"
        visao_content = "# Visão e Princípios\nZero-trust. Clareza."
        llm_content = "# Contexto LLM\nIntents e responses canônicas."
        
        def mock_read_text(self, encoding=None):
            """Mock que retorna conteúdo baseado no path."""
            path_str = str(self)
            if "vertentes" in path_str:
                return vertentes_content
            elif "visao" in path_str:
                return visao_content
            elif "contexto_llm" in path_str or "doc.md" in path_str:
                return llm_content
            return "# Default"
        
        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", mock_read_text),
        ):
            # Carregar cada tipo 3 vezes
            results_vertentes = [loader.load_vertentes() for _ in range(3)]
            results_visao = [loader.load_visao_principios() for _ in range(3)]
            results_llm = [loader.load_contexto_llm() for _ in range(3)]
        
        # Assert: todos os resultados são idênticos (determinísticos)
        assert all(r == vertentes_content for r in results_vertentes)
        assert all(r == visao_content for r in results_visao)
        assert all(r == llm_content for r in results_llm)
        
        # Assert: conteúdo não contém dados variáveis típicos
        all_content = "\n".join(results_vertentes + results_visao + results_llm)
        assert "timestamp" not in all_content.lower()
        assert "request_id" not in all_content.lower()
        assert "correlation" not in all_content.lower()


class TestGetContextLoaderSingleton:
    """Testes para validar que get_context_loader() retorna singleton."""

    def test_singleton_retorna_mesma_instancia(self) -> None:
        """get_context_loader() deve retornar a mesma instância sempre."""
        # Nota: em produção isso é garantido pelo padrão Singleton
        # mas como há estado global, testar isoladamente pode ser frágil.
        # Este teste valida a semântica esperada.
        
        loader1 = get_context_loader()
        loader2 = get_context_loader()
        
        # Assert: mesma instância (singleton)
        assert loader1 is loader2
