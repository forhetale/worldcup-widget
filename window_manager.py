import ctypes
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

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_SHOWWINDOW = 0x0040
SWP_FRAMECHANGED = 0x0020
SWP_NOACTIVATE = 0x0010

user32 = ctypes.windll.user32

# 全局变量保存窗口句柄
_hwnd = None
_config_path = os.path.join(os.path.dirname(__file__), "config.json")

def load_config():
    """加载配置文件"""
    config = None
    if os.path.exists(_config_path):
        try:
            with open(_config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception:
            pass

    if not isinstance(config, dict):
        config = {}

    # 兼容旧配置中的 mode 字段：top 视为置顶，desktop 视为非置顶
    if "topmost" not in config:
        config["topmost"] = config.get("mode", "top") == "top"

    defaults = {
        "topmost": True,
        "locked": False,
        "demo_mode": True,
        "x": 100,
        "y": 100,
        "width": 380,
        "height": 260
    }
    for key, value in defaults.items():
        config.setdefault(key, value)
    config.pop("mode", None)
    return config

def save_config(config):
    """保存配置文件"""
    try:
        with open(_config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"保存配置失败: {e}")

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
    user32.SetParent(hwnd, 0)
    if enable:
        flags = SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW | SWP_NOACTIVATE
        user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags)
        user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags | SWP_FRAMECHANGED)
    else:
        flags = SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW | SWP_NOACTIVATE
        user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, flags)

def keep_topmost(hwnd):
    """再次确认窗口保持在置顶层"""
    user32.SetParent(hwnd, 0)
    user32.SetWindowPos(
        hwnd,
        HWND_TOPMOST,
        0,
        0,
        0,
        0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW | SWP_NOACTIVATE
    )

def set_global_click_through(hwnd, enable):
    """设置系统级的全局鼠标穿透"""
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    if enable:
        style |= WS_EX_TRANSPARENT
    else:
        style &= ~WS_EX_TRANSPARENT
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
    user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)

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
