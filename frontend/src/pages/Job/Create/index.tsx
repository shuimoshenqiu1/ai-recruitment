import React, { useEffect, useState } from 'react';
import {
  PageContainer,
  ProForm,
  ProFormText,
  ProFormTextArea,
  ProFormDigit,
  ProFormSelect,
} from '@ant-design/pro-components';
import { Card, message } from 'antd';
import { history, useParams } from '@umijs/max';
import { createJob, getJobDetail, updateJob } from '@/services/job';

const JobCreatePage: React.FC = () => {
  const { id } = useParams<{ id?: string }>();
  const isEdit = Boolean(id);
  const [initialValues, setInitialValues] = useState<Partial<Job.CreateParams>>({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isEdit && id) {
      setLoading(true);
      getJobDetail(id)
        .then((data) => setInitialValues(data))
        .finally(() => setLoading(false));
    }
  }, [id, isEdit]);

  const handleSubmit = async (values: Job.CreateParams) => {
    try {
      if (isEdit && id) {
        await updateJob(id, values);
        message.success('更新成功');
      } else {
        await createJob(values);
        message.success('创建成功');
      }
      history.push('/job/list');
    } catch {
      message.error(isEdit ? '更新失败' : '创建失败');
    }
  };

  return (
    <PageContainer title={isEdit ? '编辑岗位' : '创建岗位'}>
      <Card loading={loading}>
        <ProForm<Job.CreateParams>
          initialValues={initialValues}
          onFinish={handleSubmit}
          layout="horizontal"
          labelCol={{ span: 4 }}
          wrapperCol={{ span: 16 }}
        >
          <ProFormText
            name="title"
            label="岗位名称"
            placeholder="请输入岗位名称"
            rules={[{ required: true, message: '请输入岗位名称' }]}
          />
          <ProFormText
            name="department"
            label="部门"
            placeholder="请输入所属部门"
            rules={[{ required: true, message: '请输入部门' }]}
          />
          <ProFormText
            name="location"
            label="工作地点"
            placeholder="请输入工作地点"
            rules={[{ required: true, message: '请输入工作地点' }]}
          />
          <ProFormDigit
            name="salaryMin"
            label="最低薪资(月/元)"
            min={0}
            rules={[{ required: true, message: '请输入最低薪资' }]}
          />
          <ProFormDigit
            name="salaryMax"
            label="最高薪资(月/元)"
            min={0}
            rules={[{ required: true, message: '请输入最高薪资' }]}
          />
          <ProFormDigit
            name="experienceMin"
            label="最低经验(年)"
            min={0}
            max={30}
            rules={[{ required: true, message: '请输入最低经验要求' }]}
          />
          <ProFormDigit
            name="experienceMax"
            label="最高经验(年)"
            min={0}
            max={30}
            rules={[{ required: true, message: '请输入最高经验要求' }]}
          />
          <ProFormSelect
            name="education"
            label="学历要求"
            options={[
              { label: '不限', value: '不限' },
              { label: '大专', value: '大专' },
              { label: '本科', value: '本科' },
              { label: '硕士', value: '硕士' },
              { label: '博士', value: '博士' },
            ]}
            rules={[{ required: true, message: '请选择学历要求' }]}
          />
          <ProFormSelect
            name="requiredSkills"
            label="必备技能"
            mode="tags"
            placeholder="输入技能名称后按回车添加"
            rules={[{ required: true, message: '请添加至少一个必备技能' }]}
          />
          <ProFormSelect
            name="preferredSkills"
            label="加分技能"
            mode="tags"
            placeholder="输入技能名称后按回车添加"
          />
          <ProFormTextArea
            name="description"
            label="岗位描述"
            placeholder="请输入详细的岗位描述"
            rules={[{ required: true, message: '请输入岗位描述' }]}
            fieldProps={{ rows: 6 }}
          />
        </ProForm>
      </Card>
    </PageContainer>
  );
};

export default JobCreatePage;
