"""
深度学习模型训练脚本

用于训练推荐系统中的深度学习模型：
1. NCF模型 - 神经协同过滤
2. GCN/GAT模型 - 图神经网络
3. 排序模型 - 深度排序
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import os
import json
import numpy as np
from typing import List, Tuple, Dict


class InteractionDataset(Dataset):
    """用户-物品交互数据集"""
    
    def __init__(self, interactions: List[Tuple[int, int, int]]):
        self.interactions = interactions
    
    def __len__(self):
        return len(self.interactions)
    
    def __getitem__(self, idx):
        user_id, item_id, label = self.interactions[idx]
        return torch.tensor(user_id), torch.tensor(item_id), torch.tensor(label, dtype=torch.float32)


def train_ncf_model(num_users: int = 10000, num_items: int = 50000, 
                    epochs: int = 100, batch_size: int = 256, lr: float = 0.001):
    """
    训练神经协同过滤模型
    """
    from .deep_ncf import NeuralCollaborativeFiltering
    
    # 创建模拟训练数据
    print("准备训练数据...")
    interactions = []
    for _ in range(50000):
        user_id = np.random.randint(0, num_users)
        item_id = np.random.randint(0, num_items)
        # 随机生成正负样本（1:1比例）
        label = 1 if np.random.random() > 0.5 else 0
        interactions.append((user_id, item_id, label))
    
    dataset = InteractionDataset(interactions)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
    
    # 创建模型
    model = NeuralCollaborativeFiltering(num_users, num_items, embed_dim=64)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model.to(device)
    
    # 训练配置
    criterion = nn.BCELoss()
    optimizer = optim.Adam(model.parameters(), lr=lr)
    
    # 训练循环
    print(f"开始训练NCF模型，使用{device}...")
    for epoch in range(epochs):
        model.train()
        total_loss = 0.0
        
        for user_ids, item_ids, labels in dataloader:
            user_ids = user_ids.to(device)
            item_ids = item_ids.to(device)
            labels = labels.to(device)
            
            optimizer.zero_grad()
            
            outputs = model(user_ids, item_ids)
            loss = criterion(outputs.squeeze(), labels)
            
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
        
        avg_loss = total_loss / len(dataloader)
        if (epoch + 1) % 10 == 0:
            print(f"Epoch [{epoch+1}/{epochs}], Loss: {avg_loss:.4f}")
    
    # 保存模型
    model_dir = os.path.join(os.path.dirname(__file__), 'models')
    os.makedirs(model_dir, exist_ok=True)
    torch.save(model.state_dict(), os.path.join(model_dir, 'ncf_model.pt'))
    print("NCF模型训练完成并保存!")


def train_gcn_model(num_users: int = 10000, num_items: int = 50000,
                    epochs: int = 200, batch_size: int = 256, lr: float = 0.01):
    """
    训练图神经网络模型
    """
    try:
        from torch_geometric.data import Data
        from torch_geometric.utils import to_undirected
    except ImportError:
        print("PyTorch Geometric不可用，跳过GCN训练")
        return
    
    from .deep_gcn import DeepGCNModel
    
    # 创建模拟图数据
    print("准备图数据...")
    edge_list = []
    for _ in range(100000):
        user_id = np.random.randint(0, num_users)
        item_id = np.random.randint(0, num_items)
        edge_list.append([user_id, num_users + item_id])
    
    edge_index = torch.tensor(edge_list, dtype=torch.long).t().contiguous()
    edge_index = to_undirected(edge_index)
    
    # 创建模型
    model = DeepGCNModel(num_users, num_items, embed_dim=64)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model.to(device)
    edge_index = edge_index.to(device)
    
    # 训练配置
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=lr)
    
    # 训练循环
    print(f"开始训练GCN模型，使用{device}...")
    for epoch in range(epochs):
        model.train()
        optimizer.zero_grad()
        
        # 随机采样用户-物品对
        user_ids = torch.randint(0, num_users, (batch_size,), device=device)
        item_ids = torch.randint(0, num_items, (batch_size,), device=device)
        
        outputs = model(user_ids, item_ids, edge_index)
        
        # 使用随机标签（实际应用中应使用真实交互数据）
        labels = torch.rand(batch_size, 1, device=device)
        
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()
        
        if (epoch + 1) % 20 == 0:
            print(f"Epoch [{epoch+1}/{epochs}], Loss: {loss.item():.4f}")
    
    # 保存模型
    model_dir = os.path.join(os.path.dirname(__file__), 'models')
    os.makedirs(model_dir, exist_ok=True)
    torch.save(model.state_dict(), os.path.join(model_dir, 'gcn_model.pt'))
    print("GCN模型训练完成并保存!")


def train_ranking_model(feature_dim: int = 512, epochs: int = 50, 
                        batch_size: int = 128, lr: float = 0.001):
    """
    训练深度排序模型
    """
    from .deep_ranking import DeepRankingModel
    
    # 创建模拟训练数据
    print("准备排序模型训练数据...")
    num_samples = 20000
    features = torch.randn(num_samples, feature_dim)
    labels = torch.rand(num_samples, 1)  # 随机标签
    
    # 创建模型
    model = DeepRankingModel(feature_dim=feature_dim)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model.to(device)
    
    # 训练配置
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=lr)
    
    # 训练循环
    print(f"开始训练排序模型，使用{device}...")
    for epoch in range(epochs):
        model.train()
        optimizer.zero_grad()
        
        # 随机采样
        indices = torch.randperm(num_samples)[:batch_size]
        batch_features = features[indices].to(device)
        batch_labels = labels[indices].to(device)
        
        outputs = model(batch_features)
        loss = criterion(outputs, batch_labels)
        
        loss.backward()
        optimizer.step()
        
        if (epoch + 1) % 10 == 0:
            print(f"Epoch [{epoch+1}/{epochs}], Loss: {loss.item():.4f}")
    
    # 保存模型
    model_dir = os.path.join(os.path.dirname(__file__), 'models')
    os.makedirs(model_dir, exist_ok=True)
    torch.save(model.state_dict(), os.path.join(model_dir, 'ranking_model.pt'))
    print("排序模型训练完成并保存!")


def train_all_models():
    """训练所有深度学习模型"""
    print("=" * 60)
    print("开始训练所有深度学习模型")
    print("=" * 60)
    
    # 训练NCF模型
    train_ncf_model()
    
    print()
    
    # 训练GCN模型
    train_gcn_model()
    
    print()
    
    # 训练排序模型
    train_ranking_model()
    
    print("=" * 60)
    print("所有模型训练完成!")
    print("=" * 60)


if __name__ == '__main__':
    train_all_models()