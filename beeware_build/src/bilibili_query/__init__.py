"""
B站BV号查询 - BeeWare/Toga版本
"""

import toga
from toga.style import Pack
from toga.constants import COLUMN, ROW
import requests
import sys
import traceback


class BilibiliQueryApp(toga.App):
    def startup(self):
        try:
            self.log("应用启动中...")
            self.main_window = toga.MainWindow(title=self.formal_name)
            self.main_window.size = (400, 600)
            self.log("主窗口创建成功")

            main_box = toga.Box(style=Pack(direction=COLUMN, padding=5))

            button_box = toga.Box(style=Pack(direction=ROW, margin=5))
            
            self.single_btn = toga.Button(
                '单BV查询',
                on_press=self.show_single_query,
                style=Pack(margin=5, flex=1, height=40)
            )
            self.convert_btn = toga.Button(
                'BV/AV转换',
                on_press=self.show_convert,
                style=Pack(margin=5, flex=1, height=40)
            )
            self.batch_btn = toga.Button(
                '批量查询',
                on_press=self.show_batch_query,
                style=Pack(margin=5, flex=1, height=40)
            )

            button_box.add(self.single_btn)
            button_box.add(self.convert_btn)
            button_box.add(self.batch_btn)

            self.content_box = toga.Box(style=Pack(direction=COLUMN, margin=5, flex=1))
            
            self.single_query_box = self.create_single_query_tab()
            self.convert_box = self.create_convert_tab()
            self.batch_query_box = self.create_batch_query_tab()

            self.content_box.add(self.single_query_box)

            main_box.add(button_box)
            main_box.add(self.content_box)

            self.main_window.content = main_box
            self.main_window.show()
            self.log("应用启动完成！")
        except Exception as e:
            self.log(f"启动失败: {e}")
            self.log(f"错误详情: {traceback.format_exc()}")
            raise

    def log(self, message):
        """记录日志"""
        print(f"[B站BV查询] {message}")
        try:
            with open('/sdcard/bilibili_query.log', 'a', encoding='utf-8') as f:
                import datetime
                timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"[{timestamp}] {message}\n")
        except:
            pass

    def show_single_query(self, widget):
        self.content_box.clear()
        self.content_box.add(self.single_query_box)

    def show_convert(self, widget):
        self.content_box.clear()
        self.content_box.add(self.convert_box)

    def show_batch_query(self, widget):
        self.content_box.clear()
        self.content_box.add(self.batch_query_box)

    def create_single_query_tab(self):
        box = toga.Box(style=Pack(direction=COLUMN, padding=10))

        self.bv_input = toga.TextInput(
            placeholder='输入BV号',
            style=Pack(margin=5, height=40)
        )

        query_btn = toga.Button(
            '查询',
            on_press=lambda widget: self.query_bv(self.bv_input.value),
            style=Pack(margin=5, height=40)
        )

        self.result_label = toga.Label(
            '查询结果将显示在这里',
            style=Pack(margin=10, font_size=14)
        )

        box.add(self.bv_input)
        box.add(query_btn)
        box.add(self.result_label)

        return box

    def create_convert_tab(self):
        box = toga.Box(style=Pack(direction=COLUMN, padding=10))

        self.convert_bv_input = toga.TextInput(
            placeholder='输入BV号',
            style=Pack(margin=5, height=40)
        )

        convert_btn = toga.Button(
            'BV转AV',
            on_press=lambda widget: self.convert_bv_to_av(self.convert_bv_input.value),
            style=Pack(margin=5, height=40)
        )

        self.convert_result_label = toga.Label(
            '转换结果将显示在这里',
            style=Pack(margin=10, font_size=14)
        )

        box.add(self.convert_bv_input)
        box.add(convert_btn)
        box.add(self.convert_result_label)

        return box

    def create_batch_query_tab(self):
        box = toga.Box(style=Pack(direction=COLUMN, padding=10))

        self.batch_bv_input = toga.MultilineTextInput(
            placeholder='输入多个BV号，每行一个',
            style=Pack(margin=5, flex=1, min_height=200)
        )

        query_btn = toga.Button(
            '批量查询',
            on_press=lambda widget: self.batch_query(self.batch_bv_input.value),
            style=Pack(margin=5, height=40)
        )

        self.batch_result_label = toga.Label(
            '批量查询结果将显示在这里',
            style=Pack(margin=10, font_size=14)
        )

        box.add(self.batch_bv_input)
        box.add(query_btn)
        box.add(self.batch_result_label)

        return box

    def query_bv(self, bv):
        self.log(f"开始查询BV号: {bv}")
        self.main_window.info_dialog('提示', '正在查询，请稍候...')
        
        def do_query():
            try:
                self.log(f"发送请求到API: {bv}")
                url = f"https://api.bilibili.com/x/web-interface/view?bvid={bv}"
                response = requests.get(url, timeout=10)
                data = response.json()
                self.log(f"API响应: {data.get('code')}")

                if data.get('code') == 0:
                    info = data['data']
                    title = info['title']
                    author = info['owner']['name']
                    self.log(f"查询成功: {title}")
                    self.main_window.info_dialog(
                        '查询成功',
                        f"标题: {title}\n作者: {author}"
                    )
                else:
                    self.log(f"查询失败: {data.get('message')}")
                    self.main_window.error_dialog(
                        '查询失败',
                        data.get('message', '未知错误')
                    )
            except Exception as e:
                self.log(f"查询错误: {e}")
                self.log(f"错误详情: {traceback.format_exc()}")
                self.main_window.error_dialog('错误', str(e))
        
        self.call_in_background(do_query)

    def convert_bv_to_av(self, bv):
        self.log(f"开始转换BV号: {bv}")
        self.main_window.info_dialog('提示', '正在转换，请稍候...')
        
        def do_convert():
            try:
                self.log(f"发送请求到API: {bv}")
                url = f"https://api.bilibili.com/x/web-interface/view?bvid={bv}"
                response = requests.get(url, timeout=10)
                data = response.json()
                self.log(f"API响应: {data.get('code')}")

                if data.get('code') == 0:
                    aid = data['data']['aid']
                    self.log(f"转换成功: AV{aid}")
                    self.main_window.info_dialog(
                        '转换成功',
                        f"BV号: {bv}\nAV号: {aid}"
                    )
                else:
                    self.log(f"转换失败: {data.get('message')}")
                    self.main_window.error_dialog(
                        '转换失败',
                        data.get('message', '未知错误')
                    )
            except Exception as e:
                self.log(f"转换错误: {e}")
                self.log(f"错误详情: {traceback.format_exc()}")
                self.main_window.error_dialog('错误', str(e))
        
        self.call_in_background(do_convert)

    def batch_query(self, bv_list):
        self.log(f"开始批量查询")
        self.main_window.info_dialog('提示', '正在批量查询，请稍候...')
        
        def do_batch_query():
            try:
                bvs = [line.strip() for line in bv_list.split('\n') if line.strip()]
                self.log(f"共 {len(bvs)} 个BV号")
                results = []

                for i, bv in enumerate(bvs):
                    self.log(f"查询第 {i+1}/{len(bvs)} 个: {bv}")
                    url = f"https://api.bilibili.com/x/web-interface/view?bvid={bv}"
                    response = requests.get(url, timeout=10)
                    data = response.json()

                    if data.get('code') == 0:
                        info = data['data']
                        title = info['title']
                        results.append(f"{bv}: {title}")
                    else:
                        results.append(f"{bv}: 查询失败")

                result_text = '\n'.join(results)
                self.log(f"批量查询完成")
                self.main_window.info_dialog(
                    '批量查询完成',
                    result_text
                )
            except Exception as e:
                self.log(f"批量查询错误: {e}")
                self.log(f"错误详情: {traceback.format_exc()}")
                self.main_window.error_dialog('错误', str(e))
        
        self.call_in_background(do_batch_query)


def main():
    return BilibiliQueryApp()
