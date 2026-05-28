"""
API服务器 - 智能音乐推荐与分享系统
提供本地Web服务器功能
"""
import threading
import time
import socket
import json
from pathlib import Path
from functools import wraps
from flask import Flask, request, jsonify

from .user_auth import user_auth

app = Flask(__name__)
# 暂时注释掉CORS，因为缺少flask_cors模块
# from flask_cors import CORS
# CORS(app)  # 允许跨域请求

server_thread = None
server_running = False
current_port = None

# 认证装饰器
def require_auth(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({"error": "缺少认证令牌"}), 401
        
        # 移除Bearer前缀
        if token.startswith('Bearer '):
            token = token[7:]
        
        user_info = user_auth.verify_token(token)
        if not user_info:
            return jsonify({"error": "无效的认证令牌"}), 401
        
        # 将用户信息添加到请求上下文
        request.user_info = user_info
        return func(*args, **kwargs)
    return wrapper

# 端口信息文件
PORT_INFO_FILE = Path(__file__).parent.parent / 'data' / 'api_server_port.json'

@app.route('/api/recommend', methods=['GET'])
@require_auth
def get_recommendations():
    """获取推荐接口"""
    limit = int(request.args.get('limit', 10))
    # 这里应该调用推荐引擎获取推荐
    # 暂时返回模拟数据
    recommendations = [
        {
            'bvid': 'BV1sy7VzrESV',
            'title': '【洛天依】下等马',
            'up主': '某某UP主',
            'play_count': 100000,
            'cover': 'https://i0.hdslb.com/bfs/archive/1234567890abcdef.jpg',
            'pub_time': int(time.time()) - 86400,
            '推荐类型': '热门推荐',
            '分数': 9.5
        }
    ]
    return jsonify({
        'success': True,
        'data': recommendations[:limit]
    })

@app.route('/api/user/behavior', methods=['POST'])
@require_auth
def update_behavior():
    """更新用户行为接口"""
    data = request.get_json()
    user_id = data.get('user_id')
    behavior_data = data.get('behavior_data')
    
    if not user_id or not behavior_data:
        return jsonify({'success': False, 'error': '用户ID和行为数据不能为空'})
    
    # 这里应该处理用户行为数据
    # 暂时只返回成功
    return jsonify({'success': True, 'message': '行为数据更新成功'})

@app.route('/api/ping', methods=['GET'])
def ping():
    """健康检查接口"""
    return jsonify({
        'success': True,
        'message': 'Server is running',
        'timestamp': int(time.time())
    })

@app.route('/api/user/login', methods=['POST'])
def login():
    """用户登录"""
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({'success': False, 'error': '缺少用户名或密码'})
    
    username = data['username']
    password = data['password']
    
    token = user_auth.login(username, password)
    if token:
        return jsonify({
            'success': True,
            'token': token,
            'message': '登录成功'
        })
    else:
        return jsonify({'success': False, 'error': '用户名或密码错误'})

@app.route('/api/user/register', methods=['POST'])
def register():
    """用户注册"""
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({'success': False, 'error': '缺少用户名或密码'})
    
    username = data['username']
    password = data['password']
    role = data.get('role', 'user')
    
    success = user_auth.register(username, password, role)
    if success:
        return jsonify({'success': True, 'message': '注册成功'})
    else:
        return jsonify({'success': False, 'error': '用户名已存在'})

@app.route('/api/user/info', methods=['GET'])
@require_auth
def get_user_info():
    """获取用户信息"""
    user_info = request.user_info
    return jsonify({
        'success': True,
        'data': user_info
    })

def find_available_port(start_port=5001, max_attempts=100):
    """查找可用端口"""
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', port))
                return port
        except OSError:
            continue
    return None

def save_port_info(port):
    """保存端口信息"""
    PORT_INFO_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PORT_INFO_FILE, 'w', encoding='utf-8') as f:
        json.dump({
            'port': port,
            'host': '127.0.0.1',
            'timestamp': int(time.time())
        }, f, ensure_ascii=False, indent=2)

def load_port_info():
    """加载端口信息"""
    if PORT_INFO_FILE.exists():
        try:
            with open(PORT_INFO_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载端口信息失败: {e}")
    return None

def get_api_server_url():
    """获取API服务器地址"""
    port_info = load_port_info()
    if port_info:
        return f"http://{port_info['host']}:{port_info['port']}"
    # 尝试使用当前端口
    if current_port:
        return f"http://127.0.0.1:{current_port}"
    # 默认地址
    return "http://127.0.0.1:5001"

def start_server():
    """启动服务器"""
    global server_thread, server_running, current_port
    
    if server_running:
        print("API服务器已经在运行中")
        return get_api_server_url()
    
    # 尝试加载已保存的端口
    port_info = load_port_info()
    if port_info:
        port = port_info['port']
        # 检查端口是否可用
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', port))
        except OSError:
            # 端口被占用，重新查找
            port = find_available_port()
    else:
        # 查找可用端口
        port = find_available_port()
    
    if not port:
        print("无法找到可用端口")
        return None
    
    current_port = port
    server_running = True
    
    # 保存端口信息
    save_port_info(port)
    
    server_thread = threading.Thread(
        target=app.run, 
        kwargs={'host': '127.0.0.1', 'port': port, 'debug': False}
    )
    server_thread.daemon = True
    server_thread.start()
    time.sleep(1)  # 等待服务器启动
    
    server_url = f"http://127.0.0.1:{port}"
    print(f"API服务器启动成功: {server_url}")
    return server_url

def stop_server():
    """停止服务器"""
    global server_running
    server_running = False
    # Flask的开发服务器无法优雅停止，这里只是设置标志
    print("Web服务器已停止")

def is_server_running():
    """检查服务器是否运行"""
    return server_running

def get_current_port():
    """获取当前端口"""
    return current_port


def start_api_server():
    """启动API服务器（兼容旧接口）"""
    return start_server()

def stop_api_server():
    """停止API服务器（兼容旧接口）"""
    return stop_server()