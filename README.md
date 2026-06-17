# 2026 世界杯比分挂件

一个 Windows 桌面悬浮挂件，用于展示 2026 FIFA 世界杯实时比分与近期赛程。挂件使用透明无边框窗口，支持始终置顶或放入桌面层，并带有系统托盘入口。

## 功能

- 从 ESPN 公开接口获取真实赛程和实时比分
- 展示直播比分卡、近期赛程列表和进球浮层
- 后端定时推送数据，前端定时拉取作为备份
- 支持系统托盘退出
- 自动保存窗口位置

## 环境

- Windows
- Python 3.11 或更高版本

## 安装依赖

```bash
pip install -r requirements.txt
```

## 运行

```bash
python main.py
```

首次运行会自动使用默认窗口配置。运行后生成的 `config.json` 属于本机配置，默认不会提交到 Git。

## 打包

项目包含 PyInstaller 配置文件：

```bash
pyinstaller worldcup_widget.spec
```

打包产物会生成在 `dist/` 目录中，该目录默认不会提交到 Git。

## 主要文件

| 文件 | 说明 |
| --- | --- |
| `main.py` | 程序入口，负责托盘、后台刷新线程、WebView 窗口和前后端 API |
| `data_engine.py` | ESPN 数据拉取、比分解析、进球检测 |
| `window_manager.py` | Win32 窗口样式、置顶、桌面层和位置保存 |
| `web/index.html` | 挂件界面结构 |
| `web/app.js` | 前端数据绑定、视图切换和进球浮层 |
| `web/style.css` | 挂件视觉样式和动画 |
| `worldcup_widget.spec` | PyInstaller 打包配置 |

## 注意

该项目依赖 Windows Win32 API，无法直接在 macOS 或 Linux 上运行。
