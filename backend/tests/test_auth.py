"""认证模块集成测试 - 注册/登录/获取当前用户"""

import pytest
from httpx import AsyncClient


class TestRegister:
    """用户注册测试"""

    async def test_register_success(self, client: AsyncClient):
        """注册成功：返回token和用户信息"""
        resp = await client.post("/api/v1/auth/register", json={
            "email": "newuser@example.com",
            "password": "Valid123!@#",
            "name": "新用户",
        })

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert "access_token" in body["data"]
        assert body["data"]["token_type"] == "bearer"
        assert body["data"]["user"]["email"] == "newuser@example.com"
        assert body["data"]["user"]["name"] == "新用户"
        assert body["data"]["user"]["role"] == "recruiter"

    async def test_register_duplicate_email(self, client: AsyncClient):
        """注册失败：邮箱已存在返回409"""
        user_data = {
            "email": "dup@example.com",
            "password": "Valid123!@#",
            "name": "用户A",
        }

        # 第一次注册成功
        resp1 = await client.post("/api/v1/auth/register", json=user_data)
        assert resp1.status_code == 200

        # 第二次注册同一邮箱失败
        resp2 = await client.post("/api/v1/auth/register", json=user_data)
        assert resp2.status_code == 409
        assert "已被注册" in resp2.json()["detail"]

    async def test_register_weak_password_no_uppercase(self, client: AsyncClient):
        """注册失败：密码缺少大写字母"""
        resp = await client.post("/api/v1/auth/register", json={
            "email": "weak1@example.com",
            "password": "nouppercase123!",
            "name": "弱密码用户",
        })

        assert resp.status_code == 422
        body = resp.json()
        # Pydantic validation error
        assert any("大写字母" in str(e) for e in body.get("detail", []))

    async def test_register_weak_password_no_special(self, client: AsyncClient):
        """注册失败：密码缺少特殊字符"""
        resp = await client.post("/api/v1/auth/register", json={
            "email": "weak2@example.com",
            "password": "NoSpecial123",
            "name": "弱密码用户",
        })

        assert resp.status_code == 422

    async def test_register_weak_password_too_short(self, client: AsyncClient):
        """注册失败：密码太短"""
        resp = await client.post("/api/v1/auth/register", json={
            "email": "weak3@example.com",
            "password": "Ab1!",
            "name": "弱密码用户",
        })

        assert resp.status_code == 422

    async def test_register_invalid_email(self, client: AsyncClient):
        """注册失败：邮箱格式无效"""
        resp = await client.post("/api/v1/auth/register", json={
            "email": "not-an-email",
            "password": "Valid123!@#",
            "name": "无效邮箱用户",
        })

        assert resp.status_code == 422


class TestLogin:
    """用户登录测试"""

    async def test_login_success(self, client: AsyncClient):
        """登录成功：返回token"""
        # 先注册
        await client.post("/api/v1/auth/register", json={
            "email": "login@example.com",
            "password": "Login123!@#",
            "name": "登录测试",
        })

        # 再登录
        resp = await client.post("/api/v1/auth/login", json={
            "email": "login@example.com",
            "password": "Login123!@#",
        })

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert "access_token" in body["data"]
        assert body["data"]["user"]["email"] == "login@example.com"

    async def test_login_wrong_password(self, client: AsyncClient):
        """登录失败：密码错误返回401"""
        # 先注册
        await client.post("/api/v1/auth/register", json={
            "email": "wrongpwd@example.com",
            "password": "Correct123!@#",
            "name": "密码错误测试",
        })

        # 用错误密码登录
        resp = await client.post("/api/v1/auth/login", json={
            "email": "wrongpwd@example.com",
            "password": "WrongPass123!@#",
        })

        assert resp.status_code == 401
        assert "密码错误" in resp.json()["detail"]

    async def test_login_nonexistent_email(self, client: AsyncClient):
        """登录失败：邮箱不存在返回401"""
        resp = await client.post("/api/v1/auth/login", json={
            "email": "nobody@example.com",
            "password": "Whatever123!@#",
        })

        assert resp.status_code == 401

    async def test_login_empty_password(self, client: AsyncClient):
        """登录失败：空密码返回422"""
        resp = await client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "",
        })

        assert resp.status_code == 422


class TestGetMe:
    """获取当前用户信息测试"""

    async def test_get_me_success(self, client: AsyncClient, auth_headers: dict):
        """认证成功：返回当前用户信息"""
        resp = await client.get("/api/v1/auth/me", headers=auth_headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["email"] == "test@example.com"
        assert body["data"]["name"] == "测试用户"
        assert body["data"]["is_active"] is True

    async def test_get_me_unauthorized(self, client: AsyncClient):
        """未认证：无token访问返回401"""
        resp = await client.get("/api/v1/auth/me")

        assert resp.status_code == 401

    async def test_get_me_invalid_token(self, client: AsyncClient):
        """认证失败：无效token返回401"""
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )

        assert resp.status_code == 401
