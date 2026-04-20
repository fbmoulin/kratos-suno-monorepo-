# Plan — Wave 2b: Web P0 Fixes (MVP Public-Ready)

## Context

**Why this change is being made:**

Deep analysis on 2026-04-20 scored the kratos-suno-monorepo webapp **6/10 for MVP readiness** — foundation sound but **4/10 for MVP UX gaps**. Backend scored 8/10 and infra 8/10; both are ship-ready. The web frontend is the only blocker for public launch.

Five P0 fixes eliminate the user-facing friction identified by the Explore agents:

1. **Mobile responsive** — `Container maxW="3xl"` (Chakra `maxW="3xl"` = 48rem/768px) has no responsive fallback. BR mobile users on 375px screens get shrunk layout (not broken, but sub-optimal). Additional hardcoded widths: `SpotifyTab.tsx:124 Select maxW="200px"`, `AudioUpload.tsx:62-87 p={8}`, `ResultsDisplay.tsx:86 fontSize="xl"`.
2. **30s audio timeout messaging** — Backend `/generate/audio` is synchronous ~20-35s (librosa + Claude vision). Web shows only `"Analisando áudio..."` spinner. No SSE/polling available — backend cannot emit progress. Only UX-level mitigation possible: elapsed timer + rotating status messages + upfront expectation message.
3. **Error classification** — `ApiHttpError` in `packages/core/src/api/http.ts:19-29` exposes `status` + `code` + `requestId` but `App.tsx:50-59 handleError()` ignores them all. Backend emits E_AUTH_MISSING (401), E_RATE_LIMIT (429) with `Retry-After`, E_BUDGET_EXCEEDED (402), and generic 4xx/5xx. Web currently renders all as identical red toast.
4. **Form validation** — `TextInput.tsx:20-26` validates only trim+non-empty (no maxLength, Suno has 200-char limit). `AudioUpload.tsx:34-43` enforces extension whitelist + 25MB size but not MIME type (rename bypass possible). No form library needed — lightweight inline state.
5. **Spotify OAuth E2E test** — Currently only mocked via vitest (`App.test.tsx:39-44` renders + query param). Real end-to-end coverage needs Playwright. Spotify auth page cannot be tested directly — best strategy is backend `SPOTIFY_MOCK_MODE` env + Playwright `route.fulfill()` to intercept the authorize redirect.

**Intended outcome:**

After Wave 2b, the webapp is usable for a real BR user on a 375px phone with a slow network, who doesn't know what Suno is, who may hit rate limits or expired Spotify sessions, who may submit a bad file. The app communicates clearly at every friction point. E2E coverage on the Spotify OAuth flow ensures the most complex user journey is regression-proof.

**Non-goals (deferred to post-MVP):**

- Onboarding/landing page (Rota C-level polish, out of scope for Wave 2b)
- Accessibility full audit (ARIA labels audit can happen in parallel, separate plan)
- Global state library (useState is sustainable at this scale)
- Retry UI with backoff for failed generations (related to Fix 3 but separate scope)
- Mobile a11y (deferred post-MVP per user)

---

## Approach

Five sequential fixes, committed individually. Review checkpoint between each — user can stop/redirect any time. TDD where possible (fixes 1-4 have vitest tests). Fix 5 installs Playwright and creates the first E2E test.

**Critical files already mapped by Explore agents:**

| File | Role | LOC involved |
|---|---|---|
| `packages/web/src/App.tsx` | Tab orchestration, error handler, OAuth callback detection | ~155 total; fixes 1+3 touch lines 50-59, 100-145 |
| `packages/web/src/components/TextInput.tsx` | Text subject input | ~60; fix 4 |
| `packages/web/src/components/AudioUpload.tsx` | Audio file upload + dropzone | ~130; fixes 1, 2, 4 |
| `packages/web/src/components/SpotifyTab.tsx` | Spotify OAuth UI | ~150; fixes 1, 5 |
| `packages/web/src/components/ResultsDisplay.tsx` | Prompt output rendering | ~200; fix 1 |
| `packages/web/src/components/SavedPromptsList.tsx` | Saved prompts list | ~200; fix 1 |
| `packages/web/src/components/ErrorBoundary.tsx` | Already done in Wave 2a | no changes |
| `packages/web/src/main.tsx` | App entry + theme | ~30; no changes needed |
| `packages/core/src/api/http.ts` | `ApiHttpError` + fetch wrapper | ~150; fix 3 reads |
| `backend/app/infra/logging.py:62-81` | Global exception handler with E_* codes | 20 lines; fix 3 reads |
| `backend/app/api/v1/auth_spotify.py` | Spotify OAuth endpoints | ~350; fix 5 patches (mock mode) |
| `backend/app/services/spotify_client.py` | Spotify HTTP client | ~150; fix 5 patches (mock mode) |

