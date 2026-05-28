"""
智能音乐推荐系统 - Web版入口
提供网页版界面和API服务
"""
import threading
import time
import socket
import json
import os
import hashlib
import base64
from pathlib import Path
from functools import wraps
from flask import Flask, request, jsonify, render_template, send_from_directory, session, send_file
from urllib.parse import quote, unquote

# 添加项目根目录到 Python 路径
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.user_auth import user_auth
from services.recommend_engine.hybrid import HybridRecommendEngine

app = Flask(__name__, template_folder='web/templates', static_folder='web/static')
app.secret_key = 'music_recommend_secret_key_2026'  # 添加 session 密钥

# 全局变量
server_thread = None
server_running = False
current_port = None
active_connections = 0  # 活跃连接数
last_request_time = time.time()  # 最后请求时间
auto_shutdown_delay = 300  # 自动关闭延迟（秒）- 无请求5分钟后自动关闭
recommend_engine = None

# 封面缓存目录
COVER_CACHE_DIR = Path(__file__).parent / 'data' / 'cover_cache'

# 认证装饰器
def require_auth(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        # 检查 session 中的用户信息
        if 'user_id' in session:
            return func(*args, **kwargs)

        # 尝试从请求头获取 token
        token = request.headers.get('Authorization')
        if token:
            if token.startswith('Bearer '):
                token = token[7:]
            user_info = user_auth.verify_token(token)
            if user_info:
                request.user_info = user_info
                return func(*args, **kwargs)

        # 检查登录状态
        if request.cookies.get('user_token'):
            user_info = user_auth.verify_token(request.cookies.get('user_token'))
            if user_info:
                request.user_info = user_info
                return func(*args, **kwargs)

        # 如果是 API 请求，返回未授权
        if request.path.startswith('/api/'):
            return jsonify({"error": "未授权访问"}), 401

        # 如果是网页请求，重定向到登录页
        return render_template('login.html', error='请先登录')
    return wrapper

# 端口信息文件
PORT_INFO_FILE = Path(__file__).parent / 'data' / 'web_server_port.json'

# 请求跟踪中间件
@app.before_request
def track_request():
    """跟踪请求，更新活跃连接数和最后请求时间"""
    global active_connections, last_request_time
    active_connections += 1
    last_request_time = time.time()

# 禁用浏览器缓存中间件
@app.after_request
def add_no_cache_headers(response):
    """添加缓存控制头，确保浏览器每次都获取最新内容"""
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = 'Thu, 01 Jan 1970 00:00:00 GMT'
    return response

@app.after_request
def update_connection_count(response):
    """请求结束后更新连接数"""
    global active_connections
    active_connections -= 1
    return response

def auto_shutdown_check():
    """后台检查线程：无请求一段时间后自动关闭服务器"""
    global server_running, last_request_time, auto_shutdown_delay
    
    while server_running:
        time.sleep(5)  # 每5秒检查一次
        
        if server_running:
            current_time = time.time()
            time_since_last_request = current_time - last_request_time
            
            # 如果超过自动关闭延迟且没有活跃连接，关闭服务器
            if time_since_last_request > auto_shutdown_delay and active_connections <= 0:
                print(f"无请求超过 {auto_shutdown_delay} 秒，自动关闭服务器...")
                stop_web_server()
                break

@app.route('/')
def index():
    """首页"""
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username and password:
            token = user_auth.login(username, password)
            if token:
                response = jsonify({'success': True, 'message': '登录成功'})
                response.set_cookie('user_token', token, max_age=3600*24*7)
                return response
            else:
                return jsonify({'success': False, 'error': '用户名或密码错误'})
        return jsonify({'success': False, 'error': '请输入用户名和密码'})

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """注册页面"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username and password:
            success = user_auth.register(username, password)
            if success:
                return jsonify({'success': True, 'message': '注册成功'})
            else:
                return jsonify({'success': False, 'error': '用户名已存在'})
        return jsonify({'success': False, 'error': '请输入用户名和密码'})

    return render_template('register.html')

@app.route('/recommend')
def recommend_page():
    """推荐页面（支持游客模式）"""
    return render_template('recommend.html')

@app.route('/api/cover/<path:cover_url>')
def serve_cover(cover_url):
    """
    封面图片服务 - 优先使用本地缓存
    与桌面版保持一致的封面获取逻辑
    """
    try:
        original_url = unquote(cover_url)
    except Exception:
        original_url = cover_url

    url_hash = hashlib.md5(original_url.encode()).hexdigest()
    cache_path = COVER_CACHE_DIR / f"{url_hash}.jpg"

    if cache_path.exists():
        return send_file(str(cache_path), mimetype='image/jpeg')

    if original_url.startswith('//'):
        full_url = 'https:' + original_url
    elif not original_url.startswith('http'):
        full_url = 'https://' + original_url
    else:
        full_url = original_url

    try:
        import requests
        response = requests.get(full_url, timeout=10, stream=True)
        if response.status_code == 200:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return send_file(str(cache_path), mimetype='image/jpeg')
    except Exception as e:
        print(f"下载封面失败: {e}")

    default_cover_path = Path(__file__).parent / 'web' / 'static' / 'images' / 'default_cover.png'
    if default_cover_path.exists():
        return send_file(str(default_cover_path), mimetype='image/png')
    else:
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180" viewBox="0 0 320 180"><rect fill="#66CCFF" width="320" height="180"/><text x="160" y="95" text-anchor="middle" fill="white" font-size="14">🎵</text></svg>'
        return app.response_class(svg, mimetype='image/svg+xml')


@app.route('/api/cover_b64/<b64_url>')
def serve_cover_b64(b64_url):
    """
    封面图片服务 - 使用Base64编码的URL避免解析问题
    与桌面版保持一致的封面获取逻辑
    """
    try:
        original_url = base64.b64decode(b64_url.encode()).decode('utf-8')
    except Exception as e:
        print(f"Base64解码失败: {e}")
        return '', 404

    url_hash = hashlib.md5(original_url.encode()).hexdigest()
    cache_path = COVER_CACHE_DIR / f"{url_hash}.jpg"

    if cache_path.exists():
        return send_file(str(cache_path), mimetype='image/jpeg')

    if original_url.startswith('//'):
        full_url = 'https:' + original_url
    elif not original_url.startswith('http'):
        full_url = 'https://' + original_url
    else:
        full_url = original_url

    try:
        import requests
        response = requests.get(full_url, timeout=10, stream=True)
        if response.status_code == 200:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return send_file(str(cache_path), mimetype='image/jpeg')
    except Exception as e:
        print(f"下载封面失败: {e}")

    default_cover_path = Path(__file__).parent / 'web' / 'static' / 'images' / 'default_cover.png'
    if default_cover_path.exists():
        return send_file(str(default_cover_path), mimetype='image/png')
    else:
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180" viewBox="0 0 320 180"><rect fill="#66CCFF" width="320" height="180"/><text x="160" y="95" text-anchor="middle" fill="white" font-size="14">🎵</text></svg>'
        return app.response_class(svg, mimetype='image/svg+xml')

@app.route('/api/user/status', methods=['GET'])
def api_user_status():
    """获取用户登录状态"""
    username = None
    
    # 检查 session
    if 'user_id' in session:
        username = session['user_id']
    
    # 检查请求头中的 token
    token = request.headers.get('Authorization')
    if token and token.startswith('Bearer '):
        token = token[7:]
        user_info = user_auth.verify_token(token)
        if user_info:
            username = user_info.get('username')
    
    # 检查 cookie 中的 token
    if not username and request.cookies.get('user_token'):
        user_info = user_auth.verify_token(request.cookies.get('user_token'))
        if user_info:
            username = user_info.get('username')
    
    return jsonify({
        'success': True,
        'logged_in': username is not None,
        'username': username
    })

@app.route('/api/recommend', methods=['GET'])
def api_recommend():
    """获取推荐接口（支持游客模式和登录用户）"""
    limit = int(request.args.get('limit', 20))
    force_refresh = request.args.get('refresh', 'false').lower() == 'true'
    refresh_db = request.args.get('refresh_db', 'false').lower() == 'true'  # 刷新数据库缓存

    # 获取用户信息（支持多种认证方式）
    user_info = None
    username = None
    
    # 1. 检查 session 中的用户信息
    if 'user_id' in session:
        username = session['user_id']
    
    # 2. 尝试从请求头获取 token
    token = request.headers.get('Authorization')
    if token and token.startswith('Bearer '):
        token = token[7:]
        user_info = user_auth.verify_token(token)
        if user_info:
            username = user_info.get('username')
    
    # 3. 检查登录状态（cookie）
    if not username and request.cookies.get('user_token'):
        user_info = user_auth.verify_token(request.cookies.get('user_token'))
        if user_info:
            username = user_info.get('username')

    # 获取排除列表（优先使用用户特定的排除列表）
    excluded_bvids = []
    try:
        if username:
            # 尝试获取用户特定的排除列表
            user_excluded_file = Path(__file__).parent / 'data' / 'users' / username / 'excluded.json'
            if user_excluded_file.exists():
                with open(user_excluded_file, 'r', encoding='utf-8') as f:
                    excluded_data = json.load(f)
                    if isinstance(excluded_data, dict):
                        excluded_bvids = excluded_data.get('bvids', [])
                    elif isinstance(excluded_data, list):
                        # 支持多种格式：字符串列表或 dict 列表
                        if excluded_data and isinstance(excluded_data[0], dict):
                            excluded_bvids = [item.get('bvid') for item in excluded_data if item.get('bvid')]
                        else:
                            excluded_bvids = excluded_data
                print(f"加载用户 {username} 的排除列表: {len(excluded_bvids)} 条")
        
        # 如果没有用户特定的排除列表或用户未登录，使用全局排除列表
        if not excluded_bvids:
            excluded_file = Path(__file__).parent / 'data' / 'excluded.json'
            if excluded_file.exists():
                with open(excluded_file, 'r', encoding='utf-8') as f:
                    excluded_data = json.load(f)
                    if isinstance(excluded_data, dict):
                        excluded_bvids = excluded_data.get('bvids', [])
                    elif isinstance(excluded_data, list):
                        # 支持多种格式：字符串列表或 dict 列表
                        if excluded_data and isinstance(excluded_data[0], dict):
                            excluded_bvids = [item.get('bvid') for item in excluded_data if item.get('bvid')]
                        else:
                            excluded_bvids = excluded_data
    except Exception as e:
        print(f"加载排除列表失败: {e}")

    # 使用推荐服务获取推荐（与桌面端一致，优先使用本地未浏览视频）
    from services.recommend_engine.traditional import RecommendService

    try:
        # 每次请求创建新实例
        recommend_service = RecommendService()
        
        # 如果需要刷新数据库缓存，先使其失效
        if refresh_db:
            recommend_service.engine.invalidate_db_cache()
        
        recommendations = recommend_service.get_recommendations(
            limit=limit,
            excluded_bvids=excluded_bvids,
            force_refresh=force_refresh
        )

        # 格式化数据
        formatted_recommendations = []
        for rec in recommendations:
            cover = rec.get('cover', '') or rec.get('cover_url', '')
            # 优先使用 up_name，如果没有则尝试 up主，最后使用默认值
            up_name = rec.get('up_name') or rec.get('up主') or '未知UP主'
            formatted_recommendations.append({
                'bvid': rec.get('bvid', ''),
                'title': rec.get('title', ''),
                'up_name': up_name,
                'play_count': rec.get('play_count', 0),
                'cover': _process_cover_url(cover),
                'pub_time': rec.get('pub_time', 0),
                'video_type': rec.get('video_type', '猜你喜欢'),  # 修改为更合理的"猜你喜欢"
                'score': rec.get('score', 0)
            })

        print(f"返回 {len(formatted_recommendations)} 条推荐数据（用户: {username or '游客'}, 强制刷新: {force_refresh}, 刷新数据库: {refresh_db}）")
        return jsonify({
            'success': True,
            'data': formatted_recommendations[:limit],
            'user_logged_in': username is not None,
            'username': username
        })
    except Exception as e:
        print(f"获取推荐失败: {e}")
        # 返回模拟数据作为后备
        return jsonify({
            'success': True,
            'data': get_fallback_recommendations(limit),
            'user_logged_in': False,
            'username': None
        })

def _process_cover_url(cover):
    """
    处理封面URL - 优先使用本地缓存，如果缓存不存在则直接返回原始URL让浏览器加载
    与桌面版CoverCache逻辑一致（使用原始URL计算MD5）
    """
    if not cover:
        return ''

    original_url = cover

    url_hash = hashlib.md5(original_url.encode()).hexdigest()
    cache_path = COVER_CACHE_DIR / f"{url_hash}.jpg"

    if cache_path.exists():
        b64_url = base64.b64encode(original_url.encode()).decode('utf-8')
        return f"/api/cover_b64/{b64_url}"

    # 缓存不存在时，直接返回原始URL让浏览器加载，避免通过服务器代理下载造成延迟
    if cover.startswith('//'):
        return 'https:' + cover
    if cover.startswith('http://') or cover.startswith('https://'):
        return cover
    return ''

def get_hot_recommendations(limit=20):
    """获取热门推荐（备用）"""
    from services.recommend_engine.traditional import TraditionalRecommendEngine
    engine = TraditionalRecommendEngine()
    try:
        recommendations = engine.get_hot_recommendations(limit=limit)
        formatted = []
        for rec in recommendations:
            formatted.append({
                'bvid': rec.get('bvid', ''),
                'title': rec.get('title', ''),
                'up_name': rec.get('up_name', '') or rec.get('up主', ''),
                'play_count': rec.get('play_count', 0),
                'cover': _process_cover_url(rec.get('cover', '') or rec.get('cover_url', '')),
                'pub_time': rec.get('pub_time', 0),
                'video_type': '热门推荐',
                'score': rec.get('score', 0)
            })
        return formatted
    except Exception as e:
        print(f"获取热门推荐失败: {e}")
        return get_fallback_recommendations(limit)

def get_fallback_recommendations(limit=20):
    """获取后备推荐数据（模拟数据）"""
    fallback_data = [
        {'bvid': 'BV1sy7VzrESV', 'title': '【洛天依】下等马', 'up_name': '阿良良木健', 'play_count': 100000, 'cover': 'https://i0.hdslb.com/bfs/archive/1234567890abcdef.jpg', 'pub_time': 1700000000, 'video_type': '热门推荐', 'score': 9.5},
        {'bvid': 'BV1xx411c7mZ', 'title': '【初音未来】千本樱', 'up_name': '黑兔P', 'play_count': 500000, 'cover': 'https://i0.hdslb.com/bfs/archive/abcdef1234567890.jpg', 'pub_time': 1600000000, 'video_type': '热门推荐', 'score': 9.8},
        {'bvid': 'BV1sb411i7aX', 'title': '【洛天依】权御天下', 'up_name': '乌龟Sui', 'play_count': 800000, 'cover': 'https://i0.hdslb.com/bfs/archive/0987654321fedcba.jpg', 'pub_time': 1500000000, 'video_type': '经典推荐', 'score': 9.9},
        {'bvid': 'BV1Mt411o7uE', 'title': '【初音未来】初音未来的消失', 'up_name': 'cosMo@暴走P', 'play_count': 600000, 'cover': 'https://i0.hdslb.com/bfs/archive/fedcba0987654321.jpg', 'pub_time': 1400000000, 'video_type': '经典推荐', 'score': 9.7},
        {'bvid': 'BV1bt411o7iF', 'title': '【洛天依】投食歌', 'up_name': 'ilem', 'play_count': 400000, 'cover': 'https://i0.hdslb.com/bfs/archive/1122334455667788.jpg', 'pub_time': 1300000000, 'video_type': '热门推荐', 'score': 9.3},
        {'bvid': 'BV1xs411Q799', 'title': '【初音未来】World is Mine', 'up_name': 'ryo', 'play_count': 700000, 'cover': 'https://i0.hdslb.com/bfs/archive/8877665544332211.jpg', 'pub_time': 1200000000, 'video_type': '经典推荐', 'score': 9.6},
    ]
    return fallback_data[:limit]

@app.route('/api/search', methods=['GET'])
def api_search():
    """搜索接口"""
    keyword = request.args.get('keyword', '')
    page = int(request.args.get('page', 1))

    if not keyword:
        return jsonify({'success': False, 'error': '请输入搜索关键词'})

    # 使用传统推荐引擎搜索
    from services.recommend_engine.traditional import TraditionalRecommendEngine
    from utils.api import search_bilibili_videos

    try:
        # 先尝试本地搜索
        engine = TraditionalRecommendEngine()
        results = engine.search_by_keyword(keyword, limit=20)

        if results:
            formatted_results = []
            for rec in results:
                cover = rec.get('cover', '') or rec.get('cover_url', '')
                formatted_results.append({
                    'bvid': rec.get('bvid', ''),
                    'title': rec.get('title', ''),
                    'up_name': rec.get('up_name', '') or rec.get('up主', ''),
                    'play_count': rec.get('play_count', 0),
                    'cover': _process_cover_url(cover),
                    'pub_time': rec.get('pub_time', 0),
                    'video_type': rec.get('video_type', '搜索结果'),
                    'score': rec.get('score', 0)
                })

            return jsonify({
                'success': True,
                'data': formatted_results
            })

        # 如果本地没有，调用B站API
        api_results = search_bilibili_videos(keyword, page=page)
        if 'results' in api_results:
            formatted_results = []
            for video in api_results['results'][:20]:
                cover = video.get('封面', '')
                formatted_results.append({
                    'bvid': video.get('BV号', ''),
                    'title': video.get('标题', ''),
                    'up_name': video.get('UP主', ''),
                    'play_count': video.get('播放量', 0),
                    'cover': _process_cover_url(cover),
                    'pub_time': video.get('发布时间', 0),
                    'video_type': '搜索结果',
                    'score': 0
                })
            return jsonify({
                'success': True,
                'data': formatted_results
            })

        return jsonify({'success': False, 'error': '未找到相关结果'})

    except Exception as e:
        print(f"搜索失败: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/video/<bvid>')
def api_video(bvid):
    """获取视频详情"""
    from utils.api import get_bilibili_video_info

    try:
        info = get_bilibili_video_info(bvid)
        if 'error' not in info:
            # 处理嵌套的数据结构
            basic_info = info.get('基础信息', {})
            up_info = info.get('UP主信息', {})
            stats = info.get('数据统计', {})
            other = info.get('其他', {})
            
            return jsonify({
                'success': True,
                'data': {
                    'bvid': bvid,
                    'title': basic_info.get('视频标题', ''),
                    'up_name': up_info.get('UP主名称', '') or '未知UP主',
                    'play_count': stats.get('播放量', 0),
                    'cover': _process_cover_url(basic_info.get('封面', '')),
                    'pub_time': basic_info.get('发布时间', 0),
                    'description': basic_info.get('视频简介', ''),
                    'video_url': other.get('视频链接', '')
                }
            })
        else:
            return jsonify({'success': False, 'error': info.get('error', '获取失败')})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/ping', methods=['GET'])
def api_ping():
    """健康检查"""
    return jsonify({
        'success': True,
        'message': '服务正常运行',
        'version': '1.0.0'
    })

@app.route('/api/excluded', methods=['GET'])
def api_get_excluded():
    """获取排除列表"""
    username = _get_current_username()
    
    if username:
        excluded_file = Path(__file__).parent / 'data' / 'users' / username / 'excluded.json'
    else:
        excluded_file = Path(__file__).parent / 'data' / 'excluded.json'
    
    excluded_list = []
    if excluded_file.exists():
        try:
            with open(excluded_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    excluded_list = data.get('bvids', [])
                elif isinstance(data, list):
                    if data and isinstance(data[0], dict):
                        excluded_list = [{'bvid': item.get('bvid'), 'title': item.get('title')} for item in data if item.get('bvid')]
                    else:
                        excluded_list = [{'bvid': bvid, 'title': ''} for bvid in data]
        except Exception as e:
            print(f"加载排除列表失败: {e}")
    
    return jsonify({
        'success': True,
        'data': excluded_list,
        'count': len(excluded_list)
    })

@app.route('/api/excluded/<bvid>', methods=['POST'])
def api_add_excluded(bvid):
    """添加视频到排除列表"""
    username = _get_current_username()
    
    if username:
        excluded_dir = Path(__file__).parent / 'data' / 'users' / username
    else:
        excluded_dir = Path(__file__).parent / 'data'
    
    excluded_dir.mkdir(parents=True, exist_ok=True)
    excluded_file = excluded_dir / 'excluded.json'
    
    try:
        excluded_list = []
        if excluded_file.exists():
            with open(excluded_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    excluded_list = data.get('bvids', [])
                elif isinstance(data, list):
                    excluded_list = data
        
        bvid_str = str(bvid)
        title = request.json.get('title', '') if request.json else ''
        
        if isinstance(excluded_list, list):
            if excluded_list and isinstance(excluded_list[0], dict):
                if not any(item.get('bvid') == bvid_str for item in excluded_list):
                    excluded_list.append({'bvid': bvid_str, 'title': title})
            else:
                if bvid_str not in excluded_list:
                    excluded_list.append(bvid_str)
                    excluded_list = [{'bvid': bvid, 'title': title} for bvid in excluded_list]
        
        with open(excluded_file, 'w', encoding='utf-8') as f:
            json.dump({'bvids': excluded_list, 'updated': time.strftime('%Y-%m-%d %H:%M:%S')}, f, ensure_ascii=False, indent=2)
        
        return jsonify({'success': True, 'message': '已添加到排除列表'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/excluded/<bvid>', methods=['DELETE'])
def api_remove_excluded(bvid):
    """从排除列表移除"""
    username = _get_current_username()
    
    if username:
        excluded_file = Path(__file__).parent / 'data' / 'users' / username / 'excluded.json'
    else:
        excluded_file = Path(__file__).parent / 'data' / 'excluded.json'
    
    if not excluded_file.exists():
        return jsonify({'success': False, 'error': '排除列表不存在'})
    
    try:
        with open(excluded_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        excluded_list = data.get('bvids', []) if isinstance(data, dict) else data
        
        bvid_str = str(bvid)
        if isinstance(excluded_list, list) and excluded_list:
            if isinstance(excluded_list[0], dict):
                excluded_list = [item for item in excluded_list if item.get('bvid') != bvid_str]
            else:
                excluded_list = [item for item in excluded_list if item != bvid_str]
        
        with open(excluded_file, 'w', encoding='utf-8') as f:
            json.dump({'bvids': excluded_list, 'updated': time.strftime('%Y-%m-%d %H:%M:%S')}, f, ensure_ascii=False, indent=2)
        
        return jsonify({'success': True, 'message': '已从排除列表移除'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def _get_current_username():
    """获取当前登录用户名"""
    username = None
    
    if 'user_id' in session:
        username = session['user_id']
    
    token = request.headers.get('Authorization')
    if token and token.startswith('Bearer '):
        token = token[7:]
        user_info = user_auth.verify_token(token)
        if user_info:
            username = user_info.get('username')
    
    if not username and request.cookies.get('user_token'):
        user_info = user_auth.verify_token(request.cookies.get('user_token'))
        if user_info:
            username = user_info.get('username')
    
    return username

@app.route('/api/shutdown', methods=['POST'])
def shutdown_server():
    """关闭服务器"""
    global server_running
    func = request.environ.get('werkzeug.server.shutdown')
    if func:
        func()
        server_running = False
        return jsonify({'success': True, 'message': '服务器已关闭'})
    else:
        return jsonify({'success': False, 'error': '无法关闭服务器'}), 500

@app.route('/api/stats')
def api_stats():
    """获取统计信息"""
    from services.recommend_engine.traditional import RecommendService
    service = RecommendService()
    stats = service.get_db_stats()

    return jsonify({
        'success': True,
        'data': {
            'total_videos': stats.get('total', 0),
            'viewed_videos': stats.get('viewed', 0),
            'unviewed_videos': stats.get('unviewed', 0)
        }
    })

@app.route('/static/images/<path:filename>')
def serve_images(filename):
    """静态图片服务"""
    return send_from_directory(str(Path(__file__).parent / 'web' / 'static' / 'images'), filename)

def get_local_ip():
    """获取本机IP地址"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def start_web_server(port=5000, use_existing_port=False, open_browser=True):
    """启动Web服务器"""
    global server_thread, server_running, current_port

    if server_running and server_thread and server_thread.is_alive():
        print("Web服务器已在运行中")
        return True

    server_running = True
    current_port = port

    def run_server():
        # 保存端口信息
        port_info = {
            'port': port,
            'local_ip': get_local_ip(),
            'started_at': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        try:
            with open(PORT_INFO_FILE, 'w', encoding='utf-8') as f:
                json.dump(port_info, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存端口信息失败: {e}")

        print(f"Web服务器启动成功: http://localhost:{port}")
        print(f"访问首页: http://localhost:{port}")
        print(f"访问推荐页面: http://localhost:{port}/recommend")
        print(f"API文档: http://localhost:{port}/api/ping")
        print(f"关闭服务器: POST http://localhost:{port}/api/shutdown")

        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # 启动自动关闭检查线程
    shutdown_check_thread = threading.Thread(target=auto_shutdown_check, daemon=True)
    shutdown_check_thread.start()

    time.sleep(1)
    
    # 自动打开浏览器
    if open_browser:
        import webbrowser
        try:
            webbrowser.open(f'http://localhost:{port}/recommend')
            print(f"已在浏览器中打开: http://localhost:{port}/recommend")
        except Exception as e:
            print(f"自动打开浏览器失败: {e}")
    
    return True

def stop_web_server():
    """停止Web服务器"""
    global server_running

    if not server_running:
        print("Web服务器未运行")
        return False

    try:
        import requests
        response = requests.post(f'http://localhost:{current_port}/api/shutdown', timeout=5)
        if response.status_code == 200:
            print("关闭请求已发送")
            server_running = False
            return True
    except Exception as e:
        print(f"关闭服务器失败: {e}")

    server_running = False
    return True

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='智能音乐推荐系统 - Web版')
    parser.add_argument('--port', type=int, default=5000, help='服务器端口')
    parser.add_argument('--stop', action='store_true', help='停止服务器')
    args = parser.parse_args()

    if args.stop:
        stop_web_server()
    else:
        start_web_server(port=args.port)
        try:
            while server_running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n正在关闭服务器...")
            stop_web_server()
