import ctypes
from ctypes import wintypes
import json
import os

# Windows API 常量
GWL_EXSTYLE = -20
GWL_STYLE = -16
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000

HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
HWND_BOTTOM = 1

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_SHOWWINDOW = 0x0040
SWP_FRAMECHANGED = 0x0020

user32 = ctypes.windll.user32
WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

# 全局变量保存窗口句柄
_hwnd = None
_config_path = os.path.join(os.path.dirname(__file__), "config.json")

def load_config():
    """加载配置文件"""
    if os.path.exists(_config_path):
        try:
            with open(_config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "mode": "top",
        "click_through": False,
        "locked": False,
        "demo_mode": True,
        "x": 100,
        "y": 100,
        "width": 380,
        "height": 260
    }

def save_config(config):
    """保存配置文件"""
    try:
        with open(_config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"保存配置失败: {e}")

def get_wallpaper_workerw():
    """获取 Windows 桌面的 WorkerW 窗口句柄（用于嵌入桌面背景）"""
    progman = user32.FindWindowW("Progman", None)
    # 发送消息 0x052C，促使系统生成两个 WorkerW 窗口
    user32.SendMessageTimeoutW(progman, 0x052C, 0, 0, 0, 1000, None)
    
    workerw = None
    
    def enum_proc(hwnd, lParam):
        nonlocal workerw
        buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buf, 256)
        if buf.value == "WorkerW":
            # 如果该 WorkerW 下面没有 SHELLDLL_DefView，它就是我们要找的壁纸背景层窗口
            shell_dll = user32.FindWindowExW(hwnd, 0, "SHELLDLL_DefView", None)
            if shell_dll == 0:
                workerw = hwnd
                return False  # 停止遍历
        return True

    user32.EnumWindows(WNDENUMPROC(enum_proc), 0)
    return workerw or progman

def init_window_styles(hwnd):
    """初始化窗口的 Windows 样式，如无任务栏图标、分层透明样式等"""
    global _hwnd
    _hwnd = hwnd
    
    # 设为 Tool Window（不显示在任务栏和 Alt+Tab 切换中）
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    style |= WS_EX_TOOLWINDOW
    style |= WS_EX_LAYERED
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
    
    # 触发样式更新
    user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)

def set_topmost(hwnd, enable):
    """切换窗口置顶"""
    if enable:
        # 解除与桌面背景的绑定
        user32.SetParent(hwnd, 0)
        user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    else:
        user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)

def embed_to_desktop(hwnd):
    """将窗口嵌入 Windows 桌面背景层"""
    # 避免作为子窗口挂载导致 Webview2 透明渲染异常或消失
    # 直接置为最底层窗口
    user32.SetParent(hwnd, 0)
    user32.SetWindowPos(hwnd, HWND_BOTTOM, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)

def set_global_click_through(hwnd, enable):
    """设置系统级的全局鼠标穿透"""
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    if enable:
        style |= WS_EX_TRANSPARENT
    else:
        style &= ~WS_EX_TRANSPARENT
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
    user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)

def apply_window_mode(hwnd, mode):
    """应用指定的窗口模式 (top / desktop)"""
    if mode == "top":
        set_topmost(hwnd, True)
    elif mode == "desktop":
        set_topmost(hwnd, False)
        embed_to_desktop(hwnd)

def get_window_rect(hwnd):
    """获取窗口当前位置与大小"""
    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_int),
                    ("top", ctypes.c_int),
                    ("right", ctypes.c_int),
                    ("bottom", ctypes.c_int)]
    rect = RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return {
        "x": rect.left,
        "y": rect.top,
        "width": rect.right - rect.left,
        "height": rect.bottom - rect.top
    }

def set_window_position(hwnd, x, y, width, height):
    """设置窗口位置和大小"""
    user32.SetWindowPos(hwnd, 0, x, y, width, height, SWP_NOZORDER | SWP_SHOWWINDOW)