**New files:**

| File | Purpose | Fix |
|---|---|---|
| `packages/web/src/lib/parseApiError.ts` | Typed error classifier mapping `ApiHttpError` → `{ title, description, status, action? }` | 3 |
| `packages/web/src/lib/parseApiError.test.ts` | Unit tests for 401/429/402/500/timeout mapping | 3 |
| `packages/web/src/components/AudioLoadingStatus.tsx` | Rotating status + elapsed timer shown during audio analysis | 2 |
| `packages/web/src/components/AudioLoadingStatus.test.tsx` | Unit tests for status rotation + timer | 2 |
| `packages/web/playwright.config.ts` | Playwright config (webServer + baseURL) | 5 |
| `packages/web/e2e/spotify-oauth.spec.ts` | First E2E test — Spotify OAuth happy path with mocked backend | 5 |
| `packages/web/e2e/fixtures/spotify-mocks.ts` | Test fixtures (user profile, top artists, tokens) | 5 |

**Backend additions for fix 5:**

- `backend/app/config.py`: add `spotify_mock_mode: bool = False`
- `backend/app/services/spotify_client.py`: short-circuit `exchange_code_for_tokens()` + `get_current_user()` + `get_top_artists()` when mock mode enabled
- `backend/tests/test_spotify_mock_mode.py`: 3 tests verifying mock short-circuit works

---

## Files

### Fix 1 — Mobile Responsive (S, ~1-1.5h)

**Modify:**
- `packages/web/src/App.tsx:100` — `Container maxW={{ base: "full", md: "3xl" }} px={{ base: 4, md: 0 }} py={{ base: 6, md: 10 }}`
- `packages/web/src/App.tsx:103-108` — Heading + Text responsive `fontSize={{ base: "lg", md: "xl" }}`
- `packages/web/src/components/SpotifyTab.tsx:124` — Remove hardcoded `maxW="200px"` on Select, replace with `maxW={{ base: "full", sm: "200px" }}`
- `packages/web/src/components/AudioUpload.tsx:62-87` — Dropzone `p={{ base: 4, md: 8 }}`
- `packages/web/src/components/ResultsDisplay.tsx:86,109` — Responsive `fontSize`
- `packages/web/src/components/SavedPromptsList.tsx:137` — add `minW={0}` to truncated Heading
- `packages/web/src/components/ResultsDisplay.tsx:173` — add `minW={0}` to truncated Heading

**Test strategy:** Manual check via `flutter run` not applicable (web) — run `pnpm --filter @kratos-suno/web dev`, use browser devtools responsive mode at 375px/414px/768px/1280px. Also verify no visual regression at desktop 1440px.

### Fix 2 — Audio Timeout Messaging (S, ~1-1.5h)

**Create:**
- `packages/web/src/components/AudioLoadingStatus.tsx` — component that accepts `isLoading: boolean` prop, renders elapsed timer (seconds) + rotating message list every 5s: `"Extraindo áudio..."` → `"Analisando estilo..."` → `"Gerando prompts..."`. Upfront banner: `"Isso pode levar 30-40 segundos"`.
- `packages/web/src/components/AudioLoadingStatus.test.tsx` — 3 tests: renders timer increments (fake timers), rotates message after 5s, unmounts cleanly on `isLoading=false`.

**Modify:**
- `packages/web/src/components/AudioUpload.tsx` — import + render `<AudioLoadingStatus isLoading={isLoading} />` below submit button when `isLoading === true`.

### Fix 3 — Error Classification (S-M, ~2h)

