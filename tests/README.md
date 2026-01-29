# Testes — pyloto_corp

Documentação das suites de testes, fixtures e convenções.

> **Política de qualidade:** ver [docs/governanca_qualidade.md](../docs/governanca_qualidade.md)

## Estrutura

```
tests/
├── adapters/
│   └── whatsapp/
│       ├── test_message_builder.py    # Payloads, truncation, PII sanitization
│       └── test_normalizer_all_types.py  # Normalizer com fixtures parametrizadas
├── domain/
│   └── test_flood_detector.py         # Flood/abuse detection
├── integration/
│   ├── test_webhook_security.py       # Assinatura, verify token, JSON
│   ├── test_webhook_smoke.py          # Smoke test básico
│   ├── test_firestore_*.py            # Persistência Firestore
│   └── test_export_integration.py     # Export de histórico
├── unit/
│   ├── test_whatsapp_http_client.py   # HTTP client com mocks
│   ├── test_export.py                 # Export use case
│   ├── test_flow_sender.py            # Flow crypto AES-GCM
│   └── ...
├── fixtures/
│   └── whatsapp/
│       ├── webhook/                   # 17 fixtures de webhook sanitizadas
│       │   ├── text.single.json
│       │   ├── image.json
│       │   ├── video.json
│       │   ├── audio.json
│       │   ├── document.json
│       │   ├── sticker.json
│       │   ├── location.json
│       │   ├── contacts.json
│       │   ├── interactive.button_reply.json
│       │   ├── interactive.list_reply.json
│       │   ├── reaction.json
│       │   ├── status.delivered.json
│       │   ├── status.read.json
│       │   ├── status.sent.json
│       │   ├── status.failed.json
│       │   └── unknown_type.json
│       └── graph_responses/           # 8 fixtures de Graph API
│           ├── send_text_success.json
│           └── ...
├── conftest.py                        # Fixtures globais
└── test_llm_pipeline_e2e.py           # E2E pipeline com 3 LLM points
```

## Rodar Testes

### Suite completa
```bash
pytest
```

### Com verbose
```bash
pytest -v
```

### Arquivo específico
```bash
pytest tests/integration/test_webhook_security.py -v
```

### Com cobertura
```bash
pytest --cov=src/pyloto_corp --cov-report=html
```

### Apenas fast (sem integration)
```bash
pytest -m "not integration"
```

## Fixtures Sanitizadas

Todas as fixtures em `tests/fixtures/whatsapp/webhook/` foram sanitizadas:
- IDs reais substituídos por `*_TEST` ou strings determinísticas
- Números de telefone substituídos por padrões fake
- Timestamps mantidos mas epoch fixo
- Estrutura preservada para validação

### Usar fixtures em testes

```python
from pathlib import Path
import json

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "whatsapp" / "webhook"

def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / f"{name}.json").read_text())

def test_something():
    payload = _load_fixture("text.single")
    # usar payload...
```

## Convenções

### Nomenclatura
- `test_*.py` — arquivos de teste
- `Test*` — classes de teste
- `test_*` — métodos de teste
- Nomes descritivos: `test_empty_text_raises_error`

### Organização por camada
- `unit/` — testes isolados, sem IO
- `integration/` — testes com Firestore/HTTP mockados
- `adapters/` — testes de adapters (WhatsApp, etc.)
- `domain/` — testes de regras de domínio

### Mocking
- Preferir `unittest.mock.MagicMock` para objetos
- `unittest.mock.patch` para substituir módulos
- `pytest.MonkeyPatch` para variáveis de ambiente

### Asserts
- Um assert principal por teste quando possível
- Usar `pytest.raises` para exceções esperadas
- Mensagens de match para exceções: `match="cannot be empty"`

## Gates de Qualidade (antes de commit)

**Recomendado:** rodar o script de gates antes de commit:
```bash
./scripts/check.sh
```

Este script executa ruff + pytest + coverage em sequência.

---

## Gates de Qualidade (manual)

Antes de commit:
```bash
# Lint
ruff check .

# Testes
pytest

# Cobertura mínima (se exigida)
pytest --cov=src/pyloto_corp --cov-report=term-missing --cov-fail-under=80
```

## Fixtures Globais (conftest.py)

```python
@pytest.fixture()
def client(monkeypatch):
    """Cliente de teste FastAPI."""
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "test-token")
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as c:
        yield c
```

## Suítes Parametrizadas

Para testar múltiplos cenários com mesma lógica:

```python
@pytest.mark.parametrize("fixture_name", ["text.single", "image", "video"])
def test_fixture_extracts(fixture_name: str):
    payload = _load_fixture(fixture_name)
    messages = extract_messages(payload)
    assert isinstance(messages, list)
```

## Baseline de Cobertura

Cobertura registrada em [docs/coverage_baseline.md](../docs/coverage_baseline.md).

Baseline atual: **84%** (2026-01-27)

## Contribuindo

1. Novos testes devem seguir estrutura existente
2. Fixtures novas devem ser sanitizadas (sem PII)
3. Rodar `ruff check` antes de commit
4. Testes devem passar em < 10s (exceto integration)
