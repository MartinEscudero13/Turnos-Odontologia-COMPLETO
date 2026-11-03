# syntax=docker/dockerfile:1.7
FROM node:24-alpine AS builder

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine AS runtime

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html
HEALTHCHECK --interval=15s --timeout=3s --retries=5 --start-period=5s \
  CMD wget -q -O /dev/null http://localhost/ || exit 1
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