**Create:**
- `packages/web/src/lib/parseApiError.ts` — exports `parseApiError(err: unknown): { title: string; description: string; status: "error" | "warning"; action?: { label: string; onClick: () => void } }`. Recognizes:
  - `ApiHttpError.code === "E_AUTH_MISSING"` → `{ title: "Sessão expirada", description: "Reconecte com o Spotify para continuar.", status: "error", action: { label: "Reconectar Spotify", onClick: <redirect to Spotify login> } }`
  - `ApiHttpError.status === 429` → extract `retryAfter` from `code === "E_RATE_LIMIT"` message → `{ title: "Muitas requisições", description: "Aguarde ${retryAfter}s antes de tentar novamente.", status: "warning" }`
  - `ApiHttpError.code === "E_BUDGET_EXCEEDED"` → `{ title: "Limite diário atingido", description: "Esse serviço fica disponível novamente à meia-noite UTC.", status: "warning" }`
  - `ApiHttpError.status === 400` → `{ title: "Dados inválidos", description: err.message, status: "warning" }`
  - `ApiHttpError.status === 413` → `{ title: "Arquivo muito grande", description: "O arquivo excede 25MB.", status: "warning" }`
  - `ApiHttpError.status === 502` → `{ title: "Erro na análise", description: "Tente novamente em alguns segundos.", status: "error" }`
  - Timeout (`err.code === "E_TIMEOUT"`) → `{ title: "Tempo esgotado", description: "A análise demorou demais. Tente novamente.", status: "warning" }`
  - Network (`err.code === "E_NETWORK"`) → `{ title: "Sem conexão", description: "Verifique sua internet.", status: "warning" }`
  - Fallback → `{ title: "Erro", description: err.message || "Erro desconhecido", status: "error" }`
- `packages/web/src/lib/parseApiError.test.ts` — one test per branch above (~8 tests)

**Modify:**
- `packages/web/src/App.tsx:50-59` — `handleError(err)` now calls `parseApiError(err)` and passes full object to toast, including `action` button via Chakra's `render` prop if action present. Also include `requestId` in description for support tickets (small muted text).

### Fix 4 — Form Validation (S, ~1-1.5h)

**Modify:**
- `packages/web/src/components/TextInput.tsx` — add `maxLength={200}` on `<Input />`, show char counter `{subject.length}/200` below input with color `red.400` when > 180.
- `packages/web/src/components/AudioUpload.tsx` — `useDropzone` `accept` config expanded to explicit MIME types: `{ "audio/mpeg": [".mp3"], "audio/wav": [".wav"], "audio/flac": [".flac"], "audio/mp4": [".m4a"], "audio/ogg": [".ogg"] }`. Handles MIME-validated file rejection via dropzone's `onDropRejected` callback → set error state.
- `packages/web/src/components/AudioUpload.tsx` — if `userHint` field exists, add `maxLength={200}` (backend enforces via Form field).

**Test:**
- `packages/web/src/components/TextInput.test.tsx` — 2 new tests: char counter visible, maxLength enforced.
- `packages/web/src/components/AudioUpload.test.tsx` (create) — 2 tests: rejects renamed file with bad MIME, accepts valid MIME.

### Fix 5 — Playwright E2E for Spotify OAuth (M, ~3-4h)

**Backend changes (no code duplication — add mock mode):**
- `backend/app/config.py` — add `spotify_mock_mode: bool = False` setting.
- `backend/app/services/spotify_client.py` — when `settings.spotify_mock_mode`:
  - `exchange_code_for_tokens()` returns fixed `{access_token: "mock_access", refresh_token: "mock_refresh", expires_in: 3600, scope: "user-top-read"}` without HTTPing Spotify
  - `get_current_user(token)` returns `{id: "test_user", display_name: "Test Artist", images: [], country: "BR"}`
  - `get_top_artists(token, time_range, limit)` returns fixture with 3 artists (The Beatles, Radiohead, Björk) with genres
- `backend/tests/test_spotify_mock_mode.py` — 3 tests verifying short-circuit (1 per method).

