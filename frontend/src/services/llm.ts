import request from '@/utils/request';

export interface LLMModel {
  id: string;
  name: string;
  provider: 'openai' | 'azure' | 'local';
  model: string;
  apiKey?: string;
  endpoint?: string;
  isDefault: boolean;
  maxTokens: number;
  temperature: number;
  createdAt: string;
}

export interface LLMModelParams {
  name: string;
  provider: 'openai' | 'azure' | 'local';
  model: string;
  apiKey?: string;
  endpoint?: string;
  isDefault?: boolean;
  maxTokens?: number;
  temperature?: number;
}

/** 获取LLM模型列表 */
export async function getLLMModels(): Promise<LLMModel[]> {
  return request<LLMModel[]>('/api/llm/models', { method: 'GET' });
}

/** 创建LLM模型配置 */
export async function createLLMModel(params: LLMModelParams): Promise<LLMModel> {
  return request<LLMModel>('/api/llm/models', {
    method: 'POST',
    data: params,
  });
}

/** 更新LLM模型配置 */
export async function updateLLMModel(id: string, params: Partial<LLMModelParams>): Promise<LLMModel> {
  return request<LLMModel>(`/api/llm/models/${id}`, {
    method: 'PUT',
    data: params,
  });
}

/** 删除LLM模型配置 */
export async function deleteLLMModel(id: string): Promise<void> {
  return request(`/api/llm/models/${id}`, { method: 'DELETE' });
}

/** 测试LLM连接 */
export async function testLLMConnection(id: string): Promise<{ success: boolean; message: string }> {
  return request<{ success: boolean; message: string }>(`/api/llm/models/${id}/test`, {
    method: 'POST',
  });
}
