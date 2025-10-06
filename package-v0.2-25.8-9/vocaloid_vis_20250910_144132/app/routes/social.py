from flask import Blueprint, render_template
from flask_login import login_required, current_user
from ..services import RecommendationService
from ..models import UserInterest
from .. import db

social_bp = Blueprint('social', __name__)

@social_bp.route('/matches')
@login_required
def user_matches():
    """用户匹配页面"""
    recommend_service = RecommendationService(db)
    matches = recommend_service.find_potential_friends(current_user.id)
    return render_template('matches.html', matches=matches)

@social_bp.route('/interests', methods=['GET', 'POST'])
@login_required
def user_interests():
    """用户兴趣设置"""
    if request.method == 'POST':
        # 清除现有兴趣
        UserInterest.query.filter_by(user_id=current_user.id).delete()
        
        # 添加新兴趣
        interests = request.form.getlist('interests')
        for interest in interests:
            new_interest = UserInterest(
                user_id=current_user.id,
                interest=interest,
                interest_level=5  # 默认最高兴趣程度
            )
            db.session.add(new_interest)
        
        db.session.commit()
        return redirect(url_for('social.profile'))
    
    # 获取现有兴趣
    user_interests = [i.interest for i in UserInterest.query.filter_by(user_id=current_user.id).all()]
    
    # 推荐兴趣标签
    recommended_interests = [
        'VOCALOID', 'UTAU', '洛天依', '乐正绫', '言和', 
        '星尘', '初音未来', '镜音铃', '镜音连', '巡音流歌'
    ]
    
    return render_template('interests.html', 
                          user_interests=user_interests,
                          recommended_interests=recommended_interests)

@social_bp.route('/profile')
@login_required
def user_profile():
    """用户个人资料页"""
    return render_template('profile.html', user=current_user)