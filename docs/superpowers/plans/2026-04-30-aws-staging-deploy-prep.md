# AWS Staging Deploy — Pre-flight Runbook

**Status:** ⏸️ Não executado. Requer ações manuais (console AWS, Anthropic, Neon, Spotify) antes do primeiro `cdk deploy`.
**Created:** 2026-04-30 (após Wave 2b 5/5 + smoke E2E validada local)
**Cost expected:** ~$25-30/mês infra + $10-40/mês Anthropic API (cap diário $2 já no backend)

---

## 0. TL;DR — ordem de execução

1. **Decidir** conta AWS e ajustar IAM perms (10 min)
2. **Corrigir** 2 bugs de configuração no repo (5 min, faço autônomo se autorizar)
3. **Provisionar** secrets externos: Anthropic, Neon, Spotify (30-60 min, manual)
4. **Bootstrap** CDK na conta+região (5 min)
5. **Deploy** stacks staging via CDK (10-15 min)
6. **Preencher** secrets no Secrets Manager (5 min)
7. **Force redeploy** App Runner (lê secrets em startup) + smoke API (5 min)
8. **Confirmar** SNS subscription email + GitHub Actions secrets (10 min)

Total: 75-105 min de trabalho ativo, mais ~15 min de espera (App Runner cria, Neon cold-start, etc).

---

## 1. Decisão: conta AWS

A conta AWS atual carregada via CLI é `569206842420`, user `bertrand-dev`. Confirmar:

- [ ] É realmente a conta destino do staging do kratos-suno?
- [ ] Se **sim**: prosseguir; o user `bertrand-dev` precisa de policies adicionais (ver §1.1).
- [ ] Se **não**: `aws configure --profile <correct>` e `export AWS_PROFILE=<correct>` antes de qualquer comando deste runbook.

### 1.1 Policies que faltam em `bertrand-dev` (ou no user equivalente)

Atualmente o user tem: `AWSAppRunnerFullAccess`, `AmazonEC2ContainerRegistryFullAccess`, `IAMFullAccess`, `AmazonRoute53FullAccess`, `AmazonS3FullAccess`, `AmazonEC2FullAccess`.

Anexar via console IAM (Users → bertrand-dev → Add permissions → Attach policies directly):

```
AWSCloudFormationFullAccess        # CDK usa CFN
SecretsManagerReadWrite            # stack cria 4 secrets
CloudWatchFullAccess               # alarms + log groups
AmazonSNSFullAccess                # alerts topic
AWSBudgetsActionsWithAWSResourceControlAccess   # monthly budget
```

Alternativa pragmática (menos least-privilege mas mais rápido em projeto pessoal): anexar `AdministratorAccess` direto e remover quando o stack estabilizar.

---

## 2. Bugs de configuração no repo (corrigir antes do deploy)

### 2.1 `infra/cdk/lib/config/environments.ts:40,55`

```diff
-  githubRepo: "fbmou/kratos-suno-prompt",
+  githubRepo: "fbmoulin/kratos-suno-monorepo-",
```

Aparece em **STAGING e PROD**. Owner errado (`fbmou` em vez de `fbmoulin`) + repo errado (`kratos-suno-prompt` foi arquivado em 2026-04-30; canônico é `kratos-suno-monorepo-`).

**Impacto se não corrigir:** OIDC trust policy do `GitHubActionsDeployRole` rejeita `AssumeRoleWithWebIdentity` do workflow real, e CI deploy falha com `An error occurred (AccessDenied) when calling the AssumeRoleWithWebIdentity operation: Not authorized to perform sts:AssumeRoleWithWebIdentity`. CDK deploy local funciona, mas qualquer push pra `develop`/`main` quebra silenciosamente.

### 2.2 `infra/cdk/bin/app.ts:28`

```diff
-const alertEmail = process.env.ALERT_EMAIL ?? "felipe@example.com";
+const alertEmail = process.env.ALERT_EMAIL ?? "fbmoulin@gmail.com";
```

Atualmente o default é `felipe@example.com` (placeholder). Como mitigação independente, exportar `ALERT_EMAIL=fbmoulin@gmail.com` antes de `cdk deploy` resolve sem mexer no código.

**Impacto se não corrigir:** SNS subscription cria email confirmation pro endereço placeholder, ninguém confirma, alarms não notificam.

### 2.3 `infra/cdk/lib/config/environments.ts:39` (revisar antes de deploy)

```ts
frontendOrigin: "https://staging.kratos-suno.pages.dev",
```

URL é placeholder do Cloudflare Pages projeto que ainda não existe. CORS permite só essa origem em runtime. Se o front for deployado em outro hostname (ex: Vercel preview), o backend rejeita requests CORS.

**Ação:** decidir hostname do frontend staging primeiro, atualizar aqui, **depois** deploy. Ou aceitar este como provisório e atualizar depois (require redeploy CDK).

---

## 3. Provisionar secrets externos

### 3.1 Anthropic API key

