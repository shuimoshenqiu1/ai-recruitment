import request from '@/utils/request';

/** 发起匹配任务 */
export async function runMatching(params: Matching.RunParams): Promise<Matching.Task> {
  return request<Matching.Task>('/api/v1/matching/execute', {
    method: 'POST',
    data: params,
  });
}

/** 获取匹配结果列表 */
export async function getMatchingResults(params: {
  jobId: string;
  page?: number;
  pageSize?: number;
  minScore?: number;
  grade?: string;
}): Promise<API.PaginatedResponse<Matching.ResultItem>> {
  return request<API.PaginatedResponse<Matching.ResultItem>>('/api/v1/matching/results', {
    method: 'GET',
    params,
  });
}

/** 获取单个匹配结果详情 */
export async function getMatchingResultDetail(id: string): Promise<Matching.ResultItem> {
  return request<Matching.ResultItem>(`/api/v1/matching/results/${id}`, { method: 'GET' });
}

/** 导出匹配结果Excel */
export async function exportMatchingResults(params: {
  job_id: string;
  min_score?: number;
  grades?: string[];
}): Promise<Blob> {
  return request<Blob>('/api/v1/matching/export', {
    method: 'POST',
    data: params,
  });
}
