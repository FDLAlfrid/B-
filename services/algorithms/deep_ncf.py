"""
神经协同过滤模块 - 实现NCF模型

实现论文中描述的神经协同过滤算法，包括：
1. GMF（Generalized Matrix Factorization）
2. MLP（Multi-Layer Perceptron）
3. NCF融合模型
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class NeuralCollaborativeFiltering(nn.Module):
    """
    神经协同过滤模型 - NCF
    融合GMF和MLP两种架构
    """
    
    def __init__(self, num_users: int, num_items: int, embed_dim: int = 64, 
                 mlp_layers: list = None, dropout: float = 0.2):
        super().__init__()
        
        self.num_users = num_users
        self.num_items = num_items
        self.embed_dim = embed_dim
        
        # GMF嵌入层
        self.user_gmf_embed = nn.Embedding(num_users, embed_dim)
        self.item_gmf_embed = nn.Embedding(num_items, embed_dim)
        
        # MLP嵌入层（维度更高）
        self.user_mlp_embed = nn.Embedding(num_users, embed_dim * 2)
        self.item_mlp_embed = nn.Embedding(num_items, embed_dim * 2)
        
        # MLP层
        if mlp_layers is None:
            mlp_layers = [256, 128, 64]
        
        mlp_input_dim = embed_dim * 4  # 2*embed_dim (user) + 2*embed_dim (item)
        mlp_layers = [mlp_input_dim] + mlp_layers
        
        self.mlp = nn.ModuleList()
        for i in range(len(mlp_layers) - 1):
            self.mlp.append(nn.Linear(mlp_layers[i], mlp_layers[i+1]))
            self.mlp.append(nn.ReLU())
            self.mlp.append(nn.Dropout(dropout))
        
        # 融合层
        self.fusion_layer = nn.Linear(embed_dim + mlp_layers[-1], 1)
        
        # 初始化权重
        self._init_weights()
    
    def _init_weights(self):
        """初始化嵌入层权重"""
        nn.init.normal_(self.user_gmf_embed.weight, std=0.01)
        nn.init.normal_(self.item_gmf_embed.weight, std=0.01)
        nn.init.normal_(self.user_mlp_embed.weight, std=0.01)
        nn.init.normal_(self.item_mlp_embed.weight, std=0.01)
        
        for layer in self.mlp:
            if isinstance(layer, nn.Linear):
                nn.init.xavier_uniform_(layer.weight)
    
    def forward(self, user_ids: torch.Tensor, item_ids: torch.Tensor) -> torch.Tensor:
        """
        前向传播
        :param user_ids: 用户ID张量 [batch_size]
        :param item_ids: 物品ID张量 [batch_size]
        :return: 预测分数 [batch_size, 1]
        """
        # GMF分支
        user_gmf = self.user_gmf_embed(user_ids)  # [batch, embed_dim]
        item_gmf = self.item_gmf_embed(item_ids)  # [batch, embed_dim]
        gmf_output = user_gmf * item_gmf  # 逐元素相乘 [batch, embed_dim]
        
        # MLP分支
        user_mlp = self.user_mlp_embed(user_ids)  # [batch, 2*embed_dim]
        item_mlp = self.item_mlp_embed(item_ids)  # [batch, 2*embed_dim]
        mlp_input = torch.cat([user_mlp, item_mlp], dim=-1)  # [batch, 4*embed_dim]
        
        # MLP前向
        mlp_output = mlp_input
        for layer in self.mlp:
            mlp_output = layer(mlp_output)
        
        # 融合GMF和MLP
        combined = torch.cat([gmf_output, mlp_output], dim=-1)
        prediction = torch.sigmoid(self.fusion_layer(combined))
        
        return prediction


class UserEmbeddingLookup(nn.Module):
    """用户嵌入查找模块"""
    
    def __init__(self, num_users: int, embed_dim: int = 64):
        super().__init__()
        self.embedding = nn.Embedding(num_users, embed_dim)
        nn.init.normal_(self.embedding.weight, std=0.01)
    
    def forward(self, user_ids: torch.Tensor) -> torch.Tensor:
        return self.embedding(user_ids)


class ItemEmbeddingLookup(nn.Module):
    """物品嵌入查找模块"""
    
    def __init__(self, num_items: int, embed_dim: int = 64):
        super().__init__()
        self.embedding = nn.Embedding(num_items, embed_dim)
        nn.init.normal_(self.embedding.weight, std=0.01)
    
    def forward(self, item_ids: torch.Tensor) -> torch.Tensor:
        return self.embedding(item_ids)


class NeuralPreferenceNet(nn.Module):
    """
    神经网络偏好预测模型
    根据用户历史行为预测用户偏好分布
    """
    
    def __init__(self, input_dim: int = 512, hidden_dim: int = 256, output_dim: int = 4):
        super().__init__()
        
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, output_dim),
            nn.Softmax(dim=-1)
        )
    
    def forward(self, user_history_features: torch.Tensor) -> torch.Tensor:
        """
        预测用户偏好分布
        :param user_history_features: 用户历史特征 [batch, input_dim]
        :return: 偏好分布 [batch, output_dim] - 对应style, singer, producer, emotion
        """
        return self.encoder(user_history_features)


class NCFModelWrapper:
    """NCF模型包装器 - 提供易用的接口"""
    
    def __init__(self, num_users: int, num_items: int, embed_dim: int = 64):
        self.model = NeuralCollaborativeFiltering(num_users, num_items, embed_dim)
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model.to(self.device)
        self._load_model()
    
    def _load_model(self):
        """加载预训练模型"""
        import os
        model_path = os.path.join(os.path.dirname(__file__), 'models', 'ncf_model.pt')
        
        if os.path.exists(model_path):
            try:
                self.model.load_state_dict(torch.load(model_path, map_location=self.device))
                self.model.eval()
            except Exception as e:
                print(f"加载NCF模型失败: {e}")
    
    def predict(self, user_id: int, item_id: int) -> float:
        """预测用户对物品的偏好分数"""
        self.model.eval()
        with torch.no_grad():
            user_tensor = torch.tensor([user_id], device=self.device)
            item_tensor = torch.tensor([item_id], device=self.device)
            score = self.model(user_tensor, item_tensor)
            return score.item()
    
    def predict_batch(self, user_ids: list, item_ids: list) -> list:
        """批量预测"""
        self.model.eval()
        with torch.no_grad():
            user_tensor = torch.tensor(user_ids, device=self.device)
            item_tensor = torch.tensor(item_ids, device=self.device)
            scores = self.model(user_tensor, item_tensor)
            return scores.squeeze().tolist()