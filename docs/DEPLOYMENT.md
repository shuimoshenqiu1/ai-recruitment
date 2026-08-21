# AI招聘匹配系统 — 生产环境部署指南

## 目录

1. [环境要求](#1-环境要求)
2. [快速部署](#2-快速部署)
3. [环境变量详解](#3-环境变量详解)
4. [HTTPS 配置](#4-https-配置)
5. [数据库备份](#5-数据库备份)
6. [监控和日志](#6-监控和日志)
7. [常见问题排查](#7-常见问题排查)
8. [升级步骤](#8-升级步骤)
9. [回滚](#9-回滚)

---

## 1. 环境要求

### 服务器配置

| 项目 | 最低要求 | 推荐配置 |
|------|---------|---------|
| CPU | 4 核 | 8 核 |
| 内存 | 8 GB | 16 GB |
| 磁盘 | 50 GB SSD | 100 GB SSD |
| 带宽 | 5 Mbps | 20 Mbps |

> **说明**: LLM 调用为远程 API，本地不跑模型推理。如使用 Ollama 本地模型，内存建议 ≥ 32 GB。

### 操作系统

- Ubuntu 22.04 LTS（推荐）
- CentOS 8+ / Rocky Linux 8+
- Debian 12+

### 依赖软件

| 软件 | 最低版本 | 安装参考 |
|------|---------|---------|
| Docker | 20.10+ | [docs.docker.com/engine/install](https://docs.docker.com/engine/install/) |
| Docker Compose | v2.20+ | Docker Engine 自带 `docker compose` 子命令 |
| Git | 2.x | `apt install git` / `yum install git` |

### 网络要求

- 开放端口：80（HTTP）、443（HTTPS）
- 出站需联通 LLM API（如 `api.openai.com`、`api.deepseek.com`）
- 域名（可选，用于 HTTPS 证书签发）

---

## 2. 快速部署

```bash
# 1. 克隆仓库
git clone <your-repo-url> ai-recruitment
cd ai-recruitment

# 2. 创建生产环境配置
cp backend/.env.example backend/.env.production
# 编辑环境变量，填入实际值（详见第3节）
vim backend/.env.production

# 3. 创建 docker-compose.prod.yml（见下方）
# 4. 构建并启动所有服务
docker compose -f docker-compose.prod.yml up -d --build

# 5. 等待数据库就绪后执行迁移
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head

# 6. 验证服务健康
curl http://localhost/health
curl http://localhost:8000/health
# 预期返回: 200 OK

# 7. 查看服务状态
docker compose -f docker-compose.prod.yml ps
```

### docker-compose.prod.yml 参考

```yaml
version: "3.8"

services:
  postgres:
    image: pgvector/pgvector:pg15
    container_name: recruitment-postgres
    restart: always
    environment:
      POSTGRES_DB: recruitment
      POSTGRES_USER: ${POSTGRES_USER:-recruitment}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    ports:
      - "127.0.0.1:5432:5432"  # 仅本地访问
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./backend/migrations/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U recruitment"]
      interval: 10s
      timeout: 5s
      retries: 5
    deploy:
      resources:
        limits:
          memory: 2G

  redis:
    image: redis:7-alpine
    container_name: recruitment-redis
    restart: always
    command: redis-server --requirepass ${REDIS_PASSWORD} --maxmemory 512mb --maxmemory-policy allkeys-lru
    ports:
      - "127.0.0.1:6379:6379"  # 仅本地访问
    volumes:
      - redisdata:/data
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: recruitment-backend
    restart: always
    env_file:
      - ./backend/.env.production
    environment:
      - DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER:-recruitment}:${POSTGRES_PASSWORD}@postgres:5432/recruitment
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - CELERY_BROKER_URL=redis://:${REDIS_PASSWORD}@redis:6379/1
      - CELERY_RESULT_BACKEND=redis://:${REDIS_PASSWORD}@redis:6379/2
      - ENVIRONMENT=production
      - DEBUG=false
    volumes:
      - upload_data:/app/uploads
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "5"
    deploy:
      resources:
        limits:
          memory: 2G

  celery-worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: recruitment-celery
    restart: always
    env_file:
      - ./backend/.env.production
    environment:
      - DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER:-recruitment}:${POSTGRES_PASSWORD}@postgres:5432/recruitment
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - CELERY_BROKER_URL=redis://:${REDIS_PASSWORD}@redis:6379/1
      - CELERY_RESULT_BACKEND=redis://:${REDIS_PASSWORD}@redis:6379/2
      - ENVIRONMENT=production
      - DEBUG=false
    volumes:
      - upload_data:/app/uploads
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: celery -A app.tasks.celery_app worker --loglevel=warning --concurrency=4
    logging:
      driver: "json-file"
      options:
        max-size: "30m"
        max-file: "3"
    deploy:
      resources:
        limits:
          memory: 1G

  nginx:
    build:
      context: ./nginx
      dockerfile: Dockerfile
    container_name: recruitment-nginx
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/conf.d/recruitment.conf:ro
      - frontend_dist:/usr/share/nginx/html:ro
      # HTTPS 证书挂载（配置后取消注释）
      # - /etc/letsencrypt:/etc/letsencrypt:ro
    depends_on:
      - backend
    logging:
      driver: "json-file"
      options:
        max-size: "20m"
        max-file: "3"

  # 前端构建（一次性任务，构建后退出）
  frontend-builder:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      args:
        - VITE_API_BASE_URL=${FRONTEND_API_URL:-}
        - VITE_APP_TITLE=AI招聘匹配系统
        - VITE_ENVIRONMENT=production
    container_name: recruitment-frontend-builder
    volumes:
      - frontend_dist:/app/dist
    # 构建完成后容器自动退出
    profiles:
      - build

volumes:
  pgdata:
  redisdata:
  upload_data:
  frontend_dist:
```

**首次部署时需先构建前端**：

```bash
# 构建前端静态文件
docker compose -f docker-compose.prod.yml --profile build run --rm frontend-builder

# 再启动所有服务
docker compose -f docker-compose.prod.yml up -d
```

---

## 3. 环境变量详解

### 后端 (`backend/.env.production`)

| 变量 | 必填 | 说明 | 示例/生成方式 |
|------|:----:|------|-------------|
| `SECRET_KEY` | ✅ | JWT 签名密钥，至少 32 字符 | `openssl rand -hex 32` |
| `DATABASE_URL` | ✅ | PostgreSQL 连接串（容器间通信） | `postgresql+asyncpg://recruitment:<密码>@postgres:5432/recruitment` |
| `REDIS_URL` | ✅ | Redis 连接（含密码） | `redis://:<密码>@redis:6379/0` |
| `ENVIRONMENT` | ✅ | 运行环境，必须设为 `production` | `production` |
| `DEBUG` | ✅ | 生产必须关闭 | `false` |
| `DEFAULT_LLM_PROVIDER` | ✅ | LLM 提供商 | `openai` / `azure` / `local` |
| `OPENAI_API_KEY` | ⚠️ | OpenAI API Key（使用 OpenAI 时必填） | `sk-proj-xxxx...` |
| `OPENAI_MODEL` | — | 模型名称 | `gpt-4o`（默认） |
| `AZURE_OPENAI_API_KEY` | ⚠️ | Azure Key（使用 Azure 时必填） | |
| `AZURE_OPENAI_ENDPOINT` | ⚠️ | Azure 端点 | `https://your-resource.openai.azure.com` |
| `LOCAL_LLM_API_BASE` | ⚠️ | 本地模型端点（使用 Ollama 时必填） | `http://host.docker.internal:11434/v1` |
| `LOCAL_LLM_MODEL` | ⚠️ | 本地模型名 | `qwen2.5:14b` |
| `CORS_ORIGINS` | ⚠️ | 允许的前端域名（JSON 数组） | `["https://your-domain.com"]` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | — | Token 过期时间（分钟） | `1440`（24小时） |
| `CELERY_BROKER_URL` | ✅ | Celery Broker（Redis） | `redis://:<密码>@redis:6379/1` |
| `CELERY_RESULT_BACKEND` | ✅ | Celery 结果存储 | `redis://:<密码>@redis:6379/2` |
| `MAX_FILE_SIZE` | — | 最大上传文件（字节） | `20971520`（20MB） |
| `EMBEDDING_MODEL` | — | 向量嵌入模型 | `text-embedding-3-small` |

### Docker Compose 级别变量（`.env` 或 shell export）

| 变量 | 必填 | 说明 |
|------|:----:|------|
| `POSTGRES_PASSWORD` | ✅ | PostgreSQL 密码（`openssl rand -base64 24`） |
| `REDIS_PASSWORD` | ✅ | Redis 密码（`openssl rand -base64 24`） |
| `FRONTEND_API_URL` | — | 前端编译时 API 地址（留空则走同域反代） |

### 生产环境变量生成脚本

```bash
#!/bin/bash
# generate-secrets.sh — 生成生产密钥

echo "SECRET_KEY=$(openssl rand -hex 32)"
echo "POSTGRES_PASSWORD=$(openssl rand -base64 24 | tr -d '=+/')"
echo "REDIS_PASSWORD=$(openssl rand -base64 24 | tr -d '=+/')"
```

> ⚠️ **铁律**：绝不将真实密钥提交到 Git。使用 `.gitignore` 排除 `.env.production`。

---

## 4. HTTPS 配置

### 方案 A：Certbot + Nginx（直接在服务器上）

适合单台服务器部署，域名直接解析到服务器 IP。

```bash
# 1. 安装 Certbot
apt install certbot python3-certbot-nginx

# 2. 停止 nginx 容器（释放 80 端口）
docker compose -f docker-compose.prod.yml stop nginx

# 3. 申请证书
certbot certonly --standalone -d your-domain.com -d www.your-domain.com

# 4. 证书路径
# /etc/letsencrypt/live/your-domain.com/fullchain.pem
# /etc/letsencrypt/live/your-domain.com/privkey.pem
```

修改 `nginx/nginx.conf`，添加 HTTPS server block：

```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate     /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # 现代 SSL 配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;

    # HSTS
    add_header Strict-Transport-Security "max-age=63072000" always;

    # ... 其余 location 配置与 nginx.conf 相同 ...
}
```

在 `docker-compose.prod.yml` 的 nginx 服务中挂载证书：

```yaml
volumes:
  - /etc/letsencrypt:/etc/letsencrypt:ro
```

设置自动续期：

```bash
# /etc/cron.d/certbot-renew
0 3 * * * root certbot renew --pre-hook "docker compose -f /path/to/docker-compose.prod.yml stop nginx" --post-hook "docker compose -f /path/to/docker-compose.prod.yml start nginx"
```

### 方案 B：云负载均衡器终结 SSL（推荐）

适合 AWS ALB / 阿里云 SLB / Cloudflare 等场景。

**优势**：
- 证书自动续期（云平台托管）
- Nginx 容器只需监听 80
- 无需在服务器上管理证书文件
- 轻松扩展到多实例

**配置步骤**：
1. 在云平台创建负载均衡器
2. 配置 HTTPS 监听器（443 → 后端 80）
3. 上传/申请 SSL 证书
4. 将域名 DNS 指向负载均衡器
5. Nginx 保持监听 80 端口即可
6. （可选）在 Nginx 中通过 `X-Forwarded-Proto` 判断并强制 HTTPS：

```nginx
if ($http_x_forwarded_proto != "https") {
    return 301 https://$host$request_uri;
}
```

---

## 5. 数据库备份

### 自动备份脚本

```bash
#!/bin/bash
# /opt/scripts/backup-db.sh
# 每天执行，保留最近 30 天备份

set -euo pipefail

BACKUP_DIR="/backups/postgres"
DAYS_KEEP=30
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/recruitment_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

# 执行备份
docker compose -f /path/to/docker-compose.prod.yml exec -T postgres \
  pg_dump -U recruitment -d recruitment --no-owner --no-acl | \
  gzip > "$BACKUP_FILE"

# 验证备份文件大小（> 1KB 表示非空）
if [ $(stat -f%z "$BACKUP_FILE" 2>/dev/null || stat -c%s "$BACKUP_FILE") -lt 1024 ]; then
  echo "ERROR: Backup file is suspiciously small!" >&2
  exit 1
fi

# 清理过期备份
find "$BACKUP_DIR" -name "recruitment_*.sql.gz" -mtime +${DAYS_KEEP} -delete

echo "Backup completed: $BACKUP_FILE ($(du -sh "$BACKUP_FILE" | cut -f1))"
```

### Crontab 配置

```bash
# 每天凌晨 2:00 执行备份
0 2 * * * /opt/scripts/backup-db.sh >> /var/log/db-backup.log 2>&1
```

### 手动备份和恢复

```bash
# 手动备份
docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U recruitment -d recruitment | gzip > backup_manual.sql.gz

# 恢复备份
gunzip -c backup_manual.sql.gz | \
  docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U recruitment -d recruitment
```

> **建议**：生产环境将备份文件同步到对象存储（S3 / OSS），避免服务器故障导致备份丢失。

---

## 6. 监控和日志

### 日志查看

```bash
# 所有服务日志
docker compose -f docker-compose.prod.yml logs -f

# 特定服务
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f celery-worker
docker compose -f docker-compose.prod.yml logs -f postgres

# 最近 100 行
docker compose -f docker-compose.prod.yml logs --tail=100 backend
```

### 日志轮转

已在 `docker-compose.prod.yml` 中配置：

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "50m"   # 单文件最大 50MB
    max-file: "5"     # 最多保留 5 个文件
```

### 监控建议

#### 四个黄金指标

| 指标 | 监控对象 | 告警阈值 |
|------|---------|---------|
| **延迟** | API P95 响应时间 | > 2s |
| **流量** | 请求/分钟 | 突增 300% |
| **错误率** | 5xx / 总请求 | > 5% |
| **饱和度** | CPU / 内存 / 磁盘 | > 85% |

#### 方案 1：Prometheus + Grafana（推荐自建）

```yaml
# 追加到 docker-compose.prod.yml
  prometheus:
    image: prom/prometheus:latest
    container_name: recruitment-prometheus
    restart: always
    ports:
      - "127.0.0.1:9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus

  grafana:
    image: grafana/grafana:latest
    container_name: recruitment-grafana
    restart: always
    ports:
      - "127.0.0.1:3001:3000"
    volumes:
      - grafana_data:/var/lib/grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
```

#### 方案 2：云服务商监控

- **AWS**: CloudWatch + ALB 指标
- **阿里云**: 云监控 + SLB 监控
- **腾讯云**: 云监控 + CLB 监控

### 健康检查端点

```bash
# 系统级健康（Nginx 直接返回）
curl http://localhost/health

# 应用级健康（后端 FastAPI）
curl http://localhost:8000/health

# 数据库连通性
docker compose -f docker-compose.prod.yml exec postgres pg_isready -U recruitment

# Redis 连通性
docker compose -f docker-compose.prod.yml exec redis redis-cli -a <密码> ping
```

---

## 7. 常见问题排查

### 服务启动失败

```bash
# 查看退出码和日志
docker compose -f docker-compose.prod.yml ps -a
docker compose -f docker-compose.prod.yml logs --tail=50 <service-name>

# 常见原因
# - 端口被占用: lsof -i :80 / lsof -i :8000
# - 环境变量缺失: docker compose config 检查变量替换
# - 镜像构建失败: docker compose build --no-cache <service>
```

### 数据库连接失败

```bash
# 检查 PostgreSQL 是否健康
docker compose -f docker-compose.prod.yml exec postgres pg_isready -U recruitment

# 检查连接串
docker compose -f docker-compose.prod.yml exec backend python -c "
from app.core.config import settings
print(settings.DATABASE_URL)
"

# 手动测试连接
docker compose -f docker-compose.prod.yml exec postgres \
  psql -U recruitment -d recruitment -c "SELECT 1;"
```

### LLM 调用失败

```bash
# 检查网络连通性
docker compose -f docker-compose.prod.yml exec backend \
  curl -s -o /dev/null -w "%{http_code}" https://api.openai.com/v1/models

# 检查 API Key 是否配置
docker compose -f docker-compose.prod.yml exec backend \
  python -c "from app.core.config import settings; print(settings.DEFAULT_LLM_PROVIDER)"

# 查看 LLM 相关错误日志
docker compose -f docker-compose.prod.yml logs backend | grep -i "openai\|llm\|api_key"
```

### 文件上传失败

```bash
# 检查 uploads 目录和权限
docker compose -f docker-compose.prod.yml exec backend ls -la /app/uploads/

# 检查 Nginx 上传大小限制（当前 25MB）
# nginx.conf: client_max_body_size 25m;

# 检查磁盘空间
df -h
docker system df
```

### 内存不足 / OOM

```bash
# 查看容器资源使用
docker stats --no-stream

# 查看是否被 OOM Kill
docker inspect <container-id> | grep -i oom

# 调整资源限制（docker-compose.prod.yml deploy.resources.limits）
```

### Celery 任务卡住

```bash
# 查看活跃任务
docker compose -f docker-compose.prod.yml exec celery-worker \
  celery -A app.tasks.celery_app inspect active

# 查看排队任务数
docker compose -f docker-compose.prod.yml exec redis \
  redis-cli -a <密码> llen celery

# 重启 Worker
docker compose -f docker-compose.prod.yml restart celery-worker
```

---

## 8. 升级步骤

```bash
# 1. 备份数据库（升级前必做）
/opt/scripts/backup-db.sh

# 2. 拉取最新代码
cd /path/to/ai-recruitment
git fetch origin
git pull origin main

# 3. 重新构建镜像
docker compose -f docker-compose.prod.yml build

# 4. 重新构建前端（如有前端变更）
docker compose -f docker-compose.prod.yml --profile build run --rm frontend-builder

# 5. 滚动重启服务
docker compose -f docker-compose.prod.yml up -d

# 6. 执行数据库迁移（如有新迁移）
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head

# 7. 验证服务健康
curl http://localhost/health
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail=20 backend
```

> **注意**：若迁移包含不可逆的 schema 变更，务必先在 staging 环境验证。

---

## 9. 回滚

### 快速回滚（代码级）

```bash
# 1. 停止服务
docker compose -f docker-compose.prod.yml down

# 2. 回退到上一个稳定版本
git log --oneline -5  # 确认目标 commit
git checkout <previous-commit>

# 3. 重新构建并启动
docker compose -f docker-compose.prod.yml up -d --build

# 4. 回滚数据库迁移（如需要）
docker compose -f docker-compose.prod.yml exec backend alembic downgrade -1

# 5. 验证
curl http://localhost/health
```

### 数据库回滚

```bash
# 查看当前迁移版本
docker compose -f docker-compose.prod.yml exec backend alembic current

# 查看历史
docker compose -f docker-compose.prod.yml exec backend alembic history

# 回退一个版本
docker compose -f docker-compose.prod.yml exec backend alembic downgrade -1

# 回退到指定版本
docker compose -f docker-compose.prod.yml exec backend alembic downgrade <revision-id>
```

### 从备份恢复（灾难恢复）

```bash
# 1. 停止后端和 Celery（避免写入）
docker compose -f docker-compose.prod.yml stop backend celery-worker

# 2. 删除当前数据并恢复备份
docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U recruitment -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

gunzip -c /backups/postgres/recruitment_<timestamp>.sql.gz | \
  docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U recruitment -d recruitment

# 3. 重新执行迁移（确保 schema 版本一致）
docker compose -f docker-compose.prod.yml exec backend alembic stamp head

# 4. 重启服务
docker compose -f docker-compose.prod.yml start backend celery-worker
```

---

## 附录

### 完整首次部署 Checklist

- [ ] 服务器满足最低配置要求
- [ ] Docker 和 Docker Compose 已安装
- [ ] 代码已克隆到服务器
- [ ] `backend/.env.production` 已配置所有必填变量
- [ ] `.env`（Compose 级）已设置 `POSTGRES_PASSWORD` 和 `REDIS_PASSWORD`
- [ ] 防火墙仅开放 80/443 端口
- [ ] `docker compose -f docker-compose.prod.yml up -d` 成功
- [ ] 数据库迁移已执行
- [ ] 健康检查通过
- [ ] HTTPS 已配置（如需要）
- [ ] 备份脚本已设置
- [ ] 监控已接入
- [ ] `.env.production` 已加入 `.gitignore`

### 安全加固清单

- [ ] 数据库和 Redis 端口仅绑定 `127.0.0.1`
- [ ] `SECRET_KEY` 使用高强度随机值
- [ ] `DEBUG=false`
- [ ] `CORS_ORIGINS` 限制为实际前端域名
- [ ] PostgreSQL 和 Redis 均设有强密码
- [ ] 服务器 SSH 禁用密码登录，仅用密钥
- [ ] Docker 容器以非 root 用户运行（后续优化项）
- [ ] 定期更新基础镜像（`docker compose pull`）
