FROM node:20-alpine

WORKDIR /app

ENV SERVICE=kernel

COPY deploy/package.json ./package.json
COPY deploy ./deploy
COPY frontend/src/meta ./frontend/src/meta
COPY frontend/package.json ./frontend/package.json

EXPOSE 8081

CMD ["node", "--experimental-specifier-resolution=node", "deploy/kernel-service/index.js"]
