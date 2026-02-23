# B站BV号查询 - Android APK
注意：Kivy框架版本存在打包限制问题，目前已经暂停开发转向QT和其他框架。
将Python命令行工具打包为Android APK应用，使用Kivy框架创建GUI界面。

## 项目结构

```
BB/
├── main.py                    # Kivy GUI应用主程序
├── buildozer.spec             # Buildozer配置文件
├── requirements.txt           # Python依赖列表
├── find_bv_info.py           # 原始命令行版本
├── .github/
│   └── workflows/
│       └── build.yml          # GitHub Actions工作流
└── docs/                    # 文档目录
    ├── BUILD_GUIDE.md         # 通用打包指南
    ├── DEVELOPMENT_LOG.md     # 开发日志
    ├── GITHUB_ACTIONS_GUIDE.md # GitHub Actions使用指南
    ├── GXDE_INSTALL_GUIDE.md  # GXDE系统专用指南
    └── USE_EXISTING_REPO.md   # 使用现有仓库指南
```

## 快速开始

### 方法1：使用GitHub Actions（推荐）

无需本地环境，使用GitHub自动构建APK：

1. 创建GitHub仓库或使用现有仓库
2. 上传代码到仓库
3. 等待GitHub Actions自动构建
4. 在Actions页面下载APK

详细步骤请查看 [docs/USE_EXISTING_REPO.md](docs/USE_EXISTING_REPO.md)

### 方法2：本地打包

需要Linux环境（WSL2、虚拟机等）：

1. 安装依赖
2. 创建虚拟环境
3. 安装Buildozer
4. 运行 `buildozer android debug`

详细步骤请查看 [docs/BUILD_GUIDE.md](docs/BUILD_GUIDE.md)

## 功能特性

- ✅ 单BV号查询（显示详细信息）
- ✅ BV号 ↔ AV号 互转
- ✅ 批量查询BV号并导出JSON
- ✅ 简洁的触摸界面，适合手机操作

## 技术栈

- **GUI框架**: Kivy 2.3.0
- **网络请求**: requests 2.31.0
- **打包工具**: Buildozer
- **目标平台**: Android (arm64-v8a, armeabi-v7a)

## 文档说明

- [docs/BUILD_GUIDE.md](docs/BUILD_GUIDE.md) - 通用打包指南
- [docs/DEVELOPMENT_LOG.md](docs/DEVELOPMENT_LOG.md) - 开发日志，记录遇到的问题和解决方案
- [docs/GITHUB_ACTIONS_GUIDE.md](docs/GITHUB_ACTIONS_GUIDE.md) - GitHub Actions详细使用指南
- [docs/GXDE_INSTALL_GUIDE.md](docs/GXDE_INSTALL_GUIDE.md) - GXDE系统专用安装指南
- [docs/USE_EXISTING_REPO.md](docs/USE_EXISTING_REPO.md) - 使用现有GitHub仓库的指南

## 开发日志

详细的开发过程、遇到的问题和解决方案请查看 [docs/DEVELOPMENT_LOG.md](docs/DEVELOPMENT_LOG.md)

## 许可证

MIT License
