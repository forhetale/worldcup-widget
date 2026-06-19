import sys
import time

from PySide6 import QtCore, QtGui, QtWidgets, QtNetwork, QtSvg

import window_manager as wm
from data_engine import WorldCupDataEngine

WIDGET_TITLE = "WorldCup_Desktop_Widget_2026_Unique_Title"

ICON_PATHS = {
    "pin": (
        '<path d="M12 17v5"/>'
        '<path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16h14v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7h1a2 2 0 0 0 0-4H8a2 2 0 0 0 0 4h1z"/>'
    ),
    "lock": (
        '<rect x="4" y="11" width="16" height="10" rx="2.8"/>'
        '<path d="M8 11V7a4 4 0 0 1 8 0v4"/>'
    ),
    "close": (
        '<path d="M18 6 6 18"/>'
        '<path d="m6 6 12 12"/>'
    ),
}


class DataWorker(QtCore.QObject):
    """在后台线程维护比分数据，避免窗口界面卡顿"""

    data_ready = QtCore.Signal(dict)
    goal_ready = QtCore.Signal(dict)

    def __init__(self):
        super().__init__()
        self._running = True
        self.engine = None

    @QtCore.Slot()
    def run(self):
        self.engine = WorldCupDataEngine()
        self.data_ready.emit(self.engine.get_full_data())

        while self._running:
            try:
                # 只有当数据引擎真正发起了网络请求（无论成功还是超时），才将最新状态推给 UI 重绘，从而消除无效的重绘风暴
                if self.engine.update_tick():
                    self.data_ready.emit(self.engine.get_full_data())

                goal_event = self.engine.pop_latest_goal_event()
                if goal_event:
                    self.goal_ready.emit(goal_event)

            except Exception as e:
                print(f"后台时钟异常: {e}")

            for _ in range(50):
                if not self._running:
                    return
                time.sleep(0.1)

    def stop(self):
        self._running = False


class TeamBadge(QtWidgets.QLabel):
    """绘制球队国旗，图片不可用时使用文字兜底"""

    _pixmap_cache = {}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(50, 34)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setObjectName("teamBadge")
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self._team_name = ""
        self._badge_url = ""
        self._pixmap = QtGui.QPixmap()
        self._loading = False
        self._manager = QtNetwork.QNetworkAccessManager(self)
        self._manager.finished.connect(self._handle_badge_reply)

    def set_team(self, name, badge_url=""):
        """设置球队名称和 ESPN 国旗图片地址"""
        badge_url = (badge_url or "").strip()
        name = name or ""
        if name == self._team_name and badge_url == self._badge_url:
            return

        self._team_name = name
        self._badge_url = badge_url
        self._pixmap = QtGui.QPixmap()
        self._loading = False

        if badge_url:
            cached_pixmap = self._pixmap_cache.get(badge_url)
            if cached_pixmap and not cached_pixmap.isNull():
                self._pixmap = cached_pixmap
            else:
                self._loading = True
                request = QtNetwork.QNetworkRequest(QtCore.QUrl(badge_url))
                request.setRawHeader(b"User-Agent", b"WorldCupDesktopWidget/2026")
                self._manager.get(request)

        self.update()

    def _handle_badge_reply(self, reply):
        """接收异步下载的国旗图片"""
        request_url = reply.request().url().toString()
        if request_url != self._badge_url:
            reply.deleteLater()
            return

        self._loading = False
        if reply.error() == QtNetwork.QNetworkReply.NoError:
            pixmap = QtGui.QPixmap()
            if pixmap.loadFromData(bytes(reply.readAll())):
                self._pixmap_cache[request_url] = pixmap
                self._pixmap = pixmap

        reply.deleteLater()
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        flag_rect = QtCore.QRectF(self.rect()).adjusted(2, 2, -2, -2)

        if not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                flag_rect.size().toSize(),
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation,
            )
            target = QtCore.QRectF(
                flag_rect.x() + (flag_rect.width() - scaled.width()) / 2,
                flag_rect.y() + (flag_rect.height() - scaled.height()) / 2,
                scaled.width(),
                scaled.height(),
            )
            painter.drawPixmap(target, scaled, QtCore.QRectF(scaled.rect()))
        else:
            fallback_text = "…" if self._loading else (self._team_name[:1] if self._team_name else "-")
            font = painter.font()
            font.setPointSize(15)
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QtGui.QColor(230, 246, 240, 220))
            painter.drawText(flag_rect, QtCore.Qt.AlignCenter, fallback_text)

        painter.end()


class LockControlWindow(QtWidgets.QWidget):
    """锁定状态下保留可点击的小控制窗"""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setWindowTitle("世界杯比分挂件锁定按钮")
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, False)
        self.setFixedSize(32, 32)
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.Tool
            | QtCore.Qt.WindowStaysOnTopHint
            | QtCore.Qt.NoDropShadowWindowHint
        )
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        self.button = IconButton("lock")
        self.button.setObjectName("floatingLockButton")
        self.button.setProperty("active", True)
        self.button.setFixedSize(24, 24)
        self.button.setToolTip("解除锁定和穿透")
        self.button.clicked.connect(owner.toggle_locked)
        layout.addWidget(self.button, alignment=QtCore.Qt.AlignCenter)
        self.setStyleSheet(STYLE_SHEET)

    def move_to_owner_lock_button(self, point=None):
        """移动到主窗口锁按钮所在的屏幕位置"""
        if point is None:
            point = self.owner.lock_btn.mapToGlobal(QtCore.QPoint(-4, -4))
        self.move(point)
        wm.set_topmost(int(self.winId()), True)


