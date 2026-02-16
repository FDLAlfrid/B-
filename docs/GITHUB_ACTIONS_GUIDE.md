# GitHub Actions 自动打包APK指南

## 为什么选择GitHub Actions？

✅ **无需本地环境** - 不需要配置Python、Java、Android SDK等
✅ **自动换源** - GitHub Actions自动处理依赖下载
✅ **云端构建** - 使用GitHub的服务器，不占用本地资源
✅ **完全免费** - 公开仓库完全免费使用
✅ **自动触发** - 推送代码自动构建，也可以手动触发

---

## 快速开始（5分钟搞定）

### 步骤1：创建GitHub仓库

1. 访问 [GitHub](https://github.com) 并登录
2. 点击右上角 `+` → `New repository`
3. 仓库名称填写：`bilibili-query-apk`
4. 选择 `Public`（公开）
5. 点击 `Create repository`

### 步骤2：上传代码

在项目目录 `d:\Alfrid\Desktop\BB` 中，打开PowerShell，执行：

```powershell
# 初始化git仓库
git init

# 添加所有文件
git add .

# 提交
git commit -m "Initial commit"

# 添加远程仓库（替换YOUR_USERNAME为你的GitHub用户名）
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/bilibili-query-apk.git

# 推送代码
git push -u origin main
```

### 步骤3：等待构建完成

1. 推送成功后，访问你的GitHub仓库
2. 点击 `Actions` 标签页
3. 看到工作流正在运行（黄色圆点）
4. 等待约20-40分钟（首次构建需要下载依赖）

### 步骤4：下载APK

1. 构建完成后（绿色勾），点击工作流
2. 滚动到底部，找到 `Artifacts` 区域
3. 点击 `bilibili-query-apk` 下载
4. 解压zip文件，得到APK文件

---

## 需要上传的文件

确保以下文件在项目根目录：

```
BB/
├── main.py                    # Kivy GUI应用
├── buildozer.spec             # Buildozer配置
├── requirements.txt           # Python依赖
└── .github/
    └── workflows/
        └── build.yml          # GitHub Actions工作流
```

---

## 手动触发构建

如果不想推送代码，可以手动触发：

1. 访问仓库的 `Actions` 页面
2. 点击左侧 `Build APK`
3. 点击 `Run workflow`
4. 点击绿色的 `Run workflow` 按钮

---

## 常见问题

### Q1：推送代码时提示认证失败？
```powershell
# 使用Personal Access Token
# 1. 访问 https://github.com/settings/tokens
# 2. 点击 "Generate new token" → "Generate new token (classic)"
# 3. 勾选 "repo" 权限
# 4. 生成token并复制

# 使用token推送（替换YOUR_TOKEN）
git remote set-url origin https://YOUR_TOKEN@github.com/YOUR_USERNAME/bilibili-query-apk.git
git push -u origin main
```

### Q2：构建失败怎么办？
1. 点击失败的构建查看日志
2. 检查 `main.py` 和 `buildozer.spec` 是否正确
3. 确保所有必要文件都已上传

### Q3：如何修改应用名称？
编辑 `buildozer.spec` 文件：
```ini
[app]
title = 你的应用名称
```

### Q4：如何修改应用图标？
1. 准备512x512的PNG图标
2. 命名为 `icon.png`
3. 放在项目根目录
4. 推送代码重新构建

---

## 构建时间参考

- **首次构建**: 20-40分钟（下载Android SDK/NDK）
- **后续构建**: 10-20分钟（使用缓存）
- **仅修改代码**: 5-10分钟

---

## APK文件位置

构建完成后，APK文件会自动上传到GitHub Actions的Artifacts中，保留30天。

文件名格式：`bilibili_query-1.0.0-arm64-v8a-debug.apk`

---

## 下一步

1. 下载APK到手机
2. 允许安装未知来源应用
3. 安装并测试

---

## 完整示例

```powershell
# 在PowerShell中执行
cd d:\Alfrid\Desktop\BB
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/bilibili-query-apk.git
git push -u origin main
```

替换 `YOUR_USERNAME` 为你的GitHub用户名，然后执行即可！

---

## 技术说明

GitHub Actions工作流会自动：
1. 使用Ubuntu最新版
2. 安装Python 3.11
3. 安装Buildozer
4. 下载Android SDK/NDK
5. 构建APK
6. 上传APK到Artifacts

完全不需要你手动配置任何环境！
