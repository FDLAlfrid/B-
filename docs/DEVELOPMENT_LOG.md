# B站BV号查询 - APK打包开发日志

## 项目概述
将Python命令行工具打包为Android APK应用，使用Kivy框架创建GUI界面，Buildozer进行打包。

## 开发时间
2026-02-17

## 技术栈
- **GUI框架**: Kivy 2.3.0
- **网络请求**: requests 2.31.0
- **打包工具**: Buildozer
- **目标平台**: Android (arm64-v8a, armeabi-v7a)

---

## 遇到的问题与解决方案

### 问题1: libtinfo5包不可用
**环境**: WSL2 Ubuntu
**错误信息**:
```
Package libtinfo5:mips64el is not available
```

**原因**: Ubuntu 22.04/24.04中libtinfo5已被libtinfo6替代

**解决方案**:
- Ubuntu 22.04/24.04: 使用 `libtinfo6`
- Ubuntu 20.04及更早: 使用 `libtinfo5`
- 通用方案: 使用 `libncurses-dev` 替代

**命令**:
```bash
sudo apt install -y libncurses-dev
```

---

### 问题2: GXDE系统软件源配置问题
**环境**: GXDE Linux
**错误信息**:
```
Error: Unable to locate package python3-pip
Error: Unable to locate package openjdk-17-jdk
Error: Package 'autoconf' has no installation candidate
```

**原因**: GXDE使用自定义软件源，部分包不可用

**解决方案**: 分步安装，跳过不可用的包，Buildozer会自动下载缺失依赖

**命令**:
```bash
sudo apt update
sudo apt install -y python3 python3-pip
sudo apt install -y default-jdk
sudo apt install -y build-essential
sudo apt install -y zlib1g-dev libffi-dev libssl-dev pkg-config
sudo apt install -y git curl wget
```

---

### 问题3: Python 3.13 PEP 668限制
**环境**: Python 3.13
**错误信息**:
```
error: externally-managed-environment
× This environment is externally managed
```

**原因**: Python 3.13禁止直接用pip安装到系统环境（PEP 668）

**解决方案**: 使用虚拟环境

**命令**:
```bash
python3 -m venv buildozer_env
source buildozer_env/bin/activate
pip install buildozer
```

---

### 问题4: venv创建失败
**环境**: Python 3.13
**错误信息**:
```
Error: Command '['/mnt/d/Alfrid/Desktop/BB/buildozer_env/bin/python3', '-m', 'ensurepip', '--upgrade', '--default-pip']' returned non-zero exit status 1.
```

**原因**: Python 3.13的venv模块需要 `python3-full` 包，且ensurepip存在问题

**尝试的解决方案**:
1. 安装 `python3-full` - 已安装但venv仍然失败
2. 使用 `--without-pip` 创建venv - 需要手动安装pip
3. 使用pipx - 需要额外安装
4. 使用Miniconda - 用户仅在Windows中安装，不想在Linux中安装

**最终解决方案**: 放弃本地环境配置，使用GitHub Actions云端构建

**原因**:
- 本地环境配置复杂，遇到多个依赖问题
- 用户不想在WSL中折腾环境
- Miniconda仅在Windows中，Linux环境需要重新安装
- 可能需要换源等额外配置
- GitHub Actions完全免费，自动处理所有依赖

**命令**:
```bash
# 无需本地环境，直接使用GitHub Actions
# 1. 创建GitHub仓库
# 2. 上传代码
# 3. 自动构建APK
# 4. 下载APK
```

---

## 最终解决方案：GitHub Actions

### 为什么选择GitHub Actions？

1. **无需本地环境** - 不需要配置Python、Java、Android SDK等
2. **自动换源** - GitHub Actions自动处理依赖下载
3. **云端构建** - 使用GitHub的服务器，不占用本地资源
4. **完全免费** - 公开仓库完全免费使用
5. **自动触发** - 推送代码自动构建，也可以手动触发

### 使用步骤

