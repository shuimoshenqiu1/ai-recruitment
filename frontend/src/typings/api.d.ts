declare namespace API {
  /** 通用API响应结构 */
  interface Response<T = any> {
    code: number;
    message: string;
    data: T;
  }

  /** 分页响应 */
  interface PaginatedResponse<T = any> {
    list: T[];
    total: number;
    page: number;
    pageSize: number;
  }

  /** 当前用户信息 */
  interface CurrentUser {
    id: string;
    username: string;
    email: string;
    role: 'admin' | 'recruiter' | 'viewer';
    avatar?: string;
  }

  /** 登录参数 */
  interface LoginParams {
    username: string;
    password: string;
  }

  /** 登录响应 */
  interface LoginResult {
    access_token: string;
    token_type: string;
    user: CurrentUser;
  }
}
