import json
import os
import hashlib
import shutil
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta

class UserAuth:
    """用户认证模块"""
    def __init__(self):
        self.base_data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        self.user_data_file = os.path.join(self.base_data_dir, 'users.json')
        self.token_data_file = os.path.join(self.base_data_dir, 'tokens.json')
        self.default_data_dir = os.path.join(self.base_data_dir, 'default')
        self._init_data_files()

    def _init_data_files(self):
        """初始化数据文件"""
        if not os.path.exists(self.base_data_dir):
            os.makedirs(self.base_data_dir)

        if not os.path.exists(self.default_data_dir):
            os.makedirs(self.default_data_dir)

        if not os.path.exists(self.user_data_file):
            default_users = {
                "admin": {
                    "password": self._hash_password("admin123"),
                    "role": "admin",
                    "created_at": datetime.now().isoformat(),
                    "last_login": None
                }
            }
            with open(self.user_data_file, 'w', encoding='utf-8') as f:
                json.dump(default_users, f, ensure_ascii=False, indent=2)

        if not os.path.exists(self.token_data_file):
            with open(self.token_data_file, 'w', encoding='utf-8') as f:
                json.dump({}, f, ensure_ascii=False, indent=2)

        self._create_default_data()

    def _create_default_data(self):
        """创建默认数据文件（如果不存在）"""
        default_files = ['favorites.json', 'excluded.json', 'playlists.json', 'viewed.json', 'settings.json']
        for filename in default_files:
            filepath = os.path.join(self.default_data_dir, filename)
            if not os.path.exists(filepath):
                if filename == 'settings.json':
                    default_settings = {
                        "theme": "默认主题",
                        "display_mode": "light",
                        "default_sort": "综合排序",
                        "open_in_browser": True,
                        "no_image_mode": False,
                        "cover_size": "自动适应"
                    }
                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump(default_settings, f, ensure_ascii=False, indent=2)
                else:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump([] if 'json' in filename else {}, f, ensure_ascii=False, indent=2)

    def get_user_data_dir(self, username: str) -> str:
        """获取用户数据目录"""
        user_dir = os.path.join(self.base_data_dir, 'users', username)
        return user_dir

    def init_user_data(self, username: str):
        """为用户初始化数据目录（从默认数据复制）"""
        user_dir = self.get_user_data_dir(username)
        if not os.path.exists(user_dir):
            os.makedirs(user_dir)
            for filename in os.listdir(self.default_data_dir):
                src = os.path.join(self.default_data_dir, filename)
                dst = os.path.join(user_dir, filename)
                shutil.copy2(src, dst)
            print(f"为用户 {username} 创建数据目录")

    def get_user_data_file(self, username: str, filename: str) -> str:
        """获取用户特定数据文件路径"""
        user_dir = self.get_user_data_dir(username)
        return os.path.join(user_dir, filename)
    
    def _hash_password(self, password: str) -> str:
        """密码哈希"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def _load_users(self) -> Dict[str, Dict]:
        """加载用户数据"""
        try:
            with open(self.user_data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    
    def _save_users(self, users: Dict[str, Dict]):
        """保存用户数据"""
        with open(self.user_data_file, 'w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
    
    def _load_tokens(self) -> Dict[str, Dict]:
        """加载令牌数据"""
        try:
            with open(self.token_data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    
    def _save_tokens(self, tokens: Dict[str, Dict]):
        """保存令牌数据"""
        with open(self.token_data_file, 'w', encoding='utf-8') as f:
            json.dump(tokens, f, ensure_ascii=False, indent=2)
    
    def register(self, username: str, password: str, role: str = "user") -> bool:
        """注册用户"""
        users = self._load_users()
        
        if username in users:
            return False
        
        users[username] = {
            "password": self._hash_password(password),
            "role": role,
            "created_at": datetime.now().isoformat(),
            "last_login": None
        }
        
        self._save_users(users)
        self.init_user_data(username)
        return True
    
    def login(self, username: str, password: str) -> Optional[str]:
        """用户登录，返回令牌"""
        users = self._load_users()
        
        if username not in users:
            return None
        
        if users[username]["password"] != self._hash_password(password):
            return None
        
        users[username]["last_login"] = datetime.now().isoformat()
        self._save_users(users)
        
        self.init_user_data(username)
        token = self._generate_token(username)
        return token
    
    def _generate_token(self, username: str) -> str:
        """生成认证令牌"""
        import uuid
        token = str(uuid.uuid4())
        tokens = self._load_tokens()
        
        tokens[token] = {
            "username": username,
            "expires_at": (datetime.now() + timedelta(days=7)).isoformat(),
            "created_at": datetime.now().isoformat()
        }
        
        self._save_tokens(tokens)
        return token
    
    def verify_token(self, token: str) -> Optional[Dict[str, str]]:
        """验证令牌"""
        tokens = self._load_tokens()
        
        if token not in tokens:
            return None
        
        token_data = tokens[token]
        expires_at = datetime.fromisoformat(token_data["expires_at"])
        
        if datetime.now() > expires_at:
            # 令牌过期
            del tokens[token]
            self._save_tokens(tokens)
            return None
        
        # 返回用户信息
        users = self._load_users()
        username = token_data["username"]
        
        if username in users:
            return {
                "username": username,
                "role": users[username]["role"]
            }
        
        return None
    
    def logout(self, token: str) -> bool:
        """用户登出"""
        tokens = self._load_tokens()
        
        if token in tokens:
            del tokens[token]
            self._save_tokens(tokens)
            return True
        
        return False
    
    def change_password(self, username: str, old_password: str, new_password: str) -> bool:
        """修改密码"""
        users = self._load_users()
        
        if username not in users:
            return False
        
        if users[username]["password"] != self._hash_password(old_password):
            return False
        
        users[username]["password"] = self._hash_password(new_password)
        self._save_users(users)
        return True
    
    def get_user_info(self, username: str) -> Optional[Dict]:
        """获取用户信息"""
        users = self._load_users()
        return users.get(username)
    
    def list_users(self) -> Dict[str, Dict]:
        """列出所有用户"""
        return self._load_users()

# 全局实例
user_auth = UserAuth()