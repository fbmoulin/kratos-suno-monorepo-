# Deployment — Kratos Suno Prompt

Este documento descreve o deploy de ponta a ponta em produção. A stack combina AWS (backend), Cloudflare Pages (web), Neon (Postgres serverless) e EAS (mobile).

URLs canônicas (produção):

- **Web** (Cloudflare Pages): `https://kratos-suno.felipemoulin.com`
- **API** (App Runner): `https://api.kratos-suno.felipemoulin.com`

Use-as explicitamente sempre que o documento precisar referenciar os endpoints — nunca conflate web e API no mesmo hostname.

## Prerequisites Checklist

Antes de iniciar, tenha TODOS estes itens prontos:

- [ ] AWS account com billing ativo + usuário admin
- [ ] AWS CLI v2 instalada (`aws --version`)
- [ ] Node.js 20+ e pnpm 9+ instalados globalmente (`corepack enable`)
- [ ] AWS CDK CLI (`npm install -g aws-cdk`)
- [ ] Docker Desktop OU Docker Engine 20+
- [ ] Anthropic API key (saldo mínimo recomendado: $20)
- [ ] Domínio registrado (Route 53, Cloudflare ou qualquer registrar)
- [ ] Cloudflare account (tier free resolve)
- [ ] Neon account (tier free resolve)
- [ ] GitHub repo (fork/clone) com Actions habilitadas
- [ ] Expo account (para mobile; opcional se for só backend)
- [ ] Apple Developer account + App Store Connect (para submit iOS; opcional)
- [ ] Google Play Console + service account JSON (para submit Android; opcional)

## Visão geral de custos

Stage 1 (pessoal/staging) fica em torno de $30–70/mês, dominado pelo custo da API Anthropic (~$10–40/mês com cap de $2/dia configurado no backend). A infra em si sai em torno de $20–30: App Runner com 0.25 vCPU auto-scale ($20–25), Cloudflare Pages gratuito, Neon free tier, Route 53 $0.50/mês por hosted zone.

Stage 3 (B2B com ~50 usuários pagos) projeta $300–400/mês total, ainda dominado pela API Anthropic com ~$150 proporcional ao uso. Detalhes da composição em `docs/MONOREPO.md` e no ADR 001.

## Pré-requisitos para primeiro deploy

Você precisa de uma conta AWS ativa com billing configurado, um domínio registrado (Route 53 ou outro registrar compatível), uma conta Cloudflare (Pages é grátis), uma conta Neon (tier free resolve Stage 1), e uma API key da Anthropic. Opcional mas recomendado: um app no Spotify Developer Dashboard para ativar a aba "Meu Spotify", e um domínio custom pra evitar a URL default `xxx.awsapprunner.com` em prod.

## Setup inicial AWS

O primeiro passo é bootstrap do CDK. Na pasta `infra/cdk`, com credenciais AWS carregadas (`aws configure` ou `aws sso login`), rode `npx cdk bootstrap aws://ACCOUNT_ID/us-east-1`. Isso cria o S3 bucket de assets do CDK. Faça uma vez por conta+região.

Com o bootstrap feito, `pnpm cdk:synth` valida que as stacks compilam. `pnpm cdk:diff --context env=staging` mostra o que vai mudar. `pnpm cdk:deploy:staging` cria de fato — a primeira vez demora ~5 minutos principalmente pela criação do App Runner.

Depois do deploy, o CDK imprime outputs com URL do App Runner, ARN do service, URI do ECR e o ARN do role OIDC. Copie todos para algum lugar seguro — você vai colar em GitHub Secrets na próxima etapa.

## Preencher os secrets

O CDK cria quatro secrets no Secrets Manager, mas deixa vazios (design intencional — não queremos valores sensíveis no state do CloudFormation). Preencha via AWS Console ou CLI. O `shared-secret` já vem gerado automaticamente — apenas leia e copie para o frontend. Os outros três você preenche:

