# ===== deps =====
ARG WEB_DIR=.
FROM node:20-alpine AS deps
WORKDIR /app
ARG WEB_DIR
COPY ${WEB_DIR}/package*.json ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

# ===== build =====
FROM node:20-alpine AS build
WORKDIR /app
ARG WEB_DIR
COPY --from=deps /app/node_modules ./node_modules
COPY ${WEB_DIR}/ ./
ARG VITE_API_BASE=http://localhost:8000
ENV VITE_API_BASE=$VITE_API_BASE
RUN npm run build

# ===== runtime =====
FROM node:20-alpine AS runtime
WORKDIR /app
RUN npm i -g serve
COPY --from=build /app/dist ./dist
EXPOSE 3000
CMD ["serve","-s","dist","-l","3000"]
