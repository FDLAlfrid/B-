#主程序
import os
import sys
import json
import logging
import requests
import subprocess
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import threading
import time
from io import StringIO
import re

# 修复PyInstaller打包时可能出现的stdout/stderr问题的自定义类
class BufferedStringIO(StringIO):
    def __init__(self):
        super().__init__()
        # 创建一个模拟的buffer对象
        self.buffer = self

# 修复PyInstaller打包时可能出现的stdout/stderr为None的问题
if sys.stdout is None:
    sys.stdout = BufferedStringIO()
if sys.stderr is None:
    sys.stderr = BufferedStringIO()

# 导入you-get模块，简化导入以避免打包问题
try:
    import you_get
    from you_get.common import any_download
    HAS_YOU_GET = True
except ImportError as e:
    HAS_YOU_GET = False
    logging.error(f"导入you-get失败: {str(e)}")

# 配置日志
def setup_logger(log_text_widget=None):
    logger = logging.getLogger('bilibili_downloader')
    logger.setLevel(logging.DEBUG)
    
    # 清除已有的处理器
    if logger.handlers:
        logger.handlers.clear()
    
    # 格式化器
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # 文件处理器 - 即使在GUI模式下也保存日志到文件
    try:
        # 在用户目录下创建日志文件，避免权限问题
        log_dir = os.path.join(os.path.expanduser('~'), '.bilibili_downloader')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, 'downloader.log')
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        # 如果无法创建日志文件，继续执行但不记录到文件
        pass
    
    # 文本控件处理器（如果提供了）
    class TextHandler(logging.Handler):
        def __init__(self, text_widget):
            super().__init__()
            self.text_widget = text_widget
            
        def emit(self, record):
            msg = self.format(record) + "\n"
            self.text_widget.configure(state='normal')
            self.text_widget.insert(tk.END, msg)
            self.text_widget.see(tk.END)
            self.text_widget.configure(state='disabled')
    
    # 添加文本控件处理器
    if log_text_widget:
        text_handler = TextHandler(log_text_widget)
        text_handler.setLevel(logging.DEBUG)
        text_handler.setFormatter(formatter)
        logger.addHandler(text_handler)
    
    return logger

# 检查是否在指定的虚拟环境中
def check_virtual_environment(env_name='bilibili_downloader'):
    # 检查当前Python解释器路径
    python_exe = sys.executable
    logger.info(f"当前Python解释器: {python_exe}")
    
    # 检查是否在conda环境中
    if 'conda' in python_exe.lower() and env_name in python_exe.lower():
        logger.info(f"已在虚拟环境 '{env_name}' 中运行")
        return True
    
    return False

# 获取conda环境的Python解释器路径
def get_conda_env_python(env_name='bilibili_downloader'):
    try:
        # 查找conda位置
        if os.name == 'nt':  # Windows
            conda_cmd = 'conda'
        else:
            conda_cmd = '/opt/conda/bin/conda'
            if not os.path.exists(conda_cmd):
                conda_cmd = 'conda'
        
        # 获取环境列表
        result = subprocess.run([conda_cmd, 'env', 'list', '--json'], capture_output=True, text=True)
        envs = json.loads(result.stdout)
        
        # 查找指定环境
        for env_path in envs['envs']:
            if env_name in os.path.basename(env_path) or env_path.endswith(env_name):
                if os.name == 'nt':
                    python_exe = os.path.join(env_path, 'python.exe')
                else:
                    python_exe = os.path.join(env_path, 'bin', 'python')
                
                if os.path.exists(python_exe):
                    logger.info(f"找到虚拟环境 '{env_name}' 的Python解释器: {python_exe}")
                    return python_exe
        
        logger.warning(f"未找到虚拟环境 '{env_name}'")
        return None
    except Exception as e:
        logger.error(f"获取虚拟环境Python解释器失败: {str(e)}")
        return None

