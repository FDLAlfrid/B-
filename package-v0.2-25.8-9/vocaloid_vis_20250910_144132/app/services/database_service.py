import os
from datetime import datetime, timedelta
from ..models import Music, MusicShare, MusicFavorite, UserInterest, UserMatch, User
from .. import db
import json

class DatabaseService:
    def __init__(self):
        self.backup_dir = "backups"
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def get_music_by_time_range(self, start_time=None, end_time=None):
        """根据时间范围查询音乐数据"""
        query = Music.query
        
        if start_time:
            query = query.filter(Music.crawl_time >= start_time)
        if end_time:
            query = query.filter(Music.crawl_time <= end_time)
        
        return query.order_by(Music.crawl_time.desc()).all()
    
    def get_historical_rankings(self, target_date=None):
        """获取指定日期的音乐排行榜"""
        if not target_date:
            target_date = datetime.now()
        
        # 计算时间范围（当天0点到23:59:59）
        start_time = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # 获取当天的音乐数据并按播放量排序
        music_list = self.get_music_by_time_range(start_time, end_time)
        ranked_music = sorted(music_list, key=lambda x: x.view_count, reverse=True)
        
        return ranked_music
    
    def cleanup_old_data(self, days_to_keep=30, backup=True):
        """清理指定天数前的数据"""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        if backup:
            self._backup_data(cutoff_date)
        
        # 清理旧音乐数据
        old_music = Music.query.filter(Music.crawl_time < cutoff_date).all()
        music_count = len(old_music)
        
        for music in old_music:
            # 删除相关的分享和收藏记录
            MusicShare.query.filter_by(music_id=music.id).delete()
            MusicFavorite.query.filter_by(music_id=music.id).delete()
            db.session.delete(music)
        
        # 清理旧的用户匹配数据
        old_matches = UserMatch.query.filter(UserMatch.match_time < cutoff_date).all()
        match_count = len(old_matches)
        
        for match in old_matches:
            db.session.delete(match)
        
        db.session.commit()
        
        return {
            'music_deleted': music_count,
            'matches_deleted': match_count,
            'cutoff_date': cutoff_date
        }
    
    def _backup_data(self, cutoff_date):
        """备份要删除的数据"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = os.path.join(self.backup_dir, f'backup_{timestamp}.json')
        
        # 获取要删除的音乐数据
        old_music = Music.query.filter(Music.crawl_time < cutoff_date).all()
        
        backup_data = {
            'backup_time': datetime.now().isoformat(),
            'cutoff_date': cutoff_date.isoformat(),
            'music_data': [
                {
                    'bvid': music.bvid,
                    'title': music.title,
                    'author': music.author,
                    'cover_url': music.cover_url,
                    'duration': music.duration,
                    'view_count': music.view_count,
                    'crawl_time': music.crawl_time.isoformat(),
                    'pubdate': music.pubdate
                } for music in old_music
            ],
            'music_count': len(old_music)
        }
        
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        
        return backup_file
    
    def get_database_stats(self):
        """获取数据库统计信息"""
        stats = {
            'total_music': Music.query.count(),
            'total_shares': MusicShare.query.count(),
            'total_favorites': MusicFavorite.query.count(),
            'total_users': User.query.count(),
            'oldest_music': Music.query.order_by(Music.crawl_time.asc()).first(),
            'newest_music': Music.query.order_by(Music.crawl_time.desc()).first(),
            'most_viewed_music': Music.query.order_by(Music.view_count.desc()).first()
        }
        
        return stats
    
    def export_historical_data(self, start_date, end_date, format='json'):
        """导出指定时间范围的历史数据"""
        music_data = self.get_music_by_time_range(start_date, end_date)
        
        if format == 'json':
            export_data = [
                {
                    'bvid': music.bvid,
                    'title': music.title,
                    'author': music.author,
                    'view_count': music.view_count,
                    'crawl_time': music.crawl_time.isoformat(),
                    'ranking': idx + 1
                }
                for idx, music in enumerate(sorted(music_data, key=lambda x: x.view_count, reverse=True))
            ]
            return json.dumps(export_data, ensure_ascii=False, indent=2)
        
        elif format == 'csv':
            csv_lines = ['BV号,标题,作者,播放量,收录时间,排名']
            for idx, music in enumerate(sorted(music_data, key=lambda x: x.view_count, reverse=True)):
                csv_lines.append(
                    f'{music.bvid},"{music.title}","{music.author}",'
                    f'{music.view_count},{music.crawl_time.isoformat()},{idx + 1}'
                )
            return '\n'.join(csv_lines)
        
        return None