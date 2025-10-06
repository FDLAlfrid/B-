from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from ..services.database_service import DatabaseService
from ..services.bilibili_service import BilibiliService
from .. import db
import time

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.before_request
@login_required
def check_admin():
    """检查是否为管理员"""
    # 这里可以添加管理员权限检查
    # 暂时允许所有登录用户访问管理功能
    pass

@admin_bp.route('/database')
def database_management():
    """数据库管理页面"""
    db_service = DatabaseService()
    stats = db_service.get_database_stats()
    
    # 获取最近7天的日期选项
    date_options = []
    for i in range(7):
        date = datetime.now() - timedelta(days=i)
        date_options.append({
            'value': date.strftime('%Y-%m-%d'),
            'label': date.strftime('%Y年%m月%d日')
        })
    
    return render_template('admin/database.html', 
                         stats=stats,
                         date_options=date_options)

@admin_bp.route('/api/historical-rankings', methods=['POST'])
def api_historical_rankings():
    """获取历史排行榜数据API"""
    try:
        target_date_str = request.json.get('date')
        if target_date_str:
            target_date = datetime.strptime(target_date_str, '%Y-%m-%d')
        else:
            target_date = datetime.now()
        
        db_service = DatabaseService()
        rankings = db_service.get_historical_rankings(target_date)
        
        result = [{
            'ranking': idx + 1,
            'bvid': music.bvid,
            'title': music.title,
            'author': music.author,
            'view_count': music.view_count,
            'duration': music.duration,
            'crawl_time': music.crawl_time.strftime('%Y-%m-%d %H:%M') if music.crawl_time else '未知'
        } for idx, music in enumerate(rankings)]
        
        return jsonify({
            'success': True,
            'date': target_date.strftime('%Y年%m月%d日'),
            'data': result,
            'count': len(result)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@admin_bp.route('/api/cleanup-data', methods=['POST'])
def api_cleanup_data():
    """清理数据API"""
    try:
        days_to_keep = request.json.get('days', 30)
        backup = request.json.get('backup', True)
        
        db_service = DatabaseService()
        result = db_service.cleanup_old_data(days_to_keep, backup)
        
        return jsonify({
            'success': True,
            'message': f'成功清理 {result["music_deleted"]} 条音乐数据和 {result["matches_deleted"]} 条匹配记录',
            'data': {
                'music_deleted': result['music_deleted'],
                'matches_deleted': result['matches_deleted'],
                'cutoff_date': result['cutoff_date'].strftime('%Y-%m-%d %H:%M:%S')
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@admin_bp.route('/api/export-data', methods=['POST'])
def api_export_data():
    """导出数据API"""
    try:
        start_date_str = request.json.get('start_date')
        end_date_str = request.json.get('end_date')
        export_format = request.json.get('format', 'json')
        
        if not start_date_str or not end_date_str:
            return jsonify({
                'success': False,
                'error': '请提供开始日期和结束日期'
            }), 400
        
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        
        db_service = DatabaseService()
        export_data = db_service.export_historical_data(start_date, end_date, export_format)
        
        if export_data:
            return jsonify({
                'success': True,
                'format': export_format,
                'data': export_data,
                'filename': f'export_{start_date_str}_{end_date_str}.{export_format}'
            })
        else:
            return jsonify({
                'success': False,
                'error': '没有找到指定时间范围的数据'
            }), 404
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@admin_bp.route('/api/database-stats')
def api_database_stats():
    """获取数据库统计信息API"""
    db_service = DatabaseService()
    stats = db_service.get_database_stats()
    
    result = {
        'total_music': stats['total_music'],
        'total_shares': stats['total_shares'],
        'total_favorites': stats['total_favorites'],
        'total_users': stats['total_users'],
        'oldest_music_time': stats['oldest_music'].crawl_time.strftime('%Y-%m-%d') if stats['oldest_music'] else None,
        'newest_music_time': stats['newest_music'].crawl_time.strftime('%Y-%m-%d') if stats['newest_music'] else None,
        'most_viewed_music': {
            'title': stats['most_viewed_music'].title,
            'view_count': stats['most_viewed_music'].view_count
        } if stats['most_viewed_music'] else None
    }
    
    return jsonify(result)

@admin_bp.route('/api/fetch-data', methods=['POST'])
def api_fetch_data():
    """从B站抓取数据API"""
    try:
        rids = request.json.get('rids', [30, 29, 190])  # 默认抓取所有分区
        limit = request.json.get('limit', 50)  # 每个分区抓取数量
        force_update = request.json.get('force_update', False)  # 是否强制更新
        
        print(f"开始从B站抓取数据...")
        print(f"抓取分区: {rids}, 每个分区抓取数量: {limit}, 强制更新: {force_update}")
        
        bilibili_service = BilibiliService()
        total_fetched = 0
        total_saved = 0
        
        for rid in rids:
            try:
                print(f"抓取分区 {rid} 的数据...")
                music_data = bilibili_service.fetch_vocaloid_music(rid, limit)
                fetched_count = len(music_data)
                total_fetched += fetched_count
                print(f"分区 {rid} 抓取到 {fetched_count} 条数据")
                
                if music_data:
                    # 保存数据到数据库
                    # 如果不是强制更新，检查是否已存在
                    if not force_update:
                        new_data = []
                        for item in music_data:
                            from ..models import Music
                            if not Music.query.filter_by(bvid=item['bvid']).first():
                                new_data.append(item)
                        music_data = new_data
                        
                    if music_data:
                        bilibili_service.save_music_to_db(music_data)
                        saved_count = len(music_data)
                        total_saved += saved_count
                        print(f"分区 {rid} 成功保存 {saved_count} 条数据")
                    else:
                        print(f"分区 {rid} 没有新数据需要保存")
                
                # 避免请求过于频繁
                time.sleep(1)
            except Exception as e:
                print(f"抓取分区 {rid} 时出错: {str(e)}")
        
        return jsonify({
            'success': True,
            'message': f'成功从B站抓取数据',
            'data': {
                'total_fetched': total_fetched,
                'total_saved': total_saved,
                'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        })
        
    except Exception as e:
        print(f"抓取数据时出错: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

# 在文件末尾添加自动抓取的相关代码
# 这里使用简单的定时任务实现，实际部署时可以使用更专业的调度器
from threading import Thread
import atexit

# 自动抓取开关
AUTO_FETCH_ENABLED = True
# 自动抓取间隔（秒），默认为3600秒（1小时）
AUTO_FETCH_INTERVAL = 3600

# 启动自动抓取任务
if AUTO_FETCH_ENABLED:
    def auto_fetch_task():
        """自动抓取任务"""
        import threading
        while AUTO_FETCH_ENABLED:
            try:
                print("执行自动抓取任务...")
                bilibili_service = BilibiliService()
                db_service = DatabaseService()
                
                # 抓取所有分区数据
                rids_to_crawl = [30, 29, 190]  # VOCALOID·UTAU, 华语, 其他
                total_fetched = 0
                total_saved = 0
                
                for rid in rids_to_crawl:
                    try:
                        music_data = bilibili_service.fetch_vocaloid_music(rid, 30)  # 每个分区抓取30条
                        fetched_count = len(music_data)
                        total_fetched += fetched_count
                        
                        if music_data:
                            # 只保存新数据
                            new_data = []
                            for item in music_data:
                                from ..models import Music
                                if not Music.query.filter_by(bvid=item['bvid']).first():
                                    new_data.append(item)
                            
                            if new_data:
                                bilibili_service.save_music_to_db(new_data)
                                total_saved += len(new_data)
                        
                        time.sleep(1)
                    except Exception as e:
                        print(f"自动抓取分区 {rid} 时出错: {str(e)}")
                
                print(f"自动抓取任务完成: 共抓取 {total_fetched} 条数据，保存 {total_saved} 条新数据")
            except Exception as e:
                print(f"自动抓取任务出错: {str(e)}")
            
            # 等待下一次抓取
            for _ in range(AUTO_FETCH_INTERVAL):
                if not AUTO_FETCH_ENABLED:
                    break
                time.sleep(1)
    
    # 创建并启动线程
    auto_fetch_thread = Thread(target=auto_fetch_task, daemon=True)
    auto_fetch_thread.start()
    
    # 程序退出时停止自动抓取
    @atexit.register
    def stop_auto_fetch():
        global AUTO_FETCH_ENABLED
        AUTO_FETCH_ENABLED = False
        auto_fetch_thread.join(timeout=5)  # 等待线程结束
        print("自动抓取任务已停止")