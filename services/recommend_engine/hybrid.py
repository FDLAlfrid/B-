# 混合推荐引擎

from typing import List, Dict, Any
from .traditional import TraditionalRecommendEngine
from .intelligent import IntelligentRecommendEngine


class HybridRecommendEngine:
    """混合推荐引擎
    
    结合传统推荐和智能推荐的优势
    """
    
    def __init__(self):
        """初始化混合推荐引擎"""
        self.traditional_engine = TraditionalRecommendEngine()
        self.intelligent_engine = IntelligentRecommendEngine()
        self.hybrid_weights = {
            'traditional': 0.3,  # 传统推荐权重
            'intelligent': 0.7   # 智能推荐权重
        }
    
    def get_recommendations(self, user_id: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """获取混合推荐结果
        
        Args:
            user_id: 用户ID
            limit: 推荐数量
            
        Returns:
            混合推荐结果
        """
        # 获取传统推荐
        traditional_results = self.traditional_engine.get_hot_recommendations(limit=limit * 2)
        
        # 获取智能推荐
        intelligent_results = []
        if user_id:
            try:
                intelligent_results = self.intelligent_engine.get_intelligent_recommendations(
                    user_id, limit=limit * 2
                )
            except Exception as e:
                print(f"智能推荐失败: {e}")
                intelligent_results = traditional_results[:limit * 2]
        else:
            intelligent_results = traditional_results[:limit * 2]
        
        # 合并结果
        combined_results = self._combine_results(
            traditional_results, 
            intelligent_results, 
            limit
        )
        
        return combined_results
    
    def _combine_results(self, traditional_results: List[Dict[str, Any]], 
                        intelligent_results: List[Dict[str, Any]], 
                        limit: int) -> List[Dict[str, Any]]:
        """合并推荐结果
        
        Args:
            traditional_results: 传统推荐结果
            intelligent_results: 智能推荐结果
            limit: 最终推荐数量
            
        Returns:
            合并后的推荐结果
        """
        # 去重
        seen_bvids = set()
        combined = []
        
        # 先添加智能推荐结果
        for item in intelligent_results:
            bvid = item.get('bvid')
            if bvid not in seen_bvids:
                seen_bvids.add(bvid)
                combined.append(item)
            if len(combined) >= limit * self.hybrid_weights['intelligent']:
                break
        
        # 再添加传统推荐结果
        for item in traditional_results:
            bvid = item.get('bvid')
            if bvid not in seen_bvids:
                seen_bvids.add(bvid)
                combined.append(item)
            if len(combined) >= limit:
                break
        
        return combined[:limit]
    
    def refresh_data(self) -> bool:
        """刷新数据
        
        Returns:
            是否成功
        """
        traditional_ok = self.traditional_engine.refresh_data()
        intelligent_ok = True  # 智能推荐引擎通常不需要刷新
        
        return traditional_ok and intelligent_ok
    
    def get_hot_recommendations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取热门推荐
        
        Args:
            limit: 推荐数量
            
        Returns:
            热门推荐结果
        """
        return self.traditional_engine.get_hot_recommendations(limit=limit)