class IconButton(QtWidgets.QPushButton):
    """统一绘制窗口控制图标"""

    def __init__(self, icon_name, parent=None):
        super().__init__(parent)
        self.icon_name = icon_name
        self.setText("")
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setAttribute(QtCore.Qt.WA_Hover, True)

    def _draw_svg_icon(self, painter, color):
        """使用内置 SVG 路径绘制更规整的线性图标"""
        paths = ICON_PATHS.get(self.icon_name)
        if not paths:
            return False

        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
            'viewBox="0 0 24 24" fill="none" '
            f'stroke="{color.name(QtGui.QColor.HexRgb)}" '
            f'stroke-opacity="{color.alphaF():.3f}" stroke-width="2.1" '
            'stroke-linecap="round" stroke-linejoin="round">'
            f'{paths}</svg>'
        )
        renderer = QtSvg.QSvgRenderer(QtCore.QByteArray(svg.encode("utf-8")))
        icon_rect = QtCore.QRectF(self.rect()).adjusted(4.5, 4.5, -4.5, -4.5)
        renderer.render(painter, icon_rect)
        return True

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        active_val = self.property("active")
        active = active_val in (True, "true", "True", 1, "1")
        hovered = self.underMouse()
        is_close_hovered = self.objectName() == "closeButton" and hovered

        bg_color = QtGui.QColor(255, 255, 255, 15)
        border_color = QtGui.QColor(255, 255, 255, 26)
        icon_color = QtGui.QColor(222, 235, 238, 182)

        if active:
            bg_color = QtGui.QColor(74, 224, 146, 8)
            border_color = QtGui.QColor(88, 235, 160, 24)
            icon_color = QtGui.QColor(96, 238, 166, 205)

        if hovered:
            bg_color = QtGui.QColor(255, 255, 255, 28)
            border_color = QtGui.QColor(255, 255, 255, 44)

        if active and hovered:
            bg_color = QtGui.QColor(74, 224, 146, 14)
            border_color = QtGui.QColor(88, 235, 160, 34)
            icon_color = QtGui.QColor(118, 247, 181, 220)

        if is_close_hovered:
            bg_color = QtGui.QColor(245, 86, 96, 220)
            border_color = QtGui.QColor(255, 255, 255, 52)
            icon_color = QtGui.QColor(255, 255, 255, 230)

        button_rect = QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setBrush(bg_color)
        painter.setPen(QtGui.QPen(border_color, 1))
        painter.drawRoundedRect(button_rect, 9, 9)

        if self._draw_svg_icon(painter, icon_color):
            painter.end()
            return

        pen = QtGui.QPen(icon_color, 1.85, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.NoBrush)

        rect = self.rect()
        cx = rect.center().x()
        cy = rect.center().y()

        if self.icon_name == "pin":
            painter.save()
            painter.translate(cx, cy)
            painter.rotate(-36)
            path = QtGui.QPainterPath()
            path.moveTo(-3.5, -7.0)
            path.lineTo(4.5, -7.0)
            path.lineTo(4.5, -3.0)
            path.lineTo(7.0, -0.5)
            path.lineTo(2.5, 3.4)
            path.lineTo(1.0, 8.0)
            path.lineTo(-1.0, 8.0)
            path.lineTo(-2.5, 3.4)
            path.lineTo(-7.0, -0.5)
            path.lineTo(-4.5, -3.0)
            path.lineTo(-3.5, -7.0)
            painter.drawPath(path)
            painter.drawLine(-4.7, -3.0, 4.7, -3.0)
            painter.restore()
        elif self.icon_name == "lock":
            painter.drawRoundedRect(cx - 6, cy - 1, 12, 8, 2.4, 2.4)
            path = QtGui.QPainterPath()
            path.moveTo(cx - 4.4, cy - 1)
            path.lineTo(cx - 4.4, cy - 4.4)
            path.cubicTo(cx - 4.4, cy - 9.0, cx + 4.4, cy - 9.0, cx + 4.4, cy - 4.4)
            path.lineTo(cx + 4.4, cy - 1)
            painter.drawPath(path)
            painter.setBrush(icon_color)
            painter.setPen(QtCore.Qt.NoPen)
            painter.drawEllipse(QtCore.QPointF(cx, cy + 2.2), 1.0, 1.0)
            painter.setPen(pen)
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawLine(cx, cy + 3.5, cx, cy + 5.0)
        elif self.icon_name == "close":
            painter.drawLine(cx - 5, cy - 5, cx + 5, cy + 5)
            painter.drawLine(cx + 5, cy - 5, cx - 5, cy + 5)

        painter.end()


class ScheduleMatchRow(QtWidgets.QFrame):
    """赛程列表中的一行比赛"""

    clicked = QtCore.Signal(dict)

    def __init__(self, match):
        super().__init__()
        self.match = match
        self.setObjectName("scheduleRow")
        self.setProperty("live", bool(match.get("is_live")))
        self.setProperty("finished", bool(match.get("is_finished")))
        self.setCursor(QtCore.Qt.PointingHandCursor)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(8)

        self.home_label = QtWidgets.QLabel(match.get("home_team", ""))
        self.home_label.setObjectName("scheduleTeam")
        self.home_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        self.score_label = QtWidgets.QLabel(self._score_text(match))
        self.score_label.setObjectName("scheduleScore")
        self.score_label.setAlignment(QtCore.Qt.AlignCenter)
        self.score_label.setFixedWidth(58)

        self.away_label = QtWidgets.QLabel(match.get("away_team", ""))
        self.away_label.setObjectName("scheduleTeam")
        self.away_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        self.status_label = QtWidgets.QLabel(self._status_text(match))
        self.status_label.setObjectName("scheduleMeta")
        self.status_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.status_label.setFixedWidth(54)

        layout.addWidget(self.home_label, 1)
        layout.addWidget(self.score_label)
        layout.addWidget(self.away_label, 1)
        layout.addWidget(self.status_label)

    def _score_text(self, match):
        if match.get("home_score") is not None and match.get("away_score") is not None:
            return f"{match['home_score']} - {match['away_score']}"
        return "vs"

    def _status_text(self, match):
        if match.get("is_live") or match.get("is_finished"):
            return match.get("status", "")
        return match.get("time", "")

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked.emit(self.match)
            event.accept()
            return
        super().mousePressEvent(event)


