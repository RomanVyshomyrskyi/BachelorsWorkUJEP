# ---- Build stage ----
FROM node:24-alpine AS builder
WORKDIR /app

COPY package*.json ./
# Run clean insyall all dependenses
RUN npm ci


COPY . .
RUN npm run build

# ---- Run stage (serve static) ----
FROM nginx:alpine

# Copy Vite build output to Nginx html directory
COPY --from=builder /app/dist /usr/share/nginx/html

# Optional: custom nginx.conf
# COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
