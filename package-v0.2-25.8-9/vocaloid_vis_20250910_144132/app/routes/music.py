from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user
from ..services import BilibiliService, DatabaseService
from ..models import Music, MusicShare, User, MusicFavorite
from .. import db
import time
from datetime import datetime, timedelta

music_bp = Blueprint('music', __name__)

@music_bp.route('/')
def music_list():
    """音乐列表页"""
    from datetime import datetime, timedelta
    
    bili_service = BilibiliService()
    db_service = DatabaseService()
    
    rid = request.args.get('rid', 30, type=int)
    page = request.args.get('page', 1, type=int)
    refresh = request.args.get('refresh', 'false') == 'true'
    search_query = request.args.get('q', '')
    
    # 时间范围参数
    time_range = request.args.get('time_range', 'all')
    start_time = None
    end_time = None
    
    if time_range == 'today':
        start_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = datetime.now()
    elif time_range == 'week':
        start_time = datetime.now() - timedelta(days=7)
        end_time = datetime.now()
    elif time_range == 'month':
        start_time = datetime.now() - timedelta(days=30)
        end_time = datetime.now()
    
    # 如果强制刷新或没有数据，从B站API获取
    if refresh or not Music.query.first():
        music_data = bili_service.fetch_vocaloid_music(rid=rid, limit=20)
        bili_service.save_music_to_db(music_data)
    else:
        # 从数据库获取数据
        music_data = db_service.get_music_by_time_range(start_time, end_time)
    
    # 搜索功能
    if search_query:
        music_data = [music for music in music_data 
                     if search_query.lower() in music.title.lower() 
                     or search_query.lower() in music.author.lower()
                     or search_query.lower() in (music.tags or '').lower()]
    
    return render_template('music_list.html', 
                          music_list=music_data,
                          current_rid=rid,
                          time_range=time_range,
                          search_query=search_query)

@music_bp.route('/<bvid>')
def music_detail(bvid):
    """音乐详情页"""
    # 获取音乐详情
    music = Music.query.filter_by(bvid=bvid).first()
    if not music:
        # 如果数据库中没有，从B站API获取
        bili_service = BilibiliService()
        # 这里需要实现单个音乐详情获取
        pass
    
    return render_template('music_detail.html', music=music)

@music_bp.route('/rankings')
def music_rankings():
    """音乐排行榜页面"""
    # 获取请求参数
    time_range = request.args.get('time_range', 'week')  # 时间范围: day, week, month
    sort_by = request.args.get('sort_by', 'view_count')  # 排序方式: view_count, duration
    limit = request.args.get('limit', 20, type=int)  # 显示数量
    rid = request.args.get('rid', 30, type=int)  # 分区ID，默认为VOCALOID·UTAU分区(30)
    refresh = request.args.get('refresh', 'false').lower() == 'true'  # 是否刷新数据
    
    # 从B站抓取数据
    if refresh:
        try:
            print("开始从B站抓取数据...")
            bilibili_service = BilibiliService()
            
            # 抓取多个分区的数据以增加数据量
            all_music_data = []
            if rid == 0:  # 如果是全部分区
                rids_to_crawl = [30, 29, 190]  # VOCALOID·UTAU, 华语, 其他
                for crawl_rid in rids_to_crawl:
                    print(f"抓取分区 {crawl_rid} 的数据...")
                    music_data = bilibili_service.fetch_vocaloid_music(crawl_rid, 50)  # 每个分区抓取50条
                    all_music_data.extend(music_data)
                    time.sleep(1)  # 避免请求过于频繁
            else:
                print(f"抓取分区 {rid} 的数据...")
                all_music_data = bilibili_service.fetch_vocaloid_music(rid, 100)  # 单个分区抓取100条
            
            if all_music_data:
                print(f"成功抓取到 {len(all_music_data)} 条数据，开始保存到数据库...")
                bilibili_service.save_music_to_db(all_music_data)
                print("数据保存完成")
                flash('数据刷新成功', 'success')
            else:
                print("未抓取到新数据")
                flash('未抓取到新数据', 'info')
        except Exception as e:
            print(f"抓取数据时出错: {str(e)}")
            flash(f'数据刷新失败: {str(e)}', 'danger')
    
    # 从数据库查询数据
    db_service = DatabaseService()
    
    # 根据分区ID筛选
    query = Music.query
    if rid > 0:
        query = query.filter_by(rid=rid)
    
    # 根据时间范围筛选
    if time_range == 'day':
        time_threshold = datetime.now() - timedelta(days=1)
        query = query.filter(Music.crawl_time >= time_threshold)
    elif time_range == 'week':
        time_threshold = datetime.now() - timedelta(days=7)
        query = query.filter(Music.crawl_time >= time_threshold)
    elif time_range == 'month':
        time_threshold = datetime.now() - timedelta(days=30)
        query = query.filter(Music.crawl_time >= time_threshold)
    
    # 排序
    if sort_by == 'duration':
        query = query.order_by(Music.duration.desc())
    else:
        query = query.order_by(Music.view_count.desc())
    
    # 限制数量
    music_list = query.limit(limit).all()
    
    # 获取统计信息
    total_count = query.count()
    total_views = sum(music.view_count for music in music_list) if music_list else 0
    avg_duration = sum(music.duration for music in music_list) // len(music_list) if music_list else 0
    
    # 准备统计数据
    stats = {
        'total_music': total_count,
        'total_views': total_views,
        'avg_duration': avg_duration
    }
    
    # 准备图表数据
    chart_labels = [music.title[:10] + '...' for music in music_list[:10]]
    view_counts = [music.view_count for music in music_list[:10]]
    durations = [music.duration for music in music_list[:10]]
    
    # 转换时长格式
    duration_labels = [f"{d//60}:{d%60:02d}" for d in durations]
    
    return render_template('music_rankings.html',
                          music_list=music_list,
                          time_range=time_range,
                          sort_by=sort_by,
                          limit=limit,
                          rid=rid,
                          stats=stats,
                          total_count=total_count,
                          total_views=total_views,
                          avg_duration=avg_duration,
                          chart_labels=chart_labels,
                          view_counts=view_counts,
                          durations=durations,
                          duration_labels=duration_labels)

@music_bp.route('/share/<bvid>', methods=['GET', 'POST'])
@login_required
def share_music(bvid):
    """分享音乐"""
    if request.method == 'POST':
        music = Music.query.filter_by(bvid=bvid).first()
        if music:
            share_text = request.form.get('share_text', '')
            platform = request.form.get('platform', 'internal')
            
            new_share = MusicShare(
                user_id=current_user.id,
                music_id=music.id,
                share_text=share_text,
                platform=platform
            )
            
            db.session.add(new_share)
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': '分享成功!'
            })
    
    music = Music.query.filter_by(bvid=bvid).first()
    return render_template('share.html', music=music)