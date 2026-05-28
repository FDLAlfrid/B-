"""
轻量级模型模块 - 支持移动端和资源受限环境

包含：
1. 轻量级多头注意力（Linear Attention）
2. 轻量级图神经网络（Simplified GCN）
3. 轻量级多模态融合（MLP-based）
4. GPU训练支持
5. 轻量强化学习训练器
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
import numpy as np
from typing import List, Dict, Optional, Tuple


class LightweightAttention(nn.Module):
    """
    轻量级注意力机制 - 使用Linear Attention替代标准注意力
    
    特点：
    - O(n)复杂度 vs 标准注意力O(n²)
    - 适合长序列和资源受限环境
    - 支持GPU加速
    """
    
    def __init__(self, embed_dim: int = 64, heads: int = 2, dropout: float = 0.1):
        super().__init__()
        self.embed_dim = embed_dim
        self.heads = heads
        self.head_dim = embed_dim // heads
        
        # 线性投影
        self.query_proj = nn.Linear(embed_dim, embed_dim)
        self.key_proj = nn.Linear(embed_dim, embed_dim)
        self.value_proj = nn.Linear(embed_dim, embed_dim)
        self.output_proj = nn.Linear(embed_dim, embed_dim)
        
        self.dropout = nn.Dropout(dropout)
        
    def forward(self, query: torch.Tensor, key: torch.Tensor, value: torch.Tensor, 
                mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        """
        Linear Attention前向传播
        
        Args:
            query: [batch, seq_len, embed_dim]
            key: [batch, seq_len, embed_dim]
            value: [batch, seq_len, embed_dim]
        
        Returns:
            output: [batch, seq_len, embed_dim]
        """
        batch_size = query.size(0)
        
        # 线性投影
        Q = self.query_proj(query).view(batch_size, -1, self.heads, self.head_dim).transpose(1, 2)
        K = self.key_proj(key).view(batch_size, -1, self.heads, self.head_dim).transpose(1, 2)
        V = self.value_proj(value).view(batch_size, -1, self.heads, self.head_dim).transpose(1, 2)
        
        # Linear Attention: softmax(Q) * (K^T * V)
        # 复杂度 O(n) 而非 O(n²)
        Q = F.softmax(Q, dim=-1)
        KV = torch.matmul(K.transpose(-2, -1), V)
        output = torch.matmul(Q, KV)
        
        # 拼接多头输出
        output = output.transpose(1, 2).contiguous().view(batch_size, -1, self.embed_dim)
        output = self.dropout(self.output_proj(output))
        
        return output


class LightweightGCN(nn.Module):
    """
    轻量级图卷积网络
    
    特点：
    - 简化的图卷积操作
    - 支持稀疏矩阵优化
    - 内存友好
    """
    
    def __init__(self, num_nodes: int, embed_dim: int = 32, num_layers: int = 2):
        super().__init__()
        self.num_nodes = num_nodes
        self.embed_dim = embed_dim
        
        # 节点嵌入
        self.node_embedding = nn.Embedding(num_nodes, embed_dim)
        
        # 图卷积层
        self.conv_layers = nn.ModuleList([
            nn.Linear(embed_dim, embed_dim) for _ in range(num_layers)
        ])
        
        # 初始化
        nn.init.xavier_uniform_(self.node_embedding.weight)
    
    def forward(self, adj_matrix: torch.Tensor, node_ids: torch.Tensor) -> torch.Tensor:
        """
        轻量级GCN前向传播
        
        Args:
            adj_matrix: [num_nodes, num_nodes] 邻接矩阵
            node_ids: [batch] 节点ID
        
        Returns:
            embeddings: [batch, embed_dim]
        """
        # 获取初始嵌入
        x = self.node_embedding.weight
        
        # 图卷积
        for conv in self.conv_layers:
            # 消息传递: x = ReLU(A @ x @ W)
            x = F.relu(conv(torch.matmul(adj_matrix, x)))
        
        # 返回指定节点的嵌入
        return x[node_ids]


class LightweightMultimodalFusion(nn.Module):
    """
    轻量级多模态融合网络
    
    特点：
    - 基于MLP的简单融合
    - 低计算复杂度
    - 适合资源受限环境
    """
    
    def __init__(self, text_dim: int = 384, audio_dim: int = 128, 
                 visual_dim: int = 256, behavior_dim: int = 64, output_dim: int = 64):
        super().__init__()
        
        # 模态投影到统一维度
        self.text_proj = nn.Linear(text_dim, output_dim)
        self.audio_proj = nn.Linear(audio_dim, output_dim)
        self.visual_proj = nn.Linear(visual_dim, output_dim)
        self.behavior_proj = nn.Linear(behavior_dim, output_dim)
        
        # 融合层
        self.fusion = nn.Sequential(
            nn.Linear(output_dim * 4, output_dim),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(output_dim, output_dim)
        )
        
        # 可学习的模态权重
        self.modal_weights = nn.Parameter(torch.tensor([0.3, 0.3, 0.2, 0.2]))
    
    def forward(self, text_feat: torch.Tensor, audio_feat: torch.Tensor,
                visual_feat: torch.Tensor, behavior_feat: torch.Tensor) -> torch.Tensor:
        """
        多模态融合前向传播
        """
        # 投影到相同维度
        t = self.text_proj(text_feat)
        a = self.audio_proj(audio_feat)
        v = self.visual_proj(visual_feat)
        b = self.behavior_proj(behavior_feat)
        
        # 加权融合
        weights = F.softmax(self.modal_weights, dim=0)
        fused = weights[0] * t + weights[1] * a + weights[2] * v + weights[3] * b
        
        # 最终融合
        return self.fusion(torch.cat([t, a, v, b, fused], dim=-1))


class LightweightNCF(nn.Module):
    """
    轻量级神经协同过滤模型
    """
    
    def __init__(self, num_users: int, num_items: int, embed_dim: int = 32):
        super().__init__()
        
        # 用户和物品嵌入
        self.user_embed = nn.Embedding(num_users, embed_dim)
        self.item_embed = nn.Embedding(num_items, embed_dim)
        
        # 预测层
        self.predictor = nn.Sequential(
            nn.Linear(embed_dim * 2, embed_dim),
            nn.ReLU(),
            nn.Linear(embed_dim, 1)
        )
        
        # 初始化
        nn.init.xavier_uniform_(self.user_embed.weight)
        nn.init.xavier_uniform_(self.item_embed.weight)
    
    def forward(self, user_ids: torch.Tensor, item_ids: torch.Tensor) -> torch.Tensor:
        """
        NCF前向传播
        """
        user_emb = self.user_embed(user_ids)
        item_emb = self.item_embed(item_ids)
        
        # GMF分支：逐元素相乘
        gmf = user_emb * item_emb
        
        # 拼接特征
        concat = torch.cat([user_emb, item_emb, gmf], dim=-1)
        
        # 预测
        return torch.sigmoid(self.predictor(concat))


class LightReinforcementLearner(nn.Module):
    """
    轻量级强化学习策略网络
    
    特点：
    - 策略梯度方法
    - 轻量网络结构
    - 支持在线学习
    """
    
    def __init__(self, state_dim: int = 128, action_dim: int = 10, hidden_dim: int = 64):
        super().__init__()
        
        self.policy_net = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, action_dim)
        )
        
        self.value_net = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1)
        )
    
    def forward(self, state: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        前向传播
        
        Returns:
            action_probs: 动作概率分布
            value: 状态价值估计
        """
        logits = self.policy_net(state)
        action_probs = F.softmax(logits, dim=-1)
        value = self.value_net(state)
        
        return action_probs, value


