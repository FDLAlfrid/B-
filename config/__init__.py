# 配置模块初始化

from .base import *

__all__ = [
    # 基础配置
    'APP_NAME',
    'APP_VERSION',
    'DEBUG_MODE',
    
    # 推荐配置
    'RECOMMEND_ALGORITHM',
    'RECOMMEND_LIMIT',
    'RECOMMEND_CACHE_TIME',
    
    # 数据库配置
    'DATABASE_PATH',
    'DATABASE_BACKUP_PATH',
    
    # API配置
    'API_BASE_URL',
    'API_TIMEOUT',
    'API_RETRY_TIMES',
    
    # 用户配置
    'USER_DATA_PATH',
    'FAVORITES_PATH',
    'EXCLUDED_PATH',
    'PLAYLISTS_PATH',
    
    # 云控配置
    'CLOUD_SERVER_URL',
    'CLOUD_API_KEY',
    'CLOUD_SYNC_ENABLED',
    
    # 界面配置
    'THEME',
    'FONT_SIZE',
    'WINDOW_SIZE',
    'MAXIMIZE_WINDOW'
]