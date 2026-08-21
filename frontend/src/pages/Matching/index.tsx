import React, { useState, useEffect } from 'react';
import { PageContainer } from '@ant-design/pro-components';
import { Card, Form, Select, Button, message, Progress, Typography, Space, Alert } from 'antd';
import { ThunderboltOutlined } from '@ant-design/icons';
import { history } from '@umijs/max';
import { getJobList } from '@/services/job';
import { getResumeList } from '@/services/resume';
import { runMatching } from '@/services/matching';
import { getLLMModels } from '@/services/llm';

const { Title, Paragraph } = Typography;

const MatchingPage: React.FC = () => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [jobs, setJobs] = useState<Job.Item[]>([]);
  const [resumes, setResumes] = useState<Resume.Item[]>([]);
  const [models, setModels] = useState<{ id: string; name: string }[]>([]);
  const [progress, setProgress] = useState<number | null>(null);

  useEffect(() => {
    // 加载岗位列表
    getJobList({ page: 1, pageSize: 100, status: 'open' }).then((res) => {
      setJobs(res.list);
    });
    // 加载已解析简历
    getResumeList({ page: 1, pageSize: 100, status: 'parsed' }).then((res) => {
      setResumes(res.list);
    });
    // 加载可用模型
    getLLMModels().then((res) => {
      setModels(res.map((m) => ({ id: m.id, name: m.name })));
    });
  }, []);

  const handleRun = async () => {
    try {
      const values = await form.validateFields();
      setLoading(true);
      setProgress(0);

      const task = await runMatching({
        job_id: values.jobId,
        resume_ids: values.resumeIds?.length ? values.resumeIds : [],
        llm_config_id: values.modelId,
      });

      message.success('匹配任务已提交');
      setProgress(100);

      // 跳转到结果页
      setTimeout(() => {
        history.push('/matching/results');
      }, 1000);
    } catch {
      message.error('提交匹配任务失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <PageContainer>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Alert
          message="智能匹配"
          description="选择一个岗位，系统将使用AI模型对所有已解析的简历进行智能匹配打分，生成匹配报告。"
          type="info"
          showIcon
        />

        <Card>
          <Form form={form} layout="vertical">
            <Form.Item
              name="jobId"
              label="选择岗位"
              rules={[{ required: true, message: '请选择要匹配的岗位' }]}
            >
              <Select
                placeholder="请选择岗位"
                showSearch
                optionFilterProp="label"
                options={jobs.map((j) => ({ label: `${j.title} (${j.department})`, value: j.id }))}
              />
            </Form.Item>

            <Form.Item
              name="resumeIds"
              label="选择简历（不选则匹配全部已解析简历）"
            >
              <Select
                mode="multiple"
                placeholder="全部已解析简历"
                allowClear
                optionFilterProp="label"
                options={resumes.map((r) => ({
                  label: `${r.candidateName} - ${r.currentPosition || '未知'}`,
                  value: r.id,
                }))}
              />
            </Form.Item>

            <Form.Item
              name="modelId"
              label="AI模型"
            >
              <Select
                placeholder="使用默认模型"
                allowClear
                options={models.map((m) => ({ label: m.name, value: m.id }))}
              />
            </Form.Item>

            <Form.Item>
              <Button
                type="primary"
                size="large"
                icon={<ThunderboltOutlined />}
                loading={loading}
                onClick={handleRun}
                block
              >
                开始匹配
              </Button>
            </Form.Item>
          </Form>

          {progress !== null && (
            <Progress percent={progress} status={progress < 100 ? 'active' : 'success'} />
          )}
        </Card>
      </Space>
    </PageContainer>
  );
};

export default MatchingPage;
