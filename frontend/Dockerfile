# frontend/Dockerfile
# 阶段 1: 构建
FROM node:20 AS build-stage

WORKDIR /app

# 设置 npm 镜像源，加速依赖下载 (可选，但在国内构建很有用)
RUN npm config set registry https://registry.npmmirror.com

COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

# 阶段 2: 部署
FROM nginx:alpine AS production-stage
COPY --from=build-stage /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]