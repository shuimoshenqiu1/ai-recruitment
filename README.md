# AI驱动的简历解析与智能招聘匹配系统

基于大语言模型（LLM）的智能招聘辅助系统，实现从简历上传、智能解析、岗位匹配到候选人管理的全流程自动化。

## 🎯 项目目标

- 简历筛选效率提升 ≥ 80%
- 简历解析准确率 ≥ 95%
- 单份简历解析耗时 ≤ 5秒
- 支持 ≥ 100份简历并发上传

## ✨ 核心功能

### 📄 简历采集与上传
- 单文件/批量上传（最多100份/次）
- 支持 PDF、DOCX、DOC、TXT、JPG、PNG 格式
- Magic-bytes 文件类型二次校验（防止恶意文件）
- 文件大小限制（≤20MB）
- 上传后自动触发异步解析

### 🤖 简历智能解析
- **多格式文档提取**：PyMuPDF(PDF) + python-docx(DOCX) + antiword/LibreOffice(DOC)
- **文本预处理**：全角转半角、去控制字符、去页眉页脚、合并空行
- **质量评估**：0-100分文本质量打分（过低则跳过LLM节省token）
- **LLM结构化解析**：调用大语言模型将简历文本转为标准JSON
- **提取字段**：
  - 基础信息：姓名、性别、年龄、电话、邮箱、城市、期望薪资
  - 教育经历：学校、专业、学历、时间、GPA
  - 工作经历：公司、职位、时间、职责、成就
  - 技能清单：技能名、熟练度（精通/熟练/熟悉/了解）、使用年限
  - 项目经历：项目名、角色、技术栈、成果
  - 证书资质：证书名、时间、发证机构
  - 语言能力：语种、水平等级

### 🔌 LLM多模型适配层
- **Adapter模式**：统一接口，支持热插拔
- **已支持模型**：

| Provider | 模型 | 说明 |
|:---------|:-----|:-----|
| OpenAI | GPT-4/3.5 | 官方API |
| DeepSeek | DeepSeek-Chat/Coder | OpenAI兼容协议 |
| Kimi (Moonshot) | moonshot-v1 | OpenAI兼容协议 |
| GLM (智谱) | glm-4/glm-3-turbo | OpenAI兼容协议 |
| Claude (Anthropic) | claude-3-opus/sonnet/haiku | Anthropic原生API |
| Ollama | llama3/qwen2/任意模型 | 本地部署，无需API Key |

- **容错设计**：超时重试（3次）、认证失败不重试、速率限制自动退避
- **连接池复用**：httpx AsyncClient共享，避免TCP连接浪费
- **Prompt注入防护**：边界标记 + 系统安全规则

### 🏢 岗位需求管理（W4开发中）
- 岗位创建与编辑
- 需求结构化：硬性要求 / 软性要求 / 优先条件
- 岗位状态管理：草稿 → 发布中 → 已关闭

### 🎯 智能匹配（W4开发中）
- 基于LLM的语义级人岗匹配
- 多维度评分：技能/经验/教育/软性能力
- 0-100分匹配度 + 可解释推荐理由
- 自动分级：优秀/合格/不合格

### 👤 用户认证与权限
- JWT令牌认证（30分钟过期）
- 密码复杂度校验（大小写+数字+特殊字符）
- 登录限频（5次/分钟/IP，防暴力破解）
- 四种角色：管理员 / HR经理 / 招聘专员 / 面试官

## 🛠️ 技术栈

### 后端
| 组件 | 技术 | 版本 |
|:-----|:-----|:-----|
| 框架 | FastAPI | - |
| 语言 | Python | 3.11+ |
| 数据库 | PostgreSQL + pgvector | 15 |
| 缓存/队列 | Redis | 7 |
| 异步任务 | Celery | 5.4 |
| ORM | SQLAlchemy (async) | 2.0 |
| HTTP客户端 | httpx | - |
| 文档解析 | PyMuPDF + python-docx | - |
| 认证 | python-jose (JWT) + passlib (bcrypt) | - |
| 限频 | slowapi | 0.1.9 |
| 文件校验 | python-magic | 0.4.27 |

### 前端
| 组件 | 技术 |
|:-----|:-----|
| 框架 | React + TypeScript |
| UI库 | Ant Design Pro |
| 构建 | Umi.js |
| HTTP | 统一请求封装（JWT拦截） |

