# W1-C Infra Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Polish AWS CDK infra + CI/CD + documentation to production-readiness without code-level changes. Five tightly-scoped tasks, disjoint from W1-A / W1-B.

**Architecture:** CloudWatch LogGroup retention policy via CDK, Docker web image pnpm fix, GitHub Actions secret sync from AWS Secrets Manager, documentation URL consistency + DNS setup section, and (deferred) Spotify profile exception logging (depends on W1-A structlog).

**Tech Stack:** AWS CDK 2.160, TypeScript, GitHub Actions, Docker, Markdown.

**Reference:** Parent spec `docs/superpowers/specs/2026-04-17-kss-hardening-pluggable-design.md` + analysis issues #5, #8, #13, #15, #20.

---

## File Structure

Modified files:
- `infra/cdk/lib/stacks/backend-stack.ts` — add LogGroup with retention
- `infra/cdk/test/backend-stack.test.ts` — assert retention present
- `packages/web/Dockerfile` — replace npm with pnpm
- `.github/workflows/web.yml` — pull shared-secret from Secrets Manager pre-build
- `docs/DEPLOYMENT.md` — URL consistency + DNS + consolidated checklist
- `backend/app/api/v1/auth_spotify.py` — log profile fetch failures (Task 5, post-W1-A)

---

## Task 1: CloudWatch Log retention in CDK

**Files:**
- Modify: `infra/cdk/lib/stacks/backend-stack.ts`
- Modify: `infra/cdk/test/backend-stack.test.ts`

- [ ] **Step 1: Add RetentionDays import**

At top of `backend-stack.ts`:
```typescript
import * as logs from "aws-cdk-lib/aws-logs";
```

- [ ] **Step 2: Create LogGroup with retention**

Before the `apprunner.CfnService` definition, add:
```typescript
const logGroup = new logs.LogGroup(this, "BackendLogGroup", {
  logGroupName: `/aws/apprunner/kratos-suno-backend-${environment}`,
  retention: environment === "prod"
    ? logs.RetentionDays.THREE_MONTHS
    : logs.RetentionDays.ONE_MONTH,
  removalPolicy: cdk.RemovalPolicy.DESTROY,
});
```

Note: App Runner creates its own log group automatically at `/aws/apprunner/<service-name>/...`. Creating the LogGroup explicitly (CDK-managed) with the same name claims ownership BEFORE App Runner's auto-creation, so retention applies.

- [ ] **Step 3: Update test**

Add to `backend-stack.test.ts`:
```typescript
test("LogGroup has retention policy", () => {
  const template = Template.fromStack(stack);
  template.hasResourceProperties("AWS::Logs::LogGroup", {
    RetentionInDays: 30,  // ONE_MONTH for staging
  });
});
```

- [ ] **Step 4: Run CDK test**

```bash
cd infra/cdk && pnpm test
```
Expected: test passes

- [ ] **Step 5: Synth check**

```bash
cd infra/cdk && npx cdk synth kratos-suno-backend-stg | grep -A2 RetentionInDays
```
Expected: `RetentionInDays: 30` present

- [ ] **Step 6: Commit**

```bash
git add infra/cdk/lib/stacks/backend-stack.ts infra/cdk/test/backend-stack.test.ts
git commit -m "feat(infra): CloudWatch log retention (30d stg, 90d prod)"
```

---

## Task 2: Web Dockerfile — pnpm instead of npm

**Files:**
- Modify: `packages/web/Dockerfile`

- [ ] **Step 1: Read existing Dockerfile**

Confirm current state — should be `FROM node:20-alpine AS builder` + `npm install` + `npm run build`.

- [ ] **Step 2: Rewrite with pnpm**

