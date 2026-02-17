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

### 问题5: GitHub Actions - Cython未找到
**环境**: GitHub Actions Ubuntu
**错误信息**:
```
# Search for Cython (cython)
# Cython (cython) not found, please install it.
Error: Process completed with exit code 1.
```

**原因**: Buildozer没有正确读取buildozer.spec中的requirements

**解决方案**: 在GitHub Actions工作流中显式安装Cython

**修改内容**:
```yaml
- name: Install Buildozer
  run: |
    pip install buildozer cython
```

**同时更新buildozer.spec**:
```ini
requirements = python3,kivy,requests,pyjnius,openssl,cryptography,cython
```

**同时更新requirements.txt**:
```
kivy==2.3.0
requests==2.31.0
pyjnius==1.6.1
cython
```

---

### 问题6: GitHub Actions - Android SDK许可证问题
**环境**: GitHub Actions Ubuntu
**错误信息**:
```
June 2014.
---------------------------------------
Accept? (y/N): Skipping following packages as the license is not accepted:
Android SDK Build-Tools 37-rc1
The following packages can not be installed since their licenses or those of the packages they depend on were not accepted:
build-tools;37.0.0-rc1
```

**原因**: Android SDK需要手动接受许可证，GitHub Actions无法交互

**解决方案1**: 使用环境变量
```yaml
- name: Build APK
  env:
    ANDROID_ACCEPT_LICENSES: "y"
  run: |
    yes | buildozer android debug
```

**解决方案2**: 在buildozer.spec中添加配置
```ini
[buildozer]
log_level = 2
warn_on_root = 1
android.accept_sdk_license = True
```

---

### 问题7: GitHub Actions - libffi autoconf编译错误
**环境**: GitHub Actions Ubuntu 24
**错误信息**:
```
configure.ac:215: error: possibly undefined macro: LT_SYS_SYMBOL_USCORE
If this token and others are legitimate, please use m4_pattern_allow.
See the Autoconf documentation.
autoreconf: error: /usr/bin/autoconf failed with exit status: 1
```

**原因**: 
- libffi库在编译时遇到autoconf问题
- NDK 25b在较新的Ubuntu系统上存在libtool/autoconf兼容性问题
- libtool版本与autoconf版本不匹配

**尝试的解决方案**:
1. 添加 `hostpython3` 到requirements - 无效
2. 移除 `openssl` 和 `cryptography` 依赖 - 无效
3. 更新NDK版本到27b - **有效**

**最终解决方案**: 更新NDK版本

**修改buildozer.spec**:
```ini
android.ndk = 27b
```

**原因**: NDK 27b包含更新的工具链，能更好地处理libffi的编译

---

## 最终解决方案：GitHub Actions

### 为什么选择GitHub Actions？

1. **无需本地环境** - 不需要配置Python、Java、Android SDK等
2. **自动换源** - GitHub Actions自动处理依赖下载
3. **云端构建** - 使用GitHub的服务器，不占用本地资源
4. **完全免费** - 公开仓库完全免费使用
5. **自动触发** - 推送代码自动构建，也可以手动触发

### 使用步骤

