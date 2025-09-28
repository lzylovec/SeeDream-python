import os
from flask import Flask, request, jsonify, render_template
from volcenginesdkarkruntime import Ark
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

app = Flask(__name__)

# 初始化 ARK 客户端
client = Ark(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=os.environ.get("ARK_API_KEY"),
)

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

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')

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
        
        result = safe_generate_image(
            prompt=prompt,
            size=size,
            response_format="url",
            watermark=watermark
        )
        
        if result['success']:
            return jsonify({
                'success': True,
                'image_url': result['image_url']
            })
        else:
            return jsonify({'success': False, 'error': result['error']}), 400
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

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
            return jsonify({'success': False, 'error': '缺少prompt或image_url参数'}), 400
        
        result = safe_generate_image(
            prompt=prompt,
            image=image_url,
            size=size,
            response_format="url",
            watermark=watermark
        )
        
        if result['success']:
            return jsonify({
                'success': True,
                'image_url': result['image_url']
            })
        else:
            return jsonify({'success': False, 'error': result['error']}), 400
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)