import requests
import json
from datetime import datetime
import os

# ====================== 核心配置 ======================
# 请求头（避免被B站风控）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
    "Accept": "application/json, text/plain, */*"
}
# B站视频信息API
API_URL = "https://api.bilibili.com/x/web-interface/view?bvid={}"

# ====================== BV↔AV 互转核心算法 ======================
def bv2av(bvid: str) -> int:
    """BV号转AV号（纯算法，无需调用API）"""
    table = 'fZodR9XQDSUm21yCkr6zBqiveYah8bt4xsWpHnJE7jL5VG3guMTKNPAwcF'
    tr = {c: i for i, c in enumerate(table)}
    s = [11, 10, 3, 8, 4, 6, 2, 9, 5, 7]
    xor = 177451812
    add = 8728348608
    
    try:
        r = 0
        for i in range(10):
            r += tr[bvid[s[i]]] * 58 ** i
        aid = (r - add) ^ xor
        return aid
    except Exception as e:
        raise ValueError(f"BV号格式错误：{bvid}，错误信息：{str(e)}")

def av2bv(aid: int) -> str:
    """AV号转BV号（纯算法，无需调用API）"""
    table = 'fZodR9XQDSUm21yCkr6zBqiveYah8bt4xsWpHnJE7jL5VG3guMTKNPAwcF'
    s = [11, 10, 3, 8, 4, 6, 2, 9, 5, 7]
    xor = 177451812
    add = 8728348608
    
    aid = (aid ^ xor) + add
    r = list('BV1  4 1 7  ')
    for i in range(10):
        r[s[i]] = table[aid // 58 ** i % 58]
    return ''.join(r)

# ====================== 单BV号查询核心功能 ======================
def get_bilibili_video_info(bvid: str) -> dict:
    """
    通过BV号查询B站视频完整信息
    :param bvid: B站视频BV号（如 BV1AE411r7ph）
    :return: 包含视频信息的字典，出错时返回error字段
    """
    # 校验BV号格式
    if not bvid.startswith("BV") or len(bvid) != 12:
        return {"error": f"BV号格式错误：{bvid}（需以BV开头，长度12位）"}
    
    try:
        # 调用B站公开API
        response = requests.get(API_URL.format(bvid), headers=HEADERS, timeout=10)
        response.raise_for_status()  # 抛出HTTP错误
        data = response.json()
        
        # API返回成功
        if data["code"] == 0:
            video_data = data["data"]
            # 格式化发布时间（时间戳转可读格式）
            pub_time = datetime.fromtimestamp(video_data["pubdate"]).strftime("%Y-%m-%d %H:%M:%S")
            
            # 整理核心信息
            result = {
                "基础信息": {
                    "BV号": video_data["bvid"],
                    "AV号": f"av{video_data['aid']}",
                    "视频标题": video_data["title"],
                    "发布时间": pub_time,
                    "视频简介": video_data["desc"][:100] + "..." if len(video_data["desc"]) > 100 else video_data["desc"]
                },
                "UP主信息": {
                    "UP主名称": video_data["owner"]["name"],
                    "UP主UID": video_data["owner"]["mid"],
                    "UP主主页": f"https://space.bilibili.com/{video_data['owner']['mid']}"
                },
                "数据统计": {
                    "播放量": video_data["stat"]["view"],
                    "弹幕数": video_data["stat"]["danmaku"],
                    "点赞数": video_data["stat"]["like"],
                    "投币数": video_data["stat"]["coin"],
                    "收藏数": video_data["stat"]["favorite"],
                    "转发数": video_data["stat"]["share"]
                },
                "其他": {
                    "视频时长(秒)": video_data["duration"],
                    "分区名称": video_data["tname"],
                    "视频链接": f"https://www.bilibili.com/video/{video_data['bvid']}"
                }
            }
            return result
        else:
            return {"error": f"API返回错误：{data['message']}（BV号可能不存在/已下架）"}
    
    except requests.exceptions.Timeout:
        return {"error": "请求超时，请检查网络或稍后重试"}
    except requests.exceptions.RequestException as e:
        return {"error": f"网络请求失败：{str(e)}"}
    except Exception as e:
        return {"error": f"解析数据失败：{str(e)}"}

# ====================== 批量查询 & 结果导出 ======================
def batch_query_bvids(bvid_list: list, export_path: str = "bilibili_info.json") -> None:
    """
    批量查询BV号信息并导出到JSON文件
    :param bvid_list: BV号列表（如 ["BV1AE411r7ph", "BV1sb411i7aT"]）
    :param export_path: 导出文件路径
    """
    batch_result = {}
    print(f"\n开始批量查询{len(bvid_list)}个BV号...")
    
    for idx, bvid in enumerate(bvid_list, 1):
        print(f"[{idx}/{len(bvid_list)}] 查询 {bvid}...")
        batch_result[bvid] = get_bilibili_video_info(bvid)
    
    # 导出到JSON文件
    try:
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(batch_result, f, ensure_ascii=False, indent=4)
        print(f"\n批量查询完成！结果已导出到：{os.path.abspath(export_path)}")
    except Exception as e:
        print(f"\n导出文件失败：{str(e)}")

# ====================== 命令行交互入口 ======================
def main():
    print("="*50)
    print("B站BV号信息查询工具（单文件版）")
    print("="*50)
    
    while True:
        print("\n请选择操作：")
        print("1. 单BV号查询（显示详细信息）")
        print("2. BV号 ↔ AV号 互转")
        print("3. 批量查询BV号并导出JSON")
        print("0. 退出程序")
        
        choice = input("\n输入操作编号：").strip()
        
        # 1. 单BV号查询
        if choice == "1":
            bvid = input("输入要查询的BV号（如 BV1AE411r7ph）：").strip()
            result = get_bilibili_video_info(bvid)
            
            if "error" in result:
                print(f"\n❌ 查询失败：{result['error']}")
            else:
                print("\n✅ 查询成功：")
                for category, info in result.items():
                    print(f"\n【{category}】")
                    for key, value in info.items():
                        print(f"  {key}：{value}")
        
        # 2. BV↔AV互转
        elif choice == "2":
            print("\n请选择转换类型：")
            print("a. BV号 → AV号")
            print("b. AV号 → BV号")
            sub_choice = input("输入a/b：").strip().lower()
            
            if sub_choice == "a":
                bvid = input("输入BV号：").strip()
                try:
                    aid = bv2av(bvid)
                    print(f"\n✅ {bvid} → av{aid}")
                except ValueError as e:
                    print(f"\n❌ 转换失败：{e}")
            elif sub_choice == "b":
                aid_str = input("输入AV号（如 170001）：").strip().replace("av", "")
                try:
                    aid = int(aid_str)
                    bvid = av2bv(aid)
                    print(f"\n✅ av{aid} → {bvid}")
                except ValueError:
                    print("\n❌ AV号格式错误（需为数字）")
                except Exception as e:
                    print(f"\n❌ 转换失败：{e}")
            else:
                print("\n❌ 无效选择！")
        
        # 3. 批量查询
        elif choice == "3":
            bvid_input = input("输入要批量查询的BV号（用英文逗号分隔，如 BV1AE411r7ph,BV1sb411i7aT）：").strip()
            bvid_list = [bvid.strip() for bvid in bvid_input.split(",") if bvid.strip()]
            
            if not bvid_list:
                print("\n❌ 未输入有效BV号！")
                continue
            
            export_path = input("输入导出文件名（默认 bilibili_info.json）：").strip() or "bilibili_info.json"
            batch_query_bvids(bvid_list, export_path)
        
        # 0. 退出
        elif choice == "0":
            print("\n👋 程序退出！")
            break
        
        # 无效选择
        else:
            print("\n❌ 无效操作编号，请重新输入！")

if __name__ == "__main__":
    # 安装依赖提示（首次运行）
    try:
        import requests
    except ImportError:
        print("⚠️  未安装requests库，正在自动安装...")
        os.system("pip install requests -i https://pypi.tuna.tsinghua.edu.cn/simple")
        import requests
    
    # 启动交互程序
    main()