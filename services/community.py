"""
社区系统 - 支持游客发言的社区功能
"""
import json
import os
import hashlib
import time
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

# 社区数据文件路径
PROJECT_DIR = Path(__file__).parent.parent.absolute()
COMMUNITY_DIR = PROJECT_DIR / "data" / "community"
COMMENTS_FILE = COMMUNITY_DIR / "comments.json"
GUEST_USERS_FILE = COMMUNITY_DIR / "guest_users.json"

class CommunitySystem:
    """社区系统 - 支持游客发言"""
    
    def __init__(self):
        self._ensure_data_files()
    
    def _ensure_data_files(self):
        """确保数据文件和目录存在"""
        COMMUNITY_DIR.mkdir(parents=True, exist_ok=True)
        
        # 评论数据文件
        if not COMMENTS_FILE.exists():
            with open(COMMENTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._generate_sample_comments(), f, ensure_ascii=False, indent=2)
        
        # 游客用户数据文件
        if not GUEST_USERS_FILE.exists():
            with open(GUEST_USERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._generate_sample_users(), f, ensure_ascii=False, indent=2)
    
    def _generate_sample_users(self) -> Dict[str, Any]:
        """生成示例游客用户"""
        sample_users = {
            "guest_vocaloid_1": {
                "user_id": "guest_vocaloid_1",
                "nickname": "初音ミク",
                "type": "guest",
                "created_at": "2024-03-01 10:00:00",
                "last_active": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "comment_count": 12
            },
            "guest_vocaloid_2": {
                "user_id": "guest_vocaloid_2",
                "nickname": "镜音双子",
                "type": "guest",
                "created_at": "2024-03-05 15:30:00",
                "last_active": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "comment_count": 8
            },
            "guest_music_1": {
                "user_id": "guest_music_1",
                "nickname": "音乐爱好者",
                "type": "guest",
                "created_at": "2024-03-10 09:15:00",
                "last_active": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "comment_count": 5
            }
        }
        return sample_users
    
    def _generate_sample_comments(self) -> List[Dict[str, Any]]:
        """生成示例社区评论"""
        sample_comments = [
            {
                "id": 1,
                "user_id": "guest_vocaloid_1",
                "nickname": "初音ミク",
                "is_guest": True,
                "content": "这个推荐系统太棒了！找到了好多我以前没听过的好歌！🎉",
                "bvid": "BV123456",
                "parent_id": None,
                "created_at": "2024-04-15 14:20:00",
                "likes": 24,
                "status": "active"
            },
            {
                "id": 2,
                "user_id": "guest_vocaloid_2",
                "nickname": "镜音双子",
                "is_guest": True,
                "content": "推荐算法真的很懂我，推的全是我喜欢的类型！",
                "bvid": "BV789012",
                "parent_id": None,
                "created_at": "2024-04-16 09:45:00",
                "likes": 15,
                "status": "active"
            },
            {
                "id": 3,
                "user_id": "guest_music_1",
                "nickname": "音乐爱好者",
                "is_guest": True,
                "content": "界面设计得很漂亮，用起来很顺手！",
                "bvid": None,
                "parent_id": None,
                "created_at": "2024-04-17 16:30:00",
                "likes": 8,
                "status": "active"
            },
            {
                "id": 4,
                "user_id": "guest_vocaloid_1",
                "nickname": "初音ミク",
                "is_guest": True,
                "content": "强烈推荐大家试试，真的能发现很多宝藏歌曲！",
                "bvid": "BV345678",
                "parent_id": None,
                "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "likes": 32,
                "status": "active"
            }
        ]
        return sample_comments
    
    def _load_comments(self) -> List[Dict[str, Any]]:
        """加载评论数据"""
        try:
            with open(COMMENTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载评论数据失败: {e}")
            return []
    
    def _save_comments(self, comments: List[Dict[str, Any]]) -> bool:
        """保存评论数据"""
        try:
            with open(COMMENTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(comments, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存评论数据失败: {e}")
            return False
    
    def _load_guest_users(self) -> Dict[str, Any]:
        """加载游客用户数据"""
        try:
            with open(GUEST_USERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载游客用户数据失败: {e}")
            return {}
    
    def _save_guest_users(self, users: Dict[str, Any]) -> bool:
        """保存游客用户数据"""
        try:
            with open(GUEST_USERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(users, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存游客用户数据失败: {e}")
            return False
    
    def generate_guest_id(self, ip_address: str = None) -> str:
        """
        生成游客ID
        :param ip_address: IP地址（可选）
        :return: 游客ID
        """
        # 基于时间和IP生成唯一ID
        timestamp = str(int(time.time()))
        base_str = f"{ip_address or 'unknown'}_{timestamp}_{os.urandom(8).hex()}"
        guest_id = f"guest_{hashlib.md5(base_str.encode()).hexdigest()[:12]}"
        return guest_id
    
    def create_guest_user(self, nickname: str = None, ip_address: str = None) -> Dict[str, Any]:
        """
        创建游客用户
        :param nickname: 昵称（可选，默认随机生成）
        :param ip_address: IP地址
        :return: 游客用户信息
        """
        guest_id = self.generate_guest_id(ip_address)
        
        # 如果没有提供昵称，生成默认昵称
        if not nickname:
            nickname = f"游客{hashlib.md5(guest_id.encode()).hexdigest()[:6]}"
        
        guest_user = {
            'user_id': guest_id,
            'nickname': nickname,
            'type': 'guest',
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'last_active': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'ip_address': ip_address,
            'comment_count': 0
        }
        
        # 保存游客用户
        users = self._load_guest_users()
        users[guest_id] = guest_user
        self._save_guest_users(users)
        
        return guest_user
    
    def get_guest_user(self, guest_id: str) -> Optional[Dict[str, Any]]:
        """
        获取游客用户信息
        :param guest_id: 游客ID
        :return: 游客用户信息
        """
        users = self._load_guest_users()
        return users.get(guest_id)
    
    def post_comment(self, user_id: str, content: str, bvid: str = None, 
                     parent_id: int = None, is_guest: bool = True) -> Dict[str, Any]:
        """
        发表评论
        :param user_id: 用户ID（游客ID或注册用户ID）
        :param content: 评论内容
        :param bvid: 视频BV号（可选）
        :param parent_id: 父评论ID（用于回复）
        :param is_guest: 是否为游客
        :return: 评论信息
        """
        # 内容安全检查
        if not content or len(content.strip()) == 0:
            return {"success": False, "error": "评论内容不能为空"}
        
        if len(content) > 500:
            return {"success": False, "error": "评论内容不能超过500字"}
        
        # 加载评论数据
        comments = self._load_comments()
        
        # 生成评论ID
        comment_id = len(comments) + 1
        
        # 获取用户信息
        if is_guest:
            user = self.get_guest_user(user_id)
            if not user:
                return {"success": False, "error": "游客用户不存在"}
            nickname = user.get('nickname', '游客')
        else:
            # 注册用户（预留）
            nickname = "用户"  # 实际应从用户系统获取
        
        # 创建评论
        comment = {
            'id': comment_id,
            'user_id': user_id,
            'nickname': nickname,
            'is_guest': is_guest,
            'content': content.strip(),
            'bvid': bvid,
            'parent_id': parent_id,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'likes': 0,
            'status': 'active'  # active, hidden, deleted
        }
        
        # 添加到评论列表
        comments.append(comment)
        
        # 保存评论
        if self._save_comments(comments):
            # 更新用户评论数
            if is_guest and user:
                users = self._load_guest_users()
                if user_id in users:
                    users[user_id]['comment_count'] = users[user_id].get('comment_count', 0) + 1
                    users[user_id]['last_active'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    self._save_guest_users(users)
            
            return {
                "success": True,
                "comment": comment
            }
        else:
            return {"success": False, "error": "保存评论失败"}
    
    def get_comments(self, bvid: str = None, page: int = 1, per_page: int = 20,
                     include_guest: bool = True) -> Dict[str, Any]:
        """
        获取评论列表
        :param bvid: 视频BV号（可选，为None则获取所有评论）
        :param page: 页码
        :param per_page: 每页数量
        :param include_guest: 是否包含游客评论
        :return: 评论列表和分页信息
        """
        comments = self._load_comments()
        
        # 筛选评论
        filtered_comments = []
        for comment in comments:
            # 只显示活跃状态的评论
            if comment.get('status') != 'active':
                continue
            
            # 是否包含游客评论
            if not include_guest and comment.get('is_guest', False):
                continue
            
            # 按视频筛选
            if bvid and comment.get('bvid') != bvid:
                continue
            
            filtered_comments.append(comment)
        
        # 按时间倒序排序
        filtered_comments.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        # 分页
        total = len(filtered_comments)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_comments = filtered_comments[start:end]
        
        return {
            "success": True,
            "comments": paginated_comments,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": (total + per_page - 1) // per_page
            }
        }
    
    def like_comment(self, comment_id: int) -> Dict[str, Any]:
        """
        点赞评论
        :param comment_id: 评论ID
        :return: 操作结果
        """
        comments = self._load_comments()
        
        for comment in comments:
            if comment.get('id') == comment_id:
                comment['likes'] = comment.get('likes', 0) + 1
                if self._save_comments(comments):
                    return {"success": True, "likes": comment['likes']}
                else:
                    return {"success": False, "error": "保存失败"}
        
        return {"success": False, "error": "评论不存在"}
    
    def delete_comment(self, comment_id: int, user_id: str, is_admin: bool = False) -> Dict[str, Any]:
        """
        删除评论
        :param comment_id: 评论ID
        :param user_id: 用户ID
        :param is_admin: 是否为管理员
        :return: 操作结果
        """
        comments = self._load_comments()
        
        for comment in comments:
            if comment.get('id') == comment_id:
                # 只有评论作者或管理员可以删除
                if comment.get('user_id') == user_id or is_admin:
                    comment['status'] = 'deleted'
                    if self._save_comments(comments):
                        return {"success": True}
                    else:
                        return {"success": False, "error": "保存失败"}
                else:
                    return {"success": False, "error": "无权删除此评论"}
        
        return {"success": False, "error": "评论不存在"}
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取社区统计数据
        :return: 统计数据
        """
        comments = self._load_comments()
        users = self._load_guest_users()
        
        total_comments = len(comments)
        guest_comments = sum(1 for c in comments if c.get('is_guest', False))
        active_users = len(users)
        
        # 今日评论数
        today = datetime.now().strftime('%Y-%m-%d')
        today_comments = sum(1 for c in comments if c.get('created_at', '').startswith(today))
        
        return {
            "success": True,
            "stats": {
                "total_comments": total_comments,
                "guest_comments": guest_comments,
                "user_comments": total_comments - guest_comments,
                "active_guests": active_users,
                "today_comments": today_comments
            }
        }


# 全局社区系统实例
_community_system = None

def get_community_system() -> CommunitySystem:
    """获取社区系统实例（单例模式）"""
    global _community_system
    if _community_system is None:
        _community_system = CommunitySystem()
    return _community_system