1. Login em `console.anthropic.com`.
2. Settings → API Keys → Create Key. Nome sugerido: `kratos-suno-staging`.
3. **Adicionar saldo:** mínimo $20 recomendado. Cap diário do app está em $2/dia (env var `DAILY_BUDGET_USD`), então o teto teórico mensal é $60.
4. Copiar key `sk-ant-api03-...` para um password manager temporário. **Nunca commitar nem colar em chat.**

### 3.2 Neon Postgres

1. Login em `neon.tech`.
2. New Project → nome `kratos-suno-staging`, região `us-east-1` (alinha com App Runner para minimizar latência).
3. Database name: `kratos_suno`.
4. Connection string format mostrado no painel: `postgresql://user:pass@ep-xxx.us-east-1.aws.neon.tech/kratos_suno?sslmode=require`.
5. **Converter** para asyncpg: `postgresql+asyncpg://user:pass@ep-xxx.us-east-1.aws.neon.tech/kratos_suno?sslmode=require`.
6. Tier free: 3 GB storage, autopause em 5 min idle, cold start ~1s. OK para staging.

### 3.3 Spotify Developer App

1. Login em `developer.spotify.com/dashboard`.
2. Create app → nome `kratos-suno-staging`. Type: Web API.
3. **Redirect URIs:** adicionar a URL real do App Runner depois do primeiro deploy. Para começar, adicionar placeholder `http://localhost:8000/api/v1/auth/spotify/callback` (vai precisar update após deploy).
4. Copiar `Client ID` apenas. **Não precisa de Client Secret** — o flow é PKCE (vide `backend/app/services/pkce_utils.py`).

### 3.4 Migrations no Neon

Antes do App Runner subir, banco precisa ter schema:

```bash
cd backend
DATABASE_URL="postgresql+asyncpg://user:pass@ep-xxx.us-east-1.aws.neon.tech/kratos_suno?sslmode=require" \
  alembic upgrade head
# expected: 003_user_session (head)
```

Idempotente. Pode rodar a qualquer momento depois do Neon estar provisionado.

---

## 4. CDK bootstrap

Uma vez por conta+região:

```bash
cd infra/cdk
export AWS_PROFILE=<seu profile>
export CDK_DEFAULT_ACCOUNT=569206842420  # ou conta correta
export CDK_DEFAULT_REGION=us-east-1
npx cdk bootstrap aws://${CDK_DEFAULT_ACCOUNT}/${CDK_DEFAULT_REGION}
```

Cria stack `CDKToolkit` (S3 bucket de assets + IAM roles `cdk-hnb659fds-*`). Custo ~$0.05/mês.

---

## 5. Deploy stacks

```bash
cd infra/cdk
export ALERT_EMAIL=fbmoulin@gmail.com  # ou já corrigido em §2.2
pnpm cdk:diff --context env=staging   # preview do que vai criar
pnpm cdk:deploy:staging                # cria de fato
```

Outputs esperados (anotar todos — vão pra GitHub Secrets em §8):

```
kratos-suno-backend-staging.AppRunnerServiceUrl    = https://xxx.us-east-1.awsapprunner.com
kratos-suno-backend-staging.AppRunnerServiceArn    = arn:aws:apprunner:...
kratos-suno-backend-staging.EcrRepositoryUri       = 569206842420.dkr.ecr.us-east-1.amazonaws.com/kratos-suno-staging
kratos-suno-backend-staging.SharedSecretArn        = arn:aws:secretsmanager:...
kratos-suno-cicd-staging.GitHubActionsRoleArn      = arn:aws:iam::569206842420:role/...
```

Tempo: ~5-8 min (App Runner é o gargalo).

**Se falhar:** o erro mais comum é falta de perm IAM — mensagem do CFN identifica qual policy. Anexar policy faltante e re-rodar.

---

## 6. Preencher secrets no Secrets Manager

CDK criou 4 secrets vazios (design — evita expor secrets em CFN state). Preencher 3 (o `shared-secret` é gerado pelo CDK):

```bash
aws secretsmanager put-secret-value \
  --secret-id kratos-suno/staging/anthropic-api-key \
  --secret-string "sk-ant-api03-XXXXXXXXXXXXXXXXXXXX"

aws secretsmanager put-secret-value \
  --secret-id kratos-suno/staging/database-url \
  --secret-string "postgresql+asyncpg://user:pass@ep-xxx.us-east-1.aws.neon.tech/kratos_suno?sslmode=require"

aws secretsmanager put-secret-value \
  --secret-id kratos-suno/staging/spotify-client-id \
  --secret-string "<seu_client_id_do_spotify>"
```

Verificar shared-secret (gerado pelo CDK):

```bash
aws secretsmanager get-secret-value \
  --secret-id kratos-suno/staging/shared-secret \
  --query SecretString --output text
# Copiar o valor — vai em VITE_SHARED_SECRET no Cloudflare Pages
```

---

## 7. Force redeploy + smoke API

App Runner só relê secrets em startup de container novo:

```bash
SERVICE_ARN=<output AppRunnerServiceArn de §5>
aws apprunner start-deployment --service-arn $SERVICE_ARN
# wait ~3 min
```

