"""
云端调控模块 - 智能音乐推荐与分享系统（融合版）
负责与服务器端的通信，实现算法更新、数据同步等功能
"""
import json
import os
import time
import random
from typing import List, Dict, Any
from pathlib import Path
from datetime import datetime, timedelta

from config import (
    load_cloud_config, save_cloud_config, get_server_url, get_api_base,
    DEFAULT_CLOUD_CONFIG
)
from utils.logger import logger

# 本地存储路径
PROJECT_DIR = Path(__file__).parent.parent.absolute()
CLOUD_DATA_DIR = PROJECT_DIR / "data" / "cloud"
ALGORITHM_DIR = PROJECT_DIR / "services" / "algorithms"

class CloudControl:
    """云端调控类 - 支持本地模拟模式"""
    
    def __init__(self):
        self.config = load_cloud_config()
        self.server_url = get_server_url(self.config)
        self.api_base = get_api_base(self.config)
        self.sync_interval = self.config.get('sync_interval', 3600)
        self.algorithm_update_interval = self.config.get('algorithm_update_interval', 86400)
        self.enabled = self.config.get('enabled', True)
        self.community_enabled = self.config.get('community_enabled', True)
        self.allow_guest_comments = self.config.get('allow_guest_comments', True)
        self.last_sync_time = 0
        self.last_algorithm_update_time = 0
        self._ensure_directories()
        self._init_local_mock_data()
    
    def _init_local_mock_data(self):
        """初始化本地模拟数据"""
        self.mock_hot_recommendations = self._generate_mock_hot_recommendations()
        self.mock_algorithm_updates = self._generate_mock_algorithm_updates()
        self.mock_server_status = {
            "online": True,
            "version": "2.0.0",
            "uptime": 86400,
            "users_online": random.randint(50, 200)
        }
    
    def _generate_mock_hot_recommendations(self) -> List[Dict[str, Any]]:
        """生成模拟的热门推荐数据"""
        mock_videos = [
            {"bvid": "BV1xx411c7mD", "title": "【初音ミク】世界第一的公主殿下", "ip": "vocaloid", "views": 1250000, "likes": 85000},
            {"bvid": "BV2xx411c7mE", "title": "【镜音リン】炉心融解", "ip": "vocaloid", "views": 980000, "likes": 72000},
            {"bvid": "BV3xx411c7mF", "title": "【巡音ルカ】Just Be Friends", "ip": "vocaloid", "views": 750000, "likes": 58000},
            {"bvid": "BV4xx411c7mG", "title": "【GUMI】ECHO", "ip": "vocaloid", "views": 620000, "likes": 45000},
            {"bvid": "BV5xx411c7mH", "title": "【IA】六兆年と一夜物語", "ip": "vocaloid", "views": 510000, "likes": 38000},
            {"bvid": "BV6xx411c7mI", "title": "【结月缘】夜咄DECEIVE", "ip": "vocaloid", "views": 480000, "likes": 35000},
            {"bvid": "BV7xx411c7mJ", "title": "【MEIKO】番凩", "ip": "vocaloid", "views": 420000, "likes": 31000},
            {"bvid": "BV8xx411c7mK", "title": "【KAITO】千年的独奏歌", "ip": "vocaloid", "views": 390000, "likes": 28000}
        ]
        return mock_videos
    
    def _generate_mock_algorithm_updates(self) -> Dict[str, Any]:
        """生成模拟的算法更新数据"""
        return {
            "success": True,
            "data": {
                "name": "intelligent_recommend",
                "version": "2.1.0",
                "description": "优化了用户行为分析算法，提升推荐准确率15%",
                "release_date": datetime.now().strftime('%Y-%m-%d'),
                "download_url": "local://algorithm_update"
            }
        }
    
    def reload_config(self):
        """重新加载配置"""
        self.config = load_cloud_config()
        self.server_url = get_server_url(self.config)
        self.api_base = get_api_base(self.config)
        self.sync_interval = self.config.get('sync_interval', 3600)
        self.algorithm_update_interval = self.config.get('algorithm_update_interval', 86400)
        self.enabled = self.config.get('enabled', True)
        self.community_enabled = self.config.get('community_enabled', True)
        self.allow_guest_comments = self.config.get('allow_guest_comments', True)
    
    def update_config(self, **kwargs):
        """
        更新云端配置
        :param kwargs: 配置项
        :return: 是否更新成功
        """
        try:
            self.config.update(kwargs)
            if save_cloud_config(self.config):
                self.reload_config()
                return True
            return False
        except Exception as e:
            logger.error(f"更新云端配置失败: {e}")
            return False
    
    def get_full_api_url(self, endpoint: str) -> str:
        """
        获取完整API URL
        :param endpoint: API端点
        :return: 完整URL
        """
        base = self.server_url.rstrip('/')
        api = self.api_base.rstrip('/')
        ep = endpoint.lstrip('/')
        return f"{base}{api}/{ep}"
    
    def _ensure_directories(self):
        """确保目录存在"""
        CLOUD_DATA_DIR.mkdir(parents=True, exist_ok=True)
        ALGORITHM_DIR.mkdir(parents=True, exist_ok=True)
    
    def check_server_connection(self) -> bool:
        """
        检查服务器连接（本地模拟模式）
        :return: 是否连接成功
        """
        if not self.enabled:
            return False
        return self.mock_server_status.get("online", True)
    
    def sync_user_data(self, user_id: int, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        同步用户数据（本地模拟模式）
        :param user_id: 用户ID
        :param user_data: 用户数据
        :return: 同步结果
        """
        if not self.enabled:
            return {"success": False, "error": "云端调控已禁用"}
        try:
            time.sleep(0.5)
            sync_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            local_file = CLOUD_DATA_DIR / f"sync_{user_id}_{int(time.time())}.json"
            with open(local_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "user_id": user_id,
                    "sync_time": sync_time,
                    "data": user_data
                }, f, ensure_ascii=False, indent=2)
            return {
                "success": True,
                "sync_time": sync_time,
                "message": "数据同步成功（本地存储）"
            }
        except Exception as e:
            logger.error(f"同步用户数据失败: {e}")
            return {"success": False, "error": str(e)}
    
    def get_algorithm_update(self) -> Dict[str, Any]:
        """
        获取算法更新（本地模拟模式）
        :return: 算法更新结果
        """
        try:
            time.sleep(0.3)
            return self.mock_algorithm_updates
        except Exception as e:
            logger.error(f"获取算法更新失败: {e}")
            return {"success": False, "error": str(e)}
    
    def download_algorithm(self, algorithm_name: str, version: str) -> bool:
        """
        下载算法（本地模拟模式）
        :param algorithm_name: 算法名称
        :param version: 算法版本
        :return: 是否下载成功
        """
        try:
            time.sleep(0.8)
            algorithm_file = ALGORITHM_DIR / f"{algorithm_name}_{version}.py"
            with open(algorithm_file, 'w', encoding='utf-8') as f:
                f.write(f"""# {algorithm_name} - Version {version}
# Auto-generated mock algorithm file
# Downloaded: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

def recommend(user_id, limit=20):
    \"\"\"模拟推荐函数\"\"\"
    return []
""")
            logger.info(f"算法 {algorithm_name} v{version} 下载成功（本地模拟）")
            return True
        except Exception as e:
            logger.error(f"下载算法失败: {e}")
            return False
    
    def get_hot_recommendations(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        获取热门推荐（本地模拟模式）
        :param limit: 推荐数量
        :return: 热门推荐列表
        """
        try:
            time.sleep(0.2)
            recommendations = self.mock_hot_recommendations[:limit]
            for rec in recommendations:
                rec['views'] += random.randint(100, 1000)
                rec['likes'] += random.randint(10, 100)
            logger.info(f"获取到 {len(recommendations)} 条热门推荐（本地模拟）")
            return recommendations
        except Exception as e:
            logger.error(f"获取热门推荐失败: {e}")
            return []
    
    def update_user_behavior(self, user_id: int, behavior_data: Dict[str, Any]) -> bool:
        """
        更新用户行为数据（本地模拟模式）
        :param user_id: 用户ID
        :param behavior_data: 行为数据
        :return: 是否更新成功
        """
        try:
            time.sleep(0.2)
            behavior_file = CLOUD_DATA_DIR / f"behavior_{user_id}.json"
            behaviors = []
            if behavior_file.exists():
                with open(behavior_file, 'r', encoding='utf-8') as f:
                    behaviors = json.load(f)
            behavior_data['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            behaviors.append(behavior_data)
            with open(behavior_file, 'w', encoding='utf-8') as f:
                json.dump(behaviors[-100:], f, ensure_ascii=False, indent=2)
            logger.debug(f"用户行为数据更新成功（本地存储）")
            return True
        except Exception as e:
            logger.error(f"更新用户行为数据失败: {e}")
            return False
    
    def get_server_status(self) -> Dict[str, Any]:
        """
        获取服务器状态（本地模拟模式）
        :return: 服务器状态
        """
        self.mock_server_status['users_online'] = random.randint(50, 200)
        return self.mock_server_status
    
    def should_sync(self) -> bool:
        """
        判断是否应该同步数据
        :return: 是否应该同步
        """
        current_time = time.time()
        return current_time - self.last_sync_time >= self.sync_interval
    
    def should_update_algorithm(self) -> bool:
        """
        判断是否应该更新算法
        :return: 是否应该更新
        """
        current_time = time.time()
        return current_time - self.last_algorithm_update_time >= self.algorithm_update_interval
    
    def sync_all(self, user_id: int, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        同步所有数据
        :param user_id: 用户ID
        :param user_data: 用户数据
        :return: 同步结果
        """
        results = {
            'user_data_sync': False,
            'algorithm_update': False,
            'hot_recommendations': []
        }
        
        # 同步用户数据
        if self.should_sync():
            sync_result = self.sync_user_data(user_id, user_data)
            results['user_data_sync'] = sync_result.get('success', False)
            self.last_sync_time = time.time()
        
        # 更新算法
        if self.should_update_algorithm():
            algorithm_result = self.get_algorithm_update()
            if algorithm_result.get('success'):
                algorithm_info = algorithm_result.get('data', {})
                algorithm_name = algorithm_info.get('name')
                version = algorithm_info.get('version')
                if algorithm_name and version:
                    results['algorithm_update'] = self.download_algorithm(algorithm_name, version)
                    self.last_algorithm_update_time = time.time()
        
        # 获取热门推荐
        results['hot_recommendations'] = self.get_hot_recommendations()
        
        return results
    
    def load_local_algorithm(self, algorithm_name: str) -> Any:
        """
        加载本地算法
        :param algorithm_name: 算法名称
        :return: 算法模块
        """
        try:
            # 查找最新版本的算法
            algorithm_files = list(ALGORITHM_DIR.glob(f"{algorithm_name}_*.py"))
            if not algorithm_files:
                return None
            
            # 按版本号排序，选择最新版本
            algorithm_files.sort(key=lambda x: x.name.split('_')[-1].replace('.py', ''), reverse=True)
            latest_algorithm = algorithm_files[0]
            
            # 动态导入算法模块
            import importlib.util
            spec = importlib.util.spec_from_file_location(algorithm_name, str(latest_algorithm))
            algorithm_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(algorithm_module)
            
            return algorithm_module
        except Exception as e:
            logger.error(f"加载本地算法失败: {e}")
            return None