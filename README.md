# 2026 世界杯比分挂件

一个 Windows 桌面悬浮挂件，用于展示 2026 FIFA 世界杯实时比分与近期赛程。挂件使用透明无边框窗口，支持始终置顶，并带有系统托盘入口。

## 功能

- 从 ESPN 公开接口获取真实赛程和实时比分
- 展示直播比分卡、近期赛程列表和进球浮层
- 后台线程定时刷新数据，Qt 信号推送到原生窗口
- 支持系统托盘退出
- 自动保存窗口位置
- 支持始终置顶、锁定位置和锁定穿透

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

顶部按钮可以切换窗口行为：

| 按钮 | 说明 |
| --- | --- |
| 顶 | 开启或关闭始终置顶 |
| 锁 | 锁定位置并让除锁按钮外的区域鼠标穿透；再次点击解除 |

锁定后，挂件主体会把鼠标事件交给下方窗口，只有“锁”按钮仍可点击用于解除锁定。也可以通过系统托盘菜单解除锁定。

## 打包

项目包含 PyInstaller 配置文件：

```bash
pyinstaller worldcup_widget.spec
```

打包产物会生成在 `dist/` 目录中，该目录默认不会提交到 Git。

## 主要文件

| 文件 | 说明 |
| --- | --- |
| `main.py` | 程序入口，负责 PySide6 原生浮窗、托盘、后台刷新线程和界面渲染 |
| `data_engine.py` | ESPN 数据拉取、比分解析、进球检测 |
| `window_manager.py` | Win32 置顶、鼠标穿透和配置读写 |
| `worldcup_widget.spec` | PyInstaller 打包配置 |

## 注意

该项目依赖 Windows Win32 API，无法直接在 macOS 或 Linux 上运行。
