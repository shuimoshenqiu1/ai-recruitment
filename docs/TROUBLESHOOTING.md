# 部署问题排查指南 (Troubleshooting)

本文档记录了首次部署过程中遇到的所有问题和解决方案。

## Docker 构建问题

### 1. 前端 `npm ci` 失败
**错误**: `npm ci can only install with an existing package-lock.json`
**原因**: 项目未提交 `package-lock.json`
**解决**: Dockerfile 中使用 `npm install` 替代 `npm ci`

### 2. `version` 属性警告
**错误**: `the attribute 'version' is obsolete`
**原因**: 新版 Docker Compose 废弃了 `version` 字段
**解决**: 从 `docker-compose.yml` 中移除 `version: "3.8"` 行

### 3. python-magic 模块缺失
**错误**: `ModuleNotFoundError: No module named 'magic'`
**原因**: `requirements.txt` 中漏掉了 `python-magic` 依赖
**解决**: 添加 `python-magic==0.4.27` 到 requirements.txt

### 4. libmagic1 系统库缺失
**错误**: python-magic 安装后仍报错
**原因**: python-magic 依赖系统级 `libmagic1` 库
**解决**: 在 Dockerfile 的 `apt-get install` 中添加 `libmagic1`

### 5. 源码挂载覆盖容器依赖
**错误**: 容器内 `import magic` 失败，即使镜像已安装
**原因**: `volumes: - ./backend:/app` 将宿主机目录挂载到容器，覆盖了镜像中的文件
**解决**: 移除开发模式的源码挂载，代码通过 Dockerfile 的 `COPY . .` 打入镜像

### 6. 前端容器 `npm: not found`
**错误**: `/docker-entrypoint.sh: exec: line 47: npm: not found`
**原因**: Dockerfile 多阶段构建的最终镜像是 `nginx:alpine`（无Node.js），但 compose 配了 `command: npm run dev`
**解决**: 移除 `command` 和 `volumes` 挂载，让容器使用 Dockerfile 构建的 nginx 生产模式

### 7. passlib + bcrypt 版本不兼容
**错误**: `AttributeError: module 'bcrypt' has no attribute '__about__'`
**原因**: passlib 1.7.4 不兼容 bcrypt >= 4.1（新版移除了 `__about__` 属性）
**解决**: 锁定 `bcrypt==4.0.1`（passlib 兼容的最后一个版本）

### 8. Docker Hub 网络超时
**错误**: `TLS handshake timeout` 拉取 nginx:alpine/node:18-alpine
**原因**: 国内网络无法直接访问 Docker Hub
**解决**: 配置 Docker 镜像加速器：
```json
// Docker Desktop -> Settings -> Docker Engine
{
  "registry-mirrors": [
    "https://docker.1ms.run",
    "https://docker.xuanyuan.me"
  ]
}
```

### 9. PostgreSQL 启动失败 (exit code 3)
**可能原因**: 宿主机 5432 端口被占用（本地已装 PostgreSQL）
**排查**: `netstat -an | findstr "5432"`
**解决**: 修改 docker-compose.yml 端口映射为 `"5433:5432"`，或停止本地 PG 服务

---

## API 对接问题

### 10. 登录返回 422
**错误**: `POST /api/v1/auth/login HTTP/1.1 422 Unprocessable Entity`
**原因**: 前端发送 `{username, password}`，后端期望 `{email, password}`
**解决**: 前端 LoginParams 类型和表单字段名改为 `email`

### 11. 双重路径重写 (/api/v1/v1/)
**错误**: 请求 `/api/v1/v1/resumes/` 返回 404
**原因**: nginx rewrite `/api/ -> /api/v1/` + FastAPI 307重定向 → 二次 rewrite
**解决**: 前端直接使用 `/api/v1/xxx` 路径，nginx 做纯透明代理不 rewrite

### 12. 多个前端 API 路径与后端不匹配
| 前端路径 | 后端实际路径 | 修复 |
|:---------|:------------|:-----|
| `/api/resumes/{id}/reparse` | `/api/v1/resumes/{id}/parse` | 修改前端 |
| `/api/matching/run` | `/api/v1/matching/execute` | 修改前端 |
| `/api/matching/tasks` | 不存在 | 删除前端调用 |
| `/api/llm/models` | `/api/v1/llm-configs` | 修改前端 |
| `/api/auth/logout` | 不存在(JWT无状态) | 前端只清token |
| register `username` | 后端字段是 `name` | 修改前端 |

### 13. LLM 配置返回 403
**错误**: `GET /api/v1/llm-configs/ HTTP/1.1 403 Forbidden`
**原因**: 注册用户默认角色是 `recruiter`，LLM 配置需要 `admin` 角色
**解决**: 
```bash
docker compose exec postgres psql -U recruitment -d recruitment \
  -c "UPDATE users SET role='admin' WHERE email='admin@example.com';"
```
然后重新登录获取新 token

### 14. Swagger 调用返回 401
**错误**: `POST /api/v1/jobs/ HTTP/1.1 401 Unauthorized`
**原因**: Swagger 页面未配置 Authorization header
**解决**: 先登录获取 token，点 Swagger 右上角 Authorize 按钮，输入 `Bearer <token>`

---

## 前端显示问题

### 15. PowerShell 中文显示为 `??`
**原因**: PowerShell 默认编码不是 UTF-8
**影响**: 仅影响终端显示，数据库和前端显示正常
**解决**: `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8`

### 16. 前端数据列表为空 / map 报错
**错误**: `Cannot read properties of undefined (reading 'map')`
**原因**: 后端返回 `{code, data: {items, total}}`，前端代码期望不同的数据结构
**解决**: 需要 rebuild 前端镜像（包含最新代码修复），等 Docker Hub 网络通后执行：
```bash
docker compose build frontend
docker compose up -d --force-recreate frontend
```

---

## 经验教训

1. **依赖必须声明**：代码中 `import` 的包必须在 `requirements.txt` 中声明
2. **版本兼容性**：passlib + bcrypt 等组合需要锁定兼容版本
3. **前后端约定**：字段名(camelCase vs snake_case)、API路径、响应格式必须在开发前明确
4. **Docker开发模式 vs 生产模式**：volume 挂载和 Dockerfile 构建是互斥的逻辑，不要混用
5. **国内网络**：Docker 镜像加速器是必配项
6. **JWT 角色**：修改数据库角色后必须重新登录获取新 token
