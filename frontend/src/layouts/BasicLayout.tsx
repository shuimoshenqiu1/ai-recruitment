import React from 'react';
import { ProLayout } from '@ant-design/pro-components';
import { Outlet, useModel, history } from '@umijs/max';
import {
  FileTextOutlined,
  SolutionOutlined,
  ThunderboltOutlined,
  SettingOutlined,
  LogoutOutlined,
} from '@ant-design/icons';
import { Dropdown } from 'antd';

const BasicLayout: React.FC = () => {
  const { initialState } = useModel('@@initialState');

  return (
    <ProLayout
      title="AI招聘匹配系统"
      logo={false}
      layout="mix"
      fixedHeader
      fixSiderbar
      route={{
        routes: [
          {
            path: '/resume',
            name: '简历管理',
            icon: <FileTextOutlined />,
            routes: [
              { path: '/resume/list', name: '简历列表' },
              { path: '/resume/upload', name: '简历上传' },
            ],
          },
          {
            path: '/job',
            name: '岗位管理',
            icon: <SolutionOutlined />,
            routes: [
              { path: '/job/list', name: '岗位列表' },
              { path: '/job/create', name: '创建岗位' },
            ],
          },
          {
            path: '/matching',
            name: '智能匹配',
            icon: <ThunderboltOutlined />,
            routes: [
              { path: '/matching/index', name: '匹配任务' },
              { path: '/matching/results', name: '匹配结果' },
            ],
          },
          {
            path: '/settings',
            name: '系统设置',
            icon: <SettingOutlined />,
            routes: [
              { path: '/settings/llm', name: 'LLM配置' },
            ],
          },
        ],
      }}
      avatarProps={{
        title: initialState?.currentUser?.username || '用户',
        render: (_, dom) => (
          <Dropdown
            menu={{
              items: [
                {
                  key: 'logout',
                  icon: <LogoutOutlined />,
                  label: '退出登录',
                  onClick: () => {
                    localStorage.removeItem('access_token');
                    history.push('/login');
                  },
                },
              ],
            }}
          >
            {dom}
          </Dropdown>
        ),
      }}
      menuItemRender={(item, dom) => (
        <div onClick={() => item.path && history.push(item.path)}>
          {dom}
        </div>
      )}
    >
      <Outlet />
    </ProLayout>
  );
};

export default BasicLayout;
