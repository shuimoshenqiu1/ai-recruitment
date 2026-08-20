import { defineConfig } from '@umijs/max';

export default defineConfig({
  antd: {},
  model: {},
  initialState: {},
  request: {},
  layout: {
    title: 'AI招聘匹配系统',
    locale: false,
  },
  routes: [
    {
      path: '/login',
      component: './Login',
      layout: false,
    },
    {
      path: '/',
      redirect: '/resume/list',
    },
    {
      name: '简历管理',
      path: '/resume',
      icon: 'FileTextOutlined',
      routes: [
        { name: '简历列表', path: '/resume/list', component: './Resume/List' },
        { name: '简历上传', path: '/resume/upload', component: './Resume/Upload' },
        { name: '简历详情', path: '/resume/detail/:id', component: './Resume/Detail', hideInMenu: true },
      ],
    },
    {
      name: '岗位管理',
      path: '/job',
      icon: 'SolutionOutlined',
      routes: [
        { name: '岗位列表', path: '/job/list', component: './Job/List' },
        { name: '创建岗位', path: '/job/create', component: './Job/Create' },
        { name: '编辑岗位', path: '/job/edit/:id', component: './Job/Create', hideInMenu: true },
      ],
    },
    {
      name: '智能匹配',
      path: '/matching',
      icon: 'ThunderboltOutlined',
      routes: [
        { name: '执行匹配', path: '/matching', component: './Matching', hideInMenu: true },
        { name: '匹配任务', path: '/matching/index', component: './Matching' },
        { name: '匹配结果', path: '/matching/results', component: './Matching/Results' },
      ],
    },
    {
      name: '系统设置',
      path: '/settings',
      icon: 'SettingOutlined',
      routes: [
        { name: 'LLM配置', path: '/settings/llm', component: './Settings/LLMConfig' },
      ],
    },
  ],
  proxy: {
    '/api': {
      target: process.env.API_BASE_URL || 'http://localhost:8000',
      changeOrigin: true,
    },
  },
  theme: {
    'primary-color': '#1677ff',
  },
});
