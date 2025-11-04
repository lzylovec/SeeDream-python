import os
import io
import base64
import numpy as np
from PIL import Image
from flask import Flask, request, jsonify, render_template, send_from_directory
from volcenginesdkarkruntime import Ark
from dotenv import load_dotenv
import json
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename

# 加载环境变量
load_dotenv()

app = Flask(__name__)

# 初始化 ARK 客户端（用于生成，但本功能主要用于评估，不调用生成接口）
client = Ark(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=os.environ.get("ARK_API_KEY"),
)

# 历史记录存储配置
HISTORY_DIR = os.path.join(app.root_path, 'data')
HISTORY_FILE = os.path.join(HISTORY_DIR, 'history.json')
MAX_HISTORY = 500

# 上传文件配置
UPLOAD_DIR = os.path.join(app.root_path, 'uploads')
ALLOWED_EXTS = {'jpg','jpeg','png','webp'}

def _ensure_upload_dir():
    try:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
    except Exception:
        pass

_ensure_upload_dir()

def _ensure_history_store():
    try:
        os.makedirs(HISTORY_DIR, exist_ok=True)
        if not os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False)
    except Exception:
        # 存储目录不可用时忽略，不影响主流程
        pass

_ensure_history_store()

def _load_history():
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f) or []
    except Exception:
        return []

def _save_history(items):
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(items, f, ensure_ascii=False)
    except Exception:
        pass

def _add_history_entry(entry):
    items = _load_history()
    # 追加并限制长度
    items.append(entry)
    if len(items) > MAX_HISTORY:
        items = items[-MAX_HISTORY:]
    _save_history(items)
    return entry


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
        elif "OversizeImage" in error_msg or "oversize" in error_msg.lower():
            return {'success': False, 'error': '参考图过大（超过10MB）。请更换更小图片，或使用本地上传以自动压缩'}
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

# 上传图片（返回可访问URL）
@app.route('/api/upload', methods=['POST'])
def upload_image():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': '缺少文件字段'}), 400
        f = request.files['file']
        if not f or f.filename == '':
            return jsonify({'success': False, 'error': '未选择文件'}), 400
        # 校验扩展名
        name = secure_filename(f.filename)
        ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
        if ext not in ALLOWED_EXTS:
            return jsonify({'success': False, 'error': '仅支持 JPG/PNG/WebP'}), 400
        # 保存文件
        filename = f"{uuid.uuid4().hex}.{ext}"
        path = os.path.join(UPLOAD_DIR, filename)
        f.save(path)
        # 返回可访问URL（相对路径即可）
        url = f"/uploads/{filename}"
        # 尺寸提示（不拒绝上传），避免后续生成因参考图过大失败
        try:
            size_bytes = os.path.getsize(path)
        except Exception:
            size_bytes = 0
        resp = {'success': True, 'url': url, 'filename': filename}
        if size_bytes > (10 * 1024 * 1024):
            resp['warning'] = '图片较大（>10MB），生成时将自动压缩以避免失败'
        return jsonify(resp)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# 静态服务上传文件
@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    try:
        return send_from_directory(UPLOAD_DIR, filename)
    except Exception as e:
        return jsonify({'error': f'Error serving upload: {str(e)}'}), 500

