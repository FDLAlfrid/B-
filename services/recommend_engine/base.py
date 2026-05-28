# 基础推荐引擎接口

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class BaseRecommendEngine(ABC):
    """基础推荐引擎接口"""
    
    @abstractmethod
    def get_recommendations(self, limit: int = 10, **kwargs) -> List[Dict[str, Any]]:
        """获取推荐结果
        
        Args:
            limit: 推荐数量
            **kwargs: 其他参数
            
        Returns:
            推荐结果列表
        """
        pass
    
    @abstractmethod
    def refresh_data(self) -> bool:
        """刷新数据
        
        Returns:
            是否成功
        """
        pass
    
    @abstractmethod
    def get_hot_recommendations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取热门推荐
        
        Args:
            limit: 推荐数量
            
        Returns:
            热门推荐结果
        """
        pass