"""
推荐算法模块 - 包含所有深度学习算法实现

结构：
- deep_base.py: 基础深度学习模块（多头注意力、多模态融合）
- deep_ncf.py: 神经协同过滤
- deep_gcn.py: 图神经网络（GCN/GAT）
- deep_ranking.py: 深度排序模型
- train_deep_models.py: 模型训练脚本
- auto_train.py: 自动训练管理器（离线预训练）
- online_learning.py: 在线学习模块（实时反馈）
- light_models.py: 轻量级模型（资源受限环境）
"""

from .deep_base import MultiHeadAttention, MultimodalFusion, LearnableBlend
from .deep_ncf import NeuralCollaborativeFiltering, NeuralPreferenceNet, NCFModelWrapper
from .deep_gcn import DeepGCNModel, DeepGATModel, GraphRecommender
from .deep_ranking import DeepRankingModel, CandidateReranker
from .auto_train import AutoTrainManager, AdvancedTrainer, auto_train_all_models, setup_auto_training_on_startup, auto_train_manager
from .online_learning import (
    OnlineLearner, 
    RealTimeFeedbackEngine, 
    IncrementalModelUpdater,
    init_real_time_feedback,
    submit_feedback,
    BehaviorDrivenParameterTuner,
    behavior_tuner,
    real_time_feedback_engine
)
from .light_models import (
    LightweightAttention,
    LightweightGCN,
    LightweightMultimodalFusion,
    LightweightNCF,
    LightReinforcementLearner,
    ResourceEfficientTrainer,
    LightRLTrainer,
    LightModelFactory,
    init_light_trainer,
    get_device_info
)

__all__ = [
    # 基础模块
    'MultiHeadAttention',
    'MultimodalFusion', 
    'LearnableBlend',
    
    # NCF模块
    'NeuralCollaborativeFiltering',
    'NeuralPreferenceNet',
    'NCFModelWrapper',
    
    # GCN模块
    'DeepGCNModel',
    'DeepGATModel',
    'GraphRecommender',
    
    # 排序模块
    'DeepRankingModel',
    'CandidateReranker',
    
    # 离线自动训练模块
    'AutoTrainManager',
    'AdvancedTrainer',
    'auto_train_all_models',
    'setup_auto_training_on_startup',
    'auto_train_manager',
    
    # 在线学习模块（实时反馈）
    'OnlineLearner',
    'RealTimeFeedbackEngine',
    'IncrementalModelUpdater',
    'init_real_time_feedback',
    'submit_feedback',
    'BehaviorDrivenParameterTuner',
    'behavior_tuner',
    'real_time_feedback_engine',
    
    # 轻量级模型（GPU支持、资源受限环境）
    'LightweightAttention',
    'LightweightGCN',
    'LightweightMultimodalFusion',
    'LightweightNCF',
    'LightReinforcementLearner',
    'ResourceEfficientTrainer',
    'LightRLTrainer',
    'LightModelFactory',
    'init_light_trainer',
    'get_device_info'
]