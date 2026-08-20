declare namespace Job {
  /** 岗位状态 */
  type Status = 'draft' | 'open' | 'closed' | 'archived';

  /** 岗位基本信息 */
  interface Item {
    id: string;
    title: string;
    department: string;
    location: string;
    status: Status;
    salaryMin: number;
    salaryMax: number;
    experienceMin: number;
    experienceMax: number;
    education: string;
    requiredSkills: string[];
    preferredSkills: string[];
    description: string;
    createdAt: string;
    updatedAt: string;
  }

  /** 创建/编辑岗位参数 */
  interface CreateParams {
    title: string;
    department: string;
    location: string;
    salaryMin: number;
    salaryMax: number;
    experienceMin: number;
    experienceMax: number;
    education: string;
    requiredSkills: string[];
    preferredSkills?: string[];
    description: string;
  }
}
