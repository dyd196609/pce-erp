FROM node:20-alpine

WORKDIR /app

ENV SERVICE=business

COPY deploy/package.json ./package.json
COPY deploy ./deploy
COPY frontend/src/meta ./frontend/src/meta
COPY frontend/package.json ./frontend/package.json

EXPOSE 8083

CMD ["node", "--experimental-specifier-resolution=node", "deploy/business-service/index.js"]
