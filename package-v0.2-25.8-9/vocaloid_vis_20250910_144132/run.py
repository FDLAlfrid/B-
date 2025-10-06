from app import create_app
from app.utils import init_db

# 创建Flask应用实例
app = create_app()

if __name__ == '__main__':
    # 初始化数据库（如果需要）
    init_db(app)
    
    # 作为Flask应用的核心入口，不包含独立的数据抓取逻辑
    # 数据抓取和初始化由app_manager.py统一管理
    print("Flask应用已启动，访问地址: http://127.0.0.1:5000")
    app.run(debug=True, port=5000)