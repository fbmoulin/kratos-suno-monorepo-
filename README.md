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

Precisa de Node 20+, pnpm 9+, Python 3.12, Docker.

```bash
# 1. Instala deps dos packages TS
pnpm install

# 2. Backend via Docker (Postgres + FastAPI)
cp backend/.env.example backend/.env
# edite backend/.env preenchendo ANTHROPIC_API_KEY
pnpm dev:backend

# 3. Em outro terminal — web
pnpm dev:web
# → http://localhost:5173

# 4. Em outro terminal — mobile (opcional)
cp packages/mobile/.env.example packages/mobile/.env
# edite EXPO_PUBLIC_API_BASE apontando pro backend
pnpm dev:mobile
# → escaneie QR code com Expo Go
```

## Fases do projeto

Concluídas:
- **Fase 1**: skill `suno-style-prompt.skill` para Claude Code
- **Fase 2**: app web MVP (texto + áudio)
- **Fase 3**: integração Spotify + cache Postgres + saved prompts CRUD
- **v0.3.0 (atual)**: monorepo com core compartilhado, mobile Expo scaffold, AWS CDK, GitHub Actions

Próximas (specs separadas):
- **Track A (hardening)**: SharedSecret auth, rate-limit, budget, structlog, async audio fix
- **Stage 2 deploy**: Cloudflare Turnstile + Redis (Upstash) rate-limit
- **Stage 3**: Clerk auth + Postgres user quota
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
