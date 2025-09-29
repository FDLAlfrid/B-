# B站视频下载工具

一个简单的B站视频下载工具，支持带实时日志的TK图形界面。

## 功能特点

- 🎨 美观直观的图形用户界面（GUI）
- 📋 实时操作日志显示
- 🔄 自动检测和切换到指定的conda虚拟环境
- 📥 支持两种下载方式：
  - Requests：仅获取视频页面内容
  - You-Get：下载完整视频
- 🍪 支持Cookies登录（JSON或Header格式）
- 🎞️ 多画质下载：通过正确的Cookies设置支持720p及以上画质下载
- 📁 自定义保存路径
- 🎯 错误处理和友好的用户提示
- 🚀 多线程下载，不阻塞界面

## 快速开始

### 方法一：使用启动器脚本（推荐）

1. 确保已安装[Anaconda](https://www.anaconda.com/products/distribution)或[Miniconda](https://docs.conda.io/en/latest/miniconda.html)

2. 打开命令行工具，导航到项目目录：
   ```
   cd d:\Alfrid\Desktop\BLD3.0
   ```

3. 运行启动器脚本：
   ```
   python launcher.py
   ```

   启动器会自动检查并创建/激活虚拟环境，然后启动GUI界面。

### 方法二：直接运行主程序

1. 创建并激活conda环境：
   ```
   conda env create -f environment.yml
   conda activate bilibili_downloader
   ```

2. 运行主程序：
   ```
   python bilibili_downloader.py
   ```

### 方法三：使用可执行文件（EXE）

如果项目已打包成可执行文件，可以直接双击运行`B站视频下载器.exe`文件启动程序。

详细打包方法请参考本文档的"打包为可执行文件（EXE）"章节。

## 使用指南

1. **视频URL**：输入B站视频链接（通常以 `https://www.bilibili.com/video/` 开头）

2. **保存路径**：点击"浏览"按钮选择视频保存位置

3. **Cookies设置**（可选）：
   - 勾选"使用Cookies"复选框
   - 选择Cookies格式（JSON或Header）
   - 在文本框中粘贴Cookies内容
   - （提示：登录B站后通过浏览器开发者工具获取Cookies）

4. **下载方式**：
   - **Requests**：仅获取视频页面内容，用于测试
   - **You-Get**：下载完整视频文件

5. 点击"开始下载"按钮启动任务

6. 查看实时日志和下载进度

## 环境设置详解

### 自动环境管理

程序会自动执行以下操作：
1. 检查是否已在 `bilibili_downloader` 虚拟环境中运行
2. 如果不在，尝试查找或创建该环境
3. 在合适的环境中启动程序

### 手动创建环境

如果自动环境管理失败，可以手动创建环境：

```
conda env create -f environment.yml
```

### 验证环境

```
conda activate bilibili_downloader
python -c "import requests; import you_get; print('所有依赖已成功安装！')"
```

## 常见问题解决

### 问题：程序无法启动或缺少依赖

**解决方法：**
- 确保已安装Anaconda或Miniconda
- 手动创建环境：`conda env create -f environment.yml`
- 激活环境：`conda activate bilibili_downloader`
- 手动安装缺失的依赖：`pip install 缺失的包名`

### 问题：下载失败或提示权限不足

**解决方法：**
- 尝试使用Cookies登录
- 检查网络连接是否稳定
- 确认保存路径有写入权限
- 对于付费或会员视频，确保Cookies包含有效的登录信息

### 问题：只能下载480P画质，无法下载更高画质

**解决方法：**
- B站的720P及以上画质需要登录才能下载
- 确保正确配置了Cookies（通过浏览器开发者工具获取）
- 推荐使用JSON格式的Cookies，包含SESSDATA等关键信息
- 程序会自动将Cookies保存为临时文件并传递给下载工具

### 问题：日志显示'unsupported cookies format'错误

**解决方法：**
- 这是you-get对Cookies格式的要求导致的
- 程序已自动处理此问题，会将Cookies保存为临时文件
- 确保提供的Cookies格式正确（JSON或Header）
- 如问题持续，尝试清空Cookies后重新获取并输入

### 问题：日志显示乱码

**解决方法：**
- 确保使用支持UTF-8编码的终端
- 在Windows上，建议使用Anaconda Prompt而不是命令提示符

## 依赖说明

- Python 3.9：基础编程语言环境
- requests：用于发送HTTP请求
- you-get：视频下载核心库
- ffmpeg：底层视频处理工具
- tkinter：图形用户界面库

## 项目文件说明

- `bilibili_downloader.py`：主程序文件，包含完整的GUI和下载功能
- `launcher.py`：启动器脚本，负责自动环境管理
- `environment.yml`：conda环境配置文件
- `README.md`：项目说明文档

## 打包为可执行文件（EXE）

如果你希望将本项目打包为不依赖conda环境的可执行文件（EXE），可以使用PyInstaller工具。以下是详细的打包步骤和优化方法：

### 1. 安装PyInstaller

首先确保你在conda环境中安装了PyInstaller：

```
conda activate bilibili_downloader
pip install pyinstaller
```

### 2. 执行打包命令

在项目根目录下执行以下命令：

```
pyinstaller --onefile --windowed --icon=icon.png --name=B站视频下载器 bilibili_downloader.py
```

### 3. 参数说明

- `--onefile`：将所有内容打包成单个可执行文件
- `--windowed`：不显示控制台窗口（GUI程序专用）
- `--icon=icon.png`：设置程序图标（如果没有图标文件可以省略）
- `--name=B站视频下载器`：设置生成的可执行文件名称

### 4. 自定义spec文件（重要）

首次执行上述命令后，会生成一个`.spec`文件。为了解决打包后可能出现的闪退问题，建议修改该文件以包含所有必要的依赖：

1. 打开生成的`B站视频下载器.spec`文件
2. 添加以下内容：
   ```python
   import sys
   import os
   
   sys.setrecursionlimit(5000)
   
   # 获取you-get的安装位置
   try:
       import you_get
       you_get_path = os.path.dirname(you_get.__file__)
   except:
       you_get_path = ''
   ```
3. 在`Analysis`部分添加必要的依赖：
   ```python
   datas=[(you_get_path, 'you_get')] if you_get_path else [],
   hiddenimports=[
       'requests',
       'tkinter', 
       'tkinter.ttk', 
       'tkinter.scrolledtext',
       'tkinter.filedialog',
       'tkinter.messagebox',
       'you_get',
       'you_get.extractors',
       'you_get.common',
       'you_get.util',
       'json', 
       'logging',
       'subprocess',
       'time',
       'threading',
       'shutil',
       'tempfile'
   ],
   ```
4. 使用修改后的spec文件重新打包：
   ```
   pyinstaller B站视频下载器.spec
   ```

### 5. 获取打包结果

打包完成后，可执行文件会生成在项目根目录的`dist`文件夹中。

### 6. 注意事项

- 首次打包可能会比较慢，请耐心等待
- 打包后的文件大小可能会较大，这是因为PyInstaller会将Python解释器和所有依赖库一起打包
- **重要**：如果打包后的程序出现闪退问题，程序会自动在用户目录下的`.bilibili_downloader`文件夹中生成错误日志文件，帮助排查问题
- 程序运行时会自动禁用控制台输出，避免黑窗口出现
- 对于打包后的程序，会跳过创建启动器脚本的步骤

### 7. 错误排查

如果打包后的程序无法正常运行：

1. 检查用户目录下的`.bilibili_downloader`文件夹中的错误日志
2. 确保你的conda环境中已正确安装所有依赖库
3. 尝试使用修改后的spec文件重新打包
4. 如问题依旧，可尝试在非windowed模式下打包以便查看控制台输出：
   ```
   pyinstaller --onefile --icon=icon.png --name=B站视频下载器 bilibili_downloader.py
   ```
