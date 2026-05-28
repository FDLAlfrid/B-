"""
在线学习模块 - 支持实时用户反馈和增量模型更新

功能：
1. 实时收集用户行为反馈
2. 在线模型更新（增量学习）
3. 自适应参数调整
4. 强化学习策略更新
5. 多模态反馈融合
"""

import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import json
import os
from collections import defaultdict
from typing import List, Dict, Any, Tuple, Optional


class OnlineLearner:
    """在线学习器 - 支持实时用户反馈"""
    
    def __init__(self, model: nn.Module = None, learning_rate: float = 0.001, 
                 device: str = 'auto'):
        """
        初始化在线学习器
        
        :param model: 要更新的模型
        :param learning_rate: 学习率
        :param device: 设备
        """
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu') if device == 'auto' else torch.device(device)
        
        self.model = model
        if model:
            self.model.to(self.device)
            self.optimizer = optim.Adam(model.parameters(), lr=learning_rate)
            self.criterion = nn.MSELoss()
        
        # 反馈缓冲区
        self.feedback_buffer = []
        self.buffer_size = 100
        
        # 学习状态
        self.training_steps = 0
        self.last_update_time = 0
        
        # 自适应学习率
        self.base_lr = learning_rate
        self.adaptive_lr = learning_rate
        
        # 反馈统计
        self.feedback_stats = defaultdict(lambda: defaultdict(int))
        
        # 奖励权重（可学习）
        self.reward_weights = nn.Parameter(torch.tensor([1.0, 0.8, 0.6, 0.2, -1.0]))
        
        # 特征归一化参数
        self.feature_mean = None
        self.feature_std = None
    
    def collect_feedback(self, user_id: str, item_id: str, feedback_type: str, 
                        features: Dict = None, timestamp: float = None):
        """
        收集用户反馈
        
        :param user_id: 用户ID
        :param item_id: 物品ID
        :param feedback_type: 反馈类型 (like, collect, share, click, dislike)
        :param features: 特征数据
        :param timestamp: 时间戳
        """
        feedback = {
            'user_id': user_id,
            'item_id': item_id,
            'feedback_type': feedback_type,
            'features': features or {},
            'timestamp': timestamp or self._get_timestamp()
        }
        
        self.feedback_buffer.append(feedback)
        self.feedback_stats[user_id][feedback_type] += 1
        
        # 缓冲区满时触发在线更新
        if len(self.feedback_buffer) >= self.buffer_size:
            self.update_online()
    
    def _get_timestamp(self) -> float:
        """获取当前时间戳"""
        import time
        return time.time()
    
    def update_online(self):
        """在线更新模型"""
        if not self.model or not self.feedback_buffer:
            return
        
        self.model.train()
        
        # 处理反馈数据
        for feedback in self.feedback_buffer:
            self.optimizer.zero_grad()
            
            # 提取特征
            features = feedback['features']
            reward = self._get_reward(feedback['feedback_type'])
            
            # 转换为张量
            feature_tensor = self._features_to_tensor(features)
            
            # 前向传播
            output = self.model(feature_tensor)
            
            # 计算损失（基于奖励的损失）
            target = torch.tensor([reward], dtype=torch.float32, device=self.device)
            loss = self.criterion(output, target)
            
            # 反向传播
            loss.backward()
            self.optimizer.step()
            
            self.training_steps += 1
        
        # 清空缓冲区
        self.feedback_buffer = []
        self.last_update_time = self._get_timestamp()
        
        # 自适应调整学习率
        self._adjust_learning_rate()
    
    def _get_reward(self, feedback_type: str) -> float:
        """获取反馈对应的奖励值"""
        reward_map = {
            'like': float(self.reward_weights[0].item()),
            'collect': float(self.reward_weights[1].item()),
            'share': float(self.reward_weights[2].item()),
            'click': float(self.reward_weights[3].item()),
            'dislike': float(self.reward_weights[4].item())
        }
        return reward_map.get(feedback_type, 0.0)
    
    def _features_to_tensor(self, features: Dict) -> torch.Tensor:
        """将特征字典转换为张量"""
        feature_list = []
        
        # 数值特征
        for key in ['play_count', 'like_count', 'share_count', 'duration']:
            feature_list.append(features.get(key, 0.0))
        
        # 分类特征（使用哈希编码）
        for key in ['style', 'producer', 'emotion']:
            value = features.get(key, '')
            feature_list.append(hash(value) % 100 / 100.0)
        
        # 用户特征
        for key in ['user_age', 'user_gender', 'user_activity']:
            feature_list.append(features.get(key, 0.0))
        
        # 归一化
        if self.feature_mean is not None:
            feature_list = [(f - self.feature_mean[i]) / (self.feature_std[i] + 1e-8) 
                          for i, f in enumerate(feature_list)]
        
        return torch.tensor(feature_list, dtype=torch.float32, device=self.device).unsqueeze(0)
    
    def _adjust_learning_rate(self):
        """自适应调整学习率"""
        # 根据反馈多样性调整学习率
        feedback_types = set(f['feedback_type'] for f in self.feedback_buffer)
        diversity = len(feedback_types) / 5  # 5种反馈类型
        
        # 如果反馈多样化，增大学习率
        self.adaptive_lr = self.base_lr * (1 + diversity)
        
        # 更新优化器学习率
        for param_group in self.optimizer.param_groups:
            param_group['lr'] = self.adaptive_lr
    
    def update_reward_weights(self, feedback_summary: Dict):
        """更新奖励权重"""
        # 根据反馈分布调整奖励权重
        total_feedbacks = sum(feedback_summary.values())
        if total_feedbacks == 0:
            return
        
        # 更多dislike意味着需要增大惩罚
        dislike_ratio = feedback_summary.get('dislike', 0) / total_feedbacks
        if dislike_ratio > 0.3:
            self.reward_weights[4] = torch.clamp(self.reward_weights[4] * 1.1, -2.0, -0.5)
    
    def get_feedback_summary(self, user_id: Optional[str] = None) -> Dict:
        """获取反馈统计摘要"""
        if user_id:
            return dict(self.feedback_stats.get(user_id, {}))
        else:
            # 全局统计
            global_stats = defaultdict(int)
            for user_stats in self.feedback_stats.values():
                for feedback_type, count in user_stats.items():
                    global_stats[feedback_type] += count
            return dict(global_stats)


