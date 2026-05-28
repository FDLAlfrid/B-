// 首页 JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // 加载热门推荐
    loadHotRecommendations();

    // 搜索功能
    const searchBtn = document.getElementById('search-btn');
    const searchInput = document.getElementById('search-input');

    searchBtn.addEventListener('click', function() {
        const keyword = searchInput.value.trim();
        if (keyword) {
            window.location.href = `/recommend?keyword=${encodeURIComponent(keyword)}`;
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
        modal.style.display = 'none';
    });

    window.addEventListener('click', function(e) {
        if (e.target === modal) {
            modal.style.display = 'none';
        }
    });
});

function loadHotRecommendations() {
    fetch('/api/recommend?limit=6')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const container = document.getElementById('hot-recommendations');
                container.innerHTML = data.data.map(video => createVideoCard(video)).join('');
            }
        })
        .catch(error => {
            console.error('加载推荐失败:', error);
        });
}

function createVideoCard(video) {
    const playCount = formatNumber(video.play_count);

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
            <img src="${coverUrl}" alt="${video.title}" class="video-cover" onerror="this.src='${defaultCover}'">
            <div class="video-info">
                <h3 class="video-title">${video.title}</h3>
                <div class="video-meta">
                    <span>${video.up_name}</span>
                    <span>${playCount}播放</span>
                </div>
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
    if (num >= 10000) {
        return (num / 10000).toFixed(1) + '万';
    }
    return num.toString();
}

function showVideoDetail(bvid) {
    fetch(`/api/video/${bvid}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const video = data.data;
                const modal = document.getElementById('video-modal');
                const detail = document.getElementById('video-detail');

                detail.innerHTML = `
                    <h2>${video.title}</h2>
                    <p>UP主: ${video.up_name || '未知'}</p>
                    <p>播放量: ${formatNumber(video.play_count || 0)}</p>
                    <p>发布时间: ${formatTime(video.pub_time || 0)}</p>
                    <br>
                    <iframe src="https://player.bilibili.com/player.html?bvid=${bvid}&page=1"
                            width="100%" height="340" frameborder="0" allowfullscreen></iframe>
                `;

                modal.style.display = 'flex';
            }
        })
        .catch(error => {
            console.error('获取视频信息失败:', error);
        });
}

function formatTime(timestamp) {
    if (!timestamp) return '未知';
    const date = new Date(timestamp * 1000);
    return date.toLocaleDateString('zh-CN');
}
