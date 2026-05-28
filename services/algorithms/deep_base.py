"""
深度学习基础模块 - 为推荐系统提供基础的深度学习组件

实现论文中描述的：
1. 多头注意力机制（公式4-6、4-7）
2. 多模态特征融合
3. 可学习的混合权重网络
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional


class TextEmbedding(nn.Module):
    """
    文本Embedding编码器
    使用预训练的sentence-transformers进行文本编码
    """
    
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        super().__init__()
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(model_name)
            self.embedding_dim = self.model.get_sentence_embedding_dimension()
            self._available = True
        except ImportError:
            self._available = False
            self.embedding_dim = 384  # 默认维度
    
    def forward(self, texts: list) -> torch.Tensor:
        """编码文本列表"""
        if not self._available:
            # 回退方案：随机嵌入
            return torch.randn(len(texts), self.embedding_dim)
        
        embeddings = self.model.encode(texts, convert_to_tensor=True)
        return embeddings


class MultiHeadAttention(nn.Module):
    """
    多头注意力机制 - 实现论文公式(4-6)(4-7)
    
    公式(4-6) 缩放点积注意力：
    Attention(Q,K,V) = softmax((QK^T)/√(d_k)) × V
    
    公式(4-7) 多头注意力：
    MultiHead(Q,K,V) = Concat(head_1,...,head_h) × W^O
    head_i = Attention(QW_i^Q, KW_i^K, VW_i^V)
    """
    
    def __init__(self, embed_dim: int = 128, num_heads: int = 4, dropout: float = 0.1):
        super().__init__()
        
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        
        assert embed_dim % num_heads == 0, "embed_dim必须能被num_heads整除"
        
        # 可学习权重矩阵（论文公式中的W_q, W_k, W_v, W_o）
        self.W_q = nn.Linear(embed_dim, embed_dim)
        self.W_k = nn.Linear(embed_dim, embed_dim)
        self.W_v = nn.Linear(embed_dim, embed_dim)
        self.W_o = nn.Linear(embed_dim, embed_dim)
        
        self.dropout = nn.Dropout(dropout)
    
    def scaled_dot_product_attention(self, Q: torch.Tensor, K: torch.Tensor, 
                                     V: torch.Tensor, mask: Optional[torch.Tensor] = None) -> tuple:
        """
        缩放点积注意力 - 实现论文公式(4-6)
        """
        d_k = Q.size(-1)
        
        # QK^T / √(d_k)
        scores = torch.matmul(Q, K.transpose(-2, -1)) / torch.sqrt(torch.tensor(d_k, dtype=torch.float32))
        
        if mask is not None:
            scores = scores.masked_fill(mask == 0, -1e9)
        
        # softmax((QK^T)/√(d_k))
        attention_weights = torch.softmax(scores, dim=-1)
        attention_weights = self.dropout(attention_weights)
        
        # softmax((QK^T)/√(d_k)) × V
        output = torch.matmul(attention_weights, V)
        
        return output, attention_weights
    
    def forward(self, query: torch.Tensor, key: torch.Tensor, value: torch.Tensor, 
                mask: Optional[torch.Tensor] = None) -> tuple:
        """
        多头注意力前向传播 - 实现论文公式(4-7)
        """
        batch_size = query.size(0)
        
        # 线性变换：QW^Q, KW^K, VW^V
        Q = self.W_q(query)
        K = self.W_k(key)
        V = self.W_v(value)
        
        # 分割为多个头
        Q = Q.view(batch_size, -1, self.num_heads, self.head_dim).transpose(1, 2)
        K = K.view(batch_size, -1, self.num_heads, self.head_dim).transpose(1, 2)
        V = V.view(batch_size, -1, self.num_heads, self.head_dim).transpose(1, 2)
        
        if mask is not None:
            mask = mask.unsqueeze(1).repeat(1, self.num_heads, 1, 1)
        
        # 每个头独立计算注意力
        attn_output, attention_weights = self.scaled_dot_product_attention(Q, K, V, mask)
        
        # 拼接多头输出
        attn_output = attn_output.transpose(1, 2).contiguous().view(batch_size, -1, self.embed_dim)
        
        # 输出投影：Concat × W^O
        output = self.W_o(attn_output)
        
        return output, attention_weights


class FeatureProjection(nn.Module):
    """特征投影层"""
    
    def __init__(self, input_dim: int, output_dim: int, activation: str = 'relu'):
        super().__init__()
        
        self.projection = nn.Linear(input_dim, output_dim)
        
        if activation == 'relu':
            self.activation = nn.ReLU()
        elif activation == 'tanh':
            self.activation = nn.Tanh()
        else:
            self.activation = nn.Identity()
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.activation(self.projection(x))


class MultimodalFusion(nn.Module):
    """
    多模态特征融合网络 - 实现论文公式(4-4)
    
    Multimodal_Score = 0.30 × Text_Feature + 0.30 × Behavior_Feature
                     + 0.20 × Audio_Feature + 0.20 × Visual_Feature
    """
    
    def __init__(self, text_dim: int = 768, audio_dim: int = 128, 
                 visual_dim: int = 256, behavior_dim: int = 64, output_dim: int = 128):
        super().__init__()
        
        # 模态投影层
        self.text_proj = FeatureProjection(text_dim, output_dim)
        self.audio_proj = FeatureProjection(audio_dim, output_dim)
        self.visual_proj = FeatureProjection(visual_dim, output_dim)
        self.behavior_proj = FeatureProjection(behavior_dim, output_dim)
        
        # 多模态注意力
        self.attention = MultiHeadAttention(embed_dim=output_dim, num_heads=4)
        
        # 融合层
        self.fusion = nn.Sequential(
            nn.Linear(output_dim * 4, output_dim),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(output_dim, output_dim)
        )
        
        # 模态权重（可学习）
        self.modal_weights = nn.Parameter(torch.tensor([0.3, 0.3, 0.2, 0.2]))
    
    def forward(self, text_feat: torch.Tensor, audio_feat: torch.Tensor, 
                visual_feat: torch.Tensor, behavior_feat: torch.Tensor) -> torch.Tensor:
        """
        多模态特征融合前向传播
        """
        # 投影到相同维度
        t = self.text_proj(text_feat).unsqueeze(1)
        a = self.audio_proj(audio_feat).unsqueeze(1)
        v = self.visual_proj(visual_feat).unsqueeze(1)
        b = self.behavior_proj(behavior_feat).unsqueeze(1)
        
        # 拼接后做自注意力
        combined = torch.cat([t, a, v, b], dim=1)
        attended, _ = self.attention(combined, combined, combined)
        
        # 加权融合（基于论文公式4-4）
        weights = F.softmax(self.modal_weights, dim=0)
        weighted = weights[0] * attended[:, 0] + weights[1] * attended[:, 1] + \
                   weights[2] * attended[:, 2] + weights[3] * attended[:, 3]
        
        # 最终融合
        return self.fusion(torch.cat([weighted, attended.mean(dim=1)], dim=-1))


class LearnableBlend(nn.Module):
    """
    可学习的混合权重网络
    根据用户特征和上下文动态计算各推荐源的权重
    """
    
    def __init__(self, input_dim: int = 128, num_experts: int = 4):
        super().__init__()
        
        self.gate = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.ReLU(),
            nn.Linear(64, num_experts),
            nn.Softmax(dim=-1)
        )
    
    def forward(self, user_features: torch.Tensor, context_features: torch.Tensor) -> torch.Tensor:
        """计算可学习的混合权重"""
        combined = torch.cat([user_features, context_features], dim=-1)
        return self.gate(combined)


class DeepPredictor(nn.Module):
    """通用深度预测器"""
    
    def __init__(self, input_dim: int, hidden_dim: int = 256, output_dim: int = 1):
        super().__init__()
        
        self.predictor = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, output_dim),
            nn.Sigmoid()
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.predictor(x)