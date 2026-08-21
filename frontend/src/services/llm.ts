import request from '@/utils/request';

export interface LLMModel {
  id: string;
  name: string;
  provider_type: string;
  endpoint: string;
  api_key?: string;
  model_name: string;
  is_default: boolean;
  is_active: boolean;
  config?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface LLMModelParams {
  name: string;
  provider_type: string;
  endpoint: string;
  api_key?: string;
  model_name: string;
  is_default?: boolean;
  is_active?: boolean;
  config?: Record<string, any>;
}

/** 获取LLM配置列表 */
export async function getLLMModels(): Promise<LLMModel[]> {
  return request<LLMModel[]>('/api/v1/llm-configs', { method: 'GET' });
}

/** 创建LLM配置 */
export async function createLLMModel(params: LLMModelParams): Promise<LLMModel> {
  return request<LLMModel>('/api/v1/llm-configs', {
    method: 'POST',
    data: params,
  });
}

/** 更新LLM配置 */
export async function updateLLMModel(id: string, params: Partial<LLMModelParams>): Promise<LLMModel> {
  return request<LLMModel>(`/api/v1/llm-configs/${id}`, {
    method: 'PUT',
    data: params,
  });
}

/** 删除LLM配置 */
export async function deleteLLMModel(id: string): Promise<void> {
  return request(`/api/v1/llm-configs/${id}`, { method: 'DELETE' });
}

/** 测试LLM连接 */
export async function testLLMConnection(id: string): Promise<{ success: boolean; message: string }> {
  return request<{ success: boolean; message: string }>(`/api/v1/llm-configs/${id}/test`, {
    method: 'POST',
  });
}
