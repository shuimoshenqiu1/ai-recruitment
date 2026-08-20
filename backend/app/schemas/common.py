"""通用Schema - 分页、统一响应"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageParams(BaseModel):
    """分页请求参数"""
    page: int = Field(default=1, ge=1, description="页码，从1开始")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量，最大100")

    @property
    def offset(self) -> int:
        """计算数据库偏移量"""
        return (self.page - 1) * self.page_size


class PageResponse(BaseModel, Generic[T]):
    """分页响应"""
    items: list[T] = Field(description="数据列表")
    total: int = Field(description="总数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页数量")
    pages: int = Field(description="总页数")

    @classmethod
    def create(cls, items: list[T], total: int, page: int, page_size: int) -> "PageResponse[T]":
        """工厂方法：自动计算总页数"""
        pages = (total + page_size - 1) // page_size if total > 0 else 0
        return cls(items=items, total=total, page=page, page_size=page_size, pages=pages)


class APIResponse(BaseModel, Generic[T]):
    """统一API响应格式"""
    code: int = Field(default=0, description="状态码，0表示成功")
    data: T | None = Field(default=None, description="响应数据")
    message: str = Field(default="success", description="响应消息")

    @classmethod
    def success(cls, data: Any = None, message: str = "success") -> "APIResponse":
        """成功响应"""
        return cls(code=0, data=data, message=message)

    @classmethod
    def error(cls, message: str, code: int = -1, data: Any = None) -> "APIResponse":
        """错误响应"""
        return cls(code=code, data=data, message=message)