# 查询历史记录
@app.route('/api/history', methods=['GET'])
def history_list():
    try:
        limit = int(request.args.get('limit', '100'))
        items = _load_history()
        # 按时间倒序
        items.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return jsonify({'success': True, 'items': items[:max(1, min(1000, limit))]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


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
            # 写入历史记录
            _add_history_entry({
                'id': str(uuid.uuid4()),
                'mode': 'text_to_image',
                'prompt': prompt,
                'image_url': result['image_url'],
                'size': size,
                'watermark': bool(watermark),
                'created_at': datetime.utcnow().isoformat()
            })
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
        # Ark 图生图要求参数 image 为可公开访问的 URL。
        # 若用户使用了本地上传（/uploads/xxx），尝试读取本地文件并以 data URL 形式传入。
        # 注意：如果服务端不支持 data URL，将返回错误；此时需要使用公网可访问的图片 URL。
        source_image = image_url
        try:
            if image_url and not (image_url.startswith('http://') or image_url.startswith('https://')):
                # 仅处理本地上传到 /uploads 的情况
                # 兼容以 "/uploads/" 或 "uploads/" 开头
                rel = image_url[1:] if image_url.startswith('/') else image_url
                if rel.startswith('uploads/'):
                    filename = rel.split('/', 1)[1]
                    path = os.path.join(UPLOAD_DIR, filename)
                    if not os.path.exists(path):
                        return jsonify({'success': False, 'error': '本地参考图不存在，请重新上传或填写公网URL'}), 400
                    # 若文件超过 10MB，自动压缩为 JPEG 并编码为 data URL
                    try:
                        size_bytes = os.path.getsize(path)
                    except Exception:
                        size_bytes = 0
                    if size_bytes > (10 * 1024 * 1024):
                        try:
                            img = Image.open(path)
                            # 去除透明通道并限制尺寸
                            if img.mode not in ('RGB', 'L'):
                                img = img.convert('RGB')
                            max_dim = 2048
                            w, h = img.size
                            if max(w, h) > max_dim:
                                img = img.copy()
                                img.thumbnail((max_dim, max_dim), Image.LANCZOS)
                            # 逐步降低质量直到 <=10MB
                            for q in (85, 75, 65, 55, 45, 35):
                                buf = io.BytesIO()
                                img.save(buf, format='JPEG', quality=q, optimize=True)
                                data = buf.getvalue()
                                if len(data) <= (10 * 1024 * 1024) or q == 35:
                                    b64 = base64.b64encode(data).decode('ascii')
                                    source_image = f"data:image/jpeg;base64,{b64}"
                                    break
                        except Exception:
                            # 压缩失败则回退到原始编码
                            with open(path, 'rb') as f:
                                b64 = base64.b64encode(f.read()).decode('ascii')
                            source_image = f"data:image/jpeg;base64,{b64}"
                    else:
                        # 推测 MIME 类型，直接按原格式编码
                        lower = filename.lower()
                        mime = 'image/jpeg'
                        if lower.endswith('.png'):
                            mime = 'image/png'
                        elif lower.endswith('.webp'):
                            mime = 'image/webp'
                        with open(path, 'rb') as f:
                            b64 = base64.b64encode(f.read()).decode('ascii')
                        source_image = f"data:{mime};base64,{b64}"
        except Exception as _e:
            # 读取或编码失败，维持原始 URL，交由后续调用报错
            source_image = image_url

        result = safe_generate_image(
            prompt=prompt,
            image=source_image,
            size=size,
            response_format="url",
            watermark=watermark
        )

        if result['success']:
            # 写入历史记录
            _add_history_entry({
                'id': str(uuid.uuid4()),
                'mode': 'image_to_image',
                'prompt': prompt,
                'source_image_url': image_url,
                'image_url': result['image_url'],
                'size': size,
                'watermark': bool(watermark),
                'created_at': datetime.utcnow().isoformat()
            })
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


@app.route('/video/<path:filename>')
def serve_video(filename):
    """静态视频文件服务，支持中文文件名"""
    try:
        # 确保文件名正确解码
        import urllib.parse
        decoded_filename = urllib.parse.unquote(filename, encoding='utf-8')
        
        # 检查文件是否存在
        video_path = os.path.join(app.root_path, 'video', decoded_filename)
        if not os.path.exists(video_path):
            return jsonify({'error': 'Video file not found'}), 404
            
        return send_from_directory(
            os.path.join(app.root_path, 'video'), 
            decoded_filename,
            as_attachment=False,
            mimetype='video/mp4'
        )
    except Exception as e:
        return jsonify({'error': f'Error serving video: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5008)