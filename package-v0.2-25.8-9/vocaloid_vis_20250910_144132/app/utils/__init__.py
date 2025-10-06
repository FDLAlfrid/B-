from ..models import User, UserInterest
from .. import db, login_manager

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def init_db(app):
    """初始化数据库"""
    with app.app_context():
        db.create_all()
        # 创建默认兴趣标签
        default_interests = ['VOCALOID', 'UTAU', '洛天依', '乐正绫', '言和', '初音未来']
        # 可以在这里添加更多初始化逻辑