```dockerfile
FROM node:20-alpine AS builder

# Enable corepack for pnpm (bundled with Node 20+)
RUN corepack enable && corepack prepare pnpm@9.12.0 --activate

WORKDIR /app

# Copy workspace root files
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml* ./

# Copy only package.json of the sub-packages we need (for better layer cache)
COPY packages/core/package.json ./packages/core/
COPY packages/web/package.json ./packages/web/

RUN pnpm install --frozen-lockfile --filter @kratos-suno/web...

# Copy source
COPY packages/core ./packages/core
COPY packages/web ./packages/web
COPY tsconfig.base.json ./ 2>/dev/null || true

# Build
RUN pnpm --filter @kratos-suno/web run build

# Runtime: nginx
FROM nginx:alpine
COPY --from=builder /app/packages/web/dist /usr/share/nginx/html
COPY packages/web/nginx.conf /etc/nginx/conf.d/default.conf 2>/dev/null || true
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

(Note: build context must be monorepo root, not packages/web. Update `web.yml` build step accordingly if needed.)

- [ ] **Step 3: Build locally to validate**

```bash
cd /path/to/monorepo-root
docker build -f packages/web/Dockerfile -t kratos-suno-web-test .
```
Expected: build succeeds.

- [ ] **Step 4: Run container smoke test**

```bash
docker run --rm -d --name web-test -p 8080:80 kratos-suno-web-test
sleep 2
curl -sf http://localhost:8080/ | head -c 300
docker stop web-test
```
Expected: HTML with `<div id="root">` or similar.

- [ ] **Step 5: Commit**

```bash
git add packages/web/Dockerfile
git commit -m "fix(web): Dockerfile uses pnpm via corepack + workspace-aware build"
```

---

## Task 3: Docs URL consistency + DNS + checklist

**Files:**
- Modify: `docs/DEPLOYMENT.md`

- [ ] **Step 1: Audit URLs**

Grep for URLs in `docs/DEPLOYMENT.md`. Identify inconsistencies:
- Web URL: should be `kratos-suno.felipemoulin.com` (no "api" prefix)
- API URL: should be `api.kratos-suno.felipemoulin.com`
- Ensure these two are used consistently throughout

```bash
grep -n "felipemoulin" docs/DEPLOYMENT.md
```

- [ ] **Step 2: Normalize URLs**

Replace any instance where web and API are conflated. Explicit mentions everywhere.

- [ ] **Step 3: Add DNS Setup section**

Add new section before "Deployment Steps":
```markdown
## DNS Setup

Assuming custom domain `example.com`:

1. **Web** (Cloudflare Pages): in Cloudflare dashboard → Pages → project → Custom domain.
   Cloudflare auto-creates the CNAME — no manual DNS needed if zone is already on Cloudflare.

2. **API** (App Runner): 
   - Get the AppRunner default URL (e.g. `abc123.us-east-1.awsapprunner.com`).
   - In Route 53 or your DNS: create `CNAME api.example.com → abc123.us-east-1.awsapprunner.com`.
   - In App Runner console → Custom domains → add `api.example.com`. AWS provisions ACM cert automatically (1-2 hours).
```

- [ ] **Step 4: Add consolidated prerequisites checklist**

Add at top of DEPLOYMENT.md:
```markdown
## Prerequisites Checklist

Before starting, have ALL of these ready:

- [ ] AWS account with billing enabled + admin user
- [ ] AWS CLI v2 installed (`aws --version`)
- [ ] Node.js 20+ and pnpm 9+ installed globally (`corepack enable`)
- [ ] AWS CDK CLI (`npm install -g aws-cdk`)
- [ ] Docker Desktop OR Docker Engine 20+
- [ ] Anthropic API key ($20 minimum balance recommended)
- [ ] Domain registered (Route 53, Cloudflare, or any)
- [ ] Cloudflare account (free tier OK)
- [ ] Neon account (free tier OK)
- [ ] GitHub repo fork/clone with Actions enabled
- [ ] Expo account (for mobile; optional for backend-only)
- [ ] Apple Developer account + App Store Connect (for iOS submit; optional)
- [ ] Google Play Console + service account JSON (for Android submit; optional)
```

- [ ] **Step 5: Commit**

```bash
git add docs/DEPLOYMENT.md
git commit -m "docs: URL consistency + DNS setup + prerequisites checklist"
```

---

## Task 4: Secret sync — GH Actions pulls shared-secret from AWS

**Files:**
- Modify: `.github/workflows/web.yml`

- [ ] **Step 1: Add AWS credentials step + secrets fetch**

Before the Vite build step in web.yml, add:
```yaml
      - name: Configure AWS credentials (staging)
        if: github.ref == 'refs/heads/develop' || github.event_name == 'pull_request'
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_DEPLOY_ROLE_ARN_STAGING }}
          aws-region: us-east-1

      - name: Configure AWS credentials (production)
        if: github.ref == 'refs/heads/main'
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_DEPLOY_ROLE_ARN_PROD }}
          aws-region: us-east-1

      - name: Fetch shared-secret from Secrets Manager
        id: shared-secret
        run: |
          ENV=$([[ "${{ github.ref }}" == "refs/heads/main" ]] && echo "prod" || echo "stg")
          SECRET=$(aws secretsmanager get-secret-value \
            --secret-id "kratos-suno-${ENV}/shared-secret" \
            --query SecretString --output text)
          echo "::add-mask::$SECRET"
          echo "value=$SECRET" >> "$GITHUB_OUTPUT"
