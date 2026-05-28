FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf.template
COPY start.sh /start.sh
RUN chmod +x /start.sh
EXPOSE 8080
CMD ["/start.sh"]
