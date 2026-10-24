# Private H-MEM sidecar. Node 22 LTS (>=22.12 for --experimental-transform-types); zero npm runtime dependencies.
FROM node:22-slim
WORKDIR /app
COPY package.json package-lock.json ./
COPY src src
COPY vendor vendor
USER node
CMD ["node", "--experimental-transform-types", "src/server.ts"]