```

- [ ] **Step 2: Use the fetched secret in Vite build**

In the build step, replace:
```yaml
      - name: Build web
        env:
          VITE_API_BASE: ${{ env.VITE_API_BASE }}
          VITE_SHARED_SECRET: ${{ secrets.VITE_SHARED_SECRET }}
        run: pnpm --filter @kratos-suno/web run build
```
with:
```yaml
      - name: Build web
        env:
          VITE_API_BASE: ${{ env.VITE_API_BASE }}
          VITE_SHARED_SECRET: ${{ steps.shared-secret.outputs.value }}
        run: pnpm --filter @kratos-suno/web run build
```

- [ ] **Step 3: Update docs**

In DEPLOYMENT.md, note that `VITE_SHARED_SECRET` GitHub Secret is **no longer needed** — pulled from AWS Secrets Manager dynamically.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/web.yml docs/DEPLOYMENT.md
git commit -m "ci(web): fetch VITE_SHARED_SECRET from AWS Secrets Manager (single source of truth)"
```

---

## Task 5 (DEFERRED — runs after W1-A merged): Spotify profile exception logging

**Files:**
- Modify: `backend/app/api/v1/auth_spotify.py`

**Precondition:** W1-A merged; structlog configured in `app.infra.logging`.

- [ ] **Step 1: Replace bare `except: profile = {}` around line 126-129**

Find the block:
```python
try:
    profile = await client.get_current_user(access_token)
except Exception:
    profile = {}
```

Replace with:
```python
import structlog
log = structlog.get_logger("spotify")

try:
    profile = await client.get_current_user(access_token)
except Exception as exc:
    log.warning("spotify.profile.fetch_failed",
                exc_type=type(exc).__name__, exc_msg=str(exc))
    profile = {}
```

- [ ] **Step 2: Verify structlog output in manual run**

```bash
cd backend
LOG_FORMAT=json uvicorn app.main:app --port 8000 &
# Trigger a flow that would fail profile fetch (e.g. malformed token)
curl ... 
# Expect a log line with event=spotify.profile.fetch_failed
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/v1/auth_spotify.py
git commit -m "fix(spotify): log profile fetch failures (was silently swallowed)"
```

---

## Done Criteria

- [ ] `cd infra/cdk && pnpm test` — all green including retention assertion
- [ ] `cd infra/cdk && cdk synth kratos-suno-backend-stg` — contains `RetentionInDays: 30`
- [ ] `docker build -f packages/web/Dockerfile -t test .` from monorepo root — succeeds
- [ ] `docs/DEPLOYMENT.md` contains "Prerequisites Checklist" + "DNS Setup" sections
- [ ] `grep -E "felipemoulin|example\.com" docs/DEPLOYMENT.md` — all instances consistent
- [ ] `.github/workflows/web.yml` has `aws-actions/configure-aws-credentials` + `get-secret-value` steps
- [ ] (Task 5 after W1-A) `structlog.get_logger("spotify")` used in auth_spotify.py

---

## Rollback

- **Task 1**: revert CDK changes; App Runner creates default log group with infinite retention (pre-existing behavior)
- **Task 2**: revert Dockerfile; `npm install` works but ignores pnpm-lock
- **Task 3**: docs changes are purely additive
- **Task 4**: revert workflow; restore `VITE_SHARED_SECRET` as GitHub repo secret (manual sync)
- **Task 5**: revert auth_spotify.py; silent exception restored (pre-existing)
