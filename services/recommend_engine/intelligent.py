"""
智能推荐引擎 - 集成用户偏好学习的推荐系统
基于论文[13][14][15]的深度学习技术实现智能推荐
"""

import numpy as np
from typing import List, Dict, Any, Tuple
from datetime import datetime
from collections import defaultdict
from services.user_preference_learning import (
    preference_analyzer, record_user_behavior, get_user_preferences
)
from .traditional import RecommendEngine
from config import RECOMMEND_WEIGHTS, DEFAULT_RECOMMEND_LIMIT

class IntelligentRecommendEngine:
    """智能推荐引擎 - 融合传统算法与智能偏好学习"""
    
    def __init__(self):
        # 传统推荐引擎（保持兼容性）
        self.traditional_engine = RecommendEngine()
        
        # 智能推荐配置
        self.intelligent_config = {
            'hybrid_weight': 0.7,           # 智能算法权重
            'traditional_weight': 0.3,      # 传统算法权重
            'preference_threshold': 0.6,    # 偏好匹配阈值
            'diversity_factor': 0.2,        # 多样性因子
            'cold_start_days': 7,           # 冷启动天数
            'min_behavior_count': 5         # 最小行为数
        }
        
        # 用户推荐历史
        self.user_recommendation_history = defaultdict(list)
        
        # 风格聚类模型
        self.style_clusters = None
        self.singer_clusters = None
    
    def get_intelligent_recommendations(self, user_id: str, limit: int = DEFAULT_RECOMMEND_LIMIT, 
                                      use_preferences: bool = True, excluded_bvids: List[str] = None) -> List[Dict[str, Any]]:
        """获取智能推荐 - 基于论文[14]的内容推荐系统"""
        
        # 获取传统推荐结果
        traditional_results = self.traditional_engine.get_hot_recommendations(
            limit=limit * 2,  # 获取更多用于筛选
            use_history=False,  # 不使用历史记录，避免干扰
            excluded_bvids=excluded_bvids
        )
        
        if not use_preferences or self._is_cold_start_user(user_id):
            # 冷启动用户或禁用偏好学习，使用传统算法
            # 过滤排除列表
            if excluded_bvids:
                traditional_results = [item for item in traditional_results if item.get('bvid') not in excluded_bvids]
            return traditional_results[:limit]
        
        # 获取用户偏好
        user_preferences = get_user_preferences(user_id)
        
        # 基于偏好筛选和重排序
        intelligent_results = self._rank_by_preferences(
            traditional_results, user_preferences, limit
        )
        
        # 记录推荐历史
        self._record_recommendation_history(user_id, intelligent_results)
        
        return intelligent_results
    
    def _is_cold_start_user(self, user_id: str) -> bool:
        """判断是否为冷启动用户"""
        user_preferences = get_user_preferences(user_id)
        behavior_count = user_preferences.get('behavior_count', 0)
        
        # 行为数太少或偏好分数太低
        if behavior_count < self.intelligent_config['min_behavior_count']:
            return True
        
        # 偏好分数太低
        overall_preference = user_preferences.get('overall_preference', 0)
        if overall_preference < 0.3:
            return True
        
        return False
    
    def _rank_by_preferences(self, music_list: List[Dict], 
                           preferences: Dict[str, Any], limit: int) -> List[Dict]:
        """基于用户偏好对音乐列表进行重排序"""
        
        scored_music = []
        
        for music in music_list:
            # 计算偏好匹配度
            preference_score = self._calculate_preference_match_score(music, preferences)
            
            # 计算多样性分数（避免推荐过于相似的内容）
            diversity_score = self._calculate_diversity_score(music, preferences)
            
            # 综合分数
            final_score = (preference_score * (1 - self.intelligent_config['diversity_factor']) +
                         diversity_score * self.intelligent_config['diversity_factor'])
            
            scored_music.append((music, final_score))
        
        # 按分数排序
        scored_music.sort(key=lambda x: x[1], reverse=True)
        
        # 返回前limit个结果
        return [music for music, score in scored_music[:limit]]
    
    def _calculate_preference_match_score(self, music: Dict, preferences: Dict) -> float:
        """计算音乐与用户偏好的匹配度 - 基于论文[13]的特征匹配"""
        
        title = music.get('title', '').lower()
        author = music.get('up主', '').lower()
        description = music.get('description', '').lower()
        
        # 风格匹配度
        style_score = self._calculate_style_match_score(title + ' ' + description, 
                                                      preferences['style_preferences'])
        
        # 歌手匹配度
        singer_score = self._calculate_singer_match_score(title, author, 
                                                        preferences['singer_preferences'])
        
        # UP主匹配度
        producer_score = self._calculate_producer_match_score(author, 
                                                            preferences['producer_preferences'])
        
        # 情感匹配度
        emotion_score = self._calculate_emotion_match_score(title + ' ' + description, 
                                                           preferences['emotion_preferences'])
        
        # 综合匹配度（使用偏好权重）
        total_score = (
            style_score * 0.35 +  # 风格权重
            singer_score * 0.30 +  # 歌手权重
            producer_score * 0.25 +  # UP主权重
            emotion_score * 0.10    # 情感权重
        )
        
        return min(total_score, 1.0)
    
    def _calculate_style_match_score(self, text: str, style_preferences: Dict[str, float]) -> float:
        """计算风格匹配度"""
        if not style_preferences:
            return 0.5  # 默认分数
        
        # 风格关键词匹配
        style_keywords = {
            '古风': ['古风', '中国风', '汉服', '诗词', '传统'],
            '电子': ['电子', 'edm', '电音', '合成器', '舞曲'],
            '流行': ['流行', 'pop', '情歌', '抒情', '温柔'],
            '摇滚': ['摇滚', '金属', '朋克', '硬核', '激情'],
            '说唱': ['说唱', 'rap', '饶舌', '嘻哈', '节奏'],
            '治愈': ['治愈', '温暖', '安静', '轻柔', '舒缓'],
            '燃系': ['燃', '热血', '战斗', '激昂', '震撼']
        }
        
        match_scores = []
        for style, keywords in style_keywords.items():
            if style in style_preferences:
                # 计算该风格的关键词匹配度
                keyword_matches = sum(1 for keyword in keywords if keyword in text)
                style_match = min(keyword_matches / len(keywords), 1.0)
                
                # 加权分数
                weighted_score = style_match * style_preferences[style]
                match_scores.append(weighted_score)
        
        return sum(match_scores) if match_scores else 0.0
    
    def _calculate_singer_match_score(self, title: str, author: str, 
                                    singer_preferences: Dict[str, float]) -> float:
        """计算虚拟歌手匹配度"""
        if not singer_preferences:
            return 0.5  # 默认分数
        
        # 虚拟歌手列表
        vocaloid_singers = [
            '洛天依', '乐正绫', '言和', '心华', '墨清弦', 
            '摩柯', '徵羽', '初音未来', '镜音铃', '巡音流歌'
        ]
        
        match_scores = []
        for singer in vocaloid_singers:
            if singer in singer_preferences:
                # 检查标题和UP主名中是否包含歌手
                singer_present = (singer in title or singer in author)
                if singer_present:
                    match_scores.append(singer_preferences[singer])
        
        return max(match_scores) if match_scores else 0.0
    
    def _calculate_producer_match_score(self, author: str, 
                                      producer_preferences: Dict[str, float]) -> float:
        """计算UP主匹配度"""
        if not producer_preferences:
            return 0.5  # 默认分数
        
        # 检查UP主是否在偏好列表中
        for producer, preference in producer_preferences.items():
            if producer.lower() in author.lower():
                return preference
        
        return 0.0
    
    def _calculate_emotion_match_score(self, text: str, 
                                     emotion_preferences: Dict[str, float]) -> float:
        """计算情感匹配度"""
        if not emotion_preferences:
            return 0.5  # 默认分数
        
        # 情感关键词匹配
        emotion_keywords = {
            '快乐': ['快乐', '开心', '喜悦', '欢快', '幸福'],
            '悲伤': ['悲伤', '伤感', '忧郁', '难过', '眼泪'],
            '平静': ['平静', '安宁', '宁静', '平和', '安静'],
            '激动': ['激动', '兴奋', '热血', '激情', '振奋']
        }
        
        match_scores = []
        for emotion, keywords in emotion_keywords.items():
            if emotion in emotion_preferences:
                # 计算该情感的关键词匹配度
                keyword_matches = sum(1 for keyword in keywords if keyword in text)
                emotion_match = min(keyword_matches / len(keywords), 1.0)
                
                # 加权分数
                weighted_score = emotion_match * emotion_preferences[emotion]
                match_scores.append(weighted_score)
        
        return sum(match_scores) if match_scores else 0.0
    
    def _calculate_diversity_score(self, music: Dict, preferences: Dict) -> float:
        """计算多样性分数 - 避免推荐过于相似的内容"""
        # 简化实现：基于音乐特征的多样性
        return 0.5  # 默认多样性分数
    
    def _record_recommendation_history(self, user_id: str, recommendations: List[Dict]):
        """记录推荐历史"""
        history_entry = {
            'timestamp': datetime.now().isoformat(),
            'recommendations': [music.get('bvid', '') for music in recommendations],
            'count': len(recommendations)
        }
        
        self.user_recommendation_history[user_id].append(history_entry)
        
        # 保持最近10次推荐历史
        if len(self.user_recommendation_history[user_id]) > 10:
            self.user_recommendation_history[user_id] = self.user_recommendation_history[user_id][-10:]
    
    def get_recommendation_explanation(self, user_id: str, music: Dict) -> Dict[str, Any]:
        """获取推荐解释 - 基于论文[14]的可解释性推荐"""
        preferences = get_user_preferences(user_id)
        
        title = music.get('title', '')
        author = music.get('up主', '')
        
        explanation = {
            'music_title': title,
            'music_author': author,
            'explanation_points': []
        }
        
        # 风格解释
        style_explanation = self._explain_style_match(title, preferences['style_preferences'])
        if style_explanation:
            explanation['explanation_points'].append(style_explanation)
        
        # 歌手解释
        singer_explanation = self._explain_singer_match(title, author, preferences['singer_preferences'])
        if singer_explanation:
            explanation['explanation_points'].append(singer_explanation)
        
        # UP主解释
        producer_explanation = self._explain_producer_match(author, preferences['producer_preferences'])
        if producer_explanation:
            explanation['explanation_points'].append(producer_explanation)
        
        return explanation
    
    def _explain_style_match(self, title: str, style_preferences: Dict) -> str:
        """生成风格匹配解释"""
        if not style_preferences:
            return ""
        
        # 检查标题中的风格关键词
        style_keywords = {
            '古风': ['古风', '中国风', '汉服', '诗词'],
            '电子': ['电子', 'EDM', '电音', '合成器'],
            '流行': ['流行', 'POP', '情歌', '抒情'],
            '摇滚': ['摇滚', '金属', '朋克', '硬核']
        }
        
        for style, keywords in style_keywords.items():
            if style in style_preferences and any(keyword in title for keyword in keywords):
                return f"符合您喜欢的{style}风格（偏好度：{style_preferences[style]:.1%}）"
        
        return ""
    
    def _explain_singer_match(self, title: str, author: str, singer_preferences: Dict) -> str:
        """生成歌手匹配解释"""
        if not singer_preferences:
            return ""
        
        vocaloid_singers = ['洛天依', '乐正绫', '言和', '心华', '初音未来']
        
        for singer in vocaloid_singers:
            if singer in singer_preferences and (singer in title or singer in author):
                return f"包含您喜欢的虚拟歌手{singer}（偏好度：{singer_preferences[singer]:.1%}）"
        
        return ""
    
    def _explain_producer_match(self, author: str, producer_preferences: Dict) -> str:
        """生成UP主匹配解释"""
        if not producer_preferences:
            return ""
        
        for producer, preference in producer_preferences.items():
            if producer.lower() in author.lower():
                return f"由您关注的UP主{producer}创作（偏好度：{preference:.1%}）"
        
        return ""