class ResourceEfficientTrainer:
    """
    资源高效训练器 - 支持GPU训练和轻量后台训练
    
    特点：
    - 自动检测GPU并使用
    - 支持混合精度训练
    - 低内存占用策略
    - 后台异步训练支持
    """
    
    def __init__(self, model: nn.Module, device: str = 'auto', 
                 mixed_precision: bool = True, memory_efficient: bool = True):
        """
        初始化训练器
        
        Args:
            model: 要训练的模型
            device: 'auto'自动检测, 'cuda', 'cpu'
            mixed_precision: 是否使用混合精度训练
            memory_efficient: 是否启用内存优化
        """
        # 设备配置
        self.device = self._get_device(device)
        self.model = model.to(self.device)
        
        # 混合精度
        self.mixed_precision = mixed_precision
        self.scaler = torch.cuda.amp.GradScaler(enabled=mixed_precision) if self.device.type == 'cuda' else None
        
        # 内存优化
        self.memory_efficient = memory_efficient
        
        # 优化器
        self.optimizer = None
        
        # 训练状态
        self.training = False
        self.epoch = 0
        
        # 统计信息
        self.loss_history = []
        self.metric_history = []
    
    def _get_device(self, device: str) -> torch.device:
        """获取训练设备"""
        if device == 'auto':
            if torch.cuda.is_available():
                print(f"✓ 检测到GPU: {torch.cuda.get_device_name(0)}")
                return torch.device('cuda')
            else:
                print("⚠️ 未检测到GPU，使用CPU")
                return torch.device('cpu')
        return torch.device(device)
    
    def set_optimizer(self, optimizer: torch.optim.Optimizer):
        """设置优化器"""
        self.optimizer = optimizer
    
    def train_step(self, inputs: Tuple[torch.Tensor], labels: torch.Tensor, 
                   criterion: nn.Module) -> float:
        """
        单步训练
        
        Args:
            inputs: 输入张量元组
            labels: 标签
            criterion: 损失函数
        
        Returns:
            loss: 损失值
        """
        self.model.train()
        
        # 转移到设备
        inputs = tuple(x.to(self.device) for x in inputs)
        labels = labels.to(self.device)
        
        self.optimizer.zero_grad()
        
        # 混合精度训练
        if self.mixed_precision and self.device.type == 'cuda':
            with torch.cuda.amp.autocast():
                outputs = self.model(*inputs)
                loss = criterion(outputs, labels)
            
            self.scaler.scale(loss).backward()
            self.scaler.step(self.optimizer)
            self.scaler.update()
        else:
            outputs = self.model(*inputs)
            loss = criterion(outputs, labels)
            loss.backward()
            self.optimizer.step()
        
        # 内存优化：释放中间张量
        if self.memory_efficient:
            torch.cuda.empty_cache()
        
        return loss.item()
    
    def evaluate(self, dataloader: DataLoader, criterion: nn.Module) -> Tuple[float, float]:
        """
        评估模型
        
        Returns:
            avg_loss: 平均损失
            accuracy: 准确率（分类任务）
        """
        self.model.eval()
        total_loss = 0.0
        correct = 0
        total = 0
        
        with torch.no_grad():
            for inputs, labels in dataloader:
                inputs = tuple(x.to(self.device) for x in inputs)
                labels = labels.to(self.device)
                
                outputs = self.model(*inputs)
                loss = criterion(outputs, labels)
                total_loss += loss.item() * len(labels)
                
                # 计算准确率
                preds = (outputs > 0.5).float() if outputs.size(-1) == 1 else outputs.argmax(dim=-1)
                correct += (preds == labels).sum().item()
                total += len(labels)
        
        avg_loss = total_loss / total
        accuracy = correct / total if total > 0 else 0.0
        
        return avg_loss, accuracy
    
    def train_epoch(self, dataloader: DataLoader, criterion: nn.Module, 
                   verbose: bool = True) -> float:
        """
        训练一个epoch
        
        Returns:
            avg_loss: 平均损失
        """
        self.model.train()
        total_loss = 0.0
        total_samples = 0
        
        for inputs, labels in dataloader:
            loss = self.train_step(inputs, labels, criterion)
            total_loss += loss * len(labels)
            total_samples += len(labels)
        
        avg_loss = total_loss / total_samples
        
        if verbose:
            print(f"Epoch [{self.epoch+1}] Loss: {avg_loss:.4f}")
        
        self.epoch += 1
        self.loss_history.append(avg_loss)
        
        return avg_loss


