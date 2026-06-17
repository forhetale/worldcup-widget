import os
import sys
import json
import time
import threading
import webview
import pystray
from PIL import Image, ImageDraw
import window_manager as wm
from data_engine import WorldCupDataEngine

WIDGET_TITLE = "WorldCup_Desktop_Widget_2026_Unique_Title"

# 初始化
data_engine = WorldCupDataEngine()
config = wm.load_config()

main_window = None
tray_icon = None
hwnd = None
widget_exit_flag = False


def create_tray_image():
    """动态绘制一个绿色足球托盘图标"""
    image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    dc = ImageDraw.Draw(image)
    dc.ellipse([4, 4, 60, 60], fill=(6, 42, 28, 255), outline=(0, 240, 118, 255), width=3)
    dc.ellipse([20, 20, 44, 44], fill=None, outline=(255, 255, 255, 180), width=2)
    dc.line([32, 4, 32, 60], fill=(255, 255, 255, 120), width=2)
    dc.line([4, 32, 60, 32], fill=(255, 255, 255, 120), width=2)
    dc.ellipse([29, 29, 35, 35], fill=(0, 240, 118, 255))
    return image


class WidgetApi:
    """暴露给前端的 Python API"""

    def start_drag(self):
        global hwnd
        if hwnd:
            wm.user32.ReleaseCapture()
            wm.user32.SendMessageW(hwnd, 0xA1, 2, 0)

    def request_full_data(self):
        return data_engine.get_full_data()

    def close_widget(self):
        safe_exit()


def safe_exit():
    global hwnd, config, widget_exit_flag, main_window, tray_icon
    widget_exit_flag = True
    if hwnd:
        rect = wm.get_window_rect(hwnd)
        config["x"] = rect["x"]
        config["y"] = rect["y"]
        wm.save_config(config)
    if tray_icon:
        tray_icon.stop()
    if main_window:
        main_window.destroy()
    sys.exit(0)


# ========== 托盘 ==========
def build_tray_menu():
    return pystray.Menu(
        pystray.MenuItem("2026 世界杯实时比分", lambda: None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("退出挂件", lambda: safe_exit())
    )

def run_tray():
    global tray_icon
    tray_icon = pystray.Icon("worldcup_widget", create_tray_image(),
                             "2026 世界杯比分挂件", build_tray_menu())
    tray_icon.run()


# ========== 后台数据刷新 ==========
def backend_ticker():
    global main_window, widget_exit_flag
    time.sleep(2)

    while not widget_exit_flag:
        try:
            # 推进数据引擎（内部自动控制刷新频率）
            data_engine.update_tick()

            # 检查进球
            goal_event = data_engine.pop_latest_goal_event()
            if goal_event and main_window:
                goal_json = json.dumps(goal_event, ensure_ascii=False)
                main_window.evaluate_js(f"pushGoalEvent({goal_json});")

            # 推送最新数据到前端
            if main_window:
                full_data = data_engine.get_full_data()
                data_json = json.dumps(full_data, ensure_ascii=False)
                main_window.evaluate_js(f"pushData({data_json});")

        except Exception as e:
            print(f"后台时钟异常: {e}")

        time.sleep(5)  # 每 5 秒检查一次


# ========== 窗口启动 ==========
def on_window_shown():
    global hwnd, config
    time.sleep(0.5)

    hwnd = wm.user32.FindWindowW(None, WIDGET_TITLE)
    if hwnd:
        wm.init_window_styles(hwnd)

        screen_w = wm.user32.GetSystemMetrics(0)
        screen_h = wm.user32.GetSystemMetrics(1)

        default_w, default_h = 400, 280
        saved_w = config.get("width", default_w)
        saved_h = config.get("height", default_h)
        default_x = screen_w - saved_w - 40
        default_y = screen_h - saved_h - 100

        saved_x = config.get("x", default_x)
        saved_y = config.get("y", default_y)

        if saved_x < -200 or saved_x > screen_w - 50:
            saved_x = default_x
        if saved_y < -200 or saved_y > screen_h - 50:
            saved_y = default_y

        wm.set_window_position(hwnd, saved_x, saved_y, saved_w, saved_h)
        wm.apply_window_mode(hwnd, config.get("mode", "top"))
    else:
        print("警告: 无法获取窗口句柄 HWND")


def main():
    global main_window

    threading.Thread(target=run_tray, daemon=True).start()
    threading.Thread(target=backend_ticker, daemon=True).start()

    web_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
    html_path = os.path.join(web_dir, "index.html")

    api = WidgetApi()
    main_window = webview.create_window(
        title=WIDGET_TITLE,
        url=html_path,
        js_api=api,
        width=400,
        height=280,
        resizable=False,
        frameless=True,
        transparent=True
    )

    webview.start(on_window_shown)


if __name__ == "__main__":
    main()
