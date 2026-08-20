declare namespace Matching {
  /** 匹配任务状态 */
  type TaskStatus = 'pending' | 'running' | 'completed' | 'failed';

  /** 匹配任务 */
  interface Task {
    id: string;
    jobId: string;
    jobTitle: string;
    status: TaskStatus;
    resumeCount: number;
    completedCount: number;
    createdAt: string;
    completedAt?: string;
    modelUsed: string;
  }

  /** 匹配结果条目 */
  interface ResultItem {
    id: string;
    taskId: string;
    resumeId: string;
    candidateName: string;
    jobId: string;
    jobTitle: string;
    overallScore: number;
    skillScore: number;
    experienceScore: number;
    educationScore: number;
    analysis: string;
    recommendation: 'strong_match' | 'match' | 'partial_match' | 'no_match';
    createdAt: string;
  }

  /** 发起匹配参数 */
  interface RunParams {
    jobId: string;
    resumeIds?: string[]; // 不传则匹配所有简历
    modelId?: string;
  }
}
