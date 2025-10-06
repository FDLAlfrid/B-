from flask import Blueprint, jsonify, request, Response
from flask_login import login_required, current_user
import requests
from ..services import RecommendationService
from .. import db

api_bp = Blueprint('api', __name__)

@api_bp.route('/proxy-image')
def proxy_image():
    """图片代理路由，用于处理跨域图片加载"""
    image_url = request.args.get('url')
    if not image_url:
        return "Missing image URL parameter", 400
    
    try:
        # 设置B站请求头以避免反爬虫
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Referer": "https://www.bilibili.com/",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "image",
            "Sec-Fetch-Mode": "no-cors",
            "Sec-Fetch-Site": "cross-site"
        }
        
        response = requests.get(image_url, headers=headers, timeout=10, allow_redirects=True)
        response.raise_for_status()
        
        # 返回图片内容和正确的Content-Type
        return Response(
            response.content,
            content_type=response.headers.get('Content-Type', 'image/jpeg')
        )
    except Exception as e:
        print(f"图片代理失败: {str(e)}")
        return "Image proxy failed", 500

@api_bp.route('/recommend/music')
@login_required
def api_recommend_music():
    """获取音乐推荐API"""
    time_range = request.args.get('time_range', 'all')
    search_query = request.args.get('q', '')
    
    recommend_service = RecommendationService(db)
    music_list = recommend_service.get_recommended_music(
        current_user.id, 
        time_range=time_range,
        search_query=search_query
    )
    
    result = [{
        'bvid': m.bvid,
        'title': m.title,
        'author': m.author,
        'cover_url': m.cover_url,
        'view_count': m.view_count,
        'duration': m.duration,
        'crawl_time': m.crawl_time.isoformat() if m.crawl_time else None
    } for m in music_list]
    
    return jsonify(result)

@api_bp.route('/recommend/users')
@login_required
def api_recommend_users():
    """获取用户匹配API"""
    recommend_service = RecommendationService(db)
    user_matches = recommend_service.find_potential_friends(current_user.id)
    
    result = [{
        'id': u.id,
        'username': u.username,
        'avatar_url': u.avatar_url,
        'bio': u.bio
    } for u in user_matches]
    
    return jsonify(result)

@api_bp.route('/auth/register', methods=['POST'])
def api_register():
    """用户注册API"""
    # 实现用户注册API逻辑
    pass

@api_bp.route('/auth/login', methods=['POST'])
def api_login():
    """用户登录API"""
    # 实现用户登录API逻辑
    pass

@api_bp.route('/users/<int:user_id>')
@login_required
def api_get_user(user_id):
    """获取用户信息API"""
    # 实现获取用户信息API逻辑
    pass

@api_bp.route('/music/<bvid>/share', methods=['POST'])
@login_required
def api_share_music(bvid):
    """分享音乐API"""
    # 实现分享音乐API逻辑
    pass