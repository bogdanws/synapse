# syntax=docker/dockerfile:1.7

# Stage 1: install dependencies (shared layer)
FROM node:25-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

# Stage 2: dev server with HMR (used by docker-compose)
FROM deps AS dev
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# Stage 3: production build
FROM deps AS builder
COPY . .
RUN npm run build

# Stage 4: production image - nginx serving static assets
FROM nginx:alpine AS production
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
