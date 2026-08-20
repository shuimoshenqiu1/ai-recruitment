import React, { useEffect, useState } from 'react';
import { PageContainer } from '@ant-design/pro-components';
import { Card, Descriptions, Tag, Spin, Timeline, Table, Typography, Space, Button, message } from 'antd';
import { useParams } from '@umijs/max';
import { getResumeDetail, reparseResume } from '@/services/resume';
import { ReloadOutlined } from '@ant-design/icons';

const { Title } = Typography;

const ResumeDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState<Resume.Detail | null>(null);

  const fetchDetail = async () => {
    if (!id) return;
    setLoading(true);
    try {
      const data = await getResumeDetail(id);
      setDetail(data);
    } catch {
      message.error('获取简历详情失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDetail();
  }, [id]);

  if (loading) {
    return (
      <PageContainer>
        <Spin tip="加载中..." style={{ display: 'block', marginTop: 100 }} />
      </PageContainer>
    );
  }

  if (!detail) {
    return <PageContainer>简历不存在</PageContainer>;
  }

  const { parsedData } = detail;

  return (
    <PageContainer
      title={detail.candidateName}
      extra={[
        <Button
          key="reparse"
          icon={<ReloadOutlined />}
          onClick={async () => {
            await reparseResume(detail.id);
            message.success('已重新提交解析');
            fetchDetail();
          }}
        >
          重新解析
        </Button>,
      ]}
    >
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        {/* 基本信息 */}
        <Card title="基本信息">
          <Descriptions column={3}>
            <Descriptions.Item label="姓名">{parsedData?.basicInfo?.name}</Descriptions.Item>
            <Descriptions.Item label="邮箱">{parsedData?.basicInfo?.email}</Descriptions.Item>
            <Descriptions.Item label="电话">{parsedData?.basicInfo?.phone}</Descriptions.Item>
            <Descriptions.Item label="工作年限">{detail.experience}年</Descriptions.Item>
            <Descriptions.Item label="学历">{detail.education}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={detail.status === 'parsed' ? 'success' : 'processing'}>
                {detail.status === 'parsed' ? '已解析' : '解析中'}
              </Tag>
            </Descriptions.Item>
          </Descriptions>
        </Card>

        {/* 技能标签 */}
        <Card title="技能">
          {parsedData?.skills?.map((skill) => (
            <Tag key={skill.name} color="blue" style={{ margin: '4px' }}>
              {skill.name} ({skill.level})
            </Tag>
          ))}
        </Card>

        {/* 工作经历 */}
        <Card title="工作经历">
          <Timeline>
            {parsedData?.workExperience?.map((exp, idx) => (
              <Timeline.Item key={idx}>
                <Title level={5}>{exp.company} - {exp.position}</Title>
                <p style={{ color: '#999' }}>{exp.startDate} ~ {exp.endDate}</p>
                <p>{exp.description}</p>
              </Timeline.Item>
            ))}
          </Timeline>
        </Card>

        {/* 教育经历 */}
        <Card title="教育经历">
          <Table
            dataSource={parsedData?.education}
            rowKey={(_, idx) => String(idx)}
            pagination={false}
            columns={[
              { title: '学校', dataIndex: 'school' },
              { title: '学位', dataIndex: 'degree' },
              { title: '专业', dataIndex: 'major' },
              { title: '时间', render: (_, r) => `${r.startDate} - ${r.endDate}` },
            ]}
          />
        </Card>
      </Space>
    </PageContainer>
  );
};

export default ResumeDetailPage;
