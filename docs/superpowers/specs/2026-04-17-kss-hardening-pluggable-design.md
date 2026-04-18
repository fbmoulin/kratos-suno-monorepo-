# Track A — Hardening Pluggable (Stage 1 → 4)

**Spec ID:** `2026-04-17-kss-hardening-pluggable`
**Author:** Felipe Moulin
**Status:** Draft (pending spec-reviewer)
**Related:** project `kratos-suno-prompt` v0.1.0, track C (prompt quality) em spec separada

---

## 1. Objetivo

Tornar o backend do `kratos-suno-prompt` seguro para exposição pessoal (ngrok) no
**estágio 1**, com abstrações pluggáveis que permitam escalar até **estágio 4** (B2B
com API-key) sem reescrever código de domínio, apenas trocando implementações via
configuração.

### Critérios de sucesso

| # | Critério | Verificação |
|---|---|---|
| C1 | Nenhum cenário conhecido vaza nome próprio no prompt final (text OU audio) | Teste E2E com hint malicioso |
| C2 | Uso externo não consome mais que `DAILY_BUDGET_USD` de Anthropic/dia | Budget tracker in-memory com cap |
| C3 | Event loop não bloqueia durante análise de áudio (>=2 users concorrentes) | Benchmark: 2 requests audio em paralelo terminam em ~tempo de 1 |
| C4 | Transição 1→2 é **só config** (switch rate-limit backend memory→redis) | Feature flag em `config.py`; nenhum código de domínio tocado |
| C5 | Transição 2→3 é **adicionar 1 classe** (`ClerkAuthProvider`) + feature flag | Interface `AuthProvider` estável |
| C6 | Transição 3→4 é **adicionar 1 classe** (`ApiKeyAuthProvider`) + rota scope | Interface `AuthProvider` estável |

## 2. Escopo

### In-scope

- Estágio 1 completo e pronto para ngrok (rate-limit in-memory, sem auth, budget cap global)
- Abstrações (`AuthProvider`, `RateLimiter`, `BudgetTracker`) com interfaces estáveis para estágios 2-4
- Fix do async bloqueante no pipeline de áudio (`librosa` via `asyncio.to_thread`)
- Fix da brecha de compliance no fluxo de áudio (extração heurística de `forbidden_terms` + campo opcional no schema)
- Observabilidade end-to-end: `structlog` no backend + `ESLint strict+a11y` + `logger.ts` com `sendBeacon` no frontend + rota `/api/v1/client-errors` que re-emite frontend errors no mesmo stream JSON
- Testes novos: ~45 casos cobrindo infra + extractors + endpoints

### Out-of-scope (outras specs)

- Redis como backend de rate-limit/budget (spec "estágio 2")
- Auth real via Clerk/BetterAuth (spec "estágio 3")
- API-key management UI (spec "estágio 4")
- Cache de DNAs no Postgres (Fase 3 do roadmap do projeto, spec separada)
- Migração Next.js/Vercel (não planejada)
- Integração com Suno API não-oficial (Fase 4 do roadmap)
- Avaliação e evolução de prompts v1→v2→v3 (track C, spec separada)

## 3. Arquitetura

Nova estrutura de diretório `backend/app/infra/` centraliza cross-cutting concerns:

```
backend/app/
├── infra/                              ← NOVO: cross-cutting, pluggável
│   ├── __init__.py
│   ├── auth.py                         ← AuthProvider (Protocol) + NoAuthProvider
│   ├── rate_limit.py                   ← RateLimiter (Protocol) + InMemoryRateLimiter
│   ├── budget.py                       ← BudgetTracker (Protocol) + InMemoryBudgetTracker
│   ├── logging.py                      ← setup_logging() + request-id middleware
│   └── compliance.py                   ← extract_forbidden_terms_from_hint()
├── api/v1/
│   ├── generate_text.py                ← + Depends(require_auth, rate_limit, check_budget)
│   ├── generate_audio.py               ← + asyncio.to_thread + extract_forbidden_terms
│   └── client_errors.py                ← NOVO: POST /client-errors (beacon receiver)
├── main.py                             ← setup_logging(app), setup_rate_limit(app),
                                            setup_budget(app), setup_auth(app)
frontend/
├── eslint.config.js                    ← NOVO: flat config strict+a11y+import-sort
├── .prettierrc                         ← NOVO
├── src/
│   ├── lib/logger.ts                   ← NOVO: sendBeacon batch logger
│   └── main.tsx                        ← installBrowserErrorCapture(logger)
```

