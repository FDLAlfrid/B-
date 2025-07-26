#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站VOCALOID数据可视化修复版
功能：VOCALOID区排行榜展示与数据可视化，支持曲目选择查看详细数据
使用方法：
1. 安装依赖：pip install flask requests matplotlib
2. 运行程序：python app.py
3. 访问页面：http://127.0.0.1:5000
"""

import os
import sys
import json
import time
import random
import sqlite3
import requests
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request

# 配置项
DB_NAME = 'bilibili_vocaloid_final.db'
VOCALOID_RID = 30  # VOCALOID·UTAU分区ID，可尝试改为28（音乐区）进行测试
DEFAULT_LIMIT = 20
MAX_LIMIT = 50
PORT = 5000

# API配置（增强版，增加详细日志和多路径支持）
API_CONFIG = {
    "primary_ranking_url": "https://api.bilibili.com/x/web-interface/ranking/region",
    "primary_ranking_params": {'rid': VOCALOID_RID, 'day': 7, 'original': 0},
    "backup_ranking_url": "https://api.bilibili.com/x/web-interface/popular",
    "backup_ranking_params": {'ps': 50},
    "video_detail_url": "https://api.bilibili.com/x/web-interface/view",
    "manual_bvids": ["BV1Xx411c7mZ", "BV1ax411c7mZ", "BV1wx411c7mZ"]  # 手动添加的测试BV号
}

# 扩展VOCALOID关键词列表，提高匹配率
VOCALOID_KEYWORDS = [
    "VOCALOID", "UTAU", "洛天依", "乐正绫", "言和", "星尘", "初音", 
    "初音未来", "镜音", "镜音铃", "镜音连", "巡音", "IA", "GUMI", 
    "心华", "乐正龙牙", "徵羽摩柯", "墨清弦", "SeeU", "Oliver", "Vocaloid"
]

# 设置中文字体
plt.rcParams["font.family"] = ["SimHei", "WenQuanYi Micro Hei", "Heiti TC"]
plt.rcParams['axes.unicode_minus'] = False

# 初始化Flask应用
app = Flask(__name__)

# ------------------------------
# 数据库操作类
# ------------------------------
class Database:
    def __init__(self, db_name=DB_NAME):
        self.db_name = db_name
        self.conn = None
        self.cursor = None
        self.init_db()
        
    def connect(self):
        if not self.conn:
            try:
                self.conn = sqlite3.connect(self.db_name, check_same_thread=False)
                self.conn.row_factory = sqlite3.Row
                self.cursor = self.conn.cursor()
                return True
            except Exception as e:
                print(f"数据库连接错误: {str(e)}")
                return False
            
    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
            self.cursor = None
                
    def init_db(self):
        if not self.connect():
            return
            
        try:
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bvid TEXT UNIQUE NOT NULL,
                aid TEXT,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                mid TEXT,
                view INTEGER DEFAULT 0,
                danmaku INTEGER DEFAULT 0,
                favorite INTEGER DEFAULT 0,
                coin INTEGER DEFAULT 0,
                share INTEGER DEFAULT 0,
                like INTEGER DEFAULT 0,
                typename TEXT NOT NULL,
                pubdate INTEGER,
                duration INTEGER,
                pic_url TEXT,
                crawl_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            self.conn.commit()
        except Exception as e:
            print(f"数据库初始化错误: {str(e)}")
        finally:
            self.close()
    
    def insert_videos(self, videos):
        if not self.connect() or not videos:
            return False
            
        try:
            self.cursor.executemany('''
            INSERT OR REPLACE INTO videos 
            (bvid, aid, title, author, mid, view, danmaku, favorite, coin, 
             share, like, typename, pubdate, duration, pic_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', [(
                v['bvid'], v.get('aid'), v['title'], v['author'], v.get('mid'),
                v['view'], v['danmaku'], v['favorite'], v['coin'], v.get('share', 0),
                v.get('like', 0), v['typename'], v.get('pubdate'), v.get('duration'),
                v.get('pic_url')
            ) for v in videos])
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"插入数据错误: {str(e)}")
            return False
        finally:
            self.close()
            
    def get_videos(self, sort_by='view', limit=DEFAULT_LIMIT):
        if not self.connect():
            return []
            
        try:
            valid_fields = ['view', 'danmaku', 'favorite', 'coin', 'share', 'like']
            sort_by = sort_by if sort_by in valid_fields else 'view'
            
            query = f'''
            SELECT * FROM videos 
            ORDER BY {sort_by} DESC LIMIT {min(limit, MAX_LIMIT)}
            '''
            self.cursor.execute(query)
            return [dict(row) for row in self.cursor.fetchall()]
        except Exception as e:
            print(f"查询数据错误: {str(e)}")
            return []
        finally:
            self.close()

# ------------------------------
# 数据采集类（增强版，增加详细日志和多路径支持）
# ------------------------------
class DataCollector:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/114.0.0.0 Safari/537.36",
            "Referer": "https://www.bilibili.com/",
            "Accept": "application/json, text/plain, */*"
        }
        
    def _log_api_response(self, data, api_name):
        """记录API响应的关键信息，帮助调试"""
        print(f"\n===== {api_name} API响应分析 =====")
        print(f"数据类型: {type(data)}")
        
        if isinstance(data, dict):
            print(f"键列表: {list(data.keys())}")
            
            # 检查可能包含视频列表的字段
            for key in ['list', 'data', 'result', 'items', 'videos']:
                if key in data:
                    print(f"找到 {key} 字段，类型: {type(data[key])}")
                    if isinstance(data[key], list):
                        print(f"{key} 包含 {len(data[key])} 个元素")
                        if len(data[key]) > 0 and isinstance(data[key][0], dict):
                            print(f"首个元素键列表: {list(data[key][0].keys())[:10]}...")
            
            # 保存完整响应到文件，方便调试
            with open(f"{api_name}_response.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"完整响应已保存到 {api_name}_response.json")
        
        print("=================================\n")
    
    def _fetch_from_api(self, url, params, api_name="unknown"):
        """通用API请求方法，增加详细日志"""
        try:
            print(f"调用API: {url}, 参数: {params}")
            response = requests.get(
                url,
                params=params,
                headers=self.headers,
                timeout=15
            )
            print(f"API响应状态码: {response.status_code}")
            
            # 打印响应头关键信息
            print(f"API响应头关键信息:")
            for key in ['Content-Type', 'Bili-Status-Code', 'X-Bili-Trace-Id']:
                if key in response.headers:
                    print(f"  {key}: {response.headers[key]}")
            
            response.raise_for_status()
            data = response.json()
            print(f"API响应状态: code={data.get('code')}, message={data.get('message')}")
            
            # 详细记录API响应内容
            self._log_api_response(data, api_name)
            
            if data.get('code') == 0:
                return data
            else:
                print(f"API错误: {data.get('message', '未知错误')}")
                return None
        except requests.exceptions.HTTPError as e:
            print(f"HTTP错误: {str(e)}")
            print(f"响应内容: {response.text[:500]}...")  # 打印部分响应内容
            return None
        except Exception as e:
            print(f"API调用失败: {str(e)}")
            return None
    
    def _get_video_detail(self, bvid):
        """获取单个视频的详细数据"""
        print(f"获取视频详情: {bvid}")
        data = self._fetch_from_api(
            API_CONFIG['video_detail_url'],
            {'bvid': bvid},
            api_name=f"video_detail_{bvid}"
        )
        
        if not data or not isinstance(data, dict):
            print(f"视频详情API返回无效数据: {type(data)}")
            return None
            
        # 尝试多种路径提取数据，适应API变化
        stat = data.get('data', {}).get('stat', {}) or data.get('stat', {})
        owner = data.get('data', {}).get('owner', {}) or data.get('owner', {})
        
        return {
            'bvid': bvid,
            'aid': data.get('data', {}).get('aid') or data.get('aid'),
            'title': data.get('data', {}).get('title') or data.get('title') or '未知标题',
            'author': owner.get('name', '未知作者'),
            'mid': owner.get('mid'),
            'view': stat.get('view', 0),
            'danmaku': stat.get('danmaku', 0),
            'favorite': stat.get('favorite', 0),
            'coin': stat.get('coin', 0),
            'share': stat.get('share', 0),
            'like': stat.get('like', 0),
            'typename': data.get('data', {}).get('tname') or data.get('tname') or 'VOCALOID·UTAU',
            'pubdate': data.get('data', {}).get('pubdate') or data.get('pubdate'),
            'duration': data.get('data', {}).get('duration') or data.get('duration'),
            'pic_url': data.get('data', {}).get('pic') or data.get('pic')
        }
    
    def _is_vocaloid_video(self, title, typename):
        """增强的VOCALOID视频判断逻辑"""
        text = (title + " " + typename).upper()
        return any(keyword.upper() in text for keyword in VOCALOID_KEYWORDS)
    
    def fetch_videos(self, limit=50):
        """获取视频列表，增加多路径提取和手动测试BV号"""
        videos = []
        
        # 1. 尝试主API - VOCALOID区排行榜
        print("===== 尝试主API - VOCALOID区排行榜 =====")
        ranking_data = self._fetch_from_api(
            API_CONFIG['primary_ranking_url'],
            API_CONFIG['primary_ranking_params'],
            api_name="primary_ranking"
        )
        
        # 尝试多种可能的数据路径提取视频列表
        video_list = []
        if isinstance(ranking_data, dict):
            # 尝试常见的数据路径
            for path in ['list', 'data.list', 'data', 'result', 'data.result']:
                current = ranking_data
                valid = True
                for key in path.split('.'):
                    if isinstance(current, dict) and key in current:
                        current = current[key]
                    else:
                        valid = False
                        break
                if valid and isinstance(current, list):
                    video_list = current
                    print(f"从路径 {path} 提取到 {len(video_list)} 个视频")
                    break
        
        # 处理提取到的视频列表
        if isinstance(video_list, list) and len(video_list) > 0:
            print(f"从主API获取到 {len(video_list)} 个视频")
            bvids = []
            
            # 提取BVid，尝试多种可能的字段名
            for item in video_list[:limit]:
                if isinstance(item, dict):
                    # 尝试不同的BVid字段名
                    for bvid_key in ['bvid', 'aid', 'avid', 'video_id']:
                        if bvid_key in item and item[bvid_key]:
                            bvids.append(item[bvid_key])
                            break
            
            print(f"从主API提取到 {len(bvids)} 个视频ID")
            
            # 获取详细数据
            for bvid in bvids[:limit]:
                video_detail = self._get_video_detail(bvid)
                if video_detail:
                    videos.append(video_detail)
                    print(f"成功获取 {video_detail['title']} 的详细数据")
                else:
                    print(f"获取 {bvid} 详细数据失败")
                time.sleep(random.uniform(1, 2))
        
        # 2. 如果主API失败或数据不足，尝试备用API
        if len(videos) < 5:
            print(f"===== 主API获取数据不足({len(videos)}条)，尝试备用API =====")
            backup_data = self._fetch_from_api(
                API_CONFIG['backup_ranking_url'],
                API_CONFIG['backup_ranking_params'],
                api_name="backup_ranking"
            )
            
            # 尝试多种可能的数据路径提取视频列表
            backup_video_list = []
            if isinstance(backup_data, dict):
                for path in ['list', 'data.list', 'data', 'result', 'data.result']:
                    current = backup_data
                    valid = True
                    for key in path.split('.'):
                        if isinstance(current, dict) and key in current:
                            current = current[key]
                        else:
                            valid = False
                            break
                    if valid and isinstance(current, list):
                        backup_video_list = current
                        print(f"从备用API路径 {path} 提取到 {len(backup_video_list)} 个视频")
                        break
            
            # 筛选VOCALOID相关视频
            if isinstance(backup_video_list, list) and len(backup_video_list) > 0:
                vocaloid_videos = []
                for item in backup_video_list:
                    if isinstance(item, dict):
                        title = item.get('title', '')
                        typename = item.get('typename', '') or item.get('tname', '')
                        
                        # 宽松的匹配逻辑
                        if self._is_vocaloid_video(title, typename):
                            vocaloid_videos.append(item)
                            print(f"匹配到VOCALOID视频: {title}")
                            if len(vocaloid_videos) >= limit:
                                break
                
                print(f"从备用API筛选出 {len(vocaloid_videos)} 个VOCALOID相关视频")
                bvids = []
                for item in vocaloid_videos:
                    for bvid_key in ['bvid', 'aid', 'avid', 'video_id']:
                        if bvid_key in item and item[bvid_key]:
                            bvids.append(item[bvid_key])
                            break
                
                # 获取详细数据
                for bvid in bvids[:limit - len(videos)]:
                    video_detail = self._get_video_detail(bvid)
                    if video_detail:
                        videos.append(video_detail)
                        print(f"成功获取 {video_detail['title']} 的详细数据")
                    else:
                        print(f"获取 {bvid} 详细数据失败")
                    time.sleep(random.uniform(1, 2))
        
        # 3. 如果所有API都失败，使用手动添加的测试BV号
        if len(videos) == 0:
            print(f"===== 所有API获取数据失败，使用手动测试BV号 =====")
            for bvid in API_CONFIG['manual_bvids']:
                video_detail = self._get_video_detail(bvid)
                if video_detail:
                    videos.append(video_detail)
                    print(f"成功获取手动添加的 {video_detail['title']} 数据")
                else:
                    print(f"获取手动添加的 {bvid} 数据失败")
                time.sleep(random.uniform(1, 2))
        
        print(f"数据获取完成，共获取 {len(videos)} 条有效视频数据")
        return videos[:limit]

# ------------------------------
# Flask路由
# ------------------------------
@app.route('/')
def index():
    html_template = '''<!DOCTYPE html>
<html>
<head>
    <title>VOCALOID数据可视化</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        .controls { margin: 20px 0; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { padding: 10px; border: 1px solid #ddd; text-align: left; }
        th { background-color: #f2f2f2; }
        tr:hover { background-color: #f5f5f5; cursor: pointer; }
        .chart-container { display: flex; flex-wrap: wrap; gap: 20px; margin: 20px 0; }
        .chart-card { flex: 1; min-width: 300px; }
        .selected { background-color: #e3f2fd; }
        #detailView { margin-top: 30px; padding: 20px; border: 1px solid #eee; border-radius: 5px; }
        .error-message { color: #dc3545; padding: 10px; background-color: #f8d7da; border: 1px solid #f5c6cb; border-radius: 4px; margin: 10px 0; }
        .debug-info { color: #6c757d; font-size: 0.9em; margin-top: 10px; padding: 10px; background-color: #f8f9fa; border-radius: 4px; }
    </style>
</head>
<body>
    <h1>B站VOCALOID区排行榜数据可视化</h1>
    
    <div class="controls">
        <select id="sort-by">
            <option value="view">按播放量排序</option>
            <option value="danmaku">按弹幕数排序</option>
            <option value="favorite">按收藏数排序</option>
            <option value="coin">按投币数排序</option>
        </select>
        
        <select id="limit">
            <option value="10">显示10条</option>
            <option value="20" selected>显示20条</option>
            <option value="30">显示30条</option>
            <option value="50">显示50条</option>
        </select>
        
        <button onclick="refreshData()">刷新数据</button>
        <span id="status"></span>
    </div>
    
    <div id="errorContainer" style="display: none;">
        <div class="error-message">
            <strong>数据获取失败:</strong> <span id="errorMessage"></span>
        </div>
        <div class="debug-info">
            <strong>调试信息:</strong> API返回数据结构可能已更改。详细日志已保存到本地文件，
            请查看 <code>primary_ranking_response.json</code> 和 <code>backup_ranking_response.json</code> 了解更多信息。
            <br>系统已尝试使用内置测试数据。
        </div>
    </div>
    
    <div id="detailView">
        <h2>选择视频查看详细数据</h2>
        <p>点击表格中的视频行查看详细数据...</p>
    </div>
    
    <div class="chart-container">
        <div class="chart-card">
            <canvas id="rankChart"></canvas>
        </div>
        <div class="chart-card">
            <canvas id="dataComparisonChart"></canvas>
        </div>
    </div>
    
    <table>
        <thead>
            <tr>
                <th>排名</th>
                <th>标题</th>
                <th>UP主</th>
                <th>播放量</th>
                <th>弹幕数</th>
                <th>收藏数</th>
                <th>投币数</th>
            </tr>
        </thead>
        <tbody id="video-table">
            <tr><td colspan="7">加载中...</td></tr>
        </tbody>
    </table>

    <script>
        // JavaScript代码保持不变，与之前版本相同
        let currentVideos = [];
        let rankChart = null;
        let comparisonChart = null;
        let selectedVideo = null;
        
        document.addEventListener('DOMContentLoaded', loadData);
        
        function loadData() {
            const sortBy = document.getElementById('sort-by').value;
            const limit = document.getElementById('limit').value;
            document.getElementById('status').textContent = '加载中...';
            document.getElementById('errorContainer').style.display = 'none';
            
            fetch(`/api/videos?sort_by=${sortBy}&limit=${limit}`)
                .then(r => r.json())
                .then(data => {
                    currentVideos = data;
                    updateTable(data);
                    
                    if (data.length === 0) {
                        showError("未能获取到视频数据，系统已尝试使用内置测试数据");
                    } else {
                        updateRankChart(data);
                    }
                    
                    document.getElementById('status').textContent = `加载完成 (${data.length}条数据)`;
                })
                .catch(err => {
                    console.error('加载数据失败:', err);
                    document.getElementById('status').textContent = '加载失败';
                    showError("加载数据时发生错误: " + err.message);
                });
        }
        
        function showError(message) {
            document.getElementById('errorMessage').textContent = message;
            document.getElementById('errorContainer').style.display = 'block';
        }
        
        function updateTable(videos) {
            const tableBody = document.getElementById('video-table');
            tableBody.innerHTML = '';
            
            if (videos.length === 0) {
                tableBody.innerHTML = '<tr><td colspan="7">没有找到视频数据，请尝试刷新或检查API连接</td></tr>';
                return;
            }
            
            videos.forEach((video, index) => {
                const row = document.createElement('tr');
                row.onclick = () => selectVideo(video, row);
                
                const formatNum = num => num >= 10000 ? (num/10000).toFixed(1) + '万' : num;
                
                row.innerHTML = `
                    <td>${index + 1}</td>
                    <td>${video.title}</td>
                    <td>${video.author}</td>
                    <td>${formatNum(video.view)}</td>
                    <td>${formatNum(video.danmaku)}</td>
                    <td>${formatNum(video.favorite)}</td>
                    <td>${formatNum(video.coin)}</td>
                `;
                tableBody.appendChild(row);
            });
        }
        
        function selectVideo(video, rowElement) {
            document.querySelectorAll('#video-table tr').forEach(row => 
                row.classList.remove('selected')
            );
            
            rowElement.classList.add('selected');
            selectedVideo = video;
            
            document.getElementById('detailView').innerHTML = `
                <h2>${video.title}</h2>
                <p><strong>UP主:</strong> ${video.author}</p>
                <p><strong>发布时间:</strong> ${new Date(video.pubdate * 1000).toLocaleString()}</p>
                <p><strong>时长:</strong> ${formatDuration(video.duration)}</p>
                <p><strong>播放量:</strong> ${formatNum(video.view)}</p>
                <p><strong>弹幕数:</strong> ${formatNum(video.danmaku)}</p>
                <p><strong>收藏数:</strong> ${formatNum(video.favorite)}</p>
                <p><strong>投币数:</strong> ${formatNum(video.coin)}</p>
            `;
            
            updateComparisonChart(video);
        }
        
        function formatDuration(seconds) {
            if (!seconds) return '未知';
            const mins = Math.floor(seconds / 60);
            const secs = seconds % 60;
            return `${mins}:${secs < 10 ? '0' + secs : secs}`;
        }
        
        function formatNum(num) {
            return num >= 10000 ? (num/10000).toFixed(1) + '万' : num;
        }
        
        function updateRankChart(videos) {
            const ctx = document.getElementById('rankChart').getContext('2d');
            
            if (rankChart) rankChart.destroy();
            
            const labels = videos.slice(0, 10).map(video => video.title.substring(0, 15) + '...');
            const data = videos.slice(0, 10).map(video => video.view);
            
            rankChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: '播放量',
                        data: data,
                        backgroundColor: 'rgba(54, 162, 235, 0.7)',
                        borderColor: 'rgba(54, 162, 235, 1)',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: { display: true, text: '播放量' }
                        }
                    },
                    plugins: {
                        title: { display: true, text: 'TOP 10 视频播放量', font: { size: 16 } }
                    }
                }
            });
        }
        
        function updateComparisonChart(video) {
            const ctx = document.getElementById('dataComparisonChart').getContext('2d');
            
            if (comparisonChart) comparisonChart.destroy();
            
            comparisonChart = new Chart(ctx, {
                type: 'radar',
                data: {
                    labels: ['播放量', '弹幕数', '收藏数', '投币数', '点赞数'],
                    datasets: [{
                        label: '视频数据',
                        data: [
                            normalizeValue(video.view, 'view'),
                            normalizeValue(video.danmaku, 'danmaku'),
                            normalizeValue(video.favorite, 'favorite'),
                            normalizeValue(video.coin, 'coin'),
                            normalizeValue(video.like || 0, 'like')
                        ],
                        backgroundColor: 'rgba(75, 192, 192, 0.2)',
                        borderColor: 'rgba(75, 192, 192, 1)',
                        pointBackgroundColor: 'rgba(75, 192, 192, 1)'
                    }]
                },
                options: {
                    responsive: true,
                    scales: { r: { suggestedMin: 0, suggestedMax: 100 } },
                    plugins: { title: { display: true, text: '视频各项数据对比', font: { size: 16 } } }
                }
            });
        }
        
        function normalizeValue(value, type) {
            if (!currentVideos || currentVideos.length === 0 || !value) return 0;
            
            let maxValue = 0;
            switch(type) {
                case 'view': maxValue = Math.max(...currentVideos.map(v => v.view)); break;
                case 'danmaku': maxValue = Math.max(...currentVideos.map(v => v.danmaku)); break;
                case 'favorite': maxValue = Math.max(...currentVideos.map(v => v.favorite)); break;
                case 'coin': maxValue = Math.max(...currentVideos.map(v => v.coin)); break;
                case 'like': maxValue = Math.max(...currentVideos.map(v => v.like || 0)); break;
            }
            
            return maxValue > 0 ? Math.min(100, (value / maxValue) * 100) : 0;
        }
        
        function refreshData() {
            document.getElementById('video-table').innerHTML = '<tr><td colspan="7">加载中...</td></tr>';
            
            fetch('/refresh')
                .then(r => r.json())
                .then(data => {
                    if (data.status === 'success') {
                        showError("");
                        loadData();
                    } else {
                        showError(data.message || "刷新数据失败");
                    }
                })
                .catch(err => {
                    console.error('刷新数据失败:', err);
                    showError("刷新数据时发生错误: " + err.message);
                });
        }
    </script>
</body>
</html>'''
    return render_template_string(html_template)

# ------------------------------
# API路由
# ------------------------------
@app.route('/api/videos')
def get_videos():
    sort_by = request.args.get('sort_by', 'view')
    limit = int(request.args.get('limit', DEFAULT_LIMIT))
    
    db = Database()
    videos = db.get_videos(sort_by, limit)
    return jsonify(videos)

# ------------------------------
# 数据刷新路由
# ------------------------------
@app.route('/refresh')
def refresh_data():
    collector = DataCollector()
    db = Database()
    
    try:
        videos = collector.fetch_videos(limit=50)
        if videos and db.insert_videos(videos):
            return jsonify({
                'status': 'success',
                'message': f'成功更新 {len(videos)} 条视频数据',
                'count': len(videos)
            })
        else:
            return jsonify({
                'status': 'error',
                'message': '未能获取或更新视频数据'
            }), 500
    except Exception as e:
        print(f"数据刷新异常: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'数据更新失败: {str(e)}'
        }), 500

# ------------------------------
# 启动应用
# ------------------------------
if __name__ == '__main__':
    # 初始化数据库并获取数据
    db = Database()
    collector = DataCollector()
    
    # 检查是否有数据，如果没有则获取
    if not db.get_videos(limit=1):
        print("首次运行，获取初始数据...")
        videos = collector.fetch_videos(limit=50)
        if videos:
            db.insert_videos(videos)
            print(f"成功初始化 {len(videos)} 条视频数据")
        else:
            print("警告: 未能获取初始数据，应用将在无数据状态下启动")
            # 尝试使用手动添加的测试数据
            if API_CONFIG['manual_bvids']:
                print("尝试使用手动添加的测试数据...")
                test_videos = []
                for bvid in API_CONFIG['manual_bvids']:
                    video_detail = collector._get_video_detail(bvid)
                    if video_detail:
                        test_videos.append(video_detail)
                if test_videos:
                    db.insert_videos(test_videos)
                    print(f"成功添加 {len(test_videos)} 条测试数据")
    
    # 启动Flask应用
    app.run(debug=True, port=PORT, use_reloader=False)