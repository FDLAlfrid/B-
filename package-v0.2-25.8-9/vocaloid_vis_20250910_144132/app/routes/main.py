from flask import Blueprint, render_template, request
from flask_login import current_user
from ..services import BilibiliService, RecommendationService
from .. import db
from ..models import Music

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """首页"""
    bili_service = BilibiliService()
    recommend_service = RecommendationService(db)
    
    # 获取参数
    time_range = request.args.get('time_range', 'all')
    search_query = request.args.get('q', '')
    refresh = request.args.get('refresh', 'false') == 'true'
    random_recommend = request.args.get('random', 'false') == 'true'
    
    # 如果强制刷新或没有数据，从B站API获取
    if refresh or not Music.query.first():
        music_data = bili_service.fetch_vocaloid_music(rid=30, limit=20)
        bili_service.save_music_to_db(music_data)
    
    # 获取推荐音乐（支持时间范围、搜索和随机推荐）
    popular_music = recommend_service.get_recommended_music(
        current_user.id if current_user.is_authenticated else None,
        limit=8,
        time_range=time_range,
        search_query=search_query,
        randomize=random_recommend
    )
    
    # 获取潜在好友(仅登录用户)
    potential_friends = []
    if current_user.is_authenticated:
        potential_friends = recommend_service.find_potential_friends(current_user.id)
    
    return render_template('index.html', 
                          popular_music=popular_music,
                          potential_friends=potential_friends,
                          time_range=time_range,
                          search_query=search_query)

@main_bp.route('/about')
def about():
    """关于页面"""
    return render_template('about.html')

@main_bp.route('/contact')
def contact():
    """联系页面"""
    return render_template('contact.html')