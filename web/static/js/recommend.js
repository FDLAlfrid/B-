// 推荐页面 JavaScript
let currentUser = null;  // 当前用户信息

document.addEventListener('DOMContentLoaded', function() {
    // 加载推荐内容
    loadRecommendations();

    // 刷新按钮 - 触发真正的刷新，获取新的推荐数据
    const refreshBtn = document.getElementById('refresh-btn');
    refreshBtn.addEventListener('click', function() {
        loadRecommendations(true);  // true = 强制刷新，获取新数据
    });

    // 搜索功能
    const searchBtn = document.getElementById('search-btn');
    const searchInput = document.getElementById('search-input');

    searchBtn.addEventListener('click', function() {
        const keyword = searchInput.value.trim();
        if (keyword) {
            searchVideos(keyword);
        } else {
            loadRecommendations();
        }
    });

    searchInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            searchBtn.click();
        }
    });

    // 视频卡片点击事件
    document.addEventListener('click', function(e) {
        const videoCard = e.target.closest('.video-card');
        if (videoCard) {
            const bvid = videoCard.dataset.bvid;
            showVideoDetail(bvid);
        }
    });

    // 弹窗关闭
    const modal = document.getElementById('video-modal');
    const closeBtn = document.querySelector('.close');

    closeBtn.addEventListener('click', function() {
        stopVideoPlayback();
        modal.style.display = 'none';
    });

    window.addEventListener('click', function(e) {
        if (e.target === modal) {
            stopVideoPlayback();
            modal.style.display = 'none';
        }
    });

    // 退出登录按钮
    const logoutBtn = document.getElementById('logout-btn');
    logoutBtn.addEventListener('click', function() {
        logout();
    });

    // 检查登录状态
    checkLoginStatus();
});

function checkLoginStatus() {
    // 检查cookie中是否有用户token
    const token = getCookie('user_token');
    if (token) {
        // 验证token有效性
        fetch('/api/user/status', {
            headers: {
                'Authorization': 'Bearer ' + token
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success && data.logged_in) {
                currentUser = data.username;
                updateUserInterface(true, data.username);
            } else {
                updateUserInterface(false, null);
            }
        })
        .catch(() => {
            updateUserInterface(false, null);
        });
    } else {
        updateUserInterface(false, null);
    }
}

function updateUserInterface(loggedIn, username) {
    const loginLink = document.getElementById('login-link');
    const userInfo = document.getElementById('user-info');
    const logoutBtn = document.getElementById('logout-btn');
    const recommendDesc = document.getElementById('recommend-desc');

    if (loggedIn && username) {
        loginLink.style.display = 'none';
        userInfo.style.display = 'inline';
        userInfo.textContent = `欢迎, ${username}`;
        logoutBtn.style.display = 'inline';
        recommendDesc.textContent = `为 ${username} 精选的音乐推荐`;
    } else {
        loginLink.style.display = 'inline';
        userInfo.style.display = 'none';
        logoutBtn.style.display = 'none';
        recommendDesc.textContent = '为你精选热门音乐推荐';
    }
}

function logout() {
    // 删除cookie
    document.cookie = 'user_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
    
    // 更新界面
    currentUser = null;
    updateUserInterface(false, null);
    
    // 重新加载推荐（作为游客）
    loadRecommendations(true);
}

function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
}

function loadRecommendations(refresh = false) {
    const loading = document.getElementById('loading');
    const container = document.getElementById('recommendations');

    loading.style.display = 'block';
    container.innerHTML = '';

    // 构建URL参数
    let url = '/api/recommend?limit=30';
    if (refresh) {
        // 强制刷新：包括刷新数据库缓存和强制从API获取新数据
        url += '&refresh=true&refresh_db=true';
    }

    fetch(url)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                container.innerHTML = data.data.map(video => createVideoCard(video)).join('');
                
                // 更新用户登录状态信息（从API响应中获取）
                if (data.user_logged_in !== undefined) {
                    currentUser = data.username;
                    updateUserInterface(data.user_logged_in, data.username);
                }
            } else {
                container.innerHTML = '<p style="text-align:center; color:#aaa;">暂无推荐内容</p>';
            }
        })
        .catch(error => {
            console.error('加载推荐失败:', error);
            container.innerHTML = '<p style="text-align:center; color:#e94560;">加载失败，请重试</p>';
        })
        .finally(() => {
            loading.style.display = 'none';
        });
}

function searchVideos(keyword) {
    const loading = document.getElementById('loading');
    const container = document.getElementById('recommendations');

    loading.style.display = 'block';
    container.innerHTML = '';

    fetch(`/api/search?keyword=${encodeURIComponent(keyword)}&page=1`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                if (data.data.length > 0) {
                    container.innerHTML = data.data.map(video => createVideoCard(video)).join('');
                } else {
                    container.innerHTML = `<p style="text-align:center; color:#aaa;">未找到包含 "${keyword}" 的视频</p>`;
                }
            } else {
                container.innerHTML = '<p style="text-align:center; color:#e94560;">搜索失败</p>';
            }
        })
        .catch(error => {
            console.error('搜索失败:', error);
            container.innerHTML = '<p style="text-align:center; color:#e94560;">搜索失败，请重试</p>';
        })
        .finally(() => {
            loading.style.display = 'none';
        });
}

