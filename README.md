# Kratos Suno Prompt — Monorepo v0.3.0

Gerador de prompts profissionais para Suno AI a partir de nome de artista, arquivo MP3 ou perfil Spotify do usuário. Backend FastAPI híbrido (librosa + Claude), frontend web + mobile compartilhando código TypeScript, infra-as-code em AWS CDK.

## Estrutura

```
kratos-suno-monorepo/
├── backend/                  FastAPI + Pydantic + SQLAlchemy async + Alembic
│                             Híbrido: librosa DSP + Claude Sonnet vision
│                             39 testes passando
├── packages/
│   ├── core/                 @kratos-suno/core — TS compartilhado web+mobile
│   │   ├── types/            Schemas Pydantic espelhados em TS
│   │   ├── api/              Factory de ApiClient (cookies ou bearer)
│   │   ├── hooks/            useAuth platform-agnostic
│   │   └── logic/            VARIANT_META, SOURCE_LABELS
│   ├── web/                  React + Vite + Chakra (4 abas: Texto/Áudio/Spotify/Salvos)
│   └── mobile/               Expo Router + React Native Paper (4 telas equivalentes)
├── infra/cdk/                AWS CDK TS: App Runner + ECR + Secrets + Alarms + Budget
├── .github/workflows/        3 pipelines: backend, web, mobile
├── docs/                     MONOREPO.md + DEPLOYMENT.md + MOBILE.md
├── docker-compose.dev.yml    Stack local (postgres + backend + web)
├── Makefile                  Atalhos comuns
├── package.json              pnpm workspace root
└── pnpm-workspace.yaml
```

## Quick start — dev local

Precisa de Node 20+, pnpm 9+, Python 3.12, Docker. Sem pnpm global? `corepack enable && corepack prepare pnpm@9.12.0 --activate`.

**Opção 1 — tudo via Docker (recomendado para primeiro run):**

```bash
# 1. Instala deps TS
pnpm install

# 2. Configura chave Anthropic
cp .env.example .env
# edite .env: ANTHROPIC_API_KEY=sk-ant-api03-...
# (demais vars W1 têm defaults seguros — auth disabled em dev, rate limit 100/h, budget $2/dia)

# 3. Sobe stack (postgres + backend; roda alembic upgrade head antes)
docker-compose -f docker-compose.dev.yml up -d postgres backend

# 4. Verifica saúde
curl -s http://localhost:8000/health | python -m json.tool
# → status: ok, anthropic_key: configured, budget_remaining: 2.00

# 5. Gera um prompt
curl -X POST http://localhost:8000/api/v1/generate/text \
  -H "Content-Type: application/json" \
  -d '{"subject":"Djavan"}' | python -m json.tool

# 6. Web (opcional)
docker-compose -f docker-compose.dev.yml up -d web
# → http://localhost:5173
```

**Opção 2 — web em Vite dev com HMR:**

```bash
docker-compose -f docker-compose.dev.yml up -d postgres backend
pnpm dev:web   # vite → http://localhost:5173 com proxy para 8000
```

**Opção 3 — mobile:**

```bash
cp packages/mobile/.env.example packages/mobile/.env
# EXPO_PUBLIC_API_BASE=http://<your-ip>:8000 (ou ngrok)
pnpm dev:mobile   # scan QR com Expo Go
```

**Para parar:**
```bash
docker-compose -f docker-compose.dev.yml down        # preserva dados postgres
docker-compose -f docker-compose.dev.yml down -v     # deleta volume postgres
```

## Fases do projeto

Concluídas:
- **Fase 1**: skill `suno-style-prompt.skill` para Claude Code
- **Fase 2**: app web MVP (texto + áudio)
- **Fase 3**: integração Spotify + cache Postgres + saved prompts CRUD
- **v0.3.0**: monorepo com core compartilhado, mobile Expo scaffold, AWS CDK, GitHub Actions
- **Wave 1 (atual)**: backend hardening (pluggable auth/rate-limit/budget), structlog + request-id, async audio fix, compliance heuristic, mobile Spotify deep link (JWT bearer), persistent session (survives restart), CDK log retention, web Dockerfile pnpm. **90 tests backend verdes**. Ver `CHANGELOG.md` para detalhes.

Próximas (specs/plans separadas):
- **Wave 2**: frontend tests (vitest), accessibility mobile, theme consistency, error boundaries
- **Stage 2 deploy**: Cloudflare Turnstile + Redis (Upstash) rate-limit — `RATE_LIMIT_BACKEND=redis` config flip
- **Stage 3**: Clerk auth + Postgres user quota — `AUTH_PROVIDER=clerk` + nova classe `ClerkAuthProvider`
- **Mobile v2**: mic recording, share extension, push notifications

## Docs

Ler em ordem: `docs/MONOREPO.md` → `docs/DEPLOYMENT.md` → `docs/MOBILE.md`.

## Stack decisions sumarizadas

**Backend**: AWS App Runner (não Fargate — mais simples, ~$25/mês Stage 1) + Neon Postgres (free tier com autopause) + Secrets Manager + CloudWatch.

**Frontend web**: Cloudflare Pages (não Vercel — latência BR superior, bandwidth ilimitado grátis) via wrangler action.

**Mobile**: React Native + Expo SDK 52 + Expo Router (não Flutter — reusa ~70% do TS do web) + React Native Paper + EAS Build.

**CI/CD**: GitHub Actions com OIDC (não IAM keys). Pipeline por package, paths-filtered.

**Monorepo**: pnpm workspaces (não Nx/Turbo — não temos complexidade que justifique build cache distribuído).

## Custo estimado

Stage 1 pessoal/staging: ~$30-70/mês (dominado pela Anthropic API com cap de $2/dia).

Stage 3 B2B com ~50 usuários pagos: ~$300-400/mês, proporcional ao uso Anthropic (~$150) + App Runner 1 vCPU (~$90) + infra auxiliar.

Detalhes completos em `docs/DEPLOYMENT.md`.

## Licença

MIT (seguindo projeto pai `pseuno-ai`).

## Autor

Felipe Moulin — Juiz de Direito, 2ª Vara Cível de Cariacica/ES, founder de Lex Intelligentia.
