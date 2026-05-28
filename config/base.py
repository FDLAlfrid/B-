"""
配置文件 - 智能音乐推荐与分享系统（融合版）
"""
import os
import json
from pathlib import Path

# ===================== 项目路径 =====================
PROJECT_DIR = Path(__file__).parent.absolute()
ASSETS_DIR = PROJECT_DIR / "assets"
DATA_DIR = PROJECT_DIR / "data"
LOGS_DIR = PROJECT_DIR / "logs"
MODULES_DIR = PROJECT_DIR / "modules"
SERVICES_DIR = PROJECT_DIR / "services"
UTILS_DIR = PROJECT_DIR / "utils"
MODELS_DIR = PROJECT_DIR / "models"

# 确保目录存在
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ===================== 数据库配置 =====================
DB_PATH = DATA_DIR / "vocaloid_music.db"
# 添加UTF-8编码支持，解决中文乱码问题
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}?check_same_thread=False"

# ===================== 日志配置 =====================
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE = LOGS_DIR / "app.log"

# ===================== UI配置 =====================
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800
MIN_WINDOW_WIDTH = 900
MIN_WINDOW_HEIGHT = 600

# 字体配置
FONT_PATH = ASSETS_DIR / "fonts" / "原神字体.ttf"
DEFAULT_FONT_SIZE = 12
DEFAULT_FONT_FAMILY = "微软雅黑"

# 图标配置（根据论文目录结构修改为 assets/icons/）
ICONS_DIR = ASSETS_DIR / "icons"
ICON_PATH = ICONS_DIR / "icon.png"
ICON_ICO_PATH = ICONS_DIR / "icon.ico"

# 确保图标目录存在
ICONS_DIR.mkdir(parents=True, exist_ok=True)

# ===================== B站API配置 =====================
BILIBILI_API_BASE_URL = "https://api.bilibili.com/x/web-interface"
BILIBILI_SEARCH_URL = "https://api.bilibili.com/x/web-interface/search/type"
BILIBILI_VIDEO_URL = "https://api.bilibili.com/x/web-interface/view"

# ===================== MMFDR算法配置 =====================
# 导入MMFDR配置
try:
    from config_mmfdr import MMFDR_CONFIG, FEATURE_EXTRACTION_CONFIG, IP_KEYWORDS_CONFIG, USER_ANALYSIS_CONFIG
except ImportError:
    # 默认配置
    MMFDR_CONFIG = {
        'enabled': False,
        'feature_weights': {'audio': 0.3, 'text': 0.4, 'image': 0.2, 'social': 0.1},
        'fallback_enabled': True
    }
    FEATURE_EXTRACTION_CONFIG = {}
    IP_KEYWORDS_CONFIG = {}
    USER_ANALYSIS_CONFIG = {}

# 推荐算法选择
RECOMMEND_ALGORITHM = "mmfdr"  # 可选: "mmfdr", "traditional", "hybrid"

# 混合算法权重
HYBRID_WEIGHTS = {
    'mmfdr': 0.7,      # MMFDR算法权重
    'traditional': 0.3 # 传统算法权重
}

# 请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Referer": "https://www.bilibili.com"
}

# 请求频率限制
MIN_REQUEST_INTERVAL = 2.0  # 最小请求间隔（秒）
MAX_REQUEST_INTERVAL = 4.0  # 最大请求间隔（秒）
MAX_REQUESTS_PER_MINUTE = 30  # 每分钟最大请求数

# ===================== 推荐系统配置 =====================
# 权重配置文件路径
WEIGHTS_CONFIG_PATH = os.path.expanduser('~/.vocaloid_toolbox_weights.json')

# 默认推荐权重分配
DEFAULT_RECOMMEND_WEIGHTS = {
    "collaborative": 0.4,  # 协同过滤
    "ip_driven": 0.3,      # IP驱动
    "content": 0.2,         # 内容推荐
    "hot": 0.1             # 热门推荐
}

