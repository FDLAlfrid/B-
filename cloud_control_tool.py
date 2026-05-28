"""
云端调控管理工具 - 智能音乐推荐与分享系统（融合版）
用于管理和查看每个用户的推荐模型、模型参数权重等
"""
import json
import os
import sys
import time
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTabWidget, QListWidget, QListWidgetItem, QLabel, QLineEdit, 
    QPushButton, QTableWidget, QTableWidgetItem, QSpinBox, 
    QDoubleSpinBox, QTextEdit, QMessageBox, QFileDialog, QCheckBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from services.cloud_control import CloudControl
from config import CLOUD_SERVER_URL, CLOUD_CONTROL_ENABLED

class CloudControlTool(QMainWindow):
    """云端调控管理工具"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("云端调控管理工具")
        self.setGeometry(100, 100, 1200, 800)
        self.cloud_control = CloudControl()
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        # 主布局
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        
        # 连接状态
        status_layout = QHBoxLayout()
        self.status_label = QLabel("连接状态: 未连接")
        self.connect_button = QPushButton("连接服务器")
        self.connect_button.clicked.connect(self.connect_to_server)
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.connect_button)
        main_layout.addLayout(status_layout)
        
        # 标签页
        self.tab_widget = QTabWidget()
        self.tab_widget.addTab(self.create_users_tab(), "用户管理")
        self.tab_widget.addTab(self.create_algorithms_tab(), "算法管理")
        self.tab_widget.addTab(self.create_recommendations_tab(), "推荐管理")
        self.tab_widget.addTab(self.create_settings_tab(), "设置")
        main_layout.addWidget(self.tab_widget)
        
        self.setCentralWidget(central_widget)
    
    def connect_to_server(self):
        """连接服务器"""
        if self.cloud_control.check_server_connection():
            self.status_label.setText("连接状态: 已连接")
            QMessageBox.information(self, "成功", "已成功连接到服务器")
        else:
            self.status_label.setText("连接状态: 未连接")
            QMessageBox.warning(self, "失败", "无法连接到服务器，请检查服务器是否运行")
    
    def create_users_tab(self):
        """创建用户管理标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 用户列表
        user_list_layout = QHBoxLayout()
        user_list_label = QLabel("用户列表:")
        self.user_list = QListWidget()
        self.user_list.itemClicked.connect(self.load_user_data)
        user_list_layout.addWidget(user_list_label)
        user_list_layout.addWidget(self.user_list)
        layout.addLayout(user_list_layout)
        
        # 用户数据
        user_data_layout = QVBoxLayout()
        user_data_label = QLabel("用户数据:")
        self.user_data_text = QTextEdit()
        self.user_data_text.setReadOnly(True)
        user_data_layout.addWidget(user_data_label)
        user_data_layout.addWidget(self.user_data_text)
        layout.addLayout(user_data_layout)
        
        # 操作按钮
        button_layout = QHBoxLayout()
        self.refresh_users_button = QPushButton("刷新用户列表")
        self.refresh_users_button.clicked.connect(self.refresh_users)
        self.export_user_data_button = QPushButton("导出用户数据")
        self.export_user_data_button.clicked.connect(self.export_user_data)
        button_layout.addWidget(self.refresh_users_button)
        button_layout.addWidget(self.export_user_data_button)
        layout.addLayout(button_layout)
        
        return widget
    
    def create_algorithms_tab(self):
        """创建算法管理标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 算法列表
        algorithm_list_layout = QHBoxLayout()
        algorithm_list_label = QLabel("算法列表:")
        self.algorithm_list = QListWidget()
        self.algorithm_list.itemClicked.connect(self.load_algorithm_data)
        algorithm_list_layout.addWidget(algorithm_list_label)
        algorithm_list_layout.addWidget(self.algorithm_list)
        layout.addLayout(algorithm_list_layout)
        
        # 算法参数
        algorithm_params_layout = QVBoxLayout()
        algorithm_params_label = QLabel("算法参数:")
        self.algorithm_params_table = QTableWidget()
        self.algorithm_params_table.setColumnCount(2)
        self.algorithm_params_table.setHorizontalHeaderLabels(["参数名", "参数值"])
        algorithm_params_layout.addWidget(algorithm_params_label)
        algorithm_params_layout.addWidget(self.algorithm_params_table)
        layout.addLayout(algorithm_params_layout)
        
        # 操作按钮
        button_layout = QHBoxLayout()
        self.refresh_algorithms_button = QPushButton("刷新算法列表")
        self.refresh_algorithms_button.clicked.connect(self.refresh_algorithms)
        self.update_algorithm_button = QPushButton("更新算法")
        self.update_algorithm_button.clicked.connect(self.update_algorithm)
        button_layout.addWidget(self.refresh_algorithms_button)
        button_layout.addWidget(self.update_algorithm_button)
        layout.addLayout(button_layout)
        
        return widget
    
    def create_recommendations_tab(self):
        """创建推荐管理标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 推荐设置
        recommend_settings_layout = QHBoxLayout()
        recommend_limit_label = QLabel("推荐数量:")
        self.recommend_limit = QSpinBox()
        self.recommend_limit.setMinimum(1)
        self.recommend_limit.setMaximum(50)
        self.recommend_limit.setValue(20)
        recommend_settings_layout.addWidget(recommend_limit_label)
        recommend_settings_layout.addWidget(self.recommend_limit)
        layout.addLayout(recommend_settings_layout)
        
        # 推荐结果
        recommend_results_layout = QVBoxLayout()
        recommend_results_label = QLabel("推荐结果:")
        self.recommend_results_table = QTableWidget()
        self.recommend_results_table.setColumnCount(3)
        self.recommend_results_table.setHorizontalHeaderLabels(["BV号", "标题", "分数"])
        recommend_results_layout.addWidget(recommend_results_label)
        recommend_results_layout.addWidget(self.recommend_results_table)
        layout.addLayout(recommend_results_layout)
        
        # 操作按钮
        button_layout = QHBoxLayout()
        self.get_hot_recommendations_button = QPushButton("获取热门推荐")
        self.get_hot_recommendations_button.clicked.connect(self.get_hot_recommendations)
        self.clear_recommendations_button = QPushButton("清空推荐")
        self.clear_recommendations_button.clicked.connect(self.clear_recommendations)
        button_layout.addWidget(self.get_hot_recommendations_button)
        button_layout.addWidget(self.clear_recommendations_button)
        layout.addLayout(button_layout)
        
        return widget
    
    def create_settings_tab(self):
        """创建设置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 服务器设置
        server_settings_layout = QVBoxLayout()
        server_settings_label = QLabel("服务器设置:")
        server_url_layout = QHBoxLayout()
        server_url_label = QLabel("服务器地址:")
        self.server_url_edit = QLineEdit(CLOUD_SERVER_URL)
        server_url_layout.addWidget(server_url_label)
        server_url_layout.addWidget(self.server_url_edit)
        server_settings_layout.addWidget(server_settings_label)
        server_settings_layout.addLayout(server_url_layout)
        layout.addLayout(server_settings_layout)
        
        # 同步设置
        sync_settings_layout = QVBoxLayout()
        sync_settings_label = QLabel("同步设置:")
        sync_interval_layout = QHBoxLayout()
        sync_interval_label = QLabel("同步间隔(秒):")
        self.sync_interval_spin = QSpinBox()
        self.sync_interval_spin.setMinimum(60)
        self.sync_interval_spin.setMaximum(86400)
        self.sync_interval_spin.setValue(3600)
        sync_interval_layout.addWidget(sync_interval_label)
        sync_interval_layout.addWidget(self.sync_interval_spin)
        algorithm_update_interval_layout = QHBoxLayout()
        algorithm_update_interval_label = QLabel("算法更新间隔(秒):")
        self.algorithm_update_interval_spin = QSpinBox()
        self.algorithm_update_interval_spin.setMinimum(3600)
        self.algorithm_update_interval_spin.setMaximum(604800)
        self.algorithm_update_interval_spin.setValue(86400)
        algorithm_update_interval_layout.addWidget(algorithm_update_interval_label)
        algorithm_update_interval_layout.addWidget(self.algorithm_update_interval_spin)
        sync_settings_layout.addWidget(sync_settings_label)
        sync_settings_layout.addLayout(sync_interval_layout)
        sync_settings_layout.addLayout(algorithm_update_interval_layout)
        layout.addLayout(sync_settings_layout)
        
        # 操作按钮
        button_layout = QHBoxLayout()
        self.save_settings_button = QPushButton("保存设置")
        self.save_settings_button.clicked.connect(self.save_settings)
        self.load_settings_button = QPushButton("加载设置")
        self.load_settings_button.clicked.connect(self.load_settings)
        button_layout.addWidget(self.save_settings_button)
        button_layout.addWidget(self.load_settings_button)
        layout.addLayout(button_layout)
        
        return widget
    
    def refresh_users(self):
        """刷新用户列表"""
        # 这里应该从服务器获取用户列表
        # 暂时使用模拟数据
        self.user_list.clear()
        users = ["用户1", "用户2", "用户3", "游客"]
        for user in users:
            item = QListWidgetItem(user)
            self.user_list.addItem(item)
    
    def load_user_data(self, item):
        """加载用户数据"""
        user_name = item.text()
        # 这里应该从服务器获取用户数据
        # 暂时使用模拟数据
        user_data = {
            "user_id": 1,
            "user_name": user_name,
            "preferences": {
                "singers": ["洛天依", "乐正绫"],
                "genres": ["流行", "摇滚"]
            },
            "behavior_data": {
                "play_count": 100,
                "collect_count": 20,
                "like_count": 50
            },
            "recommend_weights": {
                "collaborative": 0.4,
                "ip_driven": 0.3,
                "content": 0.2,
                "hot": 0.1
            }
        }
        self.user_data_text.setText(json.dumps(user_data, ensure_ascii=False, indent=2))
    
    def export_user_data(self):
        """导出用户数据"""
        file_path, _ = QFileDialog.getSaveFileName(self, "导出用户数据", "", "JSON Files (*.json)")
        if file_path:
            try:
                user_data = json.loads(self.user_data_text.toPlainText())
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(user_data, f, ensure_ascii=False, indent=2)
                QMessageBox.information(self, "成功", "用户数据导出成功")
            except Exception as e:
                QMessageBox.warning(self, "失败", f"导出用户数据失败: {e}")
    
    def refresh_algorithms(self):
        """刷新算法列表"""
        # 这里应该从服务器获取算法列表
        # 暂时使用模拟数据
        self.algorithm_list.clear()
        algorithms = ["协同过滤算法", "IP驱动算法", "内容推荐算法", "热门推荐算法"]
        for algorithm in algorithms:
            item = QListWidgetItem(algorithm)
            self.algorithm_list.addItem(item)
    
    def load_algorithm_data(self, item):
        """加载算法数据"""
        algorithm_name = item.text()
        # 这里应该从服务器获取算法参数
        # 暂时使用模拟数据
        params = {
            "协同过滤算法": {
                "similarity_threshold": 0.5,
                "neighborhood_size": 10
            },
            "IP驱动算法": {
                "singer_weight": 0.4,
                "up_weight": 0.3,
                "tag_weight": 0.1,
                "emotion_weight": 0.1,
                "genre_weight": 0.1
            },
            "内容推荐算法": {
                "title_weight": 0.5,
                "tag_weight": 0.3,
                "description_weight": 0.2
            },
            "热门推荐算法": {
                "play_weight": 0.5,
                "comment_weight": 0.3,
                "collect_weight": 0.2
            }
        }
        
        algorithm_params = params.get(algorithm_name, {})
        self.algorithm_params_table.setRowCount(len(algorithm_params))
        row = 0
        for param_name, param_value in algorithm_params.items():
            self.algorithm_params_table.setItem(row, 0, QTableWidgetItem(param_name))
            self.algorithm_params_table.setItem(row, 1, QTableWidgetItem(str(param_value)))
            row += 1
    
    def update_algorithm(self):
        """更新算法"""
        selected_item = self.algorithm_list.currentItem()
        if not selected_item:
            QMessageBox.warning(self, "警告", "请选择一个算法")
            return
        
        algorithm_name = selected_item.text()
        # 这里应该更新服务器上的算法参数
        # 暂时使用模拟数据
        QMessageBox.information(self, "成功", f"算法 {algorithm_name} 更新成功")
    
    def get_hot_recommendations(self):
        """获取热门推荐"""
        limit = self.recommend_limit.value()
        recommendations = self.cloud_control.get_hot_recommendations(limit)
        self.recommend_results_table.setRowCount(len(recommendations))
        row = 0
        for recommendation in recommendations:
            bvid = recommendation.get('bvid', '')
            title = recommendation.get('title', '')
            score = recommendation.get('score', 0)
            self.recommend_results_table.setItem(row, 0, QTableWidgetItem(bvid))
            self.recommend_results_table.setItem(row, 1, QTableWidgetItem(title))
            self.recommend_results_table.setItem(row, 2, QTableWidgetItem(str(score)))
            row += 1
    
    def clear_recommendations(self):
        """清空推荐"""
        self.recommend_results_table.setRowCount(0)
    
    def save_settings(self):
        """保存设置"""
        settings = {
            "server_url": self.server_url_edit.text(),
            "sync_interval": self.sync_interval_spin.value(),
            "algorithm_update_interval": self.algorithm_update_interval_spin.value()
        }
        try:
            with open('cloud_control_settings.json', 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "成功", "设置保存成功")
        except Exception as e:
            QMessageBox.warning(self, "失败", f"保存设置失败: {e}")
    
    def load_settings(self):
        """加载设置"""
        try:
            with open('cloud_control_settings.json', 'r', encoding='utf-8') as f:
                settings = json.load(f)
                self.server_url_edit.setText(settings.get('server_url', CLOUD_SERVER_URL))
                self.sync_interval_spin.setValue(settings.get('sync_interval', 3600))
                self.algorithm_update_interval_spin.setValue(settings.get('algorithm_update_interval', 86400))
            QMessageBox.information(self, "成功", "设置加载成功")
        except Exception as e:
            QMessageBox.warning(self, "失败", f"加载设置失败: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CloudControlTool()
    window.show()
    sys.exit(app.exec_())