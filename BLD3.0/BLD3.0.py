#一份来自于2024.12月的原始代码，从jupyter notebook移植。
import json
import os
import requests
import subprocess
import tkinter as tk
from tkinter import messagebox, filedialog
from moviepy import VideoFileClip, AudioFileClip, concatenate_videoclips

# 从用户输入中获取 cookies
def get_cookies_from_user():
    while True:
        cookies_format = input("请输入 cookies 的格式 (json/header): ").strip().lower()
        if cookies_format not in ['json', 'header']:
            print("无效的格式，请输入 'json' 或 'header'。")
            continue
        if cookies_format == 'json':
            cookies_input = input("请输入 JSON 格式的 cookies: ")
            try:
                cookies_list = json.loads(cookies_input)
                if isinstance(cookies_list, list):
                    cookies_dict = {cookie['name']: cookie['value'] for cookie in cookies_list}
                elif isinstance(cookies_list, dict):
                    cookies_dict = cookies_list
                else:
                    raise ValueError("无效的 JSON 格式: 不是列表也不是字典")
                return cookies_dict
            except json.JSONDecodeError as e:
                print(f"无效的 JSON 格式: {e}")
        elif cookies_format == 'header':
            cookies_input = input("请输入 HTTP header 字符串格式的 cookies: ")
            try:
                cookies_dict = {}
                for cookie in cookies_input.split(';'):
                    key, value = cookie.strip().split('=', 1)
                    cookies_dict[key] = value
                return cookies_dict
            except ValueError as e:
                print(f"无效的 HTTP header 字符串格式: {e}")

# 从用户输入中获取视频 URL
def get_video_url_from_user():
    while True:
        video_url = input("请输入 B站视频的 URL: ").strip()
        if video_url.startswith('https://www.bilibili.com/video/'):
            return video_url
        else:
            print("无效的 B站视频 URL，请重新输入。")

# 使用 requests 库获取视频页面内容
def download_video_with_requests(cookies_dict, video_url):
    response = requests.get(video_url, cookies=cookies_dict)
    if response.status_code == 200:
        print("成功获取视频页面内容:")
        print(response.text)
    else:
        print(f"请求失败，状态码: {response.status_code}")

# 使用 you-get 下载视频
def download_video_with_you_get(cookies_dict, video_url, save_path):
    cookies_str = "; ".join([f"{k}={v}" for k, v in cookies_dict.items()])
    command = ['you-get', '--cookies', cookies_str, '-o', save_path, video_url]
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if result.returncode == 0:
        print("视频下载成功！")
        return True
    else:
        print("视频下载失败！")
        print(result.stderr)
        return False

# 主函数
def main():
    print("欢迎使用 B站视频下载工具！")
    
    # 初始化Tkinter根窗口（不显示）
    root = tk.Tk()
    root.withdraw()
    
    # 获取 cookies
    use_cookies = input("是否使用 cookies 登录 (yes/no): ").strip().lower()
    if use_cookies == 'yes':
        cookies_dict = get_cookies_from_user()
    else:
        cookies_dict = {}
    
    # 获取视频 URL
    video_url = get_video_url_from_user()
    
    # 选择保存位置
    save_path = filedialog.askdirectory(title="选择保存位置")
    if not save_path:
        save_path = os.getcwd()
    print(f"保存到当前目录: {save_path}")
    
    # 选择下载方式
    while True:
        download_method = input("请选择下载方式 (requests/you-get): ").strip().lower()
        if download_method not in ['requests', 'you-get']:
            print("无效的下载方式，请输入 'requests' 或 'you-get'。")
            continue
        if download_method == 'requests':
            download_video_with_requests(cookies_dict, video_url)
            messagebox.showinfo("完成", "视频页面内容已获取")
        elif download_method == 'you-get':
            success = download_video_with_you_get(cookies_dict, video_url, save_path)
            if success:
                messagebox.showinfo("完成", "视频下载成功！")
            else:
                messagebox.showerror("错误", "视频下载失败！")
        break

if __name__ == "__main__":
    main()