class FloatingScoreWidget(QtWidgets.QWidget):
    """原生 Qt 悬浮比分窗口"""

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.current_data = None
        self.focus_match_id = None
        self.drag_offset = None
        self._startup_window_refreshed = False
        self._first_data_rendered = False
        self._last_schedule_ids = []
        self.topmost = bool(config.get("topmost", True))
        self.locked = bool(config.get("locked", False))

        self.setWindowTitle(WIDGET_TITLE)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setFixedSize(config.get("width", 400), config.get("height", 280))
        self._apply_window_flags()
        self._build_ui()
        self.lock_control = LockControlWindow(self)
        self._build_tray()
        self._restore_position()
        self._sync_controls()
        self.switch_view(0)

        QtCore.QTimer.singleShot(0, self._init_native_window)
        QtCore.QTimer.singleShot(100, self._refresh_window_after_startup)
        QtCore.QTimer.singleShot(0, self._force_initial_refresh)

    def _apply_window_flags(self):
        flags = (
            QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.Tool
            | QtCore.Qt.NoDropShadowWindowHint
        )
        if self.topmost:
            flags |= QtCore.Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)

    def _build_ui(self):
        self.setStyleSheet(STYLE_SHEET)

        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.setContentsMargins(6, 6, 6, 6)

        self.card = QtWidgets.QFrame()
        self.card.setObjectName("widgetCard")
        root_layout.addWidget(self.card)

        card_layout = QtWidgets.QVBoxLayout(self.card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(8)

        header = QtWidgets.QFrame()
        header.setObjectName("controlHeader")
        header_layout = QtWidgets.QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(7)

        self.live_dot = QtWidgets.QLabel()
        self.live_dot.setObjectName("liveDot")
        self.live_dot.setFixedSize(8, 8)

        brand = QtWidgets.QLabel("世界杯 2026")
        brand.setObjectName("brandText")

        self.status_label = QtWidgets.QLabel("数据加载中...")
        self.status_label.setObjectName("dataStatus")

        header_layout.addWidget(self.live_dot)
        header_layout.addWidget(brand)
        header_layout.addSpacing(4)
        header_layout.addWidget(self.status_label)
        header_layout.addStretch(1)

        self.topmost_btn = self._make_action_button("pin", "始终置顶", self.toggle_topmost)
        self.lock_btn = self._make_action_button("lock", "锁定并穿透", self.toggle_locked)
        self.close_btn = self._make_action_button("close", "关闭", self.close)
        self.close_btn.setObjectName("closeButton")

        for btn in (self.topmost_btn, self.lock_btn, self.close_btn):
            header_layout.addWidget(btn)

        card_layout.addWidget(header)

        self.stack = QtWidgets.QStackedWidget()
        self.stack.addWidget(self._build_live_page())
        self.stack.addWidget(self._build_schedule_page())
        card_layout.addWidget(self.stack, 1)

        self.navigation_footer = QtWidgets.QFrame()
        self.navigation_footer.setObjectName("navigationFooter")
        footer_layout = QtWidgets.QHBoxLayout(self.navigation_footer)
        footer_layout.setContentsMargins(4, 4, 4, 4)
        footer_layout.setSpacing(4)

        self.live_nav = self._make_nav_button("比分", 0)
        self.schedule_nav = self._make_nav_button("赛程", 1)
        footer_layout.addWidget(self.live_nav)
        footer_layout.addWidget(self.schedule_nav)
        card_layout.addWidget(self.navigation_footer)
        self.switch_view(0)

        self.goal_overlay = QtWidgets.QFrame(self.card)
        self.goal_overlay.setObjectName("goalOverlay")
        overlay_layout = QtWidgets.QVBoxLayout(self.goal_overlay)
        overlay_layout.setAlignment(QtCore.Qt.AlignCenter)
        self.goal_title = QtWidgets.QLabel("进球！")
        self.goal_title.setObjectName("goalTitle")
        self.goal_detail = QtWidgets.QLabel("")
        self.goal_detail.setObjectName("goalDetail")
        self.goal_score = QtWidgets.QLabel("")
        self.goal_score.setObjectName("goalScore")
        overlay_layout.addWidget(self.goal_title, alignment=QtCore.Qt.AlignCenter)
        overlay_layout.addWidget(self.goal_detail, alignment=QtCore.Qt.AlignCenter)
        overlay_layout.addWidget(self.goal_score, alignment=QtCore.Qt.AlignCenter)
        self.goal_overlay.hide()

    def _build_live_page(self):
        page = QtWidgets.QWidget()
        page.setObjectName("livePage")
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.no_match_panel = QtWidgets.QFrame()
        self.no_match_panel.setObjectName("emptyState")
        no_match_layout = QtWidgets.QVBoxLayout(self.no_match_panel)
        no_match_layout.setContentsMargins(18, 18, 18, 18)
        no_match_layout.setSpacing(7)
        no_match_layout.setAlignment(QtCore.Qt.AlignCenter)
        self.no_match_title = QtWidgets.QLabel("当前并无比赛进行中")
        self.no_match_title.setObjectName("noMatchTitle")
        self.next_match_hint = QtWidgets.QLabel("请切换到“赛程”查看后续比赛安排")
        self.next_match_hint.setObjectName("noMatchSub")
        self.next_match_hint.setWordWrap(True)
        no_match_layout.addWidget(self.no_match_title, alignment=QtCore.Qt.AlignCenter)
        no_match_layout.addWidget(self.next_match_hint, alignment=QtCore.Qt.AlignCenter)

        self.match_card = QtWidgets.QFrame()
        self.match_card.setObjectName("scoreStage")
        match_layout = QtWidgets.QHBoxLayout(self.match_card)
        match_layout.setContentsMargins(8, 8, 8, 8)
        match_layout.setSpacing(8)

        self.home_badge = TeamBadge()
        self.home_name = QtWidgets.QLabel("")
        self.home_name.setObjectName("teamName")
        self.home_record = QtWidgets.QLabel("主队")
        self.home_record.setObjectName("teamSide")
        home_box = self._team_box(self.home_badge, self.home_name, self.home_record)

        self.status_badge = QtWidgets.QLabel("")
        self.status_badge.setObjectName("statusBadge")
        self.score_label = QtWidgets.QLabel("- : -")
        self.score_label.setObjectName("scoreDisplay")
        self.score_caption = QtWidgets.QLabel("实时比分")
        self.score_caption.setObjectName("scoreCaption")
        self.group_label = QtWidgets.QLabel("")
        self.group_label.setObjectName("groupLabel")
        self.group_label.setAlignment(QtCore.Qt.AlignCenter)

        score_box = QtWidgets.QVBoxLayout()
        score_box.setAlignment(QtCore.Qt.AlignCenter)
        score_box.addWidget(self.status_badge, alignment=QtCore.Qt.AlignCenter)
        score_box.addWidget(self.score_label, alignment=QtCore.Qt.AlignCenter)
        score_box.addWidget(self.score_caption, alignment=QtCore.Qt.AlignCenter)
        score_box.addWidget(self.group_label, alignment=QtCore.Qt.AlignCenter)
        score_widget = QtWidgets.QWidget()
        score_widget.setObjectName("scoreCenter")
        score_widget.setLayout(score_box)

        self.away_badge = TeamBadge()
        self.away_name = QtWidgets.QLabel("")
        self.away_name.setObjectName("teamName")
        self.away_record = QtWidgets.QLabel("客队")
        self.away_record.setObjectName("teamSide")
        away_box = self._team_box(self.away_badge, self.away_name, self.away_record)

        match_layout.addWidget(home_box, 32)
        match_layout.addWidget(score_widget, 36)
        match_layout.addWidget(away_box, 32)

        layout.addWidget(self.no_match_panel)
        layout.addWidget(self.match_card)
        self.match_card.hide()
        return page

    def _build_schedule_page(self):
        page = QtWidgets.QWidget()
        page.setObjectName("schedulePage")
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        self.schedule_scroll = QtWidgets.QScrollArea()
        self.schedule_scroll.setObjectName("scheduleScroll")
        self.schedule_scroll.setWidgetResizable(True)
        self.schedule_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.schedule_content = QtWidgets.QWidget()
        self.schedule_content.setObjectName("scheduleContent")
        self.schedule_layout = QtWidgets.QVBoxLayout(self.schedule_content)
        self.schedule_layout.setContentsMargins(0, 0, 0, 0)
        self.schedule_layout.setSpacing(6)
        self.schedule_layout.addStretch(1)
        self.schedule_scroll.setWidget(self.schedule_content)
        layout.addWidget(self.schedule_scroll)
        return page

    def _team_box(self, badge, name_label, side_label):
        box = QtWidgets.QWidget()
        box.setObjectName("teamColumn")
        layout = QtWidgets.QVBoxLayout(box)
        layout.setAlignment(QtCore.Qt.AlignCenter)
        layout.setSpacing(5)
        side_label.setAlignment(QtCore.Qt.AlignCenter)
        name_label.setAlignment(QtCore.Qt.AlignCenter)
        name_label.setWordWrap(True)
        layout.addWidget(side_label, alignment=QtCore.Qt.AlignCenter)
        layout.addWidget(badge, alignment=QtCore.Qt.AlignCenter)
        layout.addWidget(name_label, alignment=QtCore.Qt.AlignCenter)
        return box

    def _make_action_button(self, text, tooltip, callback):
        button = IconButton(text)
        button.setObjectName("actionButton")
        button.setToolTip(tooltip)
        button.setFixedSize(24, 24)
        sp = button.sizePolicy()
        sp.setRetainSizeWhenHidden(True)
        button.setSizePolicy(sp)
        button.clicked.connect(callback)
        return button

    def _make_nav_button(self, text, index):
        button = QtWidgets.QPushButton(text)
        button.setObjectName("navButton")
        button.setCheckable(True)
        button.setFocusPolicy(QtCore.Qt.NoFocus)
        button.clicked.connect(lambda checked=False, nav_index=index: self.switch_view(nav_index))
        return button

    def _build_tray(self):
        self.tray_icon = QtWidgets.QSystemTrayIcon(create_tray_icon(), self)
        self.tray_icon.setToolTip("2026 世界杯比分挂件")
        self.tray_menu = QtWidgets.QMenu()

        title_action = QtGui.QAction("2026 世界杯实时比分", self)
        title_action.setEnabled(False)
        self.tray_menu.addAction(title_action)
        self.tray_menu.addSeparator()

        self.tray_topmost = QtGui.QAction("始终置顶", self)
        self.tray_topmost.setCheckable(True)
        self.tray_topmost.triggered.connect(self.toggle_topmost)
        self.tray_menu.addAction(self.tray_topmost)

        self.tray_locked = QtGui.QAction("锁定位置", self)
        self.tray_locked.setCheckable(True)
        self.tray_locked.triggered.connect(self.toggle_locked)
        self.tray_menu.addAction(self.tray_locked)

        self.tray_menu.addSeparator()
        quit_action = QtGui.QAction("退出挂件", self)
        quit_action.triggered.connect(self.close)
        self.tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.show()

    def _restore_position(self):
        screen = QtGui.QGuiApplication.primaryScreen().availableGeometry()
        width = self.width()
        height = self.height()
        default_x = screen.right() - width - 40
        default_y = screen.bottom() - height - 80
        x = int(self.config.get("x", default_x))
        y = int(self.config.get("y", default_y))

        if x < screen.left() - 200 or x > screen.right() - 50:
            x = default_x
        if y < screen.top() - 200 or y > screen.bottom() - 50:
            y = default_y
        self.move(x, y)

    def _save_config(self):
        self.config["topmost"] = self.topmost
        self.config["locked"] = self.locked
        self.config.pop("click_through", None)
        self.config["x"] = self.x()
        self.config["y"] = self.y()
        self.config["width"] = self.width()
        self.config["height"] = self.height()
        wm.save_config(self.config)

    def _sync_controls(self):
        lock_control_point = None
        if self.locked and self.lock_btn.isVisible():
            lock_control_point = self.lock_btn.mapToGlobal(QtCore.QPoint(-4, -4))

        self.topmost_btn.setProperty("active", self.topmost)
        self.lock_btn.setProperty("active", self.locked)
        self.card.setProperty("locked", self.locked)

        self.topmost_btn.setToolTip("关闭始终置顶" if self.topmost else "开启始终置顶")
        self.lock_btn.setToolTip("解除锁定和穿透" if self.locked else "锁定位置并穿透")

        self.tray_topmost.setChecked(self.topmost)
        self.tray_locked.setChecked(self.locked)

        self.lock_control.button.setProperty("active", True)

        for widget in (self.topmost_btn, self.lock_btn, self.card, self.close_btn, self.lock_control.button):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()

        if self.locked:
            if lock_control_point is None:
                lock_control_point = self.lock_btn.mapToGlobal(QtCore.QPoint(-4, -4))
            self.lock_control.move_to_owner_lock_button(lock_control_point)
            self.lock_control.show()
            self.lock_control.raise_()
            self.lock_btn.hide()
        else:
            self.lock_btn.show()
            self.lock_control.hide()

    def _init_native_window(self):
        """初始化原生窗口样式（仅在窗口创建或被 setWindowFlags 重建后调用）。
        
        包含 SWP_FRAMECHANGED 的重操作，会破坏 DWM 合成状态，
        因此不可在窗口可见时反复调用。
        """
        hwnd = int(self.winId())
        wm.init_window_styles(hwnd)
        self.apply_native_window_styles()

    def apply_native_window_styles(self):
        """应用当前的置顶和穿透状态（可安全反复调用，不触发 SWP_FRAMECHANGED）"""
        hwnd = int(self.winId())
        wm.set_topmost(hwnd, self.topmost)
        wm.set_global_click_through(hwnd, self.locked)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, self.locked)
        if self.topmost:
            self.raise_()

        if hasattr(self, "lock_control"):
            wm.set_global_click_through(int(self.lock_control.winId()), False)
            wm.set_topmost(int(self.lock_control.winId()), True)
            if self.locked:
                self.lock_control.raise_()

    def toggle_topmost(self):
        QtCore.QTimer.singleShot(10, self._do_toggle_topmost)

    def _do_toggle_topmost(self):
        self.topmost = not self.topmost
        self._apply_window_flags()
        
        self._init_native_window()
        self.show()
        
        self._sync_controls()
        self._save_config()
        
        self.activateWindow()
        self.update()
        self._force_dwm_repaint()

    def toggle_locked(self):
        QtCore.QTimer.singleShot(10, self._do_toggle_locked)

    def _do_toggle_locked(self):
        self.locked = not self.locked
        
        needs_rebuild = False
        if self.locked and not self.topmost:
            self.topmost = True
            needs_rebuild = True
            
        self._sync_controls()
        
        if not self.locked:
            # 递归清除所有子控件上残留的鼠标穿透属性
            self._clear_mouse_transparent_recursive(self)
            needs_rebuild = True
            
        if needs_rebuild:
            # 通过重建窗口 flags 来彻底刷新 Qt 事件传播管道和置顶状态
            self._apply_window_flags()
            self.show()
            self.activateWindow()
            self._init_native_window()
        else:
            self.apply_native_window_styles()
            
        self._save_config()
        self.update()
        if self.locked:
            self.lock_control.move_to_owner_lock_button()
        self._force_dwm_repaint()

    def _clear_mouse_transparent_recursive(self, widget):
        """递归清除控件树上的 WA_TransparentForMouseEvents 属性"""
        widget.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, False)
        for child in widget.findChildren(QtWidgets.QWidget):
            child.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, False)

    def switch_view(self, index):
        self.stack.setCurrentIndex(index)
        self.live_nav.setChecked(index == 0)
        self.schedule_nav.setChecked(index == 1)
        self.live_nav.update()
        self.schedule_nav.update()
        self.stack.update()
        self.card.update()
        self.update()
        self._force_dwm_repaint()

    def _force_dwm_repaint(self):
        """强制 DWM 合成器重绘 WA_TranslucentBackground 透明窗口。

        setFixedSize 会使 resize() 被钳位从而变成 no-op，
        因此需要先暂时放开最大高度约束，执行 resize trick，再恢复约束。
        """
        size = self.size()
        self.setMaximumHeight(size.height() + 2)
        self.resize(size.width(), size.height() + 1)
        QtWidgets.QApplication.processEvents()
        self.resize(size)
        self.setMaximumHeight(size.height())

    def eventFilter(self, watched, event):
        return super().eventFilter(watched, event)

    @QtCore.Slot(dict)
    def update_data(self, data):
        try:
            print(f"[UI] update_data 被调用, matches={len(data.get('matches', []))}, has_live={data.get('has_live')}")
            self.current_data = data
            self._update_status(data)
            self._render_focus_match()
            self._render_schedule()

            # 强制布局系统立即处理 show/hide 引起的变更
            self.card.updateGeometry()
            self.stack.currentWidget().updateGeometry()
            QtWidgets.QApplication.processEvents()

            # 强制 DWM 合成器重绘透明窗口
            self._force_dwm_repaint()

            # 首次数据到达时，延迟做一次额外的强制重绘以确保 DWM 合成正确
            if not self._first_data_rendered:
                self._first_data_rendered = True
                QtCore.QTimer.singleShot(200, self._force_first_data_repaint)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[UI] update_data 异常: {e}")

    def _force_first_data_repaint(self):
        """首次数据到达后的延迟强制重绘，确保透明窗口在启动阶段正确显示"""
        if self.current_data:
            self._render_focus_match()
            self._render_schedule()

            # 强制整个控件树 repaint
            self.card.repaint()
            self.stack.repaint()
            self.no_match_panel.repaint()
            self.match_card.repaint()

            self._force_dwm_repaint()

    @QtCore.Slot(dict)
    def show_goal_event(self, event):
        self.goal_detail.setText(f"{event.get('home_team', '')} vs {event.get('away_team', '')} 进球了")
        self.goal_score.setText(event.get("new_score", ""))
        self.goal_overlay.setGeometry(self.card.rect())
        self.goal_overlay.show()
        self.goal_overlay.raise_()
        QtCore.QTimer.singleShot(4500, self.goal_overlay.hide)

    def _update_status(self, data):
        if data.get("fetch_error"):
            self.live_dot.setProperty("active", False)
            self.status_label.setText("连接失败")
            self.status_label.setProperty("error", True)
        elif data.get("has_live"):
            self.live_dot.setProperty("active", True)
            self.status_label.setText("直播中")
            self.status_label.setProperty("error", False)
        else:
            self.live_dot.setProperty("active", False)
            self.status_label.setText("实时同步中")
            self.status_label.setProperty("error", False)

        for widget in (self.live_dot, self.status_label):
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def _render_current_data(self):
        if not self.current_data:
            return
        self._update_status(self.current_data)
        self._render_focus_match()
        self._render_schedule()

    def _force_initial_refresh(self):
        self.update()
        self.repaint()
        self.card.update()
        self.stack.update()

    def _refresh_window_after_startup(self):
        if self._startup_window_refreshed:
            return
        self._startup_window_refreshed = True
        self._init_native_window()
        self._sync_controls()
        self._refresh_after_first_data()

    def _refresh_after_first_data(self):
        if not self.current_data:
            return
        self._render_current_data()
        self.show()
        if self.topmost:
            self.raise_()
        self.update()
        self.repaint()
        self.card.update()
        self.stack.update()

    def _render_focus_match(self):
        matches = self.current_data.get("matches", []) if self.current_data else []
        match = None
        if self.focus_match_id:
            match = next((item for item in matches if item.get("id") == self.focus_match_id), None)
        if not match:
            match = next((item for item in matches if item.get("is_live")), None)

        if not match:
            next_match = next((item for item in matches if not item.get("is_finished") and not item.get("is_live")), None)
            if next_match:
                self.next_match_hint.setText(
                    f"下一场：{next_match['home_team']} vs {next_match['away_team']} · "
                    f"{next_match['date']} {next_match['time']}"
                )
            else:
                self.next_match_hint.setText("请切换到“赛程”查看后续比赛安排")
            self.match_card.hide()
            self.no_match_panel.show()
            return

        self.no_match_panel.hide()
        self.match_card.show()
        self.home_badge.set_team(match.get("home_team", ""), match.get("home_badge", ""))
        self.away_badge.set_team(match.get("away_team", ""), match.get("away_badge", ""))
        self.home_name.setText(match.get("home_team", ""))
        self.away_name.setText(match.get("away_team", ""))

        home_score = match.get("home_score")
        away_score = match.get("away_score")
        self.score_label.setText(
            f"{home_score if home_score is not None else '-'} : "
            f"{away_score if away_score is not None else '-'}"
        )

        if match.get("is_live"):
            self.status_badge.setText(match.get("status", "直播中"))
            self.status_badge.setProperty("live", True)
            self.score_caption.setText("实时比分")
        elif match.get("is_finished"):
            self.status_badge.setText(match.get("status", "已完赛"))
            self.status_badge.setProperty("live", False)
            self.score_caption.setText("已完赛")
        else:
            self.status_badge.setText(f"{match.get('date', '')} {match.get('time', '')}")
            self.status_badge.setProperty("live", False)
            self.score_caption.setText("即将开赛")

        group_text = match.get("group") or ""
        venue_text = match.get("venue") or ""
        info_lines = [text for text in (group_text, venue_text) if text]
        self.group_label.setText("\n".join(info_lines))
        self.group_label.setVisible(bool(info_lines))

        self.status_badge.style().unpolish(self.status_badge)
        self.status_badge.style().polish(self.status_badge)

    def _render_schedule(self):
        matches = self.current_data.get("matches", []) if self.current_data else []

        # 构建去重签名：仅在比赛列表或比分真正变化时才重建 UI
        new_ids = [(m.get("id"), m.get("home_score"), m.get("away_score"), m.get("status")) for m in matches]
        if new_ids == self._last_schedule_ids:
            return
        self._last_schedule_ids = new_ids

        self._clear_schedule()
        last_date = ""

        for match in matches:
            if match.get("date") != last_date:
                last_date = match.get("date", "")
                divider = QtWidgets.QLabel(last_date)
                divider.setObjectName("dateDivider")
                self.schedule_layout.insertWidget(self.schedule_layout.count() - 1, divider)

            row = ScheduleMatchRow(match)
            row.clicked.connect(self.select_match)
            self.schedule_layout.insertWidget(self.schedule_layout.count() - 1, row)

    def _clear_schedule(self):
        while self.schedule_layout.count() > 1:
            item = self.schedule_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def select_match(self, match):
        self.focus_match_id = match.get("id")
        self._render_focus_match()
        self.switch_view(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "goal_overlay"):
            self.goal_overlay.setGeometry(self.card.rect())
        if hasattr(self, "lock_control") and self.locked:
            self.lock_control.move_to_owner_lock_button(self.lock_btn.mapToGlobal(QtCore.QPoint(-4, -4)))

    def showEvent(self, event):
        super().showEvent(event)
        if self.current_data:
            QtCore.QTimer.singleShot(0, self._refresh_after_first_data)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and not self.locked:
            child = self.childAt(event.position().toPoint())
            if child and self._is_control_child(child):
                return
            self.drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def _is_control_child(self, widget):
        while widget is not None and widget is not self:
            if isinstance(widget, QtWidgets.QPushButton):
                return True
            widget = widget.parentWidget()
        return False

    def mouseMoveEvent(self, event):
        if self.drag_offset and event.buttons() & QtCore.Qt.LeftButton and not self.locked:
            self.move(event.globalPosition().toPoint() - self.drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.drag_offset = None
        self._save_config()
        event.accept()

    def closeEvent(self, event):
        self._save_config()
        self.lock_control.close()
        self.tray_icon.hide()
        super().closeEvent(event)


def create_tray_icon():
    """绘制托盘图标"""
    pixmap = QtGui.QPixmap(64, 64)
    pixmap.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    painter.setBrush(QtGui.QColor(6, 42, 28))
    painter.setPen(QtGui.QPen(QtGui.QColor(0, 240, 118), 3))
    painter.drawEllipse(4, 4, 56, 56)
    painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 160), 2))
    painter.drawEllipse(20, 20, 24, 24)
    painter.drawLine(32, 6, 32, 58)
    painter.drawLine(6, 32, 58, 32)
    painter.setBrush(QtGui.QColor(0, 240, 118))
    painter.setPen(QtCore.Qt.NoPen)
    painter.drawEllipse(29, 29, 6, 6)
    painter.end()
    return QtGui.QIcon(pixmap)


