# Mobile App — Kratos Suno Prompt

App React Native via Expo Router, reusando `@kratos-suno/core` para tipos, cliente API e hooks. Quatro telas: Texto, Áudio, Spotify, Salvos — paralelo à aba equivalente no web.

## Começando o dev local

Entre em `packages/mobile`, copie `.env.example` para `.env` e preencha `EXPO_PUBLIC_API_BASE` com a URL do seu backend (em dev, use ngrok apontado pro localhost:8000 ou o URL do App Runner de staging). Preencha `EXPO_PUBLIC_SHARED_SECRET` com o mesmo valor configurado no backend.

No terminal, `pnpm dev:mobile` (ou `pnpm start` dentro de `packages/mobile`) abre o Metro bundler e mostra um QR code. No celular, instale o app Expo Go (grátis na App Store/Play), escaneie o QR e o app carrega em hot reload.

Se quiser rodar em simulador iOS: `pnpm --filter @kratos-suno/mobile ios` (requer Xcode instalado, macOS only). Android: `pnpm --filter @kratos-suno/mobile android` (requer Android Studio com SDK). No Windows, Android funciona; iOS exige mac.

## Decisões arquiteturais

**Expo managed workflow, não bare React Native.** Prioriza velocidade de entrega. Quando precisar de um módulo nativo não disponível no Expo SDK (raro hoje — o ecossistema cobre 95% dos casos), migra para bare via `expo prebuild`. Até lá, EAS Build resolve builds iOS+Android sem abrir Xcode/Android Studio.

**Expo Router, não React Navigation direto.** File-based routing é mais limpo para um app com 4-5 telas. `app/(tabs)/text.tsx` vira a tab "Texto" automaticamente. Funciona em cima do React Navigation por baixo dos panos, então dá pra escapar se precisar.

**React Native Paper, não NativeWind/Tailwind.** Optamos por Material Design 3 via Paper por dois motivos: a biblioteca entrega componentes prontos de qualidade (TextInput, Card, Chip, SegmentedButtons, Snackbar), e nosso uso é muito "formulário + lista" — não precisa do design customizado que justificaria Tailwind. Se futuramente o design ficar muito próprio, migra pra NativeWind.

**`sessionStrategy: "bearer"` em vez de cookies.** Cookies em React Native são dolorosos — cada platform faz algo diferente, iOS perde sessão entre backgrounds, Android depende de WebView cookies. Bearer token em header `Authorization` é o padrão mobile desde sempre. Por isso o `core/api/config.ts` exposa essa opção — web usa cookies, mobile usa bearer, mesma interface de `ApiClient`.

## Deep link para Spotify OAuth

Este é o ponto mais delicado do mobile hoje. O fluxo web funciona assim: user clica em "Conectar Spotify", backend retorna a URL de authorize, frontend faz `window.location.href = url`. Spotify redireciona pra `/api/v1/auth/spotify/callback?code=XXX`, backend troca código por tokens, seta cookie, redireciona pra `frontend_origin?spotify=connected`. Frontend detecta query param e faz refresh do auth state.

No mobile não funciona assim por três motivos. Primeiro, `WebBrowser.openAuthSessionAsync` abre um browser in-app (SFAuthenticationSession no iOS, Chrome Custom Tab no Android) que fecha ao retornar via deep link. Segundo, o app precisa ter um scheme registrado (`kratossuno://`) para capturar o retorno. Terceiro, como o backend hoje seta cookie na resposta, aquele cookie fica no browser in-app — não no app mobile — e é perdido ao fechar.

A solução, **ainda não implementada no backend**, tem essa forma: criar `/api/v1/auth/spotify/mobile-callback` que, em vez de setar cookie e redirecionar pra frontend web, emite um JWT (ou session token) e redireciona para `kratossuno://spotify-connected?token=XXX`. O `useAuth` hook no mobile captura isso via `expo-linking`, salva o token em `SecureStore`, e `getBearerToken` em `apiClient.ts` passa a usar esse token.

