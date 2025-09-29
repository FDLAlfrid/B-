# -*- mode: python ; coding: utf-8 -*-

import sys
import os

sys.setrecursionlimit(5000)

# 获取所有需要的数据文件
additional_datas = []

# 添加必要的数据文件路径
try:
    # 查找并添加you-get的extractors目录
    import you_get
    you_get_path = os.path.dirname(you_get.__file__)
    extractors_dir = os.path.join(you_get_path, 'extractors')
    if os.path.exists(extractors_dir):
        additional_datas.append((extractors_dir, 'you_get/extractors'))
        print(f"已添加you-get提取器目录: {extractors_dir}")
except ImportError:
    print("警告: 未能找到you-get模块")

a = Analysis(
    ['bilibili_downloader.py'],
    pathex=['d:\\Alfrid\\Desktop\\BLD3.0'],
    binaries=[],
    datas=additional_datas,
    hiddenimports=[
        # 核心依赖库
        'requests',
        'urllib3',
        'chardet',
        'certifi',
        'idna',
        
        # you-get相关模块
    'you_get',
    'you_get.common',
    'you_get.downloader',
    'you_get.downloader.dash',
    'you_get.downloader.hls',
    'you_get.downloader.mp4',
    'you_get.extractors',
    'you_get.extractors.bilibili',
    'you_get.extractors.acfun',
    'you_get.extractors.bilibili_audio',
    'you_get.util',
    'you_get.version',
    'you_get.processor',
    'you_get.parser',
    'you_get.config',
    # 解决'NoneType' object has no attribute 'buffer'问题
    'io',
    'builtins',
    'platform',
    'codecs'
        
        # tkinter模块
        'tkinter',
        'tkinter.ttk',
        'tkinter.scrolledtext',
        'tkinter.filedialog',
        'tkinter.messagebox',
        
        # 标准库
        'json',
        'logging',
        'subprocess',
        'time',
        'threading',
        'shutil',
        'tempfile',
        'os',
        'sys'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='B站视频下载器',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # 禁用UPX以提高兼容性
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 禁用控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.png'],
)