STYLE_SHEET = """
QWidget {
  font-family: "Microsoft YaHei", "Segoe UI";
  color: rgba(248, 252, 255, 238);
}

#widgetCard {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 rgba(12, 25, 21, 238),
    stop:0.50 rgba(16, 22, 21, 236),
    stop:1 rgba(10, 12, 12, 240));
  border: 1px solid rgba(255, 255, 255, 36);
  border-radius: 18px;
}


#widgetCard[locked="true"] #brandText,
#widgetCard[locked="true"] #teamName,
#widgetCard[locked="true"] #scoreDisplay,
#widgetCard[locked="true"] #noMatchTitle {
  color: rgba(255, 255, 255, 252);
}

#widgetCard[locked="true"] #dataStatus,
#widgetCard[locked="true"] #teamSide,
#widgetCard[locked="true"] #groupLabel,
#widgetCard[locked="true"] #scoreCaption {
  color: rgba(255, 255, 255, 165);
}

#widgetCard[locked="true"] QPushButton#actionButton,
#widgetCard[locked="true"] QPushButton#closeButton {
  background: rgba(255, 255, 255, 24);
  color: rgba(255, 255, 255, 210);
}

#floatingLockButton {
  border: 0;
  background: transparent;
  color: transparent;
  font-size: 11px;
  font-weight: 800;
}

#floatingLockButton:hover {
  background: transparent;
  color: transparent;
}

#controlHeader {
  min-height: 27px;
  max-height: 27px;
  background: transparent;
}

#liveDot {
  border-radius: 4px;
  background: rgba(255, 255, 255, 92);
}

#liveDot[active="true"] {
  background: rgb(62, 232, 143);
}

#brandText {
  color: rgba(255, 255, 255, 238);
  font-size: 11px;
  font-weight: 800;
}

#dataStatus {
  color: rgba(206, 220, 226, 150);
  font-size: 9px;
}

#dataStatus[error="true"] {
  color: rgb(255, 105, 105);
}

QPushButton#actionButton,
QPushButton#closeButton {
  border: 0;
  border-radius: 9px;
  background: transparent;
  color: transparent;
  font-size: 11px;
  font-weight: 800;
}

QPushButton#actionButton:hover,
QPushButton#closeButton:hover {
  background: transparent;
  color: transparent;
}

QPushButton#actionButton[active="true"] {
  background: transparent;
  color: transparent;
  border: 0;
}

QPushButton#closeButton:hover {
  background: transparent;
  color: transparent;
}

#livePage,
#schedulePage {
  background: transparent;
}

#emptyState {
  border-radius: 14px;
  background: rgba(255, 255, 255, 8);
  border: 1px solid rgba(255, 255, 255, 20);
}

#noMatchTitle {
  color: rgba(255, 255, 255, 230);
  font-size: 15px;
  font-weight: 800;
}

#noMatchSub {
  color: rgba(218, 231, 235, 128);
  font-size: 10px;
}

#scoreStage {
  border-radius: 15px;
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 rgba(255, 255, 255, 10),
    stop:0.52 rgba(75, 125, 103, 12),
    stop:1 rgba(255, 255, 255, 5));
  border: 1px solid rgba(255, 255, 255, 26);
}

#teamColumn {
  background: transparent;
}

#teamSide {
  color: rgba(210, 224, 229, 112);
  font-size: 9px;
  font-weight: 700;
}

#teamBadge {
  background: transparent;
  border: 0;
}

#teamName {
  color: rgba(250, 253, 255, 236);
  font-size: 12px;
  font-weight: 800;
}

#statusBadge {
  border-radius: 10px;
  padding: 3px 9px;
  color: rgba(255, 220, 112, 235);
  background: rgba(255, 215, 0, 18);
  border: 1px solid rgba(255, 215, 0, 42);
  font-size: 10px;
  font-weight: 800;
}

#statusBadge[live="true"] {
  color: rgb(98, 239, 164);
  background: rgba(63, 232, 143, 22);
  border: 1px solid rgba(63, 232, 143, 58);
}

#scoreDisplay {
  color: rgba(255, 255, 255, 246);
  font-family: "Consolas", "Microsoft YaHei";
  font-size: 34px;
  font-weight: 900;
}

#scoreCaption {
  color: rgba(208, 222, 228, 118);
  font-size: 9px;
  font-weight: 800;
}

#groupLabel {
  color: rgba(210, 224, 229, 108);
  font-size: 8px;
  line-height: 105%;
}

#scheduleScroll {
  background: transparent;
}

#scheduleContent {
  background: transparent;
}

#dateDivider {
  color: rgba(196, 216, 223, 130);
  font-size: 10px;
  font-weight: 800;
  padding: 2px 4px 0 4px;
}

#scheduleRow {
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 14);
  background: rgba(255, 255, 255, 8);
}

#scheduleRow:hover {
  background: rgba(255, 255, 255, 22);
  border: 1px solid rgba(255, 255, 255, 30);
}

#scheduleRow[live="true"] {
  background: rgba(70, 225, 145, 18);
  border: 1px solid rgba(70, 225, 145, 58);
}

#scheduleRow[finished="true"] {
  background: rgba(255, 255, 255, 7);
}

#scheduleTeam {
  color: rgba(246, 251, 255, 220);
  font-size: 11px;
  font-weight: 750;
}

#scheduleScore {
  border-radius: 8px;
  background: rgba(5, 11, 16, 92);
  color: rgba(255, 255, 255, 234);
  font-family: "Consolas", "Microsoft YaHei";
  font-size: 11px;
  font-weight: 900;
}

#scheduleRow[live="true"] #scheduleScore {
  color: rgb(98, 239, 164);
  background: rgba(63, 232, 143, 22);
}

#scheduleMeta {
  color: rgba(202, 218, 224, 128);
  font-size: 9px;
  font-weight: 750;
}

#navigationFooter {
  min-height: 38px;
  max-height: 38px;
  border-radius: 15px;
  background: rgba(255, 255, 255, 10);
  border: 1px solid rgba(255, 255, 255, 18);
}

QPushButton#navButton {
  border: 1px solid transparent;
  border-radius: 11px;
  background: transparent;
  color: rgba(218, 231, 235, 166);
  font-size: 11px;
  font-weight: 800;
  min-height: 28px;
}

QPushButton#navButton:checked {
  color: rgba(242, 255, 248, 242);
  background: rgba(43, 150, 103, 190);
  border: 1px solid rgba(102, 235, 168, 118);
}

QPushButton#navButton:hover {
  background: rgba(255, 255, 255, 18);
  color: rgba(255, 255, 255, 225);
}

QPushButton#navButton:checked:hover {
  color: rgba(242, 255, 248, 245);
  background: rgba(52, 170, 116, 206);
}

#goalOverlay {
  background: rgba(15, 36, 32, 240);
  border-radius: 18px;
}

#goalTitle {
  color: rgb(255, 221, 94);
  font-size: 34px;
  font-weight: 900;
}

#goalDetail {
  color: rgb(102, 238, 170);
  font-size: 13px;
  font-weight: 700;
}

#goalScore {
  color: rgb(255, 221, 94);
  font-size: 22px;
  font-weight: 800;
}
"""


def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    config = wm.load_config()
    widget = FloatingScoreWidget(config)
    widget.show()

    # 启动保底：延迟重建窗口以确保 DWM 合成器与 Qt 的 UpdateLayeredWindow 管道完全同步
    def _startup_ensure_dwm():
        widget._apply_window_flags()
        widget._init_native_window()
        widget.show()
        widget.activateWindow()
    QtCore.QTimer.singleShot(400, _startup_ensure_dwm)

    thread = QtCore.QThread()
    worker = DataWorker()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.data_ready.connect(widget.update_data)
    worker.goal_ready.connect(widget.show_goal_event)
    app.aboutToQuit.connect(worker.stop)
    widget.data_thread = thread
    widget.data_worker = worker
    QtCore.QTimer.singleShot(100, thread.start)

    try:
        sys.exit(app.exec())
    finally:
        worker.stop()
        thread.quit()
        thread.wait(3000)


if __name__ == "__main__":
    main()
