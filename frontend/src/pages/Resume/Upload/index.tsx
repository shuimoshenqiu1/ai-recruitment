import React, { useState } from 'react';
import { PageContainer } from '@ant-design/pro-components';
import { Upload, message, Card, Typography, Space } from 'antd';
import { InboxOutlined, FileTextOutlined } from '@ant-design/icons';
import { history } from '@umijs/max';
import { uploadResume } from '@/services/resume';

const { Dragger } = Upload;
const { Title, Paragraph } = Typography;

const ResumeUploadPage: React.FC = () => {
  const [uploading, setUploading] = useState(false);

  return (
    <PageContainer>
      <Card>
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <div style={{ textAlign: 'center' }}>
            <Title level={4}>上传简历</Title>
            <Paragraph type="secondary">
              支持 PDF、Word（.doc/.docx）格式，系统将自动解析简历内容
            </Paragraph>
          </div>

          <Dragger
            name="file"
            multiple
            accept=".pdf,.doc,.docx"
            disabled={uploading}
            customRequest={async ({ file, onSuccess, onError }) => {
              setUploading(true);
              try {
                const result = await uploadResume(file as File);
                message.success('上传成功，正在解析...');
                onSuccess?.(result);
                // 上传成功后跳转到详情页
                history.push(`/resume/detail/${result.id}`);
              } catch (error) {
                message.error('上传失败');
                onError?.(error as Error);
              } finally {
                setUploading(false);
              }
            }}
            showUploadList={{
              showPreviewIcon: true,
              showRemoveIcon: true,
            }}
          >
            <p className="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p className="ant-upload-text">
              点击或拖拽文件到此区域上传
            </p>
            <p className="ant-upload-hint">
              支持单个或批量上传，支持 PDF、Word 格式
            </p>
          </Dragger>

          <Card size="small" title="支持的文件格式">
            <Space>
              <Tag icon={<FileTextOutlined />}>PDF (.pdf)</Tag>
              <Tag icon={<FileTextOutlined />}>Word (.doc)</Tag>
              <Tag icon={<FileTextOutlined />}>Word (.docx)</Tag>
            </Space>
          </Card>
        </Space>
      </Card>
    </PageContainer>
  );
};

// 本地使用的Tag组件简化
const Tag: React.FC<{ icon?: React.ReactNode; children: React.ReactNode }> = ({ icon, children }) => (
  <span style={{
    display: 'inline-flex',
    alignItems: 'center',
    gap: 4,
    padding: '4px 8px',
    border: '1px solid #d9d9d9',
    borderRadius: 4,
    fontSize: 13,
  }}>
    {icon}
    {children}
  </span>
);

export default ResumeUploadPage;
