# B站BV号查询 - APK打包指南

## 重要说明
**打包APK必须在Linux环境下进行**。如果您使用Windows，推荐使用WSL2或虚拟机。

## 方法一：GXDE/Debian/Ubuntu系统（推荐）

### 1. 安装依赖

**GXDE/Debian系统：**
```bash
sudo apt update
sudo apt install -y python3 python3-pip openjdk-17-jdk autoconf libtool pkg-config zlib1g-dev libncurses-dev cmake libffi-dev libssl-dev build-essential git
```

**Ubuntu 22.04/24.04：**
```bash
sudo apt update
sudo apt install -y python3 python3-pip openjdk-17-jdk autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo6 cmake libffi-dev libssl-dev build-essential git
```

**Ubuntu 20.04及更早版本：**
```bash
sudo apt update
sudo apt install -y python3 python3-pip openjdk-17-jdk autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev build-essential git
```

**如果遇到依赖问题，使用以下通用命令：**
```bash
sudo apt update
sudo apt install -y python3 python3-pip openjdk-17-jdk autoconf libtool pkg-config zlib1g-dev libncurses-dev cmake libffi-dev libssl-dev build-essential git
```

### 2. 安装Buildozer
```bash
pip3 install buildozer
```

### 3. 打包APK
```bash
cd /path/to/BB
buildozer android debug
```

首次打包会下载Android SDK/NDK（约3-5GB），需要较长时间。

## 方法二：使用WSL2（Windows用户）

### 1. 安装WSL2
在PowerShell（管理员）中运行：
```powershell
wsl --install
```
安装Ubuntu后重启电脑。

### 2. 在WSL2中安装依赖
打开Ubuntu终端，运行：
```bash
sudo apt update
sudo apt install -y python3 python3-pip openjdk-17-jdk autoconf libtool pkg-config zlib1g-dev libncurses-dev cmake libffi-dev libssl-dev build-essential git
```

### 3. 安装Buildozer
```bash
pip3 install buildozer
```

### 4. 打包APK
```bash
cd /mnt/d/Alfrid/Desktop/BB
buildozer android debug
```

首次打包会下载Android SDK/NDK（约3-5GB），需要较长时间。

## 方法二：使用Miniconda + Docker

### 1. 安装Docker Desktop
下载并安装Docker Desktop for Windows。

### 2. 使用Docker打包
```bash
cd d:\Alfrid\Desktop\BB
docker run --rm -v $(pwd):/home/user/appio/buildozer kivy/buildozer android debug
```

## 方法三：使用GitHub Actions（最简单）

### 1. 创建GitHub仓库并上传代码
将以下文件上传到GitHub仓库：
- main.py
- buildozer.spec
- requirements.txt

### 2. 创建GitHub Actions工作流
在仓库中创建 `.github/workflows/build.yml`：
```yaml
name: Build APK

on:
  push:
    branches: [ main ]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Build APK
      uses: Arbazkharaiti/buildozer-android-action@main
      with:
        buildozer_version: stable
        workdir: .
    - name: Upload APK
      uses: actions/upload-artifact@v3
      with:
        name: release-apk
        path: bin/*.apk
```

### 3. 推送代码
```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/你的用户名/你的仓库名.git
git push -u origin main
```

### 4. 下载APK
在GitHub仓库的Actions页面下载生成的APK。

## 测试应用

### 在电脑上测试（需要安装Kivy）
```bash
pip install kivy requests
python main.py
```

### 在手机上安装
将生成的APK文件传输到手机，安装即可。

## 常见问题

### Q: 打包失败怎么办？
A: 检查buildozer.spec中的android.api和android.ndk版本是否匹配。

### Q: APK安装后闪退？
A: 检查Android权限，确保INTERNET权限已添加。

### Q: 如何修改应用图标？
A: 在项目根目录创建`icon.png`（512x512），buildozer会自动使用。

### Q: 如何修改应用名称？
A: 修改buildozer.spec中的title字段。

## 文件说明

- **main.py**: Kivy GUI应用主程序
- **buildozer.spec**: Buildozer配置文件
- **requirements.txt**: Python依赖列表
- **find_bv_info.py**: 原始命令行版本（保留）
