import React, { useEffect, useState } from 'react';
import { PageContainer } from '@ant-design/pro-components';
import {
  Card,
  Table,
  Button,
  Modal,
  Form,
  Input,
  Select,
  InputNumber,
  Slider,
  Space,
  Tag,
  Popconfirm,
  message,
} from 'antd';
import { PlusOutlined, ApiOutlined } from '@ant-design/icons';
import {
  getLLMModels,
  createLLMModel,
  updateLLMModel,
  deleteLLMModel,
  testLLMConnection,
  type LLMModel,
  type LLMModelParams,
} from '@/services/llm';

const LLMConfigPage: React.FC = () => {
  const [models, setModels] = useState<LLMModel[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingModel, setEditingModel] = useState<LLMModel | null>(null);
  const [form] = Form.useForm();

  const fetchModels = async () => {
    setLoading(true);
    try {
      const data = await getLLMModels();
      setModels(data);
    } catch {
      message.error('获取模型列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchModels();
  }, []);

  const handleSubmit = async () => {
    const values = await form.validateFields();
    try {
      if (editingModel) {
        await updateLLMModel(editingModel.id, values);
        message.success('更新成功');
      } else {
        await createLLMModel(values);
        message.success('创建成功');
      }
      setModalOpen(false);
      form.resetFields();
      setEditingModel(null);
      fetchModels();
    } catch {
      message.error('操作失败');
    }
  };

  const handleTest = async (id: string) => {
    try {
      const result = await testLLMConnection(id);
      if (result.success) {
        message.success('连接测试成功');
      } else {
        message.error(`连接测试失败: ${result.message}`);
      }
    } catch {
      message.error('连接测试失败');
    }
  };

  const columns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    {
      title: '提供商',
      dataIndex: 'provider',
      key: 'provider',
      render: (provider: string) => {
        const colorMap: Record<string, string> = {
          openai: 'green',
          azure: 'blue',
          local: 'orange',
        };
        return <Tag color={colorMap[provider]}>{provider.toUpperCase()}</Tag>;
      },
    },
    { title: '模型', dataIndex: 'model', key: 'model' },
    { title: '最大Tokens', dataIndex: 'maxTokens', key: 'maxTokens' },
    { title: 'Temperature', dataIndex: 'temperature', key: 'temperature' },
    {
      title: '默认',
      dataIndex: 'isDefault',
      key: 'isDefault',
      render: (isDefault: boolean) => isDefault ? <Tag color="success">默认</Tag> : '-',
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: any, record: LLMModel) => (
        <Space>
          <a onClick={() => handleTest(record.id)}>
            <ApiOutlined /> 测试
          </a>
          <a
            onClick={() => {
              setEditingModel(record);
              form.setFieldsValue(record);
              setModalOpen(true);
            }}
          >
            编辑
          </a>
          <Popconfirm
            title="确定删除该模型配置？"
            onConfirm={async () => {
              await deleteLLMModel(record.id);
              message.success('删除成功');
              fetchModels();
            }}
          >
            <a style={{ color: '#ff4d4f' }}>删除</a>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <PageContainer>
      <Card
        title="LLM模型配置"
        extra={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              setEditingModel(null);
              form.resetFields();
              setModalOpen(true);
            }}
          >
            添加模型
          </Button>
        }
      >
        <Table
          dataSource={models}
          columns={columns}
          rowKey="id"
          loading={loading}
          pagination={false}
        />
      </Card>

      <Modal
        title={editingModel ? '编辑模型' : '添加模型'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => {
          setModalOpen(false);
          setEditingModel(null);
          form.resetFields();
        }}
        width={600}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="配置名称" rules={[{ required: true, message: '请输入配置名称' }]}>
            <Input placeholder="例如: GPT-4o" />
          </Form.Item>
          <Form.Item name="provider" label="提供商" rules={[{ required: true, message: '请选择提供商' }]}>
            <Select
              options={[
                { label: 'OpenAI', value: 'openai' },
                { label: 'Azure OpenAI', value: 'azure' },
                { label: '本地模型', value: 'local' },
              ]}
            />
          </Form.Item>
          <Form.Item name="model" label="模型名称" rules={[{ required: true, message: '请输入模型名称' }]}>
            <Input placeholder="例如: gpt-4o, gpt-3.5-turbo" />
          </Form.Item>
          <Form.Item name="apiKey" label="API Key">
            <Input.Password placeholder="请输入API Key" />
          </Form.Item>
          <Form.Item name="endpoint" label="API端点">
            <Input placeholder="默认使用官方端点" />
          </Form.Item>
          <Form.Item name="maxTokens" label="最大Tokens" initialValue={4096}>
            <InputNumber min={256} max={128000} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="temperature" label="Temperature" initialValue={0.7}>
            <Slider min={0} max={2} step={0.1} marks={{ 0: '精确', 1: '平衡', 2: '创造' }} />
          </Form.Item>
        </Form>
      </Modal>
    </PageContainer>
  );
};

export default LLMConfigPage;