Smoke:

```bash
URL=<output AppRunnerServiceUrl de §5>
curl -s $URL/health
# expected: {"status":"ok","app":"kratos-suno-prompt","checks":{"anthropic_key":"configured",...}}
```

Smoke `/api/v1/generate/text`:

```bash
curl -X POST $URL/api/v1/generate/text \
  -H "Content-Type: application/json" \
  -d '{"subject": "Djavan"}' | jq
# expected: variants array com 3 elementos, sonic_dna populated
```

Se Anthropic key estiver inválida → 502 com `{"detail": "anthropic_api_error"}`. Verificar secret + force redeploy.

---

## 8. GitHub Actions secrets

Em `github.com/fbmoulin/kratos-suno-monorepo-/settings/secrets/actions`, adicionar:

| Secret | Valor | Origem |
|---|---|---|
| `AWS_DEPLOY_ROLE_ARN_STAGING` | `arn:aws:iam::569206842420:role/...` | output `GitHubActionsRoleArn` da CicdStack §5 |
| `APP_RUNNER_SERVICE_ARN_STAGING` | `arn:aws:apprunner:us-east-1:...` | output `AppRunnerServiceArn` §5 |
| `CLOUDFLARE_API_TOKEN` | (criado em dash.cloudflare.com/profile/api-tokens, scope "Pages:Edit") | Cloudflare |
| `CLOUDFLARE_ACCOUNT_ID` | (Cloudflare dashboard right sidebar) | Cloudflare |

**Não precisa adicionar** `VITE_SHARED_SECRET` — o workflow `web.yml` lê do Secrets Manager via OIDC (vide CLAUDE.md "single source of truth").

---

## 9. Confirmar SNS subscription

Email com subject "AWS Notification - Subscription Confirmation" cai no `ALERT_EMAIL` em até 1 min após `cdk deploy`. Click "Confirm subscription" no email. Sem isso, alarms não notificam.

Verificar:

```bash
aws sns list-subscriptions-by-topic \
  --topic-arn $(aws cloudformation describe-stack-resources \
    --stack-name kratos-suno-backend-staging \
    --logical-resource-id AlertsTopic3414BE91 \
    --query 'StackResources[0].PhysicalResourceId' --output text)
# SubscriptionArn deve ser ARN real, não "PendingConfirmation"
```

---

## 10. Atualizar Spotify Redirect URI

Após §5 conhecer a URL App Runner:

1. Voltar em `developer.spotify.com/dashboard` → app `kratos-suno-staging` → Edit Settings.
2. Em Redirect URIs, adicionar `https://<app-runner-url>/api/v1/auth/spotify/callback` (do output §5).
3. Save.

---

## 11. Cloudflare Pages (frontend staging)

Fora do escopo deste runbook (é setup de plataforma, não AWS). Resumo em `docs/DEPLOYMENT.md` §"Setup do frontend (Cloudflare Pages)".

---

## Verificação final (Definition of Done)

- [ ] `curl https://<app-runner-url>/health` retorna 200 com `anthropic_key=configured`
- [ ] `curl -X POST .../api/v1/generate/text -d '{"subject":"Coldplay"}'` retorna 200 com 3 variantes
- [ ] SNS subscription confirmada (email clicked)
- [ ] CloudWatch alarms `OK` (não `INSUFFICIENT_DATA`) após primeiro tráfego
- [ ] GitHub Actions: push test em branch dispara workflow `backend.yml` e termina green
- [ ] Spotify OAuth login redirect funciona (tela de consent → callback → `/?spotify=connected`)

---

## Rollback / Cleanup

Stack pode ser destruído sem efeitos colaterais (não há dados de produção):

```bash
cd infra/cdk
pnpm cdk:destroy:staging
# CDK pergunta confirmação por stack. Sim em ambos.
```

Não derruba o `CDKToolkit` (one-time bootstrap, queremos manter).

Custos esperados após destroy: ~$0.05/mês (S3 do bootstrap).

---

## Notas / Lições do prep autônomo (2026-04-30)

- **CDK synth funciona sem credenciais AWS** (offline, gera templates locais). Boa fase para validar sintaxe antes de gastar tempo configurando perms.
- **CDK diff exige perm `cloudformation:DescribeStacks`** mesmo se a stack ainda não existe — falha com AccessDenied indistinguível de "stack inexistente".
- **`bertrand-dev` user name é estranho** dado que o owner Felipe Moulin usa `fbmoulin` em todo lugar. Vale confirmar se é a conta certa antes de criar recursos faturáveis.
- **`spotify_mock_mode` (Wave 2b.5) deve permanecer `false` em staging** — é só pra E2E local. O env var vem do `.env.example` com default false; nunca exportar `SPOTIFY_MOCK_MODE=true` no App Runner.
- **Custos reais a observar:** Anthropic API é o dominante. Cap diário $2 dá $60/mês teórico, mas uso típico (você mexendo de vez em quando) deve ficar abaixo de $10.
