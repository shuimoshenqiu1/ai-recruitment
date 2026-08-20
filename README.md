# AI驱动的简历解析与智能招聘匹配系统

## 项目简介

基于 AI/LLM 的智能招聘系统，实现简历自动解析、岗位智能匹配、候选人分级筛选。

## 技术栈

| 层级 | 技术 |
|:---|:---|
| 前端 | React + TypeScript + Ant Design Pro |
| 后端 | FastAPI (Python 3.11+) |
| 数据库 | PostgreSQL 15 + pgvector |
| 缓存/队列 | Redis 7 + Celery |
| LLM | 多模型适配（GPT/DeepSeek/Kimi/Claude/GLM/Ollama） |
| 部署 | Docker Compose |

## 快速开始

### 环境要求

- Docker & Docker Compose v2
- Node.js 18+ (前端开发)
- Python 3.11+ (后端开发)

### 启动开发环境

```bash
# 启动所有服务
docker compose up -d

# 前端开发模式
cd frontend && npm install && npm run dev

# 后端开发模式
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload
```

### 访问地址

- 前端: http://localhost:3000
- 后端API: http://localhost:8000
- API文档: http://localhost:8000/docs
- PostgreSQL: localhost:5432
- Redis: localhost:6379

## 项目结构

```
ai-recruitment/
├── frontend/          # React 前端
├── backend/           # FastAPI 后端
├── docker-compose.yml # 开发环境编排
├── docs/              # 项目文档
└── README.md
```

## 文档

- [PRD](../docs/PRD.md)
- [架构设计](../docs/ARCHITECTURE.md)
