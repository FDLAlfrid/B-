"""
版本管理模块 - Vocaloid Toolbox Fusion
"""

# 版本号遵循语义化版本规范 (Semantic Versioning)
# 格式: 主版本号.次版本号.修订号-预发布标识
# 主版本号: 重大功能更新或不兼容的API更改
# 次版本号: 向下兼容的功能添加
# 修订号: 向下兼容的问题修复
__version__ = "2.0.0-beta"
__version_info__ = (2, 0, 0, "beta")

# 应用信息
APP_NAME = "Vocaloid Toolbox Fusion"
APP_DISPLAY_NAME = "Vocaloid音乐推荐系统"
APP_AUTHOR = "AI Assistant"
APP_DESCRIPTION = "智能Vocaloid音乐推荐与管理系统"

# 构建信息
BUILD_DATE = "2025-03-24"
BUILD_NUMBER = "2025032401"

# 功能版本标记
FEATURES = {
    "database_management": True,      # 数据库管理功能
    "auto_background_fetch": True,    # 自动后台抓取
    "sort_preferences": True,          # 排序偏好设置
    "view_history": True,              # 浏览历史记录
    "smart_dedup": True,               # 智能去重
    "recommendation_history": True,    # 推荐历史（回退功能）
    "cloud_control": True,             # 云端控制
    "share_service": True,             # 分享服务
}

def get_version_string():
    """获取完整版本字符串"""
    return f"{APP_NAME} v{__version__} (Build {BUILD_NUMBER})"

def get_short_version():
    """获取简短版本号"""
    return __version__

def get_build_info():
    """获取构建信息"""
    return {
        "version": __version__,
        "build_date": BUILD_DATE,
        "build_number": BUILD_NUMBER,
        "features": FEATURES
    }

def generate_version_info():
    """生成 PyInstaller 所需的 version_info.txt 文件"""
    # 从版本号中提取主版本号、次版本号、修订号
    version_parts = __version__.split('-')[0].split('.')
    major = int(version_parts[0]) if len(version_parts) > 0 else 1
    minor = int(version_parts[1]) if len(version_parts) > 1 else 0
    patch = int(version_parts[2]) if len(version_parts) > 2 else 0
    
    version_info = f'''VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({major}, {minor}, {patch}, 0),
    prodvers=({major}, {minor}, {patch}, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          u'040904B0',
          [
            StringStruct(u'CompanyName', u'{APP_AUTHOR}'),
            StringStruct(u'FileDescription', u'{APP_DISPLAY_NAME}'),
            StringStruct(u'FileVersion', u'{__version__}'),
            StringStruct(u'InternalName', u'VocaloidToolboxFusion'),
            StringStruct(u'OriginalFilename', u'VocaloidToolboxFusion_v{__version__}.exe'),
            StringStruct(u'ProductName', u'{APP_NAME}'),
            StringStruct(u'ProductVersion', u'{__version__}'),
            StringStruct(u'LegalCopyright', u'Copyright (C) 2025'),
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
'''
    return version_info


def update_version_info_file(filepath='version_info.txt'):
    """更新 version_info.txt 文件"""
    version_content = generate_version_info()
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(version_content)
    print(f"已更新 {filepath}")


if __name__ == "__main__":
    print(get_version_string())
    print(f"Build Date: {BUILD_DATE}")
    print(f"Features: {', '.join(k for k, v in FEATURES.items() if v)}")
    print()
    print("更新 version_info.txt...")
    update_version_info_file()
