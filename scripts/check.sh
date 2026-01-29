#!/usr/bin/env bash
# Gate runner local - executa ruff + pytest + coverage
# Uso: ./scripts/check.sh

set -euo pipefail

# Detectar raiz do repo
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

echo "========================================"
echo "       PYLOTO_CORP QUALITY GATES       "
echo "========================================"
echo ""

# Gate 1: Ruff lint
echo "🔍 GATE 1/3: ruff check"
echo "----------------------------------------"
ruff check .
echo "✅ GATE 1/3: ruff check PASSED"
echo ""

# Gate 2: Pytest (rápido)
echo "🧪 GATE 2/3: pytest"
echo "----------------------------------------"
python -m pytest -q --tb=line
echo "✅ GATE 2/3: pytest PASSED"
echo ""

# Gate 3: Coverage com fail-under
echo "📊 GATE 3/3: coverage (fail-under=80%)"
echo "----------------------------------------"
python -m pytest --cov=src/pyloto_corp --cov-report=term-missing --cov-fail-under=80 -q
echo "✅ GATE 3/3: coverage PASSED"
echo ""

echo "========================================"
echo "       ✅ ALL GATES PASSED ✅           "
echo "========================================"