**Web changes (install + configure Playwright):**
- `packages/web/package.json` — add devDep `@playwright/test` + script `"test:e2e": "playwright test"`
- `packages/web/playwright.config.ts` — config: `baseURL: "http://localhost:5173"`, webServer starts `pnpm dev`, use Chromium only, timeout 30s.
- `packages/web/e2e/fixtures/spotify-mocks.ts` — reusable mocks for Playwright's `page.route()` to intercept `/api/v1/auth/*` if needed.
- `packages/web/e2e/spotify-oauth.spec.ts` — single test `"connects with Spotify and shows top artists"`:
  1. `page.goto("/")`
  2. Click tab "🎶 Meu Spotify"
  3. Click "Conectar com Spotify"
  4. `page.route("**/accounts.spotify.com/authorize*", route => route.fulfill({ status: 302, headers: { location: "<backend>/api/v1/auth/spotify/callback?code=MOCK_CODE&state=<state>" } }))` — intercept Spotify redirect
  5. Wait for URL to contain `?spotify=connected`
  6. Assert tab index 2 active (Spotify tab)
  7. Assert display name "Test Artist" visible
  8. Assert top artists rendered (The Beatles, Radiohead, Björk)

**Requirements for running the E2E test:**
- Backend must run with `SPOTIFY_MOCK_MODE=true`
- Test uses real backend (via docker-compose or local uvicorn) — not mocked entirely
- `.github/workflows/web.yml` needs a new job that spins up backend + runs `pnpm test:e2e` (defer to post-plan — just ensure the test runs locally for Wave 2b)

---

## Verification

After each fix, the executing agent runs:
- `pnpm --filter @kratos-suno/web test` — existing 9 tests + new tests must all pass
- `pnpm --filter @kratos-suno/web typecheck` — zero errors
- `pnpm --filter @kratos-suno/web build` — successful (size warning known, unchanged)
- `pnpm --filter @kratos-suno/web lint` — zero errors (flat config in place)

Fix-specific verification:

- **Fix 1:** Manual browser DevTools at 375/414/768/1280px. Spec: no horizontal scroll at 375px; tabs readable; buttons tappable (44px min).
- **Fix 2:** Open `<AudioLoadingStatus isLoading={true}>` in Storybook-like isolation or unit test — verify timer advances and message rotates. Manual E2E: submit audio, observe rotating message + counter.
- **Fix 3:** `parseApiError.test.ts` → 8 tests green. Manual: trigger 401 (delete cookie), 429 (spam submit — backend must be running), verify UX.
- **Fix 4:** Unit tests green. Manual: try submitting empty subject (button disabled), paste 250-char subject (truncates at 200, counter turns red at 180). Drag a `.txt` renamed to `.mp3` (rejected).
- **Fix 5:** Backend tests `pytest tests/test_spotify_mock_mode.py -v` → 3 green. Then web E2E: `SPOTIFY_MOCK_MODE=true pnpm --filter @kratos-suno/web exec playwright test` → 1 test green. Test should NOT hit real Spotify.

**Final wave-level verification:**
- 15 vitest tests green (9 existing + 6 new from fixes 2,3,4)
- 93 backend tests green (90 + 3 new from fix 5)
- 1 Playwright test green
- `pnpm build` ok
- `pnpm typecheck` ok across all packages
- CHANGELOG.md + CLAUDE.md updated with Wave 2b completion

---

## Commit strategy

One commit per fix, each atomic and independently reversible:

```
fix(web): wave 2b.1 — mobile responsive breakpoints
feat(web): wave 2b.2 — audio loading status messaging + elapsed timer
feat(web): wave 2b.3 — error classification + typed ApiHttpError handling
feat(web): wave 2b.4 — form validation (maxLength + MIME)
test(e2e): wave 2b.5 — playwright + spotify OAuth happy path + backend mock mode
docs: wave 2b completion — CHANGELOG + CLAUDE.md
```

Branch: work directly on `main` (current default). Push after each commit. Stop between commits for user review.

## Skills to invoke during execution

- `superpowers:test-driven-development` for fixes 2, 3, 4 (test → red → implement → green)
- `superpowers:executing-plans` to process this plan task by task
- `frontend-specialist` agent for fix 3 (error UX has design decisions — severity pyramid, action button UX) — optional if user wants delegation
- Playwright MCP tools for interactive debugging during fix 5 (navigating + inspecting page state)
- `superpowers:requesting-code-review` after all 5 fixes before final docs commit

## Execution choice after ExitPlanMode

Per writing-plans skill, the user picks:
1. **Subagent-driven** (recommended) — fresh agent per fix, main session reviews diffs
2. **Inline** — execute here, checkpoint after each fix
