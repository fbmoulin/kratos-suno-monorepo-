# 🟡 Checkpoint — Wave 2b in Progress (2026-04-20)

**TL;DR:** MVP pivot (webapp-only, mobile deferred). 2 of 5 P0 web fixes done. Resume with subagent-driven-development executing Wave 2b.3.

## State

| Item | Status |
|---|---|
| Branch | `main` (pushed) |
| Remote | `https://github.com/fbmoulin/kratos-suno-monorepo-.git` |
| Tests | vitest 13/13 green, backend 90/90, CDK 3/3 |
| Plan | `docs/superpowers/plans/2026-04-20-wave-2b-web-p0-fixes.md` |
| Working dir | `/home/fbmoulin/projetos-2026/kratos-suno-monorepo-v0.3.0/kratos-suno-monorepo` |

## Deep analysis conclusion (2026-04-20)

Scorecard: backend **8/10**, web **6/10**, infra **8/10**. Overall MVP: **7/10**. Ship-able for beta técnico hoje; **web precisa de 5 P0 fixes** para público geral. Rota escolhida: **B** (ship this week).

## Wave 2b progress

| # | Fix | Status | Commit |
|---|---|---|---|
| 2b.1 | Mobile responsive breakpoints | ✅ DONE | `e35987b` |
| 2b.2 | Audio loading status + elapsed timer | ✅ DONE | `cc0aa2b` |
| 2b.3 | Error classification (parseApiError) | ⏸️ NEXT | — |
| 2b.4 | Form validation (maxLength + MIME) | ⏸️ | — |
| 2b.5 | Playwright E2E Spotify OAuth | ⏸️ | — |
| 2b.6 | Docs + code review + final | ⏸️ | — |

## Resume instructions for next session

```bash
# 1. Navigate
cd /home/fbmoulin/projetos-2026/kratos-suno-monorepo-v0.3.0/kratos-suno-monorepo

# 2. Confirm state
git log --oneline -3   # expect cc0aa2b on top
git status             # expect clean

# 3. Read plan (full task list)
cat docs/superpowers/plans/2026-04-20-wave-2b-web-p0-fixes.md

# 4. Resume execution
# - Use superpowers:subagent-driven-development skill (same as this session)
# - Dispatch implementer for Wave 2b.3 "Error classification (parseApiError)"
# - Task text: section "Fix 3 — Error Classification" of the plan (lines ~120-160)
# - Pattern: implementer → spec reviewer → code quality reviewer → commit → push → user checkpoint
```

## Wave 2b.3 spec quick ref

**Create:** `packages/web/src/lib/parseApiError.ts` + `.test.ts` (~8 tests)
**Modify:** `packages/web/src/App.tsx:50-59` handleError replaces raw toast with parseApiError output
**Map:** `ApiHttpError.code`/`status` → `{ title, description, status, action? }` — PT-BR messages for 401/429/402/400/413/502/timeout/network + fallback
**Verify:** vitest 21/21 green (13 + 8 new), typecheck + build + lint clean
**Commit:** `feat(web): wave 2b.3 — error classification + typed ApiHttpError handling`

See plan section "Fix 3 — Error Classification" for full spec including action-button UX for 401 (Reconectar Spotify), Retry-After countdown for 429, "meia-noite UTC" for 402.

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
