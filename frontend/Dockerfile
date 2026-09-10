# Build de la SPA
FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm install --no-audit --no-fund
COPY . .
RUN npm run build

# Servidor estático + proxy /api (sin root: usuario appuser, puerto 8080)
FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf

# Usuario sin privilegios y directorios temporales propios dentro del contenedor.
RUN adduser -D -H -u 1000 -s /sbin/nologin appuser \
    && chown -R appuser:appuser /usr/share/nginx/html \
    && mkdir -p /tmp/nginx && chown -R appuser:appuser /tmp/nginx \
    && rm -rf /etc/nginx/conf.d /etc/nginx/templates /docker-entrypoint.d /var/cache/nginx

USER appuser

EXPOSE 8080

ENTRYPOINT ["nginx", "-g", "daemon off;"]