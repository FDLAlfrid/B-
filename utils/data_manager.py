"""
数据管理模块 - 智能音乐推荐与分享系统（融合版）
使用JSON文件存储数据，替代SQLite数据库
"""
import json
import os
from pathlib import Path
import sys
from datetime import datetime

# 数据目录和文件路径
if hasattr(sys, '_MEIPASS'):
    # 当作为exe运行时，使用用户主目录存储数据
    USER_DIR = Path.home()
    APP_DIR = USER_DIR / ".vocaloid_toolbox"
    DATA_DIR = APP_DIR / "data"
else:
    # 当在开发环境运行时，使用项目目录
    PROJECT_DIR = Path(__file__).parent.parent.absolute()
    DATA_DIR = PROJECT_DIR / "data"

DATA_FILE = DATA_DIR / "vocaloid_data.json"

def ensure_data_dir():
    """确保数据目录存在"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

def load_data():
    """加载数据"""
    ensure_data_dir()
    if not DATA_FILE.exists():
        # 创建默认数据结构
        default_data = {
            "music": [],
            "settings": {
                "no_image_mode": False,
                "theme": "默认主题",
                "default_sort": "综合排序",
                "download_path": str(PROJECT_DIR / "downloads"),
                "refresh_interval": 300
            }
        }
        save_data(default_data)
        return default_data
    
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"加载数据失败: {e}")
        return {"music": [], "settings": {}}

def save_data(data):
    """保存数据"""
    ensure_data_dir()
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存数据失败: {e}")
        return False

def get_music_data():
    """获取音乐数据"""
    data = load_data()
    return data.get("music", [])

def save_music_data(music_list):
    """保存音乐数据"""
    data = load_data()
    data["music"] = music_list
    return save_data(data)

def get_settings():
    """获取设置"""
    data = load_data()
    return data.get("settings", {})

def load_settings():
    """加载设置"""
    data = load_data()
    return data.get("settings", {})

def save_settings(settings):
    """保存设置"""
    data = load_data()
    data["settings"] = settings
    return save_data(data)

def add_music(music_data):
    """添加音乐数据"""
    music_list = get_music_data()
    
    # 检查是否已存在
    for music in music_list:
        if music.get('bvid') == music_data.get('bvid'):
            return False
    
    music_list.append(music_data)
    return save_music_data(music_list)

def get_music_by_bvid(bvid):
    """根据BV号获取音乐数据"""
    music_list = get_music_data()
    for music in music_list:
        if music.get('bvid') == bvid:
            return music
    return None

def update_music(bvid, update_data):
    """更新音乐数据"""
    music_list = get_music_data()
    for i, music in enumerate(music_list):
        if music.get('bvid') == bvid:
            music_list[i].update(update_data)
            return save_music_data(music_list)
    return False

def delete_music(bvid):
    """删除音乐数据"""
    music_list = get_music_data()
    new_list = [music for music in music_list if music.get('bvid') != bvid]
    if len(new_list) != len(music_list):
        return save_music_data(new_list)
    return False

def clear_music_data():
    """清空音乐数据"""
    return save_music_data([])

def save_favorites_and_excluded(favorites, excluded, user_id=None):
    """保存收藏列表和排除列表"""
    data = load_data()
    data["favorites"] = favorites
    data["excluded"] = excluded
    return save_data(data)

def load_favorites_and_excluded(user_id=None):
    """加载收藏列表和排除列表"""
    data = load_data()
    favorites = data.get("favorites", [])
    excluded = data.get("excluded", [])
    return favorites, excluded

def load_favorites(user_id=None):
    """加载收藏列表"""
    data = load_data()
    return data.get("favorites", [])

def save_favorites(favorites, user_id=None):
    """保存收藏列表"""
    data = load_data()
    data["favorites"] = favorites
    return save_data(data)

def load_excluded(user_id=None):
    """加载排除列表"""
    data = load_data()
    return data.get("excluded", [])

def save_excluded(excluded, user_id=None):
    """保存排除列表"""
    data = load_data()
    data["excluded"] = excluded
    return save_data(data)

def load_playlists():
    """加载播放列表"""
    data = load_data()
    return data.get("playlists", [])

def save_playlists(playlists):
    """保存播放列表"""
    data = load_data()
    data["playlists"] = playlists
    return save_data(data)

def load_share_history():
    """加载分享历史"""
    data = load_data()
    return data.get("share_history", [])

def save_share_history(share_history):
    """保存分享历史"""
    data = load_data()
    data["share_history"] = share_history
    return save_data(data)

def add_share_record(video_data, platform, user_id=None):
    """添加分享记录"""
    from datetime import datetime
    
    share_history = load_share_history()
    
    # 创建分享记录
    share_record = {
        'bvid': video_data.get('bvid'),
        'title': video_data.get('title', '未知标题'),
        'up': video_data.get('up', video_data.get('up主', '未知UP主')),
        'platform': platform,
        'share_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'cover': video_data.get('cover', '')
    }
    
    # 添加到历史记录开头
    share_history.insert(0, share_record)
    
    # 限制历史记录数量（最多保存100条）
    if len(share_history) > 100:
        share_history = share_history[:100]
    
    # 保存
    save_share_history(share_history)
    return True


# ===================== 浏览记录管理 =====================

def load_viewed_bvids():
    """加载已浏览的BV号列表"""
    data = load_data()
    return data.get("viewed_bvids", [])

def save_viewed_bvids(viewed_bvids):
    """保存已浏览的BV号列表"""
    data = load_data()
    data["viewed_bvids"] = viewed_bvids
    return save_data(data)

def mark_as_viewed(bvid):
    """标记视频为已浏览"""
    if not bvid:
        return False
    
    viewed_bvids = load_viewed_bvids()
    if bvid not in viewed_bvids:
        viewed_bvids.append(bvid)
        # 限制浏览记录数量（最多保存5000条）
        if len(viewed_bvids) > 5000:
            viewed_bvids = viewed_bvids[-5000:]
        return save_viewed_bvids(viewed_bvids)
    return True

def is_viewed(bvid):
    """检查视频是否已浏览"""
    viewed_bvids = load_viewed_bvids()
    return bvid in viewed_bvids

def get_unviewed_music():
    """获取未浏览的音乐列表"""
    music_list = get_music_data()
    viewed_bvids = load_viewed_bvids()
    return [m for m in music_list if m.get('bvid') not in viewed_bvids]

def get_viewed_count():
    """获取已浏览视频数量"""
    return len(load_viewed_bvids())

def get_unviewed_count():
    """获取未浏览视频数量"""
    return len(get_unviewed_music())

def clear_viewed_history():
    """清空浏览历史"""
    return save_viewed_bvids([])


# ===================== 上次推荐状态管理 =====================

def save_last_recommendations(recommendations: list, scroll_position: int = 0):
    """
    保存上次推荐列表和滚动位置
    :param recommendations: 推荐视频列表
    :param scroll_position: 滚动位置
    """
    data = load_data()
    data["last_recommendations"] = {
        "videos": recommendations,
        "scroll_position": scroll_position,
        "saved_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    return save_data(data)

def load_last_recommendations():
    """
    加载上次推荐列表和滚动位置
    :return: (视频列表, 滚动位置) 或 (None, 0)
    """
    data = load_data()
    last_rec = data.get("last_recommendations", {})
    if last_rec:
        return last_rec.get("videos", []), last_rec.get("scroll_position", 0)
    return None, 0

def clear_last_recommendations():
    """清除上次推荐记录"""
    data = load_data()
    if "last_recommendations" in data:
        del data["last_recommendations"]
        return save_data(data)
    return True


# ===================== 点击记录管理 =====================

def load_clicked_bvids():
    """加载已点击的BV号列表（用户实际点击过的视频）"""
    data = load_data()
    return data.get("clicked_bvids", [])

def save_clicked_bvids(clicked_bvids):
    """保存已点击的BV号列表"""
    data = load_data()
    data["clicked_bvids"] = clicked_bvids
    return save_data(data)

def mark_as_clicked(bvid):
    """标记视频为已点击（用户实际点击播放过）"""
    if not bvid:
        return False
    
    clicked_bvids = load_clicked_bvids()
    if bvid not in clicked_bvids:
        clicked_bvids.append(bvid)
        # 限制记录数量（最多保存2000条）
        if len(clicked_bvids) > 2000:
            clicked_bvids = clicked_bvids[-2000:]
        return save_clicked_bvids(clicked_bvids)
    return True

def is_clicked(bvid):
    """检查视频是否已点击过"""
    clicked_bvids = load_clicked_bvids()
    return bvid in clicked_bvids

def get_clicked_count():
    """获取已点击视频数量"""
    return len(load_clicked_bvids())

def clear_clicked_history():
    """清空点击历史"""
    return save_clicked_bvids([])


def get_videos_with_empty_playcount():
    """
    获取播放量为0或空的视频列表
    :return: 需要重新抓取的视频BV号列表
    """
    music_list = get_music_data()
    empty_videos = []
    
    for music in music_list:
        bvid = music.get('bvid', '')
        play_count = music.get('play_count', 0)
        
        # 检测播放量为0、空、None或不存在的情况
        if not play_count or play_count == 0 or play_count == '0' or play_count == '':
            empty_videos.append(bvid)
    
    return empty_videos


def mark_videos_for_refetch(bvids: list):
    """
    标记视频需要重新抓取（从数据库中移除）
    :param bvids: 需要重新抓取的BV号列表
    :return: 移除的视频数量
    """
    if not bvids:
        return 0
    
    music_list = get_music_data()
    original_count = len(music_list)
    
    # 过滤掉需要重新抓取的视频
    filtered_list = [m for m in music_list if m.get('bvid') not in bvids]
    
    removed_count = original_count - len(filtered_list)
    
    if removed_count > 0:
        save_music_data(filtered_list)
        print(f"已标记 {removed_count} 个播放量为空的视频重新抓取")
    
    return removed_count


# ===================== 数据库管理配置 =====================

# 默认数据库管理配置
DEFAULT_DB_CONFIG = {
    "target_size": 500,  # 目标数据库大小（视频数量）
    "min_threshold": 50,  # 触发后台抓取的阈值（未浏览视频少于这个数时触发）
    "auto_fetch": True,   # 是否自动后台抓取
    "max_fetch_per_session": 100  # 每次抓取最大数量
}

def load_db_config():
    """加载数据库管理配置"""
    data = load_data()
    config = data.get("db_config", {})
    # 合并默认配置
    merged_config = DEFAULT_DB_CONFIG.copy()
    merged_config.update(config)
    return merged_config

def save_db_config(config):
    """保存数据库管理配置"""
    data = load_data()
    data["db_config"] = config
    return save_data(data)

def update_db_config(**kwargs):
    """更新数据库管理配置"""
    config = load_db_config()
    config.update(kwargs)
    return save_db_config(config)

def get_db_stats():
    """获取数据库统计信息"""
    music_list = get_music_data()
    viewed_bvids = load_viewed_bvids()
    config = load_db_config()
    
    total = len(music_list)
    viewed = len(viewed_bvids)
    unviewed = total - viewed
    
    return {
        "total": total,
        "viewed": viewed,
        "unviewed": unviewed,
        "target_size": config.get("target_size", 500),
        "min_threshold": config.get("min_threshold", 50),
        "needs_fetch": unviewed < config.get("min_threshold", 50) and config.get("auto_fetch", True)
    }

# 测试函数
if __name__ == "__main__":
    print("测试数据管理模块...")
    
    # 测试加载数据
    data = load_data()
    print(f"加载的数据: {data}")
    
    # 测试添加音乐
    test_music = {
        "bvid": "BV123456789",
        "title": "测试歌曲",
        "up主": "测试UP主",
        "cover": "https://example.com/cover.jpg",
        "play_url": "https://www.bilibili.com/video/BV123456789",
        "pub_time": 1640995200,
        "play_count": 1000
    }
    
    result = add_music(test_music)
    print(f"添加音乐结果: {result}")
    
    # 测试获取音乐
    music = get_music_by_bvid("BV123456789")
    print(f"获取的音乐: {music}")
    
    # 测试更新音乐
    update_result = update_music("BV123456789", {"play_count": 2000})
    print(f"更新音乐结果: {update_result}")
    
    # 测试删除音乐
    delete_result = delete_music("BV123456789")
    print(f"删除音乐结果: {delete_result}")
    
    print("测试完成!")