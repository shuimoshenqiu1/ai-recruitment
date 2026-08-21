import request from '@/utils/request';

/** 获取岗位列表 */
export async function getJobList(params: {
  page?: number;
  pageSize?: number;
  keyword?: string;
  status?: Job.Status;
}): Promise<API.PaginatedResponse<Job.Item>> {
  return request<API.PaginatedResponse<Job.Item>>('/api/v1/jobs', {
    method: 'GET',
    params,
  });
}

/** 获取岗位详情 */
export async function getJobDetail(id: string): Promise<Job.Item> {
  return request<Job.Item>(`/api/v1/jobs/${id}`, { method: 'GET' });
}

/** 创建岗位 */
export async function createJob(params: Job.CreateParams): Promise<Job.Item> {
  return request<Job.Item>('/api/v1/jobs', {
    method: 'POST',
    data: params,
  });
}

/** 更新岗位 */
export async function updateJob(id: string, params: Partial<Job.CreateParams>): Promise<Job.Item> {
  return request<Job.Item>(`/api/v1/jobs/${id}`, {
    method: 'PUT',
    data: params,
  });
}

/** 删除岗位 */
export async function deleteJob(id: string): Promise<void> {
  return request(`/api/v1/jobs/${id}`, { method: 'DELETE' });
}

/** 更新岗位状态 */
export async function updateJobStatus(id: string, status: Job.Status): Promise<void> {
  return request(`/api/v1/jobs/${id}/status`, {
    method: 'PATCH',
    data: { status },
  });
}
