"""Carregador de contexto institucional (visão, vertentes, intents, prompts).

Injeta conhecimento Pyloto nos prompts da LLM para respostas context-aware.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pyloto_corp.observability.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Vertente:
    """Uma vertente de negócio da Pyloto."""

    name: str
    description: str
    key_keywords: list[str]
    examples: list[str]
    constraints: list[str]  # O que NÃO fazer nesta vertente
    canonical_responses: dict[str, str]  # intent → resposta padrão


@dataclass
class Intent:
    """Um intent mapeado no contexto LLM."""

    category: str  # Ex: ENTREGAS, SERVICOS, TECNOLOGIA
    name: str
    triggers: list[str]  # Palavras-chave que disparam este intent
    description: str
    canonical_response: str
    requires_escalation: bool = False
    requires_human: bool = False


class InstitutionalContextLoader:
    """Carregador e gerenciador de contexto institucional."""

    def __init__(self, docs_path: Path | None = None) -> None:
        """Inicializa loader.

        Args:
            docs_path: Caminho para pasta docs/institucional. Se None, auto-detect.
        """
        if docs_path is None:
            # Auto-detect relative to this file
            current_dir = Path(__file__).parent.parent.parent.parent
            docs_path = current_dir / "docs" / "institucional"

        self.docs_path = docs_path
        self.vertentes: dict[str, Vertente] = {}
        self.intents: dict[str, Intent] = {}
        self.visao: str = ""
        self.constraints: list[str] = []

    async def load(self) -> bool:
        """Carrega todos os arquivos institucionais.

        Returns:
            True se carregado com sucesso, False caso contrário.
        """
        try:
            # Carregar visão
            visao_file = self.docs_path / "visao_principios-e-posicionamento.md"
            if visao_file.exists():
                self.visao = visao_file.read_text(encoding="utf-8")
                logger.info(
                    "loaded_visao",
                    extra={
                        "file": str(visao_file),
                        "lines": len(self.visao.split("\n")),
                    },
                )
            else:
                logger.warning(
                    "visao_file_not_found",
                    extra={"path": str(visao_file)},
                )

            # Carregar vertentes
            vertentes_file = self.docs_path / "vertentes.md"
            if vertentes_file.exists():
                self._load_vertentes(vertentes_file)
            else:
                logger.warning(
                    "vertentes_file_not_found",
                    extra={"path": str(vertentes_file)},
                )

            # Carregar contexto LLM (intents, taxonomia, respostas canônicas)
            llm_file = self.docs_path / "contexto_llm" / "doc.md"
            if llm_file.exists():
                self._load_llm_context(llm_file)
            else:
                logger.warning(
                    "llm_context_file_not_found",
                    extra={"path": str(llm_file)},
                )

            logger.info(
                "institutional_context_loaded",
                extra={
                    "vertentes_count": len(self.vertentes),
                    "intents_count": len(self.intents),
                    "constraints_count": len(self.constraints),
                },
            )
            return True

        except Exception as e:
            logger.error(
                "failed_to_load_institutional_context",
                extra={"error": str(e)},
                exc_info=True,
            )
            return False

    def _load_vertentes(self, vertentes_file: Path) -> None:
        """Parse arquivo vertentes.md e popula self.vertentes."""
        content = vertentes_file.read_text(encoding="utf-8")

        # Simples parser: cada vertente começa com ##
        vertente_blocks = content.split("\n##")

        for block in vertente_blocks[1:]:  # Skip header
            lines = block.strip().split("\n")
            if not lines:
                continue

            # Primeira linha é o nome
            name = lines[0].strip()

            # Encontrar descrição (até próxima seção ou EOF)
            description_lines = []
            for line in lines[1:]:
                if line.startswith("###"):
                    break
                description_lines.append(line)

            description = "\n".join(description_lines).strip()

            # Extrair keywords e constraints
            keywords = []
            constraints = []
            examples = []

            for line in lines[1:]:
                line = line.strip()
                if "NÃO fazer" in line or "não fazer" in line or "Constraint" in line:
                    constraints.append(line)
                elif line.startswith("- "):
                    if "constraint" in line.lower() or "proibido" in line.lower():
                        constraints.append(line)
                    else:
                        examples.append(line.replace("- ", ""))
                elif line and not line.startswith("#") and len(line) < 50:
                    keywords.extend(line.split(", "))

            vertente = Vertente(
                name=name,
                description=description,
                key_keywords=keywords[:10],  # Limitar a 10
                examples=examples[:5],  # Limitar a 5
                constraints=constraints,
                canonical_responses={},
            )
            self.vertentes[name.lower()] = vertente

    def _load_llm_context(self, llm_file: Path) -> None:
        """Parse arquivo contexto_llm/doc.md e popula self.intents e self.constraints."""
        content = llm_file.read_text(encoding="utf-8")

        # Extrair constraints globais (linhas com **Constraint** ou similar)
        for line in content.split("\n"):
            line = line.strip()
            if (
                "constraint" in line.lower() or "never" in line.lower()
            ) and line not in self.constraints:
                self.constraints.append(line)

        # Simples parser: procurar por patterns de intents
        lines = content.split("\n")
        current_category = None
        current_intent = None
        current_intent_data: dict[str, Any] = {}

        categories = {
            "ENTREGAS",
            "SERVICOS",
            "TECNOLOGIA",
            "CRM",
            "IA",
            "COMERCIAL",
            "SUPORTE",
            "LEGAL",
        }

        for line in lines:
            line = line.strip()

            # Detectar categoria (ENTREGAS, SERVICOS, etc)
            if line.startswith("##") and any(cat in line for cat in categories):
                current_category = line.replace("##", "").strip()

            # Detectar intent (###)
            elif line.startswith("###"):
                if current_intent and current_intent_data:
                    intent = Intent(
                        category=current_category or "UNKNOWN",
                        name=current_intent,
                        triggers=current_intent_data.get("triggers", []),
                        description=current_intent_data.get("description", ""),
                        canonical_response=current_intent_data.get("response", ""),
                        requires_escalation=current_intent_data.get("escalate", False),
                    )
                    self.intents[
                        f"{current_category}:{current_intent}".lower()
                    ] = intent

                current_intent = line.replace("###", "").strip()
                current_intent_data = {}

            # Parse fields dentro de um intent
            elif "trigger:" in line.lower():
                current_intent_data["triggers"] = [
                    t.strip() for t in line.split(":", 1)[1].split(",")
                ]
            elif "response:" in line.lower() or "canonical" in line.lower():
                current_intent_data["response"] = line.split(":", 1)[1].strip()
            elif "escalat" in line.lower():
                current_intent_data["escalate"] = True

    def get_prompt_context(self) -> str:
        """Gera string de contexto para injetar no prompt da LLM.

        Returns:
            String com visão, vertentes e constraints.
        """
        parts = [
            "# Contexto Institucional Pyloto",
            "",
            "## Visão e Princípios",
            self.visao[:500] + "..." if len(self.visao) > 500 else self.visao,
            "",
            "## Vertentes de Negócio",
        ]

        for _name, vertente in self.vertentes.items():
            parts.append(f"\n### {vertente.name}")
            parts.append(vertente.description[:200])

        parts.append("\n## Constraints Obrigatórios")
        for constraint in self.constraints[:10]:
            parts.append(f"- {constraint}")

        return "\n".join(parts)

    def get_vertente(self, name: str) -> Vertente | None:
        """Retorna uma vertente pelo nome."""
        return self.vertentes.get(name.lower())

    def get_intent(self, category: str, intent_name: str) -> Intent | None:
        """Retorna um intent específico."""
        key = f"{category}:{intent_name}".lower()
        return self.intents.get(key)

    def detect_intent_from_text(self, text: str) -> Intent | None:
        """Tenta detectar intent pelo texto da mensagem.

        Args:
            text: Mensagem do usuário

        Returns:
            Intent detectado ou None
        """
        text_lower = text.lower()

        # Procura por triggers
        for intent in self.intents.values():
            for trigger in intent.triggers:
                if trigger.lower() in text_lower:
                    return intent

        return None

    def get_all_constraints(self) -> list[str]:
        """Retorna lista de constraints globais."""
        return self.constraints.copy()
