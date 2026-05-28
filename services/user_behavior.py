"""
用户行为数据管理 - 记录用户交互行为并计算推荐权重
"""
import json
import os
from datetime import datetime
from typing import Dict, List, Any

USER_BEHAVIOR_PATH = os.path.join(os.path.expanduser('~'), '.bilibili_toolbox_user_behavior.json')

# 用户行为类型和权重配置
BEHAVIOR_WEIGHTS = {
    'copy_bvid': 5.0,        # 复制BV号 - 高权重（分享意图）
    'open_video': 3.0,       # 打开视频 - 中高权重（兴趣表现）
    'open_video_repeat': 1.5,  # 重复打开 - 中等权重（持续兴趣）
    'view_card': 0.5,         # 查看卡片 - 低权重（浏览行为）
    'save_cover': 2.0,        # 保存封面 - 中等权重（收藏意图）
    'search_keyword': 1.0,      # 搜索关键词 - 低权重（探索行为）
    'open_author_space': 2.5,   # 打开作者空间 - 中高权重（对作者的兴趣）
}

# 行为有效期（秒）
BEHAVIOR_EXPIRY = {
    'copy_bvid': 30 * 24 * 60 * 60,      # 30天
    'open_video': 7 * 24 * 60 * 60,       # 7天
    'open_video_repeat': 3 * 24 * 60 * 60, # 3天
    'view_card': 1 * 24 * 60 * 60,        # 1天
    'save_cover': 14 * 24 * 60 * 60,      # 14天
    'search_keyword': 3 * 24 * 60 * 60,    # 3天
}

# 防止重复记录的时间窗口（秒）
ANTI_SPAM_WINDOW = 60  # 1分钟内相同行为不计入权重

