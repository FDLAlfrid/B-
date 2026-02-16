# 使用现有GitHub仓库打包APK

## 快速开始（3分钟搞定）

### 步骤1：确认仓库地址

您的仓库地址：`https://github.com/FDLAlfrid/B-`

**注意**：仓库名称 `B-` 看起来不完整，请确认完整地址是否为：
- `https://github.com/FDLAlfrid/B-` （如果确实是这个名称）
- `https://github.com/FDLAlfrid/Bilibili-Query` （或其他完整名称）

### 步骤2：上传代码到现有仓库

在Windows PowerShell中执行：

```powershell
cd d:\Alfrid\Desktop\BB

# 初始化git仓库（如果还没有）
git init

# 添加所有文件
git add .

# 提交
git commit -m "Add B站BV号查询APK项目"

# 设置远程仓库（使用你的现有仓库）
git remote add origin https://github.com/FDLAlfrid/B-.git

# 推送到main分支
git branch -M main
git push -u origin main
```

### 步骤3：等待构建完成

1. 访问 `https://github.com/FDLAlfrid/B-`
2. 点击 `Actions` 标签页
3. 看到工作流正在运行（黄色圆点）
4. 等待约20-40分钟（首次构建需要下载依赖）

### 步骤4：下载APK

1. 构建完成后（绿色勾），点击工作流
2. 滚动到底部，找到 `Artifacts` 区域
3. 点击 `bilibili-query-apk` 下载
4. 解压zip文件，得到APK文件

---

## 如果推送失败

### 问题1：仓库已存在远程地址
```powershell
# 查看现有远程地址
git remote -v

# 删除现有远程地址
git remote remove origin

# 添加新的远程地址
git remote add origin https://github.com/FDLAlfrid/B-.git

# 推送
git push -u origin main
```

### 问题2：需要认证
```powershell
# 使用Personal Access Token
# 1. 访问 https://github.com/settings/tokens
# 2. 点击 "Generate new token" → "Generate new token (classic)"
# 3. 勾选 "repo" 权限
# 4. 生成token并复制

# 使用token推送（替换YOUR_TOKEN）
git remote set-url origin https://YOUR_TOKEN@github.com/FDLAlfrid/B-.git
git push -u origin main
```

### 问题3：分支名称不匹配
```powershell
# 查看所有分支
git branch -a

# 如果远程是master分支
git push -u origin master
```

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

1. 访问 `https://github.com/FDLAlfrid/B-/actions`
2. 点击左侧 `Build APK`
3. 点击 `Run workflow`
4. 点击绿色的 `Run workflow` 按钮

---

## 完整示例（一次性执行）

```powershell
cd d:\Alfrid\Desktop\BB
git init
git add .
git commit -m "Add B站BV号查询APK项目"
git remote add origin https://github.com/FDLAlfrid/B-.git
git branch -M main
git push -u origin main
```

---

## 验证上传成功

推送成功后，访问 `https://github.com/FDLAlfrid/B-`，应该能看到：
- `main.py` 文件
- `buildozer.spec` 文件
- `requirements.txt` 文件
- `.github/workflows/build.yml` 文件

---

## 常见问题

### Q1：仓库名称不完整怎么办？
如果仓库名称确实是 `B-`，直接使用即可。如果需要修改，可以：
1. 在GitHub上重命名仓库
2. 或者创建一个新的完整名称的仓库

### Q2：如何查看Actions构建状态？
访问：`https://github.com/FDLAlfrid/B-/actions`

### Q3：构建失败怎么办？
1. 点击失败的构建查看日志
2. 检查 `main.py` 和 `buildozer.spec` 是否正确
3. 确保所有必要文件都已上传

### Q4：如何修改应用名称？
编辑 `buildozer.spec` 文件：
```ini
[app]
title = 你的应用名称
```
然后重新推送代码：
```powershell
git add buildozer.spec
git commit -m "Update app title"
git push
```

---

## 下一步

1. 推送代码到现有仓库
2. 等待GitHub Actions自动构建
3. 下载APK到手机
4. 允许安装未知来源应用
5. 安装并测试

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
