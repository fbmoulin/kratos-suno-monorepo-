# Monorepo — Kratos Suno Prompt

Este repositório usa pnpm workspaces para compartilhar código entre frontend web, mobile e infra. O backend FastAPI continua como um projeto Python tradicional na raiz de `backend/`.

## Estrutura

```
kratos-suno-monorepo/
├── backend/                  Backend Python/FastAPI (fora do workspace pnpm)
├── packages/
│   ├── core/                 @kratos-suno/core — TypeScript platform-agnostic
│   ├── web/                  @kratos-suno/web — React + Vite + Chakra
│   └── mobile/               @kratos-suno/mobile — Expo Router + React Native Paper
├── infra/cdk/                @kratos-suno/infra — AWS CDK TypeScript
├── .github/workflows/        3 workflows: backend.yml, web.yml, mobile.yml
├── docs/                     Documentação
├── docker-compose.dev.yml    Stack local (postgres + backend + web)
├── Makefile                  Atalhos comuns
├── package.json              Root com scripts agregados
└── pnpm-workspace.yaml
```

## Pré-requisitos

Node 20+, pnpm 9+, Python 3.12 para o backend, Docker para rodar Postgres local. AWS CLI v2 e CDK v2 para deploy. Xcode e Android Studio só se for rodar o mobile em nativo (Expo Go cobre o dev inicial).

Instale globalmente: `npm i -g pnpm@9 aws-cdk eas-cli`.

## Primeira instalação

Na raiz, `pnpm install` resolve os três pacotes TypeScript de uma vez graças ao workspace. O backend Python é independente — entra em `backend/` e roda `pip install -r requirements.txt` separadamente (ou `docker-compose up backend` para não precisar do Python local).

## Scripts comuns (do root)

O `package.json` da raiz agrega comandos. `pnpm dev:web` sobe o Vite em `localhost:5173`. `pnpm dev:mobile` abre o Expo (escaneie QR com Expo Go). `pnpm dev:backend` sobe Postgres + FastAPI via docker-compose. `pnpm build:web` compila core e web. `pnpm typecheck` roda `tsc --noEmit` em todos os packages recursivamente. `pnpm test` dispara os testes de todos os pacotes.

Os comandos CDK são `pnpm cdk:synth`, `pnpm cdk:diff`, `pnpm cdk:deploy:staging`, `pnpm cdk:deploy:prod`.

## Sobre `@kratos-suno/core`

Este pacote é o coração do reuso web+mobile. Exporta quatro sub-módulos:

**`api/`** — `createApiClient(config)` retorna um `ApiClient` tipado. A plataforma injeta config: web usa `sessionStrategy: "cookies"` + `credentials: "include"`, mobile usa `sessionStrategy: "bearer"` + `getBearerToken` lendo de `expo-secure-store`. Mesmo conjunto de 9 métodos em ambos os lados.

**`types/`** — todos os schemas TypeScript do backend (SonicDNA, GenerateResponse, SavedPrompt, TasteProfile, etc.).

**`hooks/`** — `useAuth({ client, onOpenAuthUrl })` é platform-agnostic. Web passa `url => window.location.href = url`. Mobile passa `url => WebBrowser.openAuthSessionAsync(url, "kratossuno://spotify-connected")`.

**`logic/`** — metadata compartilhada: `VARIANT_META` (emojis, labels, cores semânticas das 3 variantes) e `SOURCE_LABELS` (text/audio/spotify_taste). Cada plataforma mapeia "semantic" → seu design system.

## Adicionando um novo pacote

Crie `packages/foo/package.json` com `"name": "@kratos-suno/foo"`. Adicione ao `pnpm-workspace.yaml` se for um namespace novo (não precisa se já estiver em `packages/*`). Para consumir `@kratos-suno/core`: `"@kratos-suno/core": "workspace:*"` em dependencies. Rode `pnpm install` no root pra criar o symlink.

## Metro (Expo) e pnpm

Expo Metro bundler não resolve symlinks do pnpm sem configuração. Se você mexer em `packages/core` e não ver a mudança no mobile, é quase certo que esqueceu de atualizar `packages/mobile/metro.config.js` — ele precisa de `watchFolders: [workspaceRoot]` e `disableHierarchicalLookup: true`. Essa config está pronta, mas se quebrar depois de uma atualização de Expo SDK, é o primeiro lugar a checar.

## Vite e pnpm

Vite resolve workspace packages nativamente via `package.json`'s `main`/`types` fields. Nada de config especial. O `packages/core/package.json` já exporta `"main": "./src/index.ts"` e funciona direto.

## Lockfile

Um único `pnpm-lock.yaml` na raiz (committed, mandatório). Nunca comite `package-lock.json` ou `yarn.lock` — eles brigam com o pnpm. CI e Docker build rodam `pnpm install --frozen-lockfile`. Se alterar um `package.json`, commite também o `pnpm-lock.yaml` atualizado.

## Backend `app/infra/` (Wave 1)

O backend ganhou um package cross-cutting para concerns de infra (auth, rate-limit, budget, logging, compliance). A arquitetura usa Protocol interfaces com factories que escolhem a implementação conforme config:

```python
# backend/app/infra/factories.py
@lru_cache
def get_auth_provider() -> AuthProvider:
    match settings.auth_provider:
        case "shared_secret": return SharedSecretAuthProvider(...)   # stage 1
        case "clerk": raise NotImplementedError("stage 3")            # futuro
        case "api_key": raise NotImplementedError("stage 4")          # futuro
```

As rotas usam `Depends(require_auth)` + `Depends(rate_limit)` + `Depends(check_budget_text|audio)` — tudo pluggable. Trocar `RATE_LIMIT_BACKEND=memory` para `redis` via env não requer mudança em código de domínio, só adicionar a classe `RedisRateLimiter(RateLimiter)`.

Merge-safe pattern em `main.py`:
```python
setup_logging(app)        # structlog + request-id middleware + global exception handler
setup_rate_limit(app)     # warm up singleton
setup_budget(app)         # warm up + startup hooks
```

Cada `setup_X(app)` é uma linha, permitindo múltiplos agents trabalharem em paralelo sem merge conflicts.

## Quando sair do monorepo

Se um pacote precisar de release independente (ex: publicar `@kratos-suno/core` no npm), você não quebra o monorepo — só adiciona `changesets` ou `semantic-release` no pacote específico. Não temos essa necessidade hoje.
