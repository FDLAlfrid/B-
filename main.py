import sys
import os
import json
import threading
import time
from datetime import datetime
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QLineEdit, QComboBox, QTabWidget, QScrollArea, QListWidget, 
    QListWidgetItem, QMessageBox, QDialog, QCheckBox, QTextEdit, QMenu,
    QGridLayout, QSpacerItem, QSizePolicy, QGroupBox, QFrame, QSystemTrayIcon,
    QAction, QRadioButton, QSpinBox
)
from PyQt5.QtGui import QFont, QColor, QPixmap, QIcon
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QObject
import requests
import webbrowser
from urllib.parse import urlencode

from services.user_auth import user_auth
from services.recommend_engine.traditional import RecommendService
from services.recommend_engine.intelligent import IntelligentRecommendEngine
from services.recommend_engine.advanced import AdvancedRecommendEngine
from services.api_server import start_api_server, stop_api_server
from services.cloud_control import CloudControl
from services.share import ShareService
from services.community import get_community_system
from utils.data_manager import (
    load_settings, save_settings, load_favorites, save_favorites,
    load_excluded, save_excluded, load_favorites_and_excluded,
    save_favorites_and_excluded, load_playlists, save_playlists,
    load_share_history, save_share_history, add_share_record
)
from utils.logger import get_logger
from utils.constants import THEMES

logger = get_logger(__name__)

class CoverCache:
    """封面图片缓存管理器 - 优化版"""
    _instance = None
    _cache = {}
    _cache_dir = None
    _max_memory_cache = 100  # 最大内存缓存数量
    _access_order = []  # LRU访问顺序
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._cache_dir = os.path.join(os.path.dirname(__file__), 'data', 'cover_cache')
            if not os.path.exists(cls._cache_dir):
                os.makedirs(cls._cache_dir)
            # 预加载常用尺寸的图片缓存
            cls._preload_common_cache()
        return cls._instance
    
    @classmethod
    def _preload_common_cache(cls):
        """预加载文件缓存到内存"""
        if not os.path.exists(cls._cache_dir):
            return
        try:
            # 只加载最近修改的20个缓存文件
            cache_files = []
            for f in os.listdir(cls._cache_dir):
                if f.endswith('.jpg'):
                    filepath = os.path.join(cls._cache_dir, f)
                    cache_files.append((filepath, os.path.getmtime(filepath)))
            
            # 按修改时间排序，加载最新的20个
            cache_files.sort(key=lambda x: x[1], reverse=True)
            for filepath, _ in cache_files[:20]:
                try:
                    pixmap = QPixmap(filepath)
                    if not pixmap.isNull():
                        # 从文件名反推URL（简化处理）
                        url_hash = os.path.basename(filepath).replace('.jpg', '')
                        cls._cache[url_hash] = pixmap
                        cls._access_order.append(url_hash)
                except:
                    pass
        except Exception as e:
            logger.error(f"预加载缓存失败: {e}")
    
    def get_cache_path(self, url):
        """获取缓存文件路径"""
        import hashlib
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return os.path.join(self._cache_dir, f"{url_hash}.jpg"), url_hash
    
    def get(self, url):
        """从缓存获取图片 - LRU策略"""
        cache_path, url_hash = self.get_cache_path(url)
        
        # 先检查内存缓存
        if url_hash in self._cache:
            # 更新访问顺序
            if url_hash in self._access_order:
                self._access_order.remove(url_hash)
            self._access_order.append(url_hash)
            return self._cache[url_hash]
        
        # 检查文件缓存
        if os.path.exists(cache_path):
            try:
                pixmap = QPixmap(cache_path)
                if not pixmap.isNull():
                    # 添加到内存缓存
                    self._add_to_cache(url_hash, pixmap)
                    return pixmap
            except:
                pass
        
        return None
    
    def _add_to_cache(self, url_hash, pixmap):
        """添加图片到内存缓存，使用LRU淘汰策略"""
        # 如果缓存已满，淘汰最久未使用的
        while len(self._cache) >= self._max_memory_cache and self._access_order:
            oldest = self._access_order.pop(0)
            if oldest in self._cache:
                del self._cache[oldest]
        
        self._cache[url_hash] = pixmap
        self._access_order.append(url_hash)
    
    def set(self, url, pixmap):
        """保存图片到缓存"""
        cache_path, url_hash = self.get_cache_path(url)
        
        # 添加到内存缓存
        self._add_to_cache(url_hash, pixmap)
        
        # 异步保存到文件
        def save_to_file():
            try:
                pixmap.save(cache_path, "JPG", quality=85)
            except Exception as e:
                logger.error(f"保存缓存文件失败: {e}")
        
        threading.Thread(target=save_to_file, daemon=True).start()
    
    def batch_load(self, urls, max_workers=4):
        """批量加载图片，使用线程池"""
        results = {}
        
        def load_single(url):
            try:
                # 先检查缓存
                cached = self.get(url)
                if cached:
                    return url, cached
                
                # 处理URL格式
                full_url = url
                if full_url.startswith('//'):
                    full_url = 'https:' + full_url
                elif not full_url.startswith('http://') and not full_url.startswith('https://'):
                    full_url = 'https://' + full_url
                
                response = requests.get(full_url, timeout=10)
                if response.status_code == 200:
                    pixmap = QPixmap()
                    pixmap.loadFromData(response.content)
                    if not pixmap.isNull():
                        pixmap = pixmap.scaled(800, 450, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        self.set(url, pixmap)
                        return url, pixmap
            except Exception as e:
                logger.error(f"批量加载封面失败 {url}: {e}")
            return url, None
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {executor.submit(load_single, url): url for url in urls}
            for future in as_completed(future_to_url):
                url, pixmap = future.result()
                if pixmap:
                    results[url] = pixmap
        
        return results

class CoverLoaderThread(QThread):
    """封面图片加载线程 - 优化版"""
    finished = pyqtSignal(int, QPixmap, str)  # 添加URL参数
    
    def __init__(self, url, index, parent=None):
        super().__init__(parent)
        self.url = url
        self.idx = index
        self.cache = CoverCache()
        self._is_running = True
    
    def stop(self):
        """安全停止线程"""
        self._is_running = False
        self.wait(100)  # 等待100ms
    
    def run(self):
        if not self._is_running:
            return
            
        try:
            # 先检查缓存
            cached_pixmap = self.cache.get(self.url)
            if cached_pixmap:
                if self._is_running:
                    self.finished.emit(self.idx, cached_pixmap, self.url)
                return
            
            # 处理URL格式，添加协议
            url = self.url
            if url.startswith('//'):
                url = 'https:' + url
            elif not url.startswith('http://') and not url.startswith('https://'):
                url = 'https://' + url
            
            response = requests.get(url, timeout=8)  # 减少超时时间
            if not self._is_running:
                return
                
            if response.status_code == 200:
                pixmap = QPixmap()
                pixmap.loadFromData(response.content)
                if not pixmap.isNull():
                    # 调整图片大小
                    pixmap = pixmap.scaled(800, 450, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    # 保存到缓存
                    self.cache.set(self.url, pixmap)
                    if self._is_running:
                        self.finished.emit(self.idx, pixmap, self.url)
        except Exception as e:
            logger.error(f"加载封面失败: {e}")


class CoverUpdateSignal(QObject):
    """封面更新信号类 - 用于跨线程UI更新"""
    update_cover = pyqtSignal(str, QPixmap)  # URL, Pixmap

class BVToolsDialog(QDialog):
    """BV工具对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("BV工具")
        self.setFixedSize(800, 600)
        self.genshin_font = parent.genshin_font
        self.settings = parent.settings
        self.current_theme = parent.current_theme
        self.themes = parent.themes
        self.cover_threads = []
        self.apply_theme()
        self.setup_ui()
    
    def apply_theme(self):
        """应用主题样式"""
        # 获取显示模式
        display_mode = self.settings.get('display_mode', 'light')
        
        # 获取主题颜色
        if self.current_theme == 'custom':
            custom_color = self.settings.get('custom_theme_color', '#3498db')
            primary_color = custom_color
            # 生成次要颜色（稍微暗一点）
            try:
                from PyQt5.QtGui import QColor
                color = QColor(custom_color)
                secondary_color = color.darker(120).name()
            except:
                secondary_color = '#2980b9'
            if display_mode == 'dark':
                background_color = '#121212'
                text_color = '#e0e0e0'
            else:
                background_color = '#f5f5f5'
                text_color = '#2c3e50'
        else:
            theme = self.themes.get(self.current_theme, self.themes['默认主题'])
            primary_color = theme['primary']
            secondary_color = theme['secondary']
            if display_mode == 'dark':
                background_color = '#121212'
                text_color = '#e0e0e0'
            else:
                background_color = theme['background']
                text_color = theme['text']
        
        # 构建样式表
        if display_mode == 'dark':
            # 深色主题色彩
            border_color = '#404040'
            widget_bg = '#1a1a1a'
            input_bg = '#262626'
            tab_bg = '#212121'
            tab_text = '#f0f0f0'
            group_box_text = '#f0f0f0'
            scroll_bg = '#1a1a1a'
            scroll_border = '#404040'
            line_edit_bg = '#2a2a2a'
            line_edit_border = '#505050'
            combo_bg = '#2a2a2a'
            combo_border = '#505050'
            recommend_bg = 'rgba(42, 42, 42, 0.9)'
            card_bg = '#2d2d2d'
            hover_bg = '#3a3a3a'
            active_bg = '#4a4a4a'
            separator_color = '#555555'
        else:
            # 浅色主题色彩
            border_color = '#e0e0e0'
            widget_bg = '#ffffff'
            input_bg = '#ffffff'
            tab_bg = '#f8f9fa'
            tab_text = '#495057'
            group_box_text = '#2c3e50'
            scroll_bg = 'white'
            scroll_border = '#e0e0e0'
            line_edit_bg = 'white'
            line_edit_border = '#e0e0e0'
            combo_bg = '#f9f9f9'
            combo_border = '#e0e0e0'
            recommend_bg = 'rgba(255, 255, 255, 0.8)'
            card_bg = '#f8f9fa'
            hover_bg = '#e9ecef'
            active_bg = '#dee2e6'
            separator_color = '#ced4da'
        
        style_sheet = f"""
            QDialog {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {background_color}, stop:1 {secondary_color});
                font-family: 'Microsoft YaHei', 'SimHei', sans-serif;
                color: {text_color};
            }}
            QScrollArea {{
                border: none;
                background: transparent;
            }}
            QScrollBar:vertical {{
                border: none;
                background: {scroll_bg};
                width: 10px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background: {hover_bg};
                border-radius: 5px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {active_bg};
            }}
            QLabel {{
                color: {text_color};
                background: transparent;
            }}
            QGroupBox {{
                background: {card_bg};
                border: 2px solid {border_color};
                border-radius: 8px;
                color: {group_box_text};
            }}
            QCheckBox {{
                color: {text_color};
                background: transparent;
            }}
            QComboBox {{
                background: {combo_bg};
                border: 2px solid {combo_border};
                color: {text_color};
            }}
        """
        
        self.setStyleSheet(style_sheet)
        
        # 更新搜索框和排序下拉框的样式
        if hasattr(self, 'search_input'):
            self.search_input.setStyleSheet(f"""
                QLineEdit {{
                    padding: 12px;
                    border: 2px solid {line_edit_border};
                    border-radius: 8px;
                    font-size: 14px;
                    background: {line_edit_bg};
                    color: {text_color};
                }}
                QLineEdit:focus {{
                    border: 2px solid {primary_color};
                    background: {line_edit_bg};
                }}
            """)
        
        if hasattr(self, 'sort_combo'):
            self.sort_combo.setStyleSheet(f"""
                QComboBox {{
                    padding: 12px;
                    border: 2px solid {combo_border};
                    border-radius: 8px;
                    font-size: 14px;
                    background: {combo_bg};
                    color: {text_color};
                }}
                QComboBox:focus {{
                    border: 2px solid {primary_color};
                    background: {combo_bg};
                }}
                QComboBox::drop-down {{
                    border: none;
                }}
                QComboBox::down-arrow {{
                    width: 20px;
                    height: 20px;
                }}
            """)
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title_label = QLabel("BV工具")
        title_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #2c3e50;")
        title_label.setFont(self.genshin_font)
        layout.addWidget(title_label)
        
        # 输入框
        input_layout = QHBoxLayout()
        input_layout.setSpacing(10)
        
        bv_label = QLabel("BV号:")
        bv_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #2c3e50;")
        bv_label.setFont(self.genshin_font)
        input_layout.addWidget(bv_label)
        
        self.bv_input = QLineEdit()
        self.bv_input.setPlaceholderText("请输入BV号")
        self.bv_input.setFont(self.genshin_font)
        input_layout.addWidget(self.bv_input)
        
        search_btn = QPushButton("查询")
        search_btn.setFont(self.genshin_font)
        search_btn.clicked.connect(self.search_bv)
        input_layout.addWidget(search_btn)
        
        layout.addLayout(input_layout)
        
        # 结果区域
        self.result_area = QTextEdit()
        self.result_area.setReadOnly(True)
        self.result_area.setFont(self.genshin_font)
        layout.addWidget(self.result_area)
        
        # 按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        self.download_btn = QPushButton("下载")
        self.download_btn.setFont(self.genshin_font)
        self.download_btn.clicked.connect(self.download_video)
        button_layout.addWidget(self.download_btn)
        
        self.add_to_playlist_btn = QPushButton("添加到播放列表")
        self.add_to_playlist_btn.setFont(self.genshin_font)
        self.add_to_playlist_btn.clicked.connect(self.add_to_playlist)
        button_layout.addWidget(self.add_to_playlist_btn)
        
        self.clear_btn = QPushButton("清空")
        self.clear_btn.setFont(self.genshin_font)
        self.clear_btn.clicked.connect(lambda: self.result_area.clear())
        button_layout.addWidget(self.clear_btn)
        
        self.copy_btn = QPushButton("复制")
        self.copy_btn.setFont(self.genshin_font)
        self.copy_btn.clicked.connect(self.copy_result)
        button_layout.addWidget(self.copy_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
    
    def search_bv(self):
        bv = self.bv_input.text().strip()
        if not bv:
            QMessageBox.warning(self, "提示", "请输入BV号")
            return
        
        try:
            # 这里可以添加BV号解析逻辑
            result = f"BV号: {bv}\n" 
            result += f"解析结果: 这是一个BV号查询工具\n"
            result += f"功能开发中..."
            self.result_area.setText(result)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"查询失败: {str(e)}")
    
    def download_video(self):
        bv = self.bv_input.text().strip()
        if not bv:
            QMessageBox.warning(self, "提示", "请输入BV号")
            return
        
        try:
            # 这里可以添加下载逻辑
            result = f"BV号: {bv}\n" 
            result += f"下载功能开发中...\n"
            result += f"将支持批量下载和缓存功能"
            self.result_area.setText(result)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"下载失败: {str(e)}")
    
    def add_to_playlist(self):
        bv = self.bv_input.text().strip()
        if not bv:
            QMessageBox.warning(self, "提示", "请输入BV号")
            return
        
        try:
            # 添加到播放列表
            result = f"BV号: {bv}\n" 
            result += f"添加到播放列表功能开发中...\n"
            result += f"将支持批量选择和缓存"
            self.result_area.setText(result)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"添加失败: {str(e)}")
    
    def copy_result(self):
        text = self.result_area.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            QMessageBox.information(self, "成功", "已复制到剪贴板")

class LoginDialog(QDialog):
    """登录对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("用户登录")
        self.setMinimumSize(420, 380)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        # 使用更大的字体
        self.genshin_font = QFont("Microsoft YaHei", 12, QFont.Medium)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        title_label = QLabel("🔐 用户登录")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFont(QFont("Microsoft YaHei", 20, QFont.Bold))
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #2c3e50; padding: 10px;")
        layout.addWidget(title_label)

        # 用户名
        username_label = QLabel("用户名:")
        username_label.setFont(QFont("Microsoft YaHei", 13, QFont.Medium))
        username_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(username_label)
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("请输入用户名")
        self.username_input.setFont(QFont("Microsoft YaHei", 13))
        self.username_input.setMinimumHeight(45)
        self.username_input.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                font-size: 14px;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                background: white;
            }
            QLineEdit:focus {
                border: 2px solid #3498db;
            }
        """)
        layout.addWidget(self.username_input)

        # 密码
        password_label = QLabel("密码:")
        password_label.setFont(QFont("Microsoft YaHei", 13, QFont.Medium))
        password_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(password_label)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("请输入密码")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setFont(QFont("Microsoft YaHei", 13))
        self.password_input.setMinimumHeight(45)
        self.password_input.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                font-size: 14px;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                background: white;
            }
            QLineEdit:focus {
                border: 2px solid #3498db;
            }
        """)
        layout.addWidget(self.password_input)

        layout.addSpacing(10)

        # 按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        
        self.login_btn = QPushButton("✓ 登录")
        self.login_btn.setFont(QFont("Microsoft YaHei", 13, QFont.Bold))
        self.login_btn.setMinimumHeight(45)
        self.login_btn.setStyleSheet("""
            QPushButton {
                padding: 12px 25px;
                font-size: 15px;
                font-weight: bold;
                color: white;
                background: #3498db;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover {
                background: #2980b9;
            }
        """)
        self.login_btn.clicked.connect(self.on_login)
        button_layout.addWidget(self.login_btn)

        self.cancel_btn = QPushButton("✕ 取消")
        self.cancel_btn.setFont(QFont("Microsoft YaHei", 13))
        self.cancel_btn.setMinimumHeight(45)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                padding: 12px 25px;
                font-size: 15px;
                color: #666666;
                background: #f0f0f0;
                border: 2px solid #d0d0d0;
                border-radius: 8px;
            }
            QPushButton:hover {
                background: #e0e0e0;
            }
        """)
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFont(QFont("Microsoft YaHei", 11))
        self.status_label.setStyleSheet("color: #e74c3c; font-size: 13px;")
        layout.addWidget(self.status_label)

        # 预填充默认账号
        self.username_input.setText("admin")
        self.password_input.setText("admin123")
    
    def on_login(self):
        """登录处理"""
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()

        if not username or not password:
            self.status_label.setText("请输入用户名和密码")
            return

        # 只验证用户存在，不在这里调用user_auth.login
        # 验证逻辑移到MainWindow.show_login_dialog中统一处理
        self.accept()


class RegisterDialog(QDialog):
    """注册对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("用户注册")
        self.setMinimumSize(420, 420)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)

        title_label = QLabel("📝 用户注册")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFont(QFont("Microsoft YaHei", 20, QFont.Bold))
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #2c3e50; padding: 10px;")
        layout.addWidget(title_label)

        # 用户名
        username_label = QLabel("用户名:")
        username_label.setFont(QFont("Microsoft YaHei", 13, QFont.Medium))
        username_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(username_label)
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("请输入用户名（3-20个字符）")
        self.username_input.setFont(QFont("Microsoft YaHei", 13))
        self.username_input.setMinimumHeight(45)
        self.username_input.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                font-size: 14px;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                background: white;
            }
            QLineEdit:focus {
                border: 2px solid #2ecc71;
            }
        """)
        layout.addWidget(self.username_input)

        # 密码
        password_label = QLabel("密码:")
        password_label.setFont(QFont("Microsoft YaHei", 13, QFont.Medium))
        password_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(password_label)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("请输入密码（至少6个字符）")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setFont(QFont("Microsoft YaHei", 13))
        self.password_input.setMinimumHeight(45)
        self.password_input.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                font-size: 14px;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                background: white;
            }
            QLineEdit:focus {
                border: 2px solid #2ecc71;
            }
        """)
        layout.addWidget(self.password_input)

        # 确认密码
        confirm_label = QLabel("确认密码:")
        confirm_label.setFont(QFont("Microsoft YaHei", 13, QFont.Medium))
        confirm_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(confirm_label)
        
        self.confirm_input = QLineEdit()
        self.confirm_input.setPlaceholderText("请再次输入密码")
        self.confirm_input.setEchoMode(QLineEdit.Password)
        self.confirm_input.setFont(QFont("Microsoft YaHei", 13))
        self.confirm_input.setMinimumHeight(45)
        self.confirm_input.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                font-size: 14px;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                background: white;
            }
            QLineEdit:focus {
                border: 2px solid #2ecc71;
            }
        """)
        layout.addWidget(self.confirm_input)

        layout.addSpacing(10)

        # 按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        
        self.register_btn = QPushButton("✓ 注册")
        self.register_btn.setFont(QFont("Microsoft YaHei", 13, QFont.Bold))
        self.register_btn.setMinimumHeight(45)
        self.register_btn.setStyleSheet("""
            QPushButton {
                padding: 12px 25px;
                font-size: 15px;
                font-weight: bold;
                color: white;
                background: #2ecc71;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover {
                background: #27ae60;
            }
        """)
        self.register_btn.clicked.connect(self.on_register)
        button_layout.addWidget(self.register_btn)

        self.cancel_btn = QPushButton("✕ 取消")
        self.cancel_btn.setFont(QFont("Microsoft YaHei", 13))
        self.cancel_btn.setMinimumHeight(45)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                padding: 12px 25px;
                font-size: 15px;
                color: #666666;
                background: #f0f0f0;
                border: 2px solid #d0d0d0;
                border-radius: 8px;
            }
            QPushButton:hover {
                background: #e0e0e0;
            }
        """)
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFont(QFont("Microsoft YaHei", 11))
        self.status_label.setStyleSheet("color: #e74c3c; font-size: 13px;")
        layout.addWidget(self.status_label)
    
    def on_register(self):
        """注册处理"""
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        confirm = self.confirm_input.text().strip()

        if not username or not password or not confirm:
            self.status_label.setText("请填写所有字段")
            return
        
        if len(username) < 3 or len(username) > 20:
            self.status_label.setText("用户名长度必须在3-20个字符之间")
            return
        
        if len(password) < 6:
            self.status_label.setText("密码长度至少6个字符")
            return
        
        if password != confirm:
            self.status_label.setText("两次输入的密码不一致")
            return
        
        self.accept()