class UserBehaviorManager:
    """用户行为管理器"""
    
    def __init__(self):
        self.behavior_data = self._load_behavior_data()
    
    def _load_behavior_data(self) -> Dict[str, Any]:
        """加载用户行为数据"""
        try:
            if os.path.exists(USER_BEHAVIOR_PATH):
                with open(USER_BEHAVIOR_PATH, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"加载用户行为数据失败: {e}")
        
        return {
            'user_id': 'default',
            'behaviors': [],  # 行为记录列表
            'video_scores': {},  # 视频评分 {bvid: score}
            'keyword_scores': {},  # 关键词评分 {keyword: score}
            'author_scores': {},  # 作者评分 {author: score}
        }
    
    def _save_behavior_data(self):
        """保存用户行为数据"""
        try:
            with open(USER_BEHAVIOR_PATH, 'w', encoding='utf-8') as f:
                json.dump(self.behavior_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存用户行为数据失败: {e}")
    
    def record_behavior(self, behavior_type: str, bvid: str = None, 
                     keyword: str = None, author: str = None, 
                     additional_info: Dict = None):
        """
        记录用户行为
        :param behavior_type: 行为类型（copy_bvid, open_video, view_card等）
        :param bvid: 视频BV号
        :param keyword: 搜索关键词
        :param author: UP主名称
        :param additional_info: 附加信息
        """
        current_time = datetime.now().timestamp()
        
        # 检查是否在防重复窗口内
        if self._is_duplicate_behavior(behavior_type, bvid, keyword, author, current_time):
            print(f"行为重复，跳过记录: {behavior_type}")
            return
        
        # 创建行为记录
        behavior = {
            'type': behavior_type,
            'timestamp': current_time,
            'bvid': bvid,
            'keyword': keyword,
            'author': author,
            'additional_info': additional_info or {}
        }
        
        # 添加到行为列表
        self.behavior_data['behaviors'].append(behavior)
        
        # 更新评分
        self._update_scores(behavior_type, bvid, keyword, author)
        
        # 清理过期数据
        self._cleanup_expired_behaviors()
        
        # 保存数据
        self._save_behavior_data()
        
        # 只在有值的情况下打印日志
        log_parts = [f"{behavior_type}"]
        if bvid:
            log_parts.append(f"BV号: {bvid}")
        if keyword:
            log_parts.append(f"关键词: {keyword}")
        if author:
            log_parts.append(f"作者: {author}")
        print(f"记录用户行为: {', '.join(log_parts)}")
    
    def _is_duplicate_behavior(self, behavior_type: str, bvid: str, 
                            keyword: str, author: str, current_time: float) -> bool:
        """检查是否为重复行为"""
        recent_behaviors = [
            b for b in self.behavior_data['behaviors']
            if current_time - b['timestamp'] < ANTI_SPAM_WINDOW
        ]
        
        for behavior in recent_behaviors:
            if (behavior['type'] == behavior_type and 
                behavior.get('bvid') == bvid and 
                behavior.get('keyword') == keyword and 
                behavior.get('author') == author):
                return True
        
        return False
    
    def _update_scores(self, behavior_type: str, bvid: str, 
                     keyword: str, author: str):
        """更新评分"""
        weight = BEHAVIOR_WEIGHTS.get(behavior_type, 1.0)
        
        # 更新视频评分
        if bvid:
            self.behavior_data['video_scores'][bvid] = \
                self.behavior_data['video_scores'].get(bvid, 0) + weight
        
        # 更新关键词评分
        if keyword:
            self.behavior_data['keyword_scores'][keyword] = \
                self.behavior_data['keyword_scores'].get(keyword, 0) + weight
        
        # 更新作者评分
        if author:
            self.behavior_data['author_scores'][author] = \
                self.behavior_data['author_scores'].get(author, 0) + weight
    
    def _cleanup_expired_behaviors(self):
        """清理过期的行为记录"""
        current_time = datetime.now().timestamp()
        
        # 清理过期行为
        self.behavior_data['behaviors'] = [
            b for b in self.behavior_data['behaviors']
            if current_time - b['timestamp'] < BEHAVIOR_EXPIRY.get(b['type'], 7 * 24 * 60 * 60)
        ]
        
        # 清理过期评分
        for bvid, score in list(self.behavior_data['video_scores'].items()):
            if score < 0.1:  # 评分过低则删除
                del self.behavior_data['video_scores'][bvid]
        
        for keyword, score in list(self.behavior_data['keyword_scores'].items()):
            if score < 0.1:
                del self.behavior_data['keyword_scores'][keyword]
        
        for author, score in list(self.behavior_data['author_scores'].items()):
            if score < 0.1:
                del self.behavior_data['author_scores'][author]
    
    def get_video_score(self, bvid: str) -> float:
        """获取视频评分"""
        return self.behavior_data['video_scores'].get(bvid, 0)
    
    def get_keyword_score(self, keyword: str) -> float:
        """获取关键词评分"""
        return self.behavior_data['keyword_scores'].get(keyword, 0)
    
    def get_author_score(self, author: str) -> float:
        """获取作者评分"""
        return self.behavior_data['author_scores'].get(author, 0)
    
    def get_top_keywords(self, limit: int = 10) -> List[tuple]:
        """获取热门关键词"""
        sorted_keywords = sorted(
            self.behavior_data['keyword_scores'].items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_keywords[:limit]
    
    def get_top_authors(self, limit: int = 10) -> List[tuple]:
        """获取热门作者"""
        sorted_authors = sorted(
            self.behavior_data['author_scores'].items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_authors[:limit]
    
    def get_user_preferences(self) -> Dict[str, Any]:
        """获取用户偏好"""
        return {
            'top_keywords': self.get_top_keywords(5),
            'top_authors': self.get_top_authors(5),
            'total_behaviors': len(self.behavior_data['behaviors']),
            'video_scores_count': len(self.behavior_data['video_scores']),
            'keyword_scores_count': len(self.behavior_data['keyword_scores']),
            'author_scores_count': len(self.behavior_data['author_scores'])
        }

# 全局用户行为管理器实例
user_behavior_manager = UserBehaviorManager()