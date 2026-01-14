# DEV image voor Vite + React
FROM node:20-alpine

WORKDIR /app

# Eerst deps zodat layer cache werkt
COPY web/package*.json /app/
RUN npm install

# Code komt via volume in compose
EXPOSE 5173
