import requests
from datetime import datetime
from ..models import Music

class BilibiliService:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0 Safari/537.36",
            "Referer": "https://www.bilibili.com/"
        }
        self.api_url = "https://api.bilibili.com/x/web-interface/ranking/region"
        # 分区ID映射
        self.region_map = {
            30: "VOCALOID·UTAU",
            29: "华语",
            190: "其他"
        }
        # 语言分类关键词
        self.language_keywords = {
            'chinese': ['中文', '华语', '普通话', '粤语', '国V', '中V'],
            'japanese': ['日语', '日文', '日V', '日本'],
            'english': ['英语', '英文', '欧美']
        }
        
    def fetch_vocaloid_music(self, rid=30, limit=20):
        """获取B站VOCALOID分区音乐"""
        params = {
            'rid': rid,
            'day': 7,
            'ps': limit
        }
        
        try:
            print(f"请求B站API: {self.api_url}")
            print(f"请求参数: {params}")
            
            response = requests.get(
                self.api_url,
                params=params,
                headers=self.headers,
                timeout=10
            )
            
            print(f"响应状态码: {response.status_code}")
            print(f"API响应内容: {response.text[:500]}...")
            
            data = response.json()
            print(f"API响应数据: {data}")
            
            if data.get('code') == 0 and 'data' in data:
                # 检查不同的数据结构可能性
                if isinstance(data['data'], list):
                    print(f"直接返回列表数据，数据长度: {len(data['data'])}")
                    return self._parse_music_data(data['data'], rid)
                elif 'list' in data['data']:
                    print(f"使用list数据结构，数据长度: {len(data['data']['list'])}")
                    return self._parse_music_data(data['data']['list'], rid)
                elif 'archives' in data['data']:
                    print(f"使用archives数据结构，数据长度: {len(data['data']['archives'])}")
                    return self._parse_music_data(data['data']['archives'], rid)
                else:
                    print(f"未知的数据结构，keys: {list(data['data'].keys())}")
                    return []
            else:
                print(f"API返回错误: code={data.get('code')}, message={data.get('message', '未知错误')}")
                return []
        except Exception as e:
            print(f"获取B站数据失败: {str(e)}")
            return []
    
    def _parse_music_data(self, raw_data, rid):
        """解析原始音乐数据，增加分类功能"""
        music_list = []
        for item in raw_data:
            # 调试：打印原始数据项
            print(f"原始数据项: {item}")
            
            # 将时间字符串转换为秒数
            duration_str = item.get('duration', '0:00')
            print(f"原始duration字符串: '{duration_str}' (类型: {type(duration_str)})")
            duration_seconds = self._convert_duration_to_seconds(duration_str)
            print(f"转换后的秒数: {duration_seconds}")
            
            # 获取标签
            tags = []
            if isinstance(item.get('tags'), list):
                tags = [tag.get('tag_name', '') for tag in item.get('tags', [])]
            elif isinstance(item.get('tag'), str):
                tags = [item.get('tag')]
            elif isinstance(item.get('tags'), str):
                tags = [item.get('tags')]
            
            # 根据分区和标签进行分类
            category = self._classify_music(rid, tags, item.get('title', ''), item.get('author', ''))
            
            # 根据API响应调整字段映射
            music_info = {
                'bvid': item.get('bvid'),
                'title': item.get('title'),
                'author': item.get('author', item.get('owner', {}).get('name', '未知作者')),
                'cover_url': item.get('pic'),
                'duration': duration_seconds,
                'tags': ','.join(tags),
                'view_count': item.get('play', item.get('stat', {}).get('view', 0)),
                'pubdate': int(datetime.now().timestamp()),  # 使用当前时间作为发布时间
                'category': category,  # 添加分类信息
                'rid': rid  # 添加分区ID
            }
            
            print(f"解析后的音乐信息: {music_info}")
            music_list.append(music_info)
        return music_list
    
    def _classify_music(self, rid, tags, title, author):
        """根据分区ID、标签、标题和作者信息对音乐进行分类"""
        # 首先根据分区ID确定基本分类
        category = self.region_map.get(rid, "其他")
        
        # 如果是其他分区，尝试通过标签和标题进一步分类
        if category == "其他":
            all_text = ' '.join([title, author] + tags).lower()
            
            # 检查中文关键词
            for keyword in self.language_keywords['chinese']:
                if keyword.lower() in all_text:
                    return "华语"
            
            # 检查英文关键词
            for keyword in self.language_keywords['english']:
                if keyword.lower() in all_text:
                    return "其他-英文"
        
        return category
    
    def _convert_duration_to_seconds(self, duration_str):
        """将时间字符串(MM:SS)转换为秒数"""
        try:
            if ':' in duration_str:
                parts = duration_str.split(':')
                if len(parts) == 2:
                    minutes = int(parts[0])
                    seconds = int(parts[1])
                    return minutes * 60 + seconds
                elif len(parts) == 3:
                    hours = int(parts[0])
                    minutes = int(parts[1])
                    seconds = int(parts[2])
                    return hours * 3600 + minutes * 60 + seconds
            # 如果格式不正确，返回0
            return 0
        except (ValueError, AttributeError):
            return 0
    
    def save_music_to_db(self, music_data):
        """保存音乐数据到数据库"""
        from .. import db
        
        for music_info in music_data:
            existing = Music.query.filter_by(bvid=music_info['bvid']).first()
            current_time = int(datetime.now().timestamp())
            if existing:
                # 更新现有记录
                existing.title = music_info['title']
                existing.author = music_info['author']
                existing.cover_url = music_info['cover_url']
                existing.duration = music_info['duration']
                existing.tags = music_info['tags']
                existing.view_count = music_info['view_count']
                existing.category = music_info.get('category', '其他')
                existing.rid = music_info.get('rid', 0)
                existing.crawl_time = current_time
            else:
                # 创建新记录
                new_music = Music(
                    bvid=music_info['bvid'],
                    title=music_info['title'],
                    author=music_info['author'],
                    cover_url=music_info['cover_url'],
                    duration=music_info['duration'],
                    tags=music_info['tags'],
                    view_count=music_info['view_count'],
                    category=music_info.get('category', '其他'),
                    rid=music_info.get('rid', 0),
                    crawl_time=current_time
                )
                db.session.add(new_music)
        db.session.commit()