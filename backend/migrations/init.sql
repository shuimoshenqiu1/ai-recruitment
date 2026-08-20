-- ============================================================
-- AI招聘匹配系统 - 数据库初始化脚本
-- 用途: PostgreSQL容器首次启动时自动执行
-- ============================================================

-- 启用扩展
CREATE EXTENSION IF NOT EXISTS vector;         -- pgvector: 向量相似度搜索
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";    -- UUID生成函数

-- ============================================================
-- 创建初始管理员用户
-- 邮箱: admin@recruitment.com
-- 密码: admin123 (bcrypt hash)
-- 角色: admin
-- ============================================================
INSERT INTO users (id, email, password_hash, name, role, is_active, created_at, updated_at)
VALUES (
    uuid_generate_v4(),
    'admin@recruitment.com',
    '$2b$12$fMfjkrESsMXM.HbRl6rAGOqkizkns3ks6MimzywU57Zb.WGyBeS0e',
    '系统管理员',
    'admin',
    true,
    NOW(),
    NOW()
) ON CONFLICT (email) DO NOTHING;
