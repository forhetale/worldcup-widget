# AGENTS.md

## 项目概述

Windows 桌面悬浮挂件，展示 2026 FIFA 世界杯实时比分。使用原生 Qt 透明无边框窗口，默认始终置顶，带系统托盘图标。所有 UI 文本和代码注释均为中文。

## 技术栈

- **GUI**: Python — `PySide6` (`QWidget`, `QSystemTrayIcon`, `QThread`)
- **数据源**: `requests` 调用 ESPN 公开 API (`site.api.espn.com`)，无需 API Key
- **系统能力**: `ctypes` 调用 Win32 API，用于补强置顶和鼠标穿透

## 运行方式

```bash
pip install -r requirements.txt
python main.py
```

## 架构

| 文件 | 职责 |
|------|------|
| `main.py` | 入口。创建 PySide6 原生悬浮窗口、托盘菜单、后台数据线程和 UI 渲染 |
| `data_engine.py` | `WorldCupDataEngine` — 从 ESPN 拉取昨天/今天/明天的赛程，检测进球，线程安全 |
| `window_manager.py` | 通过 `ctypes.windll.user32` 操作 Win32 窗口 — 置顶、鼠标穿透、配置读写 |
| `config.json` | 持久化本机窗口位置和状态 (`topmost`/`locked`) |
| `worldcup_schedule.json` | 静态备用赛程数据（实时引擎未使用） |
| `worldcup_widget.spec` | PyInstaller 打包配置 |

## 关键模式

- **原生浮窗**: Qt 窗口创建时设置 `FramelessWindowHint`、`Tool`、`WindowStaysOnTopHint`、`WA_TranslucentBackground`。
- **置顶补强**: `window_manager.set_topmost()` 使用 Win32 `SetWindowPos(HWND_TOPMOST)`；Qt 自身也保持 `WindowStaysOnTopHint`。
- **锁定穿透**: 锁定后主窗口设置 `WA_TransparentForMouseEvents` 和 `WS_EX_TRANSPARENT`，鼠标事件穿到下层窗口；同时显示独立的置顶小锁按钮用于解除锁定。
- **数据线程**: `DataWorker` 在 `QThread` 中运行，使用 Qt 信号 `data_ready` / `goal_ready` 更新主线程 UI。
- **刷新频率**: 有直播比赛时 20 秒拉取一次 ESPN，否则 120 秒，由 `data_engine.py` 控制。
- **进球检测**: 比较前后两次总进球数，触发一次进球浮层。

## 注意事项

- **仅限 Windows**: `window_manager.py` 使用原始 `user32.dll` 调用，无法在 macOS/Linux 运行。
- **不再使用 WebView**: `web/` 目录、`pywebview`、`pystray`、`Pillow` 已从运行路径移除。
- **无测试套件**: 当前仅做语法检查和手动运行验证。
- **ESPN API 时间**: 使用 `datetime.utcnow()` — 日期为 UTC，非本地时间。