# 在指定虚拟环境中运行脚本
def run_in_virtual_environment(env_name='bilibili_downloader'):
    if check_virtual_environment(env_name):
        return False  # 已经在指定环境中，不需要重新启动
    
    python_exe = get_conda_env_python(env_name)
    if not python_exe:
        logger.warning(f"无法找到或创建虚拟环境 '{env_name}'，将继续在当前环境中运行")
        return False
    
    logger.info(f"正在切换到虚拟环境 '{env_name}'...")
    
    # 重新启动脚本，使用虚拟环境的Python解释器
    script_path = os.path.abspath(__file__)
    
    # 设置启动参数，隐藏控制台窗口
    if os.name == 'nt':  # Windows系统
        subprocess.Popen(
            [python_exe, script_path],
            shell=False,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
    else:
        subprocess.Popen([python_exe, script_path])
    return True

# 从JSON或Header字符串解析cookies
def parse_cookies(cookies_input, cookies_format):
    try:
        if cookies_format == 'json':
            cookies_list = json.loads(cookies_input)
            if isinstance(cookies_list, list):
                cookies_dict = {cookie['name']: cookie['value'] for cookie in cookies_list}
            elif isinstance(cookies_list, dict):
                cookies_dict = cookies_list
            else:
                raise ValueError("无效的JSON格式: 不是列表也不是字典")
        elif cookies_format == 'header':
            cookies_dict = {}
            for cookie in cookies_input.split(';'):
                cookie = cookie.strip()
                if cookie:
                    try:
                        key, value = cookie.split('=', 1)
                        cookies_dict[key] = value
                    except ValueError:
                        logger.warning(f"跳过无效的cookie: {cookie}")
        else:
            raise ValueError(f"无效的cookies格式: {cookies_format}")
        return cookies_dict
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON解析错误: {str(e)}")

# 使用requests获取视频页面内容
def download_with_requests(cookies_dict, video_url):
    try:
        logger.info(f"正在使用requests获取视频页面: {video_url}")
        response = requests.get(video_url, cookies=cookies_dict, timeout=30)
        response.raise_for_status()
        logger.info(f"成功获取视频页面内容，状态码: {response.status_code}")
        return True
    except Exception as e:
        logger.error(f"获取视频页面失败: {str(e)}")
        return False

# 使用you-get下载视频
def download_with_you_get(cookies_dict, video_url, save_path, quality=None):
    try:
        logger.info(f"正在使用you-get下载视频: {video_url}")
        logger.info(f"保存路径: {save_path}")
        if quality:
            logger.info(f"下载画质: {quality}")
        
        # 确保保存路径存在
        os.makedirs(save_path, exist_ok=True)
        
        # 检查是否成功导入了you-get模块
        if HAS_YOU_GET:
            logger.info("使用硬导入的you-get模块")
            
            # 设置下载选项
            options = {}
            options['output_dir'] = save_path
            options['merge'] = True  # 自动合并视频和音频
            if quality:
                options['format'] = quality
            
            # 处理cookies
            cookies_file = None
            if cookies_dict:
                logger.info("应用cookies配置")
                # 保存cookies到临时文件
                temp_dir = os.path.join(os.path.expanduser('~'), '.bilibili_downloader')
                os.makedirs(temp_dir, exist_ok=True)
                cookies_file = os.path.join(temp_dir, 'cookies.txt')
                
                with open(cookies_file, 'w', encoding='utf-8') as f:
                    for k, v in cookies_dict.items():
                        f.write(f"{k}={v}\n")
                
                options['cookies'] = cookies_file
                logger.debug(f"已创建cookies临时文件: {cookies_file}")
                
            # 使用you-get的内部函数下载视频
            logger.info("开始下载视频...")
            try:
                # 修复参数重复问题：output_dir和merge都已在options中设置
                any_download(video_url, info_only=False, **options)
            except Exception as inner_e:
                logger.error(f"you-get内部函数调用失败: {str(inner_e)}")
                # 尝试使用命令行方式作为备选
                raise ImportError("尝试切换到命令行模式") from inner_e
            
            # 清理cookies文件
            if cookies_file and os.path.exists(cookies_file):
                try:
                    os.remove(cookies_file)
                except Exception as e:
                    logger.warning(f"删除临时cookies文件失败: {str(e)}")
            
            logger.info("视频下载成功！")
            return True
        else:
            logger.info("未检测到you-get模块，直接使用命令行模式")
            raise ImportError("需要使用命令行模式")
    except Exception as e:
        logger.info(f"切换到命令行模式: {str(e)}")
        
        # 创建命令基础部分
        # 修复外部调用和弹窗问题：直接使用内部函数而不是创建子进程
        logger.warning("由于内部函数调用失败，尝试使用备用方法")
        
        # 尝试直接调用you-get的命令行实现，但不创建新进程
        try:
            from you_get import common as you_get_common
            # 构建参数列表
            args = ['--output-dir', save_path]
            if cookies_file:
                args.extend(['--cookies', cookies_file])
            if quality:
                args.extend(['--format', quality])
            args.append(video_url)
            
            logger.debug(f"执行内部命令行模式: {' '.join(args)}")
            # 设置sys.argv并直接调用main函数
            old_argv = sys.argv
            try:
                sys.argv = ['you-get'] + args
                you_get_common.main()
            finally:
                sys.argv = old_argv
            
            logger.info("视频下载成功！")
            return True
        except Exception as inner_e:
            logger.error(f"备用方法执行失败: {str(inner_e)}")
            
        # 如果备用方法也失败，才使用子进程方式（作为最后的备选）
        # 但为了解决外部调用问题，这里直接返回失败
        logger.error("所有下载方法均失败")
        return False
        
        # 以下代码已被替换，但保留注释供参考
        # is_frozen = getattr(sys, 'frozen', False)
        # command = [sys.executable, '-m', 'you_get', '-o', save_path]
        
        # 处理cookies（使用临时文件方式）
        cookies_file = None
        if cookies_dict:
            # 创建临时cookies文件
            temp_dir = os.path.join(os.path.expanduser('~'), '.bilibili_downloader')
            os.makedirs(temp_dir, exist_ok=True)
            cookies_file = os.path.join(temp_dir, 'cookies.txt')
            
            try:
                with open(cookies_file, 'w', encoding='utf-8') as f:
                    for k, v in cookies_dict.items():
                        f.write(f"{k}={v}\n")
                
                # 添加cookies文件参数
                command.extend(['--cookies', cookies_file])
                logger.debug(f"已创建cookies临时文件: {cookies_file}")
            except Exception as cookie_e:
                logger.error(f"创建cookies文件失败: {str(cookie_e)}")
        
        # 添加视频URL
        command.append(video_url)
        logger.debug(f"执行命令: {' '.join(command)}")
        
        # 创建进程并捕获输出，同时隐藏控制台窗口
        if os.name == 'nt':  # Windows系统
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                shell=False,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        else:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
        
        # 安全地读取输出，防止对已关闭文件的操作
        try:
            # 使用readline而不是迭代器，更可靠
            while True:
                line = process.stdout.readline()
                if not line:
                    break
                line = line.strip()
                if line:
                    logger.info(line)
        except Exception as read_e:
            logger.warning(f"读取子进程输出时发生错误: {str(read_e)}")
        
        # 等待进程完成
        process.wait()
        
        # 关闭流
        try:
            process.stdout.close()
        except Exception as close_e:
            logger.warning(f"关闭子进程输出流时发生错误: {str(close_e)}")
        
        # 删除临时cookies文件
        if cookies_file and os.path.exists(cookies_file):
            try:
                os.remove(cookies_file)
            except Exception as e:
                logger.warning(f"删除临时cookies文件失败: {str(e)}")
        
        # 检查返回码
        if process.returncode == 0:
            logger.info("视频下载成功！")
            return True
        else:
            logger.error(f"视频下载失败，返回码: {process.returncode}")
            # 对于返回码1，可能是网络问题或B站限制，尝试更详细的错误信息
            if process.returncode == 1:
                logger.error("可能是B站反爬限制，请尝试提供有效的Cookies或稍后再试")
            return False
    except Exception as e:
        logger.error(f"下载过程中发生错误: {str(e)}")
        logger.debug(f"详细错误信息: {str(e)}", exc_info=True)
        return False

# 下载任务线程
class DownloadThread(threading.Thread):
    def __init__(self, parent, cookies_dict, video_url, save_path, download_method, quality=None):
        threading.Thread.__init__(self)
        self.parent = parent
        self.cookies_dict = cookies_dict
        self.video_url = video_url
        self.save_path = save_path
        self.download_method = download_method
        self.quality = quality
        self.result = False
        
    def run(self):
        try:
            if self.download_method == 'requests':
                self.result = download_with_requests(self.cookies_dict, self.video_url)
            elif self.download_method == 'you-get':
                self.result = download_with_you_get(self.cookies_dict, self.video_url, self.save_path, self.quality)
        finally:
            # 下载完成后启用按钮
            self.parent.root.after(100, self.parent.on_download_complete, self.result)

# 主GUI类
class BilibiliDownloaderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("B站视频下载工具")
        self.root.geometry("800x600")
        self.root.resizable(True, True)
        
        # 导入必要的模块
        import os
        
        # 设置窗口图标 - 适配PyInstaller打包后的情况
        try:
            # 获取图标路径，无论是在打包还是未打包的情况下
            if getattr(sys, 'frozen', False):  # 检查是否是打包后的程序
                # 在打包程序中，获取程序所在目录
                current_dir = os.path.dirname(sys.executable)
                # 尝试多种图标格式
                icon_extensions = ['ico', 'png']
                icon_path = None
                for ext in icon_extensions:
                    test_path = os.path.join(current_dir, f'icon.{ext}')
                    if os.path.exists(test_path):
                        icon_path = test_path
                        break
                
                if icon_path:
                    if os.name == 'nt':  # Windows系统
                        # 在Windows上，使用ico格式图标设置任务栏图标
                        if icon_path.lower().endswith('.ico'):
                            self.root.iconbitmap(default=icon_path)
                        # 同时使用iconphoto设置窗口标题栏图标，支持多种格式
                        self.root.iconphoto(True, tk.PhotoImage(file=icon_path))
                    else:
                        # 非Windows系统只使用iconphoto
                        self.root.iconphoto(True, tk.PhotoImage(file=icon_path))
            else:  # 未打包的程序
                # 获取当前脚本所在目录
                current_dir = os.path.dirname(os.path.abspath(__file__))
                # 尝试多种图标格式
                icon_extensions = ['ico', 'png']
                icon_path = None
                for ext in icon_extensions:
                    test_path = os.path.join(current_dir, f'icon.{ext}')
                    if os.path.exists(test_path):
                        icon_path = test_path
                        break
                
                if icon_path:
                    if os.name == 'nt':  # Windows系统
                        # 在Windows上，使用ico格式图标设置任务栏图标
                        if icon_path.lower().endswith('.ico'):
                            self.root.iconbitmap(default=icon_path)
                        # 同时使用iconphoto设置窗口标题栏图标，支持多种格式
                        self.root.iconphoto(True, tk.PhotoImage(file=icon_path))
                    else:
                        # 非Windows系统只使用iconphoto
                        self.root.iconphoto(True, tk.PhotoImage(file=icon_path))
        except Exception as e:
            # 图标设置失败不影响程序运行
            pass  # 暂时不使用logger，因为还未初始化

        # 设置中文字体支持
        self.style = ttk.Style()
        if os.name == 'nt':  # Windows系统
            self.style.configure(
                "TLabel", 
                font=('SimHei', 10)
            )
            self.style.configure(
                "TButton", 
                font=('SimHei', 10)
            )
            self.style.configure(
                "TEntry", 
                font=('SimHei', 10)
            )
            self.style.configure(
                "TRadiobutton", 
                font=('SimHei', 10)
            )
        
        # 创建主框架
        main_frame = ttk.Frame(root, padding=(10, 10, 10, 10))
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建输入区域
        input_frame = ttk.LabelFrame(main_frame, text="下载设置", padding=(10, 10, 10, 10))
        input_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 视频URL输入
        ttk.Label(input_frame, text="视频URL:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.url_entry = ttk.Entry(input_frame)
        self.url_entry.grid(row=0, column=1, sticky=tk.EW, pady=5, padx=(5, 0))
        input_frame.columnconfigure(1, weight=1)
        # 为URL输入框添加右键菜单
        self._create_context_menu(self.url_entry)
        
        # 保存路径选择
        ttk.Label(input_frame, text="保存路径:").grid(row=1, column=0, sticky=tk.W, pady=5)
        path_frame = ttk.Frame(input_frame)
        path_frame.grid(row=1, column=1, sticky=tk.EW, pady=5, padx=(5, 0))
        self.path_entry = ttk.Entry(path_frame)
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.path_entry.insert(0, os.getcwd())
        ttk.Button(path_frame, text="浏览", command=self.browse_save_path).pack(side=tk.RIGHT, padx=(5, 0))
        # 为路径输入框添加右键菜单
        self._create_context_menu(self.path_entry)
        
        # Cookies设置
        self.use_cookies = tk.BooleanVar(value=False)
        ttk.Checkbutton(input_frame, text="使用Cookies", variable=self.use_cookies, command=self.toggle_cookies_frame).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        # Cookies详细设置
        self.cookies_frame = ttk.LabelFrame(input_frame, text="Cookies设置", padding=(10, 10, 10, 10))
        self.cookies_frame.grid(row=3, column=0, columnspan=2, sticky=tk.EW, pady=5)
        self.cookies_frame.grid_remove()  # 初始隐藏
        
        # Cookies格式选择
        self.cookies_format = tk.StringVar(value='json')
        ttk.Radiobutton(self.cookies_frame, text="JSON格式", variable=self.cookies_format, value='json').grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Radiobutton(self.cookies_frame, text="Header格式", variable=self.cookies_format, value='header').grid(row=0, column=1, sticky=tk.W, pady=5)
        
        # Cookies内容输入
        ttk.Label(self.cookies_frame, text="Cookies内容:").grid(row=1, column=0, sticky=tk.NW, pady=5)
        self.cookies_text = scrolledtext.ScrolledText(self.cookies_frame, height=5, wrap=tk.WORD)
        self.cookies_text.grid(row=1, column=1, sticky=tk.EW, pady=5)
        self.cookies_frame.columnconfigure(1, weight=1)
        
        # 下载画质选择
        ttk.Label(input_frame, text="下载画质:").grid(row=4, column=0, sticky=tk.W, pady=5)
        quality_frame = ttk.Frame(input_frame)
        quality_frame.grid(row=4, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        self.quality = tk.StringVar(value='dash-flv')
        ttk.Combobox(quality_frame, textvariable=self.quality, values=[
            'dash-flv',  # 1080P 高码率
            'dash-flv720',  # 720P
            'dash-flv480',  # 480P
            'dash-flv360'   # 360P
        ], state='readonly', width=15).pack(side=tk.LEFT)
        ttk.Label(quality_frame, text="（仅在You-Get模式下生效）").pack(side=tk.LEFT, padx=(5, 0))
        
        # 下载方式选择
        ttk.Label(input_frame, text="下载方式:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.download_method = tk.StringVar(value='you-get')
        method_frame = ttk.Frame(input_frame)
        method_frame.grid(row=5, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        ttk.Radiobutton(method_frame, text="Requests (仅获取页面)", variable=self.download_method, value='requests').pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(method_frame, text="You-Get (下载视频)", variable=self.download_method, value='you-get').pack(side=tk.LEFT)
        
        # 按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.download_button = ttk.Button(button_frame, text="开始下载", command=self.start_download)
        self.download_button.pack(side=tk.RIGHT, padx=(5, 0))
        
        ttk.Button(button_frame, text="退出", command=root.quit).pack(side=tk.RIGHT)
        
        # 历史记录区域
        history_frame = ttk.LabelFrame(main_frame, text="下载历史", padding=(10, 10, 10, 10))
        history_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 历史记录按钮区域
        history_button_frame = ttk.Frame(history_frame)
        history_button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(history_button_frame, text="导出历史", command=self.export_history).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(history_button_frame, text="清空历史", command=self.clear_history).pack(side=tk.LEFT)
        
        # 历史记录列表
        self.history_tree = ttk.Treeview(history_frame, columns=('url', 'title', 'time'), show='headings')
        self.history_tree.heading('url', text='视频链接')
        self.history_tree.heading('title', text='视频标题')
        self.history_tree.heading('time', text='下载时间')
        self.history_tree.column('url', width=300, anchor=tk.W)
        self.history_tree.column('title', width=300, anchor=tk.W)
        self.history_tree.column('time', width=150, anchor=tk.W)
        self.history_tree.pack(fill=tk.BOTH, expand=True)
        
        # 添加滚动条
        history_scrollbar = ttk.Scrollbar(self.history_tree, orient="vertical", command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=history_scrollbar.set)
        history_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 为历史记录添加右键菜单
        self._create_history_context_menu()
        
        # 日志区域
        log_frame = ttk.LabelFrame(main_frame, text="操作日志", padding=(10, 10, 10, 10))
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 日志按钮区域
        log_button_frame = ttk.Frame(log_frame)
        log_button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(log_button_frame, text="保存日志", command=self.save_log).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(log_button_frame, text="清理日志", command=self.clear_log).pack(side=tk.LEFT)
        
        # 日志文本区域
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state='disabled')
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # 为日志窗口添加右键菜单
        self._create_log_context_menu()
        
        # 初始化日志系统 - 现在log_text已创建，可以使用它了
        global logger
        logger = setup_logger(self.log_text)
        logger.info("B站视频下载工具已启动")
        
        # 加载历史记录
        self.load_history()
        
        # 记录图标设置状态
        is_frozen = getattr(sys, 'frozen', False)
        if is_frozen:
            logger.info("程序已打包，图标由PyInstaller处理")
        else:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            icon_path = os.path.join(current_dir, 'icon.png')
            if os.path.exists(icon_path):
                logger.info(f"已设置窗口图标: {icon_path}")
            else:
                logger.warning(f"未找到图标文件: {icon_path}")
        
        # 检查虚拟环境 - 只在未打包的程序中显示警告
        if not is_frozen and not check_virtual_environment():
            logger.warning("未在指定的虚拟环境中运行，某些功能可能受限")
    
    def _create_context_menu(self, widget):
        """为输入控件创建右键菜单"""
        context_menu = tk.Menu(widget, tearoff=0)
        context_menu.add_command(label="复制", command=lambda: self._copy_text(widget))
        context_menu.add_command(label="剪切", command=lambda: self._cut_text(widget))
        context_menu.add_command(label="粘贴", command=lambda: self._paste_text(widget))
        context_menu.add_separator()
        context_menu.add_command(label="全选", command=lambda: self._select_all_text(widget))
        
        # 绑定右键菜单事件
        def show_menu(event):
            context_menu.post(event.x_root, event.y_root)
        
        widget.bind("<Button-3>", show_menu)
        
        # 添加快捷键支持
        widget.bind("<Control-c>", lambda event: self._copy_text(widget))
        widget.bind("<Control-x>", lambda event: self._cut_text(widget))
        widget.bind("<Control-v>", lambda event: self._paste_text(widget))
        widget.bind("<Control-a>", lambda event: self._select_all_text(widget))
    
    def _copy_text(self, widget):
        """复制选中的文本到剪贴板"""
        try:
            # 确保控件可编辑
            widget.event_generate("<<Copy>>")
        except Exception:
            pass
            
    def _create_log_context_menu(self):
        """为日志文本框创建右键菜单"""
        log_context_menu = tk.Menu(self.log_text, tearoff=0)
        log_context_menu.add_command(label="复制", command=self._copy_log_text)
        log_context_menu.add_separator()
        log_context_menu.add_command(label="全选", command=self._select_all_log_text)
        
        # 绑定右键菜单事件
        def show_menu(event):
            log_context_menu.post(event.x_root, event.y_root)
        
        self.log_text.bind("<Button-3>", show_menu)
        
        # 添加快捷键支持
        self.log_text.bind("<Control-c>", lambda event: self._copy_log_text())
        self.log_text.bind("<Control-a>", lambda event: self._select_all_log_text())
        
    def _copy_log_text(self):
        """复制日志文本"""
        try:
            # 临时启用日志文本框
            self.log_text.configure(state='normal')
            self.log_text.event_generate("<<Copy>>")
            self.log_text.configure(state='disabled')
        except Exception:
            pass
            
    def _select_all_log_text(self):
        """全选日志文本"""
        try:
            self.log_text.configure(state='normal')
            self.log_text.selection_range(0, tk.END)
            self.log_text.configure(state='disabled')
        except Exception:
            pass
            
    def save_log(self):
        """保存日志到文件"""
        try:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".log",
                filetypes=[("日志文件", "*.log"), ("所有文件", "*")],
                title="保存日志文件"
            )
            
            if file_path:
                # 读取日志文本
                self.log_text.configure(state='normal')
                log_content = self.log_text.get(1.0, tk.END)
                self.log_text.configure(state='disabled')
                
                # 写入文件
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(log_content)
                
                logger.info(f"日志已保存到: {file_path}")
        except Exception as e:
            logger.error(f"保存日志失败: {str(e)}")
            messagebox.showerror("错误", f"保存日志失败: {str(e)}")
            
    def clear_log(self):
        """清理日志"""
        try:
            self.log_text.configure(state='normal')
            self.log_text.delete(1.0, tk.END)
            self.log_text.configure(state='disabled')
            logger.info("日志已清空")
        except Exception as e:
            logger.error(f"清理日志失败: {str(e)}")
            
    def _create_history_context_menu(self):
        """为历史记录列表创建右键菜单"""
        history_context_menu = tk.Menu(self.history_tree, tearoff=0)
        history_context_menu.add_command(label="复制链接", command=self._copy_history_url)
        history_context_menu.add_command(label="复制标题", command=self._copy_history_title)
        history_context_menu.add_separator()
        history_context_menu.add_command(label="删除选中", command=self._delete_history_item)
        
        # 绑定右键菜单事件
        def show_menu(event):
            # 选中点击的项目
            item = self.history_tree.identify_row(event.y)
            if item:
                self.history_tree.selection_set(item)
                history_context_menu.post(event.x_root, event.y_root)
        
        self.history_tree.bind("<Button-3>", show_menu)
        
    def _copy_history_url(self):
        """复制选中的历史记录链接"""
        try:
            selected_item = self.history_tree.selection()[0]
            url = self.history_tree.item(selected_item, "values")[0]
            self.root.clipboard_clear()
            self.root.clipboard_append(url)
        except (IndexError, Exception):
            pass
            
    def _copy_history_title(self):
        """复制选中的历史记录标题"""
        try:
            selected_item = self.history_tree.selection()[0]
            title = self.history_tree.item(selected_item, "values")[1]
            self.root.clipboard_clear()
            self.root.clipboard_append(title)
        except (IndexError, Exception):
            pass
            
    def _delete_history_item(self):
        """删除选中的历史记录项"""
        try:
            selected_item = self.history_tree.selection()[0]
            self.history_tree.delete(selected_item)
            self.save_history()
            logger.info("已删除选中的历史记录项")
        except (IndexError, Exception):
            pass
            
    def load_history(self):
        """加载历史记录"""
        try:
            # 获取历史记录文件路径
            history_dir = os.path.join(os.path.expanduser('~'), '.bilibili_downloader')
            history_file = os.path.join(history_dir, 'download_history.json')
            
            # 如果文件存在，加载历史记录
            if os.path.exists(history_file):
                with open(history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                    
                # 清空当前历史记录
                for item in self.history_tree.get_children():
                    self.history_tree.delete(item)
                    
                # 添加历史记录项
                for entry in history:
                    self.history_tree.insert('', tk.END, values=(entry['url'], entry['title'], entry['time']))
                
                logger.info(f"已加载 {len(history)} 条历史记录")
        except Exception as e:
            logger.error(f"加载历史记录失败: {str(e)}")
            
    def save_history(self):
        """保存历史记录"""
        try:
            # 获取历史记录文件路径
            history_dir = os.path.join(os.path.expanduser('~'), '.bilibili_downloader')
            os.makedirs(history_dir, exist_ok=True)
            history_file = os.path.join(history_dir, 'download_history.json')
            
            # 收集历史记录
            history = []
            for item in self.history_tree.get_children():
                url, title, time = self.history_tree.item(item, "values")
                history.append({'url': url, 'title': title, 'time': time})
                
            # 保存到文件
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
                
            logger.info(f"已保存 {len(history)} 条历史记录")
        except Exception as e:
            logger.error(f"保存历史记录失败: {str(e)}")
            
    def export_history(self):
        """导出历史记录"""
        try:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON文件", "*.json"), ("文本文件", "*.txt"), ("所有文件", "*")],
                title="导出历史记录"
            )
            
            if file_path:
                # 收集历史记录
                history = []
                for item in self.history_tree.get_children():
                    url, title, time = self.history_tree.item(item, "values")
                    history.append({'url': url, 'title': title, 'time': time})
                    
                # 根据文件扩展名决定保存格式
                if file_path.lower().endswith('.json'):
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(history, f, ensure_ascii=False, indent=2)
                else:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        for entry in history:
                            f.write(f"时间: {entry['time']}\n")
                            f.write(f"标题: {entry['title']}\n")
                            f.write(f"链接: {entry['url']}\n")
                            f.write("-" * 50 + "\n")
                
                logger.info(f"历史记录已导出到: {file_path}")
                messagebox.showinfo("成功", "历史记录导出成功！")
        except Exception as e:
            logger.error(f"导出历史记录失败: {str(e)}")
            messagebox.showerror("错误", f"导出历史记录失败: {str(e)}")
            
    def clear_history(self):
        """清空历史记录"""
        try:
            if messagebox.askyesno("确认", "确定要清空所有历史记录吗？"):
                # 清空当前历史记录
                for item in self.history_tree.get_children():
                    self.history_tree.delete(item)
                
                # 保存空历史记录
                self.save_history()
                logger.info("历史记录已清空")
        except Exception as e:
            logger.error(f"清空历史记录失败: {str(e)}")
            
    def add_history_item(self, url, title):
        """添加历史记录项"""
        try:
            current_time = time.strftime("%Y-%m-%d %H:%M:%S")
            
            # 插入到历史记录树的开头
            self.history_tree.insert('', 0, values=(url, title, current_time))
            
            # 保存历史记录
            self.save_history()
        except Exception as e:
            logger.error(f"添加历史记录失败: {str(e)}")
    
    def _cut_text(self, widget):
        """剪切选中的文本到剪贴板"""
        try:
            # 确保控件可编辑
            widget.event_generate("<<Cut>>")
        except Exception:
            pass
    
    def _paste_text(self, widget):
        """从剪贴板粘贴文本"""
        try:
            # 确保控件可编辑
            widget.event_generate("<<Paste>>")
        except Exception:
            pass
    
    def _select_all_text(self, widget):
        """全选文本"""
        widget.selection_range(0, tk.END)
        widget.icursor(tk.END)
    
    def toggle_cookies_frame(self):
        if self.use_cookies.get():
            self.cookies_frame.grid()
        else:
            self.cookies_frame.grid_remove()
    
    def browse_save_path(self):
        path = filedialog.askdirectory(title="选择保存位置")
        if path:
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, path)
    
    def start_download(self):
        # 获取用户输入
        video_url = self.url_entry.get().strip()
        save_path = self.path_entry.get().strip()
        use_cookies = self.use_cookies.get()
        download_method = self.download_method.get()
        quality = self.quality.get()
        
        # 验证输入
        if not video_url:
            messagebox.showerror("错误", "请输入视频URL")
            return
        
        if not video_url.startswith('https://www.bilibili.com/video/'):
            if not messagebox.askyesno("提示", "URL似乎不是B站视频链接，是否继续？"):
                return
        
        if not save_path:
            messagebox.showerror("错误", "请选择保存路径")
            return
        
        # 创建保存目录（如果不存在）
        os.makedirs(save_path, exist_ok=True)
        
        # 解析cookies
        cookies_dict = {}
        if use_cookies:
            cookies_input = self.cookies_text.get(1.0, tk.END).strip()
            if not cookies_input:
                messagebox.showerror("错误", "请输入Cookies内容")
                return
            
            try:
                cookies_format = self.cookies_format.get()
                cookies_dict = parse_cookies(cookies_input, cookies_format)
                logger.info(f"成功解析Cookies，共{len(cookies_dict)}个键值对")
            except Exception as e:
                messagebox.showerror("错误", f"解析Cookies失败: {str(e)}")
                return
        
        # 禁用下载按钮
        self.download_button.config(state='disabled')
        
        # 启动下载线程
        logger.info("准备开始下载...")
        self.download_thread = DownloadThread(
            self, 
            cookies_dict, 
            video_url, 
            save_path, 
            download_method,
            quality
        )
        self.download_thread.daemon = True
        self.download_thread.start()
    
    def on_download_complete(self, success):
        # 启用下载按钮
        self.download_button.config(state='normal')
        
        # 如果下载成功，获取视频标题并添加到历史记录
        if success:
            video_url = self.url_entry.get().strip()
            # 尝试从URL中提取视频标题（简化版）
            try:
                # 从URL中提取BV号作为标题
                import re
                bv_match = re.search(r'BV[A-Za-z0-9]+', video_url)
                if bv_match:
                    video_title = f"视频 {bv_match.group()}"
                else:
                    video_title = "未命名视频"
                
                # 添加到历史记录
                self.add_history_item(video_url, video_title)
            except Exception as e:
                logger.error(f"添加到历史记录失败: {str(e)}")
            
            messagebox.showinfo("完成", "操作已成功完成！")
        else:
            messagebox.showerror("错误", "操作失败，请查看日志获取详细信息")

# 创建启动器脚本
def create_launcher_script():
    launcher_content = f'''
import os
import sys
import subprocess
import json

# 配置
ENV_NAME = "bilibili_downloader"
MAIN_SCRIPT = "{os.path.basename(__file__)}"

# 检查并激活虚拟环境
def check_and_activate_environment():
    # 检查当前是否已在虚拟环境中
    if "conda" in sys.executable.lower() and ENV_NAME in sys.executable.lower():
        print(f"已在虚拟环境 '{{ENV_NAME}}' 中运行")
        return True
    
    # 查找conda位置
    conda_cmd = "conda"
    if os.name == 'nt':
        # Windows系统尝试从常见位置查找conda
        conda_paths = [
            os.path.join(os.environ.get('USERPROFILE', ''), 'miniconda3', 'Scripts', 'conda.exe'),
            os.path.join(os.environ.get('USERPROFILE', ''), 'anaconda3', 'Scripts', 'conda.exe')
        ]
        for path in conda_paths:
            if os.path.exists(path):
                conda_cmd = path
                break
    
    try:
        # 检查环境是否存在
        result = subprocess.run([conda_cmd, 'env', 'list', '--json'], capture_output=True, text=True)
        envs = json.loads(result.stdout)
        
        env_exists = False
        for env_path in envs['envs']:
            if ENV_NAME in os.path.basename(env_path) or env_path.endswith(ENV_NAME):
                env_exists = True
                break
        
        if not env_exists:
            print(f"虚拟环境 '{{ENV_NAME}}' 不存在，正在创建...")
            # 使用environment.yml创建环境
            if os.path.exists('environment.yml'):
                # 创建环境，隐藏控制台窗口
        if os.name == 'nt':  # Windows系统
            subprocess.run(
                [conda_cmd, 'env', 'create', '-f', 'environment.yml'], 
                check=True,
                shell=False,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        else:
            subprocess.run(
                [conda_cmd, 'env', 'create', '-f', 'environment.yml'], 
                check=True
            )
            else:
                print("未找到environment.yml文件，无法创建环境")
                return False
        
        # 使用conda run在虚拟环境中执行脚本
        print(f"正在虚拟环境 '{{ENV_NAME}}' 中启动程序...")
        # 在虚拟环境中运行脚本，隐藏控制台窗口
        if os.name == 'nt':  # Windows系统
            subprocess.run(
                [conda_cmd, 'run', '-n', ENV_NAME, 'python', MAIN_SCRIPT],
                shell=False,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        else:
            subprocess.run(
                [conda_cmd, 'run', '-n', ENV_NAME, 'python', MAIN_SCRIPT]
            )
        return True
    except Exception as e:
        print(f"激活虚拟环境失败: {{str(e)}}")
        return False

if __name__ == "__main__":
    if not check_and_activate_environment():
        # 如果无法激活虚拟环境，尝试直接运行
        print("尝试直接运行程序...")
        # 直接运行程序，隐藏控制台窗口
        if os.name == 'nt':  # Windows系统
            subprocess.run(
                [sys.executable, MAIN_SCRIPT],
                shell=False,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        else:
            subprocess.run([sys.executable, MAIN_SCRIPT])
'''.strip()
    
    launcher_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'launcher.py')
    try:
        with open(launcher_path, 'w', encoding='utf-8') as f:
            f.write(launcher_content)
        logger.info(f"启动器脚本已创建: {launcher_path}")
        
        # 在Windows上创建批处理文件
        if os.name == 'nt':
            bat_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '启动下载器.bat')
            with open(bat_path, 'w', encoding='utf-8') as f:
                f.write(f'@echo off\npython "{launcher_path}"\npause')
            logger.info(f"Windows批处理文件已创建: {bat_path}")
        
        return launcher_path
    except Exception as e:
        logger.error(f"创建启动器脚本失败: {str(e)}")
        return None

