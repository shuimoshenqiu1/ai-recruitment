import React from 'react';
import { LoginForm, ProFormText } from '@ant-design/pro-components';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { message } from 'antd';
import { history, useModel } from '@umijs/max';
import { login } from '@/services/auth';

const LoginPage: React.FC = () => {
  const { refresh } = useModel('@@initialState');

  const handleSubmit = async (values: API.LoginParams) => {
    try {
      const result = await login(values);
      message.success('登录成功');
      await refresh();
      history.push('/resume/list');
      return result;
    } catch (error) {
      message.error('登录失败，请检查用户名和密码');
    }
  };

  return (
    <div style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      minHeight: '100vh',
      background: '#f0f2f5',
    }}>
      <LoginForm
        title="AI招聘匹配系统"
        subTitle="智能简历解析与岗位匹配平台"
        onFinish={handleSubmit}
      >
        <ProFormText
          name="email"
          fieldProps={{
            size: 'large',
            prefix: <UserOutlined />,
          }}
          placeholder="邮箱"
          rules={[{ required: true, message: '请输入邮箱' }]}
        />
        <ProFormText.Password
          name="password"
          fieldProps={{
            size: 'large',
            prefix: <LockOutlined />,
          }}
          placeholder="密码"
          rules={[{ required: true, message: '请输入密码' }]}
        />
      </LoginForm>
    </div>
  );
};

export default LoginPage;
