import os
import sys

if getattr(sys, 'frozen', False):
    BASE_PATH = sys._MEIPASS
else:
    BASE_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FONT_PATH = os.path.join(BASE_PATH, '原神字体.ttf')
ICON_PATH = os.path.join(BASE_PATH, 'icon.png')
SETTINGS_PATH = os.path.join(os.path.expanduser('~'), '.bilibili_toolbox_settings.json')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
    "Accept": "application/json, text/plain, */*"
}

API_URL = "https://api.bilibili.com/x/web-interface/view?bvid={}"
SEARCH_URL = "https://api.bilibili.com/x/web-interface/search/type"

SORT_MAP = {
    '综合排序': 'totalrank',
    '最多播放': 'click',
    '最新发布': 'pubdate',
    '最多弹幕': 'dm',
    '最多收藏': 'stow'
}

THEMES = {
    '默认主题': {'primary': '#1E88E5', 'secondary': '#64B5F6', 'background': '#FAFAFA', 'text': '#212121'},
    '科技商务': {'primary': '#0D47A1', 'secondary': '#1565C0', 'background': '#F5F5F5', 'text': '#212121'},
    '洛天依': {'primary': '#64B5F6', 'secondary': '#90CAF9', 'background': '#E3F2FD', 'text': '#1565C0'},
    '乐正绫': {'primary': '#E53935', 'secondary': '#EF5350', 'background': '#FFEBEE', 'text': '#C62828'},
    '言和': {'primary': '#43A047', 'secondary': '#66BB6A', 'background': '#E8F5E8', 'text': '#2E7D32'},
    'custom': {'primary': '#3498db', 'secondary': '#2980b9', 'background': '#f5f5f5', 'text': '#2c3e50'}
}