### 基础设施
| 组件 | 技术 |
|:-----|:-----|
| 容器化 | Docker + Docker Compose |
| 反向代理 | Nginx |
| 数据库迁移 | Alembic |

## 📁 项目结构

```
ai-recruitment/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # API路由 (auth/resumes/jobs/matching/llm_configs)
│   │   ├── core/            # 配置、数据库、安全
│   │   ├── crud/            # 数据访问层
│   │   ├── llm/             # LLM多模型适配层
│   │   │   ├── base.py          # 基类 + 异常定义
│   │   │   ├── factory.py       # 适配器工厂
│   │   │   ├── openai_compatible.py  # OpenAI/DeepSeek/Kimi/GLM
│   │   │   ├── claude_adapter.py     # Anthropic Claude
│   │   │   ├── ollama_adapter.py     # 本地Ollama
│   │   │   └── prompts/        # Prompt模板
│   │   ├── models/          # SQLAlchemy数据模型
│   │   ├── schemas/         # Pydantic请求/响应模型
│   │   ├── services/        # 业务服务层
│   │   │   ├── document_extractor.py  # 多格式文档提取
│   │   │   ├── text_preprocessor.py   # 文本清洗+质量评估
│   │   │   ├── llm_resume_parser.py   # LLM解析服务
│   │   │   ├── resume_parser.py       # 解析管道集成
│   │   │   └── file_storage.py        # 文件存储
│   │   ├── tasks/           # Celery异步任务
│   │   └── utils/           # 工具函数
│   ├── migrations/          # 数据库迁移
│   ├── tests/               # 集成测试 (pytest)
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/           # 9个页面
│   │   ├── services/        # API调用层
│   │   ├── typings/         # TypeScript类型
│   │   └── layouts/         # 布局组件
│   ├── Dockerfile
│   └── package.json
├── nginx/                   # 反向代理配置
├── docker-compose.yml       # 开发环境部署
├── docker-compose.prod.yml  # 生产环境部署
├── .github/workflows/       # CI/CD (GitHub Actions)
├── Makefile                 # 常用命令
└── docs/
    ├── PRD.md              # 产品需求文档
    ├── ARCHITECTURE.md     # 系统架构设计
    └── DEPLOYMENT.md       # 生产部署指南
```

## 🚀 快速开始

### 环境要求
- Docker 20.10+
- Docker Compose v2+

### 一键启动

```bash
# 克隆项目
git clone git@github.com:shuimoshenqiu1/ai-recruitment.git
cd ai-recruitment

# 配置环境变量
cp .env.example .env
# 编辑 .env，至少填入一个 LLM 的 API Key（详见文件内注释）
# 如果用本地 Ollama 则无需 API Key，只需确保 Ollama 已启动

# 启动所有服务
docker compose up -d

# 等待服务启动（首次需要构建镜像，约2-5分钟）
docker compose logs -f backend

# 检查健康状态
curl http://localhost:8000/health
```

启动后访问：
- 前端界面：http://localhost
- API文档：http://localhost:8000/docs
- ReDoc：http://localhost:8000/redoc

### 默认账号
- 邮箱：admin@example.com
- 密码：Admin123!@#

### 本地开发（不用Docker）

```bash
# 后端
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 前端
cd frontend
npm install
npm run dev

# Celery Worker
cd backend
celery -A app.tasks worker -l info
```

## 🔧 配置说明

### 环境变量（.env）

```env
# 必填
SECRET_KEY=your-secret-key-at-least-32-chars-long
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/recruitment
REDIS_URL=redis://localhost:6379/0

# LLM配置（至少配一个）
DEFAULT_LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxx
OPENAI_MODEL=gpt-4

# 或使用DeepSeek（更便宜）
# DEFAULT_LLM_PROVIDER=deepseek
# DEEPSEEK_API_KEY=sk-xxx
# DEEPSEEK_MODEL=deepseek-chat

# 或使用本地Ollama（免费）
# DEFAULT_LLM_PROVIDER=ollama
# OLLAMA_BASE_URL=http://localhost:11434
# OLLAMA_MODEL=qwen2
```

### LLM模型切换

系统支持在运行时通过管理界面切换LLM模型，无需重启服务。也可以通过API配置：

