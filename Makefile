# ============================================================
# AI招聘匹配系统 - Makefile
# 常用命令快捷方式
# ============================================================

.PHONY: help dev up down build restart logs \
        migrate migrate-create migrate-downgrade \
        test lint format \
        shell-backend shell-db \
        clean seed

# 默认命令
help: ## 显示帮助
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ============================================================
# 开发环境
# ============================================================

dev: ## 启动开发环境 (前台)
	docker compose up

up: ## 启动开发环境 (后台)
	docker compose up -d

down: ## 停止所有服务
	docker compose down

build: ## 重新构建所有镜像
	docker compose build --no-cache

restart: ## 重启所有服务
	docker compose restart

logs: ## 查看所有日志 (follow)
	docker compose logs -f

logs-backend: ## 查看后端日志
	docker compose logs -f backend

logs-celery: ## 查看Celery日志
	docker compose logs -f celery-worker

# ============================================================
# 数据库迁移
# ============================================================

migrate: ## 执行数据库迁移到最新版本
	docker compose exec backend alembic upgrade head

migrate-create: ## 创建新迁移 (用法: make migrate-create MSG="add_xxx_table")
	docker compose exec backend alembic revision --autogenerate -m "$(MSG)"

migrate-downgrade: ## 回滚一个版本
	docker compose exec backend alembic downgrade -1

migrate-history: ## 查看迁移历史
	docker compose exec backend alembic history --verbose

migrate-current: ## 查看当前版本
	docker compose exec backend alembic current

# ============================================================
# 测试
# ============================================================

test: ## 运行所有测试
	docker compose exec backend pytest -v

test-cov: ## 运行测试并生成覆盖率报告
	docker compose exec backend pytest --cov=app --cov-report=html --cov-report=term

test-watch: ## 监视模式运行测试
	docker compose exec backend pytest-watch

# ============================================================
# 代码质量
# ============================================================

lint: ## 代码检查 (ruff)
	docker compose exec backend ruff check app/

format: ## 代码格式化 (ruff)
	docker compose exec backend ruff format app/

typecheck: ## 类型检查 (mypy)
	docker compose exec backend mypy app/

# ============================================================
# 交互式Shell
# ============================================================

shell-backend: ## 进入后端容器Shell
	docker compose exec backend bash

shell-db: ## 进入数据库交互式终端
	docker compose exec postgres psql -U recruitment -d recruitment

shell-redis: ## 进入Redis CLI
	docker compose exec redis redis-cli

# ============================================================
# 数据管理
# ============================================================

seed: ## 初始化种子数据
	docker compose exec backend python -m app.scripts.seed

clean: ## 清理所有容器和数据卷 (⚠️ 删除数据)
	docker compose down -v --remove-orphans
	@echo "⚠️  所有数据卷已删除"

# ============================================================
# 生产构建
# ============================================================

prod-build: ## 构建生产镜像
	docker compose -f docker-compose.yml -f docker-compose.prod.yml build

prod-up: ## 启动生产环境
	docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