class SettingsDialog(QDialog):
    """设置对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置 - VocaloidToolboxFusion")
        self.setMinimumSize(650, 550)
        
        self.genshin_font = parent.genshin_font
        self.setFont(self.genshin_font)
        self.settings = parent.settings
        self.parent = parent
        self.themes = parent.themes
        self.current_theme = parent.current_theme
        
        # 防抖定时器
        self.theme_change_timer = None
        
        # 应用主题样式
        self.apply_theme()
        
        self.setup_ui()
    
    def apply_theme(self):
        """应用主题样式"""
        # 获取显示模式
        display_mode = self.settings.get('display_mode', 'light')
        
        # 获取主题颜色
        if self.current_theme == 'custom':
            custom_color = self.settings.get('custom_theme_color', '#3498db')
            primary_color = custom_color
            # 生成次要颜色（稍微暗一点）
            try:
                from PyQt5.QtGui import QColor
                color = QColor(custom_color)
                secondary_color = color.darker(120).name()
            except:
                secondary_color = '#2980b9'
            if display_mode == 'dark':
                background_color = '#121212'
                text_color = '#e0e0e0'
            else:
                background_color = '#f5f5f5'
                text_color = '#2c3e50'
        else:
            theme = self.themes.get(self.current_theme, self.themes['默认主题'])
            primary_color = theme['primary']
            secondary_color = theme['secondary']
            if display_mode == 'dark':
                background_color = '#121212'
                text_color = '#e0e0e0'
            else:
                background_color = theme['background']
                text_color = theme['text']
        
        # 构建样式表
        if display_mode == 'dark':
            # 深色主题色彩
            border_color = '#404040'
            widget_bg = '#1a1a1a'
            input_bg = '#262626'
            tab_bg = '#212121'
            tab_text = '#f0f0f0'
            group_box_text = '#f0f0f0'
            scroll_bg = '#1a1a1a'
            scroll_border = '#404040'
            line_edit_bg = '#2a2a2a'
            line_edit_border = '#505050'
            combo_bg = '#2a2a2a'
            combo_border = '#505050'
            recommend_bg = 'rgba(42, 42, 42, 0.9)'
            card_bg = '#2d2d2d'
            hover_bg = '#3a3a3a'
            active_bg = '#4a4a4a'
            separator_color = '#555555'
        else:
            # 浅色主题色彩
            border_color = '#e0e0e0'
            widget_bg = '#ffffff'
            input_bg = '#ffffff'
            tab_bg = '#f8f9fa'
            tab_text = '#495057'
            group_box_text = '#2c3e50'
            scroll_bg = 'white'
            scroll_border = '#e0e0e0'
            line_edit_bg = 'white'
            line_edit_border = '#e0e0e0'
            combo_bg = '#f9f9f9'
            combo_border = '#e0e0e0'
            recommend_bg = 'rgba(255, 255, 255, 0.8)'
            card_bg = '#f8f9fa'
            hover_bg = '#e9ecef'
            active_bg = '#dee2e6'
            separator_color = '#ced4da'
        
        style_sheet = f"""
            QDialog {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {background_color}, stop:1 {secondary_color});
                font-family: 'Microsoft YaHei', 'SimHei', sans-serif;
                color: {text_color};
            }}
            QScrollArea {{
                border: none;
                background: transparent;
            }}
            QScrollBar:vertical {{
                border: none;
                background: {scroll_bg};
                width: 10px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background: {hover_bg};
                border-radius: 5px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {active_bg};
            }}
            QLabel {{
                color: {text_color};
                background: transparent;
            }}
            QGroupBox {{
                background: {card_bg};
                border: 2px solid {border_color};
                border-radius: 8px;
                color: {group_box_text};
            }}
            QCheckBox {{
                color: {text_color};
                background: transparent;
            }}
            QComboBox {{
                background: {combo_bg};
                border: 2px solid {combo_border};
                color: {text_color};
            }}
        """
        
        self.setStyleSheet(style_sheet)
    
    def setup_ui(self):
        from PyQt5.QtWidgets import QComboBox, QLineEdit, QGroupBox, QHBoxLayout, QPushButton, QLabel, QVBoxLayout, QCheckBox, QScrollArea, QFrame
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # 创建滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(12)
        scroll_layout.setContentsMargins(5, 5, 5, 5)
        
        # UI设置
        ui_group = QGroupBox("🎨 界面设置")
        ui_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 15px;
                border: 2px solid #d0d0d0;
                border-radius: 8px;
                margin-top: 12px;
                padding: 15px 10px 10px 10px;
                color: #1a252f;
                background: rgba(255, 255, 255, 0.7);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px;
                background: transparent;
            }
        """)
        ui_layout = QVBoxLayout(ui_group)
        ui_layout.setSpacing(10)
        
        # 浏览器跳转
        browser_row = QHBoxLayout()
        browser_row.setSpacing(12)
        
        browser_label = QLabel("单击跳转浏览器:")
        browser_label.setFixedWidth(130)
        browser_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #1a252f;")
        browser_label.setFont(self.genshin_font)
        browser_row.addWidget(browser_label)
        
        self.open_browser_checkbox = QCheckBox("启用")
        self.open_browser_checkbox.setChecked(self.settings.get('open_in_browser', True))
        self.open_browser_checkbox.setFont(self.genshin_font)
        browser_row.addWidget(self.open_browser_checkbox)
        
        browser_hint = QLabel("关闭后单击不会跳转浏览器")
        browser_hint.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        browser_hint.setFont(self.genshin_font)
        browser_row.addWidget(browser_hint)
        
        browser_row.addStretch()
        ui_layout.addLayout(browser_row)
        
        # 主题颜色
        theme_row = QHBoxLayout()
        theme_row.setSpacing(12)
        
        theme_label = QLabel("主题颜色:")
        theme_label.setFixedWidth(130)
        theme_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #1a252f;")
        theme_label.setFont(self.genshin_font)
        theme_row.addWidget(theme_label)
        
        self.theme_combo = QComboBox()
        theme_names = ['默认主题', '科技商务', '天依蓝', '阿绫红', '薄和绿', '自定义主题']
        theme_keys = ['默认主题', '科技商务', '洛天依', '乐正绫', '言和', 'custom']
        self.theme_combo.addItems(theme_names)
        self.theme_combo.setFont(self.genshin_font)
        
        current_theme = self.settings.get('theme', '默认主题')
        current_index = theme_keys.index(current_theme) if current_theme in theme_keys else 0
        self.theme_combo.setCurrentIndex(current_index)
        self.theme_combo.setFixedHeight(36)
        theme_row.addWidget(self.theme_combo)
        
        # 日夜模式
        mode_row = QHBoxLayout()
        mode_row.setSpacing(12)
        
        mode_label = QLabel("显示模式:")
        mode_label.setFixedWidth(130)
        mode_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #1a252f;")
        mode_label.setFont(self.genshin_font)
        mode_row.addWidget(mode_label)
        
        self.mode_combo = QComboBox()
        mode_names = ['浅色模式', '深色模式']
        mode_keys = ['light', 'dark']
        self.mode_combo.addItems(mode_names)
        self.mode_combo.setFont(self.genshin_font)
        
        current_mode = self.settings.get('display_mode', 'light')
        current_mode_index = mode_keys.index(current_mode) if current_mode in mode_keys else 0
        self.mode_combo.setCurrentIndex(current_mode_index)
        self.mode_combo.setFixedHeight(36)
        mode_row.addWidget(self.mode_combo)
        ui_layout.addLayout(theme_row)
        ui_layout.addLayout(mode_row)
        
        # 自定义主题颜色输入框
        self.custom_primary_input = QLineEdit()
        self.custom_primary_input.setPlaceholderText("#RRGGBB")
        self.custom_primary_input.setFixedWidth(100)
        self.custom_primary_input.setFixedHeight(36)
        self.custom_primary_input.setFont(self.genshin_font)
        self.custom_primary_input.textChanged.connect(self.on_custom_theme_color_changed)
        theme_row.addWidget(self.custom_primary_input)
        
        # 颜色选择按钮
        from PyQt5.QtWidgets import QColorDialog
        color_picker_btn = QPushButton("🎨")
        color_picker_btn.setFont(self.genshin_font)
        color_picker_btn.setFixedSize(36, 36)
        color_picker_btn.setToolTip("选择颜色")
        color_picker_btn.clicked.connect(lambda: self.select_color())
        theme_row.addWidget(color_picker_btn)
        
        # 根据当前主题显示/隐藏自定义颜色输入框
        self.custom_primary_input.setVisible(current_theme == 'custom')
        color_picker_btn.setVisible(current_theme == 'custom')
        
        # 主题选择变化时的处理
        self.theme_combo.currentIndexChanged.connect(lambda *args: self.on_theme_changed(args[0] if args else 0, color_picker_btn))
        self.mode_combo.currentIndexChanged.connect(lambda *args: self.on_mode_changed(args[0] if args else 0))
        
        theme_hint = QLabel("选择VSinger五色战队主题或自定义")
        theme_hint.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        theme_hint.setFont(self.genshin_font)
        theme_row.addWidget(theme_hint)
        
        theme_row.addStretch()
        ui_layout.addLayout(theme_row)
        
        # 封面大小设置
        cover_size_row = QHBoxLayout()
        cover_size_row.setSpacing(12)
        
        cover_size_label = QLabel("封面大小:")
        cover_size_label.setFixedWidth(130)
        cover_size_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #1a252f;")
        cover_size_label.setFont(self.genshin_font)
        cover_size_row.addWidget(cover_size_label)
        
        self.cover_size_combo = QComboBox()
        cover_size_options = ['自动适应', '小 (120px)', '中 (160px)', '大 (200px)', '超大 (240px)']
        self.cover_size_combo.addItems(cover_size_options)
        self.cover_size_combo.setFont(self.genshin_font)
        
        current_cover_size = self.settings.get('cover_size', '自动适应')
        current_index = cover_size_options.index(current_cover_size) if current_cover_size in cover_size_options else 0
        self.cover_size_combo.setCurrentIndex(current_index)
        self.cover_size_combo.setFixedHeight(36)
        self.cover_size_combo.setStyleSheet("""
            QComboBox {
                padding: 8px 12px;
                border: 2px solid #d0d0d0;
                border-radius: 6px;
                min-width: 140px;
                font-size: 13px;
                background: white;
                color: #2c3e50;
            }
            QComboBox:hover {
                border-color: #3498db;
            }
        """)
        cover_size_row.addWidget(self.cover_size_combo)
        
        cover_size_hint = QLabel("选择封面的默认大小")
        cover_size_hint.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        cover_size_hint.setFont(self.genshin_font)
        cover_size_row.addWidget(cover_size_hint)
        
        cover_size_row.addStretch()
        ui_layout.addLayout(cover_size_row)
        
        # 列数设置
        column_count_row = QHBoxLayout()
        column_count_row.setSpacing(12)
        
        column_count_label = QLabel("显示列数:")
        column_count_label.setFixedWidth(130)
        column_count_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #1a252f;")
        column_count_label.setFont(self.genshin_font)
        column_count_row.addWidget(column_count_label)
        
        self.column_count_combo = QComboBox()
        column_count_options = ['自动适应', '1列', '2列', '3列', '4列', '5列']
        self.column_count_combo.addItems(column_count_options)
        self.column_count_combo.setFont(self.genshin_font)
        
        current_column_count = self.settings.get('column_count', '自动适应')
        current_col_index = column_count_options.index(current_column_count) if current_column_count in column_count_options else 0
        self.column_count_combo.setCurrentIndex(current_col_index)
        self.column_count_combo.setFixedHeight(36)
        self.column_count_combo.setStyleSheet("""
            QComboBox {
                padding: 8px 12px;
                border: 2px solid #d0d0d0;
                border-radius: 6px;
                min-width: 140px;
                font-size: 13px;
                background: white;
                color: #2c3e50;
            }
            QComboBox:hover {
                border-color: #3498db;
            }
        """)
        column_count_row.addWidget(self.column_count_combo)
        
        column_count_hint = QLabel("选择每行显示的卡片列数")
        column_count_hint.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        column_count_hint.setFont(self.genshin_font)
        column_count_row.addWidget(column_count_hint)
        
        column_count_row.addStretch()
        ui_layout.addLayout(column_count_row)
        
        # 使用内置播放器
        builtin_player_row = QHBoxLayout()
        builtin_player_row.setSpacing(12)
        
        builtin_player_label = QLabel("使用内置播放器:")
        builtin_player_label.setFixedWidth(130)
        builtin_player_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #1a252f;")
        builtin_player_label.setFont(self.genshin_font)
        builtin_player_row.addWidget(builtin_player_label)
        
        self.builtin_player_checkbox = QCheckBox("启用")
        self.builtin_player_checkbox.setChecked(self.settings.get('use_builtin_player', True))
        self.builtin_player_checkbox.setFont(self.genshin_font)
        self.builtin_player_checkbox.setStyleSheet("""
            QCheckBox {
                font-size: 13px;
                spacing: 8px;
                color: #2c3e50;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #c0c0c0;
                border-radius: 4px;
                background: white;
            }
            QCheckBox::indicator:checked {
                background: #3498db;
                border-color: #3498db;
            }
            QCheckBox::indicator:hover {
                border-color: #3498db;
            }
        """)
        builtin_player_row.addWidget(self.builtin_player_checkbox)
        
        builtin_player_hint = QLabel("开启后单击使用内置播放器（开发中）")
        builtin_player_hint.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        builtin_player_hint.setFont(self.genshin_font)
        builtin_player_row.addWidget(builtin_player_hint)
        
        builtin_player_row.addStretch()
        ui_layout.addLayout(builtin_player_row)
        
        # 关闭时最小化到托盘
        tray_row = QHBoxLayout()
        tray_row.setSpacing(12)
        
        tray_label = QLabel("关闭时最小化到托盘:")
        tray_label.setFixedWidth(130)
        tray_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #1a252f;")
        tray_label.setFont(self.genshin_font)
        tray_row.addWidget(tray_label)
        
        self.tray_checkbox = QCheckBox("启用")
        self.tray_checkbox.setChecked(self.settings.get('minimize_to_tray', True))
        self.tray_checkbox.setFont(self.genshin_font)
        self.tray_checkbox.setStyleSheet("""
            QCheckBox {
                font-size: 13px;
                spacing: 8px;
                color: #2c3e50;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #c0c0c0;
                border-radius: 4px;
                background: white;
            }
            QCheckBox::indicator:checked {
                background: #3498db;
                border-color: #3498db;
            }
            QCheckBox::indicator:hover {
                border-color: #3498db;
            }
        """)
        tray_row.addWidget(self.tray_checkbox)
        
        tray_hint = QLabel("关闭窗口时最小化到系统托盘继续运行")
        tray_hint.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        tray_hint.setFont(self.genshin_font)
        tray_row.addWidget(tray_hint)
        
        tray_row.addStretch()
        ui_layout.addLayout(tray_row)
        
        # 无图模式
        no_image_row = QHBoxLayout()
        no_image_row.setSpacing(12)
        
        no_image_label = QLabel("无图模式:")
        no_image_label.setFixedWidth(130)
        no_image_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #1a252f;")
        no_image_label.setFont(self.genshin_font)
        no_image_row.addWidget(no_image_label)
        
        self.no_image_mode_checkbox = QCheckBox("启用")
        self.no_image_mode_checkbox.setChecked(self.settings.get('no_image_mode', False))
        self.no_image_mode_checkbox.setFont(self.genshin_font)
        self.no_image_mode_checkbox.setStyleSheet("""
            QCheckBox {
                font-size: 13px;
                spacing: 8px;
                color: #2c3e50;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #c0c0c0;
                border-radius: 4px;
                background: white;
            }
            QCheckBox::indicator:checked {
                background: #3498db;
                border-color: #3498db;
            }
            QCheckBox::indicator:hover {
                border-color: #3498db;
            }
        """)
        no_image_row.addWidget(self.no_image_mode_checkbox)
        
        no_image_hint = QLabel("开启后不加封面图片")
        no_image_hint.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        no_image_hint.setFont(self.genshin_font)
        no_image_row.addWidget(no_image_hint)
        
        no_image_row.addStretch()
        ui_layout.addLayout(no_image_row)
        
        # 字体设置
        font_row = QHBoxLayout()
        font_row.setSpacing(12)
        
        font_label = QLabel("界面字体:")
        font_label.setFixedWidth(130)
        font_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #1a252f;")
        font_label.setFont(self.genshin_font)
        font_row.addWidget(font_label)
        
        self.font_combo = QComboBox()
        self.font_combo.setFont(self.genshin_font)
        
        all_fonts = self.parent.get_available_fonts() if self.parent else []
        custom_font_name = self.parent.get_custom_font_name() if self.parent else None
        
        font_list = []
        font_values = []
        font_list.append("请选择字体...")
        font_values.append("")
        
        if custom_font_name:
            font_list.insert(1, f"{custom_font_name} (内置)")
            font_values.insert(1, custom_font_name)
        
        for font in all_fonts:
            if font != custom_font_name:
                font_list.append(font)
                font_values.append(font)
        
        self.font_combo.addItems(font_list)
        
        current_font_name = self.settings.get('font_name', '')
        if current_font_name:
            try:
                current_index = font_values.index(current_font_name)
                self.font_combo.setCurrentIndex(current_index)
            except ValueError:
                self.font_combo.setCurrentIndex(0)
        else:
            self.font_combo.setCurrentIndex(0)
        
        self.font_combo.setFixedHeight(36)
        self.font_combo.setMinimumWidth(200)
        self.font_combo.setStyleSheet("""
            QComboBox {
                padding: 8px 12px;
                border: 2px solid #d0d0d0;
                border-radius: 6px;
                min-width: 140px;
                font-size: 13px;
                background: white;
                color: #2c3e50;
            }
            QComboBox:hover {
                border-color: #3498db;
            }
        """)
        font_row.addWidget(self.font_combo)
        
        font_hint = QLabel("选择界面显示字体")
        font_hint.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        font_hint.setFont(self.genshin_font)
        font_row.addWidget(font_hint)
        
        font_row.addStretch()
        ui_layout.addLayout(font_row)
        
        # 启用下拉刷新
        pull_refresh_row = QHBoxLayout()
        pull_refresh_row.setSpacing(12)
        
        pull_refresh_label = QLabel("启用下拉刷新:")
        pull_refresh_label.setFixedWidth(130)
        pull_refresh_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #1a252f;")
        pull_refresh_label.setFont(self.genshin_font)
        pull_refresh_row.addWidget(pull_refresh_label)
        
        self.pull_refresh_checkbox = QCheckBox("启用")
        self.pull_refresh_checkbox.setChecked(self.settings.get('pull_refresh', True))
        self.pull_refresh_checkbox.setFont(self.genshin_font)
        self.pull_refresh_checkbox.setStyleSheet("""
            QCheckBox {
                font-size: 13px;
                spacing: 8px;
                color: #2c3e50;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 20px;
                border: 2px solid #e0e0e0;
                border-radius: 4px;
                background: white;
            }
            QCheckBox::indicator:checked {
                background: #3498db;
                border-color: #3498db;
            }
            QCheckBox::indicator:checked:hover {
                background: #2980b9;
                border-color: #2980b9;
            }
        """)
        pull_refresh_row.addWidget(self.pull_refresh_checkbox)
        
        pull_refresh_hint = QLabel("打开后支持下拉刷新推荐")
        pull_refresh_hint.setStyleSheet("color: #5a6c7d; font-size: 12px; font-weight: 500;")
        pull_refresh_hint.setFont(self.genshin_font)
        pull_refresh_row.addWidget(pull_refresh_hint)
        
        pull_refresh_row.addStretch()
        ui_layout.addLayout(pull_refresh_row)
        
        # 列表管理
        list_manage_row = QHBoxLayout()
        list_manage_row.setSpacing(10)
        
        list_manage_label = QLabel("列表管理:")
        list_manage_label.setMinimumWidth(120)
        list_manage_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #1a252f;")
        list_manage_label.setFont(self.genshin_font)
        list_manage_row.addWidget(list_manage_label)
        
        show_favorites_btn = QPushButton("查看收藏列表")
        show_favorites_btn.setFont(self.genshin_font)
        show_favorites_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 12px;
                border: 2px solid #3498db !important;
                border-radius: 6px;
                font-size: 12px;
                font-weight: bold;
                background-color: #3498db !important;
                color: white !important;
            }
            QPushButton:hover {
                background-color: #2980b9 !important;
                border-color: #2980b9 !important;
            }
            QPushButton:pressed {
                background-color: #21618c !important;
            }
        """)
        show_favorites_btn.clicked.connect(self.show_favorites_list)
        list_manage_row.addWidget(show_favorites_btn)
        
        show_excluded_btn = QPushButton("查看排除列表")
        show_excluded_btn.setFont(self.genshin_font)
        show_excluded_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 12px;
                border: 2px solid #3498db !important;
                border-radius: 6px;
                font-size: 12px;
                font-weight: bold;
                background-color: #3498db !important;
                color: white !important;
            }
            QPushButton:hover {
                background-color: #2980b9 !important;
                border-color: #2980b9 !important;
            }
            QPushButton:pressed {
                background-color: #21618c !important;
            }
        """)
        show_excluded_btn.clicked.connect(self.show_excluded_list)
        list_manage_row.addWidget(show_excluded_btn)
        
        list_manage_row.addStretch()
        ui_layout.addLayout(list_manage_row)
        
        # 数据管理 - 导入导出
        data_manage_row = QHBoxLayout()
        data_manage_row.setSpacing(10)
        
        data_manage_label = QLabel("数据管理:")
        data_manage_label.setMinimumWidth(120)
        data_manage_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #1a252f;")
        data_manage_label.setFont(self.genshin_font)
        data_manage_row.addWidget(data_manage_label)
        
        export_btn = QPushButton("📤 导出数据")
        export_btn.setFont(self.genshin_font)
        export_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 12px;
                border: 2px solid #27ae60 !important;
                border-radius: 6px;
                font-size: 12px;
                font-weight: bold;
                background-color: #27ae60 !important;
                color: white !important;
            }
            QPushButton:hover {
                background-color: #219a52 !important;
                border-color: #219a52 !important;
            }
        """)
        export_btn.clicked.connect(self.export_data)
        data_manage_row.addWidget(export_btn)
        
        import_btn = QPushButton("📥 导入数据")
        import_btn.setFont(self.genshin_font)
        import_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 12px;
                border: 2px solid #e67e22 !important;
                border-radius: 6px;
                font-size: 12px;
                font-weight: bold;
                background-color: #e67e22 !important;
                color: white !important;
            }
            QPushButton:hover {
                background-color: #d35400 !important;
                border-color: #d35400 !important;
            }
        """)
        import_btn.clicked.connect(self.import_data)
        data_manage_row.addWidget(import_btn)
        
        data_manage_row.addStretch()
        ui_layout.addLayout(data_manage_row)
        
        scroll_layout.addWidget(ui_group)
        
        # 云端设置
        cloud_group = QGroupBox("☁️ 云端设置")
        cloud_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 16px;
                border: 2px solid #e0e0e0;
                border-radius: 10px;
                margin-top: 10px;
                padding-top: 10px;
                color: #1a252f;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        cloud_layout = QVBoxLayout(cloud_group)
        cloud_layout.setSpacing(12)
        
        # 运行模式
        cloud_mode_row = QHBoxLayout()
        cloud_mode_row.setSpacing(10)
        
        cloud_mode_label = QLabel("运行模式:")
        cloud_mode_label.setMinimumWidth(120)
        cloud_mode_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #1a252f;")
        cloud_mode_label.setFont(self.genshin_font)
        cloud_mode_row.addWidget(cloud_mode_label)
        
        self.cloud_mode_combo = QComboBox()
        cloud_mode_names = ['带云端版', '纯本地版']
        self.cloud_mode_combo.addItems(cloud_mode_names)
        self.cloud_mode_combo.setFont(self.genshin_font)
        
        current_cloud_mode = self.settings.get('cloud_mode', 'local')
        current_cloud_mode_index = 0 if current_cloud_mode == 'cloud' else 1
        self.cloud_mode_combo.setCurrentIndex(current_cloud_mode_index)
        self.cloud_mode_combo.setStyleSheet("""
            QComboBox {
                padding: 10px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                min-width: 150px;
                font-size: 13px;
                background: #f9f9f9;
            }
            QComboBox:focus {
                border: 2px solid #3498db;
                background: white;
            }
        """)
        cloud_mode_row.addWidget(self.cloud_mode_combo)
        
        cloud_mode_hint = QLabel("带云端版: 使用服务器数据和算法更新")
        cloud_mode_hint.setStyleSheet("color: #5a6c7d; font-size: 12px; font-weight: 500;")
        cloud_mode_hint.setFont(self.genshin_font)
        cloud_mode_row.addWidget(cloud_mode_hint)
        
        cloud_mode_row.addStretch()
        cloud_layout.addLayout(cloud_mode_row)
        
        # 浏览记录重置设置
        viewed_reset_row = QHBoxLayout()
        viewed_reset_row.setSpacing(10)
        
        viewed_reset_label = QLabel("浏览记录重置:")
        viewed_reset_label.setMinimumWidth(120)
        viewed_reset_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #1a252f;")
        viewed_reset_label.setFont(self.genshin_font)
        viewed_reset_row.addWidget(viewed_reset_label)
        
        # 启动时重置
        self.reset_startup_checkbox = QCheckBox("启动时重置")
        self.reset_startup_checkbox.setChecked(self.settings.get('reset_viewed_on_startup', True))
        self.reset_startup_checkbox.setFont(self.genshin_font)
        self.reset_startup_checkbox.setStyleSheet("font-size: 13px;")
        viewed_reset_row.addWidget(self.reset_startup_checkbox)
        
        # 刷新时重置（间隔）
        self.reset_refresh_checkbox = QCheckBox("刷新时重置(间隔)")
        self.reset_refresh_checkbox.setChecked(self.settings.get('reset_viewed_on_refresh', True))
        self.reset_refresh_checkbox.setFont(self.genshin_font)
        self.reset_refresh_checkbox.setStyleSheet("font-size: 13px;")
        viewed_reset_row.addWidget(self.reset_refresh_checkbox)
        
        # 重置间隔
        reset_interval_label = QLabel("间隔(小时):")
        reset_interval_label.setStyleSheet("font-size: 13px; color: #5a6c7d;")
        reset_interval_label.setFont(self.genshin_font)
        viewed_reset_row.addWidget(reset_interval_label)
        
        self.reset_interval_spin = QSpinBox()
        self.reset_interval_spin.setRange(1, 168)  # 1小时到7天
        self.reset_interval_spin.setValue(self.settings.get('viewed_reset_interval', 24))
        self.reset_interval_spin.setFont(self.genshin_font)
        self.reset_interval_spin.setStyleSheet("""
            QSpinBox {
                padding: 5px;
                border: 2px solid #e0e0e0;
                border-radius: 4px;
                min-width: 60px;
            }
        """)
        viewed_reset_row.addWidget(self.reset_interval_spin)
        
        viewed_reset_row.addStretch()
        cloud_layout.addLayout(viewed_reset_row)
        
        # 用户管理
        user_manage_row = QHBoxLayout()
        user_manage_row.setSpacing(10)
        
        user_manage_label = QLabel("用户管理:")
        user_manage_label.setMinimumWidth(120)
        user_manage_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #1a252f;")
        user_manage_label.setFont(self.genshin_font)
        user_manage_row.addWidget(user_manage_label)
        
        login_btn = QPushButton("登录/切换账号")
        login_btn.setFont(self.genshin_font)
        login_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 12px;
                border: 2px solid #3498db;
                border-radius: 6px;
                font-size: 12px;
                font-weight: bold;
                background: #3498db;
                color: white;
            }
            QPushButton:hover {
                background: #2980b9;
                border-color: #2980b9;
            }
        """)
        login_btn.clicked.connect(self.show_login_dialog)
        user_manage_row.addWidget(login_btn)
        
        clear_data_btn = QPushButton("清空数据")
        clear_data_btn.setFont(self.genshin_font)
        clear_data_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 12px;
                border: 2px solid #e74c3c;
                border-radius: 6px;
                font-size: 12px;
                font-weight: bold;
                background: #e74c3c;
                color: white;
            }
            QPushButton:hover {
                background: #c0392b;
                border-color: #c0392b;
            }
        """)
        clear_data_btn.clicked.connect(self.clear_user_data)
        user_manage_row.addWidget(clear_data_btn)
        
        view_behavior_btn = QPushButton("查看喜好数据")
        view_behavior_btn.setFont(self.genshin_font)
        view_behavior_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 12px;
                border: 2px solid #9b59b6;
                border-radius: 6px;
                font-size: 12px;
                font-weight: bold;
                background: #9b59b6;
                color: white;
            }
            QPushButton:hover {
                background: #8e44ad;
                border-color: #8e44ad;
            }
        """)
        view_behavior_btn.clicked.connect(self.show_user_behavior)
        user_manage_row.addWidget(view_behavior_btn)
        
        clear_behavior_btn = QPushButton("清除喜好数据")
        clear_behavior_btn.setFont(self.genshin_font)
        clear_behavior_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 12px;
                border: 2px solid #e67e22;
                border-radius: 6px;
                font-size: 12px;
                font-weight: bold;
                background: #e67e22;
                color: white;
            }
            QPushButton:hover {
                background: #d35400;
                border-color: #d35400;
            }
        """)
        clear_behavior_btn.clicked.connect(self.clear_user_behavior)
        user_manage_row.addWidget(clear_behavior_btn)
        
        user_manage_row.addStretch()
        cloud_layout.addLayout(user_manage_row)
        
        scroll_layout.addWidget(cloud_group)
        
        scroll_layout.addStretch()
        
        # 设置滚动区域的内容
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        # 底部按钮区域
        button_widget = QWidget()
        button_widget.setStyleSheet("""
            QWidget {
                background: rgba(255, 255, 255, 0.9);
                border-top: 1px solid #e0e0e0;
                padding: 10px;
            }
        """)
        button_layout = QHBoxLayout(button_widget)
        button_layout.setSpacing(15)
        button_layout.setContentsMargins(10, 5, 10, 5)
        
        save_btn = QPushButton("✓ 保存设置")
        save_btn.setFont(self.genshin_font)
        save_btn.setFixedHeight(42)
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 30px;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3498db, stop:1 #2980b9);
                color: white;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2980b9, stop:1 #1f6dad);
            }
            QPushButton:pressed {
                background: #1f6dad;
            }
        """)
        save_btn.clicked.connect(self.save_settings)
        button_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("✕ 取消")
        cancel_btn.setFont(self.genshin_font)
        cancel_btn.setFixedHeight(42)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 30px;
                border: 2px solid #d0d0d0;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
                background: white;
                color: #2c3e50;
            }
            QPushButton:hover {
                background: #f5f5f5;
                border-color: #b0b0b0;
            }
            QPushButton:pressed {
                background: #e8e8e8;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        reset_btn = QPushButton("🔄 还原默认")
        reset_btn.setFont(self.genshin_font)
        reset_btn.setFixedHeight(42)
        reset_btn.setCursor(Qt.PointingHandCursor)
        reset_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 30px;
                border: 2px solid #f39c12;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
                background: #f39c12;
                color: white;
            }
            QPushButton:hover {
                background: #e67e22;
                border-color: #e67e22;
            }
            QPushButton:pressed {
                background: #d35400;
            }
        """)
        reset_btn.clicked.connect(self.reset_to_defaults)
        button_layout.addWidget(reset_btn)
        
        button_layout.addStretch()
        layout.addWidget(button_widget)
    
    def on_mode_changed(self, index):
        """显示模式选择变化时的处理"""
        mode_names = ['浅色模式', '深色模式']
        mode_keys = ['light', 'dark']
        
        if 0 <= index < len(mode_keys):
            # 更新当前模式
            self.settings['display_mode'] = mode_keys[index]
            
            # 保存设置
            from utils.data_manager import save_settings
            save_settings(self.settings)
            
            # 应用模式变化
            if self.parent:
                self.parent.settings['display_mode'] = mode_keys[index]
                self.parent.apply_theme()
            
            # 显示提示
            if hasattr(self.parent, 'statusBar'):
                self.parent.statusBar().showMessage(f"已切换到{mode_names[index]}", 2000)
    
    def on_theme_changed(self, index, color_picker_btn, *args):
        """主题选择变化时的处理"""
        theme_names = ['默认主题', '科技商务', '天依蓝', '阿绫红', '薄和绿', '自定义主题']
        theme_keys = ['默认主题', '科技商务', '洛天依', '乐正绫', '言和', 'custom']
        
        if 0 <= index < len(theme_keys):
            theme = theme_keys[index]
            # 更新当前主题
            self.current_theme = theme
            # 显示/隐藏自定义颜色输入框和颜色选择按钮
            is_custom = (theme == 'custom')
            self.custom_primary_input.setVisible(is_custom)
            color_picker_btn.setVisible(is_custom)
            
            # 延迟应用主题，避免卡顿
            if hasattr(self, 'theme_change_timer') and self.theme_change_timer:
                self.theme_change_timer.stop()
            
            from PyQt5.QtCore import QTimer
            self.theme_change_timer = QTimer()
            self.theme_change_timer.setSingleShot(True)
            self.theme_change_timer.timeout.connect(lambda: self.apply_theme_change(theme))
            self.theme_change_timer.start(300)  # 300ms延迟
    
    def apply_theme_change(self, theme):
        """应用主题变化"""
        # 保存主题到设置
        self.settings['theme'] = theme
        # 应用主题到主窗口
        if self.parent:
            self.parent.current_theme = theme
            self.parent.apply_theme()
    
    def on_custom_theme_color_changed(self, text):
        """自定义主题颜色变化时的处理"""
        if text:
            # 保存自定义主题颜色到设置
            self.settings['custom_theme_color'] = text
            
            # 使用防抖定时器，避免频繁更新
            if self.theme_change_timer:
                self.theme_change_timer.stop()
            
            from PyQt5.QtCore import QTimer
            self.theme_change_timer = QTimer()
            self.theme_change_timer.setSingleShot(True)
            self.theme_change_timer.timeout.connect(lambda: self.apply_custom_theme_delayed(text))
            self.theme_change_timer.start(500)  # 500ms延迟
    
    def apply_custom_theme_delayed(self, text):
        """延迟应用自定义主题"""
        # 保存自定义主题颜色到设置
        self.settings['custom_theme_color'] = text
        # 应用自定义主题
        if self.parent:
            self.parent.settings['custom_theme_color'] = text
            self.parent.current_theme = 'custom'
            self.parent.apply_theme()
    
    def select_color(self):
        """选择自定义主题颜色"""
        from PyQt5.QtWidgets import QColorDialog
        from PyQt5.QtGui import QColor
        
        # 获取当前颜色
        current_color = self.custom_primary_input.text()
        if current_color:
            try:
                color = QColor(current_color)
            except:
                color = QColor('#3498db')
        else:
            color = QColor('#3498db')
        
        # 打开颜色选择器
        new_color = QColorDialog.getColor(color, self, "选择主题颜色")
        if new_color.isValid():
            self.custom_primary_input.setText(new_color.name())
    
    def save_settings(self):
        self.settings['open_in_browser'] = self.open_browser_checkbox.isChecked()
        self.settings['no_image_mode'] = self.no_image_mode_checkbox.isChecked()
        self.settings['pull_refresh'] = self.pull_refresh_checkbox.isChecked()
        
        # 保存主题颜色
        theme_names = ['默认主题', '科技商务', '天依蓝', '阿绫红', '薄和绿', '自定义主题']
        theme_keys = ['默认主题', '科技商务', '洛天依', '乐正绫', '言和', 'custom']
        current_index = self.theme_combo.currentIndex()
        self.settings['theme'] = theme_keys[current_index] if 0 <= current_index < len(theme_keys) else '默认主题'
        
        # 保存自定义主题颜色
        if self.settings['theme'] == 'custom':
            custom_color = self.custom_primary_input.text()
            if custom_color:
                self.settings['custom_theme_color'] = custom_color
        
        # 保存云端模式设置
        cloud_mode_names = ['带云端版', '纯本地版']
        cloud_mode_keys = ['cloud', 'local']
        current_cloud_mode_index = self.cloud_mode_combo.currentIndex()
        self.settings['cloud_mode'] = cloud_mode_keys[current_cloud_mode_index] if 0 <= current_cloud_mode_index < len(cloud_mode_keys) else 'cloud'
        
        
        # 保存封面大小设置
        cover_size_options = ['自动适应', '小 (120px)', '中 (160px)', '大 (200px)', '超大 (240px)']
        current_cover_size_index = self.cover_size_combo.currentIndex()
        self.settings['cover_size'] = cover_size_options[current_cover_size_index] if 0 <= current_cover_size_index < len(cover_size_options) else '自动适应'
        
        # 保存列数设置
        column_count_options = ['自动适应', '1列', '2列', '3列', '4列', '5列']
        current_column_count_index = self.column_count_combo.currentIndex()
        self.settings['column_count'] = column_count_options[current_column_count_index] if 0 <= current_column_count_index < len(column_count_options) else '自动适应'
        
        # 保存内置播放器设置
        self.settings['use_builtin_player'] = self.builtin_player_checkbox.isChecked()
        
        # 保存最小化到托盘设置
        self.settings['minimize_to_tray'] = self.tray_checkbox.isChecked()
        
        # 保存字体设置
        font_options = ['系统默认', '自定义字体']
        font_keys = ['default', 'custom']
        current_font_index = self.font_combo.currentIndex()
        self.settings['font_type'] = font_keys[current_font_index] if 0 <= current_font_index < len(font_keys) else 'custom'
        
        # 保存字体名称设置
        current_font_name = self.font_combo.currentText()
        if current_font_name and current_font_name != "请选择字体...":
            if "(自定义)" in current_font_name:
                current_font_name = current_font_name.replace(" (自定义)", "")
            self.settings['font_name'] = current_font_name
        else:
            self.settings['font_name'] = 'Microsoft YaHei'
        
        # 保存浏览记录重置设置
        self.settings['reset_viewed_on_startup'] = self.reset_startup_checkbox.isChecked()
        self.settings['reset_viewed_on_refresh'] = self.reset_refresh_checkbox.isChecked()
        self.settings['viewed_reset_interval'] = self.reset_interval_spin.value()
        
        # 保存到文件
        try:
            SETTINGS_PATH = os.path.join(os.path.expanduser('~'), '.bilibili_toolbox_settings.json')
            with open(SETTINGS_PATH, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
            
            # 应用设置到主窗口
            if self.parent:
                parent = self.parent
                parent.settings = self.settings.copy()
                parent.current_theme = self.settings.get('theme', '默认主题')
                parent.open_in_browser = self.settings.get('open_in_browser', True)
                parent.no_image_mode = self.settings.get('no_image_mode', False)
                # 确保自定义主题颜色设置也能正确应用
                if self.settings.get('theme') == 'custom' and 'custom_theme_color' in self.settings:
                    parent.settings['custom_theme_color'] = self.settings['custom_theme_color']
                # 应用封面大小设置
                parent.cover_size = self.settings.get('cover_size', '自动适应')
                # 应用列数设置
                parent.column_count = self.settings.get('column_count', '自动适应')
                # 应用最小化到托盘设置
                parent.settings['minimize_to_tray'] = self.settings.get('minimize_to_tray', True)
                # 应用字体设置
                font_name = self.settings.get('font_name', 'Microsoft YaHei')
                if font_name:
                    parent.genshin_font = QFont(font_name, 10, QFont.Medium)
                    parent.genshin_font.setStyleStrategy(QFont.PreferAntialias)
                parent.apply_theme()
                # 刷新推荐以应用新的列数设置
                parent.refresh_recommendations()
            
            # 根据当前显示模式设置消息框样式
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setWindowTitle("成功")
            msg_box.setText("设置已保存")
            
            # 应用主题样式
            display_mode = self.settings.get('display_mode', 'light')
            if display_mode == 'dark':
                msg_box.setStyleSheet("""
                    QMessageBox {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                            stop:0 #121212, stop:1 #1e1e1e);
                        color: #e0e0e0;
                        border: 1px solid #333333;
                        border-radius: 8px;
                    }
                    QLabel {
                        color: #e0e0e0;
                    }
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                            stop:0 #3498db, stop:1 #2980b9);
                        color: white;
                        padding: 6px 12px;
                        border: none;
                        border-radius: 4px;
                    }
                    QPushButton:hover {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                            stop:0 #2980b9, stop:1 #3498db);
                    }
                """)
            else:
                msg_box.setStyleSheet("""
                    QMessageBox {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                            stop:0 #f5f7fa, stop:1 #c3cfe2);
                        color: #2c3e50;
                        border: 1px solid #e0e0e0;
                        border-radius: 8px;
                    }
                    QLabel {
                        color: #2c3e50;
                    }
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                            stop:0 #3498db, stop:1 #2980b9);
                        color: white;
                        padding: 6px 12px;
                        border: none;
                        border-radius: 4px;
                    }
                    QPushButton:hover {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                            stop:0 #2980b9, stop:1 #3498db);
                    }
                """)
            
            msg_box.exec_()
            self.accept()
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "错误", f"保存设置失败: {str(e)}")
    
    def show_favorites_list(self):
        """显示收藏列表"""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QListWidget, QPushButton, QHBoxLayout, QMessageBox
        
        dialog = QDialog(self)
        dialog.setWindowTitle("收藏列表")
        dialog.setFixedSize(600, 400)
        
        layout = QVBoxLayout(dialog)
        
        # 收藏列表
        favorites_list = QListWidget()
        favorites_list.setStyleSheet("""
            QListWidget {
                background: white;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 4px;
                color: #1a1a1a;
                font-weight: 500;
            }
            QListWidget::item:selected {
                background: #3498db;
                color: white;
            }
            QListWidget::item:hover {
                background: #f0f0f0;
            }
        """)
        for item in self.parent.favorites:
            favorites_list.addItem(f"{item['title']} ({item['bvid']})")
        layout.addWidget(favorites_list)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        # 打开视频按钮
        open_btn = QPushButton("在浏览器中打开")
        open_btn.setFont(self.genshin_font)
        open_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
                background: #3498db;
                color: white;
            }
            QPushButton:hover {
                background: #2980b9;
            }
        """)
        open_btn.clicked.connect(lambda: self.open_favorite_video(favorites_list))
        button_layout.addWidget(open_btn)
        
        # 移除按钮
        remove_btn = QPushButton("移除")
        remove_btn.setFont(self.genshin_font)
        remove_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
                background: #f9f9f9;
                color: #2c3e50;
            }
            QPushButton:hover {
                background: #e9ecef;
            }
        """)
        remove_btn.clicked.connect(lambda: self.remove_favorite(favorites_list))
        button_layout.addWidget(remove_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        dialog.exec_()
    
    def open_favorite_video(self, favorites_list):
        """在浏览器中打开收藏的视频"""
        current_item = favorites_list.currentItem()
        if current_item:
            item_text = current_item.text()
            bvid = item_text.split('(')[-1].strip(')')
            url = f"https://www.bilibili.com/video/{bvid}"
            webbrowser.open(url)
    
    def remove_favorite(self, favorites_list):
        """移除收藏"""
        current_item = favorites_list.currentItem()
        if current_item:
            item_text = current_item.text()
            bvid = item_text.split('(')[-1].strip(')')
            
            # 从收藏列表中移除
            self.parent.favorites = [item for item in self.parent.favorites if item['bvid'] != bvid]
            self.parent.save_favorites_and_excluded()
            
            # 更新列表
            favorites_list.takeItem(favorites_list.currentRow())
            QMessageBox.information(self, "成功", "已从收藏列表中移除")
    
    def show_excluded_list(self):
        """显示排除列表"""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QListWidget, QPushButton, QHBoxLayout, QMessageBox
        
        dialog = QDialog(self)
        dialog.setWindowTitle("排除列表")
        dialog.setFixedSize(600, 400)
        
        layout = QVBoxLayout(dialog)
        
        # 排除列表
        excluded_list = QListWidget()
        excluded_list.setStyleSheet("""
            QListWidget {
                background: white;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 4px;
                color: #1a1a1a;
                font-weight: 500;
            }
            QListWidget::item:selected {
                background: #3498db;
                color: white;
            }
            QListWidget::item:hover {
                background: #f0f0f0;
            }
        """)
        for item in self.parent.excluded:
            excluded_list.addItem(f"{item['title']} ({item['bvid']})")
        layout.addWidget(excluded_list)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        # 打开视频按钮
        open_btn = QPushButton("在浏览器中打开")
        open_btn.setFont(self.genshin_font)
        open_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
                background: #3498db;
                color: white;
            }
            QPushButton:hover {
                background: #2980b9;
            }
        """)
        open_btn.clicked.connect(lambda: self.open_excluded_video(excluded_list))
        button_layout.addWidget(open_btn)
        
        # 移除按钮
        remove_btn = QPushButton("移除")
        remove_btn.setFont(self.genshin_font)
        remove_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
                background: #f9f9f9;
                color: #2c3e50;
            }
            QPushButton:hover {
                background: #e9ecef;
            }
        """)
        remove_btn.clicked.connect(lambda: self.remove_excluded(excluded_list))
        button_layout.addWidget(remove_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        dialog.exec_()
    
    def open_excluded_video(self, excluded_list):
        """在浏览器中打开排除的视频"""
        current_item = excluded_list.currentItem()
        if current_item:
            item_text = current_item.text()
            bvid = item_text.split('(')[-1].strip(')')
            url = f"https://www.bilibili.com/video/{bvid}"
            webbrowser.open(url)
    
    def remove_excluded(self, excluded_list):
        """移除排除"""
        current_item = excluded_list.currentItem()
        if current_item:
            item_text = current_item.text()
            bvid = item_text.split('(')[-1].strip(')')
            
            # 从排除列表中移除
            self.parent.excluded = [item for item in self.parent.excluded if item['bvid'] != bvid]
            self.parent.save_favorites_and_excluded()
            
            # 更新列表
            excluded_list.takeItem(excluded_list.currentRow())
            QMessageBox.information(self, "成功", "已从排除列表中移除")
    
    def show_login_dialog(self):
        """显示登录对话框"""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout, QMessageBox
        
        dialog = QDialog(self)
        dialog.setWindowTitle("登录")
        dialog.setFixedSize(400, 250)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title_label = QLabel("用户登录")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #2c3e50;")
        title_label.setFont(self.genshin_font)
        layout.addWidget(title_label)
        
        # 用户名
        username_row = QHBoxLayout()
        username_row.setSpacing(10)
        
        username_label = QLabel("用户名:")
        username_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #2c3e50;")
        username_label.setFont(self.genshin_font)
        username_row.addWidget(username_label)
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("请输入用户名")
        self.username_input.setFont(self.genshin_font)
        self.username_input.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                font-size: 14px;
                background: white;
            }
            QLineEdit:focus {
                border: 2px solid #3498db;
                background: white;
            }
        """)
        username_row.addWidget(self.username_input)
        layout.addLayout(username_row)
        
        # 密码
        password_row = QHBoxLayout()
        password_row.setSpacing(10)
        
        password_label = QLabel("密码:")
        password_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #2c3e50;")
        password_label.setFont(self.genshin_font)
        password_row.addWidget(password_label)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("请输入密码")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setFont(self.genshin_font)
        self.password_input.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                font-size: 14px;
                background: white;
            }
            QLineEdit:focus {
                border: 2px solid #3498db;
                background: white;
            }
        """)
        password_row.addWidget(self.password_input)
        layout.addLayout(password_row)
        
        # 按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        login_btn = QPushButton("登录")
        login_btn.setFont(self.genshin_font)
        login_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 20px;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                background: #3498db;
                color: white;
            }
            QPushButton:hover {
                background: #2980b9;
            }
        """)
        login_btn.clicked.connect(lambda: self.login(dialog))
        button_layout.addWidget(login_btn)
        
        register_btn = QPushButton("注册账号")
        register_btn.setFont(self.genshin_font)
        register_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 20px;
                border: 2px solid #27ae60;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                background: #f9f9f9;
                color: #27ae60;
            }
            QPushButton:hover {
                background: #27ae60;
                color: white;
            }
        """)
        register_btn.clicked.connect(lambda: self.register(dialog))
        button_layout.addWidget(register_btn)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setFont(self.genshin_font)
        cancel_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 20px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                background: #f9f9f9;
                color: #2c3e50;
            }
            QPushButton:hover {
                background: #e9ecef;
            }
        """)
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        dialog.exec_()
    
    def login(self, dialog):
        """登录"""
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        
        if not username or not password:
            QMessageBox.warning(self, "提示", "请输入用户名和密码")
            return
        
        try:
            # 使用user_auth进行真正的登录验证
            token = user_auth.login(username, password)
            if token:
                self.parent.current_user = {
                    'id': 1,
                    'username': username,
                    'token': token
                }
                self.parent.current_username = username
                QMessageBox.information(self, "成功", f"登录成功，欢迎 {username}！")
                dialog.accept()
            else:
                QMessageBox.warning(self, "错误", "用户名或密码错误")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"登录失败: {str(e)}")
    
    def register(self, dialog):
        """注册新账号"""
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        
        if not username or not password:
            QMessageBox.warning(self, "提示", "请输入用户名和密码")
            return
        
        if len(username) < 3:
            QMessageBox.warning(self, "提示", "用户名至少需要3个字符")
            return
        
        if len(password) < 6:
            QMessageBox.warning(self, "提示", "密码至少需要6个字符")
            return
        
        try:
            # 使用user_auth进行注册
            success = user_auth.register(username, password)
            if success:
                QMessageBox.information(self, "成功", f"注册成功！请使用新账号登录。")
                self.username_input.clear()
                self.password_input.clear()
            else:
                QMessageBox.warning(self, "错误", "用户名已存在，请选择其他用户名")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"注册失败: {str(e)}")
    
    def clear_user_data(self):
        """清空用户数据"""
        reply = QMessageBox.question(self, "确认", "确定要清空所有用户数据吗？这将删除收藏和排除列表。",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                # 清空数据
                self.parent.favorites = []
                self.parent.excluded = []
                self.parent.save_favorites_and_excluded()
                QMessageBox.information(self, "成功", "用户数据已清空")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"清空数据失败: {str(e)}")
    
    def show_user_behavior(self):
        """显示用户喜好数据"""
        try:
            from services.user_behavior import user_behavior_manager
            
            preferences = user_behavior_manager.get_user_preferences()
            
            # 创建对话框
            dialog = QDialog(self)
            dialog.setWindowTitle("用户喜好数据")
            dialog.setFixedSize(600, 500)
            dialog.setStyleSheet("""
                QDialog {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #f5f7fa, stop:1 #c3cfe2);
                    border-radius: 10px;
                }
                QLabel {
                    font-size: 14px;
                    color: #2c3e50;
                    font-weight: bold;
                }
                QTextEdit {
                    background: white;
                    border: 2px solid #e0e0e0;
                    border-radius: 5px;
                    padding: 10px;
                    font-size: 12px;
                    color: #2c3e50;
                }
                QPushButton {
                    padding: 8px 20px;
                    border: none;
                    border-radius: 6px;
                    font-size: 14px;
                    font-weight: bold;
                    background: #3498db;
                    color: white;
                }
                QPushButton:hover {
                    background: #2980b9;
                }
            """)
            
            layout = QVBoxLayout(dialog)
            layout.setSpacing(15)
            layout.setContentsMargins(20, 20, 20, 20)
            
            # 标题
            title_label = QLabel("您的喜好数据")
            title_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(title_label)
            
            # 创建文本框显示数据
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            
            # 格式化显示数据
            info_text = "=== 用户偏好统计 ===\n\n"
            info_text += f"总行为记录数: {preferences['total_behaviors']}\n"
            info_text += f"视频评分数: {preferences['video_scores_count']}\n"
            info_text += f"关键词评分数: {preferences['keyword_scores_count']}\n"
            info_text += f"作者评分数: {preferences['author_scores_count']}\n\n"
            
            info_text += "=== 热门关键词 (前5) ===\n"
            for keyword, score in preferences['top_keywords']:
                info_text += f"{keyword}: {score:.1f}\n"
            
            info_text += "\n=== 热门作者 (前5) ===\n"
            for author, score in preferences['top_authors']:
                info_text += f"{author}: {score:.1f}\n"
            
            text_edit.setText(info_text)
            layout.addWidget(text_edit)
            
            # 关闭按钮
            close_btn = QPushButton("关闭")
            close_btn.clicked.connect(dialog.accept)
            layout.addWidget(close_btn)
            
            dialog.exec_()
            
        except Exception as e:
            QMessageBox.warning(self, "错误", f"加载喜好数据失败: {str(e)}")
    
    def clear_user_behavior(self):
        """清除用户喜好数据"""
        reply = QMessageBox.question(self, "确认", "确定要清除所有用户喜好数据吗？这将删除您的歌手偏好、关键词偏好等个性化数据。",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                from services.user_behavior import user_behavior_manager, USER_BEHAVIOR_PATH
                import os
                
                # 清空行为数据
                user_behavior_manager.behavior_data = {
                    'user_id': 'default',
                    'behaviors': [],
                    'video_scores': {},
                    'keyword_scores': {},
                    'author_scores': {}
                }
                user_behavior_manager._save_behavior_data()
                
                QMessageBox.information(self, "成功", "用户喜好数据已清除")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"清除喜好数据失败: {str(e)}")
    
    def reset_to_defaults(self):
        """还原默认设置"""
        reply = QMessageBox.question(self, "确认", "确定要还原所有设置为默认值吗？",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                # 还原默认设置
                default_settings = {
                    "theme": "默认主题",
                    "no_image_mode": False,
                    "default_sort": "综合排序",
                    "download_path": os.path.join(os.path.dirname(__file__), "downloads"),
                    "refresh_interval": 300,
                    "minimize_to_tray": True,
                    "close_confirm_shown": False
                }
                
                # 更新设置
                self.parent.settings = default_settings
                
                # 保存设置
                from utils.data_manager import save_settings
                save_settings(default_settings)
                
                # 更新UI
                self.load_settings()
                
                QMessageBox.information(self, "成功", "设置已还原为默认值")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"还原默认设置失败: {str(e)}")
    
    def export_data(self):
        """导出数据"""
        from PyQt5.QtWidgets import QFileDialog
        import json
        from datetime import datetime
        
        # 选择保存路径
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出数据", 
            f"vocaloid_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON文件 (*.json)"
        )
        
        if not file_path:
            return
        
        try:
            # 收集所有数据
            export_data = {
                'export_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'version': '1.0',
                'favorites': self.parent.favorites,
                'excluded': self.parent.excluded,
                'playlists': getattr(self.parent, 'playlists', []),
                'settings': self.parent.settings,
                'share_history': getattr(self.parent, 'share_history', [])
            }
            
            # 保存到文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            QMessageBox.information(self, "成功", f"数据已导出到:\n{file_path}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "错误", f"导出失败: {str(e)}")
    
    def import_data(self):
        """导入数据"""
        from PyQt5.QtWidgets import QFileDialog
        import json
        
        # 选择文件
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入数据", "", "JSON文件 (*.json)"
        )
        
        if not file_path:
            return
        
        try:
            # 读取文件
            with open(file_path, 'r', encoding='utf-8') as f:
                import_data = json.load(f)
            
            # 验证数据格式
            if 'version' not in import_data:
                QMessageBox.warning(self, "错误", "无效的数据文件格式")
                return
            
            # 询问导入选项
            msg = QMessageBox(self)
            msg.setWindowTitle("导入选项")
            msg.setText("请选择导入方式:")
            msg.setInformativeText("合并: 保留现有数据，添加新数据\n覆盖: 清除现有数据，使用导入数据")
            msg.setStandardButtons(QMessageBox.Apply | QMessageBox.Ok | QMessageBox.Cancel)
            msg.button(QMessageBox.Apply).setText("合并")
            msg.button(QMessageBox.Ok).setText("覆盖")
            
            result = msg.exec_()
            
            if result == QMessageBox.Cancel:
                return
            
            if result == QMessageBox.Ok:  # 覆盖
                self.parent.favorites = import_data.get('favorites', [])
                self.parent.excluded = import_data.get('excluded', [])
                self.parent.playlists = import_data.get('playlists', [])
                self.parent.settings.update(import_data.get('settings', {}))
                self.parent.share_history = import_data.get('share_history', [])
            else:  # 合并
                # 合并收藏（去重）
                existing_bvids = {item['bvid'] for item in self.parent.favorites}
                for item in import_data.get('favorites', []):
                    if item['bvid'] not in existing_bvids:
                        self.parent.favorites.append(item)
                
                # 合并排除（去重）
                existing_excluded = {item['bvid'] for item in self.parent.excluded}
                for item in import_data.get('excluded', []):
                    if item['bvid'] not in existing_excluded:
                        self.parent.excluded.append(item)
                
                # 合并播放列表
                if not hasattr(self.parent, 'playlists'):
                    self.parent.playlists = []
                self.parent.playlists.extend(import_data.get('playlists', []))
                
                # 更新设置
                self.parent.settings.update(import_data.get('settings', {}))
            
            # 保存数据
            self.parent.save_favorites_and_excluded()
            if hasattr(self.parent, 'save_playlists'):
                self.parent.save_playlists()
            
            # 应用设置
            self.parent.apply_theme()
            
            QMessageBox.information(self, "成功", "数据导入成功！")
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "错误", f"导入失败: {str(e)}")

class MainWindow(QMainWindow):
    """主窗口"""
    
    def format_pubdate(self, pubdate_value):
        """统一格式化发布时间
        处理秒级和毫秒级时间戳，以及字符串格式
        """
        if pubdate_value is None or pubdate_value == '' or pubdate_value == '未知':
            return '未知'
        
        try:
            from datetime import datetime
            
            # 如果已经是字符串，直接返回
            if isinstance(pubdate_value, str):
                # 如果是数字字符串，尝试转换
                if pubdate_value.replace('.', '', 1).isdigit():
                    try:
                        ts = float(pubdate_value)
                        return self._format_timestamp(ts)
                    except:
                        pass
                return pubdate_value
            
            # 如果是数字（秒或毫秒）
            if isinstance(pubdate_value, (int, float)):
                return self._format_timestamp(pubdate_value)
            
        except Exception as e:
            print(f"格式化发布时间失败: {e}, 值: {pubdate_value}")
        
        return '未知'
    
    def _format_timestamp(self, timestamp):
        """格式化时间戳"""
        from datetime import datetime
        
        # 判断是秒级还是毫秒级时间戳
        # 毫秒级时间戳通常是13位或更多
        if timestamp > 10000000000:  # 大于2001年的毫秒级时间戳
            timestamp = timestamp / 1000
        
        try:
            dt = datetime.fromtimestamp(timestamp)
            return dt.strftime('%Y-%m-%d %H:%M')
        except:
            return '未知'
    
    def init_system_tray(self):
        """初始化系统托盘"""
        icon_path = os.path.join(os.path.dirname(__file__), 'assets', 'icons', 'icon.ico')
        if not os.path.exists(icon_path):
            if hasattr(sys, '_MEIPASS'):
                icon_path = os.path.join(sys._MEIPASS, 'assets', 'icons', 'icon.ico')
        
        if os.path.exists(icon_path):
            tray_icon = QIcon(icon_path)
        else:
            tray_icon = QApplication.style().standardIcon(QApplication.style().SP_ComputerIcon)
        
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(tray_icon)
        self.tray_icon.setToolTip("智能音乐推荐与分享系统")
        
        # 创建托盘菜单
        tray_menu = QMenu()
        
        # 显示/隐藏窗口
        show_action = QAction("显示窗口", self)
        show_action.triggered.connect(self.show_and_activate)
        tray_menu.addAction(show_action)
        
        # 刷新推荐
        refresh_action = QAction("刷新推荐", self)
        refresh_action.triggered.connect(self.refresh_recommendations)
        tray_menu.addAction(refresh_action)
        
        tray_menu.addSeparator()
        
        # 退出
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.quit_app)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        
        # 双击托盘图标显示窗口
        self.tray_icon.activated.connect(self.on_tray_activated)
        
        # 显示托盘图标
        self.tray_icon.show()
    
    def on_tray_activated(self, reason):
        """托盘图标被激活"""
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_and_activate()
    
    def show_and_activate(self):
        """显示并激活窗口"""
        self.show()
        self.activateWindow()
        self.raise_()
    
    def closeEvent(self, event):
        """重写关闭事件，实现最小化到托盘"""
        # 检查是否首次运行或需要显示确认对话框
        if not self.settings.get('close_confirm_shown', False):
            # 创建自定义对话框，使用圆形单选按钮
            dialog = QDialog(self)
            dialog.setWindowTitle("关闭确认")
            dialog.setFixedSize(400, 250)  # 增加弹窗大小
            dialog.setStyleSheet("""
                QDialog {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #f5f7fa, stop:1 #c3cfe2);
                    border-radius: 10px;
                }
                QLabel {
                    font-size: 14px;
                    color: #2c3e50;
                    font-weight: bold;
                }
                QRadioButton {
                    font-size: 14px;
                    color: #2c3e50;
                    spacing: 8px;
                }
                QPushButton {
                    padding: 8px 20px;
                    border: none;
                    border-radius: 6px;
                    font-size: 14px;
                    font-weight: bold;
                    background: #3498db;
                    color: white;
                }
                QPushButton:hover {
                    background: #2980b9;
                }
            """)
            
            layout = QVBoxLayout(dialog)
            layout.setSpacing(20)  # 增加整体布局间距
            layout.setContentsMargins(20, 20, 20, 20)
            
            # 标题
            title_label = QLabel("您希望如何操作？")
            title_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(title_label)
            
            # 单选按钮
            minimize_radio = QRadioButton("最小化到系统托盘")
            exit_radio = QRadioButton("完全退出程序")
            
            # 设置字体大小，确保文字清晰显示
            font = minimize_radio.font()
            font.setPointSize(12)
            minimize_radio.setFont(font)
            exit_radio.setFont(font)
            
            # 默认选择最小化
            minimize_radio.setChecked(True)
            
            # 直接添加到主布局，增加间距
            layout.addWidget(minimize_radio)
            layout.addWidget(exit_radio)
            
            # 按钮布局
            button_layout = QHBoxLayout()
            
            confirm_btn = QPushButton("确认")
            cancel_btn = QPushButton("取消")
            
            # 处理确认按钮点击
            def on_confirm():
                if minimize_radio.isChecked():
                    # 最小化到托盘
                    event.ignore()
                    self.hide()
                    # 显示托盘提示
                    if self.tray_icon:
                        self.tray_icon.showMessage(
                            "智能音乐推荐与分享系统",
                            "程序已最小化到系统托盘，双击图标可恢复窗口",
                            QSystemTrayIcon.Information,
                            2000
                        )
                    # 保存设置
                    self.settings['minimize_to_tray'] = True
                elif exit_radio.isChecked():
                    # 直接退出
                    self.quit_app()
                    # 保存设置
                    self.settings['minimize_to_tray'] = False
                # 标记关闭确认已显示
                self.settings['close_confirm_shown'] = True
                # 保存设置
                try:
                    from utils.data_manager import save_settings
                    save_settings(self.settings)
                except Exception as e:
                    print(f"保存设置失败: {e}")
                dialog.accept()
            
            confirm_btn.clicked.connect(on_confirm)
            cancel_btn.clicked.connect(lambda: dialog.reject())
            
            button_layout.addStretch()
            button_layout.addWidget(cancel_btn)
            button_layout.addWidget(confirm_btn)
            layout.addLayout(button_layout)
            
            # 显示对话框
            result = dialog.exec_()
            
            if result == QDialog.Rejected:
                event.ignore()
        else:
            # 根据设置直接执行操作
            if self.settings.get('minimize_to_tray', True):
                # 最小化到托盘 - 保存当前推荐状态
                self._save_current_recommendations()
                event.ignore()
                self.hide()
                # 显示托盘提示
                if self.tray_icon:
                    self.tray_icon.showMessage(
                        "智能音乐推荐与分享系统",
                        "程序已最小化到系统托盘，双击图标可恢复窗口",
                        QSystemTrayIcon.Information,
                        2000
                    )
            else:
                # 直接退出 - 保存当前推荐状态
                self._save_current_recommendations()
                self.quit_app()
    
    def show_bv_query_dialog(self):
        """显示BV/AV号查询对话框"""
        from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                                     QLineEdit, QPushButton, QTextEdit, QTabWidget, QWidget)
        import requests
        
        dialog = QDialog(self)
        dialog.setWindowTitle("BV/AV号查询工具")
        dialog.setMinimumSize(600, 450)
        dialog.setStyleSheet("""
            QDialog {
                background: #f5f7fa;
            }
            QLabel {
                color: #2c3e50;
            }
            QLineEdit {
                padding: 10px;
                border: 2px solid #d0d0d0;
                border-radius: 6px;
                background: white;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #3498db;
            }
            QPushButton {
                padding: 10px 20px;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }
            QTextEdit {
                border: 2px solid #d0d0d0;
                border-radius: 6px;
                background: white;
                padding: 10px;
                font-size: 13px;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标签页
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 2px solid #d0d0d0;
                border-radius: 6px;
                background: white;
            }
            QTabBar::tab {
                padding: 10px 20px;
                background: #e0e0e0;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #3498db;
                color: white;
            }
        """)
        
        # BV号查询标签页
        bv_tab = QWidget()
        bv_layout = QVBoxLayout(bv_tab)
        bv_layout.setSpacing(10)
        
        bv_input_row = QHBoxLayout()
        bv_label = QLabel("BV号:")
        bv_label.setFont(self.genshin_font)
        bv_input_row.addWidget(bv_label)
        
        bv_input = QLineEdit()
        bv_input.setPlaceholderText("输入BV号，如: BV1xx411c7mD")
        bv_input.setFont(self.genshin_font)
        bv_input_row.addWidget(bv_input)
        
        bv_query_btn = QPushButton("查询")
        bv_query_btn.setFont(self.genshin_font)
        bv_query_btn.setStyleSheet("background: #3498db; color: white;")
        bv_input_row.addWidget(bv_query_btn)
        
        bv_layout.addLayout(bv_input_row)
        
        bv_result = QTextEdit()
        bv_result.setReadOnly(True)
        bv_result.setFont(self.genshin_font)
        bv_result.setPlaceholderText("查询结果将显示在这里...")
        bv_layout.addWidget(bv_result)
        
        tabs.addTab(bv_tab, "BV号查询")
        
        # AV号转换标签页
        av_tab = QWidget()
        av_layout = QVBoxLayout(av_tab)
        av_layout.setSpacing(10)
        
        av_input_row = QHBoxLayout()
        av_label = QLabel("AV号:")
        av_label.setFont(self.genshin_font)
        av_input_row.addWidget(av_label)
        
        av_input = QLineEdit()
        av_input.setPlaceholderText("输入AV号，如: 170001")
        av_input.setFont(self.genshin_font)
        av_input_row.addWidget(av_input)
        
        av_convert_btn = QPushButton("转换")
        av_convert_btn.setFont(self.genshin_font)
        av_convert_btn.setStyleSheet("background: #27ae60; color: white;")
        av_input_row.addWidget(av_convert_btn)
        
        av_layout.addLayout(av_input_row)
        
        av_result = QTextEdit()
        av_result.setReadOnly(True)
        av_result.setFont(self.genshin_font)
        av_result.setPlaceholderText("转换结果将显示在这里...")
        av_layout.addWidget(av_result)
        
        tabs.addTab(av_tab, "AV号转换")
        
        layout.addWidget(tabs)
        
        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        
        close_btn = QPushButton("关闭")
        close_btn.setFont(self.genshin_font)
        close_btn.setStyleSheet("background: #e74c3c; color: white;")
        close_btn.clicked.connect(dialog.accept)
        btn_row.addWidget(close_btn)
        
        layout.addLayout(btn_row)
        
        # BV号查询功能
        def query_bv():
            bvid = bv_input.text().strip()
            if not bvid:
                bv_result.setText("请输入BV号")
                return
            
            try:
                url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://www.bilibili.com"
                }
                resp = requests.get(url, headers=headers, timeout=10)
                data = resp.json()
                
                if data['code'] == 0:
                    info = data['data']
                    result_text = f"""标题: {info['title']}
