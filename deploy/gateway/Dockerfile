FROM node:20-alpine

WORKDIR /app

COPY deploy/package.json ./package.json
COPY deploy ./deploy
COPY frontend/src/meta ./frontend/src/meta
COPY frontend/package.json ./frontend/package.json

EXPOSE 8080

CMD ["node", "--experimental-specifier-resolution=node", "deploy/gateway/index.js"]
