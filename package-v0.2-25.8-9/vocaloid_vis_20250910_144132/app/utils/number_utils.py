def number_format(value):
    """格式化数字，添加千位分隔符"""
    if value is None:
        return "0"
    
    try:
        num = int(value)
        return f"{num:,}"
    except (ValueError, TypeError):
        return str(value)

def format_file_size(size_bytes):
    """格式化文件大小"""
    if size_bytes is None:
        return "0 B"
    
    try:
        size = int(size_bytes)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"
    except (ValueError, TypeError):
        return "0 B"