```bash
# 查看当前配置
curl http://localhost:8000/api/v1/llm-configs/ -H "Authorization: Bearer <token>"

# 切换到DeepSeek
curl -X POST http://localhost:8000/api/v1/llm-configs/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"provider": "deepseek", "api_key": "sk-xxx", "model": "deepseek-chat", "is_active": true}'
```

## 📊 API概览

| 模块 | 端点 | 说明 |
|:-----|:-----|:-----|
| 认证 | POST /api/v1/auth/register | 用户注册 |
| 认证 | POST /api/v1/auth/login | 用户登录 |
| 认证 | GET /api/v1/auth/me | 获取当前用户 |
| 简历 | POST /api/v1/resumes/upload | 单文件上传 |
| 简历 | POST /api/v1/resumes/batch-upload | 批量上传 |
| 简历 | GET /api/v1/resumes/ | 简历列表（分页） |
| 简历 | GET /api/v1/resumes/{id} | 简历详情 |
| 简历 | DELETE /api/v1/resumes/{id} | 删除简历 |
| 简历 | POST /api/v1/resumes/{id}/parse | 重新解析 |
| 岗位 | POST /api/v1/jobs/ | 创建岗位 |
| 岗位 | GET /api/v1/jobs/ | 岗位列表 |
| 岗位 | GET /api/v1/jobs/{id} | 岗位详情 |
| 岗位 | PUT /api/v1/jobs/{id} | 编辑岗位 |
| 岗位 | PATCH /api/v1/jobs/{id}/status | 变更状态 |
| 岗位 | DELETE /api/v1/jobs/{id} | 删除岗位 |
| 匹配 | POST /api/v1/matching/execute | 执行AI匹配 |
| 匹配 | GET /api/v1/matching/results | 匹配结果列表 |
| 匹配 | GET /api/v1/matching/results/{id} | 匹配详情 |
| 匹配 | POST /api/v1/matching/export | 导出Excel |
| 报告 | GET /api/v1/reports/match/{id}/report | 单份匹配报告 |
| 报告 | POST /api/v1/reports/match/export | 增强Excel导出 |
| 看板 | GET /api/v1/dashboard/overview | 总览数据 |
| 看板 | GET /api/v1/dashboard/jobs/progress | 岗位招聘进度 |
| 看板 | GET /api/v1/dashboard/resumes/stats | 简历统计 |
| 看板 | GET /api/v1/dashboard/matching/stats | 匹配统计 |
| LLM | GET /api/v1/llm-configs/ | 查看LLM配置 |
| LLM | POST /api/v1/llm-configs/ | 新增/切换模型 |
| 健康 | GET /health | 健康检查 |
| 健康 | GET /health/ready | 就绪检查 |

完整API文档启动服务后访问 http://localhost:8000/docs

## 🔒 安全特性

- JWT认证 + 角色权限控制（admin/hr_manager/recruiter/interviewer）
- 密码bcrypt哈希 + 复杂度校验（大小写+数字+特殊字符）
- 登录频率限制（5次/分钟/IP，防暴力破解）
- 文件上传双重校验（扩展名 + Magic bytes内容检测）
- 路径遍历防护（realpath校验限制在上传目录内）
- API Key脱敏（错误信息写DB/日志前自动过滤）
- Prompt注入防护（边界标记 + 系统安全规则声明）
- IDOR防护（匹配/报告路由岗位所有权校验）
- LIKE通配符转义（防搜索绕过）
- 文件名注入防护（sanitize + RFC5987编码）
- XSS防护（HTML报告数据属性转义）
- SECRET_KEY生产环境强制校验（启动时验证）
- SQL注入防护（SQLAlchemy参数化查询）
- Celery任务超时保护（soft/hard time limit）
- 自动重试分类（认证失败不重试，超时/限频重试）
- CORS白名单配置

## 🗺️ 开发路线图

| 阶段 | 内容 | 状态 |
|:-----|:-----|:-----|
| W1 | 项目初始化 + Docker | ✅ 完成 |
| W2 | 用户认证 + 简历上传 | ✅ 完成 |
| W3 | 简历智能解析 + LLM适配层 | ✅ 完成 |
| W4 | 岗位管理 + AI智能匹配 | ✅ 完成 |
| W5 | 报告导出 + 数据看板 | ✅ 完成 |
| W6 | 集成测试 + 生产部署 | ✅ 完成 |

## 📝 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request。
