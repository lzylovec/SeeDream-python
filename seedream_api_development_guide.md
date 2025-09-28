# Seedream 图片生成 API 开发指南

## 项目概述

本项目基于 Seedream 模型开发一个图片生成网站，支持文生图和图文生图两种功能。Seedream 是一个强大的AI图像生成模型，可以根据文本描述或结合现有图片生成高质量的图像。

## 技术栈

- **后端**: Python 3.7+
- **AI模型**: Seedream (doubao-seedream-4-0-250828)
- **SDK**: volcengine-python-sdk
- **API**: 火山引擎 ARK API

## 环境准备

### 1. Python 环境要求

确保您的系统已安装 Python 3.7 或更高版本：

```bash
python -V
```

### 2. 安装 Python SDK

使用 pip 安装火山引擎 Python SDK：

```bash
pip install 'volcengine-python-sdk[ark]'
```

如果安装遇到问题，可以尝试以下方法：

**Windows 系统安装失败时：**
```bash
pip install volcengine-python-sdk[ark]
```

**从源码安装：**
```bash
python setup.py install --user
```

**升级到最新版本：**
```bash
pip install -U 'volcengine-python-sdk[ark]'
```

### 3. API Key 配置

您需要获取火山引擎的 API Key：

1. 访问火山引擎控制台
2. 创建或获取您的 ARK API Key
3. 将 API Key 设置为环境变量：

```bash
export ARK_API_KEY="your_api_key_here"
```

或在代码中直接配置（不推荐用于生产环境）。

## 核心功能实现

### 1. 文生图功能 (Text-to-Image)

根据文本描述生成图片的功能实现：

```python
import os
from volcenginesdkarkruntime import Ark

# 初始化客户端
client = Ark(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=os.environ.get("ARK_API_KEY"),
)

def generate_image_from_text(prompt, size="2K", response_format="url", watermark=True):
    """
    文生图功能
    
    Args:
        prompt (str): 图片描述文本
        size (str): 图片尺寸，默认"2K"
        response_format (str): 返回格式，"url"或"b64_json"
        watermark (bool): 是否添加水印
    
    Returns:
        str: 生成图片的URL或base64数据
    """
    try:
        images_response = client.images.generate(
            model="doubao-seedream-4-0-250828",
            prompt=prompt,
            size=size,
            response_format=response_format,
            watermark=watermark
        )
        
        return images_response.data[0].url
        
    except Exception as e:
        print(f"图片生成失败: {e}")
        return None

# 使用示例
if __name__ == "__main__":
    prompt = "野玩与野餐，黑洞，黑洞里中一辆红色系数的复古车，极致冲击力，电影大片，天目蓝现，动感，对比色，oc渲染，光线追踪，动态"
    image_url = generate_image_from_text(prompt)
    if image_url:
        print(f"生成的图片URL: {image_url}")
```

### 2. 图文生图功能 (Image-to-Image)

基于现有图片和文本描述生成新图片：

```python
def generate_image_from_image_and_text(prompt, image_url, size="2K", response_format="url", watermark=True):
    """
    图文生图功能
    
    Args:
        prompt (str): 图片描述文本
        image_url (str): 参考图片的URL
        size (str): 图片尺寸，默认"2K"
        response_format (str): 返回格式，"url"或"b64_json"
        watermark (bool): 是否添加水印
    
    Returns:
        str: 生成图片的URL或base64数据
    """
    try:
        images_response = client.images.generate(
            model="doubao-seedream-4-0-250828",
            prompt=prompt,
            image=image_url,
            size=size,
            response_format=response_format,
            watermark=watermark
        )
        
        return images_response.data[0].url
        
    except Exception as e:
        print(f"图片生成失败: {e}")
        return None

# 使用示例
if __name__ == "__main__":
    prompt = "生成狗狗在草地上的近景画面"
    reference_image = "https://ark-project.tos-cn-beijing.volces.com/doc_image/seedream4_imageToImage.png"
    
    image_url = generate_image_from_image_and_text(prompt, reference_image)
    if image_url:
        print(f"生成的图片URL: {image_url}")
```

## API 参数说明

### 通用参数

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| model | string | 是 | 模型名称，固定为 "doubao-seedream-4-0-250828" |
| prompt | string | 是 | 图片描述文本，建议详细描述 |
| size | string | 否 | 图片尺寸，支持 "2K" 等 |
| response_format | string | 否 | 返回格式，"url" 或 "b64_json" |
| watermark | boolean | 否 | 是否添加水印，默认 true |

