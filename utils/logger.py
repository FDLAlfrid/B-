"""
日志工具 - 智能音乐推荐与分享系统（融合版）
"""
import os
import logging
from logging.handlers import RotatingFileHandler
from config import LOG_FILE, LOG_LEVEL, LOG_FORMAT

class Logger:
    """日志工具类"""
    
    def __init__(self, name="vocaloid_toolbox"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, LOG_LEVEL))
        
        # 创建文件处理器
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, LOG_LEVEL))
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, LOG_LEVEL))
        
        # 创建格式化器
        formatter = logging.Formatter(LOG_FORMAT)
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # 添加处理器
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def info(self, message):
        """记录信息日志"""
        self.logger.info(message)
    
    def warning(self, message):
        """记录警告日志"""
        self.logger.warning(message)
    
    def error(self, message):
        """记录错误日志"""
        self.logger.error(message)
    
    def debug(self, message):
        """记录调试日志"""
        self.logger.debug(message)
    
    def log_search(self, keyword, result_count, success=True):
        """记录搜索行为"""
        if success:
            self.info(f"搜索成功 - 关键词: {keyword}, 结果数: {result_count}")
        else:
            self.warning(f"搜索失败 - 关键词: {keyword}")
    
    def log_user_action(self, action, details):
        """记录用户行为"""
        self.info(f"用户行为 - {action}: {details}")
    
    def log_error(self, error_type, error_message):
        """记录错误"""
        self.error(f"错误类型: {error_type}, 错误信息: {error_message}")

# 创建全局日志实例
logger = Logger()


def get_logger(name=None):
    """获取日志实例"""
    global logger
    return logger