# 主函数
def main():
    # 检查是否需要在虚拟环境中运行
    # 对于打包后的程序，跳过虚拟环境检查和启动器创建
    is_frozen = getattr(sys, 'frozen', False)
    if not is_frozen:
        if run_in_virtual_environment():
            sys.exit(0)  # 已在新进程中启动，退出当前进程
        
        # 对于未打包的程序，创建启动器脚本
        create_launcher_script()
    else:
        logger.info("运行的是打包后的可执行文件，跳过创建启动器脚本")
    
    # 创建GUI
    root = tk.Tk()
    app = BilibiliDownloaderGUI(root)
    root.mainloop()

# 包装主函数以捕获所有异常
# 全局变量
logger = None

if __name__ == "__main__":
    try:
        # 初始化日志（临时，直到GUI创建）
        logger = setup_logger()
        logger.info("B站视频下载工具已启动")
        
        # 检查you-get导入状态
        if not HAS_YOU_GET:
            logger.warning("you-get模块导入失败，程序可能无法正常下载视频")
        
        # 检查是否是打包后的程序
        is_frozen = getattr(sys, 'frozen', False)
        if is_frozen:
            logger.info("正在运行打包后的可执行文件")
            # 保存原始的stdout和stderr，以便在需要时恢复
            original_stdout = sys.stdout
            original_stderr = sys.stderr
            
            # 对于打包后的程序，禁用控制台输出
            try:
                sys.stdout = open(os.devnull, 'w')
                sys.stderr = open(os.devnull, 'w')
            except:
                # 如果无法重定向输出，就继续使用原始输出
                pass
        
        main()
    except Exception as e:
        # 发生异常时，创建一个单独的错误日志文件
        try:
            error_log_path = os.path.join(os.path.expanduser('~'), '.bilibili_downloader', 'error.log')
            os.makedirs(os.path.dirname(error_log_path), exist_ok=True)
            with open(error_log_path, 'w', encoding='utf-8') as f:
                f.write(f"程序崩溃时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Python版本: {sys.version}\n")
                f.write(f"是否为打包程序: {is_frozen}\n")
                f.write(f"错误信息: {str(e)}\n\n")
                import traceback
                f.write("错误堆栈:\n")
                f.write(traceback.format_exc())
            
            # 显示错误消息框
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()  # 隐藏主窗口
            messagebox.showerror(
                "程序错误",
                f"程序运行时发生错误。\n\n错误信息: {str(e)}\n\n详细错误日志已保存至:\n{error_log_path}\n\n请查看错误日志获取更多信息。"
            )
        except Exception as inner_e:
            # 如果无法创建日志文件或显示错误消息框，尝试在控制台显示
            try:
                # 尝试恢复原始的stdout和stderr
                if 'original_stdout' in locals() and 'original_stderr' in locals():
                    sys.stdout = original_stdout
                    sys.stderr = original_stderr
                
                print(f"严重错误: 无法创建错误日志或显示错误消息框")
                print(f"原始错误: {str(e)}")
                print(f"内部错误: {str(inner_e)}")
                import traceback
                print("错误堆栈:")
                traceback.print_exc()
                
                # 在控制台等待用户输入，以便用户可以看到错误信息
                input("按Enter键退出...")
            except:
                # 如果所有方法都失败，就静默退出
                pass
        finally:

            sys.exit(1)
