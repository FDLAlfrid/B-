# -*- coding: utf-8 -*-
import os
import sys
import subprocess
import tkinter as tk
import shutil
import zipfile
import tempfile
import datetime
from pathlib import Path
from app import create_app, db
from app.utils import init_db
from app.services.bilibili_service import BilibiliService
from app.models import Music
from tkinter import ttk, messagebox, filedialog
import tkinter.font as tkfont
import threading
import datetime
import json
import logging
import webbrowser
from pathlib import Path

"""
Vocaloid应用 GUI 启动器
提供图形界面来启动、初始化、刷新、打包应用等功能
"""

class AppLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("Vocaloid应用管理器")
        self.root.geometry("800x600")
        self.root.resizable(True, True)
        
        # 配置中文字体支持
        self.configure_fonts()
        
        # 配置日志
        self.setup_logging()
        
        # 应用状态
        self.is_app_running = False
        self.server_process = None
        
        # 创建主界面
        self.create_main_frame()
        
        # 检查环境
        self.check_environment()
        
        # 设置窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def configure_fonts(self):
        """配置中文字体支持"""
        # 在Windows上设置默认字体
        if sys.platform == 'win32':
            default_font = ('SimHei', 10)
            text_font = ('SimHei', 9)
            title_font = ('SimHei', 14, 'bold')
        else:
            default_font = ('WenQuanYi Micro Hei', 10)
            text_font = ('WenQuanYi Micro Hei', 9)
            title_font = ('WenQuanYi Micro Hei', 14, 'bold')
        
        # 应用字体配置
        self.default_font = default_font
        self.text_font = text_font
        self.title_font = title_font
        
        # 设置tkinter默认字体
        try:
            app_font = tkfont.nametofont("TkDefaultFont")
            app_font.configure(family=default_font[0], size=default_font[1])
            
            # 设置文本字体
            text_font_obj = tkfont.nametofont("TkTextFont")
            text_font_obj.configure(family=text_font[0], size=text_font[1])
        except Exception as e:
            # 如果字体配置失败，记录错误但继续运行
            self.logger.warning(f"字体配置失败: {str(e)}")
    
    def setup_logging(self):
        """配置日志系统"""
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        
        log_filename = log_dir / f"launcher_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        # 创建日志器
        self.logger = logging.getLogger('AppLauncher')
        self.logger.setLevel(logging.DEBUG)
        
        # 清空现有处理器
        if self.logger.handlers:
            self.logger.handlers = []
        
        # 文件处理器
        file_handler = logging.FileHandler(log_filename, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        self.logger.info("启动器已初始化")
    
    def create_main_frame(self):
        """创建主界面"""
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题标签
        title_label = ttk.Label(main_frame, text="Vocaloid 应用管理器", font=self.title_font)
        title_label.pack(pady=10)
        
        # 环境信息标签
        self.env_status_var = tk.StringVar()
        self.env_status_var.set("环境检查中...")
        env_label = ttk.Label(main_frame, textvariable=self.env_status_var, foreground="blue")
        env_label.pack(pady=5)
        
        # 创建功能按钮区域
        buttons_frame = ttk.Frame(main_frame, padding="10")
        buttons_frame.pack(fill=tk.X, pady=10)
        
        # 创建网格布局的按钮
        button_width = 15
        
        # 第一行按钮
        ttk.Button(buttons_frame, text="启动应用", command=self.start_application_thread, width=button_width).grid(row=0, column=0, padx=5, pady=5)
        ttk.Button(buttons_frame, text="停止应用", command=self.stop_application, width=button_width).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(buttons_frame, text="初始化数据库", command=self.init_database_thread, width=button_width).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(buttons_frame, text="刷新数据", command=self.refresh_data_thread, width=button_width).grid(row=0, column=3, padx=5, pady=5)
        
        # 第二行按钮
        ttk.Button(buttons_frame, text="清空数据库", command=self.clear_database_thread, width=button_width).grid(row=1, column=0, padx=5, pady=5)
        ttk.Button(buttons_frame, text="备份数据库", command=self.backup_database_thread, width=button_width).grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(buttons_frame, text="清理缓存", command=self.clear_cache_thread, width=button_width).grid(row=1, column=2, padx=5, pady=5)
        ttk.Button(buttons_frame, text="打包应用", command=self.package_application_thread, width=button_width).grid(row=1, column=3, padx=5, pady=5)
        
        # 创建输出日志区域
        log_frame = ttk.LabelFrame(main_frame, text="运行日志", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # 创建滚动条
        log_scrollbar = ttk.Scrollbar(log_frame)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 创建文本框用于显示日志
        self.log_text = tk.Text(log_frame, wrap=tk.WORD, font=self.text_font, yscrollcommand=log_scrollbar.set)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        log_scrollbar.config(command=self.log_text.yview)
        
        # 设置文本框为只读
        self.log_text.config(state=tk.DISABLED)
        
        # 创建状态栏
        self.status_var = tk.StringVar()
        self.status_var.set("就绪")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
    def check_environment(self):
        """检查运行环境"""
        try:
            # 检查是否在正确的conda环境中
            conda_env = os.environ.get('CONDA_DEFAULT_ENV', '')
            if 'vocaloid_vis' in conda_env:
                self.env_status_var.set(f"当前环境: {conda_env}")
                self.logger.info(f"检测到conda环境: {conda_env}")
            else:
                self.env_status_var.set("警告: 未激活vocaloid_vis环境")
                self.logger.warning("未检测到vocaloid_vis环境")
                messagebox.showwarning("环境警告", "未检测到vocaloid_vis环境，请手动激活后再启动应用。")
            
            return False
            
            return True
        except Exception as e:
            self.logger.error(f"环境检查失败: {str(e)}")
            messagebox.showerror("环境检查失败", f"检查环境时出错: {str(e)}")
            return False
    
    def append_log(self, message):
        """向日志区域添加消息"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"
        
        # 在文本框中添加日志
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, log_message)
        self.log_text.see(tk.END)  # 滚动到最后
        self.log_text.config(state=tk.DISABLED)
        
        # 同时写入日志文件
        self.logger.info(message)
    
    def update_status(self, status):
        """更新状态栏信息"""
        self.status_var.set(status)
    
    def handle_migrations(self):
        """处理数据库迁移"""
        try:
            self.append_log("检查数据库迁移...")
            migrations_dir = Path('migrations')
            if not migrations_dir.exists():
                self.append_log("初始化数据库迁移...")
                result = subprocess.run(
                    ['flask', 'db', 'init'],
                    capture_output=True, text=True, encoding='utf-8'
                )
                if result.returncode != 0:
                    self.append_log(f"迁移初始化失败: {result.stderr}")
                    return False
            
            env = os.environ.copy()
            env['FLASK_APP'] = 'run.py'
            result = subprocess.run(
                ["flask", "db", "migrate", "-m", "自动迁移"],
                capture_output=True, text=True, env=env, encoding='utf-8'
            )
            
            self.append_log("应用数据库迁移...")
            result = subprocess.run(
                ["flask", "db", "upgrade"],
                capture_output=True, text=True, env=env, encoding='utf-8'
            )
            if result.returncode == 0:
                self.append_log("数据库迁移成功")
                return True
            else:
                self.append_log(f"迁移警告: {result.stderr}")
                return True
        except Exception as e:
            self.append_log(f"迁移出错: {str(e)}")
            return False
    
    def init_database(self, refresh=False):
        """初始化数据库和音乐数据"""
        try:
            self.append_log("初始化数据库...")
            self.handle_migrations()
            
            app = create_app()
            with app.app_context():
                init_db(app)
                
                if refresh or not Music.query.first():
                    self.append_log("获取音乐数据...")
                    bili_service = BilibiliService()
                    rids = [30, 29, 190]
                    all_music = []
                    
                    for rid in rids:
                        self.append_log(f"获取分区 {rid} 数据...")
                        music_data = bili_service.fetch_vocaloid_music(rid=rid, limit=50)
                        all_music.extend(music_data)
                        
                    self.append_log(f"共获取 {len(all_music)} 条数据")
                    Music.query.delete()
                    current_time = int(datetime.datetime.now().timestamp())
                    
                    for item in all_music:
                        existing = Music.query.filter_by(bvid=item['bvid']).first()
                        if existing:
                            existing.title = item['title']
                            existing.author = item['author']
                            existing.cover_url = item['cover_url']
                            existing.update_time = current_time
                        else:
                            new_music = Music(
                                bvid=item['bvid'],
                                title=item['title'],
                                author=item['author'],
                                cover_url=item['cover_url'],
                                duration=item['duration'],
                                tags=item['tags'],
                                view_count=item['view_count'],
                                category=item.get('category', '其他'),
                                rid=item.get('rid', 0),
                                crawl_time=current_time
                            )
                            db.session.add(new_music)
                    
                    db.session.commit()
                    self.append_log("数据库初始化完成")
            return True
        except Exception as e:
            self.append_log(f"初始化失败: {str(e)}")
            return False
    
    def backup_database(self):
        """备份数据库"""
        try:
            db_path = Path('instance/vocaloid_vis.sqlite')
            if not db_path.exists():
                self.append_log("数据库文件不存在")
                return False
            
            backup_dir = Path('backups')
            backup_dir.mkdir(exist_ok=True)
            filename = f'backup_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.sqlite'
            backup_path = backup_dir / filename
            
            shutil.copy2(db_path, backup_path)
            self.append_log(f"备份成功: {backup_path}")
            return True
        except Exception as e:
            self.append_log(f"备份失败: {str(e)}")
            return False
    
    def clear_database(self):
        """清空数据库"""
        try:
            app = create_app()
            with app.app_context():
                for table in reversed(db.metadata.sorted_tables):
                    db.session.execute(table.delete())
                db.session.commit()
            self.append_log("数据库已清空")
            return True
        except Exception as e:
            self.append_log(f"清空失败: {str(e)}")
            return False
    
    def clear_cache(self):
        """清理缓存文件"""
        try:
            cache_dirs = [
                Path('app/static/cache'),
                Path('tmp'),
                Path('instance/cache')
            ]
            
            for dir_path in cache_dirs:
                if dir_path.exists():
                    for item in dir_path.iterdir():
                        if item.is_file(): item.unlink()
                        elif item.is_dir(): shutil.rmtree(item)
                    self.append_log(f"清理缓存: {dir_path}")
            return True
        except Exception as e:
            self.append_log(f"缓存清理失败: {str(e)}")
            return False
    
    def package_application(self):
        """打包应用程序"""
        try:
            self.append_log("开始打包应用...")
            package_dir = Path('package')
            package_dir.mkdir(exist_ok=True)
            
            package_name = f'vocaloid_vis_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
            package_path = package_dir / package_name
            
            exclude_patterns = [
                'venv', '__pycache__', '*.pyc', '*.pyo', '*.pyd',
                'logs', 'backups', 'package', 'instance/vocaloid_vis.sqlite',
                '*.sqlite-journal', '.git', '.gitignore',
                '*.log', '*.bak', '*.tmp', '.idea', '*.swp'
            ]
            
            with zipfile.ZipFile(package_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk('.'):
                    dirs[:] = [d for d in dirs if not any(exclude in d for exclude in exclude_patterns)]
                    
                    for file in files:
                        if any(file.endswith(exclude) or exclude in file for exclude in exclude_patterns):
                            continue
                        
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, '.')
                        zipf.write(file_path, arcname)
                        self.append_log(f"添加文件: {arcname}")
            
            start_script = package_dir / 'start.bat'
            with open(start_script, 'w', encoding='utf-8') as f:
                f.write('@echo off\n')
                f.write('echo 启动Vocaloid可视化应用...\n')
                f.write('conda activate vocaloid_vis\n')
                f.write('python app_launcher.py\n')
                f.write('pause\n')
            
            self.append_log(f"应用打包成功: {package_path}")
            return True
        except Exception as e:
            self.append_log(f"打包失败: {str(e)}")
            return False
    
    def start_application(self):
        """启动应用程序"""
        if self.is_app_running:
            messagebox.showinfo("提示", "应用已经在运行中")
            return
        
        try:
            self.append_log("开始启动应用...")
            self.update_status("启动应用中")
            
            # 检查环境
            if not self.check_environment():
                return
            
            # 直接启动Flask应用
            from run import app
            import threading
            
            def run_flask_app():
                app.run(host='127.0.0.1', port=5000, debug=True)
            
            # 在新线程中启动Flask应用
            threading.Thread(target=run_flask_app, daemon=True).start()
            self.server_process = None
            self.is_app_running = True
            self.append_log("Flask应用已在后台启动")
            
            self.is_app_running = True
            
            # 实时显示输出
            while self.is_app_running and self.server_process.poll() is None:
                try:
                    line = self.server_process.stdout.readline()
                    if line:
                        self.append_log(line.strip())
                        # 检查是否包含启动链接
                        if 'http://' in line and ('localhost' in line or '127.0.0.1' in line):
                            self.update_status(f"应用已启动: {line.strip()}")
                            # 提取URL并自动打开浏览器
                            # 使用正则表达式提取URL
                            import re
                            url_match = re.search(r'http://\S+', line.strip())
                            if url_match:
                                url = url_match.group(0)
                                self.append_log(f"自动打开浏览器访问: {url}")
                                try:
                                    webbrowser.open(url)
                                except Exception as e:
                                    self.append_log(f"打开浏览器失败: {str(e)}")
                except Exception as e:
                    self.append_log(f"读取输出时出错: {str(e)}")
                    break
            
            # 检查进程是否异常退出
            if self.server_process.poll() is not None:
                self.is_app_running = False
                self.update_status(f"应用已停止，返回代码: {self.server_process.returncode}")
                self.server_process = None
                
        except Exception as e:
            self.append_log(f"启动应用时出错: {str(e)}")
            self.update_status("启动失败")
            self.is_app_running = False
            self.server_process = None
    
    def stop_application(self):
        """停止应用程序"""
        if not self.is_app_running or not self.server_process:
            messagebox.showinfo("提示", "应用未在运行中")
            return
        
        if messagebox.askyesno("确认停止", "确定要停止应用程序吗？"):
            try:
                self.append_log("正在停止应用...")
                self.update_status("停止应用中")
                
                # 终止进程
                self.server_process.terminate()
                
                # 等待进程结束
                self.server_process.wait(timeout=5)
                
                self.is_app_running = False
                self.server_process = None
                
                self.append_log("应用已停止")
                self.update_status("就绪")
            except Exception as e:
                self.append_log(f"停止应用时出错: {str(e)}")
                self.update_status("停止失败")
    
    # 线程包装方法
    def start_application_thread(self):
        threading.Thread(target=self.start_application, daemon=True).start()
    
    def init_database_thread(self):
        if messagebox.askyesno("确认初始化", "确定要初始化数据库吗？这将清空现有数据并重新抓取。"):
            threading.Thread(target=lambda: self.init_database(refresh=True), daemon=True).start()
    
    def refresh_data_thread(self):
        threading.Thread(target=lambda: self.init_database(refresh=True), daemon=True).start()
    
    def clear_database_thread(self):
        if messagebox.askyesno("确认清空", "确定要清空数据库吗？此操作不可恢复！"):
            threading.Thread(target=self.clear_database, daemon=True).start()
    
    def backup_database_thread(self):
        threading.Thread(target=self.backup_database, daemon=True).start()
    
    def clear_cache_thread(self):
        threading.Thread(target=self.clear_cache, daemon=True).start()
    
    def package_application_thread(self):
        threading.Thread(target=self.package_application, daemon=True).start()
    
    def on_closing(self):
        """窗口关闭事件处理"""
        if self.is_app_running:
            if messagebox.askyesno("确认退出", "应用程序仍在运行中，确定要退出吗？"):
                self.stop_application()
                self.root.destroy()
        else:
            self.root.destroy()

if __name__ == "__main__":
    # 设置环境变量
    os.environ['PYTHONUTF8'] = '1'
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    
    # 创建主窗口
    root = tk.Tk()
    
    # 创建启动器实例
    app = AppLauncher(root)
    
    # 运行主循环
    root.mainloop()