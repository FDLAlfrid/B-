#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vocaloid Toolbox Fusion 构建脚本
自动化打包和发布流程
"""

import os
import sys
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

# 导入版本信息
from version import __version__, BUILD_NUMBER, APP_NAME

# 构建配置
BUILD_CONFIG = {
    "output_dir": f"dist/{APP_NAME.replace(' ', '')}_v{__version__}",
    "exe_name": APP_NAME.replace(" ", ""),
    "include_dirs": [
        "assets",
    ],
    "include_files": [
        "icon.ico",
        "icon.png",
        "version.py",
        "README.md",
    ],
    "clean_build": True,  # 构建前清理
    "create_zip": True,   # 创建压缩包
}

def clean_build_dirs():
    """清理构建目录"""
    print("清理构建目录...")
    dirs_to_clean = ['build', 'dist', '__pycache__']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"  已删除: {dir_name}")
    
    # 清理pyc文件
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file.endswith('.pyc'):
                os.remove(os.path.join(root, file))
        for dir in dirs:
            if dir == '__pycache__':
                pycache_path = os.path.join(root, dir)
                shutil.rmtree(pycache_path)
    print("清理完成")

def run_pyinstaller():
    """运行PyInstaller打包"""
    print(f"\n开始打包 {APP_NAME} v{__version__}...")
    
    # 确保build.spec存在
    if not os.path.exists('build.spec'):
        print("错误: build.spec 文件不存在")
        return False
    
    # 运行PyInstaller
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        'build.spec',
        '--distpath', BUILD_CONFIG["output_dir"],
        '--workpath', 'build',
        '--noconfirm'
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        print("PyInstaller 打包成功")
        return True
    except subprocess.CalledProcessError as e:
        print(f"PyInstaller 打包失败: {e}")
        return False

def copy_dependencies():
    """复制依赖文件到输出目录"""
    print("\n复制依赖文件...")
    output_path = Path(BUILD_CONFIG["output_dir"])
    
    # 创建依赖目录
    deps_dir = output_path / "dependencies"
    deps_dir.mkdir(exist_ok=True)
    
    # 复制包含的目录
    for dir_name in BUILD_CONFIG["include_dirs"]:
        if os.path.exists(dir_name):
            src = Path(dir_name)
            dst = deps_dir / dir_name
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            print(f"  已复制目录: {dir_name}")
    
    # 创建空的data目录（用于运行时存储数据）
    data_dir = deps_dir / "data"
    data_dir.mkdir(exist_ok=True)
    print(f"  已创建目录: data")
    
    # 复制包含的文件
    for file_name in BUILD_CONFIG["include_files"]:
        if os.path.exists(file_name):
            src = Path(file_name)
            dst = deps_dir / file_name
            shutil.copy2(src, dst)
            print(f"  已复制文件: {file_name}")
    
    print("依赖文件复制完成")

def create_zip_package():
    """创建ZIP压缩包"""
    if not BUILD_CONFIG.get("create_zip", False):
        return
    
    print("\n创建ZIP压缩包...")
    output_path = Path(BUILD_CONFIG["output_dir"])
    zip_name = f"{output_path.name}.zip"
    zip_path = output_path.parent / zip_name
    
    try:
        # 删除已存在的zip文件
        if zip_path.exists():
            zip_path.unlink()
        
        # 创建zip文件
        shutil.make_archive(
            str(output_path.parent / output_path.name),
            'zip',
            root_dir=output_path.parent,
            base_dir=output_path.name
        )
        
        # 获取zip文件大小
        zip_size = zip_path.stat().st_size / (1024 * 1024)  # MB
        print(f"  已创建: {zip_name} ({zip_size:.2f} MB)")
    except Exception as e:
        print(f"  创建ZIP失败: {e}")

def create_launcher():
    """创建启动器脚本"""
    print("\n创建启动器...")
    output_path = Path(BUILD_CONFIG["output_dir"])
    exe_name = BUILD_CONFIG["exe_name"]
    
    # 创建Windows批处理启动器
    bat_content = f'''@echo off
chcp 65001 > nul
title {APP_NAME} v{__version__}
echo 正在启动 {APP_NAME}...
echo 版本: v{__version__}
echo 构建号: {BUILD_NUMBER}
echo.

"%~dp0{exe_name}.exe" %*

if errorlevel 1 (
    echo.
    echo 程序异常退出，错误码: %errorlevel%
    pause
)
'''
    
    bat_path = output_path / f"启动_{exe_name}.bat"
    with open(bat_path, 'w', encoding='utf-8') as f:
        f.write(bat_content)
    print(f"  已创建: {bat_path.name}")
    
    # 创建README
    readme_content = f'''# {APP_NAME} v{__version__}

## 启动方式
1. 双击 `启动_{exe_name}.bat` 运行程序
2. 或直接运行 `{exe_name}.exe`

## 目录结构
- `{exe_name}.exe` - 主程序
- `dependencies/` - 依赖文件目录
  - `assets/` - 资源文件（字体、图标等）
  - `data/` - 数据文件（数据库、配置等）

## 版本信息
- 版本: v{__version__}
- 构建号: {BUILD_NUMBER}
- 构建日期: {datetime.now().strftime("%Y-%m-%d")}

## 注意事项
- 首次启动可能需要从网络获取数据，请确保网络连接正常
- 数据文件会自动保存在 dependencies/data/ 目录下
- 请勿删除 dependencies 目录，否则程序无法正常运行
'''
    
    readme_path = output_path / "README.txt"
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    print(f"  已创建: {readme_path.name}")

def create_version_info():
    """创建版本信息文件"""
    print("\n创建版本信息文件...")
    output_path = Path(BUILD_CONFIG["output_dir"])
    
    version_info = f'''Application: {APP_NAME}
Version: {__version__}
Build Number: {BUILD_NUMBER}
Build Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Python Version: {sys.version}
'''
    
    version_path = output_path / "VERSION.txt"
    with open(version_path, 'w', encoding='utf-8') as f:
        f.write(version_info)
    print(f"  已创建: {version_path.name}")

def verify_build():
    """验证构建结果"""
    print("\n验证构建结果...")
    output_path = Path(BUILD_CONFIG["output_dir"])
    exe_name = BUILD_CONFIG["exe_name"]
    
    # 检查主程序是否存在
    exe_path = output_path / f"{exe_name}.exe"
    if not exe_path.exists():
        print(f"  错误: 主程序不存在: {exe_path}")
        return False
    
    # 获取文件大小
    exe_size = exe_path.stat().st_size / (1024 * 1024)  # MB
    print(f"  主程序大小: {exe_size:.2f} MB")
    
    # 检查依赖目录
    deps_dir = output_path / "dependencies"
    if deps_dir.exists():
        deps_size = sum(f.stat().st_size for f in deps_dir.rglob('*') if f.is_file()) / (1024 * 1024)
        print(f"  依赖文件大小: {deps_size:.2f} MB")
        print(f"  总大小: {exe_size + deps_size:.2f} MB")
    
    print("构建验证通过")
    return True

def main():
    """主构建流程"""
    print("=" * 60)
    print(f"{APP_NAME} 构建脚本")
    print(f"版本: v{__version__}")
    print(f"构建号: {BUILD_NUMBER}")
    print("=" * 60)
    
    # 清理
    if BUILD_CONFIG["clean_build"]:
        clean_build_dirs()
    
    # 打包
    if not run_pyinstaller():
        print("\n构建失败!")
        return 1
    
    # 复制依赖
    copy_dependencies()
    
    # 创建启动器
    create_launcher()
    
    # 创建版本信息
    create_version_info()
    
    # 验证
    if not verify_build():
        print("\n构建验证失败!")
        return 1
    
    # 创建ZIP压缩包
    create_zip_package()
    
    print("\n" + "=" * 60)
    print("构建成功!")
    print(f"输出目录: {BUILD_CONFIG['output_dir']}")
    if BUILD_CONFIG.get("create_zip", False):
        zip_name = f"{Path(BUILD_CONFIG['output_dir']).name}.zip"
        print(f"压缩包: {zip_name}")
    print("=" * 60)
    return 0

if __name__ == "__main__":
    sys.exit(main())
