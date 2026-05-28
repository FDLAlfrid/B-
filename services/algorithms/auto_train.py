"""
自动训练管理器 - 支持后台自动预训练和参数调整

功能：
1. 自动检测模型是否需要训练
2. 支持学习率自动调度
3. 早停机制
4. 后台异步训练
5. 参数自动调优
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torch.optim.lr_scheduler import ReduceLROnPlateau, CosineAnnealingLR
import os
import json
import numpy as np
import threading
import time
from typing import List, Tuple, Dict, Optional, Callable


class AutoTrainManager:
    """自动训练管理器"""
    
    def __init__(self, model_dir: str = None, auto_train: bool = True, 
                 auto_tune: bool = True, device: str = 'auto'):
        """
        初始化自动训练管理器
        
        :param model_dir: 模型保存目录
        :param auto_train: 是否自动训练（检测到模型不存在时）
        :param auto_tune: 是否自动调参
        :param device: 训练设备 ('auto', 'cuda', 'cpu')
        """
        if model_dir is None:
            model_dir = os.path.join(os.path.dirname(__file__), 'models')
        
        self.model_dir = model_dir
        self.auto_train = auto_train
        self.auto_tune = auto_tune
        self.device = self._get_device(device)
        
        os.makedirs(model_dir, exist_ok=True)
        
        # 训练状态
        self.training_in_progress = False
        self.training_thread = None
        
        # 最佳参数记录
        self.best_params = {}
        
        # 默认超参数搜索空间
        self.hyperparam_space = {
            'lr': [0.0001, 0.001, 0.01],
            'batch_size': [64, 128, 256],
            'embed_dim': [32, 64, 128],
            'num_layers': [2, 3, 4],
            'dropout': [0.1, 0.2, 0.3]
        }
    
    def _get_device(self, device: str) -> torch.device:
        """获取训练设备"""
        if device == 'auto':
            return torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        return torch.device(device)
    
    def model_exists(self, model_name: str) -> bool:
        """检查模型文件是否存在"""
        model_path = os.path.join(self.model_dir, f'{model_name}.pt')
        return os.path.exists(model_path)
    
    def start_background_training(self, model_name: str, train_func: Callable, 
                                  params: Dict = None, callback: Callable = None):
        """
        在后台启动训练
        
        :param model_name: 模型名称
        :param train_func: 训练函数
        :param params: 训练参数
        :param callback: 训练完成回调
        """
        if self.training_in_progress:
            print("训练已在进行中...")
            return False
        
        def training_wrapper():
            self.training_in_progress = True
            try:
                if params is None:
                    if self.auto_tune:
                        best_result = self.hyperparameter_tuning(model_name, train_func)
                        self.best_params[model_name] = best_result['params']
                        print(f"[{model_name}] 最佳参数: {best_result['params']}")
                        print(f"[{model_name}] 最佳指标: {best_result['metric']}")
                    else:
                        train_func()
                else:
                    train_func(**params)
            except Exception as e:
                print(f"训练失败: {e}")
            finally:
                self.training_in_progress = False
                if callback:
                    callback()
        
        self.training_thread = threading.Thread(target=training_wrapper, daemon=True)
        self.training_thread.start()
        return True
    
    def hyperparameter_tuning(self, model_name: str, train_func: Callable, 
                              max_trials: int = 5) -> Dict:
        """
        超参数自动调优（简单网格搜索）
        
        :param model_name: 模型名称
        :param train_func: 训练函数（需返回验证指标）
        :param max_trials: 最大尝试次数
        :return: 最佳参数和指标
        """
        print(f"[{model_name}] 开始超参数调优...")
        
        best_metric = float('-inf')
        best_params = None
        
        space = self.hyperparam_space
        trial_count = 0
        
        # 随机搜索
        for _ in range(max_trials):
            params = {
                'lr': np.random.choice(space['lr']),
                'batch_size': np.random.choice(space['batch_size']),
                'embed_dim': np.random.choice(space['embed_dim']),
                'num_layers': np.random.choice(space['num_layers']),
                'dropout': np.random.choice(space['dropout'])
            }
            
            print(f"[{model_name}] 尝试参数: {params}")
            
            try:
                metric = train_func(**params)
                print(f"[{model_name}] 验证指标: {metric}")
                
                if metric > best_metric:
                    best_metric = metric
                    best_params = params
                    
            except Exception as e:
                print(f"[{model_name}] 参数尝试失败: {e}")
            
            trial_count += 1
        
        return {'params': best_params, 'metric': best_metric}
    
    def ensure_models_trained(self, models: List[str], train_funcs: Dict[str, Callable]):
        """
        确保所有指定模型已训练
        
        :param models: 模型名称列表
        :param train_funcs: 训练函数字典
        """
        print("检查模型状态...")
        
        models_to_train = []
        for model_name in models:
            if not self.model_exists(model_name):
                print(f"模型 {model_name} 不存在，需要训练")
                models_to_train.append(model_name)
        
        if not models_to_train:
            print("所有模型已存在，无需训练")
            return
        
        if not self.auto_train:
            print("自动训练已禁用")
            return
        
        print(f"开始自动训练 {len(models_to_train)} 个模型...")
        
        for model_name in models_to_train:
            if model_name in train_funcs:
                print(f"启动 {model_name} 训练...")
                train_funcs[model_name]()
                print(f"{model_name} 训练完成")
    
    def wait_for_training(self, timeout: Optional[int] = None):
        """等待训练完成"""
        if self.training_thread and self.training_in_progress:
            self.training_thread.join(timeout)
    
    def is_training(self) -> bool:
        """检查是否正在训练"""
        return self.training_in_progress


class AdvancedTrainer:
    """高级训练器 - 带学习率调度和早停"""
    
    def __init__(self, model: nn.Module, criterion: nn.Module, 
                 optimizer: optim.Optimizer, scheduler_type: str = 'plateau',
                 patience: int = 10, min_lr: float = 1e-6):
        """
        初始化高级训练器
        
        :param model: 模型
        :param criterion: 损失函数
        :param optimizer: 优化器
        :param scheduler_type: 调度器类型 ('plateau', 'cosine')
        :param patience: 早停耐心值
        :param min_lr: 最小学习率
        """
        self.model = model
        self.criterion = criterion
        self.optimizer = optimizer
        self.patience = patience
        self.min_lr = min_lr
        
        # 学习率调度器
        if scheduler_type == 'plateau':
            self.scheduler = ReduceLROnPlateau(optimizer, mode='max', factor=0.5, 
                                               patience=patience//2, min_lr=min_lr)
        else:
            self.scheduler = CosineAnnealingLR(optimizer, T_max=10)
        
        # 早停状态
        self.best_metric = float('-inf')
        self.early_stop_counter = 0
        self.early_stopped = False
        
        # 训练记录
        self.train_losses = []
        self.val_metrics = []
    
    def train_epoch(self, dataloader: DataLoader, device: torch.device) -> float:
        """训练一个epoch"""
        self.model.train()
        total_loss = 0.0
        
        for batch in dataloader:
            self.optimizer.zero_grad()
            
            if isinstance(batch, (list, tuple)):
                inputs = [x.to(device) for x in batch[:-1]]
                labels = batch[-1].to(device)
                outputs = self.model(*inputs)
            else:
                inputs = batch.to(device)
                outputs = self.model(inputs)
                labels = inputs  # 自监督任务
            
            loss = self.criterion(outputs, labels)
            loss.backward()
            self.optimizer.step()
            
            total_loss += loss.item() * len(batch[0])
        
        return total_loss / len(dataloader.dataset)
    
    def validate(self, dataloader: DataLoader, device: torch.device, 
                 metric_func: Callable = None) -> float:
        """验证并计算指标"""
        self.model.eval()
        
        if metric_func is None:
            # 默认计算准确率（分类任务）
            correct = 0
            total = 0
            
            with torch.no_grad():
                for batch in dataloader:
                    if isinstance(batch, (list, tuple)):
                        inputs = [x.to(device) for x in batch[:-1]]
                        labels = batch[-1].to(device)
                        outputs = self.model(*inputs)
                    else:
                        inputs = batch.to(device)
                        outputs = self.model(inputs)
                        labels = inputs
                    
                    preds = (outputs > 0.5).float()
                    correct += (preds == labels).sum().item()
                    total += len(labels)
            
            return correct / total if total > 0 else 0.0
        else:
            # 使用自定义指标函数
            return metric_func(self.model, dataloader, device)
    
    def train(self, train_loader: DataLoader, val_loader: DataLoader = None, 
              epochs: int = 100, device: torch.device = None, 
              verbose: bool = True) -> float:
        """
        训练模型
        
        :param train_loader: 训练数据加载器
        :param val_loader: 验证数据加载器
        :param epochs: 训练轮数
        :param device: 训练设备
        :param verbose: 是否打印日志
        :return: 最佳验证指标
        """
        if device is None:
            device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        self.model.to(device)
        
        for epoch in range(epochs):
            # 训练
            train_loss = self.train_epoch(train_loader, device)
            self.train_losses.append(train_loss)
            
            # 验证
            if val_loader:
                val_metric = self.validate(val_loader, device)
                self.val_metrics.append(val_metric)
                
                # 更新学习率
                self.scheduler.step(val_metric)
                
                # 早停检查
                if val_metric > self.best_metric:
                    self.best_metric = val_metric
                    self.early_stop_counter = 0
                    # 保存最佳模型
                    torch.save(self.model.state_dict(), 
                               os.path.join(os.path.dirname(__file__), 'models', 'best_model.pt'))
                else:
                    self.early_stop_counter += 1
                    if self.early_stop_counter >= self.patience:
                        if verbose:
                            print(f"早停触发，最佳指标: {self.best_metric:.4f}")
                        self.early_stopped = True
                        break
                
                if verbose:
                    lr = self.optimizer.param_groups[0]['lr']
                    print(f"Epoch [{epoch+1}/{epochs}] | "
                          f"Loss: {train_loss:.4f} | "
                          f"Val Metric: {val_metric:.4f} | "
                          f"LR: {lr:.6f}")
            else:
                if verbose:
                    print(f"Epoch [{epoch+1}/{epochs}] | Loss: {train_loss:.4f}")
        
        return self.best_metric


# 全局自动训练管理器实例
auto_train_manager = AutoTrainManager(auto_train=True, auto_tune=True)


def auto_train_all_models(background: bool = True):
    """
    自动训练所有模型
    
    :param background: 是否在后台运行
    """
    from .train_deep_models import train_ncf_model, train_gcn_model, train_ranking_model
    
    models_to_train = ['ncf_model', 'gcn_model', 'ranking_model']
    train_funcs = {
        'ncf_model': train_ncf_model,
        'gcn_model': train_gcn_model,
        'ranking_model': train_ranking_model
    }
    
    if background:
        # 后台异步训练
        def train_all():
            auto_train_manager.ensure_models_trained(models_to_train, train_funcs)
        
        threading.Thread(target=train_all, daemon=True).start()
        print("后台自动训练已启动...")
    else:
        # 同步训练
        auto_train_manager.ensure_models_trained(models_to_train, train_funcs)


def setup_auto_training_on_startup():
    """
    在应用启动时设置自动训练
    
    使用方法：在应用入口处调用此函数
    """
    # 检查是否需要训练
    models_needed = ['ncf_model', 'gcn_model', 'ranking_model']
    needs_training = any(not auto_train_manager.model_exists(m) for m in models_needed)
    
    if needs_training and auto_train_manager.auto_train:
        print("检测到需要训练的模型，启动后台自动训练...")
        auto_train_all_models(background=True)
    else:
        print("所有模型已就绪，无需训练")


if __name__ == '__main__':
    # 示例：手动触发自动训练
    print("启动自动训练管理器...")
    setup_auto_training_on_startup()
    
    # 保持进程运行（模拟应用运行）
    while auto_train_manager.is_training():
        print(f"训练中... ({time.strftime('%H:%M:%S')})")
        time.sleep(10)