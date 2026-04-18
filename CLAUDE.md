# CLAUDE.md — kratos-suno-monorepo

## Project snapshot

Monorepo pnpm. Gerador de prompts Suno AI a partir de nome/MP3/Spotify. Fork adaptado de `pseuno-ai`.

- **Backend**: Python 3.12 + FastAPI + SQLAlchemy async + Alembic + librosa DSP + Claude Anthropic
- **Web**: React 18 + Vite + Chakra UI 2 (em `packages/web/`)
- **Mobile**: Expo Router 4 + React Native Paper MD3 (em `packages/mobile/`)
- **Shared TS**: `@kratos-suno/core` em `packages/core/` (types, API client factory, useAuth hook)
- **Infra**: AWS CDK TS — App Runner + ECR + Secrets Manager + CloudWatch + Neon PG

## Current state (2026-04-18)

**Wave 1 concluída** — 33 commits em master desde import v0.3.0. Stack full validated end-to-end via docker-compose.dev.yml + real Anthropic API (Djavan e Anitta geraram prompts corretos, 0 vazamentos de copyright).

**Tests:** 90/90 backend pytest + 3/3 CDK jest + 0 erros TS typecheck em core/mobile/web.

**Runtime local validado:**
```bash
cp .env.example .env   # preencher ANTHROPIC_API_KEY real
docker-compose -f docker-compose.dev.yml up -d postgres backend
# POST http://localhost:8000/api/v1/generate/text com {"subject":"Djavan"}
```

## Conventions

- **Primary language**: Python 3.12 backend, TypeScript 5.6 frontend
- **Package manager**: `pnpm` (NUNCA npm/yarn). Para workspace root: `corepack enable && corepack prepare pnpm@9.12.0 --activate`
- **Portuguese** para UI/UX text e textos jurídicos; **English** para código, variáveis, commits
- **Git author**: Felipe Moulin — NUNCA adicionar `Co-Authored-By` em commits
- **Tests before commit**: `cd backend && pytest tests/ -v` (deve estar 90 green)
- **Lint**: `ruff check --fix && ruff format` backend; ESLint flat config web

## Stack Decisions (não mexer sem razão)

1. **App Runner > Fargate** — $25/mo stage 1, sem VPC, sem NAT Gateway ($32/mo evitados)
2. **Neon > RDS** — free tier + autopause
3. **Cloudflare Pages > Vercel** — SPA puro, bandwidth ilimitado, latência BR
4. **pnpm workspaces > Nx/Turbo** — sem complexidade que justifique build cache distribuído
5. **React Native + Expo > Flutter** — reusa ~70% do TS do web via `@kratos-suno/core`
6. **Compressor determinístico em Python puro** — reprodutibilidade + auditoria anti-copyright (não usar LLM)

## Arquitetura hardening (W1-A)

Novo package `backend/app/infra/` com Protocol pluggables:
- `auth.py`: `AuthProvider` protocol + `SharedSecretAuthProvider` (stage 1). Clerk (stage 3) e ApiKey (stage 4) são classes futuras, interface estável
- `rate_limit.py`: `RateLimiter` + `InMemoryRateLimiter` sliding window. Redis para stage 2 é troca de config
- `budget.py`: `BudgetTracker` + `InMemoryBudgetTracker` daily UTC reset. Postgres por-user para stage 3
- `logging.py`: structlog + RequestIdMiddleware + global exception handler
- `compliance.py`: `extract_forbidden_terms_from_hint` heurístico (regex capitalizadas + quoted)

Cada `setup_X(app)` em `main.py` é merge-safe (uma linha por agent paralelo).

Settings via `config.py`: `auth_provider`, `rate_limit_backend`, `budget_backend` escolhem impl. `shared_secret_key=""` desabilita auth (dev mode).

## Mobile Spotify deep link (W1-B)

Fluxo completo implementado:
1. Mobile: `GET /auth/spotify/login?platform=mobile` → URL com redirect_uri mobile
2. Expo: `WebBrowser.openAuthSessionAsync(url, "kratossuno://spotify-connected")` abre browser nativo
3. Spotify: user aprova → redireciona para `api.example.com/auth/spotify/mobile-callback`
4. Backend: exchange code + issue JWT HS256 (PyJWT) + `302 → kratossuno://spotify-connected?token=<jwt>`
5. Mobile `app/_layout.tsx`: `Linking.addEventListener("url", ...)` + cold-start `Linking.getInitialURL()` captura deep link
6. `src/deepLinks.ts::handleSpotifyConnectedUrl` salva token via `expo-secure-store`
7. `useFocusEffect(refresh)` em `(tabs)/spotify.tsx` re-checa auth state
8. `resolve_session_id(request)` no backend aceita cookie (web) OU `Authorization: Bearer <jwt>` (mobile)

Session persistence: `PersistentSessionStore` (Postgres) hidrata in-memory cache em miss → restart do backend não invalida sessões Spotify.

## Known state

- **Compose dev**: postgres em host port **5433** (5432 geralmente ocupado), backend em 8000, web buildável em 5173
- **Docker backend build**: requer `--network=host` ou usar pip flags `--timeout=300 --retries=5` (já no Dockerfile) por causa de librosa+matplotlib+numpy ~500MB
- **Docker web**: `docker build -f packages/web/Dockerfile .` do **root** (contexto workspace). Image 62.7MB. Container sozinho falha por `upstream backend` do nginx.conf — só roda dentro do compose stack
- **Spec + plans**: `docs/superpowers/specs/` e `docs/superpowers/plans/` têm os artefatos de brainstorming/planning
- **Worktree isolation Agent tool**: durante Wave 1, dois agents paralelos (W1-A + W1-B) mexeram na mesma branch via `git checkout` concorrente. W1-A criou worktree separado em `../w1a-worktree/` para se isolar. Lição: para verdadeira paralelização, criar worktrees explícitos com `git worktree add` antes do dispatch

## Pending / Next steps

**Wave 2a concluída — MVP webapp focus (2026-04-18):**
- ✅ Error boundaries web — `packages/web/src/components/ErrorBoundary.tsx` envolvendo `<App />` no `main.tsx`
- ✅ Frontend tests — vitest + testing-library + jsdom, 8/8 tests green (5 ErrorBoundary + 3 App smoke)
- Commit: `c8b6fc6 test(web): wave 2a — ErrorBoundary + vitest + 8 tests (MVP webapp)`

**Imediato (MVP blockers, não-agent):**
- Preencher `ANTHROPIC_API_KEY` real em `.env` (gitignored) para smoke local
- Deploy staging AWS (comando em README.md / DEPLOYMENT.md) — CDK synth validado, 2 stacks (`kratos-suno-backend-staging`, `kratos-suno-cicd-staging`)
- Preencher 3 secrets no console AWS: ANTHROPIC_API_KEY, DATABASE_URL (Neon), SPOTIFY_CLIENT_ID
- Smoke test físico Spotify mobile (requer celular + SPOTIFY_CLIENT_ID real + deploy staging)

**Deferido para pós-MVP:**
- Accessibility labels mobile (zero → completo) — mobile não é MVP target
- Theme mobile bypass fix (hardcodes `#0a0a0a` → `theme.colors.*`)
- Error boundaries mobile (Expo)
- Expandir cobertura de testes web (atualmente 8 tests; meta pós-MVP ~20)
- ESLint config no `packages/web/` (script existe mas binário ausente — script `lint` falha)

**Deploy quando quiser:**
```bash
cd infra/cdk && pnpm install && cdk bootstrap && pnpm cdk:deploy:staging
# preencher 3 secrets no console AWS (Anthropic key, db URL Neon, Spotify client ID)
# GitHub Actions faz deploy automático em push a develop/main
```

Ver `docs/DEPLOYMENT.md` para checklist completo.

## References

- `README.md` — overview geral
- `docs/MONOREPO.md` — estrutura pnpm + core package
- `docs/DEPLOYMENT.md` — deploy AWS+Cloudflare+Neon passo-a-passo
- `docs/MOBILE.md` — React Native specifics + deep link flow
- `CHANGELOG.md` — histórico versionado
- `docs/superpowers/specs/2026-04-17-kss-hardening-pluggable-design.md` — spec Track A
- `docs/superpowers/plans/2026-04-17-w1{a,b,c}-*.md` — plans executados na Wave 1

## Project structure

```
kratos-suno-monorepo/
├── backend/
│   ├── app/
│   │   ├── api/v1/            # generate_{text,audio}, auth_spotify, saved_prompts, spotify_profile
│   │   ├── infra/             # W1-A: auth, rate_limit, budget, logging, compliance, factories
│   │   ├── services/          # dna_{text,audio}_extractor, audio_analyzer, prompt_compressor,
│   │   │                       #  session_store, persistent_session, spotify_client,
│   │   │                       #  dna_cache, jwt_utils, pkce_utils, cache_utils
│   │   ├── db/                # models + migrations 001→003
│   │   ├── schemas/           # sonic_dna.py, auth.py
│   │   ├── prompts/versions/  # v1_baseline.md, v2_stricter.md (A/B test via ACTIVE_PROMPT_VERSION)
│   │   ├── config.py
│   │   └── main.py
│   ├── tests/                 # 90 pytest (39 v0.3 base + 29 W1-A + 22 W1-B)
│   ├── prompt_lab/            # CLI A/B testing de prompts
│   └── Dockerfile             # Python 3.11 + libsndfile + ffmpeg + pip --timeout=300
├── packages/
│   ├── core/                  # @kratos-suno/core
│   ├── web/                   # React+Vite+Chakra — 4 abas
│   └── mobile/                # Expo — app/(tabs)/{text,audio,spotify,saved}.tsx + result.tsx + spotify-connected.tsx
├── infra/cdk/                 # AWS CDK TypeScript
├── .github/workflows/         # backend.yml, web.yml, mobile.yml (OIDC)
├── docs/
├── docker-compose.dev.yml     # postgres (5433) + backend (8000) + web (5173)
└── pnpm-lock.yaml
```