# 全局智能推荐引擎实例
intelligent_engine = IntelligentRecommendEngine()

def get_intelligent_recommendations(user_id: str, limit: int = DEFAULT_RECOMMEND_LIMIT) -> List[Dict[str, Any]]:
    """获取智能推荐"""
    return intelligent_engine.get_intelligent_recommendations(user_id, limit)

def record_user_interaction(user_id: str, music_data: Dict[str, Any], 
                          interaction_type: str):
    """记录用户交互行为"""
    record_user_behavior(user_id, music_data, interaction_type)

def get_user_preference_analysis(user_id: str) -> Dict[str, Any]:
    """获取用户偏好分析"""
    return get_user_preferences(user_id)

def get_recommendation_explanation(user_id: str, music: Dict) -> Dict[str, Any]:
    """获取推荐解释"""
    return intelligent_engine.get_recommendation_explanation(user_id, music)

# 测试函数
def test_intelligent_recommendation():
    """测试智能推荐功能"""
    print("=== 测试智能推荐系统 ===")
    
    # 模拟用户行为
    test_music = {
        'bvid': 'BV1test123',
        'title': '洛天依 - 古风电子舞曲《星辰大海》',
        'up主': 'ilem',
        'description': '一首融合古风和电子元素的原创歌曲',
        'play_count': 100000
    }
    
    # 记录用户行为
    record_user_interaction('test_user', test_music, 'click')
    record_user_interaction('test_user', test_music, 'like')
    
    # 获取智能推荐
    recommendations = get_intelligent_recommendations('test_user', limit=5)
    
    print("智能推荐结果:")
    for i, music in enumerate(recommendations, 1):
        print(f"{i}. {music.get('title', '未知')} - {music.get('up主', '未知')}")
        
        # 获取推荐解释
        explanation = get_recommendation_explanation('test_user', music)
        if explanation['explanation_points']:
            print("   推荐理由:")
            for point in explanation['explanation_points']:
                print(f"   - {point}")
    
    # 获取用户偏好分析
    preferences = get_user_preference_analysis('test_user')
    print(f"\n用户偏好分析:")
    print(f"风格偏好: {preferences['style_preferences']}")
    print(f"歌手偏好: {preferences['singer_preferences']}")
    print(f"UP主偏好: {preferences['producer_preferences']}")
    print(f"综合偏好分数: {preferences['overall_preference']:.2f}")

if __name__ == "__main__":
    test_intelligent_recommendation()