### Protocolos (estáveis estágios 1→4)

```python
# infra/auth.py
from pydantic import BaseModel, Field

class AuthContext(BaseModel):
    subject_id: str                     # "ip:<hash>" | "user:<id>" | "apikey:<hash>"
    plan: Literal["anon", "free", "pro", "b2b"] = "anon"
    scope: set[str] = Field(default_factory=set)

class AuthProvider(Protocol):
    async def authenticate(self, request: Request) -> AuthContext:
        """Nunca retorna None; lança HTTPException(401) se inválido."""

# Stage 1
class NoAuthProvider:
    async def authenticate(self, request: Request) -> AuthContext:
        ip = request.client.host if request.client else "unknown"
        return AuthContext(subject_id=f"ip:{sha256(ip.encode()).hexdigest()[:16]}")
```

```python
# infra/rate_limit.py
class RateLimitResult(BaseModel):
    allowed: bool
    retry_after_seconds: int | None = None
    remaining: int

class RateLimiter(Protocol):
    async def check(self, subject_id: str, cost: int = 1) -> RateLimitResult: ...

# Stage 1
class InMemoryRateLimiter:
    """Sliding window com collections.deque por subject_id."""
    def __init__(self, max_per_hour: int = 20): ...
```

```python
# infra/budget.py
class BudgetTracker(Protocol):
    async def can_spend(self, amount_usd: float) -> bool: ...
    async def record(self, amount_usd: float, subject_id: str) -> None: ...

# Stage 1
class InMemoryBudgetTracker:
    """Contador atômico com asyncio.Lock, reset diário UTC."""
    def __init__(self, daily_cap_usd: float = 2.0): ...
```

### Config expande (`app/config.py`)

```python
# Pluggable backends
auth_provider: Literal["none", "clerk", "api_key"] = "none"
rate_limit_backend: Literal["memory", "redis"] = "memory"
budget_backend: Literal["memory", "redis", "postgres"] = "memory"

# Limits
rate_limit_per_hour: int = 20
daily_budget_usd: float = 2.0
cost_per_text_generation_usd: float = 0.002
cost_per_audio_generation_usd: float = 0.01

# Observability
log_format: Literal["json", "console"] = "console"  # json em prod
```

### Factories (`app/infra/__init__.py`)

```python
@lru_cache
def get_auth_provider() -> AuthProvider:
    match settings.auth_provider:
        case "none":     return NoAuthProvider()
        case "clerk":    raise NotImplementedError("stage 3")
        case "api_key":  raise NotImplementedError("stage 4")

@lru_cache
def get_rate_limiter() -> RateLimiter:
    match settings.rate_limit_backend:
        case "memory":   return InMemoryRateLimiter(settings.rate_limit_per_hour)
        case "redis":    raise NotImplementedError("stage 2")

@lru_cache
def get_budget_tracker() -> BudgetTracker:
    match settings.budget_backend:
        case "memory":   return InMemoryBudgetTracker(settings.daily_budget_usd)
        case "redis":    raise NotImplementedError("stage 2")
        case "postgres": raise NotImplementedError("stage 3")
```

### Merge-safety pattern para parallel agents

Cada módulo cross-cutting exporta `setup_X(app: FastAPI)` que registra seu middleware/handler. `main.py` chama cada um em uma linha separada — **zero conflito** ao mergear PRs paralelos:

```python
from app.infra.logging import setup_logging
from app.infra.rate_limit import setup_rate_limit
from app.infra.budget import setup_budget
from app.infra.auth import setup_auth

app = FastAPI(...)

setup_logging(app)          # agent A4
setup_rate_limit(app)       # agent A2
setup_budget(app)           # agent A3
setup_auth(app)             # agent A1

app.include_router(generate_text.router, prefix="/api/v1")
app.include_router(generate_audio.router, prefix="/api/v1")
app.include_router(client_errors.router, prefix="/api/v1")
```