function createVideoCard(video) {
    const playCount = formatNumber(video.play_count);
    const pubTime = formatTime(video.pub_time);

    // 封面图片URL由后端处理（优先使用本地缓存，与桌面版一致）
    const coverUrl = video.cover || '';

    // 如果没有封面，使用默认占位图
    const defaultCover = 'data:image/svg+xml,' + encodeURIComponent(`
        <svg xmlns="http://www.w3.org/2000/svg" width="320" height="180" viewBox="0 0 320 180">
            <rect fill="#66CCFF" width="320" height="180"/>
            <text x="160" y="95" text-anchor="middle" fill="white" font-size="14">🎵</text>
            <text x="160" y="115" text-anchor="middle" fill="white" font-size="12">${truncateTitle(escapeHtml(video.title || '音乐封面'), 20)}</text>
        </svg>
    `);

    return `
        <div class="video-card" data-bvid="${video.bvid}">
            <img src="${coverUrl}" alt="${video.title}" class="video-cover" loading="lazy" onerror="this.src='${defaultCover}'">
            <div class="video-info">
                <h3 class="video-title">${video.title}</h3>
                <div class="video-meta">
                    <span>${video.up_name}</span>
                    <span>${playCount}播放</span>
                </div>
                ${video.video_type ? `<div class="video-type">${video.video_type}</div>` : ''}
            </div>
        </div>
    `;
}

function truncateTitle(title, maxLength) {
    if (title.length <= maxLength) return title;
    return title.substring(0, maxLength) + '...';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatNumber(num) {
    if (!num) return '0';
    if (num >= 10000) {
        return (num / 10000).toFixed(1) + '万';
    }
    return num.toString();
}

function formatTime(timestamp) {
    if (!timestamp) return '';
    
    // 尝试作为时间戳处理
    if (typeof timestamp === 'number' || /^\d+$/.test(timestamp)) {
        const date = new Date(parseInt(timestamp) * 1000);
        if (!isNaN(date.getTime())) {
            return date.toLocaleDateString('zh-CN');
        }
    }
    
    // 尝试作为日期字符串处理
    if (typeof timestamp === 'string') {
        const date = new Date(timestamp);
        if (!isNaN(date.getTime())) {
            return date.toLocaleDateString('zh-CN');
        }
    }
    
    return timestamp;
}

function showVideoDetail(bvid) {
    fetch(`/api/video/${bvid}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const video = data.data;
                const modal = document.getElementById('video-modal');
                const detail = document.getElementById('video-detail');

                const videoUrl = `https://www.bilibili.com/video/${bvid}`;

                detail.innerHTML = `
                    <h2>${video.title}</h2>
                    <p>UP主: ${video.up_name || '未知'}</p>
                    <p>播放量: ${formatNumber(video.play_count || 0)}</p>
                    <p>发布时间: ${formatTime(video.pub_time || 0)}</p>
                    ${video.description ? `<p>简介: ${video.description}</p>` : ''}
                    <br>
                    <iframe src="https://player.bilibili.com/player.html?bvid=${bvid}&page=1"
                            width="100%" height="340" frameborder="0" allowfullscreen></iframe>
                    <br>
                    <div class="video-actions">
                        <a href="${videoUrl}" target="_blank" class="action-btn play-btn">
                            🎬 在B站观看
                        </a>
                        <button class="action-btn refresh-btn" onclick="loadRecommendations(true); document.getElementById('video-modal').style.display='none';">
                            🔄 刷新推荐
                        </button>
                        <button class="action-btn exclude-btn" onclick="excludeVideo('${bvid}', '${video.title.replace(/'/g, "\\'")}');">
                            🚫 不再出现
                        </button>
                    </div>
                `;

                modal.style.display = 'flex';
            }
        })
        .catch(error => {
            console.error('获取视频信息失败:', error);
        });
}

function excludeVideo(bvid, title) {
    if (!confirm(`确定要将"${title}"添加到不再出现列表吗？`)) {
        return;
    }
    
    fetch(`/api/excluded/${bvid}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ title: title })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('已添加到不再出现列表');
            stopVideoPlayback();
            document.getElementById('video-modal').style.display = 'none';
            loadRecommendations(false);
        } else {
            alert('添加失败: ' + (data.error || '未知错误'));
        }
    })
    .catch(error => {
        console.error('添加排除失败:', error);
        alert('添加失败，请重试');
    });
}

function stopVideoPlayback() {
    const detail = document.getElementById('video-detail');
    const iframe = detail.querySelector('iframe');
    if (iframe) {
        // 清空iframe的src来停止播放（最可靠的方法）
        iframe.src = '';
    }
}
