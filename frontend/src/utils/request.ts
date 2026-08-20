import { request as umiRequest } from '@umijs/max';
import { message } from 'antd';

/**
 * 统一请求封装
 * - 自动携带 JWT Token
 * - 统一错误处理
 * - 401 自动跳转登录
 */

const TOKEN_KEY = 'access_token';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function removeToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export async function request<T = any>(
  url: string,
  options?: {
    method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
    data?: any;
    params?: Record<string, any>;
    headers?: Record<string, string>;
  },
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...options?.headers,
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  try {
    const response = await umiRequest<API.Response<T>>(url, {
      ...options,
      headers,
    });

    if (response.code !== 0) {
      message.error(response.message || '请求失败');
      return Promise.reject(new Error(response.message));
    }

    return response.data;
  } catch (error: any) {
    if (error?.response?.status === 401) {
      removeToken();
      message.error('登录已过期，请重新登录');
      window.location.href = '/login';
      return Promise.reject(error);
    }

    if (error?.response?.status === 403) {
      message.error('没有权限访问');
      return Promise.reject(error);
    }

    message.error(error?.message || '网络错误');
    return Promise.reject(error);
  }
}

export default request;