class RealTimeFeedbackEngine:
    """实时反馈引擎 - 整合在线学习和推荐"""
    
    def __init__(self, recommend_engine):
        """
        初始化实时反馈引擎
        
        :param recommend_engine: 推荐引擎实例
        """
        self.recommend_engine = recommend_engine
        
        # 在线学习器
        self.online_learner = OnlineLearner()
        
        # 反馈队列
        self.feedback_queue = []
        
        # 模型更新间隔（秒）
        self.update_interval = 60
        
        # 上次更新时间
        self.last_update = 0
        
        # 自适应权重调整
        self.adaptive_weights = {
            'multimodal': 0.4,
            'graph': 0.3,
            'attention': 0.2,
            'rl': 0.1
        }
    
    def process_feedback(self, feedback: Dict):
        """
        处理用户反馈
        
        :param feedback: 反馈数据 {'user_id', 'item_id', 'feedback_type', 'context'}
        """
        user_id = feedback['user_id']
        item_id = feedback['item_id']
        feedback_type = feedback['feedback_type']
        context = feedback.get('context', {})
        
        # 收集到在线学习器
        self.online_learner.collect_feedback(
            user_id=user_id,
            item_id=item_id,
            feedback_type=feedback_type,
            features=context.get('features', {})
        )
        
        # 更新强化学习模型
        self.recommend_engine.rl_optimizer.update_model(user_id, feedback)
        
        # 自适应调整推荐权重
        self._adapt_recommendation_weights(feedback)
    
    def _adapt_recommendation_weights(self, feedback: Dict):
        """根据反馈自适应调整推荐权重"""
        feedback_type = feedback['feedback_type']
        
        # 根据反馈类型调整权重
        if feedback_type in ['like', 'collect', 'share']:
            # 正向反馈，增加相关模块权重
            self.adaptive_weights['rl'] = min(0.3, self.adaptive_weights['rl'] + 0.01)
            self.adaptive_weights['multimodal'] = max(0.2, self.adaptive_weights['multimodal'] - 0.005)
        elif feedback_type == 'dislike':
            # 负向反馈，减少相关模块权重，增加探索
            self.adaptive_weights['rl'] = max(0.05, self.adaptive_weights['rl'] - 0.01)
            self.adaptive_weights['graph'] = min(0.4, self.adaptive_weights['graph'] + 0.01)
        
        # 归一化权重
        total = sum(self.adaptive_weights.values())
        for key in self.adaptive_weights:
            self.adaptive_weights[key] /= total
        
        # 更新推荐引擎配置
        self.recommend_engine.advanced_config.update(self.adaptive_weights)
    
    def update_models_periodically(self):
        """定期更新模型"""
        import time
        current_time = time.time()
        
        if current_time - self.last_update >= self.update_interval:
            self._update_all_models()
            self.last_update = current_time
    
    def _update_all_models(self):
        """更新所有模型"""
        # 1. 更新在线学习器
        self.online_learner.update_online()
        
        # 2. 更新强化学习策略
        feedback_summary = self.online_learner.get_feedback_summary()
        self.online_learner.update_reward_weights(feedback_summary)
        
        # 3. 保存更新后的模型
        self._save_models()
    
    def _save_models(self):
        """保存模型"""
        model_dir = os.path.join(os.path.dirname(__file__), 'models')
        os.makedirs(model_dir, exist_ok=True)
        
        # 保存奖励权重
        torch.save(self.online_learner.reward_weights, 
                   os.path.join(model_dir, 'reward_weights.pt'))
        
        # 保存自适应权重
        with open(os.path.join(model_dir, 'adaptive_weights.json'), 'w') as f:
            json.dump(self.adaptive_weights, f)
    
    def load_adaptive_weights(self):
        """加载自适应权重"""
        weight_path = os.path.join(os.path.dirname(__file__), 'models', 'adaptive_weights.json')
        if os.path.exists(weight_path):
            with open(weight_path, 'r') as f:
                self.adaptive_weights = json.load(f)


