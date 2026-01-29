# A4 — Flood Detection Implementation (Redis-based, multi-instance)

**Status:** ✅ COMPLETED  
**Date:** 2026-01-27  
**Objective:** Implement distributed flood detection via Redis for Cloud Run multi-instance support.

---

## 1) Overview

Implemented production-ready flood detection (rate-limiting) that:
- ✅ Detects abuse via flood (multiple messages in short time window)
- ✅ Works across multiple Cloud Run instances (Redis backend)
- ✅ Fallback-safe (dev/test uses in-memory, prod requires Redis)
- ✅ Configurable thresholds and TTL via environment variables
- ✅ Logs without PII (session_id prefix only)
- ✅ All tests passing (20/20 unit tests)
- ✅ Lint compliance (ruff 100%)

---

## 2) Deliverables

### 2.1 Environment Configuration (Settings)

**File:** [src/pyloto_corp/config/settings.py](src/pyloto_corp/config/settings.py)

Added flood detection config vars:
```python
flood_detector_backend: str = "memory"  # memory | redis
flood_threshold: int = 10  # Limit of messages per time window
flood_ttl_seconds: int = 60  # Time window in seconds
```

Also added `is_staging` property to distinguish staging from development:
```python
@property
def is_staging(self) -> bool:
    """Retorna True se ambiente é staging."""
    return self.environment.lower() in ("staging", "stage")
```

### 2.2 Factory for Flood Detector Creation

**File:** [src/pyloto_corp/infra/flood_detector_factory.py](src/pyloto_corp/infra/flood_detector_factory.py)

Two functions:
- `create_flood_detector()` — Direct instantiation with explicit params
- `create_flood_detector_from_settings()` — Convenience wrapper that reads from Settings

Key features:
- Validates that production/staging cannot use in-memory backend (Cloud Run stateless)
- Auto-creates Redis client if backend="redis" and client not provided
- Logs backend choice without PII

```python
def create_flood_detector_from_settings(
    settings: Settings, redis_client: Any | None = None
) -> FloodDetector:
    """Cria FloodDetector a partir de Settings."""
    # Validates prod/staging reject memory
    # Auto-creates Redis client if needed
    # Returns InMemoryFloodDetector or RedisFloodDetector
```

### 2.3 Integration into Application

**Files Modified:**
- [src/pyloto_corp/api/app.py](src/pyloto_corp/api/app.py) — Added flood_detector to app.state
- [src/pyloto_corp/api/dependencies.py](src/pyloto_corp/api/dependencies.py) — Added get_flood_detector() dependency
- [src/pyloto_corp/api/routes.py](src/pyloto_corp/api/routes.py) — Injected flood_detector into webhook route
- [src/pyloto_corp/application/pipeline.py](src/pyloto_corp/application/pipeline.py) — Added flood_detector parameter to process_whatsapp_webhook()

**Flow:**
```
HTTP Request → Route (get_flood_detector) → Process Webhook 
  → Create Pipeline (with flood_detector) 
  → Pipeline._is_abuse() calls check_and_record()
```

### 2.4 Unit Tests

**Files Created:**
- [tests/domain/test_flood_detector.py](tests/domain/test_flood_detector.py) — 11 tests for InMemory and Redis detectors
- [tests/infra/test_flood_detector_factory.py](tests/infra/test_flood_detector_factory.py) — 9 tests for factory logic

**Test Coverage:**

#### Domain Tests (11):
- `test_no_flood_under_threshold` — Verifies threshold logic
- `test_flood_at_threshold` — Detects flood at exact threshold
- `test_flood_multiple_sessions_isolated` — Sessions don't interfere
- `test_ttl_window_respected` — Older events expire correctly
- `test_redis_detector_creation` — Redis detector instantiation
- `test_redis_flood_detection` — Redis INCR + EXPIRE flow
- `test_redis_client_called_correctly` — Validates Redis calls
- `test_redis_error_handling` — Fail-safe (no flood) on Redis error
- `test_threshold_variations` (parametrized x2) — Different thresholds
- `test_result_structure` — FloodDetectionResult shape

#### Factory Tests (9):
- `test_create_memory_detector` — Memory backend creation
- `test_create_redis_detector` — Redis backend creation  
- `test_redis_requires_client` — ValueError if client missing
- `test_invalid_backend` — ValueError for unknown backend
- `test_dev_uses_memory_by_default` — Dev default
- `test_prod_rejects_memory` — Prod validation
- `test_staging_rejects_memory` — Staging validation
- `test_redis_with_provided_client` — Client injection
- `test_config_values_respected` — Config propagation

**Result:** 20/20 passing ✅

---

## 3) Technical Details

### 3.1 Flood Detector Implementation

**Existing Code Reused:**
- `InMemoryFloodDetector` — Already in domain, uses dict + TTL
- `RedisFloodDetector` — Already in domain, uses INCR + EXPIRE

No changes needed to domain; factory + integration handles the rest.

### 3.2 Integration Pattern

```python
# In Pipeline.__init__
def __init__(self, flood_detector: FloodDetector | None = None, ...):
    self._flood = flood_detector

# In _is_abuse()
if self._flood:
    flood_result = self._flood.check_and_record(session.session_id)
    if flood_result.is_flooded:
        return self._reject_message(...)
```

**Key:** Pipeline already had the logic; we just needed to:
1. Make flood_detector injectable (it was there but None by default)
2. Wire factory into app.state
3. Pass detector to pipeline at route time

### 3.3 Default Configuration

