# -*- mode: python ; coding: utf-8 -*-

from version import __version__, APP_NAME

block_cipher = None

# 应用名称和版本
app_name = APP_NAME.replace(' ', '')
exe_name = f'{app_name}_v{__version__}'

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # 资源文件
        ('assets/fonts', 'assets/fonts'),
        ('assets/icons', 'assets/icons'),
        ('config', 'config'),
        ('services', 'services'),
        ('utils', 'utils'),
        # 数据目录（运行时创建）
    ],
    hiddenimports=[
        # PyQt5 相关
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'PyQt5.QtMultimedia',
        'PyQt5.QtMultimediaWidgets',
        # Flask 相关
        'flask',
        'flask_cors',
        'werkzeug',
        'jinja2',
        # 网络请求
        'requests',
        'urllib3',
        'charset_normalizer',
        # 数据处理
        'numpy',
        'pandas',
        'sklearn',
        'jieba',
        'networkx',
        # 数据库
        'sqlalchemy',
        # 其他依赖
        'bs4',
        'lxml',
        'PIL',
        'fake_useragent',
        'pywin32',
        # 版本信息
        'version',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=exe_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icons/icon.ico',
    version='version_info.txt' if os.path.exists('version_info.txt') else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=exe_name,
)

# 创建额外的依赖目录
import os
from pathlib import Path

# 创建data目录（运行时数据）
data_dir = Path('dist') / exe_name / 'data'
data_dir.mkdir(parents=True, exist_ok=True)
(data_dir / 'community').mkdir(exist_ok=True)
(data_dir / 'cover_cache').mkdir(exist_ok=True)

# 复制配置文件到输出目录
config_src = Path('config')
if config_src.exists():
    config_dst = Path('dist') / exe_name / 'config'
    import shutil
    if config_dst.exists():
        shutil.rmtree(config_dst)
    shutil.copytree(config_src, config_dst)

print(f"\n{'='*60}")
print(f"打包完成!")
print(f"输出目录: dist/{exe_name}")
print(f"主程序: dist/{exe_name}/{exe_name}.exe")
print(f"{'='*60}\n")