详见 [GITHUB_ACTIONS_GUIDE.md](file:///d:\Alfrid\Desktop\BB\GITHUB_ACTIONS_GUIDE.md)

简述：
1. 创建GitHub仓库
2. 上传 `main.py`、`buildozer.spec`、`requirements.txt`、`.github/workflows/build.yml`
3. 推送代码，自动构建APK
4. 在Actions页面下载APK

---

## 最终解决方案（本地环境备选）

### 方案1: 使用python3-full（不推荐，已验证失败）
```bash
sudo apt install -y python3-full
rm -rf buildozer_env
python3 -m venv buildozer_env
source buildozer_env/bin/activate
pip install --upgrade pip
pip install buildozer
cd /mnt/d/Alfrid/Desktop/BB
buildozer android debug
```

### 方案2: 使用Miniconda（不推荐，需要Linux环境）
```bash
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh -b -p $HOME/miniconda3
~/miniconda3/bin/conda init bash
source ~/.bashrc
conda create -n buildozer python=3.11
conda activate buildozer
pip install buildozer
cd /mnt/d/Alfrid/Desktop/BB
buildozer android debug
```

### 方案3: 强制安装（不推荐，有风险）
```bash
pip3 install buildozer --break-system-packages
buildozer android debug
```

### 方案4: GitHub Actions（推荐，最终选择）
无需本地环境，使用GitHub自动构建

---

## 文件结构

```
BB/
├── main.py                    # Kivy GUI应用主程序
├── buildozer.spec             # Buildozer配置文件
├── requirements.txt           # Python依赖列表
├── install_deps.sh            # 依赖安装脚本
├── BUILD_GUIDE.md             # 通用打包指南
├── GXDE_INSTALL_GUIDE.md     # GXDE系统专用指南
├── DEVELOPMENT_LOG.md        # 本文件（开发日志）
└── find_bv_info.py           # 原始命令行版本
```

---

## Buildozer配置要点

### buildozer.spec关键配置
```ini
[app]
title = B站BV号查询
package.name = bilibili_query
package.domain = org.test
version = 1.0.0
requirements = python3,kivy,requests,pyjnius
orientation = portrait
fullscreen = 0
android.permissions = INTERNET

android.api = 33
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a,armeabi-v7a
```

---

## 打包流程

1. **安装依赖**: 运行 `install_deps.sh`
2. **创建虚拟环境**: `python3 -m venv buildozer_env`
3. **激活环境**: `source buildozer_env/bin/activate`
4. **安装Buildozer**: `pip install buildozer`
5. **开始打包**: `buildozer android debug`

---

## 预期输出

首次打包会下载：
- Android SDK (~1-2GB)
- Android NDK (~1-2GB)
- 其他依赖包

打包时间: 20-60分钟（取决于网速）

输出文件:
```
bin/bilibili_query-1.0.0-arm64-v8a-debug.apk
```

---

## 经验总结

### 1. Linux发行版差异
不同Linux发行版的软件包名称和版本差异很大，需要根据实际情况调整安装命令。

### 2. Python版本兼容性
Python 3.13引入了PEP 668，强制使用虚拟环境，需要提前规划好环境管理方案。

### 3. Buildozer依赖管理
Buildozer会在首次运行时自动下载Android SDK/NDK，不需要手动安装，但需要确保网络稳定。

### 4. 虚拟环境的重要性
使用虚拟环境可以避免污染系统Python环境，也更容易管理依赖版本。

### 5. 备选方案的重要性
当本地环境配置遇到问题时，GitHub Actions等云端构建方案是很好的备选。

---

## 后续优化方向

1. **应用图标**: 添加512x512的icon.png
2. **应用签名**: 配置release签名
3. **多架构支持**: 优化APK大小
4. **错误处理**: 增强网络错误处理
5. **UI优化**: 改进移动端用户体验

---

## 参考资料

- [Kivy官方文档](https://kivy.org/doc/stable/)
- [Buildozer官方文档](https://buildozer.readthedocs.io/)
- [PEP 668 - Marking Python base environments as "externally managed"](https://peps.python.org/pep-0668/)
- [B站API文档](https://github.com/SocialSisterYi/bilibili-API-doc)

---

## 开发者备注

本项目在开发过程中遇到了多个环境配置问题，特别是Python 3.13的新特性和GXDE系统的软件源问题。通过不断尝试和调整，最终找到了可行的解决方案。

建议后续开发者在类似项目中：
1. 提前了解目标系统的Python版本和软件源配置
2. 优先使用虚拟环境管理依赖
3. 准备多个备选方案以应对环境问题
4. 详细记录遇到的问题和解决方案
