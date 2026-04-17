# syntax=docker/dockerfile:1.6
#
# Build context must be the monorepo root (not packages/web), so that
# pnpm workspace files are visible. Build with:
#   docker build -f packages/web/Dockerfile -t kratos-suno-web .
#
FROM node:20-alpine AS builder

# Enable corepack for pnpm (bundled with Node 20+).
RUN corepack enable && corepack prepare pnpm@9.12.0 --activate

WORKDIR /app

# Copy workspace root manifests first (better layer cache).
COPY package.json pnpm-workspace.yaml ./
# pnpm-lock.yaml may not yet be committed; glob pattern tolerates absence.
COPY pnpm-lock.yaml* ./

# Copy sub-package manifests for the packages we actually need.
COPY packages/core/package.json ./packages/core/
COPY packages/web/package.json ./packages/web/

# Install only the deps required to build the web package (+ its workspace deps).
RUN pnpm install --frozen-lockfile --filter @kratos-suno/web...

# Copy source of the packages involved in the build.
COPY packages/core ./packages/core
COPY packages/web ./packages/web

# Build (runs `tsc && vite build`). Output lands in packages/web/dist.
RUN pnpm --filter @kratos-suno/web run build

# -------- Runtime: nginx serving the static bundle --------
FROM nginx:alpine
COPY --from=builder /app/packages/web/dist /usr/share/nginx/html
COPY packages/web/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
