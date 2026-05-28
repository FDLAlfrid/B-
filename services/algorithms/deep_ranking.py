"""
深度排序模型模块 - 为推荐系统提供排序能力

实现论文中描述的深度排序算法，用于候选重排序
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import List, Dict


class DeepRankingModel(nn.Module):
    """
    深度排序模型
    使用深度学习对候选推荐结果进行重排序
    """
    
    def __init__(self, feature_dim: int = 512, hidden_dim: int = 256):
        super().__init__()
        
        self.rank_net = nn.Sequential(
            nn.Linear(feature_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1)
        )
        
        # 初始化权重
        self._init_weights()
    
    def _init_weights(self):
        """初始化权重"""
        for layer in self.rank_net:
            if isinstance(layer, nn.Linear):
                nn.init.xavier_uniform_(layer.weight)
    
    def forward(self, features: torch.Tensor) -> torch.Tensor:
        """
        前向传播
        :param features: 特征张量 [batch, feature_dim]
        :return: 排序分数 [batch, 1]
        """
        return self.rank_net(features)


class RankingFeatureBuilder:
    """排序特征构建器"""
    
    def __init__(self):
        self.feature_dim = 512
    
    def build_features(self, user_profile: Dict, item_info: Dict, context: Dict = None) -> List[float]:
        """
        构建排序特征向量
        :param user_profile: 用户画像
        :param item_info: 物品信息
        :param context: 上下文信息
        :return: 特征向量
        """
        features = []
        
        # 用户特征 (64维)
        features.extend(self._encode_user_profile(user_profile))
        
        # 物品特征 (128维)
        features.extend(self._encode_item_info(item_info))
        
        # 用户-物品交互特征 (64维)
        features.extend(self._encode_interaction(user_profile, item_info))
        
        # 上下文特征 (32维)
        if context:
            features.extend(self._encode_context(context))
        else:
            features.extend([0.0] * 32)
        
        # 填充或截断到固定维度
        features = features[:self.feature_dim]
        features += [0.0] * max(0, self.feature_dim - len(features))
        
        return features
    
    def _encode_user_profile(self, user_profile: Dict) -> List[float]:
        """编码用户画像"""
        features = []
        
        # 偏好分布 (4维)
        preferences = user_profile.get('preferences', {})
        for key in ['style', 'singer', 'producer', 'emotion']:
            features.append(float(preferences.get(key, 0.0)))
        
        # 活跃度特征 (4维)
        activity = user_profile.get('activity', {})
        for key in ['total_plays', 'total_favorites', 'total_shares', 'avg_session_length']:
            val = activity.get(key, 0)
            features.append(min(val / 1000, 1.0))
        
        # 扩展到64维
        features += [0.0] * (64 - len(features))
        return features[:64]
    
    def _encode_item_info(self, item_info: Dict) -> List[float]:
        """编码物品信息"""
        features = []
        
        # 基础特征
        features.append(float(item_info.get('play_count', 0)) / 1000000)
        features.append(float(item_info.get('like_count', 0)) / 10000)
        features.append(float(item_info.get('favorite_count', 0)) / 10000)
        features.append(float(item_info.get('danmu_count', 0)) / 1000)
        
        # 类别编码 (使用哈希)
        category = item_info.get('category', '')
        for i in range(8):
            features.append(hash(category + str(i)) % 100 / 100.0)
        
        # 风格编码
        style = item_info.get('style', '')
        for i in range(8):
            features.append(hash(style + str(i)) % 100 / 100.0)
        
        # 扩展到128维
        features += [0.0] * (128 - len(features))
        return features[:128]
    
    def _encode_interaction(self, user_profile: Dict, item_info: Dict) -> List[float]:
        """编码用户-物品交互特征"""
        features = []
        
        # 历史交互
        history = user_profile.get('history', [])
        bvid = item_info.get('bvid', '')
        
        # 是否在收藏中
        features.append(1.0 if bvid in user_profile.get('favorites', []) else 0.0)
        
        # 是否在历史播放中
        features.append(1.0 if any(item.get('bvid') == bvid for item in history) else 0.0)
        
        # 播放次数
        play_count = sum(1 for item in history if item.get('bvid') == bvid)
        features.append(min(play_count / 10, 1.0))
        
        # 扩展到64维
        features += [0.0] * (64 - len(features))
        return features[:64]
    
    def _encode_context(self, context: Dict) -> List[float]:
        """编码上下文信息"""
        features = []
        
        # 时间特征
        hour = context.get('hour', 12)
        features.append(hour / 23.0)
        
        # 星期特征
        weekday = context.get('weekday', 0)
        features.append(weekday / 6.0)
        
        # 场景特征
        scene = context.get('scene', '')
        for i in range(8):
            features.append(hash(scene + str(i)) % 100 / 100.0)
        
        # 扩展到32维
        features += [0.0] * (32 - len(features))
        return features[:32]


class CandidateReranker:
    """候选重排序器"""
    
    def __init__(self):
        self.model = DeepRankingModel()
        self.feature_builder = RankingFeatureBuilder()
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model.to(self.device)
        self._load_model()
    
    def _load_model(self):
        """加载预训练模型"""
        import os
        model_path = os.path.join(os.path.dirname(__file__), 'models', 'ranking_model.pt')
        
        if os.path.exists(model_path):
            try:
                self.model.load_state_dict(torch.load(model_path, map_location=self.device))
                self.model.eval()
            except Exception as e:
                print(f"加载排序模型失败: {e}")
    
    def rerank(self, candidates: List[Dict], user_profile: Dict, 
               context: Dict = None, limit: int = 20) -> List[Dict]:
        """
        对候选列表进行重排序
        :param candidates: 候选物品列表
        :param user_profile: 用户画像
        :param context: 上下文信息
        :param limit: 返回数量
        :return: 排序后的候选列表
        """
        if not candidates:
            return []
        
        # 构建特征
        features_list = []
        for item in candidates:
            features = self.feature_builder.build_features(user_profile, item, context)
            features_list.append(features)
        
        # 预测分数
        self.model.eval()
        with torch.no_grad():
            features_tensor = torch.tensor(features_list, dtype=torch.float32, device=self.device)
            scores = self.model(features_tensor)
            scores = scores.squeeze().tolist()
        
        # 排序
        results = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
        return [item for item, score in results[:limit]]