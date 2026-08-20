import request from '@/utils/request';

/** 发起匹配任务 */
export async function runMatching(params: Matching.RunParams): Promise<Matching.Task> {
  return request<Matching.Task>('/api/matching/run', {
    method: 'POST',
    data: params,
  });
}

/** 获取匹配任务列表 */
export async function getMatchingTasks(params: {
  page?: number;
  pageSize?: number;
  status?: Matching.TaskStatus;
}): Promise<API.PaginatedResponse<Matching.Task>> {
  return request<API.PaginatedResponse<Matching.Task>>('/api/matching/tasks', {
    method: 'GET',
    params,
  });
}

/** 获取匹配结果列表 */
export async function getMatchingResults(params: {
  taskId?: string;
  jobId?: string;
  page?: number;
  pageSize?: number;
  minScore?: number;
}): Promise<API.PaginatedResponse<Matching.ResultItem>> {
  return request<API.PaginatedResponse<Matching.ResultItem>>('/api/matching/results', {
    method: 'GET',
    params,
  });
}

/** 获取单个匹配结果详情 */
export async function getMatchingResultDetail(id: string): Promise<Matching.ResultItem> {
  return request<Matching.ResultItem>(`/api/matching/results/${id}`, { method: 'GET' });
}
