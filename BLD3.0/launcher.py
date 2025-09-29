import os
import sys
import subprocess
import json

# 配置
ENV_NAME = "bilibili_downloader"
MAIN_SCRIPT = "bilibili_downloader.py"

# 检查并激活虚拟环境
def check_and_activate_environment():
    # 检查当前是否已在虚拟环境中
    if "conda" in sys.executable.lower() and ENV_NAME in sys.executable.lower():
        print(f"已在虚拟环境 '{ENV_NAME}' 中运行")
        return True
    
    # 查找conda位置
    conda_cmd = "conda"
    if os.name == 'nt':
        # Windows系统尝试从常见位置查找conda
        conda_paths = [
            os.path.join(os.environ.get('USERPROFILE', ''), 'miniconda3', 'Scripts', 'conda.exe'),
            os.path.join(os.environ.get('USERPROFILE', ''), 'anaconda3', 'Scripts', 'conda.exe')
        ]
        for path in conda_paths:
            if os.path.exists(path):
                conda_cmd = path
                break
    
    try:
        # 检查环境是否存在
        result = subprocess.run([conda_cmd, 'env', 'list', '--json'], capture_output=True, text=True)
        envs = json.loads(result.stdout)
        
        env_exists = False
        for env_path in envs['envs']:
            if ENV_NAME in os.path.basename(env_path) or env_path.endswith(ENV_NAME):
                env_exists = True
                break
        
        if not env_exists:
            print(f"虚拟环境 '{ENV_NAME}' 不存在，正在创建...")
            # 使用environment.yml创建环境
            if os.path.exists('environment.yml'):
                subprocess.run([conda_cmd, 'env', 'create', '-f', 'environment.yml'], check=True)
            else:
                print("未找到environment.yml文件，无法创建环境")
                return False
        
        # 使用conda run在虚拟环境中执行脚本
        print(f"正在虚拟环境 '{ENV_NAME}' 中启动程序...")
        subprocess.run([conda_cmd, 'run', '-n', ENV_NAME, 'python', MAIN_SCRIPT])
        return True
    except Exception as e:
        print(f"激活虚拟环境失败: {str(e)}")
        return False

if __name__ == "__main__":
    if not check_and_activate_environment():
        # 如果无法激活虚拟环境，尝试直接运行
        print("尝试直接运行程序...")
        subprocess.run([sys.executable, MAIN_SCRIPT])