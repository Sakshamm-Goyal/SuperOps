# Public edge: builds the React workbench and serves it with Caddy, which also reverse-proxies the API (same origin,
# so the API needs no CORS) and obtains TLS automatically when SITE_ADDRESS is a real domain.
FROM node:22-slim AS build
WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts
COPY . .
RUN npm run build

FROM caddy:2-alpine
COPY --from=build /web/dist /srv
COPY Caddyfile /etc/caddy/Caddyfile
