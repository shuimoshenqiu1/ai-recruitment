import React from 'react';
import { ProTable, PageContainer } from '@ant-design/pro-components';
import type { ProColumns } from '@ant-design/pro-components';
import { Tag, Progress, Typography } from 'antd';
import { getMatchingResults } from '@/services/matching';

const { Paragraph } = Typography;

const recommendMap: Record<string, { text: string; color: string }> = {
  strong_match: { text: '强烈推荐', color: 'success' },
  match: { text: '推荐', color: 'processing' },
  partial_match: { text: '部分匹配', color: 'warning' },
  no_match: { text: '不匹配', color: 'error' },
};

const MatchingResultsPage: React.FC = () => {
  const columns: ProColumns<Matching.ResultItem>[] = [
    {
      title: '候选人',
      dataIndex: 'candidateName',
    },
    {
      title: '匹配岗位',
      dataIndex: 'jobTitle',
    },
    {
      title: '综合得分',
      dataIndex: 'overallScore',
      sorter: true,
      render: (_, record) => (
        <Progress
          percent={record.overallScore}
          size="small"
          strokeColor={record.overallScore >= 80 ? '#52c41a' : record.overallScore >= 60 ? '#1677ff' : '#faad14'}
        />
      ),
    },
    {
      title: '技能匹配',
      dataIndex: 'skillScore',
      search: false,
      render: (_, record) => `${record.skillScore}%`,
    },
    {
      title: '经验匹配',
      dataIndex: 'experienceScore',
      search: false,
      render: (_, record) => `${record.experienceScore}%`,
    },
    {
      title: '学历匹配',
      dataIndex: 'educationScore',
      search: false,
      render: (_, record) => `${record.educationScore}%`,
    },
    {
      title: '推荐等级',
      dataIndex: 'recommendation',
      valueType: 'select',
      valueEnum: {
        strong_match: { text: '强烈推荐' },
        match: { text: '推荐' },
        partial_match: { text: '部分匹配' },
        no_match: { text: '不匹配' },
      },
      render: (_, record) => {
        const { text, color } = recommendMap[record.recommendation] || { text: '未知', color: 'default' };
        return <Tag color={color}>{text}</Tag>;
      },
    },
    {
      title: 'AI分析',
      dataIndex: 'analysis',
      search: false,
      ellipsis: true,
      width: 200,
      render: (_, record) => (
        <Paragraph ellipsis={{ rows: 2, expandable: true }} style={{ marginBottom: 0 }}>
          {record.analysis}
        </Paragraph>
      ),
    },
    {
      title: '匹配时间',
      dataIndex: 'createdAt',
      valueType: 'dateTime',
      search: false,
      sorter: true,
    },
  ];

  return (
    <PageContainer>
      <ProTable<Matching.ResultItem>
        headerTitle="匹配结果"
        rowKey="id"
        columns={columns}
        request={async (params) => {
          const { current, pageSize, ...rest } = params;
          const result = await getMatchingResults({
            page: current,
            pageSize,
            ...rest,
          });
          return {
            data: result.list,
            total: result.total,
            success: true,
          };
        }}
        defaultSortOrder="descend"
        search={{
          labelWidth: 'auto',
        }}
      />
    </PageContainer>
  );
};

export default MatchingResultsPage;