详见 [GITHUB_ACTIONS_GUIDE.md](file:///d:\Alfrid\Desktop\BB\docs\GITHUB_ACTIONS_GUIDE.md)

简述：
1. 创建GitHub仓库
2. 上传 `main.py`、`buildozer.spec`、`requirements.txt`、`.github/workflows/build.yml`
3. 推送代码，自动构建APK
4. 在Actions页面下载APK

---

## GitHub Actions配置详解

### 工作流文件 (.github/workflows/build.yml)

```yaml
name: Build APK
on:
  push:
    branches: [ main, master ]
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install Buildozer
      run: |
        pip install buildozer cython
    
    - name: Build APK
      env:
        ANDROID_ACCEPT_LICENSES: "y"
      run: |
        yes | buildozer android debug
    
    - name: Upload APK
      uses: actions/upload-artifact@v4
      with:
        name: bilibili-query-apk
        path: bin/*.apk
        retention-days: 30
```

### 关键配置说明

| 配置项 | 说明 |
|-------|------|
| `runs-on: ubuntu-latest` | 使用最新的Ubuntu环境 |
| `python-version: '3.11'` | 使用Python 3.11（Buildozer推荐） |
| `pip install buildozer cython` | 显式安装Cython避免编译错误 |
| `ANDROID_ACCEPT_LICENSES: "y"` | 自动接受Android SDK许可证 |
| `yes | buildozer android debug` | 自动确认所有交互式提示 |
| `retention-days: 30` | APK保留30天 |

---

## Buildozer配置详解

### buildozer.spec完整配置

```ini
[app]

title = B站BV号查询
package.name = bilibili_query
package.domain = org.test

source.include_exts = py,png,jpg,kv,atlas,json
source.dir = .

version = 1.0.0

requirements = python3,kivy,requests,pyjnius,cython

orientation = portrait

fullscreen = 0

android.permissions = INTERNET

android.api = 33
android.minapi = 19
android.ndk = 27b
android.archs = arm64-v8a,armeabi-v7a

[buildozer]

log_level = 2

warn_on_root = 1

android.accept_sdk_license = True
```

### 配置项说明

| 配置项 | 值 | 说明 |
|-------|-----|------|
| `title` | B站BV号查询 | 应用标题 |
| `package.name` | bilibili_query | 包名 |
| `package.domain` | org.test | 域名（反向域名格式） |
| `version` | 1.0.0 | 版本号 |
| `requirements` | python3,kivy,requests,pyjnius,cython | Python依赖 |
| `orientation` | portrait | 屏幕方向（portrait=竖屏） |
| `fullscreen` | 0 | 是否全屏（0=否） |
| `android.permissions` | INTERNET | Android权限 |
| `android.api` | 33 | 目标SDK版本（Android 13） |
| `android.minapi` | 19 | 最低SDK版本（Android 4.4） |
| `android.ndk` | 27b | NDK版本 |
| `android.archs` | arm64-v8a,armeabi-v7a | 支持的CPU架构 |
| `log_level` | 2 | 日志级别（2=详细） |
| `android.accept_sdk_license` | True | 自动接受SDK许可证 |

---

## 依赖管理

### buildozer.spec vs requirements.txt

| 文件 | 用途 | 内容 |
|-----|------|------|
| `buildozer.spec` | python-for-android | 包含特殊包（python3, hostpython3） |
| `requirements.txt` | 本地Python环境 | 仅包含标准pip包 |

### 当前依赖列表

#### buildozer.spec
```ini
requirements = python3,kivy,requests,pyjnius,cython
```

#### requirements.txt
```
kivy==2.3.0
requests==2.31.0
pyjnius==1.6.1
cython
```

### 依赖说明

| 依赖 | 版本 | 用途 |
|-----|------|------|
| python3 | - | Python运行时 |
| kivy | 2.3.0 | GUI框架 |
| requests | 2.31.0 | HTTP请求 |
| pyjnius | 1.6.1 | Java接口 |
| cython | - | C扩展编译 |

---

## 文件结构

```
BB/
├── main.py                    # Kivy GUI应用主程序
├── buildozer.spec             # Buildozer配置文件
├── requirements.txt           # Python依赖列表
├── .github/
│   └── workflows/
│       └── build.yml          # GitHub Actions工作流
├── docs/
│   ├── BUILD_GUIDE.md         # 通用打包指南
│   ├── COMPLETE_TUTORIAL.md   # 完整教程
│   ├── GITHUB_ACTIONS_GUIDE.md # GitHub Actions指南
│   ├── GXDE_INSTALL_GUIDE.md # GXDE系统专用指南
│   └── 20260217_DEVELOPMENT_LOG.md # 本文件（开发日志）
└── find_bv_info.py           # 原始命令行版本
```

---

## 打包流程

### 本地打包（不推荐）
```bash
# 1. 安装依赖
sudo apt install -y build-essential git libffi-dev libssl-dev pkg-config

# 2. 创建虚拟环境
python3 -m venv buildozer_env
source buildozer_env/bin/activate

# 3. 安装Buildozer
pip install buildozer cython

# 4. 开始打包
cd /path/to/project
buildozer android debug
```

### GitHub Actions打包（推荐）
```bash
# 1. 初始化Git仓库
git init
git add .
git commit -m "Initial commit"

# 2. 创建GitHub仓库并推送
git remote add origin https://github.com/username/repo.git
git branch -M main
git push -u origin main

# 3. 访问Actions页面查看构建
# https://github.com/username/repo/actions

# 4. 下载APK
# 构建完成后在Actions页面下载
```

---

## 预期输出

### 首次构建下载内容
- Android SDK (~1-2GB)
- Android NDK (~1-2GB)
- Python-for-android依赖
- 其他依赖包

### 构建时间
- **首次构建**: 20-40分钟（下载SDK/NDK）
- **后续构建**: 10-20分钟（使用缓存）

### 输出文件
```
bin/bilibili_query-1.0.0-arm64-v8a-debug.apk
bin/bilibili_query-1.0.0-armeabi-v7a-debug.apk
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

### 6. NDK版本的重要性
NDK版本与系统环境的兼容性很重要，旧版NDK在新系统上可能遇到编译问题。

### 7. 许可证处理的必要性
Android SDK许可证需要手动接受，在CI/CD环境中需要特殊处理。

### 8. Cython的显式安装
某些情况下Buildozer不会自动安装Cython，需要显式添加到依赖中。

---

## 后续优化方向

1. **应用图标**: 添加512x512的icon.png
2. **应用签名**: 配置release签名
3. **多架构支持**: 优化APK大小，考虑仅使用arm64-v8a
4. **错误处理**: 增强网络错误处理
5. **UI优化**: 改进移动端用户体验
6. **构建缓存**: 优化GitHub Actions缓存策略
7. **自动化测试**: 添加APK自动化测试

---

## 参考资料

- [Kivy官方文档](https://kivy.org/doc/stable/)
- [Buildozer官方文档](https://buildozer.readthedocs.io/)
- [Python-for-android文档](https://python-for-android.readthedocs.io/)
- [PEP 668 - Marking Python base environments as "externally managed"](https://peps.python.org/pep-0668/)
- [B站API文档](https://github.com/SocialSisterYi/bilibili-API-doc)
- [GitHub Actions文档](https://docs.github.com/en/actions)

---

## 开发者备注

本项目在开发过程中遇到了多个环境配置问题，特别是：
- Python 3.13的新特性（PEP 668）
- GXDE系统的软件源问题
- GitHub Actions的许可证处理
- libffi的autoconf编译问题
- NDK版本兼容性

通过不断尝试和调整，最终找到了可行的解决方案。

建议后续开发者在类似项目中：
1. 提前了解目标系统的Python版本和软件源配置
2. 优先使用虚拟环境管理依赖
3. 准备多个备选方案以应对环境问题
4. 详细记录遇到的问题和解决方案
5. 考虑使用GitHub Actions等云端构建方案
6. 注意NDK版本与系统环境的兼容性
7. 处理好Android SDK许可证问题
8. 显式安装Cython等关键依赖

---

## 问题解决时间线

| 时间 | 问题 | 解决方案 |
|-----|------|---------|
| 2026-02-17 | libtinfo5包不可用 | 使用libtinfo6或libncurses-dev |
| 2026-02-17 | GXDE软件源问题 | 分步安装，跳过不可用包 |
| 2026-02-17 | Python 3.13 PEP 668 | 使用虚拟环境 |
| 2026-02-17 | venv创建失败 | 放弃本地环境，使用GitHub Actions |
| 2026-02-17 | Cython未找到 | 在工作流中显式安装 |
| 2026-02-17 | Android SDK许可证 | 使用环境变量和yes管道 |
| 2026-02-17 | libffi autoconf错误 | 更新NDK到27b |

---

## 附录：完整错误日志

### 错误1: Cython未找到
```
# Search for Cython (cython)
# Cython (cython) not found, please install it.
Error: Process completed with exit code 1.
```

### 错误2: Android SDK许可证
```
June 2014.
---------------------------------------
Accept? (y/N): Skipping following packages as the license is not accepted:
Android SDK Build-Tools 37-rc1
The following packages can not be installed since their licenses or those of the packages they depend on were not accepted:
build-tools;37.0.0-rc1
```

### 错误3: libffi autoconf错误
```
configure.ac:215: error: possibly undefined macro: LT_SYS_SYMBOL_USCORE
If this token and others are legitimate, please use m4_pattern_allow.
See the Autoconf documentation.
autoreconf: error: /usr/bin/autoconf failed with exit status: 1
```
