# ---- Stage 1: deps ----
# Bump with: docker pull node:20-alpine
FROM node:20-alpine@sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293 AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

# ---- Stage 2: build ----
FROM node:20-alpine@sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293 AS build
WORKDIR /app
# API origin the browser will call. In production the web app is served
# through nginx on the same origin, so the client bundle must inline the
# RELATIVE /api/v1 path (a build-time "http://localhost:8000" would make
# browsers call the user's own machine). Override via build arg if the web
# app is hosted separately from the API.
ARG NEXT_PUBLIC_API_URL=/api/v1
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# ---- Stage 3: runtime (standalone) ----
FROM node:20-alpine@sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293 AS runner
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
# Runtime needs Node only. Upgrade Alpine security fixes and remove npm/corepack
# so build tooling and its dependency tree are not shipped in production.
RUN apk upgrade --no-cache \
 && rm -rf /usr/local/lib/node_modules \
            /usr/local/bin/npm /usr/local/bin/npx \
            /usr/local/bin/corepack /usr/local/bin/pnpm /usr/local/bin/pnpx \
            /usr/local/bin/yarn /usr/local/bin/yarnpkg \
 && addgroup -S app \
 && adduser -S app -G app
COPY --chown=app:app --from=build /app/public ./public
COPY --chown=app:app --from=build /app/.next/standalone ./
COPY --chown=app:app --from=build /app/.next/static ./.next/static
RUN chmod -R a+rX /app/public /app/.next
USER app
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD wget -q -O - http://127.0.0.1:3000/login > /dev/null 2>&1 || exit 1
CMD ["node", "server.js"]
