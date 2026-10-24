# Private H-MEM sidecar. Supported runtime: Node >=22.12 <23 (tested on v22.16.0; Node 26 rejects --experimental-transform-types). Zero npm runtime dependencies.
FROM node:22-slim
WORKDIR /app
COPY package.json package-lock.json ./
COPY src src
COPY vendor vendor
COPY scripts scripts
RUN mkdir -p /data && chown node:node /data
USER node
CMD ["node", "--experimental-transform-types", "src/server.ts"]