## 4. Componentes — atribuição de agents paralelos

Cada agent opera em arquivos disjuntos; conflitos de merge só em `main.py`
(resolvidos pela regra "uma linha `setup_X(app)` por agent") e `config.py`
(bloco comentado por agent).

| # | Agent | Arquivos owned | Stage-1 delivery |
|---|---|---|---|
| **A1** | agent-auth | `infra/auth.py`, `infra/factories.py` (só função `_build_auth_provider`) | `NoAuthProvider` + `require_auth` Depends + setup registra dependency |
| **A2** | agent-rate-limit | `infra/rate_limit.py`, `infra/factories.py` (só função `_build_rate_limiter`) | `InMemoryRateLimiter` sliding window (deque+TTL) + `rate_limit` Depends + `setup_rate_limit(app)` |
| **A3** | agent-budget | `infra/budget.py`, `infra/factories.py` (só função `_build_budget_tracker`) | `InMemoryBudgetTracker` atômico + daily reset + `check_budget` Depends + `record_spend()` helper para rotas |
| **A4** | agent-observability | `infra/logging.py`, `infra/__init__.py` (composição pública `get_auth_provider/get_rate_limiter/get_budget_tracker` importando de factories.py), `infra/factories.py` (esqueleto do arquivo + match inicial), `api/v1/client_errors.py`, `main.py` (setup + global exception handler + `setup_X(app)` lines), `config.py` (owner único, com blocos comentados recebidos em PR de A1/A2/A3/A5), `requirements.txt` (structlog) | structlog JSON + ConsoleRenderer + request-id middleware + exception handler global + rota `/client-errors` com dedup+rate-limit reusando A2 |
| **A5** | agent-compliance-audio | `infra/compliance.py`, `schemas/sonic_dna.py` (GenerateFromAudioRequest), `services/dna_audio_extractor.py`, `api/v1/generate_audio.py`, `frontend/src/components/AudioUpload.tsx` | `extract_forbidden_terms_from_hint(hint, artist_to_avoid)` heurístico + injeta em `dna.forbidden_terms` antes de `compress_all` + campo opcional no form |
| **A6** | agent-async-audio | `services/audio_analyzer.py`, `services/dna_audio_extractor.py` | Refactor: `_extract_sync` interno + `extract_async` com `await asyncio.to_thread(self._extract_sync, ...)`. Idem `generate_spectrogram_png` |
| **A7** | agent-tests | `tests/conftest.py` (fixtures), `tests/test_text_extractor.py`, `tests/test_audio_extractor.py`, `tests/test_endpoints.py`, `tests/test_infra_*.py`, `tests/test_client_errors_endpoint.py` | ~45 novos testes. Fixtures: `mock_anthropic_response`, `synthetic_wav_60s`, `test_client_no_auth`, `reset_infra_state` (autouse) |
| **A8** | agent-frontend-quality | `frontend/eslint.config.js`, `frontend/.prettierrc`, `frontend/package.json` (devDeps), `frontend/src/lib/logger.ts`, `frontend/src/main.tsx` (install logger) | ESLint flat strict+a11y+simple-import-sort + Prettier + `logger.ts` com `sendBeacon` batch ≤10 + auto-capture (window.onerror, unhandledrejection, console.error, fetch slow >5s) + install no `main.tsx` |

### Ordem de merge sugerida

1. **A4 primeiro** — todos os outros logam estruturado, fica consistente. A4 cria `infra/__init__.py`, `infra/factories.py` (esqueleto), `config.py` expandido
2. **A1, A2, A3, A5, A6, A8 em paralelo** — arquivos disjuntos. A1/A2/A3 contribuem com função `_build_*` em `infra/factories.py` via rebase sequencial (coordenado por A7 antes de integrar)
3. **A7 por último** — tests validam estado final integrado. A7 também é responsável por rodar o rebase final que agrega as funções `_build_*` em `factories.py` se houver conflito de merge

## 5. Fluxo de request

### `POST /api/v1/generate/text`

