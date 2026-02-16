import requests
import json
from datetime import datetime
import os
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.popup import Popup
from kivy.core.clipboard import Clipboard
from kivy.uix.spinner import Spinner
from kivy.uix.togglebutton import ToggleButton
from kivy.clock import Clock
from kivy.metrics import dp

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
    "Accept": "application/json, text/plain, */*"
}
API_URL = "https://api.bilibili.com/x/web-interface/view?bvid={}"

def bv2av(bvid: str) -> int:
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
    table = 'fZodR9XQDSUm21yCkr6zBqiveYah8bt4xsWpHnJE7jL5VG3guMTKNPAwcF'
    s = [11, 10, 3, 8, 4, 6, 2, 9, 5, 7]
    xor = 177451812
    add = 8728348608
    aid = (aid ^ xor) + add
    r = list('BV1  4 1 7  ')
    for i in range(10):
        r[s[i]] = table[aid // 58 ** i % 58]
    return ''.join(r)

def get_bilibili_video_info(bvid: str) -> dict:
    if not bvid.startswith("BV") or len(bvid) != 12:
        return {"error": f"BV号格式错误：{bvid}（需以BV开头，长度12位）"}
    try:
        response = requests.get(API_URL.format(bvid), headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data["code"] == 0:
            video_data = data["data"]
            pub_time = datetime.fromtimestamp(video_data["pubdate"]).strftime("%Y-%m-%d %H:%M:%S")
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
            return {"error": f"API返回错误：{data['message']}"}
    except requests.exceptions.Timeout:
        return {"error": "请求超时，请检查网络"}
    except Exception as e:
        return {"error": f"网络请求失败：{str(e)}"}

class BilibiliApp(App):
    def build(self):
        self.title = "B站BV号查询"
        self.root = TabbedPanel()
        self.root.tab_pos = 'top_left'
        
        tab1 = TabbedPanelItem(text='单BV查询')
        tab1_content = self.create_single_query_tab()
        tab1.add_widget(tab1_content)
        
        tab2 = TabbedPanelItem(text='BV/AV互转')
        tab2_content = self.create_convert_tab()
        tab2.add_widget(tab2_content)
        
        tab3 = TabbedPanelItem(text='批量查询')
        tab3_content = self.create_batch_query_tab()
        tab3.add_widget(tab3_content)
        
        self.root.add_widget(tab1)
        self.root.add_widget(tab2)
        self.root.add_widget(tab3)
        
        return self.root
    
    def create_single_query_tab(self):
        layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        
        input_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(50))
        input_layout.add_widget(Label(text='BV号:', size_hint_x=0.2))
        self.bvid_input = TextInput(multiline=False, size_hint_x=0.6)
        input_layout.add_widget(self.bvid_input)
        
        query_btn = Button(text='查询', size_hint_x=0.2)
        query_btn.bind(on_press=self.query_single_bvid)
        input_layout.add_widget(query_btn)
        
        layout.add_widget(input_layout)
        
        scroll = ScrollView()
        self.result_label = Label(text='等待查询...', size_hint_y=None, valign='top', halign='left', text_size=(dp(350), None))
        self.result_label.bind(texture_size=self.result_label.setter('size'))
        scroll.add_widget(self.result_label)
        layout.add_widget(scroll)
        
        return layout
    
    def create_convert_tab(self):
        layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        
        convert_type = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(50))
        convert_type.add_widget(Label(text='转换类型:', size_hint_x=0.3))
        self.convert_spinner = Spinner(text='BV → AV', values=['BV → AV', 'AV → BV'], size_hint_x=0.7)
        convert_type.add_widget(self.convert_spinner)
        layout.add_widget(convert_type)
        
        input_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(50))
        input_layout.add_widget(Label(text='输入:', size_hint_x=0.2))
        self.convert_input = TextInput(multiline=False, size_hint_x=0.6)
        input_layout.add_widget(self.convert_input)
        
        convert_btn = Button(text='转换', size_hint_x=0.2)
        convert_btn.bind(on_press=self.convert_bv_av)
        input_layout.add_widget(convert_btn)
        
        layout.add_widget(input_layout)
        
        self.convert_result = Label(text='等待转换...', size_hint_y=None)
        layout.add_widget(self.convert_result)
        
        return layout
    
    def create_batch_query_tab(self):
        layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        
        input_layout = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(100))
        input_layout.add_widget(Label(text='BV号列表(用逗号分隔):', size_hint_y=None, height=dp(30)))
        self.batch_input = TextInput(multiline=True, size_hint_y=None, height=dp(70))
        input_layout.add_widget(self.batch_input)
        layout.add_widget(input_layout)
        
        batch_btn = Button(text='批量查询', size_hint_y=None, height=dp(50))
        batch_btn.bind(on_press=self.batch_query)
        layout.add_widget(batch_btn)
        
        scroll = ScrollView()
        self.batch_result = Label(text='等待查询...', size_hint_y=None, valign='top', halign='left', text_size=(dp(350), None))
        self.batch_result.bind(texture_size=self.batch_result.setter('size'))
        scroll.add_widget(self.batch_result)
        layout.add_widget(scroll)
        
        return layout
    
    def query_single_bvid(self, instance):
        bvid = self.bvid_input.text.strip()
        if not bvid:
            self.show_popup('错误', '请输入BV号')
            return
        
        self.result_label.text = '查询中...'
        Clock.schedule_once(lambda dt: self._do_query(bvid), 0.1)
    
    def _do_query(self, bvid):
        result = get_bilibili_video_info(bvid)
        if "error" in result:
            self.result_label.text = f"查询失败：{result['error']}"
        else:
            text = ""
            for category, info in result.items():
                text += f"\n【{category}】\n"
                for key, value in info.items():
                    text += f"  {key}：{value}\n"
            self.result_label.text = text
    
    def convert_bv_av(self, instance):
        convert_type = self.convert_spinner.text
        input_val = self.convert_input.text.strip()
        
        if not input_val:
            self.show_popup('错误', '请输入要转换的内容')
            return
        
        try:
            if convert_type == 'BV → AV':
                aid = bv2av(input_val)
                self.convert_result.text = f"✅ {input_val} → av{aid}"
            else:
                aid_str = input_val.replace("av", "")
                aid = int(aid_str)
                bvid = av2bv(aid)
                self.convert_result.text = f"✅ av{aid} → {bvid}"
        except Exception as e:
            self.convert_result.text = f"❌ 转换失败：{str(e)}"
    
    def batch_query(self, instance):
        bvid_input = self.batch_input.text.strip()
        bvid_list = [bvid.strip() for bvid in bvid_input.split(",") if bvid.strip()]
        
        if not bvid_list:
            self.show_popup('错误', '请输入BV号')
            return
        
        self.batch_result.text = f'开始查询{len(bvid_list)}个BV号...\n'
        Clock.schedule_once(lambda dt: self._do_batch_query(bvid_list), 0.1)
    
    def _do_batch_query(self, bvid_list):
        text = ""
        for idx, bvid in enumerate(bvid_list, 1):
            text += f"[{idx}/{len(bvid_list)}] 查询 {bvid}...\n"
            result = get_bilibili_video_info(bvid)
            if "error" in result:
                text += f"  ❌ {result['error']}\n\n"
            else:
                text += f"  ✅ 标题：{result['基础信息']['视频标题']}\n"
                text += f"     播放：{result['数据统计']['播放量']}\n\n"
        
        self.batch_result.text = text
    
    def show_popup(self, title, content):
        popup = Popup(title=title, content=Label(text=content), size_hint=(0.8, 0.4))
        popup.open()

if __name__ == '__main__':
    BilibiliApp().run()
