import { history } from '@umijs/max';
import { getCurrentUser } from '@/services/auth';
import { getToken } from '@/utils/request';

/**
 * 全局初始化数据配置
 * 用于获取用户信息、权限等
 */
export async function getInitialState(): Promise<{
  currentUser?: API.CurrentUser;
}> {
  const token = getToken();
  if (!token) {
    // 未登录跳转
    if (window.location.pathname !== '/login') {
      history.push('/login');
    }
    return {};
  }

  try {
    const currentUser = await getCurrentUser();
    return { currentUser };
  } catch {
    // Token失效
    history.push('/login');
    return {};
  }
}

/**
 * ProLayout 运行时配置
 */
export const layout = () => {
  return {
    logo: undefined,
    menu: { locale: false },
    logout: () => {
      localStorage.removeItem('access_token');
      history.push('/login');
    },
  };
};