def load_recommend_weights():
    """
    从权重配置文件加载推荐权重
    如果配置文件不存在或读取失败，创建默认配置并使用默认权重
    """
    try:
        if os.path.exists(WEIGHTS_CONFIG_PATH):
            with open(WEIGHTS_CONFIG_PATH, 'r', encoding='utf-8') as f:
                weights_config = json.load(f)
            
            # 从配置文件中提取权重并转换为推荐权重格式
            ip_weight = weights_config.get('ip_weight', 50) / 100  # 转换为0-1范围
            scene_weight = weights_config.get('scene_weight', 30) / 100
            base_weight = weights_config.get('base_weight', 20) / 100
            
            # 根据开发者工具的权重配置调整推荐权重
            recommend_weights = {
                "collaborative": ip_weight * 0.5 + base_weight * 0.3,  # 协同过滤
                "ip_driven": ip_weight * 0.5 + scene_weight * 0.3,      # IP驱动
                "content": scene_weight * 0.5 + base_weight * 0.5,         # 内容推荐
                "hot": base_weight * 0.2 + scene_weight * 0.2             # 热门推荐
            }
            
            # 归一化权重，确保总和为1
            total = sum(recommend_weights.values())
            if total > 0:
                recommend_weights = {k: v/total for k, v in recommend_weights.items()}
            
            print(f"从配置文件加载权重: {recommend_weights}")
            return recommend_weights
        else:
            print("权重配置文件不存在，创建默认配置...")
            create_default_weights_config()
            print("使用默认权重")
            return DEFAULT_RECOMMEND_WEIGHTS.copy()
    except Exception as e:
        print(f"加载权重配置失败: {e}，创建默认配置...")
        create_default_weights_config()
        return DEFAULT_RECOMMEND_WEIGHTS.copy()

