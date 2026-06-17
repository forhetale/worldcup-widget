# AGENTS.md

## 项目概述

Windows 桌面悬浮挂件，展示 2026 FIFA 世界杯实时比分。无边框、透明背景、始终置顶，带系统托盘图标。所有 UI 文本和代码注释均为中文。

## 技术栈

- **后端**: Python — `pywebview` (嵌入式浏览器), `pystray` (托盘), `Pillow` (托盘图标绘制), `requests` (HTTP), `ctypes` (Win32 API)
- **前端**: 纯 HTML/CSS/JS，位于 `web/` 目录 — 无构建步骤、无打包器、无框架
- **数据源**: ESPN 公开 API (`site.api.espn.com`)，无需 API Key

## 运行方式

```bash
pip install pywebview pystray Pillow requests
python main.py
```

无 requirements.txt 或 pyproject.toml，需手动安装依赖。

## 架构

| 文件 | 职责 |
|------|------|
| `main.py` | 入口。启动托盘线程 + 数据轮询线程，创建 webview 窗口，暴露 `WidgetApi` 给 JS |
| `data_engine.py` | `WorldCupDataEngine` — 从 ESPN 拉取昨天/今天/明天的赛程，检测进球，线程安全 |
| `window_manager.py` | 通过 `ctypes.windll.user32` 操作 Win32 窗口 — 置顶、嵌入桌面、鼠标穿透、位置保存 |
| `web/index.html` | 挂件 UI — 两个视图：实时比分卡 + 赛程列表，进球浮层 |
| `web/app.js` | 前端逻辑 — 通过 `window.pushData()` 和 `window.pushGoalEvent()` 接收 Python 推送的数据 |
| `web/style.css` | 磨砂玻璃暗色主题，纯 CSS 动画 |
| `config.json` | 持久化的窗口位置和模式 (`top`/`desktop`) |
| `worldcup_schedule.json` | 静态备用赛程数据（实时引擎未使用） |

## 关键模式

- **Python→JS 通信**: Python 调用 `main_window.evaluate_js(f"pushData({json})")` 推送数据。JS 调用 `window.pywebview.api.*` 实现拖拽/关闭。
- **双重数据路径**: 后端每 5 秒主动推送 (`backend_ticker`)；前端每 5 秒也通过 `request_full_data()` 拉取作为备份 (`app.js:223-231`)。
- **刷新频率**: 有直播比赛时 20 秒拉取一次 ESPN，否则 120 秒 (`data_engine.py:164`)。
- **进球检测**: 比较前后两次总进球数，触发一次 `pushGoalEvent` (`data_engine.py:139-151`)。
- **窗口句柄**: 通过 `FindWindowW` 使用唯一标题 `WorldCup_Desktop_Widget_2026_Unique_Title` 查找 (`main.py:12`)。
- **线程模型**: 主线程运行 webview。两个守护线程：`run_tray()` 和 `backend_ticker()`。

## 注意事项

- **仅限 Windows**: `window_manager.py` 使用原始 `user32.dll` 调用，无法在 macOS/Linux 运行。
- **config.json 默认值 bug**: `window_manager.py:41` 的回退字典使用小写 `false`（JSON 风格），但 Python 需要 `False`。若无配置文件且触发回退会抛出 `NameError`。
- **无测试**: 无测试套件、无 lint、无类型检查。
- **ESPN API 时间**: 使用 `datetime.utcnow()` — 日期为 UTC，非本地时间。
- **国旗回退**: `<img>` 的 `onerror` 回退到 `flagcdn.com/w160/un.png`（联合国旗）。
- **无构建步骤**: 前端文件由 pywebview 直接从 `web/` 目录提供服务。