```
Cliente
  │  POST /api/v1/generate/text  { "subject": "Coldplay" }
  ▼
[1] CORSMiddleware (já existe)
  ▼
[2] RequestIdMiddleware (A4)
    - uuid4() se ausente; injeta contextvars; log entrada
  ▼
[3] Depends(require_auth) → AuthProvider.authenticate()
    - stage 1: AuthContext(subject_id=f"ip:{sha256(ip)[:16]}")
  ▼
[4] Depends(rate_limit) → RateLimiter.check(subject_id, cost=1)
    - stage 1: sliding window deque; limite 20/h
    - fail → 429 + Retry-After
  ▼
[5] Depends(check_budget) → BudgetTracker.can_spend(cost_per_text_generation_usd)
    - fail → 402
  ▼
[6] Handler generate_from_text
    a. dna = await extractor.extract(subject)
    b. variants = compress_all(dna)
    c. await budget_tracker.record(cost, subject_id)
    d. log saída: latency_ms, variant_count, subject_hash
    e. return GenerateResponse
  ▼
Cliente (200 OK | 4xx/5xx JSON padronizado)
```

### `POST /api/v1/generate/audio`

Idêntico, com diferenças:

- **Cost**: `cost_per_audio_generation_usd` (≈5x text)
- **[6a-pré]** `dna.forbidden_terms = extract_forbidden_terms_from_hint(user_hint, artist_to_avoid)` **antes** de `compress_all`
- **[6a]** Pipeline híbrido: `features = await asyncio.to_thread(feature_extractor.extract, audio_io)` e `spectrogram_bytes = await asyncio.to_thread(generate_spectrogram_png, audio_io)` — **não bloqueia event loop**

### `POST /api/v1/client-errors` (novo)

```
Browser logger.ts (batch ≤10 erros + warnings)
  │  navigator.sendBeacon(payload)
  ▼
[1] CORSMiddleware
  ▼
[2] RequestIdMiddleware
  ▼
[3] Depends(rate_limit) — reusa A2 com limite separado (p.ex. 60/h por IP)
  ▼
[4] Handler
    - valida shape (pydantic: list[ClientErrorEvent] max 10)
    - dedup: hash do (message, stack[:200]) por request; skip duplicatas
    - para cada evento: logger.error(event, logger="frontend", request_id=..., url=..., user_agent=...)
    - return 204 No Content
  ▼
Browser ignora resposta (beacon é fire-and-forget)
```

## 6. Error handling

### Contrato uniforme

Todo erro retorna mesmo shape + header `X-Request-Id`:

```json
{
  "error": "rate_limit_exceeded",
  "detail": "Max 20 requests/hour per IP",
  "code": "E_RATE_LIMIT",
  "request_id": "01HWPJ9K4XK..."
}
```

### Catálogo de códigos

| Código | HTTP | Quando | Retryable | Cliente pode ajudar? |
|---|---|---|---|---|
| `E_AUTH_MISSING` | 401 | Sem token em estágio ≥3 | Não | Sim (login) |
| `E_RATE_LIMIT` | 429 | Rate limiter bloqueou | Sim após `Retry-After` | Não |
| `E_BUDGET_EXCEEDED` | 402 | Daily cap global estourado | Sim após UTC midnight | Não |
| `E_INVALID_AUDIO` | 400 | librosa não leu | Não | Sim (outro arquivo) |
| `E_AUDIO_TOO_LARGE` | 413 | > 25MB | Não | Sim (comprimir) |
| `E_LLM_EXTRACTION` | 502 | Anthropic falhou / JSON inválido | Sim (retry) | Não |
| `E_LLM_TIMEOUT` | 504 | Anthropic > 30s | Sim | Não |
| `E_COMPLIANCE` | 500 | ComplianceError (bug) | Não | Não (reportar) |
| `E_INTERNAL` | 500 | Outra exceção | Talvez | Não |

### Global exception handler (A4)

Registrado em `main.py` via `@app.exception_handler(Exception)`. Mapeia:

- `HTTPException` → preserva `status_code`, adiciona código semântico
- `DNAExtractionError` → 502 `E_LLM_EXTRACTION`
- `ComplianceError` → 500 `E_COMPLIANCE` (logado em severity=CRITICAL — indica bug)
- `ValueError` em handlers de audio → 400 `E_INVALID_AUDIO`
- `anthropic.APITimeoutError` → 504 `E_LLM_TIMEOUT`
- Outros → 500 `E_INTERNAL`