Enquanto isso não existe, a aba "Spotify" no mobile mostra o botão de login mas o flow quebra ao voltar ao app. Solução temporária durante o dev: use só o web pro Spotify, ou use o scheme de URL do Spotify Dashboard apontando pro URL de produção da app (requer HTTPS).

## EAS Build

Configuração em `packages/mobile/eas.json` com três perfis:

**`development`** — build de dev client (inclui Expo tools embutidas, hot reload de JS). Use quando precisar testar módulos nativos que Expo Go não suporta.

**`preview`** — build standalone APK (Android) ou IPA de simulador (iOS). Distribuído via link do EAS, instalável em qualquer device sem passar pela store. Use pra beta-testers.

**`production`** — build otimizado pra submissão na store. Auto-increment de versão a cada build.

Primeira vez: `cd packages/mobile && eas login && eas init`. O `eas init` cria um projectId — cole em `app.json` em `extra.eas.projectId`. Também atualize `"owner"` no `app.json` para o username correto da sua conta Expo (está hardcoded como `felipemoulin`).

Comandos: `eas build --profile preview --platform all` gera APK + simulator IPA, demora ~15min, você recebe email com link quando pronto. `eas build --profile production --platform all` demora o mesmo mas inclui assinatura automática para App Store + Google Play (EAS gerencia credenciais). `eas submit --profile production` envia para as stores (descomentado no workflow quando contas dev estiverem ativas).

## Permissões

iOS pede mic (gravar voz para gerar prompt — funcionalidade futura) e Documents folder (escolher MP3). Configurado em `app.json` → `ios.infoPlist`. Não pedir permissões desnecessárias: App Store reviewers rejeitam se for sobrepermissivo sem justificativa clara.

Android: `RECORD_AUDIO` e `READ_EXTERNAL_STORAGE` em `app.json` → `android.permissions`. Dispositivos Android 13+ usam permissões granulares por tipo de mídia (`READ_MEDIA_AUDIO`) — expo-document-picker já resolve, não precisa adicionar manualmente.

## Funcionalidades mobile-first planejadas

Três features que justificam o app (acima do "web empacotado"):

A primeira é gravar voz/humming direto no mic e enviar pro `/generate/audio`. Já existe no web via `MediaRecorder`, mas a UX mobile com botão "push to talk" é naturalmente melhor. Implementa com `expo-av` em ~3 horas.

A segunda é share extension iOS/Android. Usuário tá ouvindo algo no Spotify ou Apple Music, compartilha "Copiar música → Kratos Suno Prompt" e o app abre já com o nome preenchido. iOS exige target de extensão nativa (requer `expo prebuild` ou custom dev client); Android é mais simples via intent filter.

A terceira é push notification pós-geração para long-running requests, quando a gente acha worker async no backend. Hoje os requests são síncronos e rápidos (<15s), mas pra áudio pesado faria diferença. Implementa com `expo-notifications` + backend worker rodando em App Runner com API separada.

Nenhum dos três está pronto — scaffold atual entrega paridade funcional com o web. Roadmap realista: mês 4 em diante, depois do Stage 3 B2B validado.

## Troubleshooting

**Metro não encontra `@kratos-suno/core`:** 99% das vezes é o watchFolders em `metro.config.js`. Confirme que tá apontando pra workspace root (duas pastas acima de `packages/mobile`). Rode `npx expo start --clear` para limpar cache do Metro.

**"Unable to resolve module expo-clipboard":** você atualizou o pacote e esqueceu de rodar `pnpm install` na raiz. Pnpm workspaces exigem install global depois de mudanças em qualquer `package.json`.

**EAS build falha com "Authentication failed":** `eas login` de novo. Tokens expiram em ~90 dias. Para CI, gere novo token em expo.dev → Settings → Access Tokens.

**iOS simulator não abre:** Xcode precisa estar aberto e com licença aceita (`sudo xcodebuild -license accept`). Rode `npx expo run:ios` uma vez manual antes do `pnpm ios`.

**Cor/tema não atualizou:** hot reload de React Native Paper às vezes engasga em mudanças de tema. Force refresh no Expo Go (shake device → Reload).
