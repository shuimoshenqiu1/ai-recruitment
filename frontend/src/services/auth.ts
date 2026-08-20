import request, { setToken, removeToken } from '@/utils/request';

/** 用户登录 */
export async function login(params: API.LoginParams): Promise<API.LoginResult> {
  const result = await request<API.LoginResult>('/api/auth/login', {
    method: 'POST',
    data: params,
  });
  setToken(result.access_token);
  return result;
}

/** 用户登出 */
export async function logout(): Promise<void> {
  await request('/api/auth/logout', { method: 'POST' });
  removeToken();
}

/** 获取当前用户信息 */
export async function getCurrentUser(): Promise<API.CurrentUser> {
  return request<API.CurrentUser>('/api/auth/me', { method: 'GET' });
}

/** 注册 */
export async function register(params: {
  username: string;
  email: string;
  password: string;
}): Promise<API.LoginResult> {
  return request<API.LoginResult>('/api/auth/register', {
    method: 'POST',
    data: params,
  });
}
