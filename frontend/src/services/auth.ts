import request, { setToken, removeToken } from '@/utils/request';

/** 用户登录 */
export async function login(params: API.LoginParams): Promise<API.LoginResult> {
  const result = await request<API.LoginResult>('/api/v1/auth/login', {
    method: 'POST',
    data: params,
  });
  setToken(result.access_token);
  return result;
}

/** 用户登出（JWT无状态，仅清除本地token） */
export async function logout(): Promise<void> {
  removeToken();
}

/** 获取当前用户信息 */
export async function getCurrentUser(): Promise<API.CurrentUser> {
  return request<API.CurrentUser>('/api/v1/auth/me', { method: 'GET' });
}

/** 注册 */
export async function register(params: {
  name: string;
  email: string;
  password: string;
}): Promise<API.LoginResult> {
  return request<API.LoginResult>('/api/v1/auth/register', {
    method: 'POST',
    data: params,
  });
}