```bash
aws secretsmanager put-secret-value \
  --secret-id kratos-suno/staging/anthropic-api-key \
  --secret-string "sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxx"

aws secretsmanager put-secret-value \
  --secret-id kratos-suno/staging/database-url \
  --secret-string "postgresql+asyncpg://user:pass@ep-xxx.us-east-1.aws.neon.tech/kratos_suno?sslmode=require"

aws secretsmanager put-secret-value \
  --secret-id kratos-suno/staging/spotify-client-id \
  --secret-string "seu_client_id_do_spotify"
```

Após preencher, force um redeploy do App Runner — ele só relê secrets em startup de container novo. Use `aws apprunner start-deployment --service-arn <ARN>` ou simplesmente faça push de uma imagem nova.

## Setup Neon

Crie o projeto em neon.tech. Escolha região próxima do App Runner (us-east-1 se o resto tá lá). A free tier dá 3GB, autopause automático — dorme em 5min de idle, acorda em ~1s no próximo request (aceitável pro staging). A connection string aparece no painel com formato `postgresql://user:pass@host/db?sslmode=require`. Converta para asyncpg trocando `postgresql://` por `postgresql+asyncpg://` antes de colocar no secret.

Rode as migrations localmente apontando para o Neon: `cd backend && alembic -x url="<neon_url>" upgrade head`. Idealmente adicione uma step no workflow `backend.yml` para rodar migrations automaticamente antes do deploy, mas no Stage 1 manual tá ok.

## Setup Spotify (opcional)

Em developer.spotify.com/dashboard, crie um app. Em "Redirect URIs", adicione `https://<app-runner-url>/api/v1/auth/spotify/callback` (use a URL real do App Runner após o primeiro deploy). Copie o Client ID para o secret. **Não precisa de Client Secret** — o flow é PKCE. Se for usar domínio custom, adicione o URI do custom domain também.

## Setup do frontend (Cloudflare Pages)

No dashboard Cloudflare, vá em Workers & Pages → Create → Pages → Connect to Git. Aponte pro repo do GitHub. Configure:

- Build command: `pnpm install && pnpm --filter @kratos-suno/core build && pnpm --filter @kratos-suno/web build`
- Build output directory: `packages/web/dist`
- Root directory: deixe vazio (monorepo root)
- Environment variables: `VITE_API_BASE=https://api.kratos-suno.felipemoulin.com` (URL da API — ajuste para o seu domínio), `VITE_SHARED_SECRET=<valor do secret shared-secret>`

Opcional: Cloudflare pode conectar direto ao GitHub para auto-deploy. Alternativa: usar o workflow `web.yml` que faz deploy via wrangler action (precisa do `CLOUDFLARE_API_TOKEN` e `CLOUDFLARE_ACCOUNT_ID` nos secrets do GitHub).

## Setup GitHub Actions

No repo GitHub, vá em Settings → Secrets and variables → Actions. Adicione:

Para o workflow de backend: `AWS_DEPLOY_ROLE_ARN_STAGING` e `AWS_DEPLOY_ROLE_ARN_PROD` (vem do output `GitHubActionsRoleArn` da CicdStack), `APP_RUNNER_SERVICE_ARN_STAGING` e `APP_RUNNER_SERVICE_ARN_PROD` (output `ServiceArn` da BackendStack).

Para o web: `CLOUDFLARE_API_TOKEN` (criado em dash.cloudflare.com/profile/api-tokens com scope "Cloudflare Pages:Edit"), `CLOUDFLARE_ACCOUNT_ID` (aparece no dashboard). **Nota:** `VITE_SHARED_SECRET` NÃO precisa ser adicionado como GitHub Secret — o workflow `web.yml` busca dinamicamente do AWS Secrets Manager (`kratos-suno/${env}/shared-secret`) via OIDC, usando o mesmo role de deploy. Single source of truth, zero drift.

Para o mobile: `EXPO_TOKEN` (expo.dev → settings → access tokens).

Em Settings → Environments, crie `production` e ative "Required reviewers" adicionando você mesmo — isso força aprovação manual antes de deploys pra prod.

## DNS Setup

Assumindo domínio custom `felipemoulin.com` (substitua pelo seu):

