declare namespace Resume {
  /** 简历状态 */
  type Status = 'pending' | 'parsing' | 'parsed' | 'failed';

  /** 简历基本信息 */
  interface Item {
    id: string;
    candidateName: string;
    email: string;
    phone: string;
    status: Status;
    fileName: string;
    uploadedAt: string;
    parsedAt?: string;
    skills: string[];
    experience: number; // 工作年限
    education: string;
    currentCompany?: string;
    currentPosition?: string;
  }

  /** 简历详情（含解析结果） */
  interface Detail extends Item {
    rawText: string;
    parsedData: ParsedData;
  }

  /** 解析结果结构 */
  interface ParsedData {
    basicInfo: {
      name: string;
      email: string;
      phone: string;
      location?: string;
    };
    education: EducationItem[];
    workExperience: WorkExperienceItem[];
    skills: SkillItem[];
    projects?: ProjectItem[];
    summary?: string;
  }

  interface EducationItem {
    school: string;
    degree: string;
    major: string;
    startDate: string;
    endDate: string;
  }

  interface WorkExperienceItem {
    company: string;
    position: string;
    startDate: string;
    endDate: string;
    description: string;
  }

  interface SkillItem {
    name: string;
    level: 'beginner' | 'intermediate' | 'advanced' | 'expert';
  }

  interface ProjectItem {
    name: string;
    role: string;
    description: string;
    technologies: string[];
  }

  /** 上传参数 */
  interface UploadParams {
    file: File;
  }
}
