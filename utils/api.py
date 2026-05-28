import requests
import time
import random
import json
import os
import re
from datetime import datetime
from utils.constants import HEADERS, API_URL, SEARCH_URL, SORT_MAP


def parse_play_count(play_raw):
    """
    解析播放量，处理各种格式
    :param play_raw: 原始播放量数据（可能是数字、字符串或带单位的字符串）
    :return: 整数播放量
    """
    if play_raw is None:
        return 0

    # 如果已经是数字，直接返回
    if isinstance(play_raw, (int, float)):
        return int(play_raw)

    # 如果是字符串
    if isinstance(play_raw, str):
        play_str = play_raw.strip()

        # 处理 "--" 或其他非数字标记
        if play_str in ['--', '-', '', 'None', 'null']:
            return 0

        # 处理带 "万" 的字符串（如 "1.2万"）
        if '万' in play_str:
            match = re.search(r'(\d+\.?\d*)', play_str)
            if match:
                return int(float(match.group(1)) * 10000)
            return 0

        # 处理带 "亿" 的字符串
        if '亿' in play_str:
            match = re.search(r'(\d+\.?\d*)', play_str)
            if match:
                return int(float(match.group(1)) * 100000000)
            return 0

        # 处理纯数字字符串
        try:
            return int(float(play_str.replace(',', '')))
        except (ValueError, TypeError):
            return 0

    return 0

SETTINGS_PATH = os.path.join(os.path.expanduser('~'), '.bilibili_toolbox_settings.json')

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]

session = requests.Session()

def get_random_headers():
    user_agent = random.choice(USER_AGENTS)
    return {
        "User-Agent": user_agent,
        "Referer": "https://www.bilibili.com",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Cache-Control": "max-age=0"
    }

last_request_time = 0
MIN_REQUEST_INTERVAL = 5.0

def rate_limit():
    global last_request_time
    current_time = time.time()
    time_since_last_request = current_time - last_request_time
    
    if time_since_last_request < MIN_REQUEST_INTERVAL:
        sleep_time = MIN_REQUEST_INTERVAL - time_since_last_request + random.uniform(1.0, 2.0)
        time.sleep(sleep_time)
    
    last_request_time = time.time()

def bv2av(bvid: str) -> int:
    table = 'fZodR9XQDSUm21yCkr6zBqiveYah8bt4xsWpHnJE7jL5VG3guMTKNPAwcF'
    tr = {c: i for i, c in enumerate(table)}
    s = [11, 10, 3, 8, 4, 6, 2, 9, 5, 7]
    xor = 177451812
    add = 8728348608
    try:
        r = 0
        for i in range(10):
            r += tr[bvid[s[i]]] * 58 ** i
        aid = (r - add) ^ xor
        return aid
    except Exception as e:
        raise ValueError(f"BV号格式错误：{bvid}，错误信息：{str(e)}")

def av2bv(aid: int) -> str:
    table = 'fZodR9XQDSUm21yCkr6zBqiveYah8bt4xsWpHnJE7jL5VG3guMTKNPAwcF'
    s = [11, 10, 3, 8, 4, 6, 2, 9, 5, 7]
    xor = 177451812
    add = 8728348608
    aid = (aid ^ xor) + add
    r = list('BV1  4 1 7  ')
    for i in range(10):
        r[s[i]] = table[aid // 58 ** i % 58]
    return ''.join(r)

def get_bilibili_video_info(bvid: str) -> dict:
    if not bvid.startswith("BV") or len(bvid) != 12:
        return {"error": f"BV号格式错误：{bvid}（需以BV开头，长度12位）"}
    try:
        response = requests.get(API_URL.format(bvid), headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data["code"] == 0:
            video_data = data["data"]
            pub_time = datetime.fromtimestamp(video_data["pubdate"]).strftime("%Y-%m-%d %H:%M:%S")
            result = {
                "基础信息": {
                    "BV号": video_data["bvid"],
                    "AV号": f"av{video_data['aid']}",
                    "视频标题": video_data["title"],
                    "发布时间": pub_time,
                    "视频简介": video_data["desc"][:100] + "..." if len(video_data["desc"]) > 100 else video_data["desc"]
                },
                "UP主信息": {
                    "UP主名称": video_data["owner"]["name"],
                    "UP主UID": video_data["owner"]["mid"],
                    "UP主主页": f"https://space.bilibili.com/{video_data['owner']['mid']}"
                },
                "数据统计": {
                    "播放量": video_data["stat"]["view"],
                    "弹幕数": video_data["stat"]["danmaku"],
                    "点赞数": video_data["stat"]["like"],
                    "投币数": video_data["stat"]["coin"],
                    "收藏数": video_data["stat"]["favorite"],
                    "转发数": video_data["stat"]["share"]
                },
                "其他": {
                    "视频时长(秒)": video_data["duration"],
                    "分区名称": video_data["tname"],
                    "视频链接": f"https://www.bilibili.com/video/{video_data['bvid']}"
                }
            }
            return result
        else:
            return {"error": f"API返回错误：{data['message']}"}
    except requests.exceptions.Timeout:
        return {"error": "请求超时，请检查网络"}
    except Exception as e:
        return {"error": f"网络请求失败：{str(e)}"}

def search_bilibili_videos(keyword: str, sort_type: str = '综合排序', page: int = 1) -> dict:
    rate_limit()
    
    order = SORT_MAP.get(sort_type, 'totalrank')
    
    try:
        params = {
            'search_type': 'video',
            'keyword': keyword,
            'page': page,
            'order': order,
            'duration': '',
            'tids_1': '',
            'tids_2': ''
        }
        
        headers = get_random_headers()
        
        response = session.get(SEARCH_URL, params=params, headers=headers, timeout=15, allow_redirects=True)
        response.raise_for_status()
        data = response.json()
        
        if data["code"] == 0:
            videos = data.get("data", {}).get("result", [])
            results = []
            
            for idx, video in enumerate(videos[:10], 1):
                try:
                    import html
                    title = video.get("title", "")
                    title = html.unescape(title).replace("<em class=\"keyword\">", "").replace("</em>", "")
                    author = video.get("author", "")
                    bvid = video.get("bvid", "")
                    # 处理播放量，可能是字符串、数字或带单位的字符串
                    play_raw = video.get("play", 0)
                    play = parse_play_count(play_raw)
                    pubdate = video.get("pubdate", "")
                    description = video.get("description", "")
                    pic = video.get("pic", "")
                    
                    results.append({
                        "序号": idx,
                        "标题": title,
                        "UP主": author,
                        "BV号": bvid,
                        "播放量": play,
                        "发布时间": pubdate,
                        "简介": description,
                        "封面": pic
                    })
                except Exception as e:
                    continue
            
            return {"results": results, "total": len(results)}
        else:
            return {"error": f"API返回错误：{data.get('message', '未知错误')}"}
    except requests.exceptions.Timeout:
        return {"error": "请求超时，请检查网络"}
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 412:
            return {"error": "搜索频率过高，请稍后再试（建议关闭\"加载封面\"选项）"}
        return {"error": f"HTTP错误：{e.response.status_code}"}
    except Exception as e:
        return {"error": f"搜索失败：{str(e)}"}


def get_bilibili_data(bvid):
    """获取哔哩哔哩数据"""
    return get_bilibili_video_info(bvid)
