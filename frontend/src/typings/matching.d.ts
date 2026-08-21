declare namespace Matching {
  /** 匹配结果条目 */
  interface ResultItem {
    id: string;
    resume_id: string;
    job_id: string;
    overall_score: number;
    skill_score: number | null;
    experience_score: number | null;
    education_score: number | null;
    soft_skill_score: number | null;
    grade: 'excellent' | 'qualified' | 'unqualified' | null;
    recommendation: string | null;
    details: Record<string, any> | null;
    model_used: string | null;
    created_at: string;
  }

  /** 发起匹配参数 */
  interface RunParams {
    job_id: string;
    resume_ids: string[];
    llm_config_id?: string;
  }
}