1. **Web** (`kratos-suno.felipemoulin.com`, Cloudflare Pages): no dashboard Cloudflare → Pages → projeto → Custom domain → adicionar `kratos-suno.felipemoulin.com`.
   Cloudflare auto-cria o CNAME — sem DNS manual se a zona já está na Cloudflare. Certificado emitido automaticamente (Universal SSL).

2. **API** (`api.kratos-suno.felipemoulin.com`, App Runner):
   - Capture a URL default do App Runner (ex: `abc123.us-east-1.awsapprunner.com`).
   - No Route 53 (ou no seu DNS): crie `CNAME api.kratos-suno.felipemoulin.com → abc123.us-east-1.awsapprunner.com`.
   - No console App Runner → Custom domains → adicione `api.kratos-suno.felipemoulin.com`. AWS provisiona certificado ACM automaticamente (1–2h para propagar).

Depois de validado, atualize a env var `VITE_API_BASE` do deploy Cloudflare Pages para `https://api.kratos-suno.felipemoulin.com` e trigger um redeploy do web.

## Fluxo de deploy típico

Push em `develop` dispara `backend.yml` (deploy staging) e `web.yml` (deploy preview no Cloudflare). Um PR pra `main` que é mergeado dispara deploy em produção (exige aprovação manual se o environment estiver configurado). Tag `v*.*.*` dispara `mobile.yml` para build de produção no EAS.

## Mobile — EAS

Primeira vez: `cd packages/mobile && eas init` para criar o projectId do EAS. Cole o UUID no `app.json` em `extra.eas.projectId`.

Para build de preview (APK standalone + IPA de simulador): `eas build --profile preview --platform all`. Leva ~15min no servidor EAS. Você recebe email com links para instalar. Use preview pra testar antes de submeter pra store.

Deep link do Spotify OAuth mobile **ainda é um open item**. O flow web redireciona pra `frontend_origin + ?spotify=connected`. Mobile precisa receber tokens via deep link `kratossuno://spotify-connected?token=XXX`. Isso exige uma rota nova no backend (`/api/v1/auth/spotify/mobile-callback`) que detecta User-Agent mobile e retorna JSON em vez de redirect. Documentado como pendência em `docs/MOBILE.md`.

## Rollback

App Runner mantém deployments anteriores. Para reverter: `aws apprunner start-deployment --service-arn <ARN>` com uma imagem ECR antiga (tag `:<sha-anterior>`). Tempo típico de rollback: 3–5min.

Para Cloudflare Pages, vá em Deployments, encontre o deploy anterior, clique em "Rollback to this deployment" — instantâneo.

## Validação pós-deploy

Seguindo o checklist da skill `aws-deploy`, a cada deploy valide: health endpoint retorna 200, latência p99 está dentro de 3s no CloudWatch, não há spike de 5xx, DNS resolve pra nova URL, certificado SSL válido. O workflow já faz a checagem de health automaticamente — se ela falhar, o deploy é marcado como failed.

## Observabilidade

Logs: CloudWatch Logs em `/aws/apprunner/kratos-suno-backend-{env}/application/`. Filtre por `level=ERROR` pra ver problemas. O backend loga estruturado em JSON (configurado em `LOG_FORMAT=json`), então Insights Queries funcionam bem.

Alarmes: três alarms CloudWatch configurados — 5xx rate, latência p99, instâncias saudáveis. Todos notificam via SNS topic que manda email pro `ALERT_EMAIL` configurado no CDK.

Budget: um AWS Budget notifica em 80% do gasto esperado e em 100% de forecast. Configurado para filtrar por tag `project=kratos-suno-prompt` para isolar o custo dos outros projetos na mesma conta AWS.

## Destruir ambiente

`pnpm cdk:destroy --context env=staging` remove tudo (App Runner, ECR, secrets, alarms). ECR tem `removalPolicy: DESTROY` em staging, `RETAIN` em prod. Secrets ficam em "pending deletion" por 30 dias antes de sumir de fato — útil se você errar e precisar recuperar.

Para prod, nunca destrua. Se precisar desligar, mude `desiredCount` do App Runner pra 0 (requires API call direta — CDK não expõe).
