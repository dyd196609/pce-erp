FROM node:20-alpine

WORKDIR /app

COPY frontend/package*.json ./frontend/
RUN cd frontend && npm install

COPY frontend ./frontend

WORKDIR /app/frontend

RUN npm run build

EXPOSE 3000

CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "3000"]
