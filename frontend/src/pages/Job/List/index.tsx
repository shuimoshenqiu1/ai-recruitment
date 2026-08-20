import React from 'react';
import { ProTable, PageContainer } from '@ant-design/pro-components';
import type { ProColumns, ActionType } from '@ant-design/pro-components';
import { Button, Tag, Popconfirm, message } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { history } from '@umijs/max';
import { getJobList, deleteJob, updateJobStatus } from '@/services/job';

const statusMap: Record<Job.Status, { text: string; color: string }> = {
  draft: { text: '草稿', color: 'default' },
  open: { text: '招聘中', color: 'success' },
  closed: { text: '已关闭', color: 'warning' },
  archived: { text: '已归档', color: 'default' },
};

const JobListPage: React.FC = () => {
  const actionRef = React.useRef<ActionType>();

  const columns: ProColumns<Job.Item>[] = [
    {
      title: '岗位名称',
      dataIndex: 'title',
      ellipsis: true,
    },
    {
      title: '部门',
      dataIndex: 'department',
    },
    {
      title: '工作地点',
      dataIndex: 'location',
      search: false,
    },
    {
      title: '薪资范围',
      search: false,
      render: (_, record) => `${record.salaryMin / 1000}k - ${record.salaryMax / 1000}k`,
    },
    {
      title: '经验要求',
      search: false,
      render: (_, record) => `${record.experienceMin}-${record.experienceMax}年`,
    },
    {
      title: '必备技能',
      dataIndex: 'requiredSkills',
      search: false,
      render: (_, record) => (
        <>
          {record.requiredSkills?.slice(0, 3).map((skill) => (
            <Tag key={skill} color="blue">{skill}</Tag>
          ))}
          {record.requiredSkills?.length > 3 && <Tag>+{record.requiredSkills.length - 3}</Tag>}
        </>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      valueType: 'select',
      valueEnum: {
        draft: { text: '草稿' },
        open: { text: '招聘中' },
        closed: { text: '已关闭' },
        archived: { text: '已归档' },
      },
      render: (_, record) => {
        const { text, color } = statusMap[record.status];
        return <Tag color={color}>{text}</Tag>;
      },
    },
    {
      title: '创建时间',
      dataIndex: 'createdAt',
      valueType: 'dateTime',
      search: false,
      sorter: true,
    },
    {
      title: '操作',
      valueType: 'option',
      render: (_, record) => [
        <a key="edit" onClick={() => history.push(`/job/edit/${record.id}`)}>
          编辑
        </a>,
        record.status === 'draft' && (
          <a
            key="publish"
            onClick={async () => {
              await updateJobStatus(record.id, 'open');
              message.success('发布成功');
              actionRef.current?.reload();
            }}
          >
            发布
          </a>
        ),
        <Popconfirm
          key="delete"
          title="确定删除该岗位？"
          onConfirm={async () => {
            await deleteJob(record.id);
            message.success('删除成功');
            actionRef.current?.reload();
          }}
        >
          <a style={{ color: '#ff4d4f' }}>删除</a>
        </Popconfirm>,
      ],
    },
  ];

  return (
    <PageContainer>
      <ProTable<Job.Item>
        headerTitle="岗位列表"
        actionRef={actionRef}
        rowKey="id"
        columns={columns}
        toolBarRender={() => [
          <Button
            key="create"
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => history.push('/job/create')}
          >
            创建岗位
          </Button>,
        ]}
        request={async (params) => {
          const { current, pageSize, ...rest } = params;
          const result = await getJobList({
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
      />
    </PageContainer>
  );
};

export default JobListPage;
