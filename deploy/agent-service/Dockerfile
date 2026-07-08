FROM node:20-alpine

WORKDIR /app

ENV SERVICE=agent

COPY deploy/package.json ./package.json
COPY deploy ./deploy
COPY frontend/src/meta ./frontend/src/meta
COPY frontend/package.json ./frontend/package.json

EXPOSE 8082

CMD ["node", "--experimental-specifier-resolution=node", "deploy/agent-service/index.js"]