### 图文生图专用参数

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| image | string | 是 | 参考图片的URL地址 |

## 完整的网站后端示例

```python
import os
from flask import Flask, request, jsonify
from volcenginesdkarkruntime import Ark

app = Flask(__name__)

# 初始化 ARK 客户端
client = Ark(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=os.environ.get("ARK_API_KEY"),
)

@app.route('/api/generate/text-to-image', methods=['POST'])
def text_to_image():
    """文生图API接口"""
    try:
        data = request.get_json()
        prompt = data.get('prompt')
        size = data.get('size', '2K')
        watermark = data.get('watermark', True)
        
        if not prompt:
            return jsonify({'error': '缺少prompt参数'}), 400
        
        images_response = client.images.generate(
            model="doubao-seedream-4-0-250828",
            prompt=prompt,
            size=size,
            response_format="url",
            watermark=watermark
        )
        
        return jsonify({
            'success': True,
            'image_url': images_response.data[0].url
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate/image-to-image', methods=['POST'])
def image_to_image():
    """图文生图API接口"""
    try:
        data = request.get_json()
        prompt = data.get('prompt')
        image_url = data.get('image_url')
        size = data.get('size', '2K')
        watermark = data.get('watermark', True)
        
        if not prompt or not image_url:
            return jsonify({'error': '缺少prompt或image_url参数'}), 400
        
        images_response = client.images.generate(
            model="doubao-seedream-4-0-250828",
            prompt=prompt,
            image=image_url,
            size=size,
            response_format="url",
            watermark=watermark
        )
        
        return jsonify({
            'success': True,
            'image_url': images_response.data[0].url
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
```

## 错误处理和最佳实践

### 1. 错误处理

```python
def safe_generate_image(prompt, **kwargs):
    """安全的图片生成函数，包含完整错误处理"""
    try:
        images_response = client.images.generate(
            model="doubao-seedream-4-0-250828",
            prompt=prompt,
            **kwargs
        )
        return {
            'success': True,
            'image_url': images_response.data[0].url
        }
    except Exception as e:
        error_msg = str(e)
        if "API key" in error_msg:
            return {'success': False, 'error': 'API密钥配置错误'}
        elif "quota" in error_msg.lower():
            return {'success': False, 'error': 'API配额不足'}
        elif "rate limit" in error_msg.lower():
            return {'success': False, 'error': '请求频率过高，请稍后重试'}
        else:
            return {'success': False, 'error': f'生成失败: {error_msg}'}
```

### 2. 最佳实践

1. **API Key 安全**
   - 使用环境变量存储 API Key
   - 不要在代码中硬编码敏感信息
   - 定期轮换 API Key

2. **请求优化**
   - 实现请求重试机制
   - 添加请求超时设置
   - 合理控制并发请求数量

3. **提示词优化**
   - 提供详细、具体的描述
   - 使用专业的艺术术语
   - 避免敏感或不当内容

4. **缓存策略**
   - 对相同请求实现缓存
   - 合理设置缓存过期时间
   - 考虑使用Redis等缓存方案

## 部署建议

### 1. 依赖管理

创建 `requirements.txt` 文件：

```txt
volcengine-python-sdk[ark]>=1.0.0
flask>=2.0.0
python-dotenv>=0.19.0
redis>=4.0.0
gunicorn>=20.0.0
```

### 2. 环境配置

创建 `.env` 文件：

```env
ARK_API_KEY=your_api_key_here
FLASK_ENV=production
REDIS_URL=redis://localhost:6379
```

### 3. Docker 部署

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
```

## 注意事项

1. **API 限制**
   - 注意API调用频率限制
   - 监控API配额使用情况
   - 实现合理的重试策略

2. **图片处理**
   - 生成的图片URL有时效性
   - 建议及时下载并存储图片
   - 考虑图片压缩和CDN加速

3. **内容安全**
   - 对用户输入进行内容过滤
   - 遵守相关法律法规
   - 建立内容审核机制

4. **性能优化**
   - 使用异步处理长时间任务
   - 实现任务队列机制
   - 添加负载均衡

## 联系支持

如果在开发过程中遇到问题，可以：

1. 查看火山引擎官方文档
2. 联系技术支持团队
3. 参考社区讨论和示例代码

---

**开发团队**: Python工程师团队  
**文档版本**: v1.0  
**最后更新**: 2024年