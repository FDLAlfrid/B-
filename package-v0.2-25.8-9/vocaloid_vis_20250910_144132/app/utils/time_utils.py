from datetime import datetime

def format_timestamp(timestamp):
    """将时间戳格式化为可读时间"""
    if not timestamp or timestamp == 0:
        return "未知时间"
    
    try:
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, OSError):
        return "无效时间"

def format_duration(seconds):
    """将秒数格式化为时分秒"""
    # 处理None、空字符串或0
    if not seconds or seconds == 0:
        return "0:00"
    
    # 确保seconds是整数
    try:
        seconds_int = int(seconds)
    except (ValueError, TypeError):
        return "0:00"
    
    hours = seconds_int // 3600
    minutes = (seconds_int % 3600) // 60
    seconds = seconds_int % 60
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes}:{seconds:02d}"