class IncrementalModelUpdater:
    """增量模型更新器"""
    
    def __init__(self, base_model: nn.Module, update_frequency: int = 100):
        """
        初始化增量更新器
        
        :param base_model: 基础模型
        :param update_frequency: 更新频率（每N条反馈更新一次）
        """
        self.base_model = base_model
        self.update_frequency = update_frequency
        self.update_count = 0
        
        # 累积梯度
        self.accumulated_grads = {}
        
    def accumulate_gradient(self, loss: torch.Tensor):
        """累积梯度"""
        loss.backward(retain_graph=True)
        
        for name, param in self.base_model.named_parameters():
            if param.grad is not None:
                if name not in self.accumulated_grads:
                    self.accumulated_grads[name] = torch.zeros_like(param.grad)
                self.accumulated_grads[name] += param.grad
        
        self.update_count += 1
        
        # 达到更新频率时应用更新
        if self.update_count >= self.update_frequency:
            self.apply_update()
    
    def apply_update(self):
        """应用累积的更新"""
        if not self.accumulated_grads:
            return
        
        # 使用累积梯度更新参数
        optimizer = optim.SGD(self.base_model.parameters(), lr=0.001)
        optimizer.zero_grad()
        
        for name, param in self.base_model.named_parameters():
            if name in self.accumulated_grads:
                param.grad = self.accumulated_grads[name] / self.update_count
        
        optimizer.step()
        
        # 重置累积梯度
        self.accumulated_grads = {}
        self.update_count = 0


# 全局实时反馈引擎实例
real_time_feedback_engine = None


def init_real_time_feedback(recommend_engine):
    """
    初始化实时反馈引擎
    
    :param recommend_engine: 推荐引擎实例
    :return: 反馈引擎实例
    """
    global real_time_feedback_engine
    real_time_feedback_engine = RealTimeFeedbackEngine(recommend_engine)
    return real_time_feedback_engine


def submit_feedback(user_id: str, item_id: str, feedback_type: str, context: Dict = None):
    """
    提交用户反馈（便捷接口）
    
    :param user_id: 用户ID
    :param item_id: 物品ID
    :param feedback_type: 反馈类型
    :param context: 上下文信息
    """
    if real_time_feedback_engine:
        feedback = {
            'user_id': user_id,
            'item_id': item_id,
            'feedback_type': feedback_type,
            'context': context or {}
        }
        real_time_feedback_engine.process_feedback(feedback)


class BehaviorDrivenParameterTuner:
    """行为驱动的参数调优器"""
    
    def __init__(self):
        # 参数范围
        self.param_ranges = {
            'learning_rate': (0.0001, 0.01),
            'exploration_rate': (0.01, 0.3),
            'discount_factor': (0.8, 0.99),
            'temperature': (0.5, 2.0)
        }
        
        # 当前参数
        self.current_params = {
            'learning_rate': 0.001,
            'exploration_rate': 0.1,
            'discount_factor': 0.9,
            'temperature': 1.0
        }
        
        # 性能历史
        self.performance_history = []
        
    def tune_based_on_behavior(self, behavior_metrics: Dict):
        """
        根据用户行为指标调整参数
        
        :param behavior_metrics: 行为指标 {'engagement_rate', 'diversity', 'satisfaction'}
        """
        engagement_rate = behavior_metrics.get('engagement_rate', 0.5)
        diversity = behavior_metrics.get('diversity', 0.5)
        satisfaction = behavior_metrics.get('satisfaction', 0.5)
        
        # 根据参与度调整学习率
        if engagement_rate < 0.3:
            # 低参与度，增大探索
            self.current_params['exploration_rate'] = min(
                self.param_ranges['exploration_rate'][1],
                self.current_params['exploration_rate'] * 1.1
            )
        elif engagement_rate > 0.7:
            # 高参与度，减小探索
            self.current_params['exploration_rate'] = max(
                self.param_ranges['exploration_rate'][0],
                self.current_params['exploration_rate'] * 0.9
            )
        
        # 根据多样性调整温度参数
        if diversity < 0.3:
            # 多样性低，增大温度鼓励探索
            self.current_params['temperature'] = min(
                self.param_ranges['temperature'][1],
                self.current_params['temperature'] * 1.1
            )
        elif diversity > 0.7:
            # 多样性高，减小温度聚焦优质内容
            self.current_params['temperature'] = max(
                self.param_ranges['temperature'][0],
                self.current_params['temperature'] * 0.9
            )
        
        # 根据满意度调整折扣因子
        if satisfaction < 0.3:
            # 低满意度，更关注近期奖励
            self.current_params['discount_factor'] = max(
                self.param_ranges['discount_factor'][0],
                self.current_params['discount_factor'] * 0.95
            )
        elif satisfaction > 0.7:
            # 高满意度，考虑长期奖励
            self.current_params['discount_factor'] = min(
                self.param_ranges['discount_factor'][1],
                self.current_params['discount_factor'] * 1.01
            )
        
        # 记录性能
        self.performance_history.append({
            'metrics': behavior_metrics,
            'params': self.current_params.copy(),
            'timestamp': self._get_timestamp()
        })
        
        return self.current_params
    
    def _get_timestamp(self) -> float:
        """获取时间戳"""
        import time
        return time.time()
    
    def get_param_history(self) -> List[Dict]:
        """获取参数历史"""
        return self.performance_history


# 全局参数调优器
behavior_tuner = BehaviorDrivenParameterTuner()