class LightRLTrainer:
    """
    轻量级强化学习训练器 - 支持后台轻量训练
    
    特点：
    - 低资源占用
    - 支持在线学习
    - 实时反馈训练
    - 自适应学习率
    """
    
    def __init__(self, policy_model: LightReinforcementLearner, 
                 learning_rate: float = 0.001, device: str = 'auto'):
        """
        初始化RL训练器
        
        Args:
            policy_model: 策略模型
            learning_rate: 学习率
            device: 训练设备
        """
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu') if device == 'auto' else torch.device(device)
        
        self.policy_model = policy_model.to(self.device)
        self.optimizer = torch.optim.Adam(policy_model.parameters(), lr=learning_rate)
        
        # 奖励权重
        self.reward_weights = {
            'like': 1.0,
            'collect': 0.8,
            'share': 0.6,
            'click': 0.2,
            'dislike': -1.0
        }
        
        # 累积梯度（用于增量更新）
        self.accumulated_grads = {}
        self.grad_accum_steps = 0
        self.max_accum_steps = 10  # 每10步更新一次
        
        # 统计信息
        self.total_reward = 0.0
        self.step_count = 0
    
    def get_action(self, state: torch.Tensor) -> int:
        """
        获取动作
        
        Args:
            state: 状态张量 [state_dim]
        
        Returns:
            action: 动作索引
        """
        state = state.to(self.device).unsqueeze(0)
        action_probs, _ = self.policy_model(state)
        
        # 采样动作
        action = torch.multinomial(action_probs, num_samples=1).item()
        
        return action
    
    def update_policy(self, states: List[torch.Tensor], actions: List[int], 
                      rewards: List[float], gamma: float = 0.99):
        """
        更新策略网络
        
        Args:
            states: 状态列表
            actions: 动作列表
            rewards: 奖励列表
            gamma: 折扣因子
        """
        if len(states) == 0:
            return
        
        # 转换为张量
        states_tensor = torch.stack(states).to(self.device)
        actions_tensor = torch.tensor(actions, device=self.device)
        
        # 计算折扣奖励
        discounted_rewards = []
        running_sum = 0.0
        for reward in reversed(rewards):
            running_sum = reward + gamma * running_sum
            discounted_rewards.insert(0, running_sum)
        
        discounted_rewards = torch.tensor(discounted_rewards, device=self.device)
        discounted_rewards = (discounted_rewards - discounted_rewards.mean()) / (discounted_rewards.std() + 1e-8)
        
        # 前向传播
        action_probs, values = self.policy_model(states_tensor)
        
        # 计算策略梯度损失
        action_log_probs = torch.log(action_probs.gather(1, actions_tensor.unsqueeze(1)))
        advantage = discounted_rewards.unsqueeze(1) - values
        
        policy_loss = -(action_log_probs * advantage.detach()).mean()
        value_loss = F.mse_loss(values, discounted_rewards.unsqueeze(1))
        loss = policy_loss + 0.5 * value_loss
        
        # 累积梯度
        loss.backward()
        self.grad_accum_steps += 1
        
        # 达到累积步数时更新
        if self.grad_accum_steps >= self.max_accum_steps:
            self.optimizer.step()
            self.optimizer.zero_grad()
            self.grad_accum_steps = 0
            
            # 内存优化
            if self.device.type == 'cuda':
                torch.cuda.empty_cache()
        
        # 更新统计
        self.total_reward += sum(rewards)
        self.step_count += len(rewards)
    
    def process_feedback(self, state: torch.Tensor, action: int, feedback_type: str):
        """
        处理用户反馈并更新策略
        
        Args:
            state: 状态张量
            action: 执行的动作
            feedback_type: 反馈类型 ('like', 'collect', 'share', 'click', 'dislike')
        """
        reward = self.reward_weights.get(feedback_type, 0.0)
        
        # 简单的单步更新
        self.update_policy([state], [action], [reward])


