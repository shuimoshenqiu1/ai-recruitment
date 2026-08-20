import React from 'react';
import { ProTable, PageContainer } from '@ant-design/pro-components';
import type { ProColumns, ActionType } from '@ant-design/pro-components';
import { Button, Tag, Popconfirm, message } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { history } from '@umijs/max';
import { getResumeList, deleteResume } from '@/services/resume';

const statusMap: Record<Resume.Status, { text: string; color: string }> = {
  pending: { text: '待解析', color: 'default' },
  parsing: { text: '解析中', color: 'processing' },
  parsed: { text: '已解析', color: 'success' },
  failed: { text: '解析失败', color: 'error' },
};

const ResumeListPage: React.FC = () => {
  const actionRef = React.useRef<ActionType>();

  const columns: ProColumns<Resume.Item>[] = [
    {
      title: '候选人',
      dataIndex: 'candidateName',
      ellipsis: true,
    },
    {
      title: '邮箱',
      dataIndex: 'email',
      ellipsis: true,
      search: false,
    },
    {
      title: '技能',
      dataIndex: 'skills',
      search: false,
      render: (_, record) => (
        <>
          {record.skills?.slice(0, 3).map((skill) => (
            <Tag key={skill}>{skill}</Tag>
          ))}
          {record.skills?.length > 3 && <Tag>+{record.skills.length - 3}</Tag>}
        </>
      ),
    },
    {
      title: '工作年限',
      dataIndex: 'experience',
      valueType: 'digit',
      search: false,
      render: (_, record) => `${record.experience}年`,
    },
    {
      title: '状态',
      dataIndex: 'status',
      valueType: 'select',
      valueEnum: {
        pending: { text: '待解析' },
        parsing: { text: '解析中' },
        parsed: { text: '已解析' },
        failed: { text: '解析失败' },
      },
      render: (_, record) => {
        const { text, color } = statusMap[record.status];
        return <Tag color={color}>{text}</Tag>;
      },
    },
    {
      title: '上传时间',
      dataIndex: 'uploadedAt',
      valueType: 'dateTime',
      search: false,
      sorter: true,
    },
    {
      title: '操作',
      valueType: 'option',
      render: (_, record) => [
        <a key="detail" onClick={() => history.push(`/resume/detail/${record.id}`)}>
          查看
        </a>,
        <Popconfirm
          key="delete"
          title="确定删除该简历？"
          onConfirm={async () => {
            await deleteResume(record.id);
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
      <ProTable<Resume.Item>
        headerTitle="简历列表"
        actionRef={actionRef}
        rowKey="id"
        columns={columns}
        toolBarRender={() => [
          <Button
            key="upload"
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => history.push('/resume/upload')}
          >
            上传简历
          </Button>,
        ]}
        request={async (params) => {
          const { current, pageSize, ...rest } = params;
          const result = await getResumeList({
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

export default ResumeListPage;
