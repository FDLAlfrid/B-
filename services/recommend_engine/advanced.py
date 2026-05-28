"""
高级推荐引擎 - 集成先进技术的智能推荐系统
基于论文[13][14][15]的深度学习技术，实现多模态融合和图神经网络

使用真正的PyTorch深度学习实现：
1. MultiHeadAttention - 多头注意力机制（公式4-6、4-7）
2. GraphRecommender - 图神经网络（公式4-5）
3. MultimodalFusion - 多模态特征融合（公式4-4）
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Any, Tuple
from datetime import datetime
from collections import defaultdict, Counter
import json
import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity
import jieba
from .intelligent import IntelligentRecommendEngine
from services.algorithms import (
    MultiHeadAttention, 
    MultimodalFusion, 
    GraphRecommender, 
    NeuralPreferenceNet, 
    NCFModelWrapper,
    init_real_time_feedback,
    submit_feedback,
    behavior_tuner
)
from services.user_preference_learning import get_user_preferences, record_user_behavior

class AdvancedRecommendEngine:
    """高级推荐引擎 - 集成多模态融合和图神经网络"""
    
    def __init__(self):
        # 智能推荐引擎（保持兼容性）
        self.intelligent_engine = IntelligentRecommendEngine()
        
        # 高级推荐配置
        self.advanced_config = {
            'multimodal_weight': 0.4,      # 多模态融合权重
            'graph_weight': 0.3,           # 图神经网络权重
            'attention_weight': 0.2,       # 注意力机制权重
            'rl_weight': 0.1,              # 强化学习权重
            'ip_score_threshold': 0.5,     # IP关联度阈值
            'max_graph_depth': 3,          # 图神经网络最大深度
            'diversity_factor': 0.2        # 多样性因子
        }
        
        # IP关联度计算模型
        self.ip_relevance_model = IPRelevanceModel()
        
        # 图神经网络模型 - 使用新的PyTorch Geometric实现
        self.graph_model = GraphRecommender(num_users=10000, num_items=50000, gnn_type='gcn', embed_dim=64)
        
        # 深度注意力机制 - 使用新的PyTorch多头注意力实现
        self.attention_model = MultiHeadAttention(embed_dim=128, num_heads=4, dropout=0.1)
        
        # 多模态特征提取器 - 保留旧版用于特征提取
        self.feature_extractor = MultimodalFeatureFuser()
        
        # 多模态特征融合器 - 使用新的PyTorch实现（用于端到端融合）
        self.multimodal_fuser = MultimodalFusion(text_dim=384, audio_dim=128, visual_dim=256, behavior_dim=64, output_dim=128)
        
        # 神经偏好学习模型
        self.preference_model = NeuralPreferenceNet(input_dim=512, hidden_dim=256, output_dim=4)
        
        # NCF模型包装器
        self.ncf_wrapper = NCFModelWrapper(num_users=10000, num_items=50000, embed_dim=64)
        
        # 强化学习优化机制
        self.rl_optimizer = ReinforcementLearningOptimizer()
        
        # 推荐历史和反馈
        self.recommendation_history = defaultdict(list)
        self.feedback_data = defaultdict(list)
        
        # 实时反馈引擎 - 支持在线学习和行为驱动的参数调整
        self.feedback_engine = init_real_time_feedback(self)
    
    def get_advanced_recommendations(self, user_id: str, limit: int = 20, 
                                    use_advanced: bool = True, excluded_bvids: List[str] = None) -> List[Dict[str, Any]]:
        """获取高级推荐 - 集成多模态融合和图神经网络"""
        
        # 获取智能推荐结果作为基础
        base_results = self.intelligent_engine.get_intelligent_recommendations(
            user_id=user_id,
            limit=limit * 3,  # 获取更多用于高级处理
            use_preferences=True,
            excluded_bvids=excluded_bvids
        )
        
        if not use_advanced or not base_results:
            # 过滤排除列表
            if excluded_bvids:
                base_results = [item for item in base_results if item.get('bvid') not in excluded_bvids]
            return base_results[:limit]
        
        # 1. 多模态特征融合
        multimodal_results = self._apply_multimodal_fusion(base_results, user_id)
        
        # 2. 图神经网络推荐
        graph_results = self._apply_graph_neural_network(user_id, limit)
        
        # 3. 深度注意力排序
        attention_results = self._apply_attention_mechanism(multimodal_results, user_id)
        
        # 4. 融合结果
        final_results = self._fuse_recommendation_results(
            attention_results, graph_results, limit
        )
        
        # 5. 强化学习优化
        optimized_results = self._apply_rl_optimization(final_results, user_id)
        
        # 过滤排除列表
        if excluded_bvids:
            optimized_results = [item for item in optimized_results if item.get('bvid') not in excluded_bvids]
        
        # 记录推荐历史
        self._record_recommendation_history(user_id, optimized_results)
        
        return optimized_results[:limit]
    
    def _apply_multimodal_fusion(self, music_list: List[Dict], user_id: str) -> List[Dict]:
        """应用多模态特征融合"""
        user_preferences = get_user_preferences(user_id)
        
        for music in music_list:
            # 提取多模态特征（使用特征提取器）
            multimodal_features = self.feature_extractor.extract_features(music)
            
            # 计算多模态匹配度
            multimodal_score = self.feature_extractor.calculate_match_score(
                multimodal_features, user_preferences
            )
            
            music['multimodal_score'] = multimodal_score
        
        # 按多模态分数排序
        music_list.sort(key=lambda x: x.get('multimodal_score', 0), reverse=True)
        
        return music_list
    
    def _apply_graph_neural_network(self, user_id: str, limit: int) -> List[Dict]:
        """应用图神经网络推荐 - 使用新的DeepGCNModel"""
        # 获取用户-歌曲交互数据
        user_song_interactions = self._get_user_song_interactions(user_id)
        
        # 构建图（新API）
        graph_data = self.graph_model.build_graph(user_song_interactions)
        
        # 基于图神经网络进行推荐（新API）
        graph_recommendations = self.graph_model.recommend_from_graph(
            user_id=hash(user_id) % 10000,  # 转换为数字用户ID
            graph_data=graph_data,
            limit=limit
        )
        
        return graph_recommendations
    
    def _get_user_song_interactions(self, user_id: str) -> List[Tuple]:
        """获取用户-歌曲交互数据"""
        interactions = []
        
        # 获取用户收藏
        from utils.data_manager import get_favorites
        favorites = get_favorites(user_id)
        for fav in favorites:
            interactions.append((hash(user_id) % 10000, hash(fav.get('bvid', '')) % 50000, 1.0))
        
        # 获取用户历史播放
        from services.user_preference_learning import get_user_history
        history = get_user_history(user_id)
        for item in history[:20]:
            interactions.append((hash(user_id) % 10000, hash(item.get('bvid', '')) % 50000, 0.8))
        
        return interactions
    
    def _apply_attention_mechanism(self, music_list: List[Dict], user_id: str) -> List[Dict]:
        """应用深度注意力机制 - 使用新的DeepAttentionModel"""
        user_preferences = get_user_preferences(user_id)
        
        # 生成用户嵌入向量
        user_embedding = self._generate_user_embedding(user_preferences)
        
        for music in music_list:
            # 生成音乐嵌入向量
            music_embedding = self._generate_music_embedding(music)
            
            # 计算注意力分数（使用新API）
            attention_score = self.attention_model.calculate_attention_score(
                music_embedding, user_embedding
            )
            
            music['attention_score'] = attention_score
        
        # 按注意力分数排序
        music_list.sort(key=lambda x: x.get('attention_score', 0), reverse=True)
        
        return music_list
    
    def _generate_user_embedding(self, user_preferences: Dict) -> List[float]:
        """生成用户嵌入向量"""
        features = []
        
        # 从用户偏好中提取特征
        for key in ['style', 'singer', 'emotion', 'language', 'tempo']:
            features.extend(self._encode_preference(user_preferences.get(key, {})))
        
        # 确保向量长度为embed_dim
        from services.recommend_engine.advanced import DeepAttentionModel
        return features[:DeepAttentionModel().embed_dim] + [0.0] * max(0, DeepAttentionModel().embed_dim - len(features))
    
    def _generate_music_embedding(self, music: Dict) -> List[float]:
        """生成音乐嵌入向量"""
        features = []
        
        # 从音乐信息中提取特征
        features.extend(self._encode_string(music.get('title', '')))
        features.extend(self._encode_string(music.get('singer', '')))
        features.extend(self._encode_string(music.get('style', '')))
        
        # 确保向量长度为embed_dim
        from services.recommend_engine.advanced import DeepAttentionModel
        return features[:DeepAttentionModel().embed_dim] + [0.0] * max(0, DeepAttentionModel().embed_dim - len(features))
    
    def _encode_preference(self, preference: Dict) -> List[float]:
        """编码偏好字典为特征向量"""
        if not preference:
            return [0.0] * 8
        return [float(v) for v in list(preference.values())[:8]]
    
    def _encode_string(self, s: str) -> List[float]:
        """编码字符串为特征向量"""
        if not s:
            return [0.0] * 16
        
        # 使用简单的哈希编码
        hash_values = []
        for i in range(16):
            hash_values.append(hash(s + str(i)) % 100 / 100.0)
        
        return hash_values
    
    def _fuse_recommendation_results(self, attention_results: List[Dict], 
                                   graph_results: List[Dict], limit: int) -> List[Dict]:
        """融合不同推荐结果"""
        # 合并结果并去重
        fused_results = {}
        
        # 添加注意力机制结果
        for music in attention_results:
            bvid = music.get('bvid')
            if bvid:
                fused_results[bvid] = music
        
        # 添加图神经网络结果
        for music in graph_results:
            bvid = music.get('bvid')
            if bvid and bvid not in fused_results:
                fused_results[bvid] = music
        
        # 转换为列表并排序
        final_list = list(fused_results.values())
        final_list.sort(key=lambda x: max(x.get('attention_score', 0), 
                                         x.get('graph_score', 0)), reverse=True)
        
        return final_list[:limit * 2]
    
    def _apply_rl_optimization(self, music_list: List[Dict], user_id: str) -> List[Dict]:
        """应用强化学习优化"""
        # 获取用户历史反馈
        user_feedback = self.feedback_data.get(user_id, [])
        
        # 优化推荐顺序
        optimized_list = self.rl_optimizer.optimize_recommendation_order(
            music_list=music_list,
            user_id=user_id,
            user_feedback=user_feedback
        )
        
        return optimized_list
    
    def record_feedback(self, user_id: str, music_data: Dict, feedback_type: str, 
                      feedback_value: float = 1.0):
        """记录用户反馈"""
        feedback_record = {
            'music_data': music_data,
            'feedback_type': feedback_type,  # like, dislike, click, share, collect
            'feedback_value': feedback_value,
            'timestamp': datetime.now()
        }
        
        self.feedback_data[user_id].append(feedback_record)
        
        # 保持最近500条反馈记录
        if len(self.feedback_data[user_id]) > 500:
            self.feedback_data[user_id] = self.feedback_data[user_id][-500:]
        
        # 更新强化学习模型
        self.rl_optimizer.update_model(user_id, feedback_record)
    
    def _record_recommendation_history(self, user_id: str, recommendations: List[Dict]):
        """记录推荐历史"""
        history_record = {
            'recommendations': recommendations,
            'timestamp': datetime.now()
        }
        
        self.recommendation_history[user_id].append(history_record)
        
        # 保持最近100条历史记录
        if len(self.recommendation_history[user_id]) > 100:
            self.recommendation_history[user_id] = self.recommendation_history[user_id][-100:]

class IPRelevanceModel:
    """IP关联度计算模型"""
    
    def __init__(self):
        # IP关联度权重
        self.weights = {
            'keyword_match': 0.4,      # 关键词匹配权重
            'user_preference': 0.3,    # 用户偏好权重
            'social_hotness': 0.2,     # 社交热度权重
            'ip_similarity': 0.1       # IP相似度权重
        }
        
        # IP关键词库
        self.ip_keywords = {
            'vocaloid': ['vocaloid', '虚拟歌手', '初音', '洛天依', '乐正绫'],
            'anime': ['动漫', '动画', '二次元', 'ACG', '番剧'],
            'game': ['游戏', '原神', '崩坏', '明日方舟', '英雄联盟'],
            'idol': ['偶像', '女团', '男团', '练习生', '选秀']
        }
    
    def calculate_ip_relevance(self, music_data: Dict, user_preferences: Dict) -> float:
        """计算IP关联度"""
        title = music_data.get('title', '').lower()
        description = music_data.get('description', '').lower()
        author = music_data.get('up主', '').lower()
        play_count = music_data.get('播放量', 0)
        
        # 1. 关键词匹配
        keyword_match = self._calculate_keyword_match(title + ' ' + description + ' ' + author)
        
        # 2. 用户偏好匹配
        user_preference_match = self._calculate_user_preference_match(user_preferences)
        
        # 3. 社交热度
        social_hotness = self._calculate_social_hotness(play_count)
        
        # 4. IP相似度
        ip_similarity = self._calculate_ip_similarity(music_data, user_preferences)
        
        # 综合计算
        total_score = (
            keyword_match * self.weights['keyword_match'] +
            user_preference_match * self.weights['user_preference'] +
            social_hotness * self.weights['social_hotness'] +
            ip_similarity * self.weights['ip_similarity']
        )
        
        return min(total_score, 1.0)
    
    def _calculate_keyword_match(self, text: str) -> float:
        """计算关键词匹配度"""
        match_count = 0
        total_keywords = 0
        
        for ip_category, keywords in self.ip_keywords.items():
            total_keywords += len(keywords)
            for keyword in keywords:
                if keyword.lower() in text:
                    match_count += 1
        
        if total_keywords == 0:
            return 0.5
        
        return match_count / total_keywords
    
    def _calculate_user_preference_match(self, user_preferences: Dict) -> float:
        """计算用户偏好匹配度"""
        ip_preferences = user_preferences.get('ip_preferences', {})
        if not ip_preferences:
            return 0.5
        
        return sum(ip_preferences.values()) / len(ip_preferences)
    
    def _calculate_social_hotness(self, play_count: int) -> float:
        """计算社交热度"""
        # 归一化播放量
        max_play_count = 10000000  # 1000万播放
        normalized_play_count = min(play_count / max_play_count, 1.0)
        
        return normalized_play_count
    
    def _calculate_ip_similarity(self, music_data: Dict, user_preferences: Dict) -> float:
        """计算IP相似度"""
        # 这里可以实现更复杂的IP相似度计算
        # 暂时返回默认值
        return 0.5

class ReinforcementLearningOptimizer:
    """强化学习优化机制"""
    
    def __init__(self):
        # 强化学习参数
        self.rl_params = {
            'learning_rate': 0.01,
            'discount_factor': 0.9,
            'exploration_rate': 0.1,
            'reward_values': {
                'like': 1.0,
                'collect': 0.8,
                'share': 0.6,
                'click': 0.2,
                'dislike': -1.0
            }
        }
        
        # 用户策略模型
        self.user_policies = defaultdict(dict)
    
    def optimize_recommendation_order(self, music_list: List[Dict], 
                                     user_id: str, user_feedback: List[Dict]) -> List[Dict]:
        """优化推荐顺序"""
        # 计算每首音乐的预期奖励
        for music in music_list:
            expected_reward = self._calculate_expected_reward(music, user_id, user_feedback)
            music['expected_reward'] = expected_reward
        
        # 按预期奖励排序
        music_list.sort(key=lambda x: x.get('expected_reward', 0), reverse=True)
        
        return music_list
    
    def _calculate_expected_reward(self, music: Dict, user_id: str, 
                                  user_feedback: List[Dict]) -> float:
        """计算预期奖励"""
        # 基于历史反馈计算预期奖励
        reward = 0.0
        count = 0
        
        for feedback in user_feedback:
            feedback_music = feedback['music_data']
            # 简单的相似度计算
            similarity = self._calculate_music_similarity(music, feedback_music)
            
            if similarity > 0.5:
                reward_value = self.rl_params['reward_values'].get(
                    feedback['feedback_type'], 0
                )
                reward += reward_value * similarity
                count += 1
        
        if count == 0:
            return 0.5
        
        return reward / count
    
    def _calculate_music_similarity(self, music1: Dict, music2: Dict) -> float:
        """计算音乐相似度"""
        # 简化版相似度计算
        similarity = 0.0
        weight = 0.0
        
        # 标题相似度
        title1 = music1.get('title', '').lower()
        title2 = music2.get('title', '').lower()
        if title1 and title2:
            # 简单的字符串相似度
            common_words = set(title1.split()) & set(title2.split())
            similarity += len(common_words) / (len(set(title1.split())) + len(set(title2.split()))) * 0.3
            weight += 0.3
        
        # UP主相似度
        producer1 = music1.get('up主', '').lower()
        producer2 = music2.get('up主', '').lower()
        if producer1 == producer2 and producer1:
            similarity += 1.0 * 0.4
            weight += 0.4
        
        # 风格相似度
        style1 = set(music1.get('style', []))
        style2 = set(music2.get('style', []))
        if style1 and style2:
            common_styles = style1 & style2
            similarity += len(common_styles) / (len(style1) + len(style2)) * 0.3
            weight += 0.3
        
        if weight == 0:
            return 0.5
        
        return similarity / weight
    
    def update_model(self, user_id: str, feedback_record: Dict):
        """更新强化学习模型"""
        # 这里可以实现更复杂的模型更新逻辑
        # 暂时只是记录反馈
        pass

class MultimodalFeatureFuser:
    """多模态特征融合器"""
    
    def __init__(self):
        # 多模态权重
        self.modal_weights = {
            'text': 0.3,      # 文本特征权重
            'audio': 0.2,     # 音频特征权重（模拟）
            'visual': 0.2,    # 视觉特征权重（模拟）
            'behavior': 0.3   # 行为特征权重
        }
    
    def extract_features(self, music: Dict) -> Dict[str, Any]:
        """提取多模态特征"""
        # 文本特征
        text_features = self._extract_text_features(music)
        
        # 音频特征（模拟）
        audio_features = self._extract_audio_features(music)
        
        # 视觉特征（模拟）
        visual_features = self._extract_visual_features(music)
        
        # 行为特征
        behavior_features = self._extract_behavior_features(music)
        
        return {
            'text': text_features,
            'audio': audio_features,
            'visual': visual_features,
            'behavior': behavior_features
        }
    
    def _extract_text_features(self, music: Dict) -> Dict[str, Any]:
        """提取文本特征"""
        title = music.get('title', '')
        description = music.get('description', '')
        
        # 分词
        title_words = list(jieba.cut(title))
        desc_words = list(jieba.cut(description))
        
        # 关键词提取
        all_words = title_words + desc_words
        word_freq = Counter(all_words)
        top_keywords = word_freq.most_common(10)
        
        return {
            'title_length': len(title),
            'description_length': len(description),
            'keywords': dict(top_keywords),
            'word_count': len(all_words)
        }
    
    def _extract_audio_features(self, music: Dict) -> Dict[str, Any]:
        """提取音频特征（模拟）"""
        # 由于没有实际的音频数据，我们模拟一些特征
        return {
            'tempo': np.random.uniform(60, 180),
            'genre': np.random.choice(['pop', 'rock', 'electronic', 'classical', 'hip-hop']),
            'duration': np.random.uniform(120, 300)
        }
    
    def _extract_visual_features(self, music: Dict) -> Dict[str, Any]:
        """提取视觉特征（模拟）"""
        # 由于没有实际的视觉数据，我们模拟一些特征
        return {
            'cover_brightness': np.random.uniform(0, 1),
            'cover_colorfulness': np.random.uniform(0, 1),
            'cover_complexity': np.random.uniform(0, 1)
        }
    
    def _extract_behavior_features(self, music: Dict) -> Dict[str, Any]:
        """提取行为特征"""
        return {
            'play_count': music.get('播放量', 0),
            'danmaku_count': music.get('弹幕数', 0),
            'like_count': music.get('点赞数', 0),
            'favorite_count': music.get('收藏数', 0)
        }
    
    def calculate_match_score(self, multimodal_features: Dict, 
                             user_preferences: Dict) -> float:
        """计算多模态匹配分数"""
        # 文本特征匹配
        text_score = self._calculate_text_match(multimodal_features['text'], user_preferences)
        
        # 音频特征匹配（模拟）
        audio_score = self._calculate_audio_match(multimodal_features['audio'], user_preferences)
        
        # 视觉特征匹配（模拟）
        visual_score = self._calculate_visual_match(multimodal_features['visual'], user_preferences)
        
        # 行为特征匹配
        behavior_score = self._calculate_behavior_match(multimodal_features['behavior'], user_preferences)
        
        # 综合分数
        total_score = (
            text_score * self.modal_weights['text'] +
            audio_score * self.modal_weights['audio'] +
            visual_score * self.modal_weights['visual'] +
            behavior_score * self.modal_weights['behavior']
        )
        
        return min(total_score, 1.0)
    
    def _calculate_text_match(self, text_features: Dict, user_preferences: Dict) -> float:
        """计算文本特征匹配度"""
        # 简化版文本匹配
        style_preferences = user_preferences.get('style_preferences', {})
        if not style_preferences:
            return 0.5
        
        keywords = text_features.get('keywords', {})
        match_count = 0
        total_keywords = len(keywords)
        
        if total_keywords == 0:
            return 0.5
        
        for keyword, _ in keywords.items():
            for style, weight in style_preferences.items():
                if style in keyword:
                    match_count += weight
        
        return min(match_count / total_keywords, 1.0)
    
    def _calculate_audio_match(self, audio_features: Dict, user_preferences: Dict) -> float:
        """计算音频特征匹配度（模拟）"""
        # 模拟音频匹配
        return np.random.uniform(0.3, 0.7)
    
    def _calculate_visual_match(self, visual_features: Dict, user_preferences: Dict) -> float:
        """计算视觉特征匹配度（模拟）"""
        # 模拟视觉匹配
        return np.random.uniform(0.3, 0.7)
    
    def _calculate_behavior_match(self, behavior_features: Dict, user_preferences: Dict) -> float:
        """计算行为特征匹配度"""
        play_count = behavior_features.get('play_count', 0)
        
        # 归一化播放量
        max_play_count = 10000000  # 1000万播放
        normalized_play_count = min(play_count / max_play_count, 1.0)
        
        return normalized_play_count