**Sanitização:** `detail` **nunca** vaza stack trace ou raw de Anthropic em prod (`debug=False`). Em debug, inclui para dev.

## 7. Testing strategy

### Meta — ~45 novos testes

Hoje: 19 compressor + 4 smoke = **23 testes**. Após: **~68 testes**.

### Distribuição por agent

| Agent | Test file(s) | Casos mínimos |
|---|---|---|
| A1 (auth) | `test_infra_auth.py` | (1) `NoAuthProvider` gera subject_id estável, (2) IPs diferentes → subject_ids diferentes, (3) `AuthContext` serializa |
| A2 (rate-limit) | `test_infra_rate_limit.py` | (1) permite até limit, (2) bloqueia limit+1, (3) libera após TTL, (4) `Retry-After` correto, (5) concurrent-safe com `asyncio.gather` |
| A3 (budget) | `test_infra_budget.py` | (1) aceita até cap, (2) rejeita se estoura, (3) daily reset em midnight UTC, (4) record atômico sob concorrência, (5) só grava após success |
| A4 (observability) | `test_infra_logging.py`, `test_client_errors_endpoint.py` | (1) request_id gerado, (2) preservado se vindo no header, (3) logs contêm request_id, (4) stacktrace só em debug, (5) `/client-errors` batch válido 204, (6) batch inválido 400, (7) re-emissão contém `logger=frontend` |
| A5 (compliance-audio) | `test_infra_compliance.py` | (1) extrai "Beatles" de "cover de beatles", (2) extrai palavras quoted, (3) respeita `artist_to_avoid` explícito, (4) união+dedup lowercase, (5) hint vazio → [], (6) false positive baixo em "Brazilian jazz" |
| A6 (async-audio) | `test_async_audio.py` | (1) 2 requests audio simultâneos terminam em ~tempo de 1 (não 2×), (2) `librosa.load` chamado via `to_thread` (mock + spy) |
| A7 (integration) | `test_endpoints.py` | (1) /text com mock Anthropic 200 + shape correto, (2) subject vazio 422, (3) 21º request 429, (4) budget estourado 402, (5) audio inválido 400, (6) audio mock 200, (7) ComplianceError 500 E_COMPLIANCE, (8) hint "john lennon" + mock vazamento → bloqueio |

### Fixtures em `conftest.py`

```python
@pytest.fixture
def mock_anthropic_response(monkeypatch):
    """Monkey-patches AsyncAnthropic.messages.create para retornar JSON fixo."""

@pytest.fixture
def synthetic_wav_60s(tmp_path) -> Path:
    """Gera WAV sintético de 60s (sine wave) via numpy + soundfile."""

@pytest.fixture
def test_client_no_auth(monkeypatch) -> TestClient:
    """TestClient com NoAuthProvider forçado; reset de infra state."""

@pytest.fixture(autouse=True)
def reset_infra_state():
    """Zera rate limiter e budget tracker entre testes."""
```

### Frontend (A8)

Sem testes unitários do `logger.ts` nesta spec. Validação manual:

- `bun run lint` deve passar com 0 erros
- `bun run build` deve passar type-check strict
- Dev: gerar um `throw` no console — verificar beacon no Network tab + linha JSON em `docker compose logs backend`

## 8. Migração stage 1 → 4

Recapitulando os critérios C4-C6 (Seção 1):

### Stage 1 → 2: Público sem auth (Cloudflare Turnstile + Redis)

**Mudanças de config:**
```env
RATE_LIMIT_BACKEND=redis
REDIS_URL=redis://...
BUDGET_BACKEND=redis
TURNSTILE_SECRET_KEY=...
```

**Código novo (1 classe cada):**
- `infra/rate_limit.py`: `RedisRateLimiter(RateLimiter)` — sliding window em Lua script
- `infra/budget.py`: `RedisBudgetTracker(BudgetTracker)` — INCRBYFLOAT atômico
- `infra/captcha.py`: middleware que valida header `cf-turnstile-response` via API do Cloudflare

**Endpoints de domínio (generate_text, generate_audio): ZERO mudança.**

### Stage 2 → 3: Auth via Clerk + quota por usuário

**Mudanças de config:**
```env
AUTH_PROVIDER=clerk
CLERK_SECRET_KEY=...
BUDGET_BACKEND=postgres  # per-user agora
```

**Código novo:**
- `infra/auth.py`: `ClerkAuthProvider(AuthProvider)` — valida JWT, mapeia para AuthContext com user_id+plan
- `infra/budget.py`: `PostgresBudgetTracker(BudgetTracker)` — usa `user_quota` table
- Alembic migration para `user_quota` (reaproveitando infra Fase 3 de DBs)

**Endpoints: ZERO mudança** (AuthContext é o mesmo shape, apenas subject_id muda formato).

### Stage 3 → 4: API-key para B2B

**Mudanças de config (opcional, coexiste com Clerk):**
```env
AUTH_PROVIDER=multi  # aceita Clerk OU ApiKey
```

**Código novo:**
- `infra/auth.py`: `ApiKeyAuthProvider(AuthProvider)` — valida header `X-API-Key` contra `api_keys` table
- `infra/auth.py`: `MultiAuthProvider(AuthProvider)` — tenta ApiKey primeiro, Clerk depois
- Nova rota `/admin/api-keys` para emissão

**Endpoints de domínio: ZERO mudança.**

## 9. Dependências novas

### Backend `requirements.txt`

```
# agent-observability (A4)
structlog>=24.4.0,<25
```

Constraint estilo caret/range alinhado ao restante do ecossistema kratos (ex: `kratos-case-pipeline`).

Nada de SlowAPI no stage 1 — `InMemoryRateLimiter` é simples o suficiente em 50 LoC.
SlowAPI pode entrar em stage 2 junto com Redis se o pattern ficar complexo.

### Frontend `package.json` devDependencies (A8)

```json
"eslint": "^9.12.0",
"@typescript-eslint/parser": "^8.8.0",
"@typescript-eslint/eslint-plugin": "^8.8.0",
"eslint-plugin-react": "^7.37.1",
"eslint-plugin-react-hooks": "^5.0.0",
"eslint-plugin-jsx-a11y": "^6.10.0",
"eslint-plugin-simple-import-sort": "^12.1.1",
"prettier": "^3.3.3"
```

## 10. Open questions

1. **Budget global vs per-IP no stage 1?** — Spec atual usa global (1 counter para todos). Protege contra prejuízo financeiro absoluto, mas 1 usuário abusivo trava o serviço para todos. Alternativa: ambos (global + per-IP). Decisão: **manter global-only por simplicidade**; per-IP fica para stage 2 quando Redis permitir counters múltiplos baratos.

2. **Request logs: sempre JSON ou console em dev?** — JSON quebra DX no dev. Decisão: **`debug=True` → ConsoleRenderer; `debug=False` → JSONRenderer**. Flag `log_format` permite override explícito.

3. **Frontend: qual granularidade dos erros enviados?** — Enviar `console.error` todos vira ruído se o projeto tiver logs de debug. Decisão: filtro no logger: envia apenas erros com Error-like (stack trace), warnings explícitos via `logger.warn()`, e slow API > 5s. Ignora console.log/info/debug.

4. **Dedup de client-errors no servidor:** janela? — Decisão: 5 min (rolling cache em memória no handler). Se `hash(message+stack[:200])` já foi visto nos últimos 5 min, incrementa counter e não re-emite.

5. **X-Request-Id propagação cross-service:** — Decisão: backend aceita header `X-Request-Id` se vier, senão gera uuid4. Frontend `logger.ts` não gera request-id próprio — deixa o backend agrupar.

## 11. Referências

- Sliding window rate limit: [Cloudflare blog](https://blog.cloudflare.com/counting-things-a-lot-of-different-things/) (inspiração para `InMemoryRateLimiter`)
- structlog pattern: `kratos-case-pipeline/kcp/infra/logging.py` (reusar exato)
- LintLogObservability skill: `~/.claude/skills/LintLogObservability/` (base do frontend logger)
- Projeto pai: `pseuno-ai` (MIT) — não fornece observabilidade, decisões daqui são novas
