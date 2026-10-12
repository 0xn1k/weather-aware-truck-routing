FROM node:lts-alpine AS build

ENV NPM_CONFIG_UPDATE_NOTIFIER=false
ENV NPM_CONFIG_FUND=false

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . ./
# VITE_API_BASE_URL is baked into the JS bundle at build time (Vite env
# vars are not readable at runtime) — Railway must pass it as a build arg,
# not just a regular service variable. See DEPLOYMENTPLAN.md.
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM caddy
WORKDIR /app
COPY Caddyfile ./
RUN caddy fmt Caddyfile --overwrite
COPY --from=build /app/dist ./dist

CMD ["caddy", "run", "--config", "Caddyfile", "--adapter", "caddyfile"]
