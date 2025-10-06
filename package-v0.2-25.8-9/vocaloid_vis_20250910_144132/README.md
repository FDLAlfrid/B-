# VOCALOID音乐社交平台

基于B站VOCALOID音乐的现代化社交平台，集音乐发现、分享交友、智能推荐于一体。

## 🎯 核心特性

### 🎵 音乐功能
- **B站音乐自动抓取** - 实时获取B站VOCALOID分区热门音乐
- **智能封面代理** - 解决跨域图片加载问题，自动处理B站图片资源
- **时长格式化** - 自动将秒数转换为友好的时分秒格式
- **收录时间追踪** - 精确记录音乐被系统收录的时间戳

### 👥 社交功能  
- **用户兴趣系统** - 基于标签的用户兴趣建模和匹配
- **协同过滤推荐** - 智能推荐相似音乐和潜在好友
- **音乐分享机制** - 支持平台内分享和外部社交平台分享
- **个人资料管理** - 完整的用户注册、登录和个人信息管理

### 🎨 界面特性
- **响应式设计** - 完美适配桌面和移动设备
- **现代化UI** - 基于Bootstrap 5的优雅界面设计
- **实时交互** - 丰富的JavaScript交互效果
- **图标集成** - 使用Bootstrap Icons美化界面
- **卡片点击跳转** - 点击音乐卡片直接跳转详情页，简化操作流程

## 🛠️ 技术栈

### 后端技术
- **Flask 2.3.3** - 轻量级Web框架
- **SQLAlchemy 3.0.5** - 数据库ORM
- **Flask-Login 0.6.2** - 用户认证管理
- **Requests 2.31.0** - HTTP请求处理
- **BeautifulSoup4 4.12.2** - HTML解析

### 前端技术  
- **Bootstrap 5** - 现代化CSS框架
- **Jinja2 3.1.2** - 模板引擎
- **JavaScript ES6+** - 现代交互逻辑
- **Bootstrap Icons** - 图标库

### 数据库
- **SQLite** - 开发环境（默认）
- **PostgreSQL** - 生产环境（可选）

## 📁 项目结构

```
vocaloid_social/
├── app/                    # 应用核心代码
│   ├── __init__.py        # Flask应用初始化
│   ├── models/            # 数据模型定义
│   ├── routes/            # 路由处理模块
│   │   ├── auth.py        # 认证路由
│   │   ├── main.py        # 主页面路由
│   │   ├── music.py       # 音乐相关路由
│   │   ├── social.py      # 社交功能路由
│   │   └── api.py         # API接口路由
│   ├── services/          # 业务逻辑服务
│   │   ├── bilibili_service.py     # B站音乐服务
│   │   └── recommendation_service.py  # 推荐服务
│   └── utils/             # 工具函数
│       └── time_utils.py  # 时间格式化工具
│   ├── templates/         # HTML模板
│   └── static/            # 静态资源
├── config.py              # 应用配置
├── run.py                 # Flask应用核心入口
├── app_manager.py         # 应用管理工具（整合启动、抓取、清理、打包功能）
├── requirements.txt       # Python依赖
└── README.md              # 项目说明
```

## 🚀 快速开始

### 环境要求
- Python 3.8+
- Conda环境（推荐）或 virtualenv

### 1. 创建并激活Conda环境
```bash
# 创建名为vocaloid_vis的Python环境
conda create -n vocaloid_vis python=3.9

# 激活环境
conda activate vocaloid_vis
```

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 配置环境变量（可选）
```bash
# 设置Flask密钥（生产环境必须设置）
export SECRET_KEY=your-secret-key-here
```

### 4. 使用方式

项目提供了两种启动方式：通过命令行工具 `app_manager.py` 或通过可视化GUI启动器 `app_launcher.py`。

#### 4.1 命令行管理工具

`app_manager.py` 整合了启动、数据抓取、数据库管理和打包等功能：

```bash
# 启动应用（基本模式）
python app_manager.py start

# 启动应用（调试模式，显示详细日志）
python app_manager.py start --debug --logs

# 初始化数据库并抓取最新数据
python app_manager.py init

# 仅刷新音乐数据（不重新初始化数据库）
python app_manager.py refresh

# 清空数据库（会自动备份）
python app_manager.py clear

# 备份数据库
python app_manager.py backup

# 清理缓存
python app_manager.py cache

# 打包应用（生成zip文件和启动脚本）
python app_manager.py package
```

#### 4.2 GUI启动器

`app_launcher.py` 提供了友好的图形界面，适合非技术用户使用：

```bash
# 启动GUI启动器
python app_launcher.py
```

GUI启动器提供了以下功能按钮：
- 启动应用：启动Flask服务器
- 停止应用：停止运行中的服务器
- 初始化数据库：创建数据库并抓取最新音乐数据
- 刷新数据：更新现有数据
- 清空数据库：删除所有数据（会自动备份）
- 备份数据库：创建当前数据库的备份
- 清理缓存：删除临时文件
- 应用打包：生成可部署的应用包

### 5. 应用打包

使用 `package` 命令可以将应用打包为一个压缩文件，便于部署和分享：

```bash
python app_manager.py package
```

打包后的文件将保存在 `package/` 目录下，包含所有必要的代码和资源，并附带一个启动脚本。

应用将在 http://localhost:5000 启动

### 6. 访问应用
打开浏览器访问: http://127.0.0.1:5000

## ⚙️ 配置说明

### 数据库配置
- **开发环境**: SQLite (默认) - `sqlite:///vocaloid_social.db`
- **生产环境**: PostgreSQL - 设置 `DATABASE_URL` 环境变量

### 关键配置项
```python
# 开发配置（默认）
DEBUG = True
SQLALCHEMY_DATABASE_URI = 'sqlite:///vocaloid_social.db'

# 生产配置  
DEBUG = False
SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
```

## 📊 API接口

| 端点 | 方法 | 功能描述 | 认证要求 |
|------|------|----------|----------|
| `/api/proxy-image` | GET | 图片代理服务 | 无需认证 |
| `/api/auth/register` | POST | 用户注册 | 无需认证 |
| `/api/auth/login` | POST | 用户登录 | 无需认证 |
| `/api/recommend/music` | GET | 音乐推荐 | 需要登录 |
| `/api/recommend/users` | GET | 用户匹配推荐 | 需要登录 |

## 🔧 开发功能

### 已实现功能
- ✅ 用户注册登录系统
- ✅ B站音乐自动抓取和存储
- ✅ 音乐列表和详情展示（点击卡片跳转详情）
- ✅ 图片代理服务（解决跨域问题）
- ✅ 用户兴趣标签系统
- ✅ 基础推荐算法框架
- ✅ 响应式前端界面

### 待开发功能
- 🔄 完整的协同过滤推荐算法
- 🔄 实时聊天功能
- 🔄 音乐播放器集成
- 🔄 高级搜索和过滤

## 🤝 贡献指南

1. Fork 本项目
2. 创建特性分支: `git checkout -b feature/新功能`
3. 提交更改: `git commit -m '添加新功能'`
4. 推送到分支: `git push origin feature/新功能`
5. 提交 Pull Request

## 📝 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🆘 常见问题

### Q: 图片无法显示？
A: 确保图片代理服务正常运行，检查B站图片链接有效性

### Q: 数据库初始化失败？
A: 检查文件写入权限，确保应用有创建数据库文件的权限

### Q: 推荐功能不工作？
A: 需要先有用户数据和兴趣标签才能进行推荐计算

---

**注意**: 生产环境部署时请务必设置强密钥和安全的数据库连接！