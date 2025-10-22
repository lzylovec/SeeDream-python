import os
import io
import base64
import numpy as np
from PIL import Image
from flask import Flask, request, jsonify, render_template
from volcenginesdkarkruntime import Ark
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

app = Flask(__name__)

# 初始化 ARK 客户端（用于生成，但本功能主要用于评估，不调用生成接口）
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


# ===== 批量图片质量评估与优选 =====

def _conv2d(arr: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    kh, kw = kernel.shape
    ph, pw = kh // 2, kw // 2
    padded = np.pad(arr, ((ph, ph), (pw, pw)), mode='reflect')
    out = np.zeros_like(arr)
    # 简单实现，性能足够满足中小图
    for i in range(arr.shape[0]):
        region_rows = padded[i:i+kh]
        for j in range(arr.shape[1]):
            region = region_rows[:, j:j+kw]
            out[i, j] = float((region * kernel).sum())
    return out


def _compute_quality_score(img: Image.Image) -> float:
    """
    计算图片质量评分：综合锐度(边缘)、对比度、亮度合理性与分辨率。
    返回值越大表示质量越好。
    """
    # 限制计算尺寸，保证速度与稳定
    w, h = img.size
    scaled = img.copy()
    scaled.thumbnail((1024, 1024), Image.LANCZOS)
    arr = np.array(scaled.convert('L'), dtype=np.float32)

    # Sobel 边缘强度
    kx = np.array([[1, 0, -1], [2, 0, -2], [1, 0, -1]], dtype=np.float32)
    ky = np.array([[1, 2, 1], [0, 0, 0], [-1, -2, -1]], dtype=np.float32)
    gx = _conv2d(arr, kx)
    gy = _conv2d(arr, ky)
    mag = np.sqrt(gx * gx + gy * gy)
    edge_mean = float(np.mean(mag))
    sharpness_score = float(np.log1p(edge_mean))  # 0~4 左右

    # 对比度（标准差）
    contrast_score = float(np.std(arr) / 50.0)

    # 亮度偏差惩罚，接近中性灰更佳
    brightness_penalty = float(abs(np.mean(arr) - 127.5) / 127.5)

    # 分辨率评分（偏好更高分辨率）
    resolution_score = float(min(w, h) / 1024.0)

    score = sharpness_score + 0.8 * contrast_score + 0.2 * resolution_score - 0.5 * brightness_penalty
    return round(score, 6)


def _encode_image_b64(img: Image.Image, fmt: str = 'JPEG') -> str:
    buf = io.BytesIO()
    img.save(buf, format=fmt, quality=90)
    return base64.b64encode(buf.getvalue()).decode('ascii')


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


@app.route('/api/select/best-image', methods=['POST'])
def select_best_image():
    """批量上传图片，评估质量后选出最佳一张返回（base64）。
    请求：multipart/form-data，字段名为 images，可多文件。
    响应：success, best_index, scores[], best_image_b64, format
    """
    try:
        files = request.files.getlist('images')
        if not files:
            return jsonify({'success': False, 'error': '请上传至少一张图片'}), 400

        scores = []
        pil_images = []
        max_count = 20
        count = 0
        for f in files:
            if count >= max_count:
                break
            try:
                img = Image.open(f.stream).convert('RGB')
                pil_images.append(img)
                score = _compute_quality_score(img)
                scores.append(score)
                count += 1
            except Exception:
                # 跳过无法解析的文件
                continue

        if not scores:
            return jsonify({'success': False, 'error': '未能解析任何有效图片'}), 400

        best_index = int(np.argmax(np.array(scores)))
        best_img = pil_images[best_index]
        best_b64 = _encode_image_b64(best_img, fmt='JPEG')

        return jsonify({
            'success': True,
            'best_index': best_index,
            'scores': scores,
            'best_image_b64': best_b64,
            'format': 'jpeg'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)