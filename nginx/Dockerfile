FROM nginx:1.27-alpine

# 移除默认配置
RUN rm /etc/nginx/conf.d/default.conf

# 复制自定义配置
COPY nginx.conf /etc/nginx/conf.d/recruitment.conf

# 前端构建产物由CI/CD阶段COPY进来或通过volume挂载
# COPY --from=frontend-builder /app/dist /usr/share/nginx/html

# 非root用户（需要nginx 1.25+）
# USER nginx

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://localhost/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
