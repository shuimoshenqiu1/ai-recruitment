import request from '@/utils/request';

/** 获取简历列表 */
export async function getResumeList(params: {
  page?: number;
  pageSize?: number;
  keyword?: string;
  status?: Resume.Status;
}): Promise<API.PaginatedResponse<Resume.Item>> {
  return request<API.PaginatedResponse<Resume.Item>>('/api/v1/resumes', {
    method: 'GET',
    params,
  });
}

/** 获取简历详情 */
export async function getResumeDetail(id: string): Promise<Resume.Detail> {
  return request<Resume.Detail>(`/api/v1/resumes/${id}`, { method: 'GET' });
}

/** 上传简历（返回创建的简历ID） */
export async function uploadResume(file: File): Promise<{ id: string }> {
  const formData = new FormData();
  formData.append('file', file);

  return request<{ id: string }>('/api/v1/resumes/upload', {
    method: 'POST',
    data: formData,
    headers: { 'Content-Type': 'multipart/form-data' },
  });
}

/** 删除简历 */
export async function deleteResume(id: string): Promise<void> {
  return request(`/api/v1/resumes/${id}`, { method: 'DELETE' });
}

/** 重新解析简历 */
export async function reparseResume(id: string): Promise<void> {
  return request(`/api/v1/resumes/${id}/parse`, { method: 'POST' });
}
