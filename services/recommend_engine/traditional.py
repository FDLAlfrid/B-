"""
推荐引擎 - 智能音乐推荐与分享系统（融合版）
"""
import random
import time
import threading
from typing import List, Dict, Any
from datetime import datetime, timedelta
from functools import lru_cache

from utils.data_manager import (get_music_data, add_music, save_music_data,
                                  get_unviewed_music, mark_as_viewed, get_db_stats,
                                  load_db_config, update_db_config,
                                  get_videos_with_empty_playcount, mark_videos_for_refetch)
from utils.api import parse_play_count
from config import (RECOMMEND_WEIGHTS, DEFAULT_RECOMMEND_LIMIT, MAX_RECOMMEND_LIMIT,
                    CUSTOM_KEYWORDS, load_custom_keywords, RECOMMEND_SETTINGS, 
                    load_recommend_settings, save_recommend_settings)


class RecommendEngine:
    """推荐引擎 - 优化版"""
    
    def __init__(self):
        self.weights = RECOMMEND_WEIGHTS
        self.cache = {}
        self.cache_expiry = 600  # 缓存过期时间（秒）- 增加到10分钟
        self.last_fetch_time = 0  # 上次抓取时间
        self.min_fetch_interval = 30  # 最小抓取间隔（秒）- 减少到30秒
        self.db_initialized = False  # 数据库初始化标志
        self.keywords_config = CUSTOM_KEYWORDS  # 加载关键词配置
        
        # 性能优化
        self._cache_lock = threading.Lock()  # 缓存锁
        self._db_cache = None  # 数据库缓存
        self._db_cache_time = 0  # 数据库缓存时间
        self._db_cache_ttl = 60  # 数据库缓存TTL（秒）
        self._keywords_cache = None  # 关键词缓存
        self._keywords_cache_time = 0  # 关键词缓存时间
        self._keywords_cache_ttl = 300  # 关键词缓存TTL（秒）
        
        # 推荐历史记录（用于回退功能）
        self._recommendation_history = []  # 历史推荐列表
        self._current_index = -1  # 当前推荐索引
        self._max_history_size = RECOMMEND_SETTINGS.get('max_history_size', 10)  # 最大历史记录数
        
        # 推荐设置
        self._recommend_settings = RECOMMEND_SETTINGS
        self._shown_bvids = set()  # 已展示的BV号集合（用于去重）
        self._shown_titles = []  # 已展示的标题列表（用于智能去重）
        
        # B站音乐相关分区ID
        self._music_categories = {
            129: "音乐",           # 音乐区
            193: "音乐现场",       # 音乐现场
            243: "音乐综合",       # 音乐综合
            259: "音乐教学",       # 音乐教学
            260: "音乐演奏",       # 音乐演奏
            261: "音乐翻唱",       # 音乐翻唱
            262: "音乐原创",       # 音乐原创
            263: "音乐MV",         # 音乐MV
            294: "音乐其他"        # 音乐其他
        }
        
        # 音乐相关标签
        self._music_tags = [
            'VOCALOID', '虚拟歌手', '洛天依', '乐正绫',
            '言和', '初音未来', '音乐', '歌曲',
            '翻唱', '原创', 'PV', 'MV', '调教', '调校',
            'COVER', 'vocaloid', 'Vocaloid', 'UTAU', 'SynthV'
        ]
        
        # 保留少量排除关键词作为补充
        self._exclude_keywords = [
            '军事', '战争', '武器', '导弹', '政治',
            '游戏', '电竞', '直播', '动漫', '影视'
        ]
    
    def get_keywords(self):
        """获取合并后的关键词配置 - 带缓存"""
        current_time = time.time()
        
        # 检查缓存是否有效
        if (self._keywords_cache is not None and 
            current_time - self._keywords_cache_time < self._keywords_cache_ttl):
            return self._keywords_cache
        
        config = load_custom_keywords()
        enabled_keywords = config.get('enabled_keywords', {})
        
        # 根据启用状态合并关键词
        vocaloid_keywords = []
        if enabled_keywords.get('vocaloid_keywords', True):
            vocaloid_keywords = config.get('vocaloid_keywords', [])
        vocaloid_keywords = vocaloid_keywords + config.get('custom_singers', []) + config.get('custom_include', [])
        
        exclude_keywords = []
        if enabled_keywords.get('exclude_keywords', True):
            exclude_keywords = config.get('exclude_keywords', [])
        # 添加少量排除关键词作为补充
        exclude_keywords = exclude_keywords + self._exclude_keywords + config.get('custom_exclude', [])
        # 去重
        exclude_keywords = list(set(exclude_keywords))
        
        music_keywords = []
        if enabled_keywords.get('music_keywords', True):
            music_keywords = config.get('music_keywords', [])
        
        known_producers = []
        if enabled_keywords.get('known_producers', True):
            known_producers = config.get('known_producers', [])
        known_producers = known_producers + config.get('custom_producers', [])
        
        result = (vocaloid_keywords, exclude_keywords, music_keywords, known_producers)
        
        # 更新缓存
        self._keywords_cache = result
        self._keywords_cache_time = current_time
        
        return result
    
    def get_hot_recommendations(self, limit: int = DEFAULT_RECOMMEND_LIMIT, force_refresh: bool = False, excluded_bvids: list = None, cloud_control=None, use_history: bool = True) -> List[Dict[str, Any]]:
        """
        获取热门推荐（优先从云端获取，再从数据库获取，最后从API补充）
        :param limit: 推荐数量
        :param force_refresh: 是否强制刷新，忽略缓存和抓取间隔，直接从API获取
        :param excluded_bvids: 排除的BV号列表
        :param cloud_control: 云端调控实例
        :param use_history: 是否记录到历史记录
        :return: 推荐结果列表
        """
        import time
        import sys
        
        # 设置正确的编码
        if sys.stdout.encoding != 'utf-8':
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        
        # 处理排除列表：支持字符串列表和dict列表两种格式
        excluded_set = set()
        if excluded_bvids and isinstance(excluded_bvids, list):
            if excluded_bvids and isinstance(excluded_bvids[0], dict):
                # dict列表格式：提取bvid字段
                excluded_set = {item.get('bvid') for item in excluded_bvids if item.get('bvid')}
            else:
                # 字符串列表格式
                excluded_set = set(excluded_bvids)
        
        # 检查缓存（强制刷新时忽略缓存）
        cache_key = f"hot_recommendations_{limit}"
        if not force_refresh and cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if time.time() - timestamp < self.cache_expiry:
                print("从缓存获取热门推荐，节省API请求")
                # 过滤掉排除的BV号
                if excluded_set:
                    cached_data = [item for item in cached_data if item.get('bvid') not in excluded_set]
                results = cached_data[:limit]
                # 添加到历史记录
                if use_history:
                    self._add_to_history(results)
                return results
        
        # 强制刷新时，先尝试从Bilibili API获取新数据
        if force_refresh:
            print("强制刷新：尝试从Bilibili API获取新数据...")
            try:
                api_results = self._fetch_from_bilibili_api(limit, excluded_set)
                if api_results:
                    print(f"从API获取到 {len(api_results)} 条新推荐")
                    # 保存到本地数据库
                    self._save_api_results_to_db(api_results)
                    # 更新缓存
                    self.cache[cache_key] = (api_results, time.time())
                    # 添加到历史记录
                    if use_history:
                        self._add_to_history(api_results[:limit])
                    return api_results[:limit]
            except Exception as e:
                print(f"从API获取数据失败: {e}")
            # API失败时，继续执行后续逻辑从数据库获取
        
        # 尝试从云端获取热门推荐
        if cloud_control:
            try:
                cloud_results = cloud_control.get_hot_recommendations(limit)
                if cloud_results:
                    print(f"从云端获取到 {len(cloud_results)} 条热门推荐")
                    # 过滤掉排除的BV号
                    if excluded_set:
                        cloud_results = [item for item in cloud_results if item.get('bvid') not in excluded_set]
                    # 更新缓存
                    self.cache[cache_key] = (cloud_results, time.time())
                    # 添加到历史记录
                    if use_history:
                        self._add_to_history(cloud_results[:limit])
                    return cloud_results[:limit]
            except Exception as e:
                print(f"从云端获取热门推荐失败: {e}")
        
        # 从本地数据库获取推荐
        try:
            results = self._get_recommendations_from_db(limit)
            
            # 过滤掉排除的BV号
            if excluded_set:
                results = [item for item in results if item.get('bvid') not in excluded_set]
            
            # 去重处理（如果不允许重复）
            if not self._recommend_settings.get('allow_duplicates', False):
                results = self.filter_duplicates(results)
                # 如果去重后数量不足，获取更多数据
                if len(results) < limit:
                    print(f"去重后数量不足({len(results)}/{limit})，获取更多数据...")
                    more_results = self._get_recommendations_from_db(limit * 3)
                    if excluded_set:
                        more_results = [item for item in more_results if item.get('bvid') not in excluded_set]
                    more_results = self.filter_duplicates(more_results)
                    # 合并结果并去重
                    seen_bvids = set(item.get('bvid') for item in results)
                    for item in more_results:
                        if item.get('bvid') not in seen_bvids:
                            results.append(item)
                            seen_bvids.add(item.get('bvid'))
                        if len(results) >= limit:
                            break
            
            # 截取所需数量
            results = results[:limit]
            
            # 更新缓存
            self.cache[cache_key] = (results, time.time())
            
            # 添加到历史记录
            if use_history:
                self._add_to_history(results)
                # 标记为已展示
                self._mark_as_shown(results)
            
            return results
            
        except Exception as e:
            print(f"获取推荐失败: {e}")
            return []
    
    def _add_to_history(self, recommendations: List[Dict[str, Any]]):
        """添加推荐结果到历史记录"""
        if not recommendations:
            return
        
        # 如果当前不是最新的记录，删除当前位置之后的记录
        if self._current_index < len(self._recommendation_history) - 1:
            self._recommendation_history = self._recommendation_history[:self._current_index + 1]
        
        # 添加新记录
        self._recommendation_history.append({
            'timestamp': datetime.now().isoformat(),
            'recommendations': recommendations.copy(),
            'count': len(recommendations)
        })
        
        # 限制历史记录大小
        if len(self._recommendation_history) > self._max_history_size:
            self._recommendation_history.pop(0)
        
        # 更新当前索引
        self._current_index = len(self._recommendation_history) - 1
    
    def can_go_back(self) -> bool:
        """检查是否可以回退到上一次推荐"""
        return self._current_index > 0
    
    def can_go_forward(self) -> bool:
        """检查是否可以前进到下一次推荐"""
        return self._current_index < len(self._recommendation_history) - 1
    
    def go_back(self) -> List[Dict[str, Any]]:
        """
        回退到上一次推荐
        :return: 上一次的推荐结果，如果没有则返回空列表
        """
        if not self.can_go_back():
            print("没有更早的推荐记录")
            return []
        
        self._current_index -= 1
        history_item = self._recommendation_history[self._current_index]
        print(f"回退到第 {self._current_index + 1} 次推荐（共 {len(self._recommendation_history)} 次）")
        return history_item['recommendations'].copy()
    
    def go_forward(self) -> List[Dict[str, Any]]:
        """
        前进到下一次推荐
        :return: 下一次的推荐结果，如果没有则返回空列表
        """
        if not self.can_go_forward():
            print("没有更新的推荐记录")
            return []
        
        self._current_index += 1
        history_item = self._recommendation_history[self._current_index]
        print(f"前进到第 {self._current_index + 1} 次推荐（共 {len(self._recommendation_history)} 次）")
        return history_item['recommendations'].copy()
    
    def get_current_recommendations(self) -> List[Dict[str, Any]]:
        """获取当前推荐结果"""
        if self._current_index < 0 or self._current_index >= len(self._recommendation_history):
            return []
        return self._recommendation_history[self._current_index]['recommendations'].copy()
    
    def get_history_info(self) -> Dict[str, Any]:
        """获取历史记录信息"""
        return {
            'current_index': self._current_index,
            'total_count': len(self._recommendation_history),
            'can_go_back': self.can_go_back(),
            'can_go_forward': self.can_go_forward(),
            'history': [
                {
                    'index': i,
                    'timestamp': item['timestamp'],
                    'count': item['count']
                }
                for i, item in enumerate(self._recommendation_history)
            ]
        }
    
    def clear_history(self):
        """清空历史记录"""
        self._recommendation_history = []
        self._current_index = -1
        print("推荐历史记录已清空")
    
    def get_settings(self) -> Dict[str, Any]:
        """获取当前推荐设置"""
        return self._recommend_settings.copy()
    
    def update_settings(self, settings: Dict[str, Any]) -> bool:
        """
        更新推荐设置
        :param settings: 新的设置字典
        :return: 是否成功
        """
        try:
            # 更新内存中的设置
            self._recommend_settings.update(settings)
            
            # 更新历史记录大小限制
            if 'max_history_size' in settings:
                self._max_history_size = settings['max_history_size']
                # 如果当前历史记录超过新限制，裁剪
                while len(self._recommendation_history) > self._max_history_size:
                    self._recommendation_history.pop(0)
                    if self._current_index > 0:
                        self._current_index -= 1
            
            # 保存到文件
            success = save_recommend_settings(self._recommend_settings)
            if success:
                print(f"推荐设置已更新: {settings}")
            return success
        except Exception as e:
            print(f"更新推荐设置失败: {e}")
            return False
    
    def reset_shown_items(self):
        """重置已展示的项目（用于清除重复记录）"""
        self._shown_bvids.clear()
        self._shown_titles.clear()
        print("已展示的推荐记录已重置")
    
    def _is_duplicate(self, item: Dict[str, Any]) -> bool:
        """
        检查项目是否是重复的
        :param item: 推荐项目
        :return: 是否重复
        """
        # 检查BV号
        bvid = item.get('bvid', '')
        if bvid and bvid in self._shown_bvids:
            return True
        
        # 如果不允许重复，检查标题相似度
        if not self._recommend_settings.get('allow_duplicates', False):
            title = item.get('title', '')
            if title and self._recommend_settings.get('smart_dedup', True):
                return self._is_title_similar(title)
        
        return False
    
    def _is_title_similar(self, title: str) -> bool:
        """
        检查标题是否与已展示的标题相似
        :param title: 要检查的标题
        :return: 是否相似
        """
        if not title or not self._shown_titles:
            return False
        
        threshold = self._recommend_settings.get('dedup_threshold', 0.8)
        
        for shown_title in self._shown_titles:
            similarity = self._calculate_similarity(title, shown_title)
            if similarity >= threshold:
                return True
        
        return False
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """
        计算两个字符串的相似度（使用简单的Jaccard相似度）
        :param str1: 第一个字符串
        :param str2: 第二个字符串
        :return: 相似度（0-1之间）
        """
        if not str1 or not str2:
            return 0.0
        
        # 转换为小写并分词（简单按字符分词）
        set1 = set(str1.lower())
        set2 = set(str2.lower())
        
        if not set1 or not set2:
            return 0.0
        
        # 计算Jaccard相似度
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        return intersection / union if union > 0 else 0.0
    
    def _mark_as_shown(self, items: List[Dict[str, Any]]):
        """
        标记项目为已展示
        :param items: 推荐项目列表
        """
        for item in items:
            bvid = item.get('bvid', '')
            title = item.get('title', '')
            
            if bvid:
                self._shown_bvids.add(bvid)
            if title:
                self._shown_titles.append(title)
        
        # 限制已展示标题列表的大小
        max_shown = self._recommend_settings.get('max_history_size', 10) * DEFAULT_RECOMMEND_LIMIT
        if len(self._shown_titles) > max_shown:
            self._shown_titles = self._shown_titles[-max_shown:]
    
    def filter_duplicates(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        过滤掉重复的项目
        :param items: 原始推荐列表
        :return: 过滤后的列表
        """
        if self._recommend_settings.get('allow_duplicates', False):
            return items
        
        filtered = []
        for item in items:
            if not self._is_duplicate(item):
                filtered.append(item)
        
        return filtered
    
    def _get_recommendations_from_db(self, limit: int = DEFAULT_RECOMMEND_LIMIT) -> List[Dict[str, Any]]:
        """
        从JSON文件获取推荐 - 带缓存优化
        :param limit: 推荐数量
        :return: 推荐结果列表
        """
        try:
            current_time = time.time()
            
            # 检查数据库缓存是否有效
            with self._cache_lock:
                if (self._db_cache is not None and 
                    current_time - self._db_cache_time < self._db_cache_ttl):
                    # 从缓存返回
                    return self._db_cache[:limit * 2]
            
            # 从JSON文件获取音乐数据
            music_list = get_music_data()
            
            # 获取关键词用于过滤
            vocaloid_keywords, exclude_keywords, music_keywords, known_producers = self.get_keywords()
            
            # 过滤并排序
            filtered_music = []
            for music in music_list:
                title = music.get('title', '')
                author = music.get('up主', '')
                title_lower = title.lower()
                author_lower = author.lower()
                
                # 1. 检查排除关键词 - 增强过滤力度
                # 检查标题
                title_excluded = any(ex_kw.lower() in title_lower or ex_kw in title for ex_kw in exclude_keywords)
                # 检查UP主名称
                author_excluded = any(ex_kw.lower() in author_lower or ex_kw in author for ex_kw in exclude_keywords)
                # 检查完整内容
                content_excluded = any(ex_kw.lower() in (title_lower + ' ' + author_lower) for ex_kw in exclude_keywords)
                
                if title_excluded or author_excluded or content_excluded:
                    continue
                
                # 2. 检查Vocaloid相关关键词
                has_vocaloid_keyword = any(kw.lower() in title_lower or kw in title for kw in vocaloid_keywords)
                if not has_vocaloid_keyword:
                    # 如果标题中没有关键词，检查UP主名
                    if not any(kw in author for kw in vocaloid_keywords):
                        continue
                
                # 3. 确保是音乐内容 - 增强音乐关键词匹配
                has_music_keyword = any(m_kw.lower() in title_lower or m_kw in title for m_kw in music_keywords)
                if not has_music_keyword:
                    # 如果标题中没有音乐关键词，检查UP主名是否是知名P主
                    if not any(producer.lower() in author_lower for producer in known_producers):
                        # 额外检查：如果UP主名包含音乐相关词汇
                        if not any(music_kw in author_lower for music_kw in ['音乐', 'music', 'vocaloid', '歌', '曲', '翻唱', '原创']):
                            continue
                
                # 4. 额外的音乐内容检查
                # 检查标题是否包含音乐相关词汇
                music_related_words = ['歌', '曲', '音乐', 'music', '翻唱', '原创', '演唱', '合唱', '独唱', '二重唱', '三重唱', '调教', '调校', 'cover', 'COVER', 'VOCALOID', 'Vocaloid', 'vocaloid', 'UTAU', 'SynthV']
                has_music_related = any(word in title_lower for word in music_related_words)
                if not has_music_related:
                    # 检查UP主是否是知名P主
                    if not any(producer.lower() in author_lower for producer in known_producers):
                        continue
                
                filtered_music.append(music)
            
            # 按播放量排序
            sorted_music = sorted(filtered_music, key=lambda x: x.get('play_count', 0), reverse=True)
            
            # 转换为推荐结果格式
            results = []
            for music in sorted_music[:limit * 2]:
                results.append({
                    'bvid': music.get('bvid', '未知'),
                    'title': music.get('title', '未知'),
                    'up主': music.get('up主', '未知'),
                    'play_count': music.get('play_count', 0),
                    'cover': music.get('cover', ''),
                    'pub_time': music.get('pub_time', None),
                    'pubdate': music.get('pub_time', None),  # 同时设置pubdate字段
                    '推荐类型': 'JSON文件推荐',
                    '分数': music.get('play_count', 0) / 1000000,
                    'up主UID': music.get('up主UID', '')
                })
            
            # 更新缓存
            with self._cache_lock:
                self._db_cache = results
                self._db_cache_time = current_time
            
            print(f"从本地数据库获取 {len(results)} 条过滤后的推荐（共 {len(music_list)} 条）")
            return results
            
        except Exception as e:
            print(f"从JSON文件获取推荐失败: {e}")
            return []
    
    def _fetch_from_bilibili_api(self, limit: int, excluded_bvids: list = None, max_pages: int = 5) -> List[Dict[str, Any]]:
        """
        从Bilibili API获取热门视频数据（基于分区和标签过滤）
        :param limit: 推荐数量
        :param excluded_bvids: 排除的BV号列表
        :param max_pages: 每个分区最大抓取页数
        :return: 推荐结果列表
        """
        import requests
        import time
        from utils.api import get_random_headers, rate_limit
        
        # 从配置加载关键词
        vocaloid_keywords, exclude_keywords, music_keywords, known_producers = self.get_keywords()
        
        # 创建session对象
        session = requests.Session()
        
        def make_request_with_retry(url, params, headers, max_retries=3, timeout=30):
            """带重试机制的请求函数"""
            for attempt in range(max_retries):
                try:
                    # 调用速率限制
                    rate_limit()
                    # 使用session发送请求
                    response = session.get(url, params=params, headers=headers, timeout=timeout, allow_redirects=True)
                    response.raise_for_status()
                    return response.json()
                except requests.exceptions.Timeout:
                    print(f"请求超时，第 {attempt + 1}/{max_retries} 次重试...")
                    if attempt < max_retries - 1:
                        time.sleep(2)  # 等待2秒后重试
                    else:
                        raise
                except requests.exceptions.HTTPError as e:
                    print(f"HTTP错误: {e.response.status_code}")
                    if e.response.status_code == 412:
                        print("触发412错误，可能需要等待一段时间")
                        time.sleep(5)  # 等待5秒后重试
                        if attempt < max_retries - 1:
                            continue
                    if attempt < max_retries - 1:
                        time.sleep(1)
                    else:
                        raise
                except requests.exceptions.RequestException as e:
                    print(f"请求失败: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(1)
                    else:
                        raise
                except (ConnectionResetError, ConnectionAbortedError) as e:
                    print(f"连接被重置: {e}")
                    if attempt < max_retries - 1:
                        print(f"等待5秒后重试...")
                        time.sleep(5)
                        continue
                    else:
                        print("连接多次被重置，停止重试")
                        return None
            return None
        
        try:
            # 抓取的视频集合（用于去重）
            collected_videos = []
            processed_bvids = set()
            
            # 方法1: 直接抓取音乐分区的热门视频
            print("正在从音乐分区抓取热门视频")
            for page in range(1, max_pages + 1):
                if len(collected_videos) >= limit * 3:
                    break
                
                # 音乐分区热门视频API
                params = {
                    'rid': 129,  # 音乐分区ID
                    'type': 'all',
                    'page': page,
                    'ps': 20
                }
                
                url = "https://api.bilibili.com/x/web-interface/ranking"
                headers = get_random_headers()
                response_data = make_request_with_retry(url, params, headers)
                
                if not response_data or response_data.get('code') != 0:
                    print(f"API请求失败: {response_data}")
                    continue
                
                for video in response_data.get('data', {}).get('list', []):
                    if len(collected_videos) >= limit * 3:
                        break
                    
                    bvid = video.get('bvid')
                    if not bvid or bvid in processed_bvids:
                        continue
                    
                    # 检查是否在排除列表中
                    if excluded_bvids and bvid in excluded_bvids:
                        continue
                    
                    # 解析视频数据
                    title = video.get('title', '')
                    author = video.get('owner', {}).get('name', '未知')
                    play_count = video.get('stat', {}).get('view', 0)
                    pubdate = video.get('pubdate', 0)
                    tid = video.get('tid', 0)
                    tname = video.get('tname', '')
                    tags = video.get('tag', '').split(',')
                    
                    # 1. 检查分区是否为音乐相关
                    if tid not in self._music_categories:
                        continue
                    
                    # 2. 检查标签是否包含音乐相关标签
                    has_music_tag = any(tag in tags for tag in self._music_tags)
                    has_vocaloid_tag = any(tag in tags for tag in vocaloid_keywords)
                    
                    # 3. 补充检查：标题和UP主
                    title_lower = title.lower()
                    author_lower = author.lower()
                    
                    # 4. 检查排除关键词（作为补充）
                    title_excluded = any(ex_kw.lower() in title_lower for ex_kw in exclude_keywords)
                    author_excluded = any(ex_kw.lower() in author_lower for ex_kw in exclude_keywords)
                    
                    if title_excluded or author_excluded:
                        continue
                    
                    # 构建视频信息字典
                    video_info = {
                        'bvid': bvid,
                        'title': title,
                        'up主': author,
                        'play_count': parse_play_count(play_count),
                        'cover': video.get('pic', ''),
                        'pub_time': pubdate,
                        'tid': tid,
                        'tname': tname,
                        'tags': tags,
                        '推荐类型': '音乐分区热门',
                        '分数': parse_play_count(play_count) / 1000000,
                        'up主UID': video.get('owner', {}).get('mid', '')
                    }
                    
                    collected_videos.append(video_info)
                    processed_bvids.add(bvid)
            
            # 方法2: 使用关键词搜索补充
            if len(collected_videos) < limit * 2:
                print("正在使用关键词搜索补充视频")
                search_keywords = vocaloid_keywords[:5]  # 只使用前5个关键词
                
                for keyword in search_keywords:
                    if len(collected_videos) >= limit * 3:
                        break
                    
                    for page in range(1, max_pages + 1):
                        if len(collected_videos) >= limit * 3:
                            break
                        
                        try:
                            search_url = "https://api.bilibili.com/x/web-interface/search/type"
                            params = {
                                'search_type': 'video',
                                'keyword': keyword,
                                'page': page,
                                'page_size': 50,
                                'order': 'click',
                                'duration': 0,
                            }
                            headers = get_random_headers()
                            
                            data = make_request_with_retry(search_url, params, headers)
                            if not data or data.get("code") != 0:
                                continue
                            
                            videos = data.get("data", {}).get("result", [])
                            
                            for video in videos:
                                if len(collected_videos) >= limit * 3:
                                    break
                                
                                bvid = video.get("bvid", "")
                                if not bvid or bvid in processed_bvids:
                                    continue
                                
                                if excluded_bvids and bvid in excluded_bvids:
                                    continue
                                
                                import html
                                title = video.get("title", "未知标题")
                                title = html.unescape(title).replace("<em class=\"keyword\">", "").replace("</em>", "")
                                author = video.get("author", "未知UP主")
                                mid = video.get("mid", "")
                                cover = video.get("pic", "")
                                play_count = parse_play_count(video.get("play", 0))
                                pubdate = video.get("pubdate", 0)
                                tid = video.get("tid", 0)
                                tname = video.get("tname", "")
                                
                                # 检查分区
                                if tid not in self._music_categories:
                                    continue
                                
                                # 构建视频信息字典
                                video_info = {
                                    'bvid': bvid,
                                    'title': title,
                                    'up主': author,
                                    'play_count': play_count,
                                    'cover': cover,
                                    'pub_time': pubdate,
                                    'tid': tid,
                                    'tname': tname,
                                    '推荐类型': f'关键词搜索 ({keyword})',
                                    '分数': play_count / 1000000,
                                    'up主UID': str(mid)
                                }
                                
                                collected_videos.append(video_info)
                                processed_bvids.add(bvid)
                            
                            time.sleep(0.3)  # 稍微增加延迟避免触发限制
                            
                        except Exception as e:
                            print(f"搜索关键词 '{keyword}' 第{page}页失败: {e}")
                            continue
            
            # 按播放量排序
            collected_videos.sort(key=lambda x: x.get('play_count', 0), reverse=True)
            
            # 转换为推荐结果格式
            results = []
            for video in collected_videos[:limit * 2]:
                results.append({
                    'bvid': video.get('bvid', '未知'),
                    'title': video.get('title', '未知'),
                    'up主': video.get('up主', '未知'),
                    'play_count': video.get('play_count', 0),
                    'cover': video.get('cover', ''),
                    'pub_time': video.get('pub_time', None),
                    'pubdate': video.get('pub_time', None),
                    'tid': video.get('tid', 0),
                    'tname': video.get('tname', ''),
                    '推荐类型': video.get('推荐类型', 'API推荐'),
                    '分数': video.get('分数', 0),
                    'up主UID': video.get('up主UID', '')
                })
            
            print(f"成功从API获取 {len(results)} 条音乐相关视频")
            return results
            
        except Exception as e:
            print(f"从Bilibili API获取数据失败: {e}")
            return []
    
    def _save_api_results_to_db(self, results: List[Dict[str, Any]]):
        """
        将API获取的结果保存到本地数据库
        :param results: API返回的结果列表
        """
        try:
            # 获取现有数据
            existing_music = get_music_data()
            existing_bvids = {m.get('bvid') for m in existing_music}
            
            # 添加新数据（避免重复）
            added_count = 0
            for item in results:
                bvid = item.get('bvid')
                if bvid and bvid not in existing_bvids:
                    music_data = {
                        'bvid': bvid,
                        'title': item.get('title'),
                        'up主': item.get('up主'),
                        'up主UID': item.get('up主UID'),
                        'cover': item.get('cover'),
                        'play_count': item.get('play_count', 0),
                        'pubdate': item.get('pubdate', item.get('pub_time')),
                        'pub_time': item.get('pub_time', item.get('pubdate'))
                    }
                    existing_music.append(music_data)
                    existing_bvids.add(bvid)
                    added_count += 1
            
            # 保存到文件
            if added_count > 0:
                save_music_data(existing_music)
                print(f"已将 {added_count} 条新数据保存到本地数据库")
            else:
                print("没有新数据需要保存")
            
        except Exception as e:
            print(f"保存数据到本地数据库失败: {e}")
    
    def clear_cache(self):
        """清除所有缓存"""
        with self._cache_lock:
            self.cache.clear()
            self._db_cache = None
            self._db_cache_time = 0
            self._keywords_cache = None
            self._keywords_cache_time = 0
        print("所有缓存已清除")
    
    def invalidate_db_cache(self):
        """使数据库缓存失效"""
        with self._cache_lock:
            self._db_cache = None
            self._db_cache_time = 0
        print("数据库缓存已失效")
    
    def check_and_fetch_if_needed(self, background=False):
        """
        检查数据库状态，如果需要则在后台抓取新数据
        :param background: 是否在后台运行
        :return: 是否启动了抓取
        """
        stats = get_db_stats()
        
        if stats['needs_fetch']:
            print(f"未浏览视频数量({stats['unviewed']})低于阈值({stats['min_threshold']})，需要补充数据")
            
            # 计算需要抓取的数量
            target = stats['target_size']
            current = stats['total']
            needed = min(target - current, 100)  # 每次最多抓取100条
            needed = max(needed, 50)  # 至少抓取50条
            
            if background:
                # 启动后台线程抓取
                import threading
                thread = threading.Thread(
                    target=self._background_fetch,
                    args=(needed,),
                    daemon=True
                )
                thread.start()
                print(f"已启动后台抓取线程，目标: {needed} 条")
                return True
            else:
                # 同步抓取
                print(f"正在同步抓取 {needed} 条数据...")
                return self._background_fetch(needed)
        
        return False
    
    def _background_fetch(self, limit):
        """
        后台抓取数据
        :param limit: 抓取数量
        :return: 是否成功
        """
        try:
            results = self._fetch_from_bilibili_api(limit=limit, max_pages=10)
            if results:
                self._save_api_results_to_db(results)
                print(f"后台抓取完成，成功保存 {len(results)} 条数据")
                return True
            else:
                print("后台抓取未获取到数据")
                return False
        except Exception as e:
            print(f"后台抓取失败: {e}")
            return False
    
    def get_db_stats(self):
        """获取数据库统计信息"""
        return get_db_stats()
    
    def update_db_config(self, **kwargs):
        """更新数据库配置"""
        return update_db_config(**kwargs)

class RecommendService:
    """推荐服务"""
    
    def __init__(self):
        self.engine = RecommendEngine()
    
    def get_recommendations(self, limit=20, excluded_bvids=None, force_refresh=False, prefer_unviewed=True):
        """
        获取推荐内容
        :param limit: 推荐数量
        :param excluded_bvids: 排除的BV号列表
        :param force_refresh: 是否强制刷新（从API获取新数据）
        :param prefer_unviewed: 是否优先返回未浏览的视频
        :return: 推荐结果列表
        """
        try:
            recommendations = []
            # 处理排除列表：支持字符串列表和dict列表两种格式
            excluded_set = set()
            if excluded_bvids:
                if isinstance(excluded_bvids, list):
                    if excluded_bvids and isinstance(excluded_bvids[0], dict):
                        # dict列表格式：提取bvid字段
                        excluded_set = {item.get('bvid') for item in excluded_bvids if item.get('bvid')}
                    else:
                        # 字符串列表格式
                        excluded_set = set(excluded_bvids)
            
            # 优先从本地未浏览视频获取（无论是否强制刷新，都优先本地数据，保证速度）
            if prefer_unviewed:
                unviewed_music = get_unviewed_music()
                # 过滤排除列表
                if excluded_set:
                    unviewed_music = [m for m in unviewed_music if m.get('bvid') not in excluded_set]
                
                # 强制刷新时，仍然使用本地未浏览视频，但打乱顺序以实现"刷新"效果
                if force_refresh and unviewed_music:
                    import random
                    random.shuffle(unviewed_music)
                
                if len(unviewed_music) >= limit:
                    # 未浏览视频足够，使用智能混合策略
                    print(f"从本地未浏览视频获取 {limit} 条推荐（智能混合点击/未点击）")
                    recommendations = self._smart_mix_recommendations(unviewed_music, limit)
                    return self._convert_to_ui_format(recommendations)
                elif unviewed_music:
                    # 未浏览视频不足，先获取这些
                    print(f"本地未浏览视频不足({len(unviewed_music)}/{limit})，补充获取...")
                    recommendations = unviewed_music
            
            # 如果还没有足够数据，调用推荐引擎
            if len(recommendations) < limit:
                engine_results = self.engine.get_hot_recommendations(
                    limit=limit - len(recommendations), 
                    excluded_bvids=excluded_bvids, 
                    force_refresh=force_refresh
                )
                recommendations.extend(engine_results)
            
            # 如果仍然没有获取到足够数据，尝试强制刷新
            if len(recommendations) < limit // 2 and not force_refresh:
                print("推荐数据不足，尝试强制刷新获取新数据...")
                engine_results = self.engine.get_hot_recommendations(
                    limit=limit, 
                    excluded_bvids=excluded_bvids, 
                    force_refresh=True
                )
                recommendations = engine_results
            
            # 最终过滤排除列表（确保万无一失）
            if excluded_set:
                recommendations = [item for item in recommendations if item.get('bvid') not in excluded_set]
            
            # 智能混合：确保未点击的视频有一定出场率
            if len(recommendations) > limit:
                recommendations = self._smart_mix_recommendations(recommendations, limit)
            
            # 转换为UI需要的格式
            result = self._convert_to_ui_format(recommendations[:limit])
            
            return result
        except Exception as e:
            import traceback
            print(f"获取推荐失败: {e}")
            print(f"错误堆栈: {traceback.format_exc()}")
            # 返回空列表，不返回硬编码数据
            return []

    def _smart_mix_recommendations(self, music_list, limit):
        """
        智能混合推荐列表，确保未点击的视频有一定出场率
        :param music_list: 音乐列表
        :param limit: 返回数量
        :return: 混合后的列表
        """
        try:
            from utils.data_manager import load_clicked_bvids, is_clicked
            import random
            
            # 如果可用视频不足，直接返回所有
            if len(music_list) <= limit:
                random.shuffle(music_list)
                return music_list
            
            clicked_bvids = set(load_clicked_bvids())
            
            # 分离已点击和未点击的视频
            clicked = []
            unclicked = []
            
            for item in music_list:
                bvid = item.get('bvid', '')
                if bvid in clicked_bvids:
                    clicked.append(item)
                else:
                    unclicked.append(item)
            
            unclicked_count = len(unclicked)
            clicked_count = len(clicked)
            
            # 目标未点击比例（30%-70%之间）
            target_unclicked_ratio = 0.4  # 默认40%
            
            # 计算实际要选取的未点击数量
            ideal_unclicked = int(limit * target_unclicked_ratio)
            # 确保在可用范围内
            actual_unclicked = max(0, min(ideal_unclicked, unclicked_count, limit))

            # 剩余数量用已点击填充
            actual_clicked = min(limit - actual_unclicked, clicked_count)
            
            # 如果已点击不足，用未点击补充
            if actual_clicked < limit - actual_unclicked:
                additional_unclicked = min(limit - actual_unclicked - actual_clicked, unclicked_count - actual_unclicked)
                actual_unclicked += additional_unclicked
            
            # 随机打乱
            random.shuffle(clicked)
            random.shuffle(unclicked)
            
            # 选取指定数量
            selected_unclicked = unclicked[:actual_unclicked]
            selected_clicked = clicked[:actual_clicked]
            
            # 合并并再次随机打乱顺序
            mixed = selected_unclicked + selected_clicked
            random.shuffle(mixed)
            
            print(f"智能混合: {len(selected_unclicked)} 未点击 + {len(selected_clicked)} 已点击 = {len(mixed)} 总计 (请求{limit}个)")
            return mixed
        except Exception as e:
            import traceback
            print(f"_smart_mix_recommendations 错误: {e}")
            print(f"错误堆栈: {traceback.format_exc()}")
            import random
            random.shuffle(music_list)
            return music_list[:limit]

    def _convert_to_ui_format(self, recommendations):
        """
        转换推荐结果为UI需要的格式
        :param recommendations: 推荐结果列表
        :return: 格式化后的列表
        """
        formatted = []
        for rec in recommendations:
            cover = rec.get('cover', '') or rec.get('cover_url', '')
            up_name = rec.get('up_name') or rec.get('up主') or '未知UP主'
            formatted.append({
                'bvid': rec.get('bvid', ''),
                'title': rec.get('title', ''),
                'up_name': up_name,
                'play_count': rec.get('play_count', 0),
                'cover': cover,
                'pub_time': rec.get('pub_time', 0),
                'video_type': rec.get('video_type', '猜你喜欢'),
                'score': rec.get('score', 0)
            })
        return formatted

    def _smart_mix_recommendations(self, music_list, limit):
        """
        智能混合推荐列表，确保未点击的视频有一定出场率
        :param music_list: 音乐列表
        :param limit: 返回数量
        :return: 混合后的列表
        """
        try:
            from utils.data_manager import load_clicked_bvids, is_clicked
            import random
            
            # 如果可用视频不足，直接返回所有
            if len(music_list) <= limit:
                random.shuffle(music_list)
                return music_list
            
            clicked_bvids = set(load_clicked_bvids())
            
            # 分离已点击和未点击的视频
            clicked = []
            unclicked = []
            
            for item in music_list:
                bvid = item.get('bvid', '')
                if bvid in clicked_bvids:
                    clicked.append(item)
                else:
                    unclicked.append(item)
            
            unclicked_count = len(unclicked)
            clicked_count = len(clicked)
            
            # 目标未点击比例（30%-70%之间）
            target_unclicked_ratio = 0.4  # 默认40%
            
            # 计算实际要选取的未点击数量
            ideal_unclicked = int(limit * target_unclicked_ratio)
            # 确保在可用范围内
            actual_unclicked = max(0, min(ideal_unclicked, unclicked_count, limit))

            # 剩余数量用已点击填充
            actual_clicked = min(limit - actual_unclicked, clicked_count)
            
            # 如果已点击不足，用未点击补充
            if actual_clicked < limit - actual_unclicked:
                additional_unclicked = min(limit - actual_unclicked - actual_clicked, unclicked_count - actual_unclicked)
                actual_unclicked += additional_unclicked
            
            # 随机打乱
            random.shuffle(clicked)
            random.shuffle(unclicked)
            
            # 选取指定数量
            selected_unclicked = unclicked[:actual_unclicked]
            selected_clicked = clicked[:actual_clicked]
            
            # 合并并再次随机打乱顺序
            mixed = selected_unclicked + selected_clicked
            random.shuffle(mixed)
            
            print(f"智能混合: {len(selected_unclicked)} 未点击 + {len(selected_clicked)} 已点击 = {len(mixed)} 总计 (请求{limit}个)")
            return mixed
        except Exception as e:
            import traceback
            print(f"_smart_mix_recommendations 错误: {e}")
            print(f"错误堆栈: {traceback.format_exc()}")
            import random
            random.shuffle(music_list)
            return music_list[:limit]
    
    def _sort_by_preference(self, music_list):
        """根据用户偏好排序音乐列表"""
        import time
        from datetime import datetime
        
        settings = self.engine.get_settings()
        sort_preference = settings.get('sort_preference', 'balanced')
        
        if sort_preference == 'random':
            import random
            random.shuffle(music_list)
            return music_list
        
        def get_score(item):
            play_count = item.get('play_count', 0)
            pub_time = item.get('pub_time', item.get('pubdate', 0))
            
            if sort_preference == 'hot':
                # 按热度排序（播放量）
                return play_count
            elif sort_preference == 'fresh':
                # 按新鲜度排序（发布时间，越新越高）
                return pub_time
            else:  # balanced
                # 平衡模式：综合热度和新鲜度
                hot_weight = settings.get('hot_weight', 0.5)
                fresh_weight = settings.get('fresh_weight', 0.5)
                
                # 归一化播放量（假设最大播放量为1亿）
                normalized_hot = min(play_count / 100000000, 1.0)
                
                # 归一化时间（越新越高，假设3年内的视频）
                current_time = time.time()
                time_diff = current_time - pub_time if pub_time else 94608000  # 默认3年前
                normalized_fresh = max(0, 1 - (time_diff / 94608000))  # 3年内的线性衰减
                
                return normalized_hot * hot_weight + normalized_fresh * fresh_weight
        
        # 根据偏好排序
        reverse = sort_preference != 'fresh'  # fresh模式是时间越新越靠前（数值大），其他是分数越高越好
        return sorted(music_list, key=get_score, reverse=reverse)
    
    def _convert_to_ui_format(self, music_list):
        """将音乐数据转换为UI格式"""
        # 先根据偏好排序
        music_list = self._sort_by_preference(music_list)
        
        result = []
        for item in music_list:
            # 处理不同格式的字段名
            bvid = item.get('bvid', item.get('BV号', '未知'))
            title = item.get('title', item.get('标题', '未知标题'))
            up = item.get('up主', item.get('up主', item.get('UP主', '未知UP主')))
            cover = item.get('cover', item.get('封面', ''))
            pubdate = item.get('pubdate', item.get('发布时间', item.get('pub_time', '未知')))
            play_count = item.get('play_count', item.get('播放量', 0))
            
            # 格式化发布时间
            if isinstance(pubdate, int):
                try:
                    from datetime import datetime
                    pubdate = datetime.fromtimestamp(pubdate).strftime('%Y-%m-%d %H:%M')
                except:
                    pubdate = '未知'
            
            result.append({
                'bvid': bvid,
                'title': title,
                'up': up,
                'up主': up,  # 保持一致性
                'cover': cover,
                'pubdate': pubdate,
                'play_count': play_count
            })
        
        return result
    
    def mark_as_viewed(self, bvid):
        """标记视频为已浏览"""
        return mark_as_viewed(bvid)
    
    def check_and_fetch_if_needed(self, background=True):
        """检查并后台抓取数据（如果需要）"""
        return self.engine.check_and_fetch_if_needed(background=background)

    def check_and_fix_empty_playcount(self, auto_fix=True):
        """
        检查并修复播放量为0/空的视频
        :param auto_fix: 是否自动从数据库移除并重新抓取
        :return: (异常视频数量, 已移除数量)
        """
        empty_videos = get_videos_with_empty_playcount()
        empty_count = len(empty_videos)

        if empty_count > 0:
            print(f"检测到 {empty_count} 个播放量为空的视频")

            if auto_fix and empty_count > 0:
                # 从数据库中移除这些视频，以便重新抓取
                removed_count = mark_videos_for_refetch(empty_videos)
                print(f"已移除 {removed_count} 个异常视频，将在后台重新抓取")
                return empty_count, removed_count

        return empty_count, 0

    def get_db_stats(self):
        """获取数据库统计信息"""
        return self.engine.get_db_stats()

    def update_db_config(self, **kwargs):
        """更新数据库配置"""
        return self.engine.update_db_config(**kwargs)

    def clear_cache(self):
        """清除所有缓存"""
        self.engine.clear_cache()

    def invalidate_db_cache(self):
        """使数据库缓存失效"""
        self.engine.invalidate_db_cache()

    def _save_to_database(self, video_data: Dict[str, Any]):
        """
        保存视频数据到JSON文件
        :param video_data: 视频数据
        """
        try:
            # 转换为JSON文件存储格式
            music_data = {
                'bvid': video_data['bvid'],
                'title': video_data['title'],
                'up主': video_data['up主'],
                'play_count': video_data['play_count'],
                'cover': video_data['cover'],
                'pub_time': video_data['pub_time'],
                'play_url': f"https://www.bilibili.com/video/{video_data['bvid']}",
                'up主UID': video_data.get('up主UID', '')  # 添加UP主UID
            }
            
            # 保存到JSON文件
            result = add_music(music_data)
            if result:
                print(f"保存视频到JSON文件: {video_data['title']}")
            else:
                print(f"视频已存在: {video_data['title']}")
            
        except Exception as e:
            print(f"保存到JSON文件失败: {e}")

# 向后兼容：添加TraditionalRecommendEngine作为RecommendEngine的别名
TraditionalRecommendEngine = RecommendEngine

if __name__ == "__main__":
    # 测试推荐服务
    service = RecommendService()
    recommendations = service.get_recommendations(limit=10, force_refresh=False)
    print(f"获取到 {len(recommendations)} 条推荐")
    for i, item in enumerate(recommendations, 1):
        print(f"{i}. {item.get('title', '未知')} - {item.get('up主', '未知')}")
