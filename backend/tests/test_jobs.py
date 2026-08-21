"""岗位管理集成测试 - CRUD/状态流转/权限"""

import uuid

import pytest
from httpx import AsyncClient


class TestCreateJob:
    """创建岗位测试"""

    async def test_create_job_success(
        self, client: AsyncClient, auth_headers: dict, sample_job_data: dict
    ):
        """创建成功：返回201和岗位详情，默认状态draft"""
        resp = await client.post(
            "/api/v1/jobs/", json=sample_job_data, headers=auth_headers
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["title"] == sample_job_data["title"]
        assert body["data"]["department"] == "技术部"
        assert body["data"]["headcount"] == 2
        assert body["data"]["status"] == "draft"
        assert body["data"]["requirements"]["hard"] == sample_job_data["requirements"]["hard"]

    async def test_create_job_minimal_fields(self, client: AsyncClient, auth_headers: dict):
        """创建成功：只填必填字段"""
        minimal = {
            "title": "初级工程师",
            "requirements": {"hard": ["Python"], "soft": [], "preferred": []},
        }

        resp = await client.post("/api/v1/jobs/", json=minimal, headers=auth_headers)

        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["title"] == "初级工程师"
        assert body["data"]["headcount"] == 1  # 默认值

    async def test_create_job_unauthorized(self, client: AsyncClient, sample_job_data: dict):
        """创建失败：未认证返回401"""
        resp = await client.post("/api/v1/jobs/", json=sample_job_data)

        assert resp.status_code == 401

    async def test_create_job_missing_title(self, client: AsyncClient, auth_headers: dict):
        """创建失败：缺少必填字段title返回422"""
        resp = await client.post(
            "/api/v1/jobs/",
            json={"requirements": {"hard": [], "soft": [], "preferred": []}},
            headers=auth_headers,
        )

        assert resp.status_code == 422


class TestListJobs:
    """岗位列表测试"""

    async def test_list_jobs_empty(self, client: AsyncClient, auth_headers: dict):
        """空列表：返回total=0"""
        resp = await client.get("/api/v1/jobs/", headers=auth_headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["total"] == 0
        assert body["data"]["items"] == []

    async def test_list_jobs_with_data(
        self, client: AsyncClient, auth_headers: dict, sample_job_data: dict
    ):
        """有数据时：返回岗位列表"""
        # 创建2个岗位
        await client.post("/api/v1/jobs/", json=sample_job_data, headers=auth_headers)
        job2 = sample_job_data.copy()
        job2["title"] = "前端开发工程师"
        await client.post("/api/v1/jobs/", json=job2, headers=auth_headers)

        resp = await client.get("/api/v1/jobs/", headers=auth_headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["total"] == 2
        assert len(body["data"]["items"]) == 2

    async def test_list_jobs_filter_by_status(
        self, client: AsyncClient, auth_headers: dict, sample_job_data: dict
    ):
        """按状态筛选：只返回匹配状态的岗位"""
        # 创建岗位（默认draft）
        create_resp = await client.post(
            "/api/v1/jobs/", json=sample_job_data, headers=auth_headers
        )
        job_id = create_resp.json()["data"]["id"]

        # 发布岗位
        await client.patch(
            f"/api/v1/jobs/{job_id}/status",
            json={"status": "published"},
            headers=auth_headers,
        )

        # 筛选published
        resp = await client.get(
            "/api/v1/jobs/", params={"status": "published"}, headers=auth_headers
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["total"] == 1
        assert body["data"]["items"][0]["status"] == "published"

        # 筛选draft - 应该为0
        resp2 = await client.get(
            "/api/v1/jobs/", params={"status": "draft"}, headers=auth_headers
        )
        assert resp2.json()["data"]["total"] == 0


class TestUpdateJob:
    """更新岗位测试"""

    async def test_update_job_success(
        self, client: AsyncClient, auth_headers: dict, sample_job_data: dict
    ):
        """更新成功：修改标题和描述"""
        # 创建
        create_resp = await client.post(
            "/api/v1/jobs/", json=sample_job_data, headers=auth_headers
        )
        job_id = create_resp.json()["data"]["id"]

        # 更新
        update_data = sample_job_data.copy()
        update_data["title"] = "资深Python架构师"
        update_data["headcount"] = 3

        resp = await client.put(
            f"/api/v1/jobs/{job_id}", json=update_data, headers=auth_headers
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["title"] == "资深Python架构师"
        assert body["data"]["headcount"] == 3

    async def test_update_closed_job_fails(
        self, client: AsyncClient, auth_headers: dict, sample_job_data: dict
    ):
        """更新失败：已关闭岗位不可编辑"""
        # 创建 -> 发布 -> 关闭
        create_resp = await client.post(
            "/api/v1/jobs/", json=sample_job_data, headers=auth_headers
        )
        job_id = create_resp.json()["data"]["id"]

        await client.patch(
            f"/api/v1/jobs/{job_id}/status",
            json={"status": "published"},
            headers=auth_headers,
        )
        await client.patch(
            f"/api/v1/jobs/{job_id}/status",
            json={"status": "closed"},
            headers=auth_headers,
        )

        # 尝试更新已关闭岗位
        update_data = sample_job_data.copy()
        update_data["title"] = "不应该生效"
        resp = await client.put(
            f"/api/v1/jobs/{job_id}", json=update_data, headers=auth_headers
        )

        assert resp.status_code == 400
        assert "不可编辑" in resp.json()["detail"]

    async def test_update_nonexistent_job(
        self, client: AsyncClient, auth_headers: dict, sample_job_data: dict
    ):
        """更新失败：岗位不存在返回404"""
        fake_id = str(uuid.uuid4())
        resp = await client.put(
            f"/api/v1/jobs/{fake_id}", json=sample_job_data, headers=auth_headers
        )

        assert resp.status_code == 404


class TestJobStatusTransition:
    """岗位状态流转测试"""

    async def test_draft_to_published(
        self, client: AsyncClient, auth_headers: dict, sample_job_data: dict
    ):
        """正常流转：draft -> published"""
        create_resp = await client.post(
            "/api/v1/jobs/", json=sample_job_data, headers=auth_headers
        )
        job_id = create_resp.json()["data"]["id"]

        resp = await client.patch(
            f"/api/v1/jobs/{job_id}/status",
            json={"status": "published"},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "published"

    async def test_published_to_closed(
        self, client: AsyncClient, auth_headers: dict, sample_job_data: dict
    ):
        """正常流转：published -> closed"""
        create_resp = await client.post(
            "/api/v1/jobs/", json=sample_job_data, headers=auth_headers
        )
        job_id = create_resp.json()["data"]["id"]

        await client.patch(
            f"/api/v1/jobs/{job_id}/status",
            json={"status": "published"},
            headers=auth_headers,
        )

        resp = await client.patch(
            f"/api/v1/jobs/{job_id}/status",
            json={"status": "closed"},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "closed"

    async def test_closed_to_published_fails(
        self, client: AsyncClient, auth_headers: dict, sample_job_data: dict
    ):
        """非法流转：closed -> published 应失败"""
        create_resp = await client.post(
            "/api/v1/jobs/", json=sample_job_data, headers=auth_headers
        )
        job_id = create_resp.json()["data"]["id"]

        # draft -> published -> closed
        await client.patch(
            f"/api/v1/jobs/{job_id}/status",
            json={"status": "published"},
            headers=auth_headers,
        )
        await client.patch(
            f"/api/v1/jobs/{job_id}/status",
            json={"status": "closed"},
            headers=auth_headers,
        )

        # closed -> published 应失败
        resp = await client.patch(
            f"/api/v1/jobs/{job_id}/status",
            json={"status": "published"},
            headers=auth_headers,
        )

        assert resp.status_code == 400
        assert "无效的状态变更" in resp.json()["detail"]

    async def test_draft_to_closed_directly(
        self, client: AsyncClient, auth_headers: dict, sample_job_data: dict
    ):
        """允许：draft -> closed 直接关闭"""
        create_resp = await client.post(
            "/api/v1/jobs/", json=sample_job_data, headers=auth_headers
        )
        job_id = create_resp.json()["data"]["id"]

        resp = await client.patch(
            f"/api/v1/jobs/{job_id}/status",
            json={"status": "closed"},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "closed"


class TestDeleteJob:
    """岗位删除测试"""

    async def test_delete_draft_job_success(
        self, client: AsyncClient, auth_headers: dict, sample_job_data: dict
    ):
        """删除成功：草稿状态且无匹配结果"""
        create_resp = await client.post(
            "/api/v1/jobs/", json=sample_job_data, headers=auth_headers
        )
        job_id = create_resp.json()["data"]["id"]

        resp = await client.delete(f"/api/v1/jobs/{job_id}", headers=auth_headers)

        assert resp.status_code == 200
        assert "删除成功" in resp.json()["message"]

        # 确认已删除 - 获取详情应该404
        detail_resp = await client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers)
        assert detail_resp.status_code == 404

    async def test_delete_published_job_fails(
        self, client: AsyncClient, auth_headers: dict, sample_job_data: dict
    ):
        """删除失败：已发布岗位不可删除"""
        create_resp = await client.post(
            "/api/v1/jobs/", json=sample_job_data, headers=auth_headers
        )
        job_id = create_resp.json()["data"]["id"]

        # 先发布
        await client.patch(
            f"/api/v1/jobs/{job_id}/status",
            json={"status": "published"},
            headers=auth_headers,
        )

        # 尝试删除
        resp = await client.delete(f"/api/v1/jobs/{job_id}", headers=auth_headers)

        assert resp.status_code == 400
        assert "草稿" in resp.json()["detail"]

    async def test_delete_nonexistent_job(self, client: AsyncClient, auth_headers: dict):
        """删除失败：岗位不存在返回404"""
        fake_id = str(uuid.uuid4())
        resp = await client.delete(f"/api/v1/jobs/{fake_id}", headers=auth_headers)

        assert resp.status_code == 404
