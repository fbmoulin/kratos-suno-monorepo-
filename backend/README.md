# backend

FastAPI + Pydantic v2 + SQLAlchemy async + Alembic + Claude Anthropic + librosa DSP.

## Local dev (sem Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# preencher ANTHROPIC_API_KEY

# Postgres local (Docker)
docker run -d --name ks-pg -p 5433:5432 -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=kratos_suno postgres:16-alpine

export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/kratos_suno
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

## Tests

```bash
pytest tests/ -v                          # 90 tests, ~5s
pytest tests/ --cov=app.infra             # cobertura do package Wave 1 (>90%)
pytest tests/test_infra_* -v              # só os novos da Wave 1
```

## Lint/format

```bash
ruff check --fix && ruff format           # antes de commitar (obrigatório)
```

## Layout

- `app/api/v1/` — rotas REST versionadas: `generate_text`, `generate_audio`, `auth_spotify`, `spotify_profile`, `saved_prompts`
- `app/infra/` (Wave 1) — auth, rate_limit, budget, compliance, logging, factories
- `app/services/` — dna extractors, audio analyzer, prompt compressor (determinístico), session stores, spotify client, jwt, cache
- `app/db/` — models, session, migrations Alembic (001→003)
- `app/schemas/` — Pydantic v2 mirrored em `packages/core/src/types/`
- `app/prompts/versions/` — system prompts A/B testáveis via `ACTIVE_PROMPT_VERSION`
- `prompt_lab/` — CLI para A/B test de prompts (`python -m prompt_lab.run --prompts v1_baseline v2_stricter`)

## Endpoints principais

| Método | Path | Auth | Rate limit | Budget |
|---|---|---|---|---|
| GET | `/health` | — | — | — |
| POST | `/api/v1/generate/text` | ✅ | ✅ | ✅ |
| POST | `/api/v1/generate/audio` | ✅ | ✅ | ✅ |
| GET | `/api/v1/auth/spotify/login?platform={web\|mobile}` | — | ✅ | — |
| GET | `/api/v1/auth/spotify/callback` | cookie | ✅ | — |
| GET | `/api/v1/auth/spotify/mobile-callback` | session | ✅ | — |
| GET | `/api/v1/auth/status` | cookie/bearer | — | — |
| POST | `/api/v1/auth/logout` | cookie/bearer | — | — |
| GET | `/api/v1/spotify/profile?time_range=...` | cookie/bearer | — | — |
| GET/POST/DELETE | `/api/v1/prompts` | cookie/bearer | — | — |

## Env vars essenciais

Ver `.env.example` para lista completa. Mínimo para rodar:

- `ANTHROPIC_API_KEY` — obrigatório
- `DATABASE_URL` — default aponta para postgres local
- `AUTH_PROVIDER=shared_secret` + `SHARED_SECRET_KEY=""` (vazio desabilita auth em dev)
- `ACTIVE_PROMPT_VERSION=v1_baseline`

Wave 1 additions (todos com defaults seguros):
- `RATE_LIMIT_PER_HOUR=20` — 100 no compose dev
- `DAILY_BUDGET_USD=2.0`
- `LOG_FORMAT=console` — mude para `json` em prod
- `JWT_SECRET_KEY=""` — obrigatório só se usar mobile

## Contratos importantes

- **Compressor `prompt_compressor.py` é determinístico** — dado o mesmo SonicDNA, sempre o mesmo output. Não usar LLM aqui.
- **ComplianceError** é bug, não degradação — nomes próprios vazando no prompt é crítico, nunca silenciar
- **`cost_per_{text,audio}_generation_usd`** é estimativa; budget decrementa no success path apenas
- **structlog `request_id`** propaga via contextvars — todos os logs da mesma request compartilham o ID
