"""
视频下载和本地播放模块
支持使用 yt-dlp 下载 B站视频并本地播放
"""
import os
import re
import subprocess
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QProgressBar, QTextEdit, QMessageBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QMenu, QAction, QComboBox, QLineEdit, QFrame
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QUrl, QSize
from PyQt5.QtGui import QDesktopServices, QFont, QColor

# 视频缓存目录
VIDEO_CACHE_DIR = Path(__file__).parent.parent / "data" / "video_cache"
VIDEO_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# 缓存索引文件
CACHE_INDEX_FILE = VIDEO_CACHE_DIR / "cache_index.json"


def load_cache_index() -> Dict:
    """加载缓存索引"""
    if CACHE_INDEX_FILE.exists():
        try:
            with open(CACHE_INDEX_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {}


def save_cache_index(index: Dict):
    """保存缓存索引"""
    try:
        with open(CACHE_INDEX_FILE, 'w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存缓存索引失败: {e}")


def add_to_cache_index(bvid: str, title: str, file_path: str, up_name: str = "", pubdate: str = ""):
    """添加视频到缓存索引"""
    index = load_cache_index()
    index[bvid] = {
        'title': title,
        'file_path': file_path,
        'up_name': up_name,
        'pubdate': pubdate,
        'download_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'size': os.path.getsize(file_path) if os.path.exists(file_path) else 0
    }
    save_cache_index(index)


def remove_from_cache_index(bvid: str):
    """从缓存索引中移除视频"""
    index = load_cache_index()
    if bvid in index:
        # 删除文件
        file_path = index[bvid].get('file_path', '')
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        del index[bvid]
        save_cache_index(index)
        return True
    return False


def get_cache_info() -> Dict:
    """获取缓存信息"""
    index = load_cache_index()
    total_size = 0
    video_count = 0
    
    for bvid, info in list(index.items()):
        file_path = info.get('file_path', '')
        if file_path and os.path.exists(file_path):
            size = os.path.getsize(file_path)
            total_size += size
            video_count += 1
            # 更新大小信息
            if info.get('size', 0) != size:
                info['size'] = size
        else:
            # 文件不存在，从索引中移除
            del index[bvid]
    
    if index != load_cache_index():
        save_cache_index(index)
    
    return {
        'count': video_count,
        'total_size_mb': total_size / (1024 * 1024),
        'videos': index
    }


class VideoDownloadThread(QThread):
    """视频下载线程"""
    progress_signal = pyqtSignal(str)  # 进度信息
    finished_signal = pyqtSignal(bool, str)  # 成功/失败, 文件路径或错误信息
    
    def __init__(self, bvid: str, output_path: str):
        super().__init__()
        self.bvid = bvid
        self.output_path = output_path
        self.process = None
        
    def run(self):
        try:
            url = f"https://www.bilibili.com/video/{self.bvid}"
            
            # 使用 yt-dlp 下载视频
            cmd = [
                "yt-dlp",
                "-f", "bv*+ba/b",
                "--merge-output-format", "mp4",
                "-o", self.output_path,
                "--no-warnings",
                "--progress",
                "--newline",
                "--no-check-certificates",
                "--postprocessor-args", "-c:v copy -c:a aac",
                url
            ]
            
            self.progress_signal.emit(f"🌐 开始下载: {url}")
            
            # 执行下载
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                encoding='utf-8',
                errors='ignore'
            )
            
            # 实时读取输出
            for line in self.process.stdout:
                line = line.strip()
                if line:
                    # 简化输出，只显示关键信息
                    if any(keyword in line for keyword in ['download', 'Destination', 'Merger', 'Deleting', '100%']):
                        self.progress_signal.emit(line)
            
            # 等待进程结束
            return_code = self.process.wait()
            
            if return_code == 0 and os.path.exists(self.output_path):
                file_size = os.path.getsize(self.output_path) / (1024 * 1024)  # MB
                self.progress_signal.emit(f"✅ 下载完成: {file_size:.2f} MB")
                self.finished_signal.emit(True, self.output_path)
            else:
                # 下载失败，返回特殊错误码让上层处理备用方案
                self.finished_signal.emit(False, f"DOWNLOAD_FAILED:{return_code}")
                
        except Exception as e:
            self.finished_signal.emit(False, f"下载出错: {str(e)}")
    
    def stop(self):
        """停止下载"""
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except:
                self.process.kill()


class VideoDownloadDialog(QDialog):
    """视频下载对话框 - 美化版"""
    
    def __init__(self, bvid: str, title: str, up_name: str = "", pubdate: str = "", parent=None):
        super().__init__(parent)
        self.bvid = bvid
        self.title = title
        self.up_name = up_name
        self.pubdate = pubdate
        self.download_thread = None
        self.output_path = None
        
        # 获取系统主题设置
        self.display_mode = 'light'
        if parent and hasattr(parent, 'settings'):
            self.display_mode = parent.settings.get('display_mode', 'light')
        
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("📥 视频下载")
        self.setFixedSize(580, 420)
        
        # 根据主题设置样式
        if self.display_mode == 'dark':
            self.setStyleSheet("""
                QDialog {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #1a1a2e, stop:1 #16213e);
                    border: 2px solid #0f3460;
                    border-radius: 12px;
                }
                QLabel {
                    color: #eaeaea;
                    font-family: 'Microsoft YaHei', 'SimHei', sans-serif;
                }
                QTextEdit {
                    background: #0f0f1a;
                    border: 1px solid #2d3561;
                    border-radius: 8px;
                    color: #a0d2eb;
                    font-family: 'Consolas', 'Monaco', monospace;
                    font-size: 11px;
                    padding: 8px;
                }
                QProgressBar {
                    border: 2px solid #2d3561;
                    border-radius: 6px;
                    text-align: center;
                    color: white;
                    font-weight: bold;
                    background: #0f0f1a;
                }
                QProgressBar::chunk {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #3498db, stop:1 #2ecc71);
                    border-radius: 4px;
                }
                QPushButton {
                    font-family: 'Microsoft YaHei', 'SimHei', sans-serif;
                    font-weight: bold;
                    border-radius: 8px;
                    padding: 10px 24px;
                }
            """)
        else:
            self.setStyleSheet("""
                QDialog {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #f5f7fa, stop:1 #c3cfe2);
                    border: 2px solid #b0c4de;
                    border-radius: 12px;
                }
                QLabel {
                    color: #2c3e50;
                    font-family: 'Microsoft YaHei', 'SimHei', sans-serif;
                }
                QTextEdit {
                    background: #ffffff;
                    border: 1px solid #d0d0d0;
                    border-radius: 8px;
                    color: #34495e;
                    font-family: 'Consolas', 'Monaco', monospace;
                    font-size: 11px;
                    padding: 8px;
                }
                QProgressBar {
                    border: 2px solid #d0d0d0;
                    border-radius: 6px;
                    text-align: center;
                    color: #2c3e50;
                    font-weight: bold;
                    background: #f9f9f9;
                }
                QProgressBar::chunk {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #3498db, stop:1 #2ecc71);
                    border-radius: 4px;
                }
                QPushButton {
                    font-family: 'Microsoft YaHei', 'SimHei', sans-serif;
                    font-weight: bold;
                    border-radius: 8px;
                    padding: 10px 24px;
                }
            """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题区域
        title_container = QLabel()
        title_container.setStyleSheet("""
            background: rgba(52, 152, 219, 0.15);
            border-radius: 10px;
            padding: 15px;
        """)
        title_container.setMinimumHeight(80)
        title_layout = QVBoxLayout(title_container)
        title_layout.setSpacing(5)
        
        # 主标题
        title_label = QLabel(f"🎬 {self.title[:60]}{'...' if len(self.title) > 60 else ''}")
        title_label.setStyleSheet("""
            font-size: 15px;
            font-weight: bold;
            color: #3498db;
        """)
        title_label.setWordWrap(True)
        title_layout.addWidget(title_label)
        
        # BV号
        bvid_label = QLabel(f"🔗 BV号: {self.bvid}")
        bvid_label.setStyleSheet("font-size: 12px; color: #7f8c8d;")
        title_layout.addWidget(bvid_label)
        
        layout.addWidget(title_container)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # 不确定模式
        self.progress_bar.setFixedHeight(30)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("⏳ 准备下载...")
        layout.addWidget(self.progress_bar)
        
        # 日志区域
        log_label = QLabel("📋 下载日志:")
        log_label.setStyleSheet("font-size: 12px; color: #95a5a6;")
        layout.addWidget(log_label)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFixedHeight(120)
        layout.addWidget(self.log_text)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)
        
        self.cancel_btn = QPushButton("❌ 取消")
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background: #e74c3c;
                color: white;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #c0392b;
            }
        """)
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.cancel_download)
        btn_layout.addWidget(self.cancel_btn)
        
        self.play_btn = QPushButton("▶️ 下载并播放")
        self.play_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #27ae60, stop:1 #219a52);
                color: white;
                font-size: 14px;
                min-width: 150px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2ecc71, stop:1 #27ae60);
            }
            QPushButton:disabled {
                background: #555;
                color: #888;
            }
        """)
        self.play_btn.setCursor(Qt.PointingHandCursor)
        self.play_btn.clicked.connect(self.start_download)
        btn_layout.addWidget(self.play_btn)
        
        layout.addLayout(btn_layout)
        
        # 自动开始下载
        self.start_download()
    
    def start_download(self):
        """开始下载"""
        self.play_btn.setEnabled(False)
        self.play_btn.setText("⏳ 下载中...")
        self.progress_bar.setFormat("⏳ 正在下载视频...")
        
        # 优化文件名格式：日期_BV号_UP主_标题
        # 清理标题中的特殊字符
        safe_title = re.sub(r'[\\/*?:"<>|]', "_", self.title)
        safe_title = safe_title[:40] if len(safe_title) > 40 else safe_title  # 限制长度
        
        # 处理UP主名称
        safe_up = re.sub(r'[\\/*?:"<>|]', "_", self.up_name) if self.up_name else "未知UP主"
        safe_up = safe_up[:20] if len(safe_up) > 20 else safe_up
        
        # 处理日期
        date_str = self.pubdate[:10] if self.pubdate and len(self.pubdate) >= 10 else datetime.now().strftime('%Y%m%d')
        
        # 构建文件名：[日期]_BV号_[UP主]_标题.mp4
        filename = f"[{date_str}]_{self.bvid}_[{safe_up}]_{safe_title}.mp4"
        output_file = VIDEO_CACHE_DIR / filename
        self.output_path = str(output_file)
        
        # 创建下载线程
        self.download_thread = VideoDownloadThread(self.bvid, self.output_path)
        self.download_thread.progress_signal.connect(self.update_progress)
        self.download_thread.finished_signal.connect(self.download_finished)
        self.download_thread.start()
    
    def update_progress(self, message: str):
        """更新进度"""
        self.log_text.append(message)
        # 滚动到底部
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
        # 更新进度条文本
        if "100%" in message:
            self.progress_bar.setFormat("✅ 下载完成，正在合并...")
        elif "Merger" in message:
            self.progress_bar.setFormat("🔧 正在合并音视频...")
    
    def download_finished(self, success: bool, result: str):
        """下载完成"""
        self.progress_bar.setRange(0, 100)
        
        if success:
            self.progress_bar.setValue(100)
            self.progress_bar.setFormat("✅ 下载完成！")
            
            # 添加到缓存索引（包含UP主和日期信息）
            add_to_cache_index(self.bvid, self.title, self.output_path, self.up_name, self.pubdate)
            
            self.play_btn.setText("▶️ 立即播放")
            self.play_btn.setEnabled(True)
            self.play_btn.clicked.disconnect()
            self.play_btn.clicked.connect(self.play_video)
            self.cancel_btn.setText("📁 打开文件夹")
            self.cancel_btn.clicked.disconnect()
            self.cancel_btn.clicked.connect(self.open_folder)
            
            # 自动播放
            self.play_video()
        else:
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("❌ 下载失败")
            
            # 检查是否是下载失败，提供备用播放方案
            if result.startswith("DOWNLOAD_FAILED:"):
                self.log_text.append("\n⚠️ 下载失败，尝试使用在线播放...")
                self._try_online_play()
            else:
                self.play_btn.setText("🔄 重试")
                self.play_btn.setEnabled(True)
                QMessageBox.warning(self, "下载失败", result)
    
    def _try_online_play(self):
        """尝试使用B站网页播放器在线播放"""
        try:
            from PyQt5.QtWidgets import QMessageBox
            
            # 询问用户是否使用在线播放
            reply = QMessageBox.question(
                self,
                "下载失败",
                "视频下载失败（可能是网络问题或视频受限）。\n\n"
                "是否使用浏览器在线播放？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            
            if reply == QMessageBox.Yes:
                # 使用B站网页播放器打开
                video_url = f"https://www.bilibili.com/video/{self.bvid}"
                QDesktopServices.openUrl(QUrl(video_url))
                self.log_text.append(f"✅ 已在浏览器打开: {video_url}")
                self.accept()  # 关闭对话框
            else:
                self.play_btn.setText("🌐 浏览器播放")
                self.play_btn.setEnabled(True)
                self.play_btn.clicked.disconnect()
                self.play_btn.clicked.connect(self._open_in_browser)
                
        except Exception as e:
            self.log_text.append(f"❌ 在线播放也失败了: {e}")
            self.play_btn.setText("🔄 重试下载")
            self.play_btn.setEnabled(True)
    
    def _open_in_browser(self):
        """在浏览器中打开视频"""
        video_url = f"https://www.bilibili.com/video/{self.bvid}"
        QDesktopServices.openUrl(QUrl(video_url))
        self.accept()
    
    def play_video(self):
        """播放视频"""
        if self.output_path and os.path.exists(self.output_path):
            # 使用系统默认播放器打开
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.output_path))
            self.accept()
    
    def open_folder(self):
        """打开缓存文件夹并选中下载的视频文件"""
        if self.output_path and os.path.exists(self.output_path):
            # 打开文件夹并选中文件（Windows 使用 explorer /select）
            import subprocess
            import platform
            if platform.system() == 'Windows':
                subprocess.run(['explorer', '/select,', os.path.normpath(self.output_path)])
            else:
                # macOS 和 Linux 只打开文件夹
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(VIDEO_CACHE_DIR)))
        else:
            # 文件不存在，只打开文件夹
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(VIDEO_CACHE_DIR)))
    
    def cancel_download(self):
        """取消下载"""
        if self.download_thread and self.download_thread.isRunning():
            self.download_thread.stop()
            self.download_thread.wait(3000)
        self.reject()
    
    def closeEvent(self, event):
        """关闭事件"""
        self.cancel_download()
        event.accept()


