# 🟡 Checkpoint — Wave 2b 4/5 Done (2026-04-20 late session)

**TL;DR:** MVP pivot (webapp-only, mobile deferred). **4 of 5 P0 web fixes done**. Resume with subagent-driven-development executing Wave 2b.5 (Playwright E2E).

## State

| Item | Status |
|---|---|
| Branch | `main` (pushed through `6a8f0a3`) |
| Remote | `https://github.com/fbmoulin/kratos-suno-monorepo-.git` |
| Tests | vitest **37/37** green (was 13), backend 90/90, CDK 3/3 |
| Plan | `docs/superpowers/plans/2026-04-20-wave-2b-web-p0-fixes.md` |
| Working dir | `/home/fbmoulin/projetos-2026/kratos-suno-monorepo-v0.3.0/kratos-suno-monorepo` |
| Partial 2b.5 uncommitted | backend config + spotify_client + playwright.config + e2e/ dir + pnpm-lock (decide keep/discard before dispatching 2b.5) |

## Deep analysis conclusion (2026-04-20)

Scorecard: backend **8/10**, web **6/10**, infra **8/10**. Overall MVP: **7/10**. Ship-able for beta técnico hoje; **web precisa de 5 P0 fixes** para público geral. Rota escolhida: **B** (ship this week).

## Wave 2b progress

| # | Fix | Status | Commit(s) |
|---|---|---|---|
| 2b.1 | Mobile responsive breakpoints | ✅ DONE | `e35987b` |
| 2b.2 | Audio loading status + elapsed timer | ✅ DONE | `cc0aa2b` |
| 2b.3 | Error classification (parseApiError) | ✅ DONE | `00bde9e` + `056761b` (fix pass) |
| 2b.4 | Form validation (maxLength + MIME) | ✅ DONE | `a818b4d` + `6a8f0a3` (fix pass) |
| 2b.5 | Playwright E2E Spotify OAuth | ⏸️ NEXT | partial staged in working tree |
| 2b.6 | Docs + code review + final | 🟡 IN PROGRESS | CHANGELOG + CLAUDE.md atualizados nesta sessão |

## Lessons from 2b.3 + 2b.4 review process

**Two-stage review (spec compliance → code quality) catches distinct classes of bugs:**
- 2b.3 spec ✅ but code quality ❌: `spotifyLoginRedirect()` pointed browser at JSON endpoint (not 302) — spec strings were exact, behavior was broken. Fix: callback injection via `ParseApiErrorOptions.onReconnectSpotify`, wire `useAuth().loginWithSpotify`.
- 2b.4 spec ✅ but code quality ❌: `onDropRejected` didn't clear previously accepted file (user could accidentally submit old file after trying to replace it) + counter had no `aria-live` (invisible to screen readers). Fix: `setFile(null)` first-line in rejection handler + `role="status"` + Chakra `isInvalid` prop.

**Takeaway:** Always run both review stages. Spec-only review would have shipped both bugs.

## Resume instructions for next session

```bash
# 1. Navigate
cd /home/fbmoulin/projetos-2026/kratos-suno-monorepo-v0.3.0/kratos-suno-monorepo

# 2. Confirm state
git log --oneline -5   # expect 6a8f0a3 (or later docs commit) on top
git status             # check for partial 2b.5 staged — see notes below

# 3. Read plan (full task list) + this checkpoint
cat docs/superpowers/plans/2026-04-20-wave-2b-web-p0-fixes.md
cat docs/superpowers/CHECKPOINT-2026-04-20.md

# 4. Decide on partial 2b.5 work
#    If uncommitted: backend/app/config.py, spotify_client.py, playwright.config.ts, e2e/, pnpm-lock.yaml
#    Options:
#    (a) Discard + restart 2b.5 fresh via subagent: git checkout -- . && git clean -fd packages/web/e2e/ backend/tests/test_spotify_mock_mode.py
#    (b) Continue from partial — read the files, assess what's done, dispatch reviewer on diff
#    (c) Commit partial as-is as WIP and iterate

# 5. Resume execution
# - Use superpowers:subagent-driven-development skill
# - Dispatch implementer for Wave 2b.5 "Playwright E2E Spotify OAuth"
# - Task text: section "Fix 5" of the plan
# - Pattern: implementer → spec reviewer → code quality reviewer → commit → push
# - Warning: E2E requires backend on :8000 with SPOTIFY_MOCK_MODE=true AND Vite on :5173;
#   implementer may land code but be unable to actually RUN the E2E locally — acceptable
```

## Wave 2b.5 spec quick ref

**Backend:**
- `backend/app/config.py`: add `spotify_mock_mode: bool = False`
- `backend/app/services/spotify_client.py`: short-circuit `exchange_code_for_tokens` / `get_current_user` / `get_top_artists` when `settings.spotify_mock_mode`
  - Fixture artists: The Beatles, Radiohead, Björk + genres
  - Fixture user: `{id: "test_user", display_name: "Test Artist", country: "BR"}`
- `backend/tests/test_spotify_mock_mode.py`: 3 pytest async tests

**Web:**
- `pnpm add -D @playwright/test` + `pnpm exec playwright install chromium`
- `packages/web/playwright.config.ts`: webServer `pnpm dev`, baseURL `:5173`, Chromium only
- `packages/web/e2e/spotify-oauth.spec.ts`: single test intercepting `**/accounts.spotify.com/authorize*` via `page.route()` → forge 302 to backend callback → assert `?spotify=connected` + "Test Artist" + 3 artist names visible
- `package.json`: `"test:e2e": "playwright test"`

**Verify:**
- Backend: 93/93 (90 + 3 new)
- Web unit: 37/37 unchanged
- E2E: 1 spec written; actual run requires live stack

See plan section "Fix 5 — Playwright E2E for Spotify OAuth" for complete spec.

## After Wave 2b complete (all 5 fixes + docs)

**Day 2 of Rota B — AWS Staging Deploy** (user hands-on):
1. `cdk bootstrap aws://ACCOUNT/us-east-1`
2. `pnpm --filter @kratos-suno/infra deploy:staging`
3. Fill 3 AWS Secrets Manager entries (Anthropic, Neon DB URL, Spotify Client ID)
4. Fill 2 GitHub Actions secrets (AWS_DEPLOY_ROLE_ARN_STAGING, APP_RUNNER_SERVICE_ARN_STAGING)
5. Push to `develop` branch to trigger `backend.yml` workflow
6. Smoke test `curl <app-runner-url>/health`

## Conventions reminder

- Branch: work directly on `main` (user has explicit consent per plan)
- **NO co-authorship trailers** (per user's MEMORY.md)
- Tests must pass before commit; lint + typecheck + build also required
- Push after each commit (script: `git push`)
- Pause between commits for user review
