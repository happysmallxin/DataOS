# DataOS Platform Frontend — 多阶段构建
# 开发: docker build --target development -t dataos-frontend:dev .
# 生产: docker build -t dataos-frontend:latest .

# ---- 开发阶段 ----
FROM node:20-alpine AS development

WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# ---- 构建阶段 ----
FROM node:20-alpine AS builder

WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

# ---- 生产阶段 ----
FROM nginx:alpine AS production

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
