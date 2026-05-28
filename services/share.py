"""
分享系统 - 智能音乐推荐与分享系统（融合版）
"""
import json
import os
from typing import List, Dict, Any
from datetime import datetime
from pathlib import Path

from config import SHARE_LINK_FORMAT, SHARE_TYPES
from utils.data_manager import get_music_data, get_music_by_bvid

# 分享数据文件路径
PROJECT_DIR = Path(__file__).parent.parent.absolute()
SHARES_FILE = PROJECT_DIR / "data" / "shares.json"

class ShareSystem:
    """分享系统"""
    
    def __init__(self):
        self.share_types = SHARE_TYPES
        self.link_format = SHARE_LINK_FORMAT
        self._ensure_shares_file()
    
    def _ensure_shares_file(self):
        """确保分享数据文件存在"""
        shares_dir = SHARES_FILE.parent
        shares_dir.mkdir(parents=True, exist_ok=True)
        if not SHARES_FILE.exists():
            with open(SHARES_FILE, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
    
    def _load_shares(self) -> List[Dict[str, Any]]:
        """加载分享数据"""
        self._ensure_shares_file()
        try:
            with open(SHARES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载分享数据失败: {e}")
            return []
    
    def _save_shares(self, shares: List[Dict[str, Any]]):
        """保存分享数据"""
        self._ensure_shares_file()
        try:
            with open(SHARES_FILE, 'w', encoding='utf-8') as f:
                json.dump(shares, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存分享数据失败: {e}")
            return False
    
    def create_share(self, user_id: int, bvid: str, share_type: str = "link") -> Dict[str, Any]:
        """
        创建分享
        :param user_id: 用户ID
        :param bvid: 视频BV号
        :param share_type: 分享类型
        :return: 分享信息
        """
        try:
            # 获取音乐信息
            music = get_music_by_bvid(bvid)
            if not music:
                # 如果在音乐数据中找不到，使用BV号生成基本信息
                title = f"视频 {bvid}"
            else:
                title = music.get('title', f"视频 {bvid}")
            
            # 生成分享链接
            share_link = self.link_format.format(bvid=bvid)
            
            # 加载现有分享数据
            shares = self._load_shares()
            
            # 生成分享ID
            share_id = len(shares) + 1
            
            # 创建分享记录
            share = {
                'id': share_id,
                'user_id': user_id,
                'bvid': bvid,
                'title': title,
                'share_type': share_type,
                'share_content': f'{{"link": "{share_link}", "title": "{title}"}}',
                'share_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'view_count': 0
            }
            
            # 添加到分享列表
            shares.append(share)
            
            # 保存分享数据
            if self._save_shares(shares):
                return {
                    "success": True,
                    "share_id": share_id,
                    "share_link": share_link,
                    "share_type": share_type,
                    "share_time": share['share_time']
                }
            else:
                return {"error": "保存分享记录失败"}
        except Exception as e:
            return {"error": str(e)}
    
    def get_user_shares(self, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """
        获取用户的分享记录
        :param user_id: 用户ID
        :param limit: 数量限制
        :return: 分享记录列表
        """
        try:
            # 加载分享数据
            shares = self._load_shares()
            
            # 过滤用户的分享记录
            user_shares = [share for share in shares if share.get('user_id') == user_id]
            
            # 按分享时间排序
            user_shares.sort(key=lambda x: x.get('share_time', ''), reverse=True)
            
            # 限制数量
            return user_shares[:limit]
        except Exception as e:
            print(f"获取用户分享记录失败: {e}")
            return []
    
    def get_hot_shares(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        获取热门分享
        :param limit: 数量限制
        :return: 热门分享列表
        """
        try:
            # 加载分享数据
            shares = self._load_shares()
            
            # 按查看次数排序
            shares.sort(key=lambda x: x.get('view_count', 0), reverse=True)
            
            # 限制数量
            return shares[:limit]
        except Exception as e:
            print(f"获取热门分享失败: {e}")
            return []
    
    def increment_view_count(self, share_id: int) -> bool:
        """
        增加分享查看次数
        :param share_id: 分享ID
        :return: 是否成功
        """
        try:
            # 加载分享数据
            shares = self._load_shares()
            
            # 查找分享记录
            for share in shares:
                if share.get('id') == share_id:
                    share['view_count'] = share.get('view_count', 0) + 1
                    # 保存更新后的数据
                    return self._save_shares(shares)
            
            return False
        except Exception as e:
            print(f"增加分享查看次数失败: {e}")
            return False


class ShareService:
    """分享服务"""
    
    def __init__(self):
        self.system = ShareSystem()
    
    def share_video(self, bvid, title, share_type="link"):
        """
        分享视频
        :param bvid: 视频BV号
        :param title: 视频标题
        :param share_type: 分享类型
        :return: 分享结果
        """
        try:
            # 创建分享记录
            result = self.system.create_share(1, bvid, share_type)
            return result
        except Exception as e:
            return {"error": str(e)}
    
    def get_user_shares(self, limit=20):
        """
        获取用户的分享记录
        :param limit: 数量限制
        :return: 分享记录列表
        """
        try:
            return self.system.get_user_shares(1, limit)
        except Exception as e:
            print(f"获取用户分享记录失败: {e}")
            return []
    
    def get_hot_shares(self, limit=20):
        """
        获取热门分享
        :param limit: 数量限制
        :return: 热门分享列表
        """
        try:
            return self.system.get_hot_shares(limit)
        except Exception as e:
            print(f"获取热门分享失败: {e}")
            return []