**Development:** 
- Backend: `memory`
- Threshold: 10 messages
- Window: 60 seconds
- ✅ Sufficient for local testing

**Production/Staging:**
- Backend: `redis` (enforced, fail-safe: raises ValueError if memory)
- Threshold: 10 messages (configurable via env)
- Window: 60 seconds (configurable via env)
- ✅ Distributed, scalable, Cloud Run compatible

---

## 4) Quality Gates

### 4.1 Linting (ruff)

```bash
✅ All checks passed!

Modified files:
- src/pyloto_corp/config/settings.py
- src/pyloto_corp/infra/flood_detector_factory.py
- src/pyloto_corp/api/app.py
- src/pyloto_corp/api/dependencies.py
- src/pyloto_corp/api/routes.py
- src/pyloto_corp/application/pipeline.py
```

### 4.2 Testing (pytest)

```bash
✅ 20 passed in 0.04s

tests/domain/test_flood_detector.py::TestInMemoryFloodDetector          (4 tests)
tests/domain/test_flood_detector.py::TestRedisFloodDetector             (4 tests)
tests/domain/test_flood_detector.py::TestFloodDetectorParametrized      (3 tests)
tests/infra/test_flood_detector_factory.py::TestCreateFloodDetector     (4 tests)
tests/infra/test_flood_detector_factory.py::TestCreateFloodDetectorFromSettings (5 tests)
```

### 4.3 App Bootstrap

```bash
✅ App created successfully
   flood_detector: <InMemoryFloodDetector object at ...>
```

---

## 5) Files Changed & Created

### Created:
- **[src/pyloto_corp/infra/flood_detector_factory.py](src/pyloto_corp/infra/flood_detector_factory.py)** (130 lines)
- **[tests/domain/test_flood_detector.py](tests/domain/test_flood_detector.py)** (220 lines)
- **[tests/infra/test_flood_detector_factory.py](tests/infra/test_flood_detector_factory.py)** (130 lines)

### Modified:
- **[src/pyloto_corp/config/settings.py](src/pyloto_corp/config/settings.py)** — Added 3 flood vars + is_staging
- **[src/pyloto_corp/api/app.py](src/pyloto_corp/api/app.py)** — Added factory call to app.state
- **[src/pyloto_corp/api/dependencies.py](src/pyloto_corp/api/dependencies.py)** — Added get_flood_detector()
- **[src/pyloto_corp/api/routes.py](src/pyloto_corp/api/routes.py)** — Added flood_detector param to route
- **[src/pyloto_corp/application/pipeline.py](src/pyloto_corp/application/pipeline.py)** — Added flood_detector to process_whatsapp_webhook()

---

## 6) Security & Compliance

### ✅ PII Protection
- Logs use session_id[:8] prefix only (no phone, email, etc.)
- Redis key uses session_id, never phone/email
- No sensitive data in error messages

### ✅ Production Ready
- Enforces Redis backend for prod/staging (Cloud Run stateless)
- Fail-safe: Redis errors return is_flooded=False (don't block)
- TTL configurable (not hardcoded)
- Thresholds tunable via env vars

### ✅ Test Coverage
- Unit tests for both backends
- Parametrized tests for threshold variations
- Redis error handling tested (mock exception)
- Session isolation verified

---

## 7) Usage Example

### Configuration (env vars)
```bash
FLOOD_DETECTOR_BACKEND=redis        # or "memory" for dev
FLOOD_THRESHOLD=10                  # messages per window
FLOOD_TTL_SECONDS=60                # window in seconds
REDIS_URL=redis://localhost:6379    # for Redis backend
ENVIRONMENT=production              # enforces Redis
```

### In Code
```python
# No changes needed — fully automatic via dependency injection

# Internally:
# 1. FastAPI route calls get_flood_detector() from dependencies
# 2. Dependencies reads app.state.flood_detector (created at boot)
# 3. Factory instantiated detector based on settings
# 4. Pipeline calls detector.check_and_record(session_id) in _is_abuse()
# 5. If flooded, outcome = DUPLICATE_OR_SPAM
```

---

## 8) Next Steps (Optional Enhancements)

- [ ] Add metrics/counters (flood events per hour, etc.)
- [ ] Per-IP rate-limiting (currently session-based only)
- [ ] Gradual backoff (increase window after N floods)
- [ ] Webhook to notify admins on sustained flood patterns

---

## 9) References

- **Specification:** [TODO_seguranca_mensagens_ia.md](TODO_seguranca_mensagens_ia.md) § 2.3 A4
- **Domain:** [src/pyloto_corp/domain/abuse_detection.py](src/pyloto_corp/domain/abuse_detection.py)
- **Architecture:** Conforme regras_e_padroes.md (factory pattern, dependency injection)
- **Testing:** pytest + ruff linting

---

## 10) Summary Table

| Item | Status | Evidence |
|------|--------|----------|
| Config vars added | ✅ | settings.py: flood_detector_backend, flood_threshold, flood_ttl_seconds |
| Factory created | ✅ | flood_detector_factory.py (130 lines, 2 functions) |
| App integration | ✅ | app.py + dependencies.py + routes.py |
| Pipeline wired | ✅ | process_whatsapp_webhook() + PipelineV2/Pipeline both accept detector |
| Unit tests | ✅ | 20/20 passing (11 domain + 9 factory) |
| Lint (ruff) | ✅ | All checks passed |
| App bootstrap | ✅ | Detector created and injected at startup |
| Security | ✅ | No PII in logs, Redis keys, error messages |
| Production ready | ✅ | Enforces Redis for prod/staging, fail-safe design |