def create_default_weights_config():
    """
    创建默认权重配置文件
    """
    try:
        default_weights = {
            'ip_weight': 50,
            'scene_weight': 30,
            'base_weight': 20,
            'revisit_ip_coef': 1.2,
            'discover_new_ip_coef': 1.1,
            'explore_author_coef': 1.3,
            'play_weight': 10,
            'search_weight': 8,
            'copy_weight': 5,
            'author_weight': 12
        }
        with open(WEIGHTS_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(default_weights, f, ensure_ascii=False, indent=2)
        print(f"默认权重配置文件创建成功: {WEIGHTS_CONFIG_PATH}")
    except Exception as e:
        print(f"创建默认权重配置文件失败: {e}")

# 推荐权重（从配置文件加载）
RECOMMEND_WEIGHTS = load_recommend_weights()

# 默认推荐数量
DEFAULT_RECOMMEND_LIMIT = 10
MAX_RECOMMEND_LIMIT = 20

# ===================== 用户画像配置 =====================
# 粉丝类型阈值
SINGLE_FAN_THRESHOLD = 0.7  # 单推人阈值（占比>70%）
MULTI_FAN_MIN_COUNT = 3     # 多角色厨最少歌手数

# 行为权重
BEHAVIOR_WEIGHTS = {
    "like": 3.0,      # 点赞
    "collect": 2.0,    # 收藏
    "play": 0.5,      # 播放
    "share": 2.5       # 分享
}

# ===================== IP驱动配置 =====================
# 虚拟歌手列表
VOCALOID_SINGERS = [
    "洛天依", "乐正绫", "言和", "心华", 
    "墨清弦", "摩柯", "徵羽", "绫", "初音未来"
]

# IP评分权重
IP_SCORE_WEIGHTS = {
    "singer": 0.4,    # 歌手匹配度
    "up": 0.3,        # UP主匹配度
    "tag": 0.1,       # 标签匹配度
    "emotion": 0.1,   # 情感匹配度
    "genre": 0.1      # 曲风匹配度
}

# ===================== 分享系统配置 =====================
# 分享类型
SHARE_TYPES = ["link", "playlist"]

# 分享链接格式
SHARE_LINK_FORMAT = "https://www.bilibili.com/video/{bvid}"

# ===================== 主题配置 =====================
# 科技商务简约配色方案
THEMES = {
    "默认主题": {
        "primary": "#1e3a8a",  # 深蓝色
        "secondary": "#3b82f6",
        "background": "#f0f0f0",  # 浅灰色
        "text": "#1a1a1a",
        "border": "#e0e0e0"  # 中灰色
    },
    "科技商务": {
        "primary": "#1e3a8a",  # 深蓝色
        "secondary": "#3b82f6",
        "background": "#f0f0f0",  # 浅灰色
        "text": "#1a1a1a",
        "border": "#e0e0e0"  # 中灰色
    },
    "洛天依": {
        "primary": "#66CCFF",
        "secondary": "#3399CC",
        "background": "#F0F8FF",
        "text": "#1a1a1a",
        "border": "#B8E0F0"
    },
    "乐正绫": {
        "primary": "#EE0000",
        "secondary": "#CC0000",
        "background": "#FFF0F0",
        "text": "#1a1a1a",
        "border": "#F0D8D8"
    },
    "言和": {
        "primary": "#00FFCC",
        "secondary": "#00CC99",
        "background": "#F0FFFA",
        "text": "#1a1a1a",
        "border": "#D8FFF0"
    }
}

# ===================== 缓存配置 =====================
CACHE_DIR = DATA_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# 缓存大小限制（MB）
MAX_CACHE_SIZE_MB = 50

# 缓存过期时间（秒）
CACHE_EXPIRE_TIME = 3600  # 1小时

# ===================== 设置文件配置 =====================
SETTINGS_PATH = os.path.expanduser("~/.vocaloid_toolbox_settings.json")

# ===================== 其他配置 =====================
# 排序方式映射
SORT_MAP = {
    "综合排序": "totalrank",
    "最多播放": "click",
    "最新发布": "pubdate",
    "最多弹幕": "dm",
    "最多收藏": "stow"
}

# 默认下载路径（相对路径）
DEFAULT_DOWNLOAD_PATH = PROJECT_DIR / "downloads"
DEFAULT_DOWNLOAD_PATH.mkdir(parents=True, exist_ok=True)

# 默认Cookies
DEFAULT_COOKIES = ""

# ===================== 云端调控配置 =====================
# 云端调控设置配置文件路径
CLOUD_SETTINGS_PATH = os.path.expanduser("~/.vocaloid_toolbox_cloud.json")

# 默认云端调控配置
DEFAULT_CLOUD_CONFIG = {
    # 服务器地址
    'server_url': 'http://sgscp.cc',  # 默认服务器
    'api_base': '/api/v1',  # API基础路径
    
    # 本地测试配置
    'local_server_url': 'http://127.0.0.1:5002',
    'local_api_base': '/api',
    
    # 使用本地还是远程服务器
    'use_local': False,
    
    # 同步间隔（秒）
    'sync_interval': 3600,  # 1小时
    
    # 算法更新间隔（秒）
    'algorithm_update_interval': 86400,  # 24小时
    
    # 云端调控功能开关
    'enabled': True,
    
    # 社区功能开关
    'community_enabled': True,
    
    # 允许游客发言
    'allow_guest_comments': True,
    
    # 自定义服务器配置（高级用户）
    'custom_server': {
        'enabled': False,
        'url': '',
        'api_base': '/api',
        'api_key': ''
    }
}

def load_cloud_config():
    """加载云端调控配置"""
    try:
        if os.path.exists(CLOUD_SETTINGS_PATH):
            with open(CLOUD_SETTINGS_PATH, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # 合并默认配置
                merged = DEFAULT_CLOUD_CONFIG.copy()
                merged.update(config)
                return merged
        else:
            return create_default_cloud_config()
    except Exception as e:
        print(f"加载云端调控配置失败: {e}")
        return DEFAULT_CLOUD_CONFIG.copy()

def create_default_cloud_config():
    """创建默认云端调控配置文件"""
    try:
        with open(CLOUD_SETTINGS_PATH, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_CLOUD_CONFIG, f, ensure_ascii=False, indent=2)
        return DEFAULT_CLOUD_CONFIG.copy()
    except Exception as e:
        print(f"创建默认云端调控配置失败: {e}")
        return DEFAULT_CLOUD_CONFIG.copy()

def save_cloud_config(config):
    """保存云端调控配置"""
    try:
        with open(CLOUD_SETTINGS_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存云端调控配置失败: {e}")
        return False

def get_server_url(config=None):
    """获取当前使用的服务器URL"""
    if config is None:
        config = load_cloud_config()
    
    # 优先使用自定义服务器
    if config.get('custom_server', {}).get('enabled', False):
        return config['custom_server']['url']
    
    # 使用本地或远程服务器
    if config.get('use_local', False):
        return config.get('local_server_url', 'http://127.0.0.1:5002')
    else:
        return config.get('server_url', 'http://sgscp.cc')

def get_api_base(config=None):
    """获取当前使用的API基础路径"""
    if config is None:
        config = load_cloud_config()
    
    # 优先使用自定义服务器
    if config.get('custom_server', {}).get('enabled', False):
        return config['custom_server'].get('api_base', '/api')
    
    # 使用本地或远程服务器
    if config.get('use_local', False):
        return config.get('local_api_base', '/api')
    else:
        return config.get('api_base', '/api/v1')

# 向后兼容的变量（使用函数动态获取）
CLOUD_SERVER_URL = get_server_url()
CLOUD_SYNC_INTERVAL = lambda: load_cloud_config().get('sync_interval', 3600)
CLOUD_ALGORITHM_UPDATE_INTERVAL = lambda: load_cloud_config().get('algorithm_update_interval', 86400)
CLOUD_CONTROL_ENABLED = lambda: load_cloud_config().get('enabled', True)

# ===================== 自定义关键词配置 =====================
# 自定义关键词配置文件路径
CUSTOM_KEYWORDS_PATH = os.path.expanduser("~/.vocaloid_toolbox_keywords.json")

# 默认Vocaloid关键词
DEFAULT_VOCALOID_KEYWORDS = [
    # 核心角色
    '洛天依', '乐正绫', '言和', '乐正龙牙', '徵羽摩柯', '墨清弦',
    # VOCALOID相关
    'VOCALOID', 'Vocaloid', 'vocaloid', '虚拟歌姬', '中文VOCALOID',
    '中V', '原创曲', '翻唱', 'UTAU', 'DeepVocal', 'Sharpkey', 'ACE虚拟歌姬',
    # 知名P主
    'ilem', '乌龟sui', '阿良良木健', 'COP', 'JUSF周存', 'DELA',
    '洛天依原创', '乐正绫原创', '言和原创', '心华', '星尘', '海伊',
    # 扩展关键词
    '赤羽', '诗岸', '苍穹', '永夜', '牧心', 'Minus',
    'Synthesizer V', 'SynthV', 'SV', '五维介质', '平行四界',
    '初音未来', '镜音铃', '镜音连', '巡音流歌', 'GUMI',
    '重音Teto', '可不', '花谱', '异世界情绪', '理芽',
    # 近期热门标签
    '虚拟歌手', '电子音乐', '原创音乐', '音乐制作', '编曲',
    '调教', '人力VOCALOID', '鬼畜', '音MAD', '新曲'
]

# 默认排除关键词
DEFAULT_EXCLUDE_KEYWORDS = [
    '教程', '教学', '攻略', '游戏', '直播', '录播', '实况',
    '开箱', '测评', '评测', '新闻', '资讯', '动态', 'vlog', 'VLOG',
    '手书', 'MMD', 'mmd', '舞蹈', '翻跳', '宅舞', '手办', '模型',
    '绘画', '画画', '绘图', '插画', '漫画', '动画', '番剧',
    '杂谈', '吐槽', '解说', '反应', 'reaction', 'Reaction',
    '整活', '搞笑', '沙雕', '鬼畜调教', '鬼畜剧', '音游', 'osu',
    '钢琴', '吉他', '乐器', '演奏', '弹奏', 'cover', 'Cover',
    'AMV', 'MAD', 'mad', 'PV', 'pv', 'OP', 'ED', 'op', 'ed'
]

# 默认音乐关键词
DEFAULT_MUSIC_KEYWORDS = [
    '原创', '翻唱', '曲', '歌', '音乐', 'Music', 'music', 'MUSIC',
    '演唱', '合唱', '独唱', '二重唱', '三重唱',
    '调教', '调校', 'cover', 'Cover', 'COVER',
    'VOCALOID', 'Vocaloid', 'vocaloid', 'UTAU', 'SynthV',
    '中V', '日V', '虚拟歌姬', '虚拟歌手'
]

# 默认知名P主列表
DEFAULT_KNOWN_PRODUCERS = [
    'ilem', '乌龟sui', '阿良良木健', 'COP', 'JUSF周存', 'DELA',
    'PoKeR', 'Kide', '阿原adam', '无名社', '煌煌', '纯白',
    '芹菜猪肉大馄饨', 'Sakurayama', '小旭PRO', 'litterzy',
    '杉田朗', '战场原妖精', 'OQQ', '纳兰寻风', '潜移默化'
]

def load_custom_keywords():
    """
    加载自定义关键词配置
    """
    try:
        if os.path.exists(CUSTOM_KEYWORDS_PATH):
            with open(CUSTOM_KEYWORDS_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            return create_default_keywords_config()
    except Exception as e:
        print(f"加载自定义关键词失败: {e}")
        return create_default_keywords_config()

def create_default_keywords_config():
    """
    创建默认关键词配置文件
    """
    default_config = {
        'vocaloid_keywords': DEFAULT_VOCALOID_KEYWORDS,
        'exclude_keywords': DEFAULT_EXCLUDE_KEYWORDS,
        'music_keywords': DEFAULT_MUSIC_KEYWORDS,
        'known_producers': DEFAULT_KNOWN_PRODUCERS,
        'custom_singers': [],  # 用户自定义歌手
        'custom_producers': [],  # 用户自定义P主
        'custom_exclude': [],  # 用户自定义排除词
        'custom_include': [],  # 用户自定义包含词
        # 关键词启用状态（默认关键词不能删除，只能启用/禁用）
        'enabled_keywords': {
            'vocaloid_keywords': True,  # 启用Vocaloid关键词
            'exclude_keywords': True,  # 启用排除关键词
            'music_keywords': True,  # 启用音乐关键词
            'known_producers': True  # 启用知名P主
        }
    }
    try:
        with open(CUSTOM_KEYWORDS_PATH, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, ensure_ascii=False, indent=2)
        print(f"默认关键词配置文件创建成功: {CUSTOM_KEYWORDS_PATH}")
    except Exception as e:
        print(f"创建默认关键词配置文件失败: {e}")
    return default_config

def save_custom_keywords(config):
    """
    保存自定义关键词配置
    """
    try:
        with open(CUSTOM_KEYWORDS_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存自定义关键词失败: {e}")
        return False

# 加载自定义关键词
CUSTOM_KEYWORDS = load_custom_keywords()

# ===================== 推荐系统设置配置 =====================
# 推荐设置配置文件路径
RECOMMEND_SETTINGS_PATH = os.path.expanduser("~/.vocaloid_toolbox_recommend_settings.json")

# 默认推荐设置
DEFAULT_RECOMMEND_SETTINGS = {
    # 是否允许重复推荐（每次刷新是否出现重复）
    'allow_duplicates': False,  # 默认不允许重复
    
    # 数据库范围设置
    'database_scope': 'all',  # 可选值: 'all'(全部), 'favorites'(仅收藏), 'recent'(最近播放)
    
    # 推荐历史记录最大数量
    'max_history_size': 10,
    
    # 推荐刷新间隔（秒）
    'refresh_interval': 30,
    
    # 是否启用智能去重（基于标题相似度）
    'smart_dedup': True,
    
    # 智能去重相似度阈值（0-1之间）
    'dedup_threshold': 0.8,
    
    # 推荐排序偏好
    'sort_preference': 'balanced',  # 可选值: 'hot'(历史热度), 'fresh'(发布时间新鲜度), 'balanced'(平衡)
    
    # 热度权重（0-1之间，仅当sort_preference为'balanced'时有效）
    'hot_weight': 0.5,
    
    # 新鲜度权重（0-1之间，仅当sort_preference为'balanced'时有效）
    'fresh_weight': 0.5
}

def load_recommend_settings():
    """
    加载推荐设置
    """
    try:
        if os.path.exists(RECOMMEND_SETTINGS_PATH):
            with open(RECOMMEND_SETTINGS_PATH, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                # 合并默认设置，确保新字段存在
                merged_settings = DEFAULT_RECOMMEND_SETTINGS.copy()
                merged_settings.update(settings)
                return merged_settings
        else:
            return create_default_recommend_settings()
    except Exception as e:
        print(f"加载推荐设置失败: {e}")
        return DEFAULT_RECOMMEND_SETTINGS.copy()

def create_default_recommend_settings():
    """
    创建默认推荐设置文件
    """
    try:
        with open(RECOMMEND_SETTINGS_PATH, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_RECOMMEND_SETTINGS, f, ensure_ascii=False, indent=2)
        print(f"默认推荐设置文件创建成功: {RECOMMEND_SETTINGS_PATH}")
    except Exception as e:
        print(f"创建默认推荐设置文件失败: {e}")
    return DEFAULT_RECOMMEND_SETTINGS.copy()

def save_recommend_settings(settings):
    """
    保存推荐设置
    """
    try:
        with open(RECOMMEND_SETTINGS_PATH, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存推荐设置失败: {e}")
        return False

# 加载推荐设置
RECOMMEND_SETTINGS = load_recommend_settings()
