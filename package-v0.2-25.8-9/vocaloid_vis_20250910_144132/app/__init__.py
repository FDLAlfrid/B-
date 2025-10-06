from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
import os
from config import config

# 初始化数据库
db = SQLAlchemy()
login_manager = LoginManager()

def create_app(config_name='default'):
    app = Flask(__name__, template_folder='templates', static_folder='static')
    
    # 加载配置
    app.config.from_object(config[config_name])
    
    # 初始化扩展
    db.init_app(app)
    migrate = Migrate(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    
    # 确保静态文件夹和模板文件夹存在
    if not os.path.exists('../static'):
        os.makedirs('../static')
    if not os.path.exists('../templates'):
        os.makedirs('../templates')
    
    # 注册蓝图
    from .routes.auth import auth_bp
    from .routes.music import music_bp
    from .routes.social import social_bp
    from .routes.api import api_bp
    from .routes.admin import admin_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(music_bp, url_prefix='/music')
    app.register_blueprint(social_bp, url_prefix='/social')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    # 注册主路由
    from .routes.main import main_bp
    app.register_blueprint(main_bp)
    
    # 注册模板过滤器
    from .utils.time_utils import format_duration
    from .utils.number_utils import number_format
    app.add_template_filter(format_duration, 'format_duration')
    app.add_template_filter(number_format, 'number_format')
    
    return app