# 轻量级模型工厂
class LightModelFactory:
    """
    轻量级模型工厂 - 创建各种轻量模型实例
    """
    
    @staticmethod
    def create_attention(embed_dim: int = 64, heads: int = 2) -> LightweightAttention:
        """创建轻量级注意力模型"""
        return LightweightAttention(embed_dim=embed_dim, heads=heads)
    
    @staticmethod
    def create_gcn(num_nodes: int, embed_dim: int = 32) -> LightweightGCN:
        """创建轻量级GCN模型"""
        return LightweightGCN(num_nodes=num_nodes, embed_dim=embed_dim)
    
    @staticmethod
    def create_multimodal_fusion(output_dim: int = 64) -> LightweightMultimodalFusion:
        """创建轻量级多模态融合模型"""
        return LightweightMultimodalFusion(output_dim=output_dim)
    
    @staticmethod
    def create_ncf(num_users: int, num_items: int, embed_dim: int = 32) -> LightweightNCF:
        """创建轻量级NCF模型"""
        return LightweightNCF(num_users=num_users, num_items=num_items, embed_dim=embed_dim)
    
    @staticmethod
    def create_rl_agent(state_dim: int = 128, action_dim: int = 10) -> LightReinforcementLearner:
        """创建轻量级强化学习智能体"""
        return LightReinforcementLearner(state_dim=state_dim, action_dim=action_dim)


# 全局轻量训练器实例
light_trainer = None


def init_light_trainer(model: nn.Module = None):
    """
    初始化轻量训练器
    
    Args:
        model: 可选的模型实例
    
    Returns:
        trainer: ResourceEfficientTrainer实例
    """
    global light_trainer
    
    if model is not None:
        light_trainer = ResourceEfficientTrainer(
            model=model,
            device='auto',
            mixed_precision=True,
            memory_efficient=True
        )
    
    return light_trainer


def get_device_info() -> Dict[str, str]:
    """
    获取设备信息
    
    Returns:
        info: 设备信息字典
    """
    info = {
        'device': 'cuda' if torch.cuda.is_available() else 'cpu',
        'gpu_name': torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A',
        'gpu_memory': f"{torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB" if torch.cuda.is_available() else 'N/A',
        'mixed_precision_supported': str(torch.cuda.is_available())
    }
    return info


if __name__ == '__main__':
    # 示例：使用轻量级模型和训练器
    print("=== 轻量级模型测试 ===")
    
    # 检查设备
    device_info = get_device_info()
    print(f"设备: {device_info['device']}")
    print(f"GPU名称: {device_info['gpu_name']}")
    print(f"GPU内存: {device_info['gpu_memory']}")
    
    # 创建轻量级模型
    attention = LightModelFactory.create_attention()
    gcn = LightModelFactory.create_gcn(num_nodes=1000)
    fusion = LightModelFactory.create_multimodal_fusion()
    ncf = LightModelFactory.create_ncf(num_users=1000, num_items=5000)
    rl_agent = LightModelFactory.create_rl_agent()
    
    print("\n=== 模型创建成功 ===")
    print(f"注意力模型参数: {sum(p.numel() for p in attention.parameters())/1e3:.1f}K")
    print(f"GCN模型参数: {sum(p.numel() for p in gcn.parameters())/1e3:.1f}K")
    print(f"多模态融合参数: {sum(p.numel() for p in fusion.parameters())/1e3:.1f}K")
    print(f"NCF模型参数: {sum(p.numel() for p in ncf.parameters())/1e3:.1f}K")
    print(f"RL智能体参数: {sum(p.numel() for p in rl_agent.parameters())/1e3:.1f}K")
    
    # 测试前向传播
    print("\n=== 前向传播测试 ===")
    
    # 测试注意力
    x = torch.randn(2, 10, 64)
    out = attention(x, x, x)
    print(f"注意力输出形状: {out.shape}")
    
    # 测试NCF
    user_ids = torch.tensor([0, 1])
    item_ids = torch.tensor([10, 20])
    out = ncf(user_ids, item_ids)
    print(f"NCF输出形状: {out.shape}")
    
    print("\n=== 测试完成 ===")