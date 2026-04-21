# Changelog

Todas as mudanças notáveis neste projeto são documentadas aqui.

Formato: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Semver: [semver.org](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Wave 2b — 2026-04-20 (Web P0 fixes — public MVP readiness)

**Context:** Deep analysis scored webapp 6/10 MVP-ready (backend 8/10, infra 8/10). Chose Rota B (ship this week). 5 sequential P0 fixes + docs; **4 of 5 done, 2b.5 Playwright pending**. Plan: `docs/superpowers/plans/2026-04-20-wave-2b-web-p0-fixes.md`.

#### Added (2b.1-2b.4)

**Fix 2b.1 — Mobile responsive breakpoints** (`e35987b`)
- `Container maxW={{ base: "full", md: "3xl" }}` + `px={{ base: 4, md: 0 }}` em App.tsx
- Heading/Text responsive `fontSize` across App/ResultsDisplay/SavedPromptsList
- `SpotifyTab Select maxW={{ base: "full", sm: "200px" }}` + AudioUpload dropzone `p={{ base: 4, md: 8 }}`
- `minW={0}` em Headings truncadas

**Fix 2b.2 — Audio loading UX** (`cc0aa2b`)
- `packages/web/src/components/AudioLoadingStatus.tsx` — banner "Isso pode levar 30-40 segundos" + rotating status messages (5s intervals: "Extraindo áudio" → "Analisando estilo" → "Gerando prompts") + elapsed timer `⏱ Ns`
- 4 novos tests: render guard (isLoading=false), initial state, rotation + timer increments, cleanup on unmount

**Fix 2b.3 — Error classification + typed ApiHttpError** (`00bde9e` + `056761b`)
- `packages/core/src/api/http.ts`: `ApiHttpError` extendido com 5º param opcional `retryAfter?: number`; `request()` lê header `Retry-After` (regex `/^\d+$/`) no branch 4xx/5xx — backward-compat em todos callsites
- `packages/web/src/lib/parseApiError.ts` — função pura mapeando 9 branches PT-BR: `E_AUTH_MISSING`/`E_TIMEOUT`/`E_NETWORK`/`E_BUDGET_EXCEEDED`/`429`/`400`/`413`/`502` + fallback. Action button injection via `ParseApiErrorOptions.onReconnectSpotify` (callback pattern, mantém função pura)
- `packages/web/src/App.tsx`: `handleError` usa `parseApiError` + Chakra toast `render` prop com Alert + action button; `requestId` full (sem truncation) mostrado como muted text; `useAuth().loginWithSpotify` injetado no callback
- Fallback branch loga `console.error("[parseApiError] Unclassified error", err)` para debug prod
- 13 testes parseApiError + 1 integration test em App.test.tsx (400 path via mock rejection)

**Fix 2b.4 — Form validation (maxLength + MIME)** (`a818b4d` + `6a8f0a3`)
- `packages/web/src/components/TextInput.tsx`: `maxLength={200}` no Input (match backend `Field(..., max_length=200)` em `schemas/sonic_dna.py:140`) + live char counter `N/200` com `color="red.400"` quando > 180, `role="status"` + `aria-live="polite"` + Chakra `isInvalid={isWarning}` (emite `aria-invalid` nativo no DOM)
- `packages/web/src/components/AudioUpload.tsx`: `useDropzone` ganha `maxSize` config; `onDropRejected` callback mapeia `file-invalid-type` → "Formato não suportado. Use MP3, WAV, FLAC, M4A ou OGG." e `file-too-large` → "Arquivo excede 25MB" (PT-BR); `userHint` Input ganha `maxLength={200}` (match backend `Form(default=None, max_length=200)`); `setFile(null)` em `onDropRejected` limpa estado stale (evita submissão acidental de arquivo anterior após rejeição); manual size check em `onDrop` removido (dead code pós-`maxSize` config)
- 4 testes TextInput (counter render/update/warning state via `data-warning`/`maxLength` attr, aria-live announcement) + 4 testes AudioUpload (accept MP3, reject .txt, reject 26MB, userHint maxLength) + 2 regression tests (stale file cleared on rejection, a11y attributes)

#### Deferred to 2b.5 + 2b.6

- Playwright E2E Spotify OAuth — backend `spotify_mock_mode` + `SpotifyClient` short-circuits + `@playwright/test` setup + first E2E spec com `page.route()` interceptando Spotify authorize URL
- Docs + final code review — consolidar CHANGELOG + CLAUDE.md + requesting-code-review final pass

#### Verificação (Wave 2b.1-2b.4)

- Web unit tests: **37/37** passed (was 13/13 at start of Wave 2b; +24 net)
  - Novos: 4 AudioLoadingStatus, 13 parseApiError, 1 App integration, 4 TextInput, 4 AudioUpload, 2 regression
- Web typecheck: ✅ clean (core + web + mobile — `ApiHttpError` extension backward-compat)
- Web lint: ✅ clean (`--max-warnings 0`)
- Web build: ✅ success (bundle ~533KB, unchanged)
- Backend: 90/90 unchanged (no backend changes in 2b.1-2b.4)

#### Review process validation

- Subagent-driven-development workflow usado em 2b.3 + 2b.4: implementer → spec reviewer → code quality reviewer → fix pass → re-review
- **2b.3 crítico capturado**: `spotifyLoginRedirect` apontava pro endpoint JSON em vez do fluxo OAuth — corrigido via callback injection
- **2b.4 crítico capturado**: stale file no `onDropRejected` permitia submissão acidental do arquivo anterior após rejeição — corrigido
- Spec compliance review e code quality review dão sinais distintos; manter ambos

### Wave 2a — 2026-04-18 (MVP webapp focus)

**Reframe:** user decidiu pivot pra webapp full-stack como MVP; mobile a11y + theme fixes deferidos pós-MVP. Spotify deep link (Wave 1) mantido já que tá shipado.

#### Added
- `packages/web/src/components/ErrorBoundary.tsx` — React class-based Error Boundary envolvendo `<App />` no `main.tsx`. Fallback PT-BR com botão retry, Chakra-styled, error details apenas em dev (`import.meta.env.DEV`). Props opcionais: `fallback` (render prop custom) + `onError` (hook para Sentry futuro)
- `packages/web/src/main.tsx` — wraps `<App />` em `<ErrorBoundary>`
- `packages/web/vitest.config.ts` + `src/test/setup.ts` + `src/test/test-utils.tsx` — infra vitest (jsdom + testing-library + renderWithProviders helper com ChakraProvider)
- `packages/web/src/App.test.tsx` — 3 smoke tests (título + tabs, OAuth callback auto-switch, disclaimer 200-char)
- `packages/web/src/components/ErrorBoundary.test.tsx` — 6 tests cobrindo: children render normal, fallback em erro, `onError` callback, retry sem mudar causa, recuperação real após remover a causa, custom fallback prop
- `packages/web/eslint.config.mjs` — configuração ESLint flat mínima para TypeScript + React hooks no pacote web

#### Dev deps
- `vitest ^2.1.2`, `@testing-library/{react,jest-dom,user-event}`, `jsdom ^25.0.1`, `eslint ^9`, `@eslint/js`, `typescript-eslint`, `eslint-plugin-react-hooks`, `globals`

#### Scripts
- `pnpm --filter @kratos-suno/web test` / `test:watch`

#### Verificação
- Web tests: **9/9 passed**
- Web typecheck: ✅ clean
- Web lint: ✅ clean
- Web build: ✅ success (530KB gzip — warning pré-existente, não relacionado)
- Backend: 90/90 still green (zero regression)
- CDK: 3/3 tests + `pnpm synth` clean → deploy path staging validado

#### Deferido para pós-MVP
- Accessibility labels mobile (Expo `accessibilityLabel` props)
- Theme mobile bypass fix (hardcoded `#0a0a0a` → `theme.colors.*`)

### Wave 1 — 2026-04-18 (23 commits aplicados a master)

#### Added

**W1-C Infra Polish** (4 commits)
- CloudWatch LogGroup com retention 30d staging / 90d prod via CDK
- Web Dockerfile reescrito para pnpm+corepack com workspace-aware build (monorepo root como contexto)
- `docs/DEPLOYMENT.md`: seção "Prerequisites Checklist" (13 itens) + "DNS Setup" (Cloudflare Pages + Route 53 App Runner) + URLs canônicas explícitas
- `.github/workflows/web.yml`: `aws-actions/configure-aws-credentials@v4` + `aws secretsmanager get-secret-value` para pull de `VITE_SHARED_SECRET` (elimina duplicação GH Secrets vs AWS Secrets Manager)
- `infra/cdk/test/backend-stack.test.ts`: 2 novos testes para retention 30d/90d + env var setup
- CDK test coverage: 3/3 passing

**W1-A Backend Hardening** (12 commits)
- Novo package `backend/app/infra/` com 7 módulos: `auth.py`, `rate_limit.py`, `budget.py`, `logging.py`, `compliance.py`, `factories.py`, `__init__.py`
- Protocol-based abstractions para escalar stage 1→4 sem reescrita: `AuthProvider`, `RateLimiter`, `BudgetTracker`
- Stage 1 impls: `SharedSecretAuthProvider` (X-Kratos-Key header), `InMemoryRateLimiter` (sliding window deque), `InMemoryBudgetTracker` (asyncio.Lock + UTC daily reset)
- `structlog` + `RequestIdMiddleware` (uuid4 gerado se ausente, preservado se header `X-Request-Id` vier) + JSON renderer em prod, ConsoleRenderer em debug
- Global exception handler com catálogo E_* codes (`E_AUTH_MISSING`, `E_RATE_LIMIT`, `E_BUDGET_EXCEEDED`, `E_INVALID_AUDIO`, `E_LLM_EXTRACTION`, `E_COMPLIANCE`, etc.) + header `X-Request-Id` em todas as respostas + sanitização do detail em prod
- Async fix audio: `librosa.load` + `matplotlib.pyplot` via `asyncio.to_thread` — event loop livre para concorrência
- Compliance fix audio: heurística `extract_forbidden_terms_from_hint(hint, artist_to_avoid)` (regex capitalizadas + quoted phrases + filtro common false positives) + novo campo opcional `artist_to_avoid` em `GenerateFromAudioRequest` + integração em `/generate/audio` antes de `compress_all`
- Health check melhorado: `/health` valida `anthropic_key` configured + `budget_remaining_usd` + `prompt_version_file` presente + retorna `status: ok|degraded`
- CI: step `alembic upgrade head` com Postgres ephemeral em container antes do Docker build
- Config: 9 novas settings (auth_provider, rate_limit_backend, budget_backend, shared_secret_key, rate_limit_per_hour, daily_budget_usd, cost_per_text/audio_generation_usd, log_format)
- Config: `SPOTIFY_REDIRECT_URI` passa a exigir env var (removido default localhost hardcoded)
- 29 novos tests (6 auth + 5 rate_limit + 4 budget + 7 compliance + 3 logging + 2 async_audio + 2 integration) — cobertura infra/ em 91%

**W1-B Spotify Mobile Deep Link** (8 commits)
- `GET /api/v1/auth/spotify/mobile-callback` — exchange code + issue JWT HS256 + `302 → kratossuno://spotify-connected?token=<jwt>` on success, `?error=<code>` em cinco modos de falha
- `GET /api/v1/auth/spotify/login?platform=mobile|web` — Query param seleciona redirect_uri correto; sessão guarda `redirect_uri` para o callback rematchar (Spotify enforça equality entre authorize e token exchange)
- PyJWT 2.9.0 — `sign_session_token(session_id, secret, ttl)` + `verify_session_token(token, secret)` com `jwt.ExpiredSignatureError`
- `PersistentSessionStore` com `async_sessionmaker` + upsert save/get/delete em `user_session` table
- Alembic migration `003_user_session.py` — tabela com session_id unique index + spotify_user_id index
- Hydration: `SessionStore.attach_persistent()` + cache-miss rehydration em `get()` + write-through em `update()`/`delete()` → backend restart não invalida sessões
- `resolve_session_id(request)` — nova dependency que aceita cookie (web) OU `Authorization: Bearer <jwt>` (mobile), prioridade cookie > bearer
- Mobile: `packages/mobile/app/spotify-connected.tsx` — rota expo-router que extrai token de query param + salva via `expo-secure-store`
- Mobile: `packages/mobile/src/deepLinks.ts` — `parseSpotifyConnectedUrl(url)` + `handleSpotifyConnectedUrl(url)` utils
- Mobile: `packages/mobile/app/_layout.tsx` — `Linking.addEventListener("url", ...)` para warm start + `Linking.getInitialURL()` para cold start
- Mobile: `packages/mobile/app/(tabs)/spotify.tsx` — `useFocusEffect(refresh)` para re-check pós deep link return
- Core: `ApiClient.initiateSpotifyLogin({ platform })` + `useAuth({ platform })` plumbing cross-package
- Core: `SpotifyClient.build_authorize_url` + `exchange_code_for_tokens` aceitam `redirect_uri` override (mandatório para mobile)
- Settings: `spotify_mobile_redirect_uri` + `spotify_mobile_scheme` + `jwt_secret_key` + `jwt_ttl_seconds`
- 22 novos tests (4 jwt_utils + 4 persistent_session + 7 mobile_callback + 7 bearer_auth)

#### Fixed (post-merge, outside the waves)
- `packages/web/src/vite-env.d.ts` adicionado — `import.meta.env` agora resolve, desbloqueia docker build da web
- `backend/app/api/v1/auth_spotify.py`: `except Exception: profile = {}` no profile fetch trocado por `log.warning("spotify.profile.fetch_failed", ...)` via structlog — erros não mais silenciosos (W1-C Task 5 deferido completado após W1-A)
- `backend/Dockerfile`: `pip install --timeout=300 --retries=5` para resistir a network lenta baixando librosa+matplotlib+numpy (~500MB)
- `docker-compose.dev.yml`: serviço `frontend` renomeado para `web` com `context=.` + `dockerfile=packages/web/Dockerfile` (monorepo-aware); added W1-A/B env vars; postgres em `5433:5432`; backend command roda `alembic upgrade head` antes de uvicorn

#### Infrastructure
- `pnpm-lock.yaml` committed em root (necessário para `pnpm install --frozen-lockfile` em CI/Docker)
- `.env.example` em root documenta vars do compose stack
- `docs/superpowers/specs/2026-04-17-kss-hardening-pluggable-design.md` — spec Track A aprovada pelo spec-reviewer
- `docs/superpowers/plans/2026-04-17-w1{a,b,c}-*.md` — 3 plans TDD detalhados (600+500+300 linhas)
- 33 commits em master desde baseline v0.3.0

#### Validation (2026-04-18 end-to-end)
- Backend pytest: **90/90** (39 v0.3.0 base + 29 W1-A + 22 W1-B)
- CDK jest: **3/3** (smoke + retention 30d + retention 90d)
- TypeScript typecheck: 0 erros em @kratos-suno/core + mobile + web
- Docker web build: 62.7MB image via pnpm+corepack+workspace-aware Dockerfile
- Docker compose: postgres healthy + backend up + alembic 3 migrations OK + structlog JSON logs + `/health` status ok
- Generation E2E com Anthropic real: Djavan (MPB/soul) + Anitta (reggaeton/latin trap) → 6 variantes dentro de 200 chars, 0 vazamentos de forbidden_terms
- DNA cache Postgres (W1-B): INSERT + SELECT hit instantâneo em retry

### Migration path documented
- **Stage 1 → 2**: set `RATE_LIMIT_BACKEND=redis` + `BUDGET_BACKEND=redis` + add `TURNSTILE_SECRET_KEY`. Código de domínio não muda.
- **Stage 2 → 3**: set `AUTH_PROVIDER=clerk` + `BUDGET_BACKEND=postgres`. Criar `ClerkAuthProvider(AuthProvider)` + `PostgresBudgetTracker(BudgetTracker)`. Routes não mudam.
- **Stage 3 → 4**: criar `ApiKeyAuthProvider(AuthProvider)` + `MultiAuthProvider(AuthProvider)`. Routes não mudam.

## [0.3.0] — 2026-04-17

### Added (import inicial)

- Monorepo pnpm: `backend/` + `packages/{core,web,mobile}/` + `infra/cdk/`
- `@kratos-suno/core` — TypeScript shared: types (mirrorando Pydantic), API client factory (cookies/bearer), `useAuth` hook, `VARIANT_META`/`SOURCE_LABELS`
- Spotify OAuth PKCE backend (web flow) — `/auth/spotify/{login,callback,status,logout}`, session store in-memory com asyncio.Lock
- Spotify taste profile — `/spotify/profile?time_range={short|medium|long}_term` retorna top 20 artists + dominant genres
- Saved Prompts CRUD — `POST/GET/DELETE /prompts` com session-based isolation
- DNA cache Postgres — SHA256(subject+prompt_version) keys, version-gated invalidation
- Alembic migrations 001 (cached_dna + generation_log) + 002 (saved_prompt)
- Web: 4 abas Chakra (Texto, Áudio, Spotify, Salvos)
- Mobile: Expo Router 4 + React Native Paper MD3 — 4 tabs + result modal + spotify-connected.tsx (placeholder — deep link não funcional nesta versão, resolvido em Wave 1)
- Infra CDK: App Runner (0.25 vCPU stg / 1 vCPU prod) + ECR + Secrets Manager + CloudWatch alarms + Budgets + Neon PG + Cloudflare Pages
- GitHub Actions OIDC: `backend.yml` (develop → stg auto, main → prod com approval gate), `web.yml` (Cloudflare Pages), `mobile.yml` (EAS build)
- 39 tests backend (compressor + session_store + auth_and_cache + smoke)

### Decided

- **App Runner > Fargate** para stage 1 (~$25/mo vs $60+, sem VPC, sem NAT Gateway)
- **Neon > RDS** (free tier + autopause ~1s wake)
- **Cloudflare Pages > Vercel** (bandwidth ilimitado free, latência BR)
- **pnpm workspaces > Nx/Turbo** (sem complexidade que justifique)
- **React Native + Expo > Flutter** (reusa ~70% TS via core)
- **`sessionStrategy: "bearer"` em mobile + "cookies" em web** com mesma interface de ApiClient
- **Metro + pnpm**: `watchFolders: [workspaceRoot]` + `disableHierarchicalLookup: true` resolve monorepo module resolution

## [0.2.0] — 2026-04-15

Projeto v0.1 original (Fase 2): app web MVP com texto + áudio, librosa + Claude híbrido, prompt_compressor determinístico + ComplianceError guard-rail, prompt_lab CLI A/B testing. Raiz em `/home/fbmoulin/projetos-2026/kratos-suno-prompt/`.

## [0.1.0] — 2026-04-17 (pseuno-ai fork)

Fase 1 — Skill Claude Code para gerar style prompts Suno a partir de texto.