class CacheManagerDialog(QDialog):
    """缓存管理对话框 - 增强版"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 获取系统主题设置
        self.display_mode = 'light'
        if parent and hasattr(parent, 'settings'):
            self.display_mode = parent.settings.get('display_mode', 'light')
        
        self.setup_ui()
        self.load_cache_data()
        
    def setup_ui(self):
        self.setWindowTitle("💾 视频缓存管理")
        self.setMinimumSize(850, 600)
        
        # 根据主题设置样式
        if self.display_mode == 'dark':
            self.setStyleSheet("""
                QDialog {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #1a1a2e, stop:1 #16213e);
                }
                QLabel {
                    color: #eaeaea;
                    font-family: 'Microsoft YaHei', 'SimHei', sans-serif;
                }
                QTableWidget {
                    background: #0f0f1a;
                    border: 1px solid #2d3561;
                    border-radius: 8px;
                    color: #eaeaea;
                    gridline-color: #2d3561;
                }
                QTableWidget::item {
                    padding: 8px;
                    border-bottom: 1px solid #2d3561;
                }
                QTableWidget::item:selected {
                    background: rgba(52, 152, 219, 0.3);
                }
                QHeaderView::section {
                    background: #1a1a2e;
                    color: #3498db;
                    padding: 10px;
                    border: none;
                    font-weight: bold;
                }
                QPushButton {
                    font-family: 'Microsoft YaHei', 'SimHei', sans-serif;
                    font-weight: bold;
                    border-radius: 8px;
                    padding: 10px 20px;
                    font-size: 13px;
                }
                QComboBox {
                    background: #1a1a2e;
                    color: #eaeaea;
                    border: 1px solid #2d3561;
                    border-radius: 6px;
                    padding: 8px;
                    font-size: 13px;
                }
                QComboBox::drop-down {
                    border: none;
                }
                QComboBox QAbstractItemView {
                    background: #1a1a2e;
                    color: #eaeaea;
                    selection-background-color: #3498db;
                }
                QLineEdit {
                    background: #0f0f1a;
                    color: #eaeaea;
                    border: 1px solid #2d3561;
                    border-radius: 6px;
                    padding: 8px;
                    font-size: 13px;
                }
            """)
        else:
            self.setStyleSheet("""
                QDialog {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #f5f7fa, stop:1 #c3cfe2);
                }
                QLabel {
                    color: #2c3e50;
                    font-family: 'Microsoft YaHei', 'SimHei', sans-serif;
                }
                QTableWidget {
                    background: #ffffff;
                    border: 1px solid #d0d0d0;
                    border-radius: 8px;
                    color: #2c3e50;
                    gridline-color: #d0d0d0;
                }
                QTableWidget::item {
                    padding: 8px;
                    border-bottom: 1px solid #d0d0d0;
                }
                QTableWidget::item:selected {
                    background: rgba(52, 152, 219, 0.2);
                }
                QHeaderView::section {
                    background: #f5f7fa;
                    color: #3498db;
                    padding: 10px;
                    border: none;
                    font-weight: bold;
                }
                QPushButton {
                    font-family: 'Microsoft YaHei', 'SimHei', sans-serif;
                    font-weight: bold;
                    border-radius: 8px;
                    padding: 10px 20px;
                    font-size: 13px;
                }
                QComboBox {
                    background: #f5f7fa;
                    color: #2c3e50;
                    border: 1px solid #d0d0d0;
                    border-radius: 6px;
                    padding: 8px;
                    font-size: 13px;
                }
                QComboBox::drop-down {
                    border: none;
                }
                QComboBox QAbstractItemView {
                    background: #f5f7fa;
                    color: #2c3e50;
                    selection-background-color: #3498db;
                }
                QLineEdit {
                    background: #ffffff;
                    color: #2c3e50;
                    border: 1px solid #d0d0d0;
                    border-radius: 6px;
                    padding: 8px;
                    font-size: 13px;
                }
            """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title_label = QLabel("💾 视频缓存管理")
        title_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #3498db;")
        layout.addWidget(title_label)
        
        # 统计信息面板
        stats_container = QLabel()
        stats_container.setStyleSheet("""
            background: rgba(52, 152, 219, 0.1);
            border: 1px solid rgba(52, 152, 219, 0.3);
            border-radius: 10px;
            padding: 15px;
        """)
        stats_layout = QVBoxLayout(stats_container)
        
        self.stats_label = QLabel("加载中...")
        self.stats_label.setStyleSheet("font-size: 14px; color: #eaeaea;")
        stats_layout.addWidget(self.stats_label)
        
        layout.addWidget(stats_container)
        
        # 筛选和搜索区域
        filter_container = QLabel()
        filter_container.setStyleSheet("""
            background: rgba(255, 255, 255, 0.03);
            border-radius: 8px;
            padding: 10px;
        """)
        filter_layout = QHBoxLayout(filter_container)
        
        # 排序选项
        sort_label = QLabel("📊 排序:")
        sort_label.setStyleSheet("color: #95a5a6;")
        filter_layout.addWidget(sort_label)
        
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["按下载时间", "按文件大小", "按发布日期", "按UP主"])
        self.sort_combo.currentIndexChanged.connect(self.load_cache_data)
        filter_layout.addWidget(self.sort_combo)
        
        filter_layout.addSpacing(20)
        
        # 搜索框
        search_label = QLabel("🔍 搜索:")
        search_label.setStyleSheet("color: #95a5a6;")
        filter_layout.addWidget(search_label)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入标题、BV号或UP主...")
        self.search_input.setFixedWidth(200)
        self.search_input.textChanged.connect(self.load_cache_data)
        filter_layout.addWidget(self.search_input)
        
        filter_layout.addStretch()
        layout.addWidget(filter_container)
        
        # 缓存列表
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["BV号", "标题", "UP主", "发布日期", "大小", "下载时间", "操作"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.table)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background: #3498db;
                color: white;
            }
            QPushButton:hover {
                background: #2980b9;
            }
        """)
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.clicked.connect(self.load_cache_data)
        btn_layout.addWidget(refresh_btn)
        
        open_folder_btn = QPushButton("📁 打开缓存文件夹")
        open_folder_btn.setStyleSheet("""
            QPushButton {
                background: #9b59b6;
                color: white;
            }
            QPushButton:hover {
                background: #8e44ad;
            }
        """)
        open_folder_btn.setCursor(Qt.PointingHandCursor)
        open_folder_btn.clicked.connect(self.open_cache_folder)
        btn_layout.addWidget(open_folder_btn)
        
        # 智能清理按钮
        smart_clean_btn = QPushButton("🧹 智能清理")
        smart_clean_btn.setStyleSheet("""
            QPushButton {
                background: #f39c12;
                color: white;
            }
            QPushButton:hover {
                background: #e67e22;
            }
        """)
        smart_clean_btn.setCursor(Qt.PointingHandCursor)
        smart_clean_btn.setToolTip("清理超过30天的旧缓存")
        smart_clean_btn.clicked.connect(self.smart_clean)
        btn_layout.addWidget(smart_clean_btn)
        
        clear_all_btn = QPushButton("🗑️ 清空所有")
        clear_all_btn.setStyleSheet("""
            QPushButton {
                background: #e74c3c;
                color: white;
            }
            QPushButton:hover {
                background: #c0392b;
            }
        """)
        clear_all_btn.setCursor(Qt.PointingHandCursor)
        clear_all_btn.clicked.connect(self.clear_all_cache)
        btn_layout.addWidget(clear_all_btn)
        
        btn_layout.addStretch()
        
        close_btn = QPushButton("✕ 关闭")
        close_btn.setStyleSheet("""
            QPushButton {
                background: #7f8c8d;
                color: white;
            }
            QPushButton:hover {
                background: #5f6a6a;
            }
        """)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
    
    def load_cache_data(self):
        """加载缓存数据 - 支持排序和搜索"""
        cache_info = get_cache_info()
        videos = cache_info['videos']
        
        # 获取搜索关键词
        search_text = self.search_input.text().lower() if hasattr(self, 'search_input') else ""
        
        # 过滤视频
        filtered_videos = []
        for bvid, info in videos.items():
            if search_text:
                title = info.get('title', '').lower()
                up_name = info.get('up_name', '').lower()
                if search_text not in bvid.lower() and search_text not in title and search_text not in up_name:
                    continue
            filtered_videos.append((bvid, info))
        
        # 排序
        sort_mode = self.sort_combo.currentIndex() if hasattr(self, 'sort_combo') else 0
        if sort_mode == 0:  # 按下载时间
            filtered_videos.sort(key=lambda x: x[1].get('download_time', ''), reverse=True)
        elif sort_mode == 1:  # 按文件大小
            filtered_videos.sort(key=lambda x: x[1].get('size', 0), reverse=True)
        elif sort_mode == 2:  # 按发布日期
            filtered_videos.sort(key=lambda x: x[1].get('pubdate', ''), reverse=True)
        elif sort_mode == 3:  # 按UP主
            filtered_videos.sort(key=lambda x: x[1].get('up_name', '').lower())
        
        # 更新统计
        total_size = sum(info.get('size', 0) for _, info in filtered_videos)
        self.stats_label.setText(
            f"📊 显示: {len(filtered_videos)} / {cache_info['count']} 个视频 | "
            f"💾 占用: {total_size / (1024 * 1024):.2f} / {cache_info['total_size_mb']:.2f} MB | "
            f"📁 位置: {VIDEO_CACHE_DIR}"
        )
        
        # 更新表格
        self.table.setRowCount(len(filtered_videos))
        
        for row, (bvid, info) in enumerate(filtered_videos):
            # BV号
            bvid_item = QTableWidgetItem(bvid)
            bvid_item.setForeground(QColor('#3498db'))
            self.table.setItem(row, 0, bvid_item)
            
            # 标题
            title_item = QTableWidgetItem(info.get('title', '未知标题')[:60])
            title_item.setToolTip(info.get('title', ''))
            self.table.setItem(row, 1, title_item)
            
            # UP主
            up_item = QTableWidgetItem(info.get('up_name', '未知UP主')[:20])
            up_item.setForeground(QColor('#9b59b6'))
            self.table.setItem(row, 2, up_item)
            
            # 发布日期
            pubdate = info.get('pubdate', '')
            if pubdate and len(pubdate) >= 10:
                pubdate = pubdate[:10]
            else:
                pubdate = "未知"
            pubdate_item = QTableWidgetItem(pubdate)
            pubdate_item.setForeground(QColor('#eaeaea'))
            self.table.setItem(row, 3, pubdate_item)
            
            # 大小
            size_mb = info.get('size', 0) / (1024 * 1024)
            size_item = QTableWidgetItem(f"{size_mb:.1f} MB")
            if size_mb > 100:
                size_item.setForeground(QColor('#e74c3c'))  # 大文件标红
            elif size_mb > 50:
                size_item.setForeground(QColor('#f39c12'))  # 中等文件标黄
            else:
                size_item.setForeground(QColor('#2ecc71'))  # 小文件标绿
            self.table.setItem(row, 4, size_item)
            
            # 下载时间
            download_time_item = QTableWidgetItem(info.get('download_time', '未知'))
            download_time_item.setForeground(QColor('#eaeaea'))
            self.table.setItem(row, 5, download_time_item)
            
            # 操作按钮
            play_btn = QPushButton("▶️ 播放")
            play_btn.setStyleSheet("""
                QPushButton {
                    background: #27ae60;
                    color: white;
                    padding: 5px 12px;
                    font-size: 11px;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background: #219a52;
                }
            """)
            play_btn.clicked.connect(lambda checked, b=bvid: self.play_video(b))
            self.table.setCellWidget(row, 6, play_btn)
        
        # 只调整非拉伸列的宽度，保持标题列的拉伸状态
        for i in range(self.table.columnCount()):
            if i != 1:  # 跳过标题列（索引为1），它已经设置为Stretch
                self.table.resizeColumnToContents(i)
    
    def show_context_menu(self, position):
        """显示右键菜单"""
        row = self.table.rowAt(position.y())
        if row < 0:
            return
        
        bvid = self.table.item(row, 0).text()
        
        menu = QMenu(self)
        if self.display_mode == 'dark':
            menu.setStyleSheet("""
                QMenu {
                    background: #1a1a2e;
                    color: #eaeaea;
                    border: 1px solid #2d3561;
                }
                QMenu::item:selected {
                    background: rgba(52, 152, 219, 0.3);
                }
            """)
        else:
            menu.setStyleSheet("""
                QMenu {
                    background: #f5f7fa;
                    color: #2c3e50;
                    border: 1px solid #d0d0d0;
                }
                QMenu::item:selected {
                    background: rgba(52, 152, 219, 0.2);
                }
            """)
        
        play_action = QAction("▶️ 播放", self)
        play_action.triggered.connect(lambda: self.play_video(bvid))
        menu.addAction(play_action)
        
        open_folder_action = QAction("📁 打开所在文件夹", self)
        open_folder_action.triggered.connect(lambda: self.open_video_folder(bvid))
        menu.addAction(open_folder_action)
        
        menu.addSeparator()
        
        delete_action = QAction("🗑️ 删除", self)
        delete_action.triggered.connect(lambda: self.delete_video(bvid))
        menu.addAction(delete_action)
        
        menu.exec_(self.table.viewport().mapToGlobal(position))
    
    def play_video(self, bvid: str):
        """播放视频"""
        index = load_cache_index()
        if bvid in index:
            file_path = index[bvid].get('file_path', '')
            if file_path and os.path.exists(file_path):
                QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
    
    def delete_video(self, bvid: str):
        """删除视频"""
        reply = QMessageBox.question(
            self, "确认删除", 
            f"确定要删除视频 {bvid} 吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if remove_from_cache_index(bvid):
                self.load_cache_data()
                QMessageBox.information(self, "成功", "视频已删除")
    
    def open_cache_folder(self):
        """打开缓存文件夹"""
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(VIDEO_CACHE_DIR)))
    
    def open_video_folder(self, bvid: str):
        """打开视频所在文件夹并选中文件"""
        index = load_cache_index()
        if bvid in index:
            file_path = index[bvid].get('file_path', '')
            if file_path and os.path.exists(file_path):
                # 打开文件夹并选中文件（Windows 使用 explorer /select）
                import subprocess
                import platform
                if platform.system() == 'Windows':
                    subprocess.run(['explorer', '/select,', os.path.normpath(file_path)])
                else:
                    # macOS 和 Linux 只打开文件夹
                    QDesktopServices.openUrl(QUrl.fromLocalFile(str(VIDEO_CACHE_DIR)))
            else:
                QMessageBox.warning(self, "错误", "视频文件不存在")
    
    def smart_clean(self):
        """智能清理 - 删除超过30天的旧缓存"""
        from datetime import datetime, timedelta
        
        index = load_cache_index()
        if not index:
            QMessageBox.information(self, "提示", "缓存为空")
            return
        
        # 计算30天前的日期
        cutoff_date = datetime.now() - timedelta(days=30)
        
        to_delete = []
        for bvid, info in index.items():
            download_time_str = info.get('download_time', '')
            try:
                download_time = datetime.strptime(download_time_str, '%Y-%m-%d %H:%M:%S')
                if download_time < cutoff_date:
                    to_delete.append(bvid)
            except:
                # 如果日期解析失败，也删除
                to_delete.append(bvid)
        
        if not to_delete:
            QMessageBox.information(self, "提示", "没有超过30天的旧缓存")
            return
        
        reply = QMessageBox.question(
            self, "确认清理", 
            f"发现 {len(to_delete)} 个超过30天的旧缓存视频\n"
            f"确定要清理这些旧缓存吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            deleted_count = 0
            for bvid in to_delete:
                if remove_from_cache_index(bvid):
                    deleted_count += 1
            
            self.load_cache_data()
            QMessageBox.information(self, "成功", f"已清理 {deleted_count} 个旧缓存视频")

    def clear_all_cache(self):
        """清空所有缓存"""
        cache_info = get_cache_info()
        
        if cache_info['count'] == 0:
            QMessageBox.information(self, "提示", "缓存为空")
            return
        
        reply = QMessageBox.question(
            self, "确认清空", 
            f"确定要清空所有 {cache_info['count']} 个视频缓存吗？\n"
            f"这将释放 {cache_info['total_size_mb']:.2f} MB 空间。",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            index = load_cache_index()
            for bvid in list(index.keys()):
                remove_from_cache_index(bvid)
            
            self.load_cache_data()
            QMessageBox.information(self, "成功", "缓存已清空")


def download_and_play_video(bvid: str, title: str, up_name: str = "", pubdate: str = "", parent=None):
    """
    下载并播放视频的便捷函数
    :param bvid: BV号
    :param title: 视频标题
    :param up_name: UP主名称
    :param pubdate: 发布日期
    :param parent: 父窗口
    :return: 是否成功
    """
    dialog = VideoDownloadDialog(bvid, title, up_name, pubdate, parent)
    result = dialog.exec_()
    return result == QDialog.Accepted


def play_video_local(bvid: str, title: str, parent=None):
    """
    播放本地缓存的视频，如果没有则下载
    :param bvid: BV号
    :param title: 视频标题
    :param parent: 父窗口
    :return: 是否成功
    """
    # 检查是否已缓存
    index = load_cache_index()
    
    if bvid in index:
        file_path = index[bvid].get('file_path', '')
        if file_path and os.path.exists(file_path):
            # 直接播放
            QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
            return True
    
    # 需要下载
    return download_and_play_video(bvid, title, parent)


def play_video_online(bvid: str, title: str, parent=None):
    """
    在线播放视频（直接在浏览器打开）
    :param bvid: BV号
    :param title: 视频标题
    :param parent: 父窗口
    :return: 是否成功
    """
    url = f"https://www.bilibili.com/video/{bvid}"
    QDesktopServices.openUrl(QUrl(url))
    return True


def get_video_stream_url(bvid: str) -> Optional[str]:
    """
    使用 yt-dlp 获取视频的流媒体直链
    :param bvid: BV号
    :return: 视频直链或None
    """
    try:
        url = f"https://www.bilibili.com/video/{bvid}"
        
        # 使用 yt-dlp 获取视频直链
        cmd = [
            "yt-dlp",
            "-f", "bv*+ba/b",
            "-g",  # 只获取URL，不下载
            "--no-warnings",
            "--no-check-certificates",
            url
        ]
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            encoding='utf-8',
            errors='ignore',
            timeout=30
        )
        
        if result.returncode == 0 and result.stdout:
            # 提取URL（可能有多行，取第一行视频URL）
            lines = result.stdout.strip().split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('http'):
                    return line
        
        return None
        
    except Exception as e:
        print(f"获取视频直链失败: {e}")
        return None


def play_video_streaming(bvid: str, title: str) -> bool:
    """
    使用外部播放器进行流媒体播放
    :param bvid: BV号
    :param title: 视频标题
    :return: 是否成功
    """
    try:
        # 获取视频直链
        video_url = get_video_stream_url(bvid)
        if not video_url:
            print("无法获取视频直链")
            return False
        
        print(f"获取到视频直链: {video_url[:50]}...")
        
        # 尝试使用 mpv 播放
        cmd = [
            "mpv",
            "--no-terminal",
            "--title", title,
            video_url
        ]
        
        # 启动 mpv 播放器（后台运行）
        subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        return True
        
    except FileNotFoundError:
        print("mpv 播放器未安装，请安装 mpv 后重试")
        return False
    except Exception as e:
        print(f"流媒体播放失败: {e}")
        return False


def open_cache_manager(parent=None):
    """打开缓存管理器"""
    dialog = CacheManagerDialog(parent)
    dialog.exec_()


def clear_video_cache():
    """清理视频缓存"""
    index = load_cache_index()
    count = 0
    for bvid in list(index.keys()):
        if remove_from_cache_index(bvid):
            count += 1
    return count


def get_cache_size():
    """获取缓存大小（MB）"""
    cache_info = get_cache_info()
    return cache_info['total_size_mb']
