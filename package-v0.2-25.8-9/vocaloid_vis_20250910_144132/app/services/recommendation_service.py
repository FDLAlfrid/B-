import random
from ..models import Music, User, UserMusicInteraction

class RecommendationService:
    def __init__(self, db):
        self.db = db
        
    def get_popular_music(self, limit=10):
        """获取热门音乐"""
        return Music.query.order_by(Music.view_count.desc()).limit(limit).all()
    
    def get_recommended_music(self, user_id, limit=10, time_range='all', search_query='', randomize=False):
        """基于用户兴趣推荐音乐，支持随机推荐"""
        from datetime import datetime, timedelta
        
        # 获取基础推荐音乐
        if randomize:
            # 随机推荐：从所有音乐中随机选择
            all_music = Music.query.all()
            recommended_music = random.sample(all_music, min(len(all_music), limit * 3))
        else:
            # 热门推荐：按播放量排序
            recommended_music = self.get_popular_music(limit * 2)
        
        # 应用时间范围筛选
        if time_range != 'all':
            start_time = None
            end_time = datetime.now()
            
            if time_range == 'today':
                start_time = end_time.replace(hour=0, minute=0, second=0, microsecond=0)
            elif time_range == 'week':
                start_time = end_time - timedelta(days=7)
            elif time_range == 'month':
                start_time = end_time - timedelta(days=30)
            
            if start_time:
                recommended_music = [music for music in recommended_music 
                                   if music.crawl_time >= start_time and music.crawl_time <= end_time]
        
        # 应用搜索筛选
        if search_query:
            query_lower = search_query.lower()
            recommended_music = [music for music in recommended_music 
                               if query_lower in music.title.lower() 
                               or query_lower in music.author.lower()
                               or query_lower in (music.tags or '').lower()]
        
        # 如果随机推荐，再次随机打乱结果
        if randomize:
            random.shuffle(recommended_music)
        
        # 限制返回数量
        return recommended_music[:limit]
    
    def find_potential_friends(self, user_id, limit=5):
        """查找潜在好友"""
        # 简化版: 返回随机用户
        # 实际实现应基于兴趣相似度
        current_user = User.query.get(user_id)
        other_users = User.query.filter(User.id != user_id).all()
        
        # 随机选择几个用户作为潜在好友
        if len(other_users) > limit:
            return random.sample(other_users, limit)
        return other_users
    
    def user_based_recommendation(self, user_id, k=10, n=20):
        """基于用户的协同过滤推荐算法"""
        # 1. 获取用户兴趣矩阵
        user_interest_matrix = self._build_user_interest_matrix()
        
        # 2. 计算用户相似度
        user_similarity = self._calculate_user_similarity(user_interest_matrix)
        
        # 3. 找到最相似的k个用户
        similar_users = self._find_similar_users(user_id, user_similarity, k)
        
        # 4. 推荐这些用户喜欢的音乐
        recommendations = self._generate_recommendations(user_id, similar_users, n)
        
        return recommendations
    
    def _build_user_interest_matrix(self):
        """构建用户-音乐兴趣矩阵"""
        # 获取所有用户和音乐
        all_users = User.query.all()
        all_music = Music.query.all()
        
        # 创建用户-音乐兴趣矩阵
        user_interest_matrix = {}
        
        for user in all_users:
            user_interest_matrix[user.id] = {}
            
            # 获取用户的音乐交互记录
            interactions = UserMusicInteraction.query.filter_by(user_id=user.id).all()
            
            for music in all_music:
                # 计算用户对音乐的兴趣分数
                interest_score = 0
                
                # 查找用户对该音乐的交互记录
                user_interaction = next((interaction for interaction in interactions 
                                      if interaction.music_id == music.id), None)
                
                if user_interaction:
                    # 基于交互类型计算兴趣分数
                    if user_interaction.interaction_type == 'like':
                        interest_score = 5
                    elif user_interaction.interaction_type == 'play':
                        interest_score = 3
                    elif user_interaction.interaction_type == 'share':
                        interest_score = 4
                    elif user_interaction.interaction_type == 'comment':
                        interest_score = 2
                
                user_interest_matrix[user.id][music.id] = interest_score
        
        return user_interest_matrix
    
    def _calculate_user_similarity(self, user_interest_matrix):
        """计算用户相似度矩阵（使用余弦相似度）"""
        from math import sqrt
        
        user_ids = list(user_interest_matrix.keys())
        similarity_matrix = {}
        
        for i, user_id1 in enumerate(user_ids):
            similarity_matrix[user_id1] = {}
            
            for user_id2 in user_ids:
                if user_id1 == user_id2:
                    similarity_matrix[user_id1][user_id2] = 1.0
                    continue
                
                # 获取两个用户的兴趣向量
                user1_scores = list(user_interest_matrix[user_id1].values())
                user2_scores = list(user_interest_matrix[user_id2].values())
                
                # 计算余弦相似度
                dot_product = sum(a * b for a, b in zip(user1_scores, user2_scores))
                magnitude1 = sqrt(sum(a * a for a in user1_scores))
                magnitude2 = sqrt(sum(b * b for b in user2_scores))
                
                if magnitude1 == 0 or magnitude2 == 0:
                    similarity = 0.0
                else:
                    similarity = dot_product / (magnitude1 * magnitude2)
                
                similarity_matrix[user_id1][user_id2] = similarity
        
        return similarity_matrix
    
    def _find_similar_users(self, user_id, user_similarity, k):
        """找到最相似的k个用户"""
        # 实现查找相似用户逻辑
        pass
    
    def _generate_recommendations(self, user_id, similar_users, n):
        """生成推荐结果"""
        # 实现推荐生成逻辑
        pass