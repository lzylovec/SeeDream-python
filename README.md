# Seedream 图片生成网站

基于火山引擎 Seedream 模型的图片生成网站，支持文生图和图文生图功能。

## 功能特性

- 文生图 (Text-to-Image)：根据文本描述生成图片
- 图文生图 (Image-to-Image)：基于参考图片和文本描述生成新图片
- 响应式网页界面
- 错误处理和用户反馈

## 技术栈

- 后端：Python + Flask
- AI模型：Seedream (doubao-seedream-4-0-250828)
- 前端：HTML + CSS + JavaScript
- SDK：volcengine-python-sdk

## 安装和运行

1. 克隆项目代码

2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

3. 配置环境变量：
   在 `.env` 文件中配置您的 API Key：
   ```env
   ARK_API_KEY=your_api_key_here
   FLASK_ENV=development
   ```

4. 运行应用：
   ```bash
   python app.py
   ```

5. 访问网站：
   打开浏览器访问 `http://localhost:5000`

## API 接口

### 文生图接口

- URL: `/api/generate/text-to-image`
- 方法: POST
- 参数:
  - `prompt` (必需): 图片描述文本
  - `size` (可选): 图片尺寸，默认为"2K"
  - `watermark` (可选): 是否添加水印，默认为true

### 图文生图接口

- URL: `/api/generate/image-to-image`
- 方法: POST
- 参数:
  - `prompt` (必需): 图片描述文本
  - `image_url` (必需): 参考图片URL
  - `size` (可选): 图片尺寸，默认为"2K"
  - `watermark` (可选): 是否添加水印，默认为true

## 部署

可以使用 Gunicorn 部署到生产环境：

```bash
gunicorn --bind 0.0.0.0:5000 app:app
```

## 注意事项

1. API Key 安全：
   - 请勿在代码中硬编码 API Key
   - 使用环境变量存储敏感信息

2. 使用限制：
   - 注意 API 调用频率限制
   - 监控 API 配额使用情况

3. 内容安全：
   - 避免生成敏感或不当内容
   - 遵守相关法律法规