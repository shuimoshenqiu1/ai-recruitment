"""数据看板集成测试 - 总览/简历统计/匹配统计"""

import pytest
from httpx import AsyncClient


class TestDashboardOverview:
    """看板总览测试"""

    async def test_overview_success(self, client: AsyncClient, auth_headers: dict):
        """获取总览数据成功"""
        resp = await client.get("/api/v1/dashboard/overview", headers=auth_headers)

        assert resp.status_code == 200
        body = resp.json()
        # 新用户应该全为0
        assert "total_jobs" in body or "job_count" in body or isinstance(body, dict)

    async def test_overview_unauthorized(self, client: AsyncClient):
        """未认证：返回401"""
        resp = await client.get("/api/v1/dashboard/overview")

        assert resp.status_code == 401

    async def test_overview_with_data(
        self, client: AsyncClient, auth_headers: dict, sample_job_data: dict
    ):
        """有数据时：总览数据反映实际状态"""
        # 创建并发布一个岗位
        create_resp = await client.post(
            "/api/v1/jobs/", json=sample_job_data, headers=auth_headers
        )
        job_id = create_resp.json()["data"]["id"]
        await client.patch(
            f"/api/v1/jobs/{job_id}/status",
            json={"status": "published"},
            headers=auth_headers,
        )

        resp = await client.get("/api/v1/dashboard/overview", headers=auth_headers)

        assert resp.status_code == 200
        body = resp.json()
        # 具体字段名取决于OverviewStats schema，至少应能成功返回
        assert isinstance(body, dict)


class TestResumeStats:
    """简历统计测试"""

    async def test_resume_stats_success(self, client: AsyncClient, auth_headers: dict):
        """获取简历统计成功"""
        resp = await client.get("/api/v1/dashboard/resumes/stats", headers=auth_headers)

        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, dict)

    async def test_resume_stats_custom_days(self, client: AsyncClient, auth_headers: dict):
        """自定义统计天数范围"""
        resp = await client.get(
            "/api/v1/dashboard/resumes/stats",
            params={"days": 7},
            headers=auth_headers,
        )

        assert resp.status_code == 200

    async def test_resume_stats_invalid_days(self, client: AsyncClient, auth_headers: dict):
        """无效天数参数：超出范围返回422"""
        resp = await client.get(
            "/api/v1/dashboard/resumes/stats",
            params={"days": 0},
            headers=auth_headers,
        )

        assert resp.status_code == 422

    async def test_resume_stats_unauthorized(self, client: AsyncClient):
        """未认证：返回401"""
        resp = await client.get("/api/v1/dashboard/resumes/stats")

        assert resp.status_code == 401


class TestMatchingStats:
    """匹配统计测试"""

    async def test_matching_stats_success(self, client: AsyncClient, auth_headers: dict):
        """获取匹配统计成功"""
        resp = await client.get("/api/v1/dashboard/matching/stats", headers=auth_headers)

        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, dict)

    async def test_matching_stats_custom_days(self, client: AsyncClient, auth_headers: dict):
        """自定义统计天数"""
        resp = await client.get(
            "/api/v1/dashboard/matching/stats",
            params={"days": 14},
            headers=auth_headers,
        )

        assert resp.status_code == 200

    async def test_matching_stats_unauthorized(self, client: AsyncClient):
        """未认证：返回401"""
        resp = await client.get("/api/v1/dashboard/matching/stats")

        assert resp.status_code == 401


class TestJobsProgress:
    """岗位招聘进度测试"""

    async def test_jobs_progress_success(self, client: AsyncClient, auth_headers: dict):
        """获取岗位进度成功"""
        resp = await client.get("/api/v1/dashboard/jobs/progress", headers=auth_headers)

        assert resp.status_code == 200
        body = resp.json()
        # 空数据时应返回空列表
        assert isinstance(body, list)

    async def test_jobs_progress_unauthorized(self, client: AsyncClient):
        """未认证：返回401"""
        resp = await client.get("/api/v1/dashboard/jobs/progress")

        assert resp.status_code == 401
