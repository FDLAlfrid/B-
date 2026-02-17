# BeeWare打包指南

## 概述

使用BeeWare/Briefcase将Python应用打包为Android APK，完全在Windows/GXDE上运行，无需Ubuntu。

## 目录结构

```
BB/
├── pyproject.toml              # BeeWare配置文件
├── src/
│   └── bilibili_query/
│       └── __init__.py       # 主应用代码（Toga GUI）
├── resources/
│   └── icon                # 应用图标（需要添加）
├── tests/
│   └── __init__.py         # 测试代码
├── main.py                 # Kivy版本（旧）
├── buildozer.spec          # Buildozer配置（旧）
└── find_bv_info.py         # 原始命令行版本
```

## 安装依赖

```powershell
pip install briefcase
```

## 构建步骤

### 1. 创建应用图标

创建一个512x512的PNG图标，保存为：
```
resources/icon.png
```

### 2. 初始化项目（可选）

```powershell
briefcase create android
```

### 3. 构建APK

```powershell
briefcase build android
```

### 4. 运行应用（可选）

```powershell
briefcase run android
```

### 5. 打包发布版本（可选）

```powershell
briefcase package android
```

## 配置说明

### pyproject.toml

```toml
[tool.briefcase]
project_name = "bilibili_query"
bundle = "org.test"
version = "1.0.0"
requires = [
    "requests>=2.31.0",
]

[tool.briefcase.app.bilibili_query.android]
requires = [
    "toga-android>=0.3.0",
]
```

## 预期输出

构建完成后，APK文件位于：
```
linux/android/gradle/bilibili_query/app/build/outputs/apk/debug/app-debug.apk
```

## 构建时间

- **首次构建**: 10-20分钟（下载依赖）
- **后续构建**: 5-10分钟

## 常见问题

### 问题1: 缺少Android SDK

Briefcase会自动下载Android SDK，无需手动安装。

### 问题2: 构建失败

检查：
1. 是否安装了Java JDK
2. 是否有足够的磁盘空间
3. 网络连接是否正常

### 问题3: 图标问题

确保图标是512x512的PNG格式。

## 优势

| 特点 | BeeWare | Buildozer |
|-----|----------|------------|
| Windows支持 | ✅ 原生支持 | ⚠️ 需要WSL/Ubuntu |
| 构建速度 | ✅ 较快 | ⚠️ 较慢 |
| GUI框架 | Toga | Kivy |
| 学习曲线 | ⚠️ 需要学习Toga | ✅ Kivy更成熟 |

## 参考资料

- [BeeWare官方文档](https://beeware.org/)
- [Briefcase文档](https://briefcase.readthedocs.io/)
- [Toga文档](https://toga.readthedocs.io/)
