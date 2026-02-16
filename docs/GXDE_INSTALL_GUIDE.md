# GXDE系统 - Buildozer安装指南（分步版）

由于GXDE的软件源配置问题，建议分步安装依赖。

## 方法一：使用安装脚本（推荐）

```bash
cd /mnt/d/Alfrid/Desktop/BB
chmod +x install_deps.sh
./install_deps.sh
```

## 方法二：手动分步安装

### 步骤1：更新软件源
```bash
sudo apt update
```

### 步骤2：安装Python和pip
```bash
sudo apt install -y python3 python3-pip
```

### 步骤3：安装Java JDK
```bash
sudo apt install -y default-jdk
```

### 步骤4：安装构建工具
```bash
sudo apt install -y build-essential
```

### 步骤5：安装开发库
```bash
sudo apt install -y zlib1g-dev libffi-dev libssl-dev pkg-config
```

### 步骤6：安装其他工具
```bash
sudo apt install -y git curl wget
```

### 步骤7：安装Buildozer
```bash
pip3 install --user buildozer
```

### 步骤8：配置环境变量
```bash
echo 'export PATH=$HOME/.local/bin:$PATH' >> ~/.bashrc
source ~/.bashrc
```

### 步骤9：开始打包
```bash
cd /mnt/d/Alfrid/Desktop/BB
buildozer android debug
```

## 常见问题解决

### 问题1：找不到某个包
如果某个包找不到，跳过它继续安装其他包。Buildozer会在首次运行时自动下载缺失的依赖。

### 问题2：pip安装失败
```bash
# 使用国内镜像源
pip3 install --user buildozer -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 问题3：Java版本问题
```bash
# 检查Java版本
java -version

# 如果版本太低，安装OpenJDK 11
sudo apt install -y openjdk-11-jdk
```

## 最简方案（如果上述都失败）

如果GXDE环境问题太多，建议使用Docker：

```bash
# 安装Docker
sudo apt install -y docker.io

# 使用Docker打包
cd /mnt/d/Alfrid/Desktop/BB
docker run --rm -v $(pwd):/home/user/appio/buildozer kivy/buildozer android debug
```

## 或者使用GitHub Actions（最简单）

完全跳过本地环境配置，使用GitHub自动打包：

1. 创建GitHub仓库
2. 上传 `main.py`、`buildozer.spec`、`requirements.txt`
3. 推送代码，自动生成APK
4. 在Actions页面下载