BV号: {info['bvid']}
AV号: av{info['aid']}
UP主: {info['owner']['name']}
播放量: {info['stat']['view']:,}
弹幕数: {info['stat']['danmaku']:,}
点赞数: {info['stat']['like']:,}
收藏数: {info['stat']['favorite']:,}
投币数: {info['stat']['coin']:,}
分享数: {info['stat']['share']:,}
发布时间: {self.format_pubdate(info['pubdate'])}
时长: {info['duration']//60}分{info['duration']%60}秒
简介: {info['desc'][:200]}...

链接: https://www.bilibili.com/video/{info['bvid']}"""
                    bv_result.setText(result_text)
                else:
                    bv_result.setText(f"查询失败: {data.get('message', '未知错误')}")
            except Exception as e:
                bv_result.setText(f"查询出错: {str(e)}")
        
        # AV号转换功能
        def convert_av():
            try:
                aid = int(av_input.text().strip())
                
                # AV号转BV号算法
                table = 'fZodR9XQDSUm21yCkr6zBqiveYah8bt4xsWpHnJE7jL5VG3guMTKNPAwcF'
                tr = {c: i for i, c in enumerate(table)}
                s = [11, 10, 3, 8, 4, 6]
                xor = 177451812
                add = 8728348608
                
                def av2bv(aid):
                    x = (aid ^ xor) + add
                    r = list('BV1  4 1 7  ')
                    for i in range(6):
                        r[s[i]] = table[x // 58**i % 58]
                    return ''.join(r)
                
                bvid = av2bv(aid)
                result_text = f"""AV号: av{aid}
BV号: {bvid}

链接: https://www.bilibili.com/video/{bvid}"""
                av_result.setText(result_text)
            except ValueError:
                av_result.setText("请输入有效的AV号数字")
            except Exception as e:
                av_result.setText(f"转换出错: {str(e)}")
        
        bv_query_btn.clicked.connect(query_bv)
        av_convert_btn.clicked.connect(convert_av)
        bv_input.returnPressed.connect(query_bv)
        av_input.returnPressed.connect(convert_av)
        
        dialog.exec_()
    
    def show_download_dialog(self):
        """显示视频下载对话框"""
        from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                                     QLineEdit, QPushButton, QProgressBar, QComboBox,
                                     QCheckBox, QFileDialog)
        import requests
        import threading
        
        dialog = QDialog(self)
        dialog.setWindowTitle("视频下载工具")
        dialog.setMinimumSize(500, 400)
        dialog.setStyleSheet("""
            QDialog {
                background: #f5f7fa;
            }
            QLabel {
                color: #2c3e50;
            }
            QLineEdit, QComboBox {
                padding: 10px;
                border: 2px solid #d0d0d0;
                border-radius: 6px;
                background: white;
                font-size: 14px;
            }
            QPushButton {
                padding: 10px 20px;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }
            QProgressBar {
                border: 2px solid #d0d0d0;
                border-radius: 6px;
                text-align: center;
                background: white;
            }
            QProgressBar::chunk {
                background: #3498db;
                border-radius: 4px;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # BV号输入
        input_row = QHBoxLayout()
        input_label = QLabel("BV号:")
        input_label.setFont(self.genshin_font)
        input_row.addWidget(input_label)
        
        bv_input = QLineEdit()
        bv_input.setPlaceholderText("输入BV号")
        bv_input.setFont(self.genshin_font)
        input_row.addWidget(bv_input)
        
        layout.addLayout(input_row)
        
        # 画质选择
        quality_row = QHBoxLayout()
        quality_label = QLabel("画质:")
        quality_label.setFont(self.genshin_font)
        quality_row.addWidget(quality_label)
        
        quality_combo = QComboBox()
        quality_combo.addItems(['最高画质', '1080P', '720P', '480P', '360P'])
        quality_combo.setFont(self.genshin_font)
        quality_row.addWidget(quality_combo)
        
        quality_row.addStretch()
        layout.addLayout(quality_row)
        
        # 保存路径
        path_row = QHBoxLayout()
        path_label = QLabel("保存到:")
        path_label.setFont(self.genshin_font)
        path_row.addWidget(path_label)
        
        path_input = QLineEdit()
        path_input.setText(str(self.download_path) if hasattr(self, 'download_path') else os.path.expanduser('~/Downloads'))
        path_input.setFont(self.genshin_font)
        path_row.addWidget(path_input)
        
        browse_btn = QPushButton("浏览")
        browse_btn.setFont(self.genshin_font)
        browse_btn.setStyleSheet("background: #95a5a6; color: white;")
        path_row.addWidget(browse_btn)
        
        layout.addLayout(path_row)
        
        # 进度条
        progress = QProgressBar()
        progress.setValue(0)
        layout.addWidget(progress)
        
        # 状态标签
        status_label = QLabel("准备就绪")
        status_label.setFont(self.genshin_font)
        status_label.setStyleSheet("color: #7f8c8d;")
        layout.addWidget(status_label)
        
        # 按钮
        btn_row = QHBoxLayout()
        
        download_btn = QPushButton("开始下载")
        download_btn.setFont(self.genshin_font)
        download_btn.setStyleSheet("background: #27ae60; color: white;")
        btn_row.addWidget(download_btn)
        
        open_btn = QPushButton("打开目录")
        open_btn.setFont(self.genshin_font)
        open_btn.setStyleSheet("background: #3498db; color: white;")
        btn_row.addWidget(open_btn)
        
        close_btn = QPushButton("关闭")
        close_btn.setFont(self.genshin_font)
        close_btn.setStyleSheet("background: #e74c3c; color: white;")
        close_btn.clicked.connect(dialog.accept)
        btn_row.addWidget(close_btn)
        
        layout.addLayout(btn_row)
        
        # 浏览按钮
        def browse_path():
            folder = QFileDialog.getExistingDirectory(dialog, "选择保存目录")
            if folder:
                path_input.setText(folder)
        
        browse_btn.clicked.connect(browse_path)
        
        # 打开目录
        def open_folder():
            import subprocess
            folder = path_input.text()
            if os.path.exists(folder):
                subprocess.run(['explorer', folder])
        
        open_btn.clicked.connect(open_folder)
        
        # 下载功能
        def start_download():
            bvid = bv_input.text().strip()
            if not bvid:
                status_label.setText("请输入BV号")
                return
            
            status_label.setText("正在获取视频信息...")
            progress.setValue(10)
            
            try:
                # 获取视频信息
                url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://www.bilibili.com"
                }
                resp = requests.get(url, headers=headers, timeout=10)
                data = resp.json()
                
                if data['code'] != 0:
                    status_label.setText(f"获取失败: {data.get('message', '未知错误')}")
                    return
                
                info = data['data']
                title = info['title']
                cid = info['cid']
                
                status_label.setText(f"视频: {title[:30]}...")
                progress.setValue(30)
                
                # 注意：实际下载需要登录Cookie和更复杂的处理
                # 这里只提供信息展示和跳转到网页下载
                status_label.setText("提示: 请使用专业下载工具或浏览器插件\n点击下方链接在网页下载")
                progress.setValue(100)
                
                # 打开B站视频页面
                import webbrowser
                video_url = f"https://www.bilibili.com/video/{bvid}"
                webbrowser.open(video_url)
                
            except Exception as e:
                status_label.setText(f"错误: {str(e)}")
                progress.setValue(0)
        
        download_btn.clicked.connect(start_download)
        
        dialog.exec_()
    
    def show_keyword_manager(self):
        """显示关键词管理对话框"""
        from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                                     QListWidget, QLineEdit, QPushButton, QTabWidget, QWidget)
        from config import load_custom_keywords, save_custom_keywords
        
        dialog = QDialog(self)
        dialog.setWindowTitle("关键词管理")
        dialog.setMinimumSize(600, 500)
        dialog.setStyleSheet("""
            QDialog {
                background: #f5f7fa;
            }
            QLabel {
                color: #2c3e50;
                font-weight: bold;
            }
            QListWidget {
                border: 2px solid #d0d0d0;
                border-radius: 6px;
                background: white;
                padding: 5px;
            }
            QListWidget::item {
                padding: 5px;
                border-radius: 3px;
            }
            QListWidget::item:selected {
                background: #3498db;
                color: white;
            }
            QLineEdit {
                padding: 8px;
                border: 2px solid #d0d0d0;
                border-radius: 6px;
                background: white;
            }
            QPushButton {
                padding: 8px 15px;
                border: none;
                border-radius: 6px;
                font-size: 13px;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 加载当前配置
        config = load_custom_keywords()
        
        # 标签页
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 2px solid #d0d0d0;
                border-radius: 6px;
                background: white;
            }
            QTabBar::tab {
                padding: 8px 15px;
                background: #e0e0e0;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QTabBar::tab:selected {
                background: #3498db;
                color: white;
            }
        """)
        
        def create_keyword_tab(title, key, color):
            tab = QWidget()
            tab_layout = QVBoxLayout(tab)
            tab_layout.setSpacing(10)
            
            # 列表
            list_widget = QListWidget()
            list_widget.setFont(self.genshin_font)
            for kw in config.get(key, []):
                list_widget.addItem(kw)
            tab_layout.addWidget(list_widget)
            
            # 输入行
            input_row = QHBoxLayout()
            kw_input = QLineEdit()
            kw_input.setPlaceholderText("输入新关键词")
            kw_input.setFont(self.genshin_font)
            input_row.addWidget(kw_input)
            
            add_btn = QPushButton("添加")
            add_btn.setFont(self.genshin_font)
            add_btn.setStyleSheet(f"background: {color}; color: white;")
            input_row.addWidget(add_btn)
            
            remove_btn = QPushButton("删除选中")
            remove_btn.setFont(self.genshin_font)
            remove_btn.setStyleSheet("background: #e74c3c; color: white;")
            input_row.addWidget(remove_btn)
            
            tab_layout.addLayout(input_row)
            
            # 按钮功能
            def add_keyword():
                text = kw_input.text().strip()
                if text and text not in [list_widget.item(i).text() for i in range(list_widget.count())]:
                    list_widget.addItem(text)
                    kw_input.clear()
            
            def remove_keyword():
                current = list_widget.currentRow()
                if current >= 0:
                    list_widget.takeItem(current)
            
            add_btn.clicked.connect(add_keyword)
            remove_btn.clicked.connect(remove_keyword)
            
            return tab, list_widget
        
        # 创建各标签页
        singer_tab, singer_list = create_keyword_tab("自定义歌手", 'custom_singers', '#3498db')
        tabs.addTab(singer_tab, "自定义歌手")
        
        producer_tab, producer_list = create_keyword_tab("自定义P主", 'custom_producers', '#27ae60')
        tabs.addTab(producer_tab, "自定义P主")
        
        exclude_tab, exclude_list = create_keyword_tab("自定义排除词", 'custom_exclude', '#e74c3c')
        tabs.addTab(exclude_tab, "排除关键词")
        
        include_tab, include_list = create_keyword_tab("自定义包含词", 'custom_include', '#f39c12')
        tabs.addTab(include_tab, "包含关键词")
        
        # 默认关键词启用/禁用标签页
        default_tab = QWidget()
        default_layout = QVBoxLayout(default_tab)
        default_layout.setSpacing(10)
        
        # 创建启用/禁用选项
        enabled_keywords = config.get('enabled_keywords', {})
        
        def create_enable_option(label, key, description):
            option_widget = QWidget()
            option_layout = QVBoxLayout(option_widget)
            option_layout.setSpacing(5)
            
            # 标签
            title_label = QLabel(label)
            title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #2c3e50;")
            option_layout.addWidget(title_label)
            
            # 描述
            desc_label = QLabel(description)
            desc_label.setStyleSheet("font-size: 12px; color: #7f8c8d;")
            desc_label.setWordWrap(True)
            option_layout.addWidget(desc_label)
            
            # 复选框
            checkbox = QCheckBox("启用")
            checkbox.setChecked(enabled_keywords.get(key, True))
            checkbox.setStyleSheet("font-size: 14px;")
            checkbox.stateChanged.connect(lambda state, k=key: enabled_keywords.update({k: state == 2}))
            option_layout.addWidget(checkbox)
            
            return option_widget, checkbox
        
        # Vocaloid关键词选项
        vocaloid_widget, vocaloid_checkbox = create_enable_option(
            "Vocaloid关键词",
            'vocaloid_keywords',
            "包含洛天依、乐正绫、言和等虚拟歌手相关关键词"
        )
        default_layout.addWidget(vocaloid_widget)
        
        # 排除关键词选项
        exclude_widget, exclude_checkbox = create_enable_option(
            "排除关键词",
            'exclude_keywords',
            "排除教程、游戏、直播等非音乐内容"
        )
        default_layout.addWidget(exclude_widget)
        
        # 音乐关键词选项
        music_widget, music_checkbox = create_enable_option(
            "音乐关键词",
            'music_keywords',
            "包含原创、翻唱、曲等音乐相关关键词"
        )
        default_layout.addWidget(music_widget)
        
        # 知名P主选项
        producer_widget, producer_checkbox = create_enable_option(
            "知名P主",
            'known_producers',
            "包含ilem、乌龟sui等知名UP主"
        )
        default_layout.addWidget(producer_widget)
        
        default_layout.addStretch()
        tabs.addTab(default_tab, "默认关键词")
        
        layout.addWidget(tabs)
        
        # 按钮
        btn_row = QHBoxLayout()
        
        save_btn = QPushButton("保存")
        save_btn.setFont(self.genshin_font)
        save_btn.setStyleSheet("background: #27ae60; color: white; padding: 10px 30px;")
        btn_row.addWidget(save_btn)
        
        close_btn = QPushButton("关闭")
        close_btn.setFont(self.genshin_font)
        close_btn.setStyleSheet("background: #95a5a6; color: white; padding: 10px 30px;")
        close_btn.clicked.connect(dialog.reject)
        btn_row.addWidget(close_btn)
        
        layout.addLayout(btn_row)
        
        # 保存功能
        def save_keywords():
            config['custom_singers'] = [singer_list.item(i).text() for i in range(singer_list.count())]
            config['custom_producers'] = [producer_list.item(i).text() for i in range(producer_list.count())]
            config['custom_exclude'] = [exclude_list.item(i).text() for i in range(exclude_list.count())]
            config['custom_include'] = [include_list.item(i).text() for i in range(include_list.count())]
            
            # 保存启用/禁用状态
            config['enabled_keywords'] = {
                'vocaloid_keywords': vocaloid_checkbox.isChecked(),
                'exclude_keywords': exclude_checkbox.isChecked(),
                'music_keywords': music_checkbox.isChecked(),
                'known_producers': producer_checkbox.isChecked()
            }
            
            if save_custom_keywords(config):
                QMessageBox.information(dialog, "成功", "关键词已保存，刷新推荐后生效")
                dialog.accept()
            else:
                QMessageBox.warning(dialog, "错误", "保存失败")
        
        save_btn.clicked.connect(save_keywords)
        
        dialog.exec_()
    
    def _save_current_recommendations(self):
        """保存当前推荐列表和滚动位置"""
        try:
            from utils.data_manager import save_last_recommendations
            
            # 获取当前推荐列表
            recommendations = getattr(self, '_current_recommendations', [])
            if recommendations:
                # 获取滚动位置
                scroll_pos = 0
                if hasattr(self, 'recommend_scroll'):
                    scroll_pos = self.recommend_scroll.verticalScrollBar().value()
                
                # 保存到数据文件
                save_last_recommendations(recommendations, scroll_pos)
                print(f"已保存推荐状态: {len(recommendations)} 个视频, 滚动位置: {scroll_pos}")
        except Exception as e:
            print(f"保存推荐状态失败: {e}")
    
    def _restore_last_recommendations(self):
        """恢复上次保存的推荐列表"""
        try:
            from utils.data_manager import load_last_recommendations
            
            recommendations, scroll_pos = load_last_recommendations()
            if recommendations and len(recommendations) > 0:
                print(f"恢复上次推荐: {len(recommendations)} 个视频")
                self.display_recommendations(recommendations)
                
                # 恢复滚动位置
                if scroll_pos > 0 and hasattr(self, 'recommend_scroll'):
                    # 延迟恢复滚动位置，等待布局完成
                    from PyQt5.QtCore import QTimer
                    QTimer.singleShot(500, lambda: self.recommend_scroll.verticalScrollBar().setValue(scroll_pos))
                
                return True
            return False
        except Exception as e:
            print(f"恢复推荐状态失败: {e}")
            return False
    
    def _load_recommendations_with_restore(self):
        """加载推荐，优先恢复上次状态"""
        try:
            from utils.data_manager import load_last_recommendations
            recommendations, scroll_pos = load_last_recommendations()
            if recommendations and len(recommendations) > 0:
                print(f"恢复上次推荐: {len(recommendations)} 个视频")
                self.display_recommendations(recommendations)
                if scroll_pos > 0 and hasattr(self, 'recommend_scroll'):
                    from PyQt5.QtCore import QTimer
                    QTimer.singleShot(500, lambda: self.recommend_scroll.verticalScrollBar().setValue(scroll_pos))
                self.hide_loading_screen()
                self.start_preload()
                return
        except Exception as e:
            print(f"恢复推荐状态失败: {e}")
        self.load_recommendations()
    
    def quit_app(self):
        """退出应用 - 确保所有进程和线程都被清理"""
        try:
            # 保存当前推荐状态
            self._save_current_recommendations()
            
            # 停止预加载线程
            self.is_preloading = False
            if self.preload_thread and self.preload_thread.is_alive():
                self.preload_thread.join(timeout=1.0)
            
            # 停止预加载状态定时器
            if hasattr(self, 'preload_timer') and self.preload_timer:
                self.preload_timer.stop()
            
            # 停止resize定时器
            if hasattr(self, 'resize_timer') and self.resize_timer:
                self.resize_timer.stop()
            
            # 清理封面加载线程
            for thread in self.cover_threads:
                if thread and thread.isRunning():
                    thread.terminate()
                    thread.wait(1000)
            
            # 停止API服务器
            try:
                from services.api_server import stop_api_server
                stop_api_server()
            except:
                pass
            
            # 隐藏托盘图标
            if hasattr(self, 'tray_icon') and self.tray_icon:
                self.tray_icon.hide()
                self.tray_icon = None
            
            # 保存设置
            try:
                save_settings(self.settings)
            except Exception as e:
                print(f"保存设置失败: {e}")
            
            # 退出应用
            QApplication.quit()
            
        except Exception as e:
            print(f"退出时发生错误: {e}")
            # 强制退出
            import sys
            sys.exit(0)
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("智能音乐推荐与分享系统 (融合版) - VocaloidToolboxFusion")
        
        # 根据设备显示器尺寸自动调整窗口大小
        from PyQt5.QtWidgets import QApplication
        screen = QApplication.desktop().screenGeometry()
        screen_width = screen.width()
        screen_height = screen.height()
        
        # 计算合适的窗口大小，优先使用接近全屏的尺寸
        window_width = int(screen_width * 0.95)  # 95%的屏幕宽度
        window_height = int(screen_height * 0.9)  # 90%的屏幕高度
        
        # 确保窗口大小合理
        window_width = max(800, window_width)
        window_height = max(600, window_height)
        
        # 设置窗口位置为屏幕中心
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        self.setGeometry(x, y, window_width, window_height)
        
        # 加载窗口图标
        try:
            icon_path = os.path.join(os.path.dirname(__file__), 'assets', 'icons', 'icon.ico')
            if not os.path.exists(icon_path):
                if hasattr(sys, '_MEIPASS'):
                    icon_path = os.path.join(sys._MEIPASS, 'assets', 'icons', 'icon.ico')
            
            if os.path.exists(icon_path):
                app_icon = QIcon(icon_path)
                self.setWindowIcon(app_icon)
                # 同时设置应用程序图标
                QApplication.setWindowIcon(app_icon)
                print(f"加载图标成功: {icon_path}")
            else:
                # 使用默认图标（使用SP_ComputerIcon替代SP_MusicIcon，兼容性更好）
                default_icon = QApplication.style().standardIcon(QApplication.style().SP_ComputerIcon)
                self.setWindowIcon(default_icon)
                QApplication.setWindowIcon(default_icon)
                print("使用默认图标")
        except Exception as e:
            print(f"加载窗口图标失败: {e}")
            # 确保使用默认图标
            try:
                default_icon = QApplication.style().standardIcon(QApplication.style().SP_ComputerIcon)
                self.setWindowIcon(default_icon)
                QApplication.setWindowIcon(default_icon)
                print("使用默认图标作为后备")
            except Exception as e2:
                print(f"设置默认图标也失败: {e2}")
                pass
        
        # 优化字体样式 - 使用更美观的字体
        self.genshin_font = QFont("Microsoft YaHei", 10, QFont.Medium)
        self.genshin_font.setStyleStrategy(QFont.PreferAntialias)  # 抗锯齿
        
        # 尝试加载自定义字体
        self.load_custom_font()
        
        # 加载设置
        self.settings = load_settings()
        
        # 检查是否需要重置浏览记录（每次启动时）
        self._check_and_reset_viewed_on_startup()
        
        # 初始化系统托盘
        self.init_system_tray()
        
        # 初始化变量
        self.favorites = []
        self.excluded = []
        self.playlists = []
        self.current_user = None
        self.logged_in = False
        self.auth_token = None
        
        # 主题设置
        self.themes = {
            '默认主题': {'primary': '#1E88E5', 'secondary': '#64B5F6', 'background': '#FAFAFA', 'text': '#212121'},
            '科技商务': {'primary': '#0D47A1', 'secondary': '#1565C0', 'background': '#F5F5F5', 'text': '#212121'},
            '洛天依': {'primary': '#64B5F6', 'secondary': '#90CAF9', 'background': '#E3F2FD', 'text': '#1565C0'},
            '乐正绫': {'primary': '#E53935', 'secondary': '#EF5350', 'background': '#FFEBEE', 'text': '#C62828'},
            '言和': {'primary': '#43A047', 'secondary': '#66BB6A', 'background': '#E8F5E8', 'text': '#2E7D32'},
            'custom': {'primary': '#3498db', 'secondary': '#2980b9', 'background': '#f5f5f5', 'text': '#2c3e50'}
        }
        self.current_theme = self.settings.get('theme', '默认主题')
        
        # 其他设置
        self.open_in_browser = self.settings.get('open_in_browser', True)
        self.no_image_mode = self.settings.get('no_image_mode', False)
        self.cover_size = self.settings.get('cover_size', '自动适应')
        self.column_count = self.settings.get('column_count', '自动适应')
        
        # 播放列表侧边栏状态（默认显示，5列模式）
        self.playlist_sidebar_visible = True
        
        # 预初始化内置播放器组件
        self._init_player_components()
        
        # 线程池管理 - 优化版
        self.cover_threads = []
        self.max_concurrent_loads = 8  # 增加最大并发加载数量
        self.load_semaphore = 0  # 当前加载计数
        self._thread_pool = ThreadPoolExecutor(max_workers=8)  # 全局线程池

        self._cover_load_queue = []  # 封面加载队列
        self._is_loading_covers = False  # 是否正在批量加载封面
        
        # 预加载缓存
        self.preloaded_recommendations = []  # 预加载的推荐数据
        self.is_preloading = False  # 是否正在预加载
        self.preload_thread = None  # 预加载线程
        
        # 性能优化：UI更新节流
        self._display_update_timer = QTimer(self)
        self._display_update_timer.setSingleShot(True)
        self._display_update_timer.timeout.connect(self._process_display_queue)
        self._display_queue = []  # 待显示的推荐项队列
        self._batch_display_size = 10  # 每批显示的数量

        # 封面更新信号
        self._cover_update_signal = CoverUpdateSignal()
        self._cover_update_signal.update_cover.connect(self._on_cover_update)

    def _init_player_components(self):
        """预初始化播放器组件 - 提高首次播放响应速度"""
        try:
            # 预导入视频播放器模块
            from utils.video_player import VIDEO_CACHE_DIR
            import os
            
            # 确保缓存目录存在
            if not os.path.exists(VIDEO_CACHE_DIR):
                os.makedirs(VIDEO_CACHE_DIR, exist_ok=True)
            
            # 预检查yt-dlp是否可用
            try:
                import yt_dlp
                self.ytdlp_available = True
                print("[播放器初始化] yt-dlp 已就绪")
            except ImportError:
                self.ytdlp_available = False
                print("[播放器初始化] yt-dlp 未安装")
            
            # 初始化播放器状态
            self.current_playing_video = None
            self.player_initialized = True
            print("[播放器初始化] 内置播放器组件预初始化完成")
        except Exception as e:
            print(f"[播放器初始化] 预初始化失败: {e}")
            self.player_initialized = False

        # 服务
        self.recommend_service = RecommendService()
        self.cloud_control = CloudControl()
        self.share_service = ShareService()
        self.community_system = get_community_system()

        # 智能推荐服务
        try:
            from services.recommend_engine.intelligent import IntelligentRecommendEngine
            self.intelligent_engine = IntelligentRecommendEngine()
            print("智能推荐服务加载成功")
        except Exception as e:
            print(f"智能推荐服务加载失败: {e}")
            self.intelligent_engine = None

        # 高级推荐服务
        try:
            from services.recommend_engine.advanced import AdvancedRecommendEngine
            self.advanced_engine = AdvancedRecommendEngine()
            print("高级推荐服务加载成功")
        except Exception as e:
            print(f"高级推荐服务加载失败: {e}")
            self.advanced_engine = None

        # 启动API服务器
        api_url = start_api_server()
        if api_url:
            print(f"API服务器启动成功: {api_url}")

        # 登录状态
        self.logged_in = False
        self.current_user = None
        self.auth_token = None

        # 初始化数据
        self._init_user_data()

    def _init_user_data(self):
        """初始化用户数据"""
        self.load_favorites_and_excluded()
        try:
            self.playlists = load_playlists()
        except Exception as e:
            logger.error(f"加载播放列表失败: {e}")
            self.playlists = []

        self.create_menu_bar()
        self.setup_ui()
        self.apply_theme()
        self.show_loading_screen()
        QTimer.singleShot(100, self._load_recommendations_with_restore)
        QTimer.singleShot(200, self._show_login_if_needed)

    def load_custom_font(self):
        """加载自定义字体"""
        from PyQt5.QtGui import QFontDatabase
        
        font_path = os.path.join(os.path.dirname(__file__), 'assets', 'fonts', '原神风格字体.ttf')
        
        if os.path.exists(font_path):
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id != -1:
                font_families = QFontDatabase.applicationFontFamilies(font_id)
                if font_families:
                    self.genshin_font = QFont(font_families[0], 10, QFont.Medium)
                    self.genshin_font.setStyleStrategy(QFont.PreferAntialias)
                    print(f"成功加载自定义字体: {font_families[0]}")
                else:
                    print("加载字体失败：无法获取字体族")
            else:
                print("加载字体失败：QFontDatabase.addApplicationFont 返回 -1")
        else:
            print(f"自定义字体文件不存在: {font_path}")

    def get_available_fonts(self):
        """获取系统中可用的字体列表"""
        from PyQt5.QtGui import QFontDatabase
        all_fonts = QFontDatabase().families()
        return all_fonts

    def get_custom_font_name(self):
        """获取自定义字体的显示名称"""
        from PyQt5.QtGui import QFontDatabase
        font_path = os.path.join(os.path.dirname(__file__), 'assets', 'fonts', '原神风格字体.ttf')
        if os.path.exists(font_path):
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id != -1:
                font_families = QFontDatabase.applicationFontFamilies(font_id)
                if font_families:
                    return font_families[0]
        return "原神风格字体"

    def _show_login_if_needed(self):
        """显示登录对话框（如需要）"""
        # 遮罩层已经显示，等待用户操作
        pass
    
    def show_login_dialog(self):
        """显示登录对话框（支持从游客模式切换）"""
        dialog = LoginDialog(self)
        result = dialog.exec_()

        if result == QDialog.Accepted:
            username = dialog.username_input.text().strip()
            password = dialog.password_input.text().strip()

            # 调用认证服务
            token = user_auth.login(username, password)

            if token:
                # 登录成功
                self.logged_in = True
                self.current_user = username
                self.auth_token = token
                print(f"用户 {self.current_user} 登录成功")
                
                # 隐藏遮罩层（如果存在）
                self.hide_login_overlay()
                
                # 显示登录成功提示
                QMessageBox.information(self, "登录成功", f"欢迎回来，{username}！")
            else:
                # 登录失败，提示错误
                QMessageBox.warning(self, "登录失败", "用户名或密码错误")
                print("登录失败：用户名或密码错误")
    
    def show_register_dialog(self):
        """显示注册对话框"""
        dialog = RegisterDialog(self)
        result = dialog.exec_()

        if result == QDialog.Accepted:
            username = dialog.username_input.text().strip()
            password = dialog.password_input.text().strip()

            # 调用注册服务
            success = user_auth.register(username, password)

            if success:
                # 注册成功
                QMessageBox.information(self, "注册成功", f"账号 {username} 注册成功！请登录。")
                print(f"用户 {username} 注册成功")
                # 自动打开登录对话框
                self.show_login_dialog()
            else:
                # 注册失败
                QMessageBox.warning(self, "注册失败", "用户名已存在或注册失败")
                print("注册失败：用户名已存在")
    
    def login_as_guest(self):
        """以游客身份登录"""
        self.logged_in = False
        self.current_user = "guest"
        self.auth_token = None
        print("以游客身份继续")
    
    def logout(self):
        """退出登录"""
        # 调用认证服务注销
        if self.auth_token:
            user_auth.logout(self.auth_token)
        
        # 重置登录状态
        self.logged_in = False
        self.current_user = "guest"
        self.auth_token = None
        
        # 切换到游客数据
        self.load_guest_data()
        
        QMessageBox.information(self, "退出成功", "已退出登录，将以游客身份继续")
        print("用户已退出登录")
    
    def load_guest_data(self):
        """加载游客数据"""
        # 切换到默认/游客数据
        self.favorites = []
        self.playlists = []
        self.excluded = []
        # 从默认目录加载数据
        default_data_dir = os.path.join(os.path.dirname(__file__), 'data', 'default')
        if os.path.exists(default_data_dir):
            # 加载收藏
            fav_file = os.path.join(default_data_dir, 'favorites.json')
            if os.path.exists(fav_file):
                try:
                    with open(fav_file, 'r', encoding='utf-8') as f:
                        self.favorites = json.load(f)
                except:
                    pass
            # 加载播放列表
            playlist_file = os.path.join(default_data_dir, 'playlists.json')
            if os.path.exists(playlist_file):
                try:
                    with open(playlist_file, 'r', encoding='utf-8') as f:
                        self.playlists = json.load(f)
                except:
                    pass
            # 加载排除列表
            excluded_file = os.path.join(default_data_dir, 'excluded.json')
            if os.path.exists(excluded_file):
                try:
                    with open(excluded_file, 'r', encoding='utf-8') as f:
                        self.excluded = json.load(f)
                except:
                    pass
        # 隐藏遮罩层
        self.hide_login_overlay()
    
    def hide_login_overlay(self):
        """隐藏登录遮罩层"""
        if hasattr(self, 'login_overlay'):
            self.login_overlay.hide()
            # 启用主界面交互
            self.setCentralWidget(self.centralWidget())

    def resizeEvent(self, event):
        """处理窗口大小变化事件"""
        super().resizeEvent(event)
        # 更新遮罩层大小
        if hasattr(self, 'login_overlay') and self.login_overlay.isVisible():
            self.login_overlay.setGeometry(self.rect())
        # 延迟一下，确保窗口大小已经稳定
        if not hasattr(self, 'resize_timer'):
            self.resize_timer = QTimer(self)
            self.resize_timer.setSingleShot(True)
            self.resize_timer.timeout.connect(self._on_resize_complete)
        
        self.resize_timer.stop()
        self.resize_timer.start(300)  # 延迟300ms后处理
    
    def _on_resize_complete(self):
        """窗口大小变化完成后重新布局"""
        # 只重新布局，不重新加载数据
        if hasattr(self, 'recommend_layout') and self.recommend_layout:
            # 获取当前显示的推荐数据
            current_items = []
            for i in range(self.recommend_layout.count()):
                item = self.recommend_layout.itemAt(i)
                if item and item.widget():
                    widget = item.widget()
                    video_data = widget.property('video_data')
                    if video_data:
                        current_items.append(video_data)
            
            # 如果有数据，重新显示
            if current_items:
                self.display_recommendations(current_items)
    
    def create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()
        
        # 根据当前显示模式生成样式
        display_mode = self.settings.get('display_mode', 'light')
        
        if display_mode == 'dark':
            menubar.setStyleSheet("""
                QMenuBar {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #121212, stop:1 #1e1e1e);
                    border-bottom: 1px solid #333333;
                    padding: 5px 10px;
                }
                QMenuBar::item {
                    background: transparent;
                    padding: 8px 15px;
                    border-radius: 4px;
                    color: #e0e0e0;
                }
                QMenuBar::item:selected {
                    background: rgba(88, 166, 255, 0.2);
                    color: #58a6ff;
                }
                QMenu {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #1e1e1e, stop:1 #2a2a2a);
                    border: 1px solid #333333;
                    border-radius: 6px;
                    padding: 5px;
                }
                QMenu::item {
                    padding: 8px 20px;
                    border-radius: 4px;
                    color: #e0e0e0;
                }
                QMenu::item:selected {
                    background: rgba(88, 166, 255, 0.2);
                    color: #58a6ff;
                }
                QMenu::item:disabled {
                    color: #666666;
                }
                QMenu::separator {
                    background: #333333;
                    height: 1px;
                    margin: 2px 0;
                }
            """)
        else:
            menubar.setStyleSheet("""
                QMenuBar {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #f5f7fa, stop:1 #c3cfe2);
                    border-bottom: 1px solid #e0e0e0;
                    padding: 5px 10px;
                }
                QMenuBar::item {
                    background: transparent;
                    padding: 8px 15px;
                    border-radius: 4px;
                    color: #2c3e50;
                }
                QMenuBar::item:selected {
                    background: rgba(52, 152, 219, 0.2);
                    color: #3498db;
                }
                QMenu {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #f5f7fa, stop:1 #c3cfe2);
                    border: 1px solid #e0e0e0;
                    border-radius: 6px;
                    padding: 5px;
                }
                QMenu::item {
                    padding: 8px 20px;
                    border-radius: 4px;
                    color: #2c3e50;
                }
                QMenu::item:selected {
                    background: rgba(52, 152, 219, 0.2);
                    color: #3498db;
                }
                QMenu::item:disabled {
                    color: #95a5a6;
                }
                QMenu::separator {
                    background: #e0e0e0;
                    height: 1px;
                    margin: 2px 0;
                }
            """)
        
        # 文件菜单
        file_menu = menubar.addMenu("文件(&F)")
        
        refresh_action = file_menu.addAction("刷新推荐(&R)")
        refresh_action.setShortcut("Ctrl+R")
        refresh_action.triggered.connect(self.refresh_recommendations)
        
        file_menu.addSeparator()
        
        exit_action = file_menu.addAction("退出(&X)")
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        
        # 收藏菜单
        favorites_menu = menubar.addMenu("收藏(&C)")
        
        manage_fav_action = favorites_menu.addAction("管理收藏(&F)")
        manage_fav_action.setShortcut("Ctrl+F")
        manage_fav_action.triggered.connect(self.show_favorites)
        
        manage_excluded_action = favorites_menu.addAction("管理排除(&E)")
        manage_excluded_action.setShortcut("Ctrl+E")
        manage_excluded_action.triggered.connect(self.show_excluded)
        
        # 播放列表菜单
        playlist_menu = menubar.addMenu("播放列表(&P)")
        
        toggle_playlist_action = playlist_menu.addAction("显示/隐藏播放列表(&S)")
        toggle_playlist_action.setShortcut("Ctrl+L")
        toggle_playlist_action.triggered.connect(self.toggle_playlist_sidebar)
        
        playlist_menu.addSeparator()
        
        new_playlist_action = playlist_menu.addAction("新建播放列表(&N)")
        new_playlist_action.setShortcut("Ctrl+Shift+N")
        new_playlist_action.triggered.connect(self.create_new_playlist)
        
        # 社交菜单
        social_menu = menubar.addMenu("社交(&O)")
        
        social_feed_action = social_menu.addAction("社区动态(&F)")
        social_feed_action.setShortcut("Ctrl+D")
        social_feed_action.triggered.connect(self.show_social_feed)
        
        profile_action = social_menu.addAction("个人资料(&P)")
        profile_action.setShortcut("Ctrl+U")
        profile_action.triggered.connect(self.show_user_profile)
        
        social_menu.addSeparator()
        
        share_history_action = social_menu.addAction("分享历史(&H)")
        share_history_action.setShortcut("Ctrl+H")
        share_history_action.triggered.connect(self.show_share_history)
        
        share_action = social_menu.addAction("分享设置(&S)")
        share_action.triggered.connect(lambda: QMessageBox.information(self, "分享设置", "分享功能已集成在右键菜单中"))
        
        # 设置菜单
        settings_menu = menubar.addMenu("设置(&S)")
        
        settings_action = settings_menu.addAction("设置(&S)")
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self.show_settings)
        
        # 小工具菜单
        tools_menu = menubar.addMenu("小工具(&T)")
        
        bv_query_action = tools_menu.addAction("BV/AV号查询(&B)")
        bv_query_action.setShortcut("Ctrl+B")
        bv_query_action.triggered.connect(self.show_bv_query_dialog)
        
        tools_menu.addSeparator()
        
        download_action = tools_menu.addAction("视频下载(&D)")
        download_action.setShortcut("Ctrl+D")
        download_action.triggered.connect(self.show_download_dialog)
        
        tools_menu.addSeparator()
        
        keyword_action = tools_menu.addAction("关键词管理(&K)")
        keyword_action.setShortcut("Ctrl+K")
        keyword_action.triggered.connect(self.show_keyword_manager)
        
        # 帮助菜单
        help_menu = menubar.addMenu("帮助(&H)")
        
        about_action = help_menu.addAction("关于(&A)")
        about_action.triggered.connect(self.show_about)
    
    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(self, "关于", 
            "智能音乐推荐与分享系统 (融合版)\n\n"
            "版本: 1.0.0\n"
            "基于VocaloidToolboxFusion开发\n\n"
            "功能:\n"
            "• 智能音乐推荐\n"
            "• 收藏管理\n"
            "• 排除列表\n"
            "• 社交分享\n"
            "• 云端同步")
    
    def setup_playlist_sidebar_for_splitter(self):
        """设置播放列表侧边栏 - 用于QSplitter，支持拖拽调整宽度"""
        self.playlist_sidebar = QWidget()
        self.playlist_sidebar.setObjectName("playlist_sidebar")
        self.playlist_sidebar.setMinimumWidth(180)
        self.playlist_sidebar.setMaximumWidth(600)
        
        # 获取显示模式
        display_mode = self.settings.get('display_mode', 'light')
        
        # 根据显示模式设置侧边栏样式
        if display_mode == 'dark':
            self.playlist_sidebar.setStyleSheet("""
                QWidget#playlist_sidebar {
                    background: rgba(42, 42, 42, 0.95);
                    border-left: 2px solid #404040;
                    border-radius: 0;
                }
            """)
        else:
            self.playlist_sidebar.setStyleSheet("""
                QWidget#playlist_sidebar {
                    background: rgba(255, 255, 255, 0.95);
                    border-left: 2px solid #e0e0e0;
                    border-radius: 0;
                }
            """)
        
        sidebar_layout = QVBoxLayout(self.playlist_sidebar)
        sidebar_layout.setSpacing(10)
        sidebar_layout.setContentsMargins(10, 10, 10, 10)
        
        # 播放列表标题栏
        header_layout = QHBoxLayout()
        
        playlist_title = QLabel("📋 播放列表")
        
        # 根据显示模式设置标题样式
        if display_mode == 'dark':
            playlist_title.setStyleSheet("""
                QLabel {
                    font-size: 16px;
                    font-weight: bold;
                    color: #e0e0e0;
                }
            """)
        else:
            playlist_title.setStyleSheet("""
                QLabel {
                    font-size: 16px;
                    font-weight: bold;
                    color: #2c3e50;
                }
            """)
        playlist_title.setFont(self.genshin_font)
        header_layout.addWidget(playlist_title)
        
        header_layout.addStretch()
        
        # 关闭按钮
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        
        # 根据显示模式设置关闭按钮样式
        if display_mode == 'dark':
            close_btn.setStyleSheet("""
                QPushButton {
                    border: none;
                    background: transparent;
                    color: #999;
                    font-size: 14px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    color: #e74c3c;
                    background: rgba(231, 76, 60, 0.1);
                    border-radius: 4px;
                }
            """)
        else:
            close_btn.setStyleSheet("""
                QPushButton {
                    border: none;
                    background: transparent;
                    color: #999;
                    font-size: 14px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    color: #e74c3c;
                    background: rgba(231, 76, 60, 0.1);
                    border-radius: 4px;
                }
            """)
        close_btn.clicked.connect(self.toggle_playlist_sidebar)
        header_layout.addWidget(close_btn)
        
        sidebar_layout.addLayout(header_layout)
        
        # 播放列表选择
        self.playlist_combo = QComboBox()
        self.playlist_combo.setFont(self.genshin_font)
        
        # 根据显示模式设置下拉框样式
        if display_mode == 'dark':
            self.playlist_combo.setStyleSheet("""
                QComboBox {
                    padding: 8px;
                    border: 2px solid #505050;
                    border-radius: 6px;
                    background: #2a2a2a;
                    color: #e0e0e0;
                }
                QComboBox:focus {
                    border: 2px solid #3498db;
                }
                QComboBox QAbstractItemView {
                    background: #2a2a2a;
                    color: #e0e0e0;
                    border: 1px solid #505050;
                }
            """)
        else:
            self.playlist_combo.setStyleSheet("""
                QComboBox {
                    padding: 8px;
                    border: 2px solid #e0e0e0;
                    border-radius: 6px;
                    background: white;
                }
                QComboBox:focus {
                    border: 2px solid #3498db;
                }
            """)
        self.playlist_combo.currentIndexChanged.connect(self.on_playlist_selected)
        sidebar_layout.addWidget(self.playlist_combo)
        
        # 新建按钮区域
        new_btn_layout = QHBoxLayout()
        
        # 新建歌单按钮（永久）
        new_playlist_btn = QPushButton("➕ 新歌单")
        new_playlist_btn.setFont(self.genshin_font)
        new_playlist_btn.setToolTip("创建永久保存的歌单")
        
        # 新建临时播放列表按钮
        new_temp_btn = QPushButton("⚡ 临时")
        new_temp_btn.setFont(self.genshin_font)
        new_temp_btn.setToolTip("创建可随时清空的临时播放列表")
        
        # 根据显示模式设置按钮样式
        if display_mode == 'dark':
            btn_style = """
                QPushButton {
                    padding: 8px 12px;
                    border: 2px dashed #555555;
                    border-radius: 6px;
                    background: transparent;
                    color: #999;
                    font-size: 12px;
                }
                QPushButton:hover {
                    border-color: #3498db;
                    color: #3498db;
                    background: rgba(52, 152, 219, 0.1);
                }
            """
        else:
            btn_style = """
                QPushButton {
                    padding: 8px 12px;
                    border: 2px dashed #bdc3c7;
                    border-radius: 6px;
                    background: transparent;
                    color: #7f8c8d;
                    font-size: 12px;
                }
                QPushButton:hover {
                    border-color: #3498db;
                    color: #3498db;
                    background: rgba(52, 152, 219, 0.05);
                }
            """
        new_playlist_btn.setStyleSheet(btn_style)
        new_temp_btn.setStyleSheet(btn_style)
        
        new_playlist_btn.clicked.connect(lambda: self.create_new_playlist('permanent'))
        new_temp_btn.clicked.connect(lambda: self.create_new_playlist('temporary'))
        
        new_btn_layout.addWidget(new_playlist_btn)
        new_btn_layout.addWidget(new_temp_btn)
        sidebar_layout.addLayout(new_btn_layout)
        
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        
        # 根据显示模式设置分隔线样式
        if display_mode == 'dark':
            line.setStyleSheet("background: #555555;")
        else:
            line.setStyleSheet("background: #e0e0e0;")
        line.setFixedHeight(1)
        sidebar_layout.addWidget(line)
        
        # 当前播放列表内容
        self.playlist_content_label = QLabel("暂无播放列表")
        self.playlist_content_label.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        self.playlist_content_label.setFont(self.genshin_font)
        self.playlist_content_label.setWordWrap(True)
        sidebar_layout.addWidget(self.playlist_content_label)
        
        # 播放列表项目列表 - 使用自定义项实现跑马灯效果
        self.playlist_items_list = QListWidget()
        # 初始样式会在apply_theme中设置，这里只设置基本属性
        self.playlist_items_list.setFrameShape(QListWidget.NoFrame)
        self.playlist_items_list.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.playlist_items_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.playlist_items_list.setFont(self.genshin_font)
        self.playlist_items_list.itemDoubleClicked.connect(self.play_playlist_item)
        # 启用右键菜单
        self.playlist_items_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.playlist_items_list.customContextMenuRequested.connect(self.show_playlist_context_menu)
        sidebar_layout.addWidget(self.playlist_items_list, 1)
        
        # 播放控制按钮
        control_layout = QHBoxLayout()
        
        play_all_btn = QPushButton("▶ 播放全部")
        play_all_btn.setFont(self.genshin_font)
        play_all_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 16px;
                border: none;
                border-radius: 6px;
                background: #3498db;
                color: white;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #2980b9;
            }
        """)
        play_all_btn.clicked.connect(self.play_all_in_playlist)
        control_layout.addWidget(play_all_btn)
        
        # 上一首按钮
        prev_btn = QPushButton("⏮")
        prev_btn.setFixedSize(36, 36)
        prev_btn.setFont(self.genshin_font)
        prev_btn.setToolTip("上一首")
        prev_btn.setStyleSheet("""
            QPushButton {
                border: 2px solid rgba(52, 152, 219, 0.5);
                border-radius: 6px;
                background: rgba(52, 152, 219, 0.15);
                color: #3498db;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(52, 152, 219, 0.3);
                border-color: rgba(52, 152, 219, 0.8);
            }
        """)
        prev_btn.clicked.connect(self.play_previous)
        control_layout.addWidget(prev_btn)
        
        # 下一首按钮
        next_btn = QPushButton("⏭")
        next_btn.setFixedSize(36, 36)
        next_btn.setFont(self.genshin_font)
        next_btn.setToolTip("下一首")
        next_btn.setStyleSheet("""
            QPushButton {
                border: 2px solid rgba(52, 152, 219, 0.5);
                border-radius: 6px;
                background: rgba(52, 152, 219, 0.15);
                color: #3498db;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(52, 152, 219, 0.3);
                border-color: rgba(52, 152, 219, 0.8);
            }
        """)
        next_btn.clicked.connect(self.play_next)
        control_layout.addWidget(next_btn)
        
        # 定位到当前播放按钮
        locate_btn = QPushButton("🎯")
        locate_btn.setFixedSize(36, 36)
        locate_btn.setFont(self.genshin_font)
        locate_btn.setToolTip("定位到当前播放")
        locate_btn.setStyleSheet("""
            QPushButton {
                border: 2px solid rgba(46, 204, 113, 0.5);
                border-radius: 6px;
                background: rgba(46, 204, 113, 0.15);
                color: #2ecc71;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(46, 204, 113, 0.3);
                border-color: rgba(46, 204, 113, 0.8);
            }
        """)
        locate_btn.clicked.connect(self.locate_current_playing)
        control_layout.addWidget(locate_btn)
        
        # 排序按钮
        sort_btn = QPushButton("⇅")
        sort_btn.setFixedSize(36, 36)
        sort_btn.setFont(self.genshin_font)
        sort_btn.setToolTip("排序")
        sort_btn.setStyleSheet("""
            QPushButton {
                border: 2px solid rgba(155, 89, 182, 0.5);
                border-radius: 6px;
                background: rgba(155, 89, 182, 0.15);
                color: #9b59b6;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(155, 89, 182, 0.3);
                border-color: rgba(155, 89, 182, 0.8);
            }
        """)
        sort_btn.clicked.connect(self.show_sort_menu)
        control_layout.addWidget(sort_btn)
        
        clear_btn = QPushButton("🗑")
        clear_btn.setFixedSize(36, 36)
        clear_btn.setFont(self.genshin_font)
        clear_btn.setToolTip("清空当前列表")
        clear_btn.setStyleSheet("""
            QPushButton {
                border: 2px solid rgba(231, 76, 60, 0.5);
                border-radius: 6px;
                background: rgba(231, 76, 60, 0.15);
                color: #e74c3c;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(231, 76, 60, 0.3);
                border-color: rgba(231, 76, 60, 0.8);
            }
        """)
        clear_btn.clicked.connect(self.clear_current_playlist)
        control_layout.addWidget(clear_btn)
        
        sidebar_layout.addLayout(control_layout)
        
        # 添加到主分割器
        self.main_splitter.addWidget(self.playlist_sidebar)
        
        # 初始化播放列表数据
        self.update_playlist_combo()
    
    def toggle_playlist_sidebar(self):
        """切换播放列表侧边栏显示/隐藏 - 自动调整列数"""
        sidebar_index = self.main_splitter.indexOf(self.playlist_sidebar)
        if sidebar_index < 0:
            return
        
        if self.playlist_sidebar_visible:
            self.main_splitter.setSizes([self.main_splitter.width(), 0])
            self.playlist_sidebar_visible = False
        else:
            self.main_splitter.setSizes([self.main_splitter.width() - 250, 250])
            self.update_playlist_combo()
            self.playlist_sidebar_visible = True
        
        QTimer.singleShot(300, self._refresh_card_layout)
    
    def update_playlist_combo(self):
        """更新播放列表下拉框 - 区分临时和永久"""
        self.playlist_combo.clear()
        if not self.playlists:
            self.playlist_combo.addItem("暂无播放列表/歌单")
            self.playlist_content_label.setText("点击上方按钮创建")
            self.playlist_items_list.clear()
            return
        
        # 分离临时和永久列表
        temp_playlists = [(i, p) for i, p in enumerate(self.playlists) if p.get('type') == 'temporary']
        perm_playlists = [(i, p) for i, p in enumerate(self.playlists) if p.get('type') == 'permanent']
        
        # 先添加临时播放列表
        if temp_playlists:
            for idx, playlist in temp_playlists:
                name = playlist.get('name', '未命名')
                self.playlist_combo.addItem(f"⚡ {name}")
        
        # 再添加永久歌单
        if perm_playlists:
            for idx, playlist in perm_playlists:
                name = playlist.get('name', '未命名')
                self.playlist_combo.addItem(f"📁 {name}")
    
    def get_playlist_by_combo_index(self, combo_index):
        """根据下拉框索引获取播放列表"""
        temp_playlists = [(i, p) for i, p in enumerate(self.playlists) if p.get('type') == 'temporary']
        perm_playlists = [(i, p) for i, p in enumerate(self.playlists) if p.get('type') == 'permanent']
        
        all_playlists = temp_playlists + perm_playlists
        if 0 <= combo_index < len(all_playlists):
            return all_playlists[combo_index]
        return None, None
    
    def _refresh_card_layout(self):
        """刷新卡片布局 - 在侧边栏切换后重新计算列数"""
        if not hasattr(self, 'recommend_layout') or not self.recommend_layout:
            return
        
        # 获取当前所有推荐数据
        current_recommendations = []
        for i in range(self.recommend_layout.count()):
            item = self.recommend_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                if hasattr(widget, 'video_data'):
                    current_recommendations.append(widget.video_data)
        
        if current_recommendations:
            # 清空并重新显示，使用新的列数
            self._clear_recommend_layout()
            self.display_recommendations(current_recommendations)
            
            # 计算新的列数
            viewport_width = self.recommend_scroll.viewport().width()
            card_width = self._calculate_card_width()
            cols = max(1, (viewport_width + 2) // (card_width + 2))
            print(f"侧边栏切换后重新布局: {cols}列, 卡片宽度: {card_width}px")
    
    def on_playlist_selected(self, index):
        """播放列表选择变化 - 显示类型和操作按钮，使用自定义项实现跑马灯"""
        playlist_index, playlist = self.get_playlist_by_combo_index(index)
        if playlist is None:
            return
        
        items = playlist.get('items', [])
        playlist_type = playlist.get('type', 'permanent')
        playlist_name = playlist.get('name', '未命名')
        
        # 根据类型显示不同信息
        if playlist_type == 'temporary':
            type_str = "⚡ 临时播放列表"
            # 更新清空按钮提示
            for i in range(self.playlist_items_list.parent().layout().count()):
                layout_item = self.playlist_items_list.parent().layout().itemAt(i)
                if layout_item and layout_item.layout():
                    control_layout = layout_item.layout()
                    for j in range(control_layout.count()):
                        widget = control_layout.itemAt(j).widget()
                        if widget and isinstance(widget, QPushButton) and widget.toolTip() == "清空当前列表":
                            widget.setToolTip(f"🗑️ 清空临时列表 '{playlist_name}'")
                            break
        else:
            type_str = "📁 永久歌单"
            # 更新清空按钮提示
            for i in range(self.playlist_items_list.parent().layout().count()):
                layout_item = self.playlist_items_list.parent().layout().itemAt(i)
                if layout_item and layout_item.layout():
                    control_layout = layout_item.layout()
                    for j in range(control_layout.count()):
                        widget = control_layout.itemAt(j).widget()
                        if widget and isinstance(widget, QPushButton) and widget.toolTip().startswith("🗑️"):
                            widget.setToolTip(f"⚠️ 清空歌单 '{playlist_name}'（谨慎操作）")
                            break
        
        self.playlist_content_label.setText(f"{type_str}  •  {len(items)} 个视频")
        
        self.playlist_items_list.clear()
        for i, item in enumerate(items):
            title = item.get('title', '未知标题')
            # 创建自定义列表项
            list_item = QListWidgetItem()
            list_item.setData(Qt.UserRole, item)  # 存储完整数据
            list_item.setText(title)  # 显示完整标题
            list_item.setToolTip(title)  # 鼠标悬停显示完整标题
            self.playlist_items_list.addItem(list_item)
    
    def create_new_playlist(self, playlist_type='permanent'):
        """创建新播放列表/歌单
        
        Args:
            playlist_type: 'permanent' 为永久歌单，'temporary' 为临时播放列表
        """
        from PyQt5.QtWidgets import QInputDialog
        
        if playlist_type == 'temporary':
            title = "新建临时播放列表"
            label = "临时播放列表名称（可随时清空）:"
            default_name = f"临时列表 {len([p for p in self.playlists if p.get('type') == 'temporary']) + 1}"
        else:
            title = "新建歌单"
            label = "歌单名称（永久保存）:"
            default_name = ""
        
        name, ok = QInputDialog.getText(self, title, label, text=default_name)
        if ok and name.strip():
            new_playlist = {
                'name': name.strip(),
                'items': [],
                'created_at': datetime.now().isoformat(),
                'type': playlist_type,  # 区分类型
                'description': ''
            }
            self.playlists.append(new_playlist)
            save_playlists(self.playlists)
            self.update_playlist_combo()
            # 选中新创建的播放列表
            self.playlist_combo.setCurrentIndex(len(self.playlists) - 1)
            
            type_str = "临时播放列表" if playlist_type == 'temporary' else "歌单"
            QMessageBox.information(self, "成功", f"{type_str} '{name}' 创建成功！")
    
    def show_playlist_context_menu(self, position):
        """显示播放列表右键菜单"""
        combo_index = self.playlist_combo.currentIndex()
        playlist_index, playlist = self.get_playlist_by_combo_index(combo_index)
        
        if playlist is None:
            return
        
        playlist_type = playlist.get('type', 'permanent')
        
        menu = QMenu(self)
        menu.setFont(self.genshin_font)
        
        # 根据类型显示不同菜单项
        if playlist_type == 'temporary':
            # 临时播放列表 - 可清空
            clear_action = QAction("🗑️ 清空临时列表", self)
            clear_action.triggered.connect(lambda: self.clear_temporary_playlist(playlist_index))
            menu.addAction(clear_action)
            
            # 临时列表也可以删除
            delete_action = QAction("❌ 删除临时列表", self)
            delete_action.triggered.connect(lambda: self.delete_permanent_playlist(playlist_index))
            menu.addAction(delete_action)
        else:
            # 永久歌单 - 需要确认删除
            delete_action = QAction("❌ 删除歌单", self)
            delete_action.triggered.connect(lambda: self.delete_permanent_playlist(playlist_index))
            menu.addAction(delete_action)
        
        # 通用菜单项
        menu.addSeparator()
        
        rename_action = QAction("✏️ 重命名", self)
        rename_action.triggered.connect(lambda: self.rename_playlist(playlist_index))
        menu.addAction(rename_action)
        
        # 导出歌单
        export_action = QAction("📤 导出歌单", self)
        export_action.triggered.connect(lambda: self.export_playlist(playlist_index))
        menu.addAction(export_action)
        
        # 批量分享
        share_action = QAction("🔗 批量分享", self)
        share_action.triggered.connect(lambda: self.share_playlist(playlist_index))
        menu.addAction(share_action)
        
        # 显示菜单
        menu.exec_(self.playlist_items_list.mapToGlobal(position))
    
    def clear_temporary_playlist(self, index):
        """清空临时播放列表"""
        playlist = self.playlists[index]
        playlist['items'] = []
        self.save_playlists()
        self.on_playlist_selected(index)
        QMessageBox.information(self, "成功", f"已清空临时播放列表 '{playlist.get('name')}'")
    
    def delete_permanent_playlist(self, index):
        """删除永久歌单（需要确认）"""
        playlist = self.playlists[index]
        name = playlist.get('name', '未命名')
        item_count = len(playlist.get('items', []))
        
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除歌单 '{name}' 吗？\n"
            f"该歌单包含 {item_count} 个视频，删除后无法恢复。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            del self.playlists[index]
            self.save_playlists()
            self.update_playlist_combo()
            QMessageBox.information(self, "成功", f"歌单 '{name}' 已删除")
    
    def rename_playlist(self, index):
        """重命名播放列表/歌单"""
        from PyQt5.QtWidgets import QInputDialog
        
        playlist = self.playlists[index]
        old_name = playlist.get('name', '')
        
        new_name, ok = QInputDialog.getText(
            self,
            "重命名",
            "请输入新名称:",
            text=old_name
        )
        
        if ok and new_name.strip() and new_name.strip() != old_name:
            playlist['name'] = new_name.strip()
            self.save_playlists()
            self.update_playlist_combo()
            self.playlist_combo.setCurrentIndex(index)
            QMessageBox.information(self, "成功", f"已重命名为 '{new_name}'")
    
    def export_playlist(self, index):
        """导出播放列表为JSON文件"""
        from PyQt5.QtWidgets import QFileDialog
        import json
        
        playlist = self.playlists[index]
        name = playlist.get('name', '未命名')
        items = playlist.get('items', [])
        
        if not items:
            QMessageBox.information(self, "提示", "歌单为空，无需导出")
            return
        
        # 选择保存路径
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出歌单",
            f"{name}.json",
            "JSON文件 (*.json);;所有文件 (*.*)"
        )
        
        if file_path:
            try:
                export_data = {
                    'name': name,
                    'type': playlist.get('type', 'permanent'),
                    'description': playlist.get('description', ''),
                    'created_at': playlist.get('created_at', ''),
                    'exported_at': datetime.now().isoformat(),
                    'items_count': len(items),
                    'items': items
                }
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, ensure_ascii=False, indent=2)
                
                QMessageBox.information(self, "成功", f"歌单 '{name}' 已导出到:\n{file_path}")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"导出失败: {e}")
    
    def share_playlist(self, index):
        """分享整个播放列表"""
        playlist = self.playlists[index]
        name = playlist.get('name', '未命名')
        items = playlist.get('items', [])
        
        if not items:
            QMessageBox.information(self, "提示", "歌单为空，无法分享")
            return
        
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QTextEdit
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"分享歌单: {name}")
        dialog.setFixedSize(500, 400)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title_label = QLabel(f"📤 {name}")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        title_label.setFont(self.genshin_font)
        layout.addWidget(title_label)
        
        # 统计信息
        info_label = QLabel(f"共 {len(items)} 个视频")
        info_label.setStyleSheet("color: #7f8c8d; font-size: 13px;")
        info_label.setFont(self.genshin_font)
        layout.addWidget(info_label)
        
        # 生成分享文本
        share_text = f"🎵 歌单: {name}\n"
        share_text += f"📊 共 {len(items)} 个视频\n"
        share_text += "━" * 30 + "\n\n"
        
        for i, item in enumerate(items[:10], 1):  # 只显示前10个
            title = item.get('title', '未知标题')
            up = item.get('up', '未知UP主')
            share_text += f"{i}. {title}\n   👤 {up}\n\n"
        
        if len(items) > 10:
            share_text += f"... 还有 {len(items) - 10} 个视频\n\n"
        
        share_text += "━" * 30 + "\n"
        share_text += "🎧 来自 AI音乐推荐系统"
        
        # 文本框
        text_edit = QTextEdit()
        text_edit.setPlainText(share_text)
        text_edit.setFont(self.genshin_font)
        text_edit.setStyleSheet("""
            QTextEdit {
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                padding: 10px;
                font-size: 13px;
                background: #f9f9f9;
            }
        """)
        layout.addWidget(text_edit, 1)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        
        copy_btn = QPushButton("📋 复制全部")
        copy_btn.setFont(self.genshin_font)
        copy_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 20px;
                border: none;
                border-radius: 6px;
                background: #3498db;
                color: white;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #2980b9;
            }
        """)
        copy_btn.clicked.connect(lambda: self._copy_text_and_close(text_edit.toPlainText(), dialog))
        btn_layout.addWidget(copy_btn)
        
        export_btn = QPushButton("💾 导出JSON")
        export_btn.setFont(self.genshin_font)
        export_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 20px;
                border: 2px solid #9b59b6;
                border-radius: 6px;
                background: white;
                color: #9b59b6;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #9b59b6;
                color: white;
            }
        """)
        export_btn.clicked.connect(lambda: [self.export_playlist(index), dialog.close()])
        btn_layout.addWidget(export_btn)
        
        btn_layout.addStretch()
        
        close_btn = QPushButton("关闭")
        close_btn.setFont(self.genshin_font)
        close_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 20px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                background: #f9f9f9;
                color: #2c3e50;
            }
            QPushButton:hover {
                background: #e9ecef;
            }
        """)
        close_btn.clicked.connect(dialog.close)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        dialog.exec_()
    
    def _copy_text_and_close(self, text, dialog):
        """复制文本并关闭对话框"""
        QApplication.clipboard().setText(text)
        dialog.close()
        self._show_toast("✅ 歌单信息已复制")
    
    def play_previous(self):
        """播放上一首"""
        if not hasattr(self, 'current_playlist_index') or not hasattr(self, 'current_playing_index'):
            QMessageBox.information(self, "提示", "当前没有正在播放的视频")
            return
        
        if self.current_playlist_index >= len(self.playlists):
            return
        
        playlist = self.playlists[self.current_playlist_index]
        items = playlist.get('items', [])
        
        if not items:
            return
        
        # 计算上一首索引
        prev_index = self.current_playing_index - 1
        if prev_index < 0:
            prev_index = len(items) - 1  # 循环到最后一首
        
        self.current_playing_index = prev_index
        self.play_video(items[prev_index])
        
        # 更新列表显示
        self.playlist_combo.setCurrentIndex(self.current_playlist_index)
        self.on_playlist_selected(self.current_playlist_index)
        self.locate_current_playing()
    
    def play_next(self):
        """播放下一首（无感过渡）"""
        if not hasattr(self, 'current_playlist_index') or not hasattr(self, 'current_playing_index'):
            QMessageBox.information(self, "提示", "当前没有正在播放的视频")
            return
        
        if self.current_playlist_index >= len(self.playlists):
            return
        
        playlist = self.playlists[self.current_playlist_index]
        items = playlist.get('items', [])
        
        if not items:
            return
        
        # 计算下一首索引
        next_index = self.current_playing_index + 1
        if next_index >= len(items):
            next_index = 0  # 循环到第一首
        
        self.current_playing_index = next_index
        self.play_video(items[next_index])
        
        # 更新列表显示
        self.playlist_combo.setCurrentIndex(self.current_playlist_index)
        self.on_playlist_selected(self.current_playlist_index)
        self.locate_current_playing()
    
    def play_playlist_item(self, item):
        """播放播放列表中的项目 - 使用存储的数据"""
        # 记录当前播放状态
        combo_index = self.playlist_combo.currentIndex()
        self.current_playlist_index = combo_index
        self.current_playing_index = self.playlist_items_list.row(item)
        
        # 从列表项中获取存储的视频数据
        video_data = item.data(Qt.UserRole)
        if video_data:
            self.play_video(video_data)
        else:
            # 兼容旧数据格式
            playlist_index, playlist = self.get_playlist_by_combo_index(combo_index)
            if playlist is None:
                return
            
            items = playlist.get('items', [])
            
            row = self.playlist_items_list.row(item)
            if row < 0 or row >= len(items):
                return
            
            video_data = items[row]
            self.play_video(video_data)
    
    def play_all_in_playlist(self):
        """播放当前播放列表中的所有视频"""
        combo_index = self.playlist_combo.currentIndex()
        playlist_index, playlist = self.get_playlist_by_combo_index(combo_index)
        
        if playlist is None:
            QMessageBox.warning(self, "提示", "请先选择一个播放列表")
            return
        
        items = playlist.get('items', [])
        
        if not items:
            QMessageBox.information(self, "提示", "播放列表为空")
            return
        
        # 播放第一个视频
        self.current_playlist_index = combo_index
        self.current_playing_index = 0
        self.play_video(items[0])
        QMessageBox.information(self, "播放", f"开始播放播放列表 '{playlist.get('name')}' 中的 {len(items)} 个视频")
    
    def locate_current_playing(self):
        """定位到当前播放的视频 - 高亮显示"""
        # 检查是否有正在播放的视频
        if not hasattr(self, 'current_playlist_index') or not hasattr(self, 'current_playing_index'):
            QMessageBox.information(self, "提示", "当前没有正在播放的视频")
            return
        
        # 切换到对应的播放列表
        if self.current_playlist_index < len(self.playlists):
            self.playlist_combo.setCurrentIndex(self.current_playlist_index)
            
            # 高亮当前播放项
            if self.current_playing_index < self.playlist_items_list.count():
                self.playlist_items_list.setCurrentRow(self.current_playing_index)
                # 滚动到该项
                item = self.playlist_items_list.item(self.current_playing_index)
                self.playlist_items_list.scrollToItem(item, QAbstractItemView.PositionAtCenter)
                
                # 添加播放中标记
                for i in range(self.playlist_items_list.count()):
                    list_item = self.playlist_items_list.item(i)
                    if i == self.current_playing_index:
                        list_item.setText(f"▶ {list_item.text().replace('▶ ', '').replace('⏸ ', '')}")
                    else:
                        list_item.setText(list_item.text().replace('▶ ', '').replace('⏸ ', ''))
    
    def show_sort_menu(self):
        """显示排序菜单"""
        combo_index = self.playlist_combo.currentIndex()
        playlist_index, playlist = self.get_playlist_by_combo_index(combo_index)
        
        if playlist is None:
            return
        
        menu = QMenu(self)
        menu.setFont(self.genshin_font)
        
        # 排序选项
        actions = [
            ("⏱️ 按添加时间 (新→旧)", lambda: self.sort_playlist('time_desc')),
            ("⏱️ 按添加时间 (旧→新)", lambda: self.sort_playlist('time_asc')),
            ("🔤 按标题 (A→Z)", lambda: self.sort_playlist('title_asc')),
            ("🔤 按标题 (Z→A)", lambda: self.sort_playlist('title_desc')),
            ("👤 按UP主", lambda: self.sort_playlist('up')),
        ]
        
        for text, callback in actions:
            action = QAction(text, self)
            action.triggered.connect(callback)
            menu.addAction(action)
        
        # 显示菜单
        sender = self.sender()
        menu.exec_(sender.mapToGlobal(sender.rect().bottomLeft()))
    
    def sort_playlist(self, sort_type):
        """排序播放列表"""
        combo_index = self.playlist_combo.currentIndex()
        playlist_index, playlist = self.get_playlist_by_combo_index(combo_index)
        
        if playlist is None:
            return
        
        items = playlist.get('items', [])
        
        if not items:
            return
        
        # 根据类型排序
        if sort_type == 'time_desc':
            # 新→旧（默认，不需要排序）
            pass
        elif sort_type == 'time_asc':
            # 旧→新
            items.reverse()
        elif sort_type == 'title_asc':
            # A→Z
            items.sort(key=lambda x: x.get('title', '').lower())
        elif sort_type == 'title_desc':
            # Z→A
            items.sort(key=lambda x: x.get('title', '').lower(), reverse=True)
        elif sort_type == 'up':
            # 按UP主
            items.sort(key=lambda x: x.get('up', '').lower())
        
        playlist['items'] = items
        self.save_playlists()
        self.on_playlist_selected(combo_index)
        QMessageBox.information(self, "成功", "播放列表已排序")
    
    def clear_current_playlist(self):
        """清空当前播放列表 - 根据类型区分处理"""
        combo_index = self.playlist_combo.currentIndex()
        playlist_index, playlist = self.get_playlist_by_combo_index(combo_index)
        
        if playlist is None:
            return
        
        playlist_type = playlist.get('type', 'permanent')
        playlist_name = playlist.get('name', '未命名')
        item_count = len(playlist.get('items', []))
        
        if item_count == 0:
            QMessageBox.information(self, "提示", "当前列表为空，无需清空")
            return
        
        if playlist_type == 'temporary':
            # 临时列表 - 直接清空
            reply = QMessageBox.question(
                self, 
                "清空临时列表", 
                f"确定要清空临时播放列表 '{playlist_name}' 吗？\n"
                f"该列表包含 {item_count} 个视频。",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.playlists[playlist_index]['items'] = []
                save_playlists(self.playlists)
                self.on_playlist_selected(combo_index)
                QMessageBox.information(self, "成功", f"临时播放列表 '{playlist_name}' 已清空")
        else:
            # 永久歌单 - 需要更谨慎的确认
            reply = QMessageBox.warning(
                self, 
                "⚠️ 清空歌单", 
                f"您即将清空永久歌单 '{playlist_name}'！\n\n"
                f"该歌单包含 {item_count} 个视频。\n"
                f"此操作将删除歌单中的所有视频，但保留歌单本身。\n\n"
                f"确定要继续吗？",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.playlists[playlist_index]['items'] = []
                save_playlists(self.playlists)
                self.on_playlist_selected(combo_index)
                QMessageBox.information(self, "成功", f"歌单 '{playlist_name}' 已清空")
    
    def apply_theme(self):
        """应用主题"""
        # 获取显示模式
        display_mode = self.settings.get('display_mode', 'light')
        
        # 获取主题颜色
        if self.current_theme == 'custom':
            custom_color = self.settings.get('custom_theme_color', '#3498db')
            primary_color = custom_color
            # 生成次要颜色（稍微暗一点）
            try:
                from PyQt5.QtGui import QColor
                color = QColor(custom_color)
                secondary_color = color.darker(120).name()
            except:
                secondary_color = '#2980b9'
            if display_mode == 'dark':
                background_color = '#121212'
                text_color = '#e0e0e0'
            else:
                background_color = '#f5f5f5'
                text_color = '#2c3e50'
        else:
            theme = self.themes.get(self.current_theme, self.themes['默认主题'])
            primary_color = theme['primary']
            secondary_color = theme['secondary']
            if display_mode == 'dark':
                background_color = '#121212'
                text_color = '#e0e0e0'
            else:
                background_color = theme['background']
                text_color = theme['text']
        
        # 构建样式表 - 优化深色主题的色彩层次和对比度
        if display_mode == 'dark':
            # 深色主题色彩层次：从深到浅的层次感
            border_color = '#404040'  # 更明显的边框色
            widget_bg = '#1a1a1a'     # 最深的背景
            input_bg = '#262626'     # 输入框背景
            tab_bg = '#212121'       # 标签页背景
            tab_text = '#f0f0f0'     # 标签页文字
            group_box_text = '#f0f0f0' # 分组框文字
            scroll_bg = '#1a1a1a'    # 滚动区域背景
            scroll_border = '#404040' # 滚动区域边框
            line_edit_bg = '#2a2a2a'  # 输入框背景
            line_edit_border = '#505050' # 输入框边框
            combo_bg = '#2a2a2a'     # 下拉框背景
            combo_border = '#505050'  # 下拉框边框
            recommend_bg = 'rgba(42, 42, 42, 0.9)' # 推荐区域背景
            
            # 新增层次色彩
            card_bg = '#2d2d2d'      # 卡片背景
            hover_bg = '#3a3a3a'     # 悬停背景
            active_bg = '#4a4a4a'    # 激活状态背景
            separator_color = '#555555' # 分隔线颜色
            
            # 封面相关颜色
            cover_bg = '#2d2d2d'      # 封面背景
            cover_border = '#404040'   # 封面边框
        else:
            border_color = '#e0e0e0'
            widget_bg = '#ffffff'
            input_bg = '#ffffff'
            tab_bg = '#f8f9fa'
            tab_text = '#495057'
            group_box_text = '#2c3e50'
            scroll_bg = 'white'
            scroll_border = '#e0e0e0'
            line_edit_bg = 'white'
            line_edit_border = '#e0e0e0'
            combo_bg = '#f9f9f9'
            combo_border = '#e0e0e0'
            recommend_bg = 'rgba(255, 255, 255, 0.8)'
            
            # 浅色主题的层次色彩
            card_bg = '#f8f9fa'
            hover_bg = '#e9ecef'
            active_bg = '#dee2e6'
            separator_color = '#ced4da'
            
            # 封面相关颜色
            cover_bg = '#f5f5f5'      # 封面背景
            cover_border = '#e0e0e0'   # 封面边框
        
        style_sheet = f"""
            QMainWindow {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {background_color}, stop:1 {secondary_color});
            }}
            QWidget {{
                color: {text_color};
            }}
            QTabWidget::pane {{
                border: 2px solid {primary_color};
                border-radius: 12px;
                background-color: {background_color};
                padding: 8px;
            }}
            QTabBar::tab {{
                background-color: {tab_bg};
                color: {tab_text};
                padding: 12px 24px;
                border: 1px solid {primary_color};
                border-bottom: none;
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
                margin-right: 4px;
                font-weight: 500;
            }}
            QTabBar::tab:selected {{
                background-color: {primary_color};
                color: white;
            }}
            QScrollArea {{
                border: 2px solid {scroll_border};
                border-radius: 10px;
                background: {scroll_bg};
            }}
            QPushButton {{
                padding: 10px 20px;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {primary_color}, stop:1 {secondary_color});
                color: white;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {secondary_color}, stop:1 {primary_color});
            }}
            QLineEdit {{
                padding: 10px;
                border: 2px solid {line_edit_border};
                border-radius: 6px;
                font-size: 14px;
                background: {line_edit_bg};
                color: {text_color};
            }}
            QLineEdit:focus {{
                border: 2px solid {primary_color};
                background: {line_edit_bg};
            }}
            QComboBox {{
                padding: 10px;
                border: 2px solid {combo_border};
                border-radius: 6px;
                min-width: 150px;
                font-size: 13px;
                background: {combo_bg};
                color: {text_color};
            }}
            QComboBox:focus {{
                border: 2px solid {primary_color};
                background: {combo_bg};
            }}
            QComboBox QAbstractItemView {{
                background: {combo_bg};
                color: {text_color};
                border: 1px solid {combo_border};
            }}
            QGroupBox {{
                font-weight: bold;
                font-size: 16px;
                border: 2px solid {border_color};
                border-radius: 10px;
                margin-top: 10px;
                padding-top: 10px;
                color: {group_box_text};
                background: {card_bg};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
            QLabel {{
                color: {text_color};
            }}
            QLabel[is_cover="true"] {{
                border: none;
                border-radius: 4px 4px 0 0;
                background: {cover_bg};
            }}
            QLabel[card_title="true"] {{
                font-size: 14px;
                font-weight: bold;
                color: {text_color};
                padding: 5px;
                background: transparent;
            }}
            QLabel[card_info="true"] {{
                font-size: 12px;
                color: {text_color};
                padding: 0 5px;
                background: transparent;
            }}
            QWidget#recommend_widget {{
                background: {recommend_bg};
                border-radius: 12px;
                padding: 10px;
            }}
            QWidget#edge_widget {{
                background: {recommend_bg};
                border-radius: 12px;
                padding: 10px;
            }}
            
            /* 新增层次样式 */
            QFrame {{
                background: {card_bg};
                border: 1px solid {border_color};
                border-radius: 8px;
            }}
            QFrame:hover {{
                background: {hover_bg};
            }}
            QListWidget {{
                background: {card_bg};
                border: 1px solid {border_color};
                border-radius: 8px;
                outline: none;
            }}
            QListWidget::item {{
                background: transparent;
                padding: 8px 12px;
                border-bottom: 1px solid {separator_color};
            }}
            QListWidget::item:selected {{
                background: {active_bg};
                color: {text_color};
            }}
            QListWidget::item:hover {{
                background: {hover_bg};
            }}
            QTableWidget {{
                background: {card_bg};
                border: 1px solid {border_color};
                border-radius: 8px;
                gridline-color: {separator_color};
            }}
            QTableWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {separator_color};
            }}
            QTableWidget::item:selected {{
                background: {active_bg};
                color: {text_color};
            }}
            QHeaderView::section {{
                background: {tab_bg};
                color: {text_color};
                padding: 8px;
                border: none;
                border-bottom: 2px solid {primary_color};
            }}
        """
        
        # 应用样式表
        self.setStyleSheet(style_sheet)
        
        # 更新所有控件样式
        if hasattr(self, 'open_browser_checkbox'):
            self.open_browser_checkbox.setStyleSheet(f"""
                QCheckBox {
                    font-size: 13px;
                    spacing: 8px;
                    color: {text_color};
                }
                QCheckBox::indicator {
                    width: 18px;
                    height: 18px;
                    border: 2px solid {border_color};
                    border-radius: 4px;
                    background: {card_bg};
                }
                QCheckBox::indicator:checked {
                    background: {primary_color};
                    border-color: {primary_color};
                }
                QCheckBox::indicator:hover {
                    border-color: {primary_color};
                }
            """)
        
        if hasattr(self, 'theme_combo'):
            self.theme_combo.setStyleSheet(f"""
                QComboBox {
                    padding: 8px 12px;
                    border: 2px solid {combo_border};
                    border-radius: 6px;
                    min-width: 140px;
                    font-size: 13px;
                    background: {combo_bg};
                    color: {text_color};
                }
                QComboBox:hover {
                    border-color: {primary_color};
                }
                QComboBox::drop-down {
                    border: none;
                    width: 24px;
                }
                QComboBox::down-arrow {
                    image: none;
                    border-left: 5px solid transparent;
                    border-right: 5px solid transparent;
                    border-top: 6px solid {text_color};
                    margin-right: 8px;
                }
            """)
        
        if hasattr(self, 'mode_combo'):
            self.mode_combo.setStyleSheet(f"""
                QComboBox {
                    padding: 8px 12px;
                    border: 2px solid {combo_border};
                    border-radius: 6px;
                    min-width: 140px;
                    font-size: 13px;
                    background: {combo_bg};
                    color: {text_color};
                }
                QComboBox:hover {
                    border-color: {primary_color};
                }
                QComboBox::drop-down {
                    border: none;
                    width: 24px;
                }
                QComboBox::down-arrow {
                    image: none;
                    border-left: 5px solid transparent;
                    border-right: 5px solid transparent;
                    border-top: 6px solid {text_color};
                    margin-right: 8px;
                }
            """)
        
        if hasattr(self, 'custom_primary_input'):
            self.custom_primary_input.setStyleSheet(f"""
                QLineEdit {
                    padding: 6px 10px;
                    border: 2px solid {line_edit_border};
                    border-radius: 6px;
                    font-size: 13px;
                    background: {line_edit_bg};
                    color: {text_color};
                }
                QLineEdit:focus {
                    border-color: {primary_color};
                }
            """)
        
        # 更新输入框样式
        if hasattr(self, 'bv_input'):
            self.bv_input.setStyleSheet(f"""
                QLineEdit {
                    padding: 10px;
                    border: 2px solid {line_edit_border};
                    border-radius: 6px;
                    font-size: 14px;
                    background: {line_edit_bg};
                    color: {text_color};
                }
                QLineEdit:focus {
                    border: 2px solid {primary_color};
                    background: {line_edit_bg};
                }
            """)
        
        # 更新文本编辑框样式
        if hasattr(self, 'result_area'):
            self.result_area.setStyleSheet(f"""
                QTextEdit {
                    padding: 10px;
                    border: 2px solid {border_color};
                    border-radius: 6px;
                    font-size: 14px;
                    background: {card_bg};
                    color: {text_color};
                }
            """)
        
        # 更新按钮样式
        if hasattr(self, 'download_btn'):
            self.download_btn.setStyleSheet(f"""
                QPushButton {
                    padding: 10px 20px;
                    border: none;
                    border-radius: 6px;
                    font-size: 14px;
                    font-weight: bold;
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 {primary_color}, stop:1 {secondary_color});
                    color: white;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 {secondary_color}, stop:1 {primary_color});
                }
            """)
        
        if hasattr(self, 'add_to_playlist_btn'):
            self.add_to_playlist_btn.setStyleSheet(f"""
                QPushButton {
                    padding: 10px 20px;
                    border: none;
                    border-radius: 6px;
                    font-size: 14px;
                    font-weight: bold;
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #27ae60, stop:1 #229954);
                    color: white;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #229954, stop:1 #27ae60);
                }
            """)
        
        if hasattr(self, 'clear_btn'):
            self.clear_btn.setStyleSheet(f"""
                QPushButton {
                    padding: 10px 20px;
                    border: 2px solid {border_color};
                    border-radius: 6px;
                    font-size: 14px;
                    font-weight: bold;
                    background: {card_bg};
                    color: {text_color};
                }
                QPushButton:hover {
                    background: {hover_bg};
                }
            """)
        
        if hasattr(self, 'copy_btn'):
            self.copy_btn.setStyleSheet(f"""
                QPushButton {
                    padding: 10px 20px;
                    border: 2px solid {border_color};
                    border-radius: 6px;
                    font-size: 14px;
                    font-weight: bold;
                    background: {card_bg};
                    color: {text_color};
                }
                QPushButton:hover {
                    background: {hover_bg};
                }
            """)
        
        # 更新搜索框和排序下拉框的样式
        if hasattr(self, 'search_input'):
            self.search_input.setStyleSheet(f"""
                QLineEdit {{
                    padding: 12px;
                    border: 2px solid {line_edit_border};
                    border-radius: 8px;
                    font-size: 14px;
                    background: {line_edit_bg};
                    color: {text_color};
                }}
                QLineEdit:focus {{
                    border: 2px solid {primary_color};
                    background: {line_edit_bg};
                }}
            """)
        
        if hasattr(self, 'sort_combo'):
            self.sort_combo.setStyleSheet(f"""
                QComboBox {{
                    padding: 12px;
                    border: 2px solid {combo_border};
                    border-radius: 8px;
                    font-size: 14px;
                    background: {combo_bg};
                    color: {text_color};
                }}
                QComboBox:focus {{
                    border: 2px solid {primary_color};
                    background: {combo_bg};
                }}
                QComboBox::drop-down {{
                    border: none;
                }}
                QComboBox::down-arrow {{
                    width: 20px;
                    height: 20px;
                }}
            """)
        
        # 更新搜索按钮样式
        if hasattr(self, 'search_btn'):
            self.search_btn.setStyleSheet(f"""
                QPushButton {{
                    padding: 12px 24px;
                    border: none;
                    border-radius: 8px;
                    font-size: 14px;
                    font-weight: bold;
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 {primary_color}, stop:1 {secondary_color});
                    color: white;
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 {secondary_color}, stop:1 {primary_color});
                }}
            """)
        
        # 更新标题标签样式
        if hasattr(self, 'title_label'):
            self.title_label.setStyleSheet(f"""
                QLabel {{
                    font-size: 24px;
                    font-weight: bold;
                    color: {text_color};
                    margin-bottom: 20px;
                    padding-left: 10px;
                    padding-right: 10px;
                    border-left: 5px solid {primary_color};
                    min-height: 35px;
                }}
            """)
        
        # 更新加载动画样式
        if hasattr(self, 'loading_widget'):
            self.loading_widget.setStyleSheet(f"""
                QWidget {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 {background_color}, stop:1 {secondary_color});
                    border-radius: 10px;
                }}
            """)
        
        if hasattr(self, 'loading_label'):
            self.loading_label.setStyleSheet(f"""
                QLabel {{
                    font-size: 24px;
                    font-weight: bold;
                    color: {text_color};
                    padding: 20px;
                }}
            """)
        
        if hasattr(self, 'loading_hint'):
            self.loading_hint.setStyleSheet(f"""
                QLabel {{
                    font-size: 14px;
                    color: {text_color};
                }}
            """)
        
        # 更新播放列表样式 - 修复主题切换问题
        if hasattr(self, 'playlist_items_list'):
            self.playlist_items_list.setStyleSheet(f"""
                QListWidget {{
                    background: {card_bg};
                    border: 1px solid {border_color};
                    border-radius: 8px;
                    outline: none;
                }}
                QListWidget::item {{
                    background: transparent;
                    padding: 8px 12px;
                    border-bottom: 1px solid {separator_color};
                    color: {text_color};
                    font-weight: bold;
                    min-height: 36px;
                }}
                QListWidget::item:selected {{
                    background: {active_bg};
                    color: {text_color};
                }}
                QListWidget::item:hover {{
                    background: {hover_bg};
                }}
            """)
        
        # 更新播放列表下拉框样式
        if hasattr(self, 'playlist_combo'):
            self.playlist_combo.setStyleSheet(f"""
                QComboBox {{
                    padding: 8px 12px;
                    border: 2px solid {combo_border};
                    border-radius: 6px;
                    font-size: 13px;
                    background: {combo_bg};
                    color: {text_color};
                    font-weight: bold;
                }}
                QComboBox:hover {{
                    border-color: {primary_color};
                }}
                QComboBox::drop-down {{
                    border: none;
                    width: 24px;
                }}
                QComboBox QAbstractItemView {{
                    background: {combo_bg};
                    color: {text_color};
                    border: 1px solid {combo_border};
                    selection-background-color: {active_bg};
                }}
            """)
        
        # 重新创建菜单栏以应用新的主题样式
        if hasattr(self, 'menuBar'):
            # 清除现有的菜单栏
            while self.menuBar().actions():
                action = self.menuBar().actions()[0]
                self.menuBar().removeAction(action)
            # 重新创建菜单栏
            self.create_menu_bar()
        
        # 调整边距和留白
            if hasattr(self, 'centralWidget') and self.centralWidget():
                main_layout = self.centralWidget().layout()
                if main_layout:
                    # 减少主布局的边距
                    main_layout.setContentsMargins(10, 10, 10, 10)
                    main_layout.setSpacing(15)
        
        # 更新现有推荐卡片的样式
        if hasattr(self, 'recommend_layout') and self.recommend_layout:
            for i in range(self.recommend_layout.count()):
                item = self.recommend_layout.itemAt(i)
                if item and item.widget():
                    card = item.widget()
                    # 根据显示模式更新卡片样式
                    if display_mode == 'dark':
                        card.setStyleSheet("""
                            QWidget {
                                background: #2d2d2d;
                                border: 1px solid #404040;
                                border-radius: 4px;
                                padding: 0;
                            }
                            QWidget:hover {
                                border: 1px solid #3498db;
                                background: #3a3a3a;
                            }
                        """)
                    else:
                        card.setStyleSheet("""
                            QWidget {
                                background: white;
                                border: 1px solid #e0e0e0;
                                border-radius: 4px;
                                padding: 0;
                            }
                            QWidget:hover {
                                border: 1px solid #3498db;
                                background: #f8f9fa;
                            }
                        """)
        
        # 更新播放列表侧边栏样式
        if hasattr(self, 'playlist_sidebar'):
            # 重新设置侧边栏样式
            if display_mode == 'dark':
                self.playlist_sidebar.setStyleSheet("""
                    QWidget#playlist_sidebar {
                        background: rgba(42, 42, 42, 0.95);
                        border-left: 2px solid #404040;
                        border-radius: 0;
                    }
                """)
            else:
                self.playlist_sidebar.setStyleSheet("""
                    QWidget#playlist_sidebar {
                        background: rgba(255, 255, 255, 0.95);
                        border-left: 2px solid #e0e0e0;
                        border-radius: 0;
                    }
                """)
    
    def setup_ui(self):
        """设置界面"""
        # 主部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # 创建登录遮罩层（初始显示，登录后隐藏）
        self.login_overlay = QWidget(central_widget)
        self.login_overlay.setGeometry(self.rect())
        self.login_overlay.setStyleSheet("""
            QWidget {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #1a1a2e,
                    stop: 1 #16213e
                );
            }
        """)
        overlay_layout = QVBoxLayout(self.login_overlay)
        overlay_layout.setAlignment(Qt.AlignCenter)
        overlay_layout.setSpacing(30)
        
        # 遮罩层标题
        overlay_title = QLabel("🔒 智能音乐推荐与分享系统")
        overlay_title.setStyleSheet("""
            font-size: 28px; 
            font-weight: bold; 
            color: #ffffff;
            padding: 20px;
        """)
        overlay_title.setAlignment(Qt.AlignCenter)
        overlay_layout.addWidget(overlay_title)
        
        # 提示文字
        overlay_hint = QLabel("请先登录以访问系统内容")
        overlay_hint.setStyleSheet("""
            font-size: 16px; 
            color: #a0a0a0;
            padding: 10px;
        """)
        overlay_hint.setAlignment(Qt.AlignCenter)
        overlay_layout.addWidget(overlay_hint)
        
        # 登录按钮
        login_overlay_btn = QPushButton("🔐 点击登录")
        login_overlay_btn.setStyleSheet("""
            QPushButton {
                padding: 15px 40px;
                font-size: 16px;
                font-weight: bold;
                color: white;
                background: #3498db;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover {
                background: #2980b9;
            }
        """)
        login_overlay_btn.clicked.connect(self.show_login_dialog)
        overlay_layout.addWidget(login_overlay_btn, alignment=Qt.AlignCenter)
        
        # 游客入口
        guest_btn = QPushButton("以游客身份浏览")
        guest_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 30px;
                font-size: 14px;
                color: #a0a0a0;
                background: transparent;
                border: 1px solid #555555;
                border-radius: 6px;
            }
            QPushButton:hover {
                color: #ffffff;
                border-color: #888888;
            }
        """)
        guest_btn.clicked.connect(self.login_as_guest)
        overlay_layout.addWidget(guest_btn, alignment=Qt.AlignCenter)
        
        self.login_overlay.raise_()
        self.login_overlay.show()
        
        # 初始化加载动画组件（初始隐藏）
        self.loading_widget = QWidget()
        loading_layout = QVBoxLayout(self.loading_widget)
        loading_layout.setAlignment(Qt.AlignCenter)
        
        # 加载动画标签
        self.loading_label = QLabel("🎵 正在加载推荐内容...")
        self.loading_label.setFont(self.genshin_font)
        self.loading_label.setAlignment(Qt.AlignCenter)
        loading_layout.addWidget(self.loading_label)
        
        # 加载提示
        self.loading_hint = QLabel("首次加载可能需要一些时间，请耐心等待...")
        self.loading_hint.setFont(self.genshin_font)
        self.loading_hint.setAlignment(Qt.AlignCenter)
        loading_layout.addWidget(self.loading_hint)
        
        main_layout.addWidget(self.loading_widget)
        self.loading_widget.show()
        if hasattr(self, 'recommend_widget'):
            self.recommend_widget.hide()
        
        # 搜索栏
        search_layout = QHBoxLayout()
        search_layout.setSpacing(10)
        
        # 搜索输入框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索音乐...")
        self.search_input.setFont(self.genshin_font)
        search_layout.addWidget(self.search_input, 3)
        
        # 排序选择
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(['综合排序', '最新发布', '最多播放', '最多弹幕'])
        self.sort_combo.setCurrentText(self.settings.get('default_sort', '综合排序'))
        self.sort_combo.setFont(self.genshin_font)
        search_layout.addWidget(self.sort_combo, 1)
        
        # 搜索按钮
        self.search_btn = QPushButton("搜索")
        self.search_btn.setFont(self.genshin_font)
        self.search_btn.clicked.connect(self.search_music)
        search_layout.addWidget(self.search_btn)
        
        main_layout.addLayout(search_layout)
        
        # 内容区域 - 使用QSplitter实现可拉伸布局
        from PyQt5.QtWidgets import QSplitter
        
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setHandleWidth(8)  # 拖拽手柄宽度
        self.main_splitter.setStyleSheet("""
            QSplitter::handle {
                background: transparent;
            }
            QSplitter::handle:hover {
                background: rgba(52, 152, 219, 0.3);
            }
        """)
        
        # 推荐列表 - 占据主要宽度
        self.recommend_widget = QWidget()
        self.recommend_widget.setObjectName("recommend_widget")
        recommend_layout = QVBoxLayout(self.recommend_widget)
        recommend_layout.setSpacing(5)
        recommend_layout.setContentsMargins(5, 5, 5, 5)
        
        # 今日推荐标题
        self.title_label = QLabel("今日推荐")
        self.title_label.setFont(self.genshin_font)
        self.title_label.setWordWrap(True)
        recommend_layout.addWidget(self.title_label)
        
        # 推荐内容区域 - 使用流式布局显示更大的卡片
        self.recommend_scroll = QScrollArea()
        self.recommend_scroll.setWidgetResizable(True)
        self.recommend_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                border-radius: 10px;
                background: transparent;
            }
        """)
        
        self.recommend_content = QWidget()
        # 使用流式布局，每行显示更多卡片
        self.recommend_layout = QGridLayout(self.recommend_content)
        self.recommend_layout.setSpacing(5)
        self.recommend_layout.setContentsMargins(0, 0, 0, 0)
        
        self.recommend_scroll.setWidget(self.recommend_content)
        recommend_layout.addWidget(self.recommend_scroll, 1)
        
        self.main_splitter.addWidget(self.recommend_widget)
        
        # 播放列表侧边栏 - 贴边可伸缩
        self.setup_playlist_sidebar_for_splitter()
        
        # 设置初始比例（推荐区:侧边栏 = 4:1）
        self.main_splitter.setSizes([800, 250])
        
        # 添加分割器到主布局
        main_layout.addWidget(self.main_splitter)
        
        # 快速操作按钮 - 直接添加到底部
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        
        # 刷新推荐按钮
        refresh_btn = QPushButton("🔄 刷新推荐")
        refresh_btn.setFont(self.genshin_font)
        refresh_btn.setStyleSheet("""
            QPushButton {
                padding: 12px 24px;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
                background: #3498db;
                color: white;
            }
            QPushButton:hover {
                background: #2980b9;
            }
        """)
        refresh_btn.clicked.connect(self.refresh_recommendations)
        button_layout.addWidget(refresh_btn)
        
        # 预加载状态标签
        self.preload_status_label = QLabel("")
        self.preload_status_label.setFont(self.genshin_font)
        self.preload_status_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #27ae60;
                padding: 5px 10px;
                background: transparent;
            }
        """)
        button_layout.addWidget(self.preload_status_label)
        
        # 启动预加载状态更新定时器
        self.preload_timer = QTimer(self)
        self.preload_timer.timeout.connect(self.update_preload_status)
        self.preload_timer.start(2000)  # 每2秒更新一次状态
        
        button_layout.addStretch()
        
        # 设置按钮
        settings_btn = QPushButton("⚙️ 设置")
        settings_btn.setFont(self.genshin_font)
        settings_btn.setStyleSheet("""
            QPushButton {
                padding: 12px 24px;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                font-size: 14px;
                background: #f9f9f9;
                color: #2c3e50;
            }
            QPushButton:hover {
                background: #e9ecef;
            }
        """)
        settings_btn.clicked.connect(self.show_settings)
        button_layout.addWidget(settings_btn)
        
        main_layout.addLayout(button_layout)
    
    def show_loading_screen(self):
        """显示加载动画"""
        if hasattr(self, 'loading_widget'):
            self.loading_widget.show()
            if hasattr(self, 'recommend_widget'):
                self.recommend_widget.hide()
    
    def hide_loading_screen(self):
        """隐藏加载动画"""
        if hasattr(self, 'loading_widget'):
            self.loading_widget.hide()
        if hasattr(self, 'recommend_widget'):
            self.recommend_widget.show()
    
    def _calculate_recommend_count(self):
        """根据窗口大小计算需要的推荐数量 - 增加滚动深度"""
        # 获取滚动区域尺寸
        viewport_width = self.recommend_scroll.viewport().width()
        viewport_height = self.recommend_scroll.viewport().height()
        
        # 使用与实际显示相同的卡片宽度计算方法
        card_width = self._calculate_card_width()
        card_height = int(card_width * 9 / 16) + 100  # 封面高度 + 文字区域高度
        
        # 计算可容纳的列数和行数（使用2px间距，与布局一致）
        cols = max(1, (viewport_width + 2) // (card_width + 2))
        rows = max(1, viewport_height // (card_height + 2))
        
        # 计算需要的数量（填满当前视图 + 额外4行用于滚动，体现滚动条作用）
        needed_count = cols * (rows + 4)
        
        # 确保至少填满5行，让滚动条有意义
        needed_count = max(needed_count, cols * 5)
        
        print(f"窗口尺寸: {viewport_width}x{viewport_height}, 卡片: {card_width}x{card_height}, 行列: {cols}x{rows}, 需要: {needed_count}个")
        
        # 增加最小数量到30，最大到200，确保有足够的滚动深度
        return max(30, min(needed_count, 200))
    
    def load_recommendations(self, force_refresh=False, use_intelligent=True):
        """加载推荐内容"""
        try:
            # 显示加载动画
            self.show_loading_screen()
            
            # 计算需要的推荐数量
            recommend_count = self._calculate_recommend_count()
            print(f"计算需要 {recommend_count} 个推荐来填满区域")
            
            # 获取排除列表的BV号
            excluded_bvids = [item.get('bvid') for item in self.excluded if item.get('bvid')]
            if excluded_bvids:
                print(f"排除列表中有 {len(excluded_bvids)} 个视频")
            
            # 获取推荐（支持智能推荐和强制刷新）
            if use_intelligent and self.advanced_engine:
                # 使用高级推荐
                user_id = self._get_current_user_id()
                recommendations = self.advanced_engine.get_advanced_recommendations(
                    user_id, limit=recommend_count, excluded_bvids=excluded_bvids
                )
                print(f"高级推荐获取到 {len(recommendations)} 条结果")
            elif use_intelligent and self.intelligent_engine:
                # 使用智能推荐
                user_id = self._get_current_user_id()
                recommendations = self.intelligent_engine.get_intelligent_recommendations(
                    user_id, limit=recommend_count, excluded_bvids=excluded_bvids
                )
                print(f"智能推荐获取到 {len(recommendations)} 条结果")
            else:
                # 使用传统推荐
                recommendations = self.recommend_service.get_recommendations(
                    force_refresh=force_refresh, limit=recommend_count, excluded_bvids=excluded_bvids
                )
            
            # 如果本地数据库为空且不是强制刷新，尝试从API获取
            if not recommendations and not force_refresh:
                print("本地数据库为空，正在从API获取初始数据...")
                recommendations = self.recommend_service.get_recommendations(force_refresh=True, limit=recommend_count, excluded_bvids=excluded_bvids)
            
            # 隐藏加载动画
            self.hide_loading_screen()
            
            # 显示推荐
            if recommendations:
                self.display_recommendations(recommendations)
                # 标记这些视频为已浏览
                for rec in recommendations:
                    self.recommend_service.mark_as_viewed(rec.get('bvid'))
                
                # 记录用户浏览行为（用于智能学习）
                if use_intelligent and self.intelligent_engine:
                    self._record_user_interactions(recommendations)
            else:
                # 显示空状态提示
                self.display_error_message("暂无推荐数据，请点击刷新按钮获取")
            
            # 检查是否需要后台抓取补充数据
            self.check_and_start_background_fetch()
        except Exception as e:
            logger.error(f"加载推荐失败: {e}")
            # 隐藏加载动画
            self.hide_loading_screen()
            # 显示友好的错误提示，而不是弹出警告框
            self.display_error_message(f"加载推荐失败，请检查网络连接后重试。\n错误信息: {str(e)}")
    
    def check_and_start_background_fetch(self):
        """检查并启动后台数据抓取（如果需要）"""
        try:
            # 先检查并修复播放量为空的视频
            empty_count, removed_count = self.recommend_service.check_and_fix_empty_playcount(auto_fix=True)
            if empty_count > 0:
                print(f"检测到 {empty_count} 个播放量为空的视频，已移除 {removed_count} 个")
                if hasattr(self, 'statusBar'):
                    self.statusBar().showMessage(f"清理异常数据: 移除 {removed_count} 个播放量为空的视频", 3000)

            # 检查数据库状态
            stats = self.recommend_service.get_db_stats()
            if stats['needs_fetch']:
                print(f"未浏览视频数量({stats['unviewed']})低于阈值({stats['min_threshold']})，启动后台补充...")
                self.recommend_service.check_and_fetch_if_needed(background=True)
                if hasattr(self, 'statusBar'):
                    self.statusBar().showMessage(f"后台补充数据中... (未浏览: {stats['unviewed']}/{stats['min_threshold']})", 3000)
            else:
                print(f"数据库状态良好 (未浏览: {stats['unviewed']}, 总计: {stats['total']})")
        except Exception as e:
            print(f"检查数据库状态失败: {e}")
    
    def start_preload(self):
        """启动后台预加载"""
        if self.is_preloading:
            return
        
        self.is_preloading = True
        self.preload_thread = threading.Thread(target=self._preload_worker, daemon=True)
        self.preload_thread.start()
    
    def _preload_worker(self):
        """预加载工作线程 - 从本地数据库预加载，不从API抓取"""
        try:
            # 计算需要的推荐数量
            recommend_count = self._calculate_recommend_count()
            # 获取排除列表的BV号
            excluded_bvids = [item.get('bvid') for item in self.excluded if item.get('bvid')]
            # 从本地数据库获取更多数据（不强制刷新）
            recommendations = self.recommend_service.get_recommendations(force_refresh=False, limit=recommend_count, excluded_bvids=excluded_bvids)
            if recommendations:
                self.preloaded_recommendations = recommendations
                print(f"预加载完成: {len(recommendations)} 条数据（来自本地数据库）")
        except Exception as e:
            print(f"预加载失败: {e}")
        finally:
            self.is_preloading = False
    
    def _get_current_user_id(self) -> str:
        """获取当前用户ID（简化实现）"""
        # 在实际应用中，这里应该从用户系统获取真实用户ID
        # 这里使用设备标识或默认用户ID
        return "default_user"
    
    def _record_user_interactions(self, recommendations: List[Dict]):
        """记录用户交互行为（用于智能学习）"""
        try:
            from services.recommend_engine.intelligent import record_user_interaction
            
            user_id = self._get_current_user_id()
            
            # 记录浏览行为
            for rec in recommendations:
                record_user_interaction(user_id, rec, 'click')
            
            print(f"记录用户 {user_id} 的浏览行为，共 {len(recommendations)} 条")
            
        except Exception as e:
            print(f"记录用户交互行为失败: {e}")
    
    def record_user_feedback(self, music_data: Dict, feedback_type: str):
        """记录用户反馈（点赞、收藏、分享等）"""
        try:
            from services.recommend_engine.intelligent import record_user_interaction
            
            user_id = self._get_current_user_id()
            record_user_interaction(user_id, music_data, feedback_type)
            
            print(f"记录用户 {user_id} 的{feedback_type}反馈")
            
        except Exception as e:
            print(f"记录用户反馈失败: {e}")
    
    def _check_and_reset_viewed_on_startup(self):
        """启动时检查并重置浏览记录"""
        try:
            from utils.data_manager import clear_viewed_history, load_db_config
            
            # 获取配置
            db_config = load_db_config()
            
            # 检查设置中是否启用启动时重置
            reset_on_startup = self.settings.get('reset_viewed_on_startup', True)
            
            if reset_on_startup:
                print("启动时重置浏览记录...")
                clear_viewed_history()
                
                # 记录重置时间
                from datetime import datetime
                self.settings['last_viewed_reset'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                save_settings(self.settings)
                
        except Exception as e:
            print(f"启动时重置浏览记录失败: {e}")
    
    def use_preloaded_or_refresh(self):
        """使用预加载数据或刷新"""
        if self.preloaded_recommendations:
            # 使用预加载的数据
            recommendations = self.preloaded_recommendations
            self.preloaded_recommendations = []  # 清空预加载缓存
            self.display_recommendations(recommendations)
            # 标记这些视频为已浏览
            for rec in recommendations:
                self.recommend_service.mark_as_viewed(rec.get('bvid'))
            # 立即启动新的预加载
            self.start_preload()
            return True
        return False
    
    def update_preload_status(self):
        """更新预加载状态显示"""
        if not hasattr(self, 'preload_status_label'):
            return
        
        if self.preloaded_recommendations:
            self.preload_status_label.setText(f"✓ 已缓存 {len(self.preloaded_recommendations)} 条")
            self.preload_status_label.setStyleSheet("""
                QLabel {
                    font-size: 12px;
                    color: #27ae60;
                    padding: 5px 10px;
                    background: rgba(39, 174, 96, 0.1);
                    border-radius: 4px;
                }
            """)
        elif self.is_preloading:
            self.preload_status_label.setText("⟳ 预加载中...")
            self.preload_status_label.setStyleSheet("""
                QLabel {
                    font-size: 12px;
                    color: #f39c12;
                    padding: 5px 10px;
                    background: rgba(243, 156, 18, 0.1);
                    border-radius: 4px;
                }
            """)
        else:
            self.preload_status_label.setText("")
    
    def display_error_message(self, message):
        """在推荐区域显示错误信息"""
        # 清空现有的推荐内容
        for i in reversed(range(self.recommend_layout.count())):
            item = self.recommend_layout.itemAt(i)
            if item.widget():
                item.widget().deleteLater()
        
        # 显示错误信息
        error_label = QLabel(message)
        error_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                color: #e74c3c;
                padding: 20px;
                background: white;
                border-radius: 8px;
            }
        """)
        error_label.setFont(self.genshin_font)
        error_label.setWordWrap(True)
        error_label.setAlignment(Qt.AlignCenter)
        self.recommend_layout.addWidget(error_label, 0, 0)
    
    def display_recommendations(self, recommendations):
        """显示推荐内容 - 优化版，使用批量显示和虚拟滚动"""
        # 停止之前的封面加载
        self._stop_cover_loading()

        # 清空现有的推荐内容
        self._clear_recommend_layout()

        # 保存当前推荐数据
        self._current_recommendations = recommendations

        # 先获取卡片宽度
        self._current_card_width = self._calculate_card_width()

        # 根据用户设置或自动逻辑确定列数
        if hasattr(self, 'column_count'):
            if self.column_count == '1列':
                self._current_cols = 1
            elif self.column_count == '2列':
                self._current_cols = 2
            elif self.column_count == '3列':
                self._current_cols = 3
            elif self.column_count == '4列':
                self._current_cols = 4
            elif self.column_count == '5列':
                self._current_cols = 5
            else:
                # 自动模式：根据侧边栏状态决定列数
                sidebar_visible = getattr(self, 'playlist_sidebar_visible', True)
                window_width = max(800, self.recommend_scroll.viewport().width())
                
                if sidebar_visible:
                    # 侧边栏显示时，4-5列
                    self._current_cols = max(4, min(5, window_width // (self._current_card_width + 8)))
                else:
                    # 侧边栏隐藏时，5-6列
                    self._current_cols = max(5, min(6, window_width // (self._current_card_width + 8)))
                
                # 确保列数合理
                self._current_cols = max(2, self._current_cols)
        else:
            # 默认自动模式
            sidebar_visible = getattr(self, 'playlist_sidebar_visible', True)
            window_width = max(800, self.recommend_scroll.viewport().width())
            
            if sidebar_visible:
                self._current_cols = max(4, min(5, window_width // (self._current_card_width + 8)))
            else:
                self._current_cols = max(5, min(6, window_width // (self._current_card_width + 8)))
            
            self._current_cols = max(2, self._current_cols)

        # 使用队列分批显示，避免UI卡顿
        self._display_queue = list(enumerate(recommendations))
        self._process_display_queue()

        # 批量加载封面（后台）
        self._batch_load_covers(recommendations)
    
    def _calculate_card_width(self):
        """计算卡片宽度 - 根据侧边栏状态或用户设置调整列数"""
        # 确保窗口宽度有效，避免初始化时太小
        window_width = max(800, self.recommend_scroll.viewport().width())
        
        if hasattr(self, 'cover_size'):
            if self.cover_size == '小 (120px)':
                return 240  # 放大2倍
            elif self.cover_size == '中 (160px)':
                return 320  # 放大2倍
            elif self.cover_size == '大 (200px)':
                return 400  # 放大2倍
            elif self.cover_size == '超大 (240px)':
                return 480  # 放大2倍
        
        # 检查用户是否设置了固定列数
        if hasattr(self, 'column_count'):
            if self.column_count == '1列':
                target_cols = 1
            elif self.column_count == '2列':
                target_cols = 2
            elif self.column_count == '3列':
                target_cols = 3
            elif self.column_count == '4列':
                target_cols = 4
            elif self.column_count == '5列':
                target_cols = 5
            else:
                # 自动适应 - 根据侧边栏状态决定列数
                sidebar_visible = getattr(self, 'playlist_sidebar_visible', True)
                
                if sidebar_visible:
                    # 侧边栏显示时，4-5列
                    target_cols = 4
                else:
                    # 侧边栏隐藏时，5-6列
                    target_cols = 5
                
                # 根据窗口宽度微调
                if window_width > 2000:
                    target_cols = max(target_cols, 6)
                elif window_width > 1600:
                    target_cols = max(target_cols, 5)
                elif window_width > 1200:
                    target_cols = max(target_cols, 4)
                elif window_width > 900:
                    target_cols = max(target_cols, 3)
                else:
                    target_cols = 2
        else:
            # 没有设置 column_count 属性时使用默认自动适应
            sidebar_visible = getattr(self, 'playlist_sidebar_visible', True)
            if sidebar_visible:
                target_cols = 4
            else:
                target_cols = 5
        
        calculated_width = (window_width - (target_cols - 1) * 8) // target_cols
        
        # 设置合理的卡片宽度范围（增大范围避免空隙）
        min_width = 200  # 减小最小宽度
        max_width = 400  # 保持最大宽度
        
        return max(min_width, min(calculated_width, max_width))
    
    def _clear_recommend_layout(self):
        """清空推荐布局 - 优化版"""
        # 批量删除，减少布局更新次数
        widgets_to_delete = []
        for i in range(self.recommend_layout.count()):
            item = self.recommend_layout.itemAt(i)
            if item and item.widget():
                widgets_to_delete.append(item.widget())
        
        # 隐藏所有widget后再删除
        for widget in widgets_to_delete:
            widget.hide()
            widget.deleteLater()
    
    def _process_display_queue(self):
        """处理显示队列 - 分批显示卡片"""
        if not self._display_queue:
            # 添加占位符填充最后一行
            self._add_row_spacers()
            return
        
        # 每批处理10个
        batch = self._display_queue[:self._batch_display_size]
        self._display_queue = self._display_queue[self._batch_display_size:]
        
        for idx, item in batch:
            card = self.create_recommend_card(item, self._current_card_width)
            row = idx // self._current_cols
            col = idx % self._current_cols
            self.recommend_layout.addWidget(card, row, col)
        
        # 如果还有数据，延迟处理下一批
        if self._display_queue:
            self._display_update_timer.start(10)  # 10ms后处理下一批
    
    def _add_row_spacers(self):
        """添加行占位符"""
        if not hasattr(self, '_current_recommendations'):
            return
        
        remaining = self._current_cols - (len(self._current_recommendations) % self._current_cols)
        if remaining < self._current_cols:
            start_idx = len(self._current_recommendations)
            for i in range(remaining):
                spacer = QWidget()
                spacer.setMinimumWidth(self._current_card_width)
                row = (start_idx + i) // self._current_cols
                col = (start_idx + i) % self._current_cols
                self.recommend_layout.addWidget(spacer, row, col)
    
    def _batch_load_covers(self, recommendations):
        """批量加载封面 - 后台线程池"""
        if self.no_image_mode:
            return
        
        # 收集需要加载的封面URL
        urls_to_load = []
        for item in recommendations:
            cover_url = item.get('cover')
            if cover_url:
                cache = CoverCache()
                if not cache.get(cover_url):  # 只加载未缓存的
                    urls_to_load.append(cover_url)
        
        if not urls_to_load:
            return
        
        # 使用线程池批量加载
        def load_covers_worker():
            cache = CoverCache()
            results = cache.batch_load(urls_to_load[:20], max_workers=6)  # 限制最多加载20个
            
            # 更新UI（在主线程）
            for url, pixmap in results.items():
                if pixmap:
                    # 找到对应的label并更新
                    self._update_cover_by_url(url, pixmap)
        
        # 在后台线程执行
        threading.Thread(target=load_covers_worker, daemon=True).start()
    
    def _update_cover_by_url(self, url, pixmap):
        """根据URL更新封面 - 使用信号机制跨线程更新"""
        # 发射信号，让主线程更新UI
        self._cover_update_signal.update_cover.emit(url, pixmap)
    
    def _on_cover_update(self, url, pixmap):
        """封面更新槽方法 - 在主线程执行"""
        try:
            # 遍历所有卡片，找到匹配的封面
            for i in range(self.recommend_layout.count()):
                item = self.recommend_layout.itemAt(i)
                if item and item.widget():
                    card = item.widget()
                    # 检查卡片是否有布局
                    card_layout = card.layout()
                    if not card_layout:
                        continue
                    # 查找卡片中的封面label
                    for j in range(card_layout.count()):
                        child = card_layout.itemAt(j)
                        if child and child.widget():
                            widget = child.widget()
                            if isinstance(widget, QLabel) and widget.property('is_cover'):
                                if widget.property('cover_url') == url:
                                    widget.setPixmap(pixmap)
                                    return
        except Exception as e:
            logger.error(f"更新封面失败: {e}")
    
    def _stop_cover_loading(self):
        """停止所有封面加载线程"""
        # 停止现有的线程
        for thread in self.cover_threads:
            if thread.isRunning():
                thread.stop()
        self.cover_threads.clear()
        self.load_semaphore = 0
    
    def create_recommend_card(self, item, card_width):
        """创建推荐卡片"""
        card = QWidget()
        card.setFixedWidth(card_width)
        
        # 获取显示模式
        display_mode = self.settings.get('display_mode', 'light')
        
        # 根据显示模式设置卡片样式
        if display_mode == 'dark':
            card.setStyleSheet("""
                QWidget {
                    background: #2d2d2d;
                    border: 1px solid #404040;
                    border-radius: 4px;
                    padding: 0;
                }
                QWidget:hover {
                    border: 1px solid #3498db;
                    background: #3a3a3a;
                }
            """)
        else:
            card.setStyleSheet("""
                QWidget {
                    background: white;
                    border: 1px solid #e0e0e0;
                    border-radius: 4px;
                    padding: 0;
                }
                QWidget:hover {
                    border: 1px solid #3498db;
                    background: #f8f9fa;
                }
            """)
        
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(2)
        card_layout.setContentsMargins(0, 0, 0, 0)
        
        # 封面 - 自适应宽度
        cover_label = QLabel()
        cover_height = int(card_width * 9 / 16)  # 16:9 比例，充满整个卡片宽度
        cover_label.setFixedSize(card_width, cover_height)
        cover_label.setProperty('is_cover', 'true')
        cover_label.setScaledContents(True)  # 确保图片正确缩放
        
        # 标记为封面label，用于后续更新
        cover_label.setProperty('cover_url', item.get('cover', ''))
        
        # 加载封面 - 优化版：只从缓存加载，后台批量加载未缓存的
        if not self.no_image_mode and item.get('cover'):
            cache = CoverCache()
            cached_pixmap = cache.get(item['cover'])
            if cached_pixmap:
                cover_label.setPixmap(cached_pixmap)
        
        card_layout.addWidget(cover_label)
        
        # 标题
        title_text = item.get('title', '未知标题')
        title_label = QLabel()
        title_label.setProperty('card_title', 'true')
        title_label.setFont(self.genshin_font)
        title_label.setWordWrap(True)
        title_label.setFixedHeight(40)  # 增加高度以显示完整标题
        title_label.setTextFormat(Qt.PlainText)
        title_label.setProperty('full_title', title_text)
        
        # 使用 QFontMetrics 截断标题
        font_metrics = title_label.fontMetrics()
        available_width = card_width - 30  # 卡片宽度减去 padding
        elided_title = font_metrics.elidedText(title_text, Qt.ElideRight, available_width)
        title_label.setText(elided_title)
        
        card_layout.addWidget(title_label)
        
        # 发布时间和UP主信息
        info_layout = QVBoxLayout()
        info_layout.setSpacing(5)
        
        # UP主
        up_text = item.get('up主', item.get('up', '未知UP主'))
        up_label = QLabel(f"UP主: {up_text}")
        up_label.setProperty('card_info', 'true')
        up_label.setFont(self.genshin_font)
        up_label.setWordWrap(True)
        up_label.setFixedHeight(20)
        info_layout.addWidget(up_label)
        
        # 发布时间
        pubdate_text = self.format_pubdate(item.get('pubdate', item.get('pub_time', '未知')))
        pubdate_label = QLabel(f"发布: {pubdate_text}")
        
        # 根据显示模式设置标签样式
        if display_mode == 'dark':
            pubdate_label.setStyleSheet("""
                QLabel {
                    font-size: 12px;
                    color: #999;
                    padding: 0 5px;
                    background: transparent;
                }
            """)
        else:
            pubdate_label.setStyleSheet("""
                QLabel {
                    font-size: 12px;
                    color: #999;
                    padding: 0 5px;
                    background: transparent;
                }
            """)
        pubdate_label.setFont(self.genshin_font)
        pubdate_label.setWordWrap(True)
        pubdate_label.setFixedHeight(20)
        info_layout.addWidget(pubdate_label)
        
        card_layout.addLayout(info_layout)
        
        # 存储完整信息，用于悬停显示
        card.setProperty('video_data', item)
        
        # 安装事件过滤器
        card.installEventFilter(self)
        
        return card
    
    def eventFilter(self, obj, event):
        """事件过滤器，用于处理点击和右键菜单"""
        if event.type() == event.MouseButtonPress:
            # 查找包含 video_data 的父控件（可能是卡片本身或其子控件）
            target = obj
            video_data = None
            
            # 向上查找直到找到包含 video_data 的控件
            while target and not video_data:
                video_data = target.property('video_data')
                if not video_data:
                    target = target.parent()
                    # 防止无限循环，限制查找层级
                    if target and target == self:
                        break
            
            if not video_data:
                return super().eventFilter(obj, event)
            
            if event.button() == Qt.LeftButton:
                # 左键直接播放视频
                self.play_video(video_data)
                return True  # 已处理事件
            elif event.button() == Qt.RightButton:
                # 右键显示菜单
                self.show_context_menu(event.globalPos(), video_data, target)
                return True  # 已处理事件
        return super().eventFilter(obj, event)
    
    def show_context_menu(self, pos, video_data, card_widget):
        """显示右键菜单"""
        from PyQt5.QtWidgets import QMenu, QAction
        
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 5px;
            }
            QMenu::item {
                padding: 8px 20px;
                border-radius: 4px;
                color: #2c3e50;
            }
            QMenu::item:selected {
                background: #3498db;
                color: white;
            }
        """)
        
        # 播放视频
        play_action = QAction("▶ 播放视频", self)
        play_action.setFont(self.genshin_font)
        play_action.triggered.connect(lambda: self.play_video(video_data))
        menu.addAction(play_action)
        
        # 在浏览器中打开
        open_action = QAction("在浏览器中打开", self)
        open_action.setFont(self.genshin_font)
        open_action.triggered.connect(lambda: self.open_video(video_data.get('bvid')))
        menu.addAction(open_action)
        
        menu.addSeparator()
        
        # 收藏
        favorite_action = QAction("添加到收藏", self)
        favorite_action.setFont(self.genshin_font)
        favorite_action.triggered.connect(lambda: self.add_to_favorites(video_data))
        menu.addAction(favorite_action)
        
        # 排除
        exclude_action = QAction("添加到排除列表", self)
        exclude_action.setFont(self.genshin_font)
        exclude_action.triggered.connect(lambda: self.add_to_excluded(video_data, card_widget))
        menu.addAction(exclude_action)
        
        menu.addSeparator()
        
        # 添加到播放列表
        playlist_action = QAction("添加到播放列表", self)
        playlist_action.setFont(self.genshin_font)
        playlist_action.triggered.connect(lambda: self.add_to_playlist_dialog(video_data))
        menu.addAction(playlist_action)
        
        # 分享
        share_action = QAction("分享", self)
        share_action.setFont(self.genshin_font)
        share_action.triggered.connect(lambda: self.share_video(video_data))
        menu.addAction(share_action)
        
        menu.addSeparator()
        
        # 复制链接
        copy_action = QAction("复制链接", self)
        copy_action.setFont(self.genshin_font)
        copy_action.triggered.connect(lambda: self.copy_video_link(video_data))
        menu.addAction(copy_action)
        
        menu.exec_(pos)
    
    def add_to_favorites(self, video):
        """添加到收藏"""
        bvid = video.get('bvid')
        if bvid:
            if not any(item.get('bvid') == bvid for item in self.favorites):
                self.favorites.append({
                    'bvid': bvid,
                    'title': video.get('title', '未知标题'),
                    'cover': video.get('cover'),
                    'up': video.get('up', '未知UP主'),
                    'pubdate': video.get('pubdate', '未知')
                })
                self.save_favorites_and_excluded()
                QMessageBox.information(self, "成功", "已添加到收藏列表")
            else:
                QMessageBox.information(self, "提示", "该视频已在收藏列表中")
    
    def add_to_excluded(self, video, card_widget=None):
        """添加到排除列表"""
        bvid = video.get('bvid')
        if bvid:
            if not any(item.get('bvid') == bvid for item in self.excluded):
                self.excluded.append({
                    'bvid': bvid,
                    'title': video.get('title', '未知标题')
                })
                self.save_favorites_and_excluded()
                
                # 从当前显示中移除该卡片
                if card_widget:
                    card_widget.deleteLater()
                
                QMessageBox.information(self, "成功", "已添加到排除列表")
            else:
                QMessageBox.information(self, "提示", "该视频已在排除列表中")
    
    def add_to_playlist_dialog(self, video):
        """添加到播放列表对话框"""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QListWidget, QPushButton, QHBoxLayout, QLineEdit
        
        dialog = QDialog(self)
        dialog.setWindowTitle("添加到播放列表")
        dialog.setFixedSize(400, 350)
        
        # 获取当前主题
        display_mode = getattr(self, 'settings', {}).get('display_mode', 'light')
        is_dark = display_mode == 'dark'
        
        # 根据主题设置对话框样式
        if is_dark:
            dialog.setStyleSheet("""
                QDialog {
                    background: #2d2d2d;
                }
                QLabel {
                    color: #ffffff;
                }
            """)
        else:
            dialog.setStyleSheet("""
                QDialog {
                    background: #ffffff;
                }
                QLabel {
                    color: #2c3e50;
                }
            """)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title_label = QLabel(f"视频: {video.get('title', '未知标题')[:30]}...")
        title_label.setStyleSheet(f"font-weight: bold; font-size: 14px; color: {'#ffffff' if is_dark else '#2c3e50'};")
        title_label.setFont(self.genshin_font)
        layout.addWidget(title_label)
        
        # 播放列表 - 区分临时和永久
        playlist_list = QListWidget()
        if is_dark:
            playlist_list.setStyleSheet("""
                QListWidget {
                    background: #3d3d3d;
                    border: 2px solid #555555;
                    border-radius: 6px;
                    padding: 5px;
                }
                QListWidget::item {
                    padding: 8px;
                    border-radius: 4px;
                    color: #ffffff;
                    background: transparent;
                    border-bottom: 1px solid #4d4d4d;
                }
                QListWidget::item:selected {
                    background: #3498db;
                    color: white;
                }
                QListWidget::item:hover {
                    background: #4d4d4d;
                }
            """)
        else:
            playlist_list.setStyleSheet("""
                QListWidget {
                    background: white;
                    border: 2px solid #e0e0e0;
                    border-radius: 6px;
                    padding: 5px;
                }
                QListWidget::item {
                    padding: 8px;
                    border-radius: 4px;
                    color: #2c3e50;
                    background: transparent;
                    border-bottom: 1px solid #f0f0f0;
                }
                QListWidget::item:selected {
                    background: #3498db;
                    color: white;
                }
                QListWidget::item:hover {
                    background: #f0f0f0;
                }
            """)
        
        # 添加分组标签
        if self.playlists:
            # 临时播放列表组
            temp_playlists = [p for p in self.playlists if p.get('type') == 'temporary']
            if temp_playlists:
                header_temp = QListWidgetItem("⚡ 临时播放列表（可随时清空）")
                header_temp.setFlags(Qt.NoItemFlags)  # 不可选择
                header_temp.setBackground(QColor('#3498db' if not is_dark else '#2980b9'))
                header_temp.setForeground(QColor('#ffffff'))
                playlist_list.addItem(header_temp)
                for playlist in temp_playlists:
                    item = QListWidgetItem(f"   {playlist.get('name', '未命名')}")
                    item.setData(Qt.UserRole, self.playlists.index(playlist))
                    playlist_list.addItem(item)
            
            # 永久歌单组
            perm_playlists = [p for p in self.playlists if p.get('type') == 'permanent']
            if perm_playlists:
                if temp_playlists:
                    playlist_list.addItem("")  # 分隔
                header_perm = QListWidgetItem("📁 永久歌单（长期保存）")
                header_perm.setFlags(Qt.NoItemFlags)
                header_perm.setBackground(QColor('#27ae60' if not is_dark else '#1e8449'))
                header_perm.setForeground(QColor('#ffffff'))
                playlist_list.addItem(header_perm)
                for playlist in perm_playlists:
                    item = QListWidgetItem(f"   {playlist.get('name', '未命名')}")
                    item.setData(Qt.UserRole, self.playlists.index(playlist))
                    playlist_list.addItem(item)
        else:
            playlist_list.addItem("暂无播放列表/歌单")
        
        layout.addWidget(playlist_list)
        
        # 新建播放列表
        new_playlist_layout = QHBoxLayout()
        new_playlist_input = QLineEdit()
        new_playlist_input.setPlaceholderText("新建播放列表名称")
        if is_dark:
            new_playlist_input.setStyleSheet("""
                QLineEdit {
                    padding: 8px;
                    border: 2px solid #555555;
                    border-radius: 6px;
                    font-size: 13px;
                    background: #3d3d3d;
                    color: #ffffff;
                }
                QLineEdit::placeholder {
                    color: #888888;
                }
            """)
        else:
            new_playlist_input.setStyleSheet("""
                QLineEdit {
                    padding: 8px;
                    border: 2px solid #e0e0e0;
                    border-radius: 6px;
                    font-size: 13px;
                    background: white;
                    color: #2c3e50;
                }
            """)
        new_playlist_input.setFont(self.genshin_font)
        new_playlist_layout.addWidget(new_playlist_input)
        
        new_playlist_btn = QPushButton("新建")
        new_playlist_btn.setFont(self.genshin_font)
        new_playlist_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border: none;
                border-radius: 6px;
                background: #3498db;
                color: white;
            }
            QPushButton:hover {
                background: #2980b9;
            }
        """)
        new_playlist_btn.clicked.connect(lambda: self.create_and_add_to_playlist(new_playlist_input.text(), video, dialog))
        new_playlist_layout.addWidget(new_playlist_btn)
        layout.addLayout(new_playlist_layout)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        add_btn = QPushButton("添加到选中播放列表")
        add_btn.setFont(self.genshin_font)
        add_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 20px;
                border: none;
                border-radius: 6px;
                background: #3498db;
                color: white;
            }
            QPushButton:hover {
                background: #2980b9;
            }
        """)
        add_btn.clicked.connect(lambda: self.add_video_to_selected_playlist(playlist_list, video, dialog))
        button_layout.addWidget(add_btn)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setFont(self.genshin_font)
        if is_dark:
            cancel_btn.setStyleSheet("""
                QPushButton {
                    padding: 10px 20px;
                    border: 2px solid #555555;
                    border-radius: 6px;
                    background: #3d3d3d;
                    color: #ffffff;
                }
                QPushButton:hover {
                    background: #4d4d4d;
                }
            """)
        else:
            cancel_btn.setStyleSheet("""
                QPushButton {
                    padding: 10px 20px;
                    border: 2px solid #e0e0e0;
                    border-radius: 6px;
                    background: #f9f9f9;
                    color: #2c3e50;
                }
                QPushButton:hover {
                    background: #e9ecef;
                }
            """)
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        dialog.exec_()
    
    def create_and_add_to_playlist(self, playlist_name, video, dialog):
        """创建新歌单并添加视频 - 歌单是永久的"""
        if not playlist_name.strip():
            QMessageBox.warning(self, "提示", "请输入歌单名称")
            return
        
        # 创建新歌单（永久保存）
        new_playlist = {
            'name': playlist_name,
            'items': [{
                'bvid': video.get('bvid'),
                'title': video.get('title'),
                'cover': video.get('cover'),
                'up': video.get('up'),
                'pubdate': video.get('pubdate')
            }],
            'created_at': datetime.now().isoformat(),
            'type': 'permanent',  # 永久歌单
            'description': ''
        }
        self.playlists.append(new_playlist)
        self.save_playlists()
        self.update_playlist_combo()
        QMessageBox.information(self, "成功", f"已创建歌单 '{playlist_name}' 并添加视频")
        dialog.accept()
    
    def add_video_to_selected_playlist(self, playlist_list, video, dialog):
        """添加视频到选中的歌单"""
        current_item = playlist_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "提示", "请选择一个歌单")
            return
        
        # 获取存储的索引
        playlist_index = current_item.data(Qt.UserRole)
        if playlist_index is None:
            QMessageBox.warning(self, "提示", "请选择一个有效的歌单（不能选择分组标题）")
            return
        
        if playlist_index < 0 or playlist_index >= len(self.playlists):
            QMessageBox.warning(self, "错误", "无效的歌单索引")
            return
        
        playlist = self.playlists[playlist_index]
        
        # 确保 items 键存在
        if 'items' not in playlist:
            playlist['items'] = []
        
        # 检查是否已存在
        bvid = video.get('bvid')
        if any(v.get('bvid') == bvid for v in playlist['items']):
            QMessageBox.information(self, "提示", "该视频已在歌单中")
            return
        
        # 添加视频
        playlist['items'].append({
            'bvid': bvid,
            'title': video.get('title'),
            'cover': video.get('cover'),
            'up': video.get('up'),
            'pubdate': video.get('pubdate')
        })
        self.save_playlists()
        QMessageBox.information(self, "成功", f"已添加到歌单 '{playlist.get('name')}'")
        dialog.accept()
    
    def share_video(self, video):
        """分享视频"""
        self.show_share_dialog(video)
    
    def copy_video_link(self, video):
        """复制视频链接"""
        bvid = video.get('bvid')
        if bvid:
            url = f"https://www.bilibili.com/video/{bvid}"
            QApplication.clipboard().setText(url)
            QMessageBox.information(self, "成功", "链接已复制到剪贴板")
    
    def show_video_detail(self, video_data):
        """显示视频详情"""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
        
        dialog = QDialog(self)
        dialog.setWindowTitle("视频详情")
        dialog.setFixedSize(400, 300)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title_label = QLabel(video_data.get('title', '未知标题'))
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        title_label.setFont(self.genshin_font)
        title_label.setWordWrap(True)
        layout.addWidget(title_label)
        
        # UP主
        up_label = QLabel(f"UP主: {video_data.get('up', '未知UP主')}")
        up_label.setStyleSheet("font-size: 14px; color: #666;")
        up_label.setFont(self.genshin_font)
        layout.addWidget(up_label)
        
        # BV号
        bvid_label = QLabel(f"BV号: {video_data.get('bvid', '未知')}")
        bvid_label.setStyleSheet("font-size: 14px; color: #3498db;")
        bvid_label.setFont(self.genshin_font)
        layout.addWidget(bvid_label)
        
        # 发布时间
        pubdate_text = self.format_pubdate(video_data.get('pubdate', video_data.get('pub_time', '未知')))
        pubdate_label = QLabel(f"发布时间: {pubdate_text}")
        pubdate_label.setStyleSheet("font-size: 14px; color: #666;")
        pubdate_label.setFont(self.genshin_font)
        layout.addWidget(pubdate_label)
        
        layout.addStretch()
        
        # 按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        open_btn = QPushButton("打开视频")
        open_btn.setFont(self.genshin_font)
        open_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 20px;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                background: #3498db;
                color: white;
            }
            QPushButton:hover {
                background: #2980b9;
            }
        """)
        open_btn.clicked.connect(lambda: self.open_video(video_data.get('bvid', '')))
        button_layout.addWidget(open_btn)
        
        close_btn = QPushButton("关闭")
        close_btn.setFont(self.genshin_font)
        close_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 20px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                font-size: 14px;
                background: #f9f9f9;
                color: #2c3e50;
            }
            QPushButton:hover {
                background: #e9ecef;
            }
        """)
        close_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        dialog.exec_()
    
    def play_video(self, video_data):
        """播放视频（内置播放器或浏览器）"""
        bvid = video_data.get('bvid')
        if not bvid:
            return
        
        # 标记为已点击（用户实际感兴趣的视频）
        from utils.data_manager import mark_as_clicked
        mark_as_clicked(bvid)
        
        # 优先使用内置播放器（默认启用）
        if self.settings.get('use_builtin_player', True):
            self.show_builtin_player(video_data)
        else:
            # 使用浏览器播放
            self.open_video(bvid)
    
    def show_builtin_player(self, video_data):
        """显示视频预览 - 提供多种播放选项（精致美化版）"""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QGraphicsDropShadowEffect
        from PyQt5.QtCore import Qt, QUrl
        from PyQt5.QtGui import QDesktopServices, QColor
        from utils.video_player import play_video_local, VIDEO_CACHE_DIR, open_cache_manager, get_cache_info
        import os
        
        bvid = video_data.get('bvid', '')
        title = video_data.get('title', '未知标题')
        
        print(f"[内置播放器] 尝试播放: {title} (BV: {bvid})")
        
        if not bvid:
            QMessageBox.warning(self, "错误", "无法获取视频BV号")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("🎬 视频播放")
        # 使用最小尺寸而不是固定尺寸，允许调整大小
        dialog.setMinimumSize(580, 480)
        dialog.resize(620, 520)
        # 设置窗口标志，确保可以正常拖动
        dialog.setWindowFlags(
            Qt.Dialog |
            Qt.WindowTitleHint |
            Qt.WindowCloseButtonHint
        )
        
        # 根据当前显示模式设置主题
        display_mode = self.settings.get('display_mode', 'light')
        if display_mode == 'dark':
            dialog.setStyleSheet("""
                QDialog {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #0d1117, stop:0.5 #161b22, stop:1 #0d1117);
                    border: 1px solid #30363d;
                    border-radius: 16px;
                }
            """)
        else:
            dialog.setStyleSheet("""
                QDialog {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #f5f7fa, stop:0.5 #c3cfe2, stop:1 #f5f7fa);
                    border: 1px solid #e0e0e0;
                    border-radius: 16px;
                }
            """)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # ========== 标题区域 - 精简版 ==========
        title_container = QFrame()
        if display_mode == 'dark':
            title_container.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 rgba(56, 139, 253, 0.15), stop:1 rgba(56, 139, 253, 0.05));
                    border-radius: 10px;
                    border: 1px solid rgba(56, 139, 253, 0.3);
                }
            """)
        else:
            title_container.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 rgba(52, 152, 219, 0.15), stop:1 rgba(52, 152, 219, 0.05));
                    border-radius: 10px;
                    border: 1px solid rgba(52, 152, 219, 0.3);
                }
            """)
        
        title_layout = QVBoxLayout(title_container)
        title_layout.setSpacing(6)
        title_layout.setContentsMargins(12, 12, 12, 12)
        
        # 主标题 - 精简显示
        title_label = QLabel(f"🎬 {title[:50]}{'...' if len(title) > 50 else ''}")
        if display_mode == 'dark':
            title_label.setStyleSheet("""
                font-size: 15px;
                font-weight: bold;
                color: #58a6ff;
            """)
        else:
            title_label.setStyleSheet("""
                font-size: 15px;
                font-weight: bold;
                color: #3498db;
            """)
        title_label.setFont(self.genshin_font)
        title_label.setWordWrap(True)
        title_layout.addWidget(title_label)
        
        # BV号 - 简化显示
        if display_mode == 'dark':
            bvid_label = QLabel(f"🔗 BV: <span style='color:#58a6ff; font-family: Consolas, monospace;'>{bvid}</span>")
            bvid_label.setStyleSheet("font-size: 12px; color: #8b949e;")
        else:
            bvid_label = QLabel(f"🔗 BV: <span style='color:#3498db; font-family: Consolas, monospace;'>{bvid}</span>")
            bvid_label.setStyleSheet("font-size: 12px; color: #7f8c8d;")
        bvid_label.setFont(self.genshin_font)
        title_layout.addWidget(bvid_label)
        
        layout.addWidget(title_container)
        
        # ========== 视频信息区域 - 紧凑版 ==========
        up_text = video_data.get('up主', video_data.get('up', '未知UP主'))
        pubdate_text = self.format_pubdate(video_data.get('pubdate', video_data.get('pub_time', '未知')))
        play_count = video_data.get('play_count', 0)
        
        info_container = QFrame()
        if display_mode == 'dark':
            info_container.setStyleSheet("""
                QFrame {
                    background: rgba(22, 27, 34, 0.8);
                    border-radius: 8px;
                    border: 1px solid #30363d;
                }
            """)
        else:
            info_container.setStyleSheet("""
                QFrame {
                    background: rgba(245, 247, 250, 0.8);
                    border-radius: 8px;
                    border: 1px solid #e0e0e0;
                }
            """)
        info_layout = QHBoxLayout(info_container)
        info_layout.setSpacing(8)
        info_layout.setContentsMargins(12, 10, 12, 10)
        
        # 格式化播放量
        if play_count >= 10000:
            play_str = f"{play_count/10000:.1f}万"
        elif play_count >= 1000:
            play_str = f"{play_count/1000:.1f}k"
        else:
            play_str = f"{play_count}"
        
        # 显示完整时间
        short_date = pubdate_text  # 显示完整的年月日时分秒
        
        info_items = [
            ("👤", up_text[:8] + '...' if len(up_text) > 8 else up_text, "#f0883e"),
            ("📅", short_date, "#3fb950"),
            ("▶", play_str, "#58a6ff"),
        ]
        
        for icon, value, color in info_items:
            if display_mode == 'dark':
                item_label = QLabel(f"{icon}<span style='color:{color};'>{value}</span>")
                item_label.setStyleSheet("font-size: 11px; color: #8b949e;")
            else:
                item_label = QLabel(f"{icon}<span style='color:{color};'>{value}</span>")
                item_label.setStyleSheet("font-size: 11px; color: #7f8c8d;")
            item_label.setFont(self.genshin_font)
            info_layout.addWidget(item_label)
        
        info_layout.addStretch()
        layout.addWidget(info_container)
        
        # ========== 播放选项区域 - 精简版 ==========
        buttons_container = QFrame()
        if display_mode == 'dark':
            buttons_container.setStyleSheet("""
                QFrame {
                    background: rgba(22, 27, 34, 0.6);
                    border-radius: 10px;
                    border: 1px solid #30363d;
                }
            """)
        else:
            buttons_container.setStyleSheet("""
                QFrame {
                    background: rgba(245, 247, 250, 0.6);
                    border-radius: 10px;
                    border: 1px solid #e0e0e0;
                }
            """)
        btn_layout = QVBoxLayout(buttons_container)
        btn_layout.setSpacing(8)
        btn_layout.setContentsMargins(15, 15, 15, 15)
        
        # 1. 下载并播放（推荐）- 主按钮 - 精简版
        download_btn = QPushButton("📥 下载并播放")
        download_btn.setFont(self.genshin_font)
        download_btn.setFixedHeight(44)
        download_btn.setCursor(Qt.PointingHandCursor)
        download_btn.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #238636, stop:1 #2ea043);
                color: white;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2ea043, stop:1 #3fb950);
            }
        """)
        download_btn.clicked.connect(lambda: self._download_and_play(bvid, title, dialog, up_text, pubdate_text))
        btn_layout.addWidget(download_btn)
        
        # 2. 在线播放（流媒体）
        online_btn = QPushButton("🎬 流媒体播放")
        online_btn.setFont(self.genshin_font)
        online_btn.setFixedHeight(44)
        online_btn.setCursor(Qt.PointingHandCursor)
        if display_mode == 'dark':
            online_btn.setStyleSheet("""
                QPushButton {
                    border: none;
                    border-radius: 8px;
                    font-size: 14px;
                    font-weight: bold;
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #1f6feb, stop:1 #388bfd);
                    color: white;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #388bfd, stop:1 #58a6ff);
                }
            """)
        else:
            online_btn.setStyleSheet("""
                QPushButton {
                    border: none;
                    border-radius: 8px;
                    font-size: 14px;
                    font-weight: bold;
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #2980b9, stop:1 #3498db);
                    color: white;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #3498db, stop:1 #5dade2);
                }
            """)
        online_btn.clicked.connect(lambda: self._play_online(bvid, title, dialog))
        btn_layout.addWidget(online_btn)
        
        # 次要操作按钮行 - 水平排列
        secondary_layout = QHBoxLayout()
        secondary_layout.setSpacing(8)
        
        # 2. 浏览器打开
        browser_btn = QPushButton("🌐 浏览器")
        browser_btn.setFont(self.genshin_font)
        browser_btn.setFixedHeight(36)
        browser_btn.setCursor(Qt.PointingHandCursor)
        if display_mode == 'dark':
            browser_btn.setStyleSheet("""
                QPushButton {
                    border: 1px solid #58a6ff;
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: bold;
                    background: transparent;
                    color: #58a6ff;
                }
                QPushButton:hover {
                    background: rgba(88, 166, 255, 0.15);
                }
            """)
        else:
            browser_btn.setStyleSheet("""
                QPushButton {
                    border: 1px solid #3498db;
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: bold;
                    background: transparent;
                    color: #3498db;
                }
                QPushButton:hover {
                    background: rgba(52, 152, 219, 0.15);
                }
            """)
        browser_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(f"https://www.bilibili.com/video/{bvid}")))
        secondary_layout.addWidget(browser_btn)
        
        # 3. 复制链接
        copy_btn = QPushButton("📋 复制")
        copy_btn.setFont(self.genshin_font)
        copy_btn.setFixedHeight(36)
        copy_btn.setCursor(Qt.PointingHandCursor)
        if display_mode == 'dark':
            copy_btn.setStyleSheet("""
                QPushButton {
                    border: 1px solid #8b949e;
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: bold;
                    background: transparent;
                    color: #8b949e;
                }
                QPushButton:hover {
                    background: rgba(139, 148, 158, 0.15);
                    color: #c9d1d9;
                }
            """)
        else:
            copy_btn.setStyleSheet("""
                QPushButton {
                    border: 1px solid #7f8c8d;
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: bold;
                    background: transparent;
                    color: #7f8c8d;
                }
                QPushButton:hover {
                    background: rgba(127, 140, 141, 0.15);
                    color: #2c3e50;
                }
            """)
        copy_btn.clicked.connect(lambda: self.copy_video_link(bvid))
        secondary_layout.addWidget(copy_btn)
        
        # 4. 收藏
        fav_btn = QPushButton("❤️ 收藏")
        fav_btn.setFont(self.genshin_font)
        fav_btn.setFixedHeight(36)
        fav_btn.setCursor(Qt.PointingHandCursor)
        if display_mode == 'dark':
            fav_btn.setStyleSheet("""
                QPushButton {
                    border: 1px solid #f778ba;
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: bold;
                    background: transparent;
                    color: #f778ba;
                }
                QPushButton:hover {
                    background: rgba(247, 120, 186, 0.15);
                }
            """)
        else:
            fav_btn.setStyleSheet("""
                QPushButton {
                    border: 1px solid #e74c3c;
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: bold;
                    background: transparent;
                    color: #e74c3c;
                }
                QPushButton:hover {
                    background: rgba(231, 76, 60, 0.15);
                }
            """)
        fav_btn.clicked.connect(lambda: self.add_to_favorites(video_data))
        secondary_layout.addWidget(fav_btn)
        
        btn_layout.addLayout(secondary_layout)
        layout.addWidget(buttons_container)
        
        # ========== 缓存信息区域 - 精简版 ==========
        cache_container = QFrame()
        if display_mode == 'dark':
            cache_container.setStyleSheet("""
                QFrame {
                    background: rgba(139, 148, 158, 0.08);
                    border-radius: 8px;
                    border: 1px solid rgba(139, 148, 158, 0.2);
                }
            """)
        else:
            cache_container.setStyleSheet("""
                QFrame {
                    background: rgba(127, 140, 141, 0.08);
                    border-radius: 8px;
                    border: 1px solid rgba(127, 140, 141, 0.2);
                }
            """)
        cache_layout = QHBoxLayout(cache_container)
        cache_layout.setSpacing(10)
        cache_layout.setContentsMargins(12, 8, 12, 8)
        
        # 获取缓存信息
        cache_info = get_cache_info()
        
        # 缓存图标和文字
        cache_icon = QLabel("💾")
        cache_icon.setStyleSheet("font-size: 14px;")
        cache_layout.addWidget(cache_icon)
        
        # 缓存统计 - 使用颜色区分大小
        cache_count = cache_info['count']
        cache_size = cache_info['total_size_mb']
        
        size_color = "#3fb950" if cache_size < 500 else ("#f0883e" if cache_size < 1000 else "#f85149")
        
        if display_mode == 'dark':
            cache_text = QLabel(f"<b>{cache_count}</b>个视频 | <span style='color:{size_color};'>{cache_size:.0f}MB</span>")
            cache_text.setStyleSheet("font-size: 12px; color: #8b949e;")
        else:
            cache_text = QLabel(f"<b>{cache_count}</b>个视频 | <span style='color:{size_color};'>{cache_size:.0f}MB</span>")
            cache_text.setStyleSheet("font-size: 12px; color: #7f8c8d;")
        cache_text.setFont(self.genshin_font)
        cache_layout.addWidget(cache_text)
        
        cache_layout.addStretch()
        
        # 管理按钮
        manage_btn = QPushButton("管理")
        manage_btn.setFixedHeight(28)
        if display_mode == 'dark':
            manage_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(88, 166, 255, 0.1);
                    color: #58a6ff;
                    border: 1px solid rgba(88, 166, 255, 0.3);
                    border-radius: 5px;
                    font-size: 11px;
                    padding: 2px 10px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: rgba(88, 166, 255, 0.2);
                }
            """)
        else:
            manage_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(52, 152, 219, 0.1);
                    color: #3498db;
                    border: 1px solid rgba(52, 152, 219, 0.3);
                    border-radius: 5px;
                    font-size: 11px;
                    padding: 2px 10px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: rgba(52, 152, 219, 0.2);
                }
            """)
        manage_btn.setCursor(Qt.PointingHandCursor)
        manage_btn.clicked.connect(lambda: open_cache_manager(self))
        cache_layout.addWidget(manage_btn)
        
        layout.addWidget(cache_container)
        
        # ========== 关闭按钮 - 精简版 ==========
        close_btn = QPushButton("关闭")
        close_btn.setFont(self.genshin_font)
        close_btn.setFixedHeight(36)
        close_btn.setCursor(Qt.PointingHandCursor)
        if display_mode == 'dark':
            close_btn.setStyleSheet("""
                QPushButton {
                    border: 1px solid #30363d;
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: bold;
                    background: rgba(48, 54, 61, 0.5);
                    color: #8b949e;
                }
                QPushButton:hover {
                    background: rgba(48, 54, 61, 0.8);
                    color: #c9d1d9;
                }
            """)
        else:
            close_btn.setStyleSheet("""
                QPushButton {
                    border: 1px solid #e0e0e0;
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: bold;
                    background: rgba(249, 249, 249, 0.5);
                    color: #7f8c8d;
                }
                QPushButton:hover {
                    background: rgba(233, 236, 239, 0.8);
                    color: #2c3e50;
                }
            """)
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn, alignment=Qt.AlignCenter)
        
        dialog.exec_()
    
    def _download_and_play(self, bvid: str, title: str, parent_dialog, up_name: str = "", pubdate: str = ""):
        """下载并播放视频"""
        from utils.video_player import download_and_play_video
        parent_dialog.close()
        download_and_play_video(bvid, title, up_name, pubdate, self)
    
    def _play_online(self, bvid: str, title: str, parent_dialog):
        """在线播放视频（使用外部播放器流媒体播放）"""
        from utils.video_player import play_video_streaming
        
        # 关闭父对话框
        parent_dialog.close()
        
        # 使用外部播放器进行流媒体播放
        success = play_video_streaming(bvid, title)
        
        if not success:
            # 如果 mpv 不可用，回退到浏览器播放
            from PyQt5.QtCore import QUrl
            from PyQt5.QtGui import QDesktopServices
            QMessageBox.information(self, "提示", "mpv 播放器未安装，将使用浏览器播放")
            url = f"https://www.bilibili.com/video/{bvid}"
            QDesktopServices.openUrl(QUrl(url))
    
    def copy_video_link(self, video_or_bvid):
        """复制视频链接
        :param video_or_bvid: 可以是视频字典或BV号字符串
        """
        if isinstance(video_or_bvid, dict):
            bvid = video_or_bvid.get('bvid', '')
        else:
            bvid = video_or_bvid
        
        if bvid:
            QApplication.clipboard().setText(f"https://www.bilibili.com/video/{bvid}")
            QMessageBox.information(self, "成功", "视频链接已复制到剪贴板")
        else:
            QMessageBox.warning(self, "错误", "无法获取视频链接")
    
    def decrement_load_semaphore(self):
        """减少加载计数"""
        if self.load_semaphore > 0:
            self.load_semaphore -= 1
    
    def delayed_load_cover(self, cover_url, cover_label):
        """延迟加载封面 - 保留用于兼容性"""
        # 检查控件是否还存在
        try:
            if not cover_label or not cover_label.parent():
                return
        except RuntimeError:
            return
        
        # 检查缓存
        cache = CoverCache()
        cached_pixmap = cache.get(cover_url)
        if cached_pixmap:
            try:
                cover_label.setPixmap(cached_pixmap)
            except RuntimeError:
                pass
    
    def update_cover(self, idx, pixmap, label_or_url):
        """更新封面图片 - 支持新旧两种调用方式"""
        # 检查 QLabel 是否还存在（可能已被删除）
        try:
            if isinstance(label_or_url, str):
                # 新方式：通过URL更新
                self._cover_update_signal.update_cover.emit(label_or_url, pixmap)
            elif label_or_url and label_or_url.parent():
                # 旧方式：直接更新label
                label_or_url.setPixmap(pixmap)
        except RuntimeError:
            # QLabel 已被删除，忽略错误
            pass
    
    def open_video(self, bvid):
        """在浏览器中打开视频"""
        if bvid and self.open_in_browser:
            url = f"https://www.bilibili.com/video/{bvid}"
            webbrowser.open(url)
    
    def favorite_video(self, video):
        """收藏视频"""
        bvid = video.get('bvid')
        if bvid:
            # 检查是否已经收藏
            if not any(item.get('bvid') == bvid for item in self.favorites):
                self.favorites.append({
                    'bvid': bvid,
                    'title': video.get('title', '未知标题'),
                    'cover': video.get('cover'),
                    'up': video.get('up', '未知UP主'),
                    'pubdate': video.get('pubdate', '未知')
                })
                self.save_favorites_and_excluded()
                QMessageBox.information(self, "成功", "已添加到收藏列表")
            else:
                QMessageBox.information(self, "提示", "该视频已在收藏列表中")
    
    def dislike_video(self, video):
        """排除视频"""
        bvid = video.get('bvid')
        if bvid:
            # 检查是否已经排除
            if not any(item.get('bvid') == bvid for item in self.excluded):
                self.excluded.append({
                    'bvid': bvid,
                    'title': video.get('title', '未知标题')
                })
                self.save_favorites_and_excluded()
                # 刷新推荐内容
                self.refresh_recommendations()
                QMessageBox.information(self, "成功", "已添加到排除列表")
            else:
                QMessageBox.information(self, "提示", "该视频已在排除列表中")
    
    def share_video(self, video):
        """分享视频 - 简化版，借鉴小程序体验"""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QGridLayout
        
        dialog = QDialog(self)
        dialog.setWindowTitle("分享视频")
        dialog.setFixedSize(450, 300)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title_label = QLabel(f"📤 {video.get('title', '未知标题')}")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50;")
        title_label.setFont(self.genshin_font)
        layout.addWidget(title_label)
        
        # 快速分享选项 - 使用网格布局
        quick_share_layout = QGridLayout()
        quick_share_layout.setSpacing(12)
        
        quick_options = [
            ("📋 复制链接", "copy", "#3498db"),
            ("💬 微信", "wechat", "#07C160"),
            ("🐧 QQ", "qq", "#12B7F5"),
            ("📢 微博", "weibo", "#E6162D"),
            ("🐦 Twitter", "twitter", "#1DA1F2"),
            ("📘 Facebook", "facebook", "#1877F2")
        ]
        
        for idx, (name, platform, color) in enumerate(quick_options):
            row = idx // 3
            col = idx % 3
            
            btn = QPushButton(name)
            btn.setFont(self.genshin_font)
            btn.setStyleSheet(f"""
                QPushButton {{
                    padding: 12px;
                    border: 2px solid {color};
                    border-radius: 8px;
                    font-size: 13px;
                    background: white;
                    color: {color};
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background: {color};
                    color: white;
                }}
                QPushButton:pressed {{
                    background: {color};
                    color: white;
                }}
            """)
            btn.clicked.connect(lambda checked, p=platform, d=dialog: self._quick_share(video, p, d))
            quick_share_layout.addWidget(btn, row, col)
        
        layout.addLayout(quick_share_layout)
        
        # 更多选项
        more_layout = QHBoxLayout()
        more_layout.setSpacing(10)
        
        card_btn = QPushButton("🎨 生成分享卡片")
        card_btn.setFont(self.genshin_font)
        card_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 20px;
                border: 2px solid #9b59b6;
                border-radius: 6px;
                font-size: 13px;
                background: white;
                color: #9b59b6;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #9b59b6;
                color: white;
            }
        """)
        card_btn.clicked.connect(lambda: self.generate_share_card(video))
        more_layout.addWidget(card_btn)
        
        more_layout.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setFont(self.genshin_font)
        cancel_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 20px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                font-size: 13px;
                background: #f9f9f9;
                color: #2c3e50;
            }
            QPushButton:hover {
                background: #e9ecef;
            }
        """)
        cancel_btn.clicked.connect(dialog.reject)
        more_layout.addWidget(cancel_btn)
        
        layout.addLayout(more_layout)
        
        dialog.exec_()
    
    def _quick_share(self, video, platform, dialog):
        """快速分享 - 借鉴小程序的简洁体验"""
        bvid = video.get('bvid')
        title = video.get('title', '未知标题')
        up = video.get('up', video.get('up主', '未知UP主'))
        
        if bvid:
            url = f"https://www.bilibili.com/video/{bvid}"
            
            if platform == 'copy':
                # 直接复制链接 - 小程序风格
                share_text = f"{title}\nUP主: {up}\n{url}"
                QApplication.clipboard().setText(share_text)
                
                # 关闭对话框并显示简洁提示
                dialog.close()
                self._show_toast("✅ 链接已复制到剪贴板")
                
            elif platform == 'wechat':
                # 微信分享
                share_text = f"{title}\nUP主: {up}\n{url}"
                QApplication.clipboard().setText(share_text)
                dialog.close()
                self._show_toast("✅ 已复制，请粘贴到微信")
                
            elif platform == 'qq':
                share_text = f"{title}\nUP主: {up}\n{url}"
                share_url = f"https://connect.qq.com/widget/shareqq/index.html?url={url}&title={title}"
                QApplication.clipboard().setText(share_text)
                webbrowser.open(share_url)
                dialog.close()
                
            elif platform == 'weibo':
                share_text = f"{title}\nUP主: {up}\n{url}"
                share_url = f"https://service.weibo.com/share/share.php?url={url}&title={share_text}"
                webbrowser.open(share_url)
                dialog.close()
                
            elif platform == 'twitter':
                share_text = f"{title} - {up}"
                share_url = f"https://twitter.com/intent/tweet?url={url}&text={share_text}"
                webbrowser.open(share_url)
                dialog.close()
                
            elif platform == 'facebook':
                share_url = f"https://www.facebook.com/sharer/sharer.php?u={url}"
                webbrowser.open(share_url)
                dialog.close()
            
            # 记录分享历史
            try:
                add_share_record(video, platform)
            except Exception as e:
                print(f"记录分享历史失败: {e}")
    
    def _show_toast(self, message):
        """显示简洁的提示消息 - 借鉴小程序风格"""
        from PyQt5.QtWidgets import QLabel, QWidget
        from PyQt5.QtCore import QTimer, Qt
        
        toast = QLabel(message)
        toast.setStyleSheet("""
            QLabel {
                background: rgba(0, 0, 0, 0.8);
                color: white;
                padding: 15px 25px;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
        """)
        toast.setFont(self.genshin_font)
        
        # 居中显示
        toast.setParent(self)
        toast.setAlignment(Qt.AlignCenter)
        toast.adjustSize()
        
        # 计算位置
        x = (self.width() - toast.width()) // 2
        y = self.height() - 100
        toast.move(x, y)
        
        toast.show()
        
        # 2秒后自动消失
        QTimer.singleShot(2000, toast.deleteLater)
    
    def _show_post_comment_dialog(self):
        """显示发表评论对话框"""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QTextEdit, QPushButton, QHBoxLayout, QLineEdit
        
        dialog = QDialog(self)
        dialog.setWindowTitle("发表评论")
        dialog.setFixedSize(500, 400)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title_label = QLabel("✏️ 发表社区评论")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
                padding-bottom: 10px;
                border-bottom: 2px solid #27ae60;
            }
        """)
        title_label.setFont(self.genshin_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # 用户昵称
        nickname_layout = QHBoxLayout()
        nickname_label = QLabel("昵称:")
        nickname_label.setStyleSheet("font-size: 13px; color: #2c3e50;")
        nickname_label.setFont(self.genshin_font)
        nickname_layout.addWidget(nickname_label)
        
        nickname_input = QLineEdit()
        nickname_input.setPlaceholderText("输入昵称（可选）")
        nickname_input.setFont(self.genshin_font)
        nickname_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 2px solid #27ae60;
            }
        """)
        nickname_layout.addWidget(nickname_input)
        layout.addLayout(nickname_layout)
        
        # 视频BV号（可选）
        bvid_layout = QHBoxLayout()
        bvid_label = QLabel("视频BV号:")
        bvid_label.setStyleSheet("font-size: 13px; color: #2c3e50;")
        bvid_label.setFont(self.genshin_font)
        bvid_layout.addWidget(bvid_label)
        
        bvid_input = QLineEdit()
        bvid_input.setPlaceholderText("输入BV号（可选，如：BV1xx411c7mD）")
        bvid_input.setFont(self.genshin_font)
        bvid_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 2px solid #27ae60;
            }
        """)
        bvid_layout.addWidget(bvid_input)
        layout.addLayout(bvid_layout)
        
        # 评论内容
        content_label = QLabel("评论内容:")
        content_label.setStyleSheet("font-size: 13px; color: #2c3e50;")
        content_label.setFont(self.genshin_font)
        layout.addWidget(content_label)
        
        content_text = QTextEdit()
        content_text.setPlaceholderText("分享你的音乐发现和想法...")
        content_text.setMaximumHeight(150)
        content_text.setFont(self.genshin_font)
        content_text.setStyleSheet("""
            QTextEdit {
                padding: 10px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                font-size: 13px;
            }
            QTextEdit:focus {
                border: 2px solid #27ae60;
            }
        """)
        layout.addWidget(content_text)
        
        # 提示
        hint_label = QLabel("💡 提示：最多500字，支持分享音乐推荐和交流")
        hint_label.setStyleSheet("color: #95a5a6; font-size: 11px;")
        hint_label.setFont(self.genshin_font)
        layout.addWidget(hint_label)
        
        # 按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setFont(self.genshin_font)
        cancel_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 25px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                font-size: 13px;
                background: #f9f9f9;
                color: #2c3e50;
            }
            QPushButton:hover {
                background: #e9ecef;
            }
        """)
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_btn)
        
        button_layout.addStretch()
        
        submit_btn = QPushButton("📝 发表评论")
        submit_btn.setFont(self.genshin_font)
        submit_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 25px;
                border: 2px solid #27ae60;
                border-radius: 6px;
                font-size: 13px;
                background: #27ae60;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #219150;
            }
        """)
        submit_btn.clicked.connect(lambda: self._submit_comment(
            nickname_input.text(),
            bvid_input.text(),
            content_text.toPlainText(),
            dialog
        ))
        button_layout.addWidget(submit_btn)
        
        layout.addLayout(button_layout)
        
        dialog.exec_()
    
    def _submit_comment(self, nickname, bvid, content, dialog):
        """提交评论"""
        # 验证内容
        if not content or len(content.strip()) == 0:
            QMessageBox.warning(dialog, "提示", "评论内容不能为空")
            return
        
        if len(content) > 500:
            QMessageBox.warning(dialog, "提示", "评论内容不能超过500字")
            return
        
        try:
            # 生成或获取游客ID
            import hashlib
            import os
            import time
            timestamp = str(int(time.time()))
            base_str = f"local_user_{timestamp}_{os.urandom(8).hex()}"
            user_id = f"guest_{hashlib.md5(base_str.encode()).hexdigest()[:12]}"
            
            # 如果没有昵称，生成默认昵称
            if not nickname or not nickname.strip():
                nickname = f"音乐爱好者{hashlib.md5(user_id.encode()).hexdigest()[:4]}"
            else:
                nickname = nickname.strip()
            
            # 发表评论
            result = self.community_system.post_comment(
                user_id=user_id,
                content=content,
                bvid=bvid if bvid else None,
                is_guest=True
            )
            
            if result.get("success"):
                dialog.close()
                self._show_toast("✅ 评论发表成功")
                
                # 刷新社区动态
                self.show_social_feed()
            else:
                error_msg = result.get("error", "发表失败")
                QMessageBox.warning(dialog, "错误", error_msg)
                
        except Exception as e:
            QMessageBox.warning(dialog, "错误", f"发表评论失败: {str(e)}")
    
    def social_share(self, video):
        """社交分享 - 显示平台选择对话框"""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QGridLayout
        from PyQt5.QtCore import Qt
        
        dialog = QDialog(self)
        dialog.setWindowTitle("社交分享")
        dialog.setFixedSize(450, 350)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(20)
        layout.setContentsMargins(25, 25, 25, 25)
        
        # 标题
        title_label = QLabel("📤 选择分享平台")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
                padding-bottom: 10px;
                border-bottom: 2px solid #3498db;
            }
        """)
        title_label.setFont(self.genshin_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # 视频信息
        video_title = video.get('title', '未知标题')[:30] + "..." if len(video.get('title', '')) > 30 else video.get('title', '未知标题')
        info_label = QLabel(f"分享: {video_title}")
        info_label.setStyleSheet("font-size: 13px; color: #7f8c8d; padding: 5px;")
        info_label.setFont(self.genshin_font)
        info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(info_label)
        
        # 分享平台 - 使用网格布局
        platform_grid = QGridLayout()
        platform_grid.setSpacing(15)
        
        platforms = [
            ("💬 微信", "wechat", "#07C160"),
            ("🐧 QQ", "qq", "#12B7F5"),
            ("📢 微博", "weibo", "#E6162D"),
            ("🐦 Twitter", "twitter", "#1DA1F2"),
            ("📘 Facebook", "facebook", "#1877F2"),
            ("📋 复制链接", "copy", "#3498db"),
            ("🎨 生成卡片", "card", "#9b59b6")
        ]
        
        for idx, (name, platform, color) in enumerate(platforms):
            row = idx // 2
            col = idx % 2
            
            platform_btn = QPushButton(name)
            platform_btn.setFont(self.genshin_font)
            platform_btn.setFixedHeight(50)
            platform_btn.setCursor(Qt.PointingHandCursor)
            platform_btn.setStyleSheet(f"""
                QPushButton {{
                    padding: 10px;
                    border: none;
                    border-radius: 8px;
                    font-size: 14px;
                    font-weight: bold;
                    background: {color};
                    color: white;
                }}
                QPushButton:hover {{
                    background: {color}dd;
                    transform: scale(1.05);
                }}
                QPushButton:pressed {{
                    background: {color}bb;
                }}
            """)
            platform_btn.clicked.connect(lambda checked=False, p=platform, v=video, d=dialog: 
                self.share_to_platform_and_close(v, p, d))
            platform_grid.addWidget(platform_btn, row, col)
        
        layout.addLayout(platform_grid)
        layout.addStretch()
        
        # 取消按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        cancel_btn = QPushButton("❌ 取消")
        cancel_btn.setFont(self.genshin_font)
        cancel_btn.setFixedHeight(40)
        cancel_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 30px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                background: #f9f9f9;
                color: #2c3e50;
            }
            QPushButton:hover {
                background: #e9ecef;
                border-color: #bdc3c7;
            }
        """)
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        dialog.exec_()
    
    def share_to_platform_and_close(self, video, platform, dialog):
        """分享到平台并关闭对话框"""
        dialog.close()
        self.share_to_platform(video, platform)
    
    def share_to_platform(self, video, platform):
        """分享到指定平台"""
        bvid = video.get('bvid')
        title = video.get('title', '未知标题')
        up = video.get('up', video.get('up主', '未知UP主'))
        if bvid:
            url = f"https://www.bilibili.com/video/{bvid}"
            
            # 构建分享文本
            share_text = f"【{title}】UP主: {up} - 来自Vocaloid音乐推荐系统"
            
            # 构建分享链接
            if platform == 'wechat':
                # 微信分享 - 复制链接并提示
                full_text = f"{share_text}\n{url}"
                QApplication.clipboard().setText(full_text)
                QMessageBox.information(self, "微信分享", "分享内容已复制到剪贴板，请粘贴到微信")
            elif platform == 'qq':
                share_url = f"https://connect.qq.com/widget/shareqq/index.html?url={url}&title={share_text}"
                webbrowser.open(share_url)
            elif platform == 'weibo':
                share_url = f"https://service.weibo.com/share/share.php?url={url}&title={share_text}"
                webbrowser.open(share_url)
            elif platform == 'twitter':
                share_url = f"https://twitter.com/intent/tweet?url={url}&text={share_text}"
                webbrowser.open(share_url)
            elif platform == 'facebook':
                share_url = f"https://www.facebook.com/sharer/sharer.php?u={url}"
                webbrowser.open(share_url)
            elif platform == 'copy':
                # 复制链接功能
                full_text = f"{share_text}\n{url}"
                QApplication.clipboard().setText(full_text)
                QMessageBox.information(self, "复制成功", "分享内容已复制到剪贴板！")
            elif platform == 'card':
                # 生成分享卡片
                self.generate_share_card(video)
                return  # 生成卡片有自己的记录逻辑
            
            # 记录分享历史
            try:
                add_share_record(video, platform)
            except Exception as e:
                print(f"记录分享历史失败: {e}")
    
    def generate_share_card(self, video):
        """生成分享卡片"""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QTextEdit
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QPixmap, QImage
        import requests
        from io import BytesIO
        
        dialog = QDialog(self)
        dialog.setWindowTitle("生成分享卡片")
        dialog.setFixedSize(500, 600)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title_label = QLabel("🎨 分享卡片")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
                padding-bottom: 10px;
                border-bottom: 2px solid #9b59b6;
            }
        """)
        title_label.setFont(self.genshin_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # 卡片预览区域
        card_widget = QWidget()
        card_widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #667eea, stop:1 #764ba2);
                border-radius: 12px;
                padding: 20px;
            }
        """)
        card_layout = QVBoxLayout(card_widget)
        card_layout.setSpacing(10)
        
        # 视频标题
        video_title = video.get('title', '未知标题')
        card_title = QLabel(video_title)
        card_title.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: white;
                padding: 10px;
            }
        """)
        card_title.setFont(self.genshin_font)
        card_title.setWordWrap(True)
        card_layout.addWidget(card_title)
        
        # UP主信息
        up_name = video.get('up', video.get('up主', '未知UP主'))
        up_label = QLabel(f"UP主: {up_name}")
        up_label.setStyleSheet("font-size: 13px; color: rgba(255,255,255,0.9);")
        up_label.setFont(self.genshin_font)
        card_layout.addWidget(up_label)
        
        # 封面图片
        cover_label = QLabel()
        cover_label.setFixedSize(400, 225)
        cover_label.setStyleSheet("""
            QLabel {
                background: rgba(255,255,255,0.1);
                border-radius: 8px;
            }
        """)
        cover_label.setAlignment(Qt.AlignCenter)
        
        # 加载封面
        cover_url = video.get('cover', '')
        if cover_url:
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                response = requests.get(cover_url, headers=headers, timeout=10)
                if response.status_code == 200:
                    image = QImage.fromData(response.content)
                    pixmap = QPixmap.fromImage(image)
                    scaled_pixmap = pixmap.scaled(400, 225, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    cover_label.setPixmap(scaled_pixmap)
            except Exception as e:
                cover_label.setText("封面加载失败")
        else:
            cover_label.setText("暂无封面")
        
        card_layout.addWidget(cover_label, alignment=Qt.AlignCenter)
        
        # 推荐语
        recommend_label = QLabel("🎵 来自 VocaloidToolboxFusion 音乐推荐")
        recommend_label.setStyleSheet("font-size: 12px; color: rgba(255,255,255,0.8);")
        recommend_label.setFont(self.genshin_font)
        recommend_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(recommend_label)
        
        layout.addWidget(card_widget)
        
        # 分享文案编辑区
        edit_label = QLabel("分享文案（可编辑）:")
        edit_label.setStyleSheet("font-size: 13px; color: #2c3e50;")
        edit_label.setFont(self.genshin_font)
        layout.addWidget(edit_label)
        
        bvid = video.get('bvid', '')
        default_text = f"🎵 发现了一首好听的Vocaloid音乐！\n\n📺 {video_title}\n👤 UP主: {up_name}\n\n🔗 https://www.bilibili.com/video/{bvid}\n\n🎶 来自 VocaloidToolboxFusion 音乐推荐系统"
        
        text_edit = QTextEdit()
        text_edit.setPlainText(default_text)
        text_edit.setFont(self.genshin_font)
        text_edit.setStyleSheet("""
            QTextEdit {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 10px;
                font-size: 13px;
            }
        """)
        text_edit.setFixedHeight(120)
        layout.addWidget(text_edit)
        
        # 按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        
        # 复制文案按钮
        copy_text_btn = QPushButton("📋 复制文案")
        copy_text_btn.setFont(self.genshin_font)
        copy_text_btn.setFixedHeight(45)
        copy_text_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 20px;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                background: #3498db;
                color: white;
            }
            QPushButton:hover {
                background: #2980b9;
            }
        """)
        copy_text_btn.clicked.connect(lambda: self.copy_share_card_text(text_edit.toPlainText()))
        button_layout.addWidget(copy_text_btn)
        
        # 保存图片按钮
        save_img_btn = QPushButton("💾 保存卡片")
        save_img_btn.setFont(self.genshin_font)
        save_img_btn.setFixedHeight(45)
        save_img_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 20px;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                background: #27ae60;
                color: white;
            }
            QPushButton:hover {
                background: #229954;
            }
        """)
        save_img_btn.clicked.connect(lambda: self.save_share_card_image(card_widget, video))
        button_layout.addWidget(save_img_btn)
        
        # 关闭按钮
        close_btn = QPushButton("❌ 关闭")
        close_btn.setFont(self.genshin_font)
        close_btn.setFixedHeight(45)
        close_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 20px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                background: #f9f9f9;
                color: #2c3e50;
            }
            QPushButton:hover {
                background: #e9ecef;
            }
        """)
        close_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        # 记录分享历史
        try:
            add_share_record(video, 'card')
        except Exception as e:
            print(f"记录分享历史失败: {e}")
        
        dialog.exec_()
    
    def copy_share_card_text(self, text):
        """复制分享卡片文案"""
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, "复制成功", "分享文案已复制到剪贴板！")
    
    def save_share_card_image(self, card_widget, video):
        """保存分享卡片为图片"""
        from PyQt5.QtWidgets import QFileDialog
        from PyQt5.QtCore import QDateTime
        
        # 生成文件名
        timestamp = QDateTime.currentDateTime().toString("yyyyMMdd_hhmmss")
        bvid = video.get('bvid', 'unknown')
        default_name = f"share_card_{bvid}_{timestamp}.png"
        
        # 选择保存路径
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存分享卡片",
            default_name,
            "PNG图片 (*.png);;JPEG图片 (*.jpg);;所有文件 (*.*)"
        )
        
        if file_path:
            try:
                # 截取卡片区域
                pixmap = card_widget.grab()
                pixmap.save(file_path)
                QMessageBox.information(self, "保存成功", f"分享卡片已保存到:\n{file_path}")
            except Exception as e:
                QMessageBox.warning(self, "保存失败", f"保存图片时出错:\n{str(e)}")
    
    def show_share_history(self):
        """显示分享历史"""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QScrollArea, QWidget, QHBoxLayout, QPushButton
        from PyQt5.QtCore import Qt
        
        dialog = QDialog(self)
        dialog.setWindowTitle("分享历史")
        dialog.setMinimumSize(600, 500)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title_label = QLabel("📤 分享历史")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 20px;
                font-weight: bold;
                color: #2c3e50;
                padding-bottom: 10px;
                border-bottom: 2px solid #3498db;
            }
        """)
        title_label.setFont(self.genshin_font)
        layout.addWidget(title_label)
        
        # 加载分享历史
        share_history = load_share_history()
        
        if not share_history:
            empty_label = QLabel("还没有分享记录，快去分享喜欢的音乐吧！")
            empty_label.setStyleSheet("font-size: 14px; color: #7f8c8d; padding: 50px;")
            empty_label.setFont(self.genshin_font)
            empty_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(empty_label)
        else:
            # 滚动区域
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("""
                QScrollArea {
                    border: 1px solid #e0e0e0;
                    border-radius: 8px;
                    background: white;
                }
            """)
            
            content_widget = QWidget()
            content_layout = QVBoxLayout(content_widget)
            content_layout.setSpacing(10)
            content_layout.setContentsMargins(15, 15, 15, 15)
            
            # 平台图标映射
            platform_icons = {
                'wechat': '💬 微信',
                'qq': '🐧 QQ',
                'weibo': '📢 微博',
                'twitter': '🐦 Twitter',
                'facebook': '📘 Facebook',
                'copy': '📋 复制链接'
            }
            
            for record in share_history[:50]:  # 只显示最近50条
                # 创建记录卡片
                record_widget = QWidget()
                record_widget.setStyleSheet("""
                    QWidget {
                        background: #f8f9fa;
                        border-radius: 8px;
                        padding: 5px;
                    }
                """)
                record_layout = QHBoxLayout(record_widget)
                record_layout.setSpacing(10)
                
                # 平台
                platform = record.get('platform', 'unknown')
                platform_text = platform_icons.get(platform, platform)
                platform_label = QLabel(platform_text)
                platform_label.setStyleSheet("font-size: 12px; color: #3498db; font-weight: bold;")
                platform_label.setFont(self.genshin_font)
                record_layout.addWidget(platform_label)
                
                # 标题
                title = record.get('title', '未知标题')
                if len(title) > 30:
                    title = title[:30] + "..."
                title_label = QLabel(title)
                title_label.setStyleSheet("font-size: 13px; color: #2c3e50;")
                title_label.setFont(self.genshin_font)
                record_layout.addWidget(title_label, stretch=1)
                
                # 时间
                time_str = record.get('share_time', '')
                time_label = QLabel(time_str)
                time_label.setStyleSheet("font-size: 11px; color: #95a5a6;")
                time_label.setFont(self.genshin_font)
                record_layout.addWidget(time_label)
                
                content_layout.addWidget(record_widget)
            
            content_layout.addStretch()
            scroll.setWidget(content_widget)
            layout.addWidget(scroll)
        
        # 关闭按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_btn = QPushButton("关闭")
        close_btn.setFont(self.genshin_font)
        close_btn.setFixedHeight(40)
        close_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 30px;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                background: #3498db;
                color: white;
            }
            QPushButton:hover {
                background: #2980b9;
            }
        """)
        close_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(close_btn)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        dialog.exec_()
    
    def show_social_feed(self):
        """显示社交动态页面 - 使用真实社区数据"""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QScrollArea, QWidget, QHBoxLayout, QPushButton, QTabWidget
        
        dialog = QDialog(self)
        dialog.setWindowTitle("社区动态")
        dialog.setMinimumSize(700, 600)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title_label = QLabel("🌟 社区动态")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 20px;
                font-weight: bold;
                color: #2c3e50;
            }
        """)
        title_label.setFont(self.genshin_font)
        layout.addWidget(title_label)
        
        # 标签页
        tabs = QTabWidget()
        tabs.setFont(self.genshin_font)
        
        # 社区评论标签页
        community_tab = QWidget()
        community_layout = QVBoxLayout(community_tab)
        
        # 统计信息
        stats_result = self.community_system.get_stats()
        if stats_result.get("success"):
            stats = stats_result.get("stats", {})
            stats_text = f"总评论: {stats.get('total_comments', 0)} | 今日评论: {stats.get('today_comments', 0)} | 活跃用户: {stats.get('active_guests', 0)}"
            stats_label = QLabel(stats_text)
            stats_label.setStyleSheet("color: #7f8c8d; font-size: 12px; padding: 8px; background: #f8f9fa; border-radius: 4px;")
            stats_label.setFont(self.genshin_font)
            community_layout.addWidget(stats_label)
        
        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                background: white;
            }
        """)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(15)
        content_layout.setContentsMargins(15, 15, 15, 15)
        
        # 获取真实社区评论
        comments_result = self.community_system.get_comments(include_guest=True, per_page=50)
        
        if comments_result.get("success") and comments_result.get("comments"):
            comments = comments_result["comments"]
            
            for comment in comments:
                comment_widget = self._create_comment_widget(comment)
                content_layout.addWidget(comment_widget)
        else:
            # 没有评论时显示提示
            empty_label = QLabel("📭 暂无社区动态，快来分享你的音乐发现吧！")
            empty_label.setStyleSheet("color: #95a5a6; font-size: 14px; padding: 20px;")
            empty_label.setFont(self.genshin_font)
            empty_label.setAlignment(Qt.AlignCenter)
            content_layout.addWidget(empty_label)
        
        content_layout.addStretch()
        scroll.setWidget(content_widget)
        community_layout.addWidget(scroll)
        
        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新动态")
        refresh_btn.setFont(self.genshin_font)
        refresh_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 20px;
                border: 2px solid #3498db;
                border-radius: 6px;
                font-size: 14px;
                background: #3498db;
                color: white;
            }
            QPushButton:hover {
                background: #2980b9;
            }
        """)
        refresh_btn.clicked.connect(lambda: self._refresh_community_feed(scroll, content_layout))
        community_layout.addWidget(refresh_btn)
        
        # 发表评论按钮
        post_btn = QPushButton("✏️ 发表评论")
        post_btn.setFont(self.genshin_font)
        post_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 20px;
                border: 2px solid #27ae60;
                border-radius: 6px;
                font-size: 14px;
                background: #27ae60;
                color: white;
            }
            QPushButton:hover {
                background: #219150;
            }
        """)
        post_btn.clicked.connect(lambda: self._show_post_comment_dialog())
        community_layout.addWidget(post_btn)
        
        tabs.addTab(community_tab, "社区评论")
        
        # 热门分享标签页
        hot_shares_tab = QWidget()
        hot_shares_layout = QVBoxLayout(hot_shares_tab)
        
        hot_scroll = QScrollArea()
        hot_scroll.setWidgetResizable(True)
        hot_scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                background: white;
            }
        """)
        
        hot_content_widget = QWidget()
        hot_content_layout = QVBoxLayout(hot_content_widget)
        hot_content_layout.setSpacing(15)
        hot_content_layout.setContentsMargins(15, 15, 15, 15)
        
        # 获取热门分享
        hot_shares = self.share_service.get_hot_shares(limit=20)
        
        if hot_shares:
            for share in hot_shares:
                share_widget = self._create_share_widget(share)
                hot_content_layout.addWidget(share_widget)
        else:
            empty_hot_label = QLabel("📭 暂无热门分享")
            empty_hot_label.setStyleSheet("color: #95a5a6; font-size: 14px; padding: 20px;")
            empty_hot_label.setFont(self.genshin_font)
            empty_hot_label.setAlignment(Qt.AlignCenter)
            hot_content_layout.addWidget(empty_hot_label)
        
        hot_content_layout.addStretch()
        hot_scroll.setWidget(hot_content_widget)
        hot_shares_layout.addWidget(hot_scroll)
        
        tabs.addTab(hot_shares_tab, "热门分享")
        
        layout.addWidget(tabs)
        
        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.setFont(self.genshin_font)
        close_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 20px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                font-size: 14px;
                background: #f9f9f9;
                color: #2c3e50;
            }
            QPushButton:hover {
                background: #e9ecef;
            }
        """)
        close_btn.clicked.connect(dialog.reject)
        layout.addWidget(close_btn, alignment=Qt.AlignCenter)
        
        dialog.exec_()
    
    def _create_comment_widget(self, comment):
        """创建评论组件"""
        from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton
        
        widget = QWidget()
        widget.setStyleSheet("""
            QWidget {
                background: #f8f9fa;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        
        main_layout = QVBoxLayout(widget)
        main_layout.setSpacing(8)
        
        # 顶部信息行
        top_layout = QHBoxLayout()
        
        # 用户信息
        user_info = QLabel(f"👤 {comment.get('nickname', '匿名用户')}")
        user_info.setStyleSheet("font-weight: bold; color: #2c3e50;")
        user_info.setFont(self.genshin_font)
        top_layout.addWidget(user_info)
        
        top_layout.addStretch()
        
        # 时间
        time_label = QLabel(comment.get('created_at', ''))
        time_label.setStyleSheet("color: #95a5a6; font-size: 11px;")
        time_label.setFont(self.genshin_font)
        top_layout.addWidget(time_label)
        
        main_layout.addLayout(top_layout)
        
        # 评论内容
        content_label = QLabel(comment.get('content', ''))
        content_label.setWordWrap(True)
        content_label.setStyleSheet("color: #34495e; padding: 4px;")
        content_label.setFont(self.genshin_font)
        main_layout.addWidget(content_label)
        
        # 底部操作行
        bottom_layout = QHBoxLayout()
        
        # 点赞按钮
        like_count = comment.get('likes', 0)
        like_btn = QPushButton(f"👍 {like_count}")
        like_btn.setStyleSheet("""
            QPushButton {
                border: none;
                background: transparent;
                color: #7f8c8d;
                font-size: 12px;
                padding: 4px 8px;
            }
            QPushButton:hover {
                color: #3498db;
            }
        """)
        like_btn.setFont(self.genshin_font)
        like_btn.clicked.connect(lambda: self._like_comment(comment.get('id'), like_btn))
        bottom_layout.addWidget(like_btn)
        
        bottom_layout.addStretch()
        
        # 游客标识
        if comment.get('is_guest'):
            guest_label = QLabel("🏷️ 游客")
            guest_label.setStyleSheet("color: #95a5a6; font-size: 10px; padding: 2px 6px; background: #ecf0f1; border-radius: 3px;")
            guest_label.setFont(self.genshin_font)
            bottom_layout.addWidget(guest_label)
        
        main_layout.addLayout(bottom_layout)
        
        return widget
    
    def _create_share_widget(self, share):
        """创建分享组件"""
        from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton
        
        widget = QWidget()
        widget.setStyleSheet("""
            QWidget {
                background: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        
        main_layout = QVBoxLayout(widget)
        main_layout.setSpacing(8)
        
        # 标题
        title_label = QLabel(f"🎵 {share.get('title', '未知标题')}")
        title_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        title_label.setFont(self.genshin_font)
        main_layout.addWidget(title_label)
        
        # 信息行
        info_layout = QHBoxLayout()
        
        # 分享时间
        time_label = QLabel(f"⏰ {share.get('share_time', '')}")
        time_label.setStyleSheet("color: #95a5a6; font-size: 11px;")
        time_label.setFont(self.genshin_font)
        info_layout.addWidget(time_label)
        
        info_layout.addStretch()
        
        # 查看次数
        view_count = share.get('view_count', 0)
        view_label = QLabel(f"👁️ {view_count} 次查看")
        view_label.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        view_label.setFont(self.genshin_font)
        info_layout.addWidget(view_label)
        
        main_layout.addLayout(info_layout)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        
        # 打开链接按钮
        open_btn = QPushButton("🔗 打开链接")
        open_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
                border: 1px solid #3498db;
                border-radius: 4px;
                font-size: 12px;
                background: white;
                color: #3498db;
            }
            QPushButton:hover {
                background: #3498db;
                color: white;
            }
        """)
        open_btn.setFont(self.genshin_font)
        open_btn.clicked.connect(lambda: self._open_share_link(share.get('bvid')))
        btn_layout.addWidget(open_btn)
        
        btn_layout.addStretch()
        
        # 增加查看次数
        view_btn = QPushButton("👁️ 查看详情")
        view_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
                border: 1px solid #95a5a6;
                border-radius: 4px;
                font-size: 12px;
                background: white;
                color: #7f8c8d;
            }
            QPushButton:hover {
                background: #95a5a6;
                color: white;
            }
        """)
        view_btn.setFont(self.genshin_font)
        view_btn.clicked.connect(lambda: self._increment_share_view(share.get('id'), view_label))
        btn_layout.addWidget(view_btn)
        
        main_layout.addLayout(btn_layout)
        
        return widget
    
    def _refresh_community_feed(self, scroll, content_layout):
        """刷新社区动态"""
        # 清空现有内容
        while content_layout.count():
            child = content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # 重新加载评论
        comments_result = self.community_system.get_comments(include_guest=True, per_page=50)
        
        if comments_result.get("success") and comments_result.get("comments"):
            comments = comments_result["comments"]
            
            for comment in comments:
                comment_widget = self._create_comment_widget(comment)
                content_layout.addWidget(comment_widget)
        else:
            empty_label = QLabel("📭 暂无社区动态")
            empty_label.setStyleSheet("color: #95a5a6; font-size: 14px; padding: 20px;")
            empty_label.setFont(self.genshin_font)
            empty_label.setAlignment(Qt.AlignCenter)
            content_layout.addWidget(empty_label)
        
        content_layout.addStretch()
    
    def _like_comment(self, comment_id, like_btn):
        """点赞评论"""
        result = self.community_system.like_comment(comment_id)
        if result.get("success"):
            new_likes = result.get("likes", 0)
            like_btn.setText(f"👍 {new_likes}")
            like_btn.setStyleSheet("""
                QPushButton {
                    border: none;
                    background: transparent;
                    color: #e74c3c;
                    font-size: 12px;
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    color: #c0392b;
                }
            """)
    
    def _open_share_link(self, bvid):
        """打开分享链接"""
        if bvid:
            url = f"https://www.bilibili.com/video/{bvid}"
            webbrowser.open(url)
    
    def _increment_share_view(self, share_id, view_label):
        """增加分享查看次数"""
        success = self.share_service.system.increment_view_count(share_id)
        if success:
            current_text = view_label.text()
            import re
            match = re.search(r'(\d+)', current_text)
            if match:
                new_count = int(match.group(1)) + 1
                view_label.setText(f"👁️ {new_count} 次查看")
    
    def _create_user_share_widget(self, share):
        """创建用户分享组件"""
        from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton
        
        widget = QWidget()
        widget.setStyleSheet("""
            QWidget {
                background: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        
        main_layout = QVBoxLayout(widget)
        main_layout.setSpacing(6)
        
        # 标题和分享类型
        top_layout = QHBoxLayout()
        
        title_label = QLabel(f"🎵 {share.get('title', '未知标题')}")
        title_label.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 13px;")
        title_label.setFont(self.genshin_font)
        top_layout.addWidget(title_label)
        
        top_layout.addStretch()
        
        # 分享类型标签
        share_type = share.get('share_type', 'link')
        type_label = QLabel(f"📤 {share_type}")
        type_label.setStyleSheet("color: #3498db; font-size: 10px; padding: 2px 6px; background: #e8f4f8; border-radius: 3px;")
        type_label.setFont(self.genshin_font)
        top_layout.addWidget(type_label)
        
        main_layout.addLayout(top_layout)
        
        # 信息行
        info_layout = QHBoxLayout()
        
        # 分享时间
        time_label = QLabel(f"⏰ {share.get('share_time', '')}")
        time_label.setStyleSheet("color: #95a5a6; font-size: 10px;")
        time_label.setFont(self.genshin_font)
        info_layout.addWidget(time_label)
        
        info_layout.addStretch()
        
        # 查看次数
        view_count = share.get('view_count', 0)
        view_label = QLabel(f"👁️ {view_count}")
        view_label.setStyleSheet("color: #7f8c8d; font-size: 10px;")
        view_label.setFont(self.genshin_font)
        info_layout.addWidget(view_label)
        
        main_layout.addLayout(info_layout)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        
        # 打开链接按钮
        open_btn = QPushButton("🔗 打开")
        open_btn.setStyleSheet("""
            QPushButton {
                padding: 4px 10px;
                border: 1px solid #3498db;
                border-radius: 3px;
                font-size: 11px;
                background: white;
                color: #3498db;
            }
            QPushButton:hover {
                background: #3498db;
                color: white;
            }
        """)
        open_btn.setFont(self.genshin_font)
        open_btn.clicked.connect(lambda: self._open_share_link(share.get('bvid')))
        btn_layout.addWidget(open_btn)
        
        # 再次分享按钮
        reshare_btn = QPushButton("🔄 再分享")
        reshare_btn.setStyleSheet("""
            QPushButton {
                padding: 4px 10px;
                border: 1px solid #27ae60;
                border-radius: 3px;
                font-size: 11px;
                background: white;
                color: #27ae60;
            }
            QPushButton:hover {
                background: #27ae60;
                color: white;
            }
        """)
        reshare_btn.setFont(self.genshin_font)
        reshare_btn.clicked.connect(lambda: self._reshare_video(share))
        btn_layout.addWidget(reshare_btn)
        
        btn_layout.addStretch()
        
        # 删除分享按钮
        delete_btn = QPushButton("🗑️ 删除")
        delete_btn.setStyleSheet("""
            QPushButton {
                padding: 4px 10px;
                border: 1px solid #e74c3c;
                border-radius: 3px;
                font-size: 11px;
                background: white;
                color: #e74c3c;
            }
            QPushButton:hover {
                background: #e74c3c;
                color: white;
            }
        """)
        delete_btn.setFont(self.genshin_font)
        delete_btn.clicked.connect(lambda: self._delete_share(share.get('id'), widget))
        btn_layout.addWidget(delete_btn)
        
        main_layout.addLayout(btn_layout)
        
        return widget
    
    def _reshare_video(self, share):
        """再次分享视频"""
        bvid = share.get('bvid')
        title = share.get('title', '未知标题')
        
        # 获取视频信息
        video_info = {
            'bvid': bvid,
            'title': title
        }
        
        # 打开分享对话框
        self.share_video(video_info)
    
    def _delete_share(self, share_id, widget):
        """删除分享记录"""
        reply = QMessageBox.question(
            self, 
            "确认删除", 
            "确定要删除这条分享记录吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                # 从分享数据中删除
                shares = self.share_service.system._load_shares()
                shares = [s for s in shares if s.get('id') != share_id]
                self.share_service.system._save_shares(shares)
                
                # 从UI中移除
                widget.deleteLater()
                
                QMessageBox.information(self, "成功", "分享记录已删除")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"删除失败: {str(e)}")
    
    def show_user_profile(self):
        """显示用户个人资料"""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QTabWidget, QWidget, QHBoxLayout, QPushButton
        
        dialog = QDialog(self)
        dialog.setWindowTitle("个人资料")
        dialog.setFixedSize(600, 500)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(25)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # 用户信息
        user_info = QWidget()
        user_info.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #667eea, stop:1 #764ba2);
                border-radius: 12px;
                padding: 25px;
            }
        """)
        user_layout = QHBoxLayout(user_info)
        user_layout.setSpacing(25)
        
        # 头像
        avatar = QLabel("👤")
        avatar.setStyleSheet("font-size: 64px;")
        user_layout.addWidget(avatar)
        
        # 用户名和统计
        info_layout = QVBoxLayout()
        info_layout.setSpacing(12)
        username = QLabel(self.current_user if self.current_user else '未登录')
        username.setStyleSheet("font-size: 24px; font-weight: bold; color: white;")
        username.setFont(self.genshin_font)
        info_layout.addWidget(username)
        
        stats = QLabel(f"收藏: {len(self.favorites)} | 播放列表: {len(self.playlists)} | 排除: {len(self.excluded)}")
        stats.setStyleSheet("color: rgba(255,255,255,0.9); font-size: 14px;")
        stats.setFont(self.genshin_font)
        info_layout.addWidget(stats)
        
        # 如果未登录，添加登录按钮
        if not self.current_user or self.current_user == "guest":
            login_btn = QPushButton("🔐 登录")
            login_btn.setFont(self.genshin_font)
            login_btn.setMinimumHeight(45)
            login_btn.setStyleSheet("""
                QPushButton {
                    padding: 12px 24px;
                    border: 2px solid rgba(255,255,255,0.6);
                    border-radius: 8px;
                    font-size: 14px;
                    font-weight: bold;
                    background: rgba(255,255,255,0.15);
                    color: white;
                }
                QPushButton:hover {
                    background: rgba(255,255,255,0.25);
                }
            """)
            login_btn.clicked.connect(lambda: (dialog.close(), self.show_login_dialog()))
            info_layout.addWidget(login_btn)
            
            # 添加注册按钮
            register_btn = QPushButton("📝 注册")
            register_btn.setFont(self.genshin_font)
            register_btn.setMinimumHeight(45)
            register_btn.setStyleSheet("""
                QPushButton {
                    padding: 12px 24px;
                    border: 2px solid rgba(46, 204, 113, 0.9);
                    border-radius: 8px;
                    font-size: 14px;
                    font-weight: bold;
                    background: rgba(46, 204, 113, 0.25);
                    color: white;
                }
                QPushButton:hover {
                    background: rgba(46, 204, 113, 0.35);
                }
            """)
            register_btn.clicked.connect(lambda: (dialog.close(), self.show_register_dialog()))
            info_layout.addWidget(register_btn)
        else:
            # 如果已登录，添加退出登录按钮
            logout_btn = QPushButton("🚪 退出登录")
            logout_btn.setFont(self.genshin_font)
            logout_btn.setMinimumHeight(45)
            logout_btn.setStyleSheet("""
                QPushButton {
                    padding: 12px 24px;
                    border: 2px solid rgba(231, 76, 60, 0.8);
                    border-radius: 8px;
                    font-size: 14px;
                    font-weight: bold;
                    background: rgba(231, 76, 60, 0.2);
                    color: white;
                }
                QPushButton:hover {
                    background: rgba(231, 76, 60, 0.3);
                }
            """)
            logout_btn.clicked.connect(lambda: (dialog.close(), self.logout()))
            info_layout.addWidget(logout_btn)
        
        user_layout.addLayout(info_layout)
        user_layout.addStretch()
        layout.addWidget(user_info)
        
        # 标签页
        tabs = QTabWidget()
        tabs.setFont(self.genshin_font)
        
        # 我的动态
        activity_tab = QWidget()
        activity_layout = QVBoxLayout(activity_tab)
        activity_label = QLabel("最近活动将显示在这里")
        activity_label.setStyleSheet("color: #7f8c8d;")
        activity_label.setFont(self.genshin_font)
        activity_label.setAlignment(Qt.AlignCenter)
        activity_layout.addWidget(activity_label)
        tabs.addTab(activity_tab, "我的动态")
        
        # 我的分享
        share_tab = QWidget()
        share_layout = QVBoxLayout(share_tab)
        
        # 滚动区域
        share_scroll = QScrollArea()
        share_scroll.setWidgetResizable(True)
        share_scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                background: white;
            }
        """)
        
        share_content_widget = QWidget()
        share_content_layout = QVBoxLayout(share_content_widget)
        share_content_layout.setSpacing(10)
        share_content_layout.setContentsMargins(10, 10, 10, 10)
        
        # 获取用户的分享历史
        user_shares = self.share_service.get_user_shares(limit=50)
        
        if user_shares:
            for share in user_shares:
                share_item_widget = self._create_user_share_widget(share)
                share_content_layout.addWidget(share_item_widget)
        else:
            empty_share_label = QLabel("📭 暂无分享记录，快去分享你喜欢的音乐吧！")
            empty_share_label.setStyleSheet("color: #95a5a6; font-size: 13px; padding: 15px;")
            empty_share_label.setFont(self.genshin_font)
            empty_share_label.setAlignment(Qt.AlignCenter)
            share_content_layout.addWidget(empty_share_label)
        
        share_content_layout.addStretch()
        share_scroll.setWidget(share_content_widget)
        share_layout.addWidget(share_scroll)
        
        tabs.addTab(share_tab, "我的分享")
        
        layout.addWidget(tabs)
        
        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.setFont(self.genshin_font)
        close_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 20px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                font-size: 14px;
                background: #f9f9f9;
                color: #2c3e50;
            }
            QPushButton:hover {
                background: #e9ecef;
            }
        """)
        close_btn.clicked.connect(dialog.reject)
        layout.addWidget(close_btn, alignment=Qt.AlignCenter)
        
        dialog.exec_()
    
    def refresh_recommendations(self):
        """刷新推荐内容 - 点击刷新时重置浏览记录"""
        try:
            # 检查并修复播放量为空的视频（在后台执行）
            threading.Thread(
                target=self._check_empty_playcount_background,
                daemon=True
            ).start()

            # 检查是否需要重置浏览记录
            self._check_reset_viewed_on_refresh()

            # 尝试使用预加载的数据
            if self.use_preloaded_or_refresh():
                # 预加载数据已使用，显示快速刷新提示
                if hasattr(self, 'statusBar'):
                    self.statusBar().showMessage("已加载预缓存数据", 2000)
                return

            # 没有预加载数据，先尝试从本地获取
            print("没有预加载数据，尝试从本地数据库获取...")
            self.load_recommendations(force_refresh=False)
        except Exception as e:
            logger.error(f"刷新推荐失败: {e}")
            # 本地获取失败，显示错误但不强制弹窗
            if hasattr(self, 'statusBar'):
                self.statusBar().showMessage(f"刷新失败: {str(e)}", 5000)
            else:
                QMessageBox.warning(self, "错误", f"刷新推荐失败。\n错误信息: {str(e)}")

    def _check_empty_playcount_background(self):
        """后台检查播放量为空的视频"""
        try:
            empty_count, removed_count = self.recommend_service.check_and_fix_empty_playcount(auto_fix=True)
            if empty_count > 0:
                print(f"后台检测到 {empty_count} 个播放量为空的视频，已移除 {removed_count} 个")
                # 触发后台补充
                self.recommend_service.check_and_fetch_if_needed(background=True)
        except Exception as e:
            print(f"后台检查播放量为空失败: {e}")
    
    def _check_reset_viewed_on_refresh(self):
        """刷新时检查是否需要重置浏览记录"""
        try:
            from utils.data_manager import clear_viewed_history
            from datetime import datetime
            
            # 检查是否启用了刷新时重置
            if not self.settings.get('reset_viewed_on_refresh', True):
                return
            
            # 获取上次重置时间
            last_reset_str = self.settings.get('last_viewed_reset')
            reset_interval_hours = self.settings.get('viewed_reset_interval', 24)  # 默认24小时
            
            should_reset = False
            
            if last_reset_str:
                try:
                    last_reset = datetime.strptime(last_reset_str, '%Y-%m-%d %H:%M:%S')
                    time_diff = datetime.now() - last_reset
                    # 如果距离上次重置超过设定的时间间隔，则重置
                    if time_diff.total_seconds() > reset_interval_hours * 3600:
                        should_reset = True
                        print(f"距离上次重置已超过 {reset_interval_hours} 小时，重置浏览记录...")
                except:
                    should_reset = True
            else:
                should_reset = True
            
            if should_reset:
                clear_viewed_history()
                self.settings['last_viewed_reset'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                save_settings(self.settings)
                print("浏览记录已重置")
                
        except Exception as e:
            print(f"刷新时重置浏览记录失败: {e}")
    
    def show_favorites(self):
        """显示收藏列表"""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QListWidget, QPushButton, QHBoxLayout, QMessageBox
        
        dialog = QDialog(self)
        dialog.setWindowTitle("收藏列表")
        dialog.setFixedSize(600, 400)
        
        layout = QVBoxLayout(dialog)
        
        # 收藏列表
        favorites_list = QListWidget()
        for item in self.favorites:
            favorites_list.addItem(f"{item['title']} ({item['bvid']})")
        layout.addWidget(favorites_list)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        # 打开视频按钮
        open_btn = QPushButton("在浏览器中打开")
        open_btn.setFont(self.genshin_font)
        open_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
                background: #3498db;
                color: white;
            }
            QPushButton:hover {
                background: #2980b9;
            }
        """)
        open_btn.clicked.connect(lambda: self.open_favorite_video(favorites_list))
        button_layout.addWidget(open_btn)
        
        # 移除按钮
        remove_btn = QPushButton("移除")
        remove_btn.setFont(self.genshin_font)
        remove_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
                background: #f9f9f9;
                color: #2c3e50;
            }
            QPushButton:hover {
                background: #e9ecef;
            }
        """)
        remove_btn.clicked.connect(lambda: self.remove_favorite(favorites_list))
        button_layout.addWidget(remove_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        dialog.exec_()
    
    def open_favorite_video(self, favorites_list):
        """在浏览器中打开收藏的视频"""
        current_item = favorites_list.currentItem()
        if current_item:
            item_text = current_item.text()
            bvid = item_text.split('(')[-1].strip(')')
            url = f"https://www.bilibili.com/video/{bvid}"
            webbrowser.open(url)
    
    def remove_favorite(self, favorites_list):
        """移除收藏"""
        current_item = favorites_list.currentItem()
        if current_item:
            item_text = current_item.text()
            bvid = item_text.split('(')[-1].strip(')')
            
            # 从收藏列表中移除
            self.favorites = [item for item in self.favorites if item['bvid'] != bvid]
            self.save_favorites_and_excluded()
            
            # 更新列表
            favorites_list.takeItem(favorites_list.currentRow())
            QMessageBox.information(self, "成功", "已从收藏列表中移除")
    
    def show_excluded(self):
        """显示排除列表"""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QListWidget, QPushButton, QHBoxLayout, QMessageBox
        
        dialog = QDialog(self)
        dialog.setWindowTitle("排除列表")
        dialog.setFixedSize(600, 400)
        
        layout = QVBoxLayout(dialog)
        
        # 排除列表
        excluded_list = QListWidget()
        for item in self.excluded:
            excluded_list.addItem(f"{item['title']} ({item['bvid']})")
        layout.addWidget(excluded_list)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        # 打开视频按钮
        open_btn = QPushButton("在浏览器中打开")
        open_btn.setFont(self.genshin_font)
        open_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
                background: #3498db;
                color: white;
            }
            QPushButton:hover {
                background: #2980b9;
            }
        """)
        open_btn.clicked.connect(lambda: self.open_excluded_video(excluded_list))
        button_layout.addWidget(open_btn)
        
        # 移除按钮
        remove_btn = QPushButton("移除")
        remove_btn.setFont(self.genshin_font)
        remove_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
                background: #f9f9f9;
                color: #2c3e50;
            }
            QPushButton:hover {
                background: #e9ecef;
            }
        """)
        remove_btn.clicked.connect(lambda: self.remove_excluded(excluded_list))
        button_layout.addWidget(remove_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        dialog.exec_()
    
    def open_excluded_video(self, excluded_list):
        """在浏览器中打开排除的视频"""
        current_item = excluded_list.currentItem()
        if current_item:
            item_text = current_item.text()
            bvid = item_text.split('(')[-1].strip(')')
            url = f"https://www.bilibili.com/video/{bvid}"
            webbrowser.open(url)
    
    def remove_excluded(self, excluded_list):
        """移除排除"""
        current_item = excluded_list.currentItem()
        if current_item:
            item_text = current_item.text()
            bvid = item_text.split('(')[-1].strip(')')
            
            # 从排除列表中移除
            self.excluded = [item for item in self.excluded if item['bvid'] != bvid]
            self.save_favorites_and_excluded()
            
            # 更新列表
            excluded_list.takeItem(excluded_list.currentRow())
            QMessageBox.information(self, "成功", "已从排除列表中移除")
    
    def show_settings(self):
        """显示设置对话框"""
        dialog = SettingsDialog(self)
        dialog.exec_()
    
    def search_music(self):
        """搜索音乐"""
        keyword = self.search_input.text().strip()
        if keyword:
            try:
                from utils.api import search_bilibili_videos
                results = search_bilibili_videos(keyword, page=1)
                self.display_recommendations(results)
            except Exception as e:
                logger.error(f"搜索失败: {e}")
                QMessageBox.warning(self, "错误", f"搜索失败: {str(e)}")
    
    def load_favorites_and_excluded(self):
        """加载收藏和排除列表"""
        try:
            self.favorites, self.excluded = load_favorites_and_excluded()
        except Exception as e:
            logger.error(f"加载收藏和排除列表失败: {e}")
            self.favorites = []
            self.excluded = []
    
    def save_favorites_and_excluded(self):
        """保存收藏和排除列表"""
        try:
            save_favorites_and_excluded(self.favorites, self.excluded)
        except Exception as e:
            logger.error(f"保存收藏和排除列表失败: {e}")
    
    def load_playlists(self):
        """加载播放列表"""
        try:
            self.playlists = load_playlists()
        except Exception as e:
            logger.error(f"加载播放列表失败: {e}")
            self.playlists = []
    
    def save_playlists(self):
        """保存播放列表"""
        try:
            save_playlists(self.playlists)
        except Exception as e:
            logger.error(f"保存播放列表失败: {e}")

if __name__ == "__main__":
    # 在创建 QApplication 之前设置 WebEngine 需要的属性
    from PyQt5.QtCore import Qt, QCoreApplication
    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
