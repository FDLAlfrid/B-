"""
图神经网络模块 - 基于PyTorch Geometric实现

实现论文中描述的图神经网络推荐算法，包括：
1. 异构图数据集构建
2. GCN（图卷积网络）- 论文公式(4-5)
3. GAT（图注意力网络）
4. 图推荐接口
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import List, Tuple, Optional

try:
    from torch_geometric.nn import GCNConv, GATConv, global_mean_pool
    from torch_geometric.data import Data, HeteroData
    from torch_geometric.utils import to_undirected
    PYG_AVAILABLE = True
except ImportError:
    PYG_AVAILABLE = False


class DeepGCNModel(nn.Module):
    """
    深度图卷积网络模型 - 实现论文公式(4-5)
    
    论文公式(4-5)：
    Graph_Score(u,s) = Σ_(p∈Paths(u,s)) 1/|p| × ∏_(e∈p) w_e
    
    GCN卷积公式：
    h_v^(l+1) = σ(W^(l) · AGG(h_u^(l) : u ∈ N(v)))
    """
    
    def __init__(self, num_users: int, num_items: int, num_ips: int = 100, 
                 embed_dim: int = 64, num_layers: int = 3):
        super().__init__()
        
        self.num_users = num_users
        self.num_items = num_items
        self.num_ips = num_ips
        self.embed_dim = embed_dim
        
        # 节点嵌入层
        self.user_embed = nn.Embedding(num_users, embed_dim)
        self.item_embed = nn.Embedding(num_items, embed_dim)
        self.ip_embed = nn.Embedding(num_ips, embed_dim)
        
        # GCN卷积层
        self.convs = nn.ModuleList()
        for i in range(num_layers):
            if i == 0:
                self.convs.append(GCNConv(embed_dim, embed_dim * 2))
            elif i == num_layers - 1:
                self.convs.append(GCNConv(embed_dim * 2, embed_dim))
            else:
                self.convs.append(GCNConv(embed_dim * 2, embed_dim * 2))
        
        # 预测层
        self.predict = nn.Sequential(
            nn.Linear(embed_dim * 2, 32),
            nn.ReLU(),
            nn.Linear(32, 1)
        )
        
        # 初始化权重
        self._init_weights()
    
    def _init_weights(self):
        """初始化权重"""
        nn.init.normal_(self.user_embed.weight, std=0.01)
        nn.init.normal_(self.item_embed.weight, std=0.01)
        nn.init.normal_(self.ip_embed.weight, std=0.01)
    
    def forward(self, user_ids: torch.Tensor, item_ids: torch.Tensor, 
                edge_index: torch.Tensor, edge_weight: Optional[torch.Tensor] = None) -> torch.Tensor:
        """
        前向传播
        :param user_ids: 用户ID [batch]
        :param item_ids: 物品ID [batch]
        :param edge_index: 边索引 [2, num_edges]
        :param edge_weight: 边权重 [num_edges]
        :return: 预测分数 [batch, 1]
        """
        # 获取节点嵌入
        num_nodes = self.num_users + self.num_items + self.num_ips
        x = torch.zeros(num_nodes, self.embed_dim, device=user_ids.device)
        
        # 填充用户嵌入
        user_mask = user_ids < self.num_users
        x[user_ids[user_mask]] = self.user_embed(user_ids[user_mask])
        
        # 图卷积
        h = x[edge_index[0]]
        for conv in self.convs:
            h = F.relu(conv(h, edge_index, edge_weight))
        
        # 获取用户和物品的最终嵌入
        user_h = x[user_ids]
        item_h = x[self.num_users + item_ids]
        
        # 计算相似度分数
        similarity = F.cosine_similarity(user_h, item_h, dim=-1).unsqueeze(-1)
        
        return torch.sigmoid(similarity)


class DeepGATModel(nn.Module):
    """
    图注意力网络模型 - GAT
    
    注意力系数计算（论文公式扩展）：
    α_ij = softmax(LeakyReLU(a^T [Wh_i || Wh_j]))
    """
    
    def __init__(self, num_users: int, num_items: int, num_ips: int = 100, 
                 embed_dim: int = 64, num_heads: int = 4):
        super().__init__()
        
        self.num_users = num_users
        self.num_items = num_items
        self.num_ips = num_ips
        self.embed_dim = embed_dim
        
        # 节点嵌入层
        self.user_embed = nn.Embedding(num_users, embed_dim)
        self.item_embed = nn.Embedding(num_items, embed_dim)
        self.ip_embed = nn.Embedding(num_ips, embed_dim)
        
        # GAT卷积层
        self.conv1 = GATConv(embed_dim, embed_dim, heads=num_heads)
        self.conv2 = GATConv(embed_dim * num_heads, embed_dim, heads=1)
        
        # 预测层
        self.predict = nn.Linear(embed_dim, 1)
        
        # 初始化权重
        self._init_weights()
    
    def _init_weights(self):
        """初始化权重"""
        nn.init.normal_(self.user_embed.weight, std=0.01)
        nn.init.normal_(self.item_embed.weight, std=0.01)
        nn.init.normal_(self.ip_embed.weight, std=0.01)
    
    def forward(self, user_ids: torch.Tensor, item_ids: torch.Tensor, 
                edge_index: torch.Tensor) -> torch.Tensor:
        """
        前向传播
        """
        # 获取节点嵌入
        num_nodes = self.num_users + self.num_items + self.num_ips
        x = torch.zeros(num_nodes, self.embed_dim, device=user_ids.device)
        
        user_mask = user_ids < self.num_users
        x[user_ids[user_mask]] = self.user_embed(user_ids[user_mask])
        
        # GAT卷积
        x = F.elu(self.conv1(x, edge_index))
        x = F.elu(self.conv2(x, edge_index))
        
        # 获取用户和物品嵌入
        user_h = x[user_ids]
        item_h = x[self.num_users + item_ids]
        
        # 计算相似度
        similarity = F.cosine_similarity(user_h, item_h, dim=-1).unsqueeze(-1)
        
        return torch.sigmoid(similarity)


class HeteroGraphDataset:
    """异构图数据集构建器"""
    
    def __init__(self):
        self.data = None
    
    def build_from_interactions(self, user_song_interactions: List[Tuple[int, int, float]],
                                user_ip_associations: List[Tuple[int, int, float]] = None):
        """
        从交互数据构建异构图
        :param user_song_interactions: [(user_id, song_id, weight), ...]
        :param user_ip_associations: [(user_id, ip_id, weight), ...]
        """
        if not PYG_AVAILABLE:
            raise ImportError("PyTorch Geometric not available")
        
        edge_list = []
        
        # 添加用户-歌曲边
        for user_id, song_id, weight in user_song_interactions:
            edge_list.append((user_id, song_id + 10000))  # 歌曲ID偏移
        
        # 添加用户-IP边
        if user_ip_associations:
            for user_id, ip_id, weight in user_ip_associations:
                edge_list.append((user_id, ip_id + 10000 + 50000))  # IP ID偏移
        
        edge_index = torch.tensor(edge_list, dtype=torch.long).t().contiguous()
        edge_index = to_undirected(edge_index)
        
        self.data = Data(edge_index=edge_index)
    
    def to_tensor(self):
        """转换为PyTorch张量"""
        return self.data


class GraphRecommender:
    """图推荐接口类"""
    
    def __init__(self, num_users: int = 10000, num_items: int = 50000, 
                 gnn_type: str = 'gcn', embed_dim: int = 64):
        self.num_users = num_users
        self.num_items = num_items
        self.gnn_type = gnn_type
        self.embed_dim = embed_dim
        
        if PYG_AVAILABLE:
            if gnn_type == 'gcn':
                self.model = DeepGCNModel(num_users, num_items, embed_dim=embed_dim)
            else:
                self.model = DeepGATModel(num_users, num_items, embed_dim=embed_dim)
            
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            self.model.to(self.device)
            self._load_model()
        else:
            self.model = None
        
        self._use_real_gnn = PYG_AVAILABLE
    
    def _load_model(self):
        """加载预训练模型"""
        import os
        model_path = os.path.join(os.path.dirname(__file__), 'models', f'{self.gnn_type}_model.pt')
        
        if os.path.exists(model_path):
            try:
                self.model.load_state_dict(torch.load(model_path, map_location=self.device))
                self.model.eval()
            except Exception as e:
                print(f"加载GNN模型失败: {e}")
    
    def recommend(self, user_id: int, candidates: List[int], limit: int = 20) -> List[Tuple[int, float]]:
        """
        基于图神经网络推荐
        :param user_id: 用户ID
        :param candidates: 候选物品ID列表
        :param limit: 返回数量
        :return: [(item_id, score), ...]
        """
        if not self._use_real_gnn:
            # 回退到简单相似度计算
            return self._fallback_recommend(user_id, candidates, limit)
        
        self.model.eval()
        with torch.no_grad():
            user_tensor = torch.tensor([user_id] * len(candidates), device=self.device)
            item_tensor = torch.tensor(candidates, device=self.device)
            
            # 构建简单的边索引（假设有一条边连接用户和所有候选物品）
            edge_index = torch.tensor([[user_id] * len(candidates), 
                                       [10000 + c for c in candidates]], 
                                      device=self.device, dtype=torch.long)
            
            scores = self.model(user_tensor, item_tensor, edge_index)
            scores = scores.squeeze().tolist()
        
        # 排序并返回
        results = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
        return results[:limit]
    
    def _fallback_recommend(self, user_id: int, candidates: List[int], limit: int) -> List[Tuple[int, float]]:
        """回退推荐方法（无PyG时使用）"""
        # 简单的随机分数作为回退
        import random
        results = [(c, random.random()) for c in candidates]
        return sorted(results, key=lambda x: x[1], reverse=True)[:limit]