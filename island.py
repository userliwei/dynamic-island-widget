# -*- coding: utf-8 -*-
"""
灵动岛主窗口
------------
无边框 / 透明 / 置顶的胶囊窗口，支持紧凑与展开两种形态及平滑变形动画。
"""

import math
from datetime import datetime

from PyQt5.QtCore import (
    QEasingCurve, QPoint, QPointF, QRect, QRectF, Qt, QTimer,
    QVariantAnimation, pyqtSignal,
)
from PyQt5.QtGui import (
    QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen,
    QPixmap, QRadialGradient,
)
from PyQt5.QtWidgets import (
    QAction, QGraphicsOpacityEffect, QHBoxLayout, QMenu, QStackedWidget,
    QVBoxLayout, QWidget,
)

import win_utils
from components import Dot, NavButton, draw_icon, noise_pixmap, safe_paint
from config import (
    EXP_H, EXP_R, EXP_W, IDLE_H, IDLE_R, IDLE_W, NAV_W, PAD, SHADOW_MARGIN,
    Theme, save_config,
)
from panels import (
    ClockPanel, NowPlayingPanel, SettingsPanel, SystemPanel, WeatherPanel,
    WorkStatusPanel, make_label,
)


def _smoothstep(edge0, edge1, x):
    if edge1 <= edge0:
        return 0.0 if x < edge0 else 1.0
    t = (x - edge0) / (edge1 - edge0)
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


# ============================================================
#  紧凑视图（休眠胶囊内部）
# ============================================================
class CompactView(QWidget):
    """自绘的紧凑显示：状态点 + 时间 + 附属图标。"""

    def __init__(self, island, parent=None):
        super().__init__(parent)
        self.island = island
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._pulse = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(70)
        self._state_color = Theme.OK
        self._extra_icon = None
        self._extra_text = ""

    def _tick(self):
        self._pulse = (self._pulse + 0.05) % 1.0
        self.update()

    def set_state(self, color, extra_icon=None, extra_text=""):
        self._state_color = color
        self._extra_icon = extra_icon
        self._extra_text = extra_text

    @safe_paint
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect())

        # 左侧呼吸点
        cx = r.left() + 17
        cy = r.center().y()
        pulse = 0.5 + 0.5 * math.sin(self._pulse * 2 * math.pi)
        glow_col = QColor(self._state_color)
        glow_col.setAlpha(int(40 + 60 * pulse))
        p.setPen(Qt.NoPen)
        p.setBrush(glow_col)
        p.drawEllipse(QRectF(cx - 4.2, cy - 4.2, 8.4, 8.4))
        p.setBrush(QColor(self._state_color))
        p.drawEllipse(QRectF(cx - 2.4, cy - 2.4, 4.8, 4.8))

        # 时间（居中）
        now = datetime.now()
        p.setFont(QFont("Microsoft YaHei UI", 12, QFont.DemiBold))
        p.setPen(QPen(Theme.TEXT))
        p.drawText(r, Qt.AlignCenter, now.strftime("%H:%M"))

        # 右侧附属信息：优先展示专注倒计时 / 图标，否则显示日期
        if self._extra_icon:
            draw_icon(p, QRectF(r.right() - 28, cy - 7, 14, 14),
                      self._extra_icon, QColor(Theme.TEXT_DIM), 1.4)
        elif self._extra_text:
            p.setFont(QFont("Microsoft YaHei UI", 9, QFont.DemiBold))
            p.setPen(QPen(Theme.ACCENT))
            p.drawText(QRectF(r.right() - 62, r.top(), 46, r.height()),
                       Qt.AlignVCenter | Qt.AlignRight, self._extra_text)
        else:
            p.setFont(QFont("Microsoft YaHei UI", 8))
            p.setPen(QPen(Theme.TEXT_FAINT))
            p.drawText(QRectF(r.right() - 56, r.top(), 40, r.height()),
                       Qt.AlignVCenter | Qt.AlignRight, now.strftime("%m/%d"))
        p.end()


# ============================================================
#  展开视图（导航栏 + 面板）
# ============================================================
class ExpandedView(QWidget):
    NAV = [
        ("clock", "clock", "时钟"),
        ("work", "monitor", "工作状态"),
        ("music", "music", "正在播放"),
        ("system", "cpu", "系统状态"),
        ("weather", "cloud", "天气"),
        ("settings", "gear", "设置"),
    ]

    def __init__(self, island, parent=None):
        super().__init__(parent)
        self.island = island
        self._drag_origin = None
        self.setAttribute(Qt.WA_NoSystemBackground, True)

        root = QHBoxLayout(self)
        root.setContentsMargins(PAD, PAD, PAD, PAD)
        root.setSpacing(8)

        # 左侧导航
        nav_host = QWidget(self)
        nav_lay = QVBoxLayout(nav_host)
        nav_lay.setContentsMargins(0, 2, 0, 2)
        nav_lay.setSpacing(3)
        nav_lay.addStretch(1)
        self.buttons = {}
        for key, icon, tip in self.NAV:
            btn = NavButton(key, icon, tip)
            btn.setFixedSize(34, 34)
            btn.clicked.connect(self.island.show_panel)
            self.buttons[key] = btn
            nav_lay.addWidget(btn, 0, Qt.AlignHCenter)
        nav_lay.addStretch(1)
        nav_host.setFixedWidth(NAV_W - 6)
        root.addWidget(nav_host)

        # 右侧内容
        self.stack = QStackedWidget(self)
        self.panels = {}
        for key, cls in (
            ("clock", ClockPanel),
            ("work", WorkStatusPanel),
            ("music", NowPlayingPanel),
            ("system", SystemPanel),
            ("weather", WeatherPanel),
            ("settings", SettingsPanel),
        ):
            panel = cls(island)
            self.panels[key] = panel
            self.stack.addWidget(panel)
        root.addWidget(self.stack, 1)

    def select(self, key):
        if key not in self.panels:
            key = "clock"
        self.stack.setCurrentWidget(self.panels[key])
        for k, b in self.buttons.items():
            b.set_active(k == key)

    # --- 空白区域拖动支持 ---
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_origin = e.globalPos() - self.island.frameGeometry().topLeft()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._drag_origin is not None and e.buttons() & Qt.LeftButton:
            self.island.drag_to(e.globalPos() - self._drag_origin)
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._drag_origin = None
        self.island.finish_drag()
        super().mouseReleaseEvent(e)


# ============================================================
#  通知气泡
# ============================================================
class NotifyBubble(QWidget):
    """出现在灵动岛下方的轻量提示条，独立置顶窗口。"""

    def __init__(self):
        super().__init__(
            None,
            Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint
            | Qt.WindowTransparentForInput,
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self._alpha = 0.0
        self._title = ""
        self._text = ""
        self._icon = "check"
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on_alpha)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.fade_out)

    def _on_alpha(self, v):
        self._alpha = float(v)
        self.update()

    @safe_paint
    def paintEvent(self, e):
        if self._alpha <= 0.01:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setOpacity(self._alpha)
        r = QRectF(self.rect()).adjusted(SHADOW_MARGIN, SHADOW_MARGIN,
                                         -SHADOW_MARGIN, -SHADOW_MARGIN)

        for i in range(6, 0, -1):
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 10))
            p.drawRoundedRect(r.adjusted(-i, -i + 2, i, i + 2),
                              r.height() / 2 + i, r.height() / 2 + i)

        grad = QLinearGradient(0, r.top(), 0, r.bottom())
        grad.setColorAt(0, QColor(32, 32, 37, 250))
        grad.setColorAt(1, QColor(18, 18, 22, 252))
        p.setPen(QPen(QColor(255, 255, 255, 32), 1))
        p.setBrush(grad)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)

        badge = QRectF(r.left() + 12, r.center().y() - 13, 26, 26)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(Theme.ACCENT))
        p.drawEllipse(badge)
        draw_icon(p, badge.adjusted(6, 6, -6, -6), self._icon,
                  QColor(255, 255, 255), 1.7)

        p.setFont(QFont("Microsoft YaHei UI", 9, QFont.DemiBold))
        p.setPen(QPen(Theme.TEXT))
        p.drawText(QRectF(badge.right() + 10, r.top() + 9, r.width() - 60, 16),
                   Qt.AlignVCenter | Qt.AlignLeft, self._title)
        p.setFont(QFont("Microsoft YaHei UI", 8))
        p.setPen(QPen(Theme.TEXT_DIM))
        p.drawText(QRectF(badge.right() + 10, r.top() + 26, r.width() - 60, 16),
                   Qt.AlignVCenter | Qt.AlignLeft, self._text)
        p.end()

    def show_message(self, title, text, icon, anchor, hold_ms=2400):
        self._title = title
        self._text = text
        self._icon = icon
        w, h = 330 + 2 * SHADOW_MARGIN, 62 + 2 * SHADOW_MARGIN
        self.setFixedSize(w, h)
        x = anchor.x() + anchor.width() // 2 - w // 2
        y = anchor.bottom() - SHADOW_MARGIN + 8
        screen = self.screen().availableGeometry() if self.screen() else None
        if screen is not None:
            x = max(screen.left() + 8, min(x, screen.right() - w - 8))
            if y + h > screen.bottom():
                y = screen.bottom() - h - 8
        self.move(int(x), int(y))
        self.show()
        self.raise_()
        self._anim.stop()
        self._anim.setStartValue(self._alpha)
        self._anim.setEndValue(1.0)
        self._anim.start()
        self._hide_timer.start(hold_ms)

    def fade_out(self):
        self._anim.stop()
        self._anim.setStartValue(self._alpha)
        self._anim.setEndValue(0.0)
        self._anim.start()
        QTimer.singleShot(260, self.hide)


# ============================================================
#  主窗口
# ============================================================
class DynamicIsland(QWidget):
    def __init__(self, cfg):
        super().__init__(
            None,
            Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus,
        )
        self.cfg = cfg
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setWindowTitle("DynamicIsland")
        self.setMouseTracking(True)
        self.setCursor(Qt.ArrowCursor)

        self._morph = 0.0
        self._target = 0.0
        self._expanded = False
        self._dragging = False
        self._drag_off = QPoint()
        self._opacity = float(cfg.get("opacity", 0.96))
        self._panel_key = cfg.get("panel", "clock")
        self._pin_top = True

        # 内容几何状态（不含阴影边距）
        self._content_x = 0.0
        self._content_y = float(cfg.get("y", 46))
        self._content_w = float(IDLE_W)
        self._content_h = float(IDLE_H)

        # 子视图
        self.compact = CompactView(self, self)
        self.expanded = ExpandedView(self, self)

        self.ef_compact = QGraphicsOpacityEffect(self.compact)
        self.ef_compact.setOpacity(1.0)
        self.compact.setGraphicsEffect(self.ef_compact)
        self.ef_expanded = QGraphicsOpacityEffect(self.expanded)
        self.ef_expanded.setOpacity(0.0)
        self.expanded.setGraphicsEffect(self.ef_expanded)

        # 变形动画
        self.morph_anim = QVariantAnimation(self)
        self.morph_anim.setDuration(280)
        self.morph_anim.setEasingCurve(QEasingCurve.OutCubic)
        self.morph_anim.valueChanged.connect(self._on_morph)

        # 收起检测
        self.collapse_timer = QTimer(self)
        self.collapse_timer.setSingleShot(True)
        self.collapse_timer.timeout.connect(self._maybe_collapse)
        self.hover_poll = QTimer(self)
        self.hover_poll.timeout.connect(self._poll_hover)
        self.hover_poll.start(120)

        # 数据刷新
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._tick_clock)
        self.clock_timer.start(1000)

        # 面板切换柔光脉冲
        self._pulse = 0.0
        self.pulse_anim = QVariantAnimation(self)
        self.pulse_anim.setDuration(460)
        self.pulse_anim.setStartValue(1.0)
        self.pulse_anim.setEndValue(0.0)
        self.pulse_anim.setEasingCurve(QEasingCurve.OutCubic)
        self.pulse_anim.valueChanged.connect(self._on_pulse)

        # 实时信息刷新（当前窗口 / 正在播放 / 系统状态）
        self.live_timer = QTimer(self)
        self.live_timer.timeout.connect(self._tick_live)
        self.live_timer.start(2000)

        self.notify_bubble = NotifyBubble()

        # 顶层保活：避免被其他 topmost 窗口（如歌词条）遮挡
        self.topmost_timer = QTimer(self)
        self.topmost_timer.timeout.connect(self._keep_topmost)
        self.topmost_timer.start(2000)

        self.expanded.select(self._panel_key)
        self._place_initial()
        self._apply_morph(0.0)

    # ---------------- 几何 ----------------
    def _on_pulse(self, v):
        self._pulse = float(v)
        self.update()

    def _place_initial(self):
        screen = self.screen().availableGeometry()
        cx = self.cfg.get("x")
        if cx is None:
            self._content_x = (screen.width() - IDLE_W) / 2 + screen.left()
        else:
            self._content_x = float(cx)
        self._content_y = float(self.cfg.get("y", screen.top() + 64))
        S = SHADOW_MARGIN
        self.setGeometry(
            int(self._content_x - S), int(self._content_y - S),
            int(IDLE_W + 2 * S), int(IDLE_H + 2 * S),
        )

    def _set_content_geometry(self, w, h):
        cx = self._content_x + self._content_w / 2.0
        self._content_w, self._content_h = w, h
        self._content_x = cx - w / 2.0
        S = SHADOW_MARGIN
        self.setGeometry(
            int(round(self._content_x - S)),
            int(round(self._content_y - S)),
            int(round(w + 2 * S)),
            int(round(h + 2 * S)),
        )

    def resizeEvent(self, e):
        S = SHADOW_MARGIN
        rect = QRect(S, S, max(1, self.width() - 2 * S),
                     max(1, self.height() - 2 * S))
        self.compact.setGeometry(rect)
        self.expanded.setGeometry(rect)
        super().resizeEvent(e)

    # ---------------- 变形 ----------------
    def _on_morph(self, v):
        self._apply_morph(float(v))

    def _apply_morph(self, t):
        self._morph = t
        w = IDLE_W + (EXP_W - IDLE_W) * t
        h = IDLE_H + (EXP_H - IDLE_H) * t
        self._set_content_geometry(w, h)

        cop = 1.0 - _smoothstep(0.0, 0.40, t)
        eop = _smoothstep(0.22, 0.82, t)
        self.ef_compact.setOpacity(cop)
        self.ef_expanded.setOpacity(eop)

        if t <= 0.02:
            self.compact.show()
            self.expanded.hide()
        elif t >= 0.98:
            self.compact.hide()
            self.expanded.show()
        else:
            self.compact.show()
            self.expanded.show()
        self.update()

    def _animate_morph(self, target):
        self._target = target
        self.morph_anim.stop()
        self.morph_anim.setStartValue(self._morph)
        self.morph_anim.setEndValue(target)
        self.morph_anim.start()

    def expand(self):
        if self._expanded and self._target >= 0.99:
            return
        self._expanded = True
        self.collapse_timer.stop()
        self.expanded.select(self._panel_key)
        self._animate_morph(1.0)
        self._refresh_panel(self._panel_key)

    def collapse(self):
        if not self._expanded and self._target <= 0.01:
            return
        self._expanded = False
        self._animate_morph(0.0)

    def toggle(self):
        self.collapse() if self._expanded else self.expand()

    def _maybe_collapse(self):
        if not self._expanded:
            return
        if self.rect().contains(self.mapFromGlobal(self.cursor().pos())):
            return
        if self.notify_bubble.isVisible():
            pass
        self.collapse()

    def _poll_hover(self):
        pos = self.cursor().pos()
        inside = self.rect().contains(self.mapFromGlobal(pos))
        if inside:
            if not self._expanded and not self._dragging:
                self.expand()
            self.collapse_timer.stop()
        else:
            if self._expanded and not self._dragging and not self.collapse_timer.isActive():
                self.collapse_timer.start(int(self.cfg.get("collapse_delay_ms", 900)))

    # ---------------- 面板 ----------------
    def show_panel(self, key):
        self._panel_key = key
        self.cfg["panel"] = key
        self.persist()
        self.expanded.select(key)
        self._refresh_panel(key)
        self.pulse_anim.start()
        if not self._expanded:
            self.expand()

    def _refresh_panel(self, key):
        panel = self.expanded.panels.get(key)
        if panel is None:
            return
        if hasattr(panel, "refresh"):
            try:
                if key == "weather" and panel.lb_temp.text() == "--°":
                    panel.refresh()
                elif key != "weather":
                    panel.refresh()
            except Exception:
                pass

    # ---------------- 定时刷新 ----------------
    def _tick_clock(self):
        now = datetime.now()
        clock = self.expanded.panels.get("clock")
        if clock is not None and self._expanded:
            clock.refresh()

        cpu = psutil_cpu()
        if cpu >= 80:
            self.compact.set_state(Theme.DANGER)
        elif cpu >= 55:
            self.compact.set_state(Theme.WARN)
        else:
            self.compact.set_state(Theme.OK)

        work = self.expanded.panels.get("work")
        if work is not None and work.running:
            self.compact.set_state(
                Theme.ACCENT,
                extra_text="%02d:%02d" % (work.remaining // 60,
                                           work.remaining % 60),
            )
        else:
            music = self.expanded.panels.get("music")
            if music is not None and getattr(music, "_last_key", None):
                info = music._last_key
                if isinstance(info, tuple) and len(info) == 4 and info[2]:
                    self.compact.set_state(Theme.OK, extra_icon="music")
        self.compact.update()

    def _tick_live(self):
        """按当前面板刷新实时信息。"""
        if not self._expanded:
            return
        key = self._panel_key
        panel = self.expanded.panels.get(key)
        if panel is None or not hasattr(panel, "refresh"):
            return
        try:
            panel.refresh()
        except Exception:
            pass

    # ---------------- 绘制 ----------------
    @safe_paint
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        S = SHADOW_MARGIN
        r = QRectF(S, S, self.width() - 2 * S, self.height() - 2 * S)
        radius = IDLE_R + (EXP_R - IDLE_R) * self._morph

        body = QPainterPath()
        body.addRoundedRect(r, radius, radius)

        # ---- 1. 大范围柔和投影（多层累加，光向下扩散）----
        p.setPen(Qt.NoPen)
        for i in range(18, 0, -1):
            alpha = int(6.5 * (1.0 - i / 19.0) ** 1.9)
            if alpha <= 0:
                continue
            p.setBrush(QColor(0, 0, 0, min(16, alpha)))
            p.drawRoundedRect(
                r.adjusted(-i, -i * 0.35 + 5, i, i * 0.85 + 5),
                radius + i, radius + i,
            )

        # ---- 2. 玻璃主体（三段渐变，上部更通透）----
        a = self._opacity
        top = QColor(Theme.BG_TOP)
        bot = QColor(Theme.BG_BOT)
        top.setAlphaF(min(1.0, top.alphaF() * a + 0.04))
        bot.setAlphaF(min(1.0, bot.alphaF() * a + 0.02))
        mid = QColor(int((top.red() + bot.red()) * 0.52),
                     int((top.green() + bot.green()) * 0.52),
                     int((top.blue() + bot.blue()) * 0.54),
                     int((top.alpha() + bot.alpha()) * 0.5))
        grad = QLinearGradient(0, r.top(), 0, r.bottom())
        grad.setColorAt(0.0, top)
        grad.setColorAt(0.42, mid)
        grad.setColorAt(1.0, bot)
        p.setBrush(QBrush(grad))
        p.drawPath(body)

        # ---- 3. 极淡磨砂噪点（只提供微妙的材质颗粒）----
        p.save()
        p.setClipPath(body)
        p.setBrushOrigin(r.topLeft())
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(noise_pixmap()))
        p.drawRect(r.toRect())
        p.restore()

        # ---- 4. 光学层次：左上角反射 + 顶部微光 + 底部内阴影 ----
        p.save()
        p.setClipPath(body)
        p.setPen(Qt.NoPen)

        # 4a. 左上角柔和反光（模拟环境光入射）
        refl = QRadialGradient(
            QPointF(r.left() + r.width() * 0.22, r.top() + r.height() * 0.02),
            r.width() * 0.62,
        )
        refl.setColorAt(0.0, QColor(255, 255, 255, 26))
        refl.setColorAt(0.45, QColor(255, 255, 255, 9))
        refl.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(QBrush(refl))
        p.drawRect(r)

        # 4b. 顶部垂向微光
        hl_h = min(r.height() * 0.34, 58)
        hl = QLinearGradient(0, r.top(), 0, r.top() + hl_h)
        hl.setColorAt(0.0, QColor(255, 255, 255, 16))
        hl.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(QBrush(hl))
        p.drawRect(QRectF(r.left(), r.top(), r.width(), hl_h))

        # 4c. 底部内阴影（玻璃厚度）
        sh_h = min(r.height() * 0.34, 56)
        sh = QLinearGradient(0, r.bottom() - sh_h, 0, r.bottom())
        sh.setColorAt(0.0, QColor(0, 0, 0, 0))
        sh.setColorAt(1.0, QColor(0, 0, 0, 52))
        p.setBrush(QBrush(sh))
        p.drawRect(QRectF(r.left(), r.bottom() - sh_h, r.width(), sh_h))

        # ---- 5. 切换面板时的极淡脉冲 ----
        if self._pulse > 0.01:
            pg = QRadialGradient(r.center(), r.width() * 0.75)
            c1 = QColor(Theme.ACCENT)
            c1.setAlphaF(0.07 * self._pulse)
            c2 = QColor(Theme.ACCENT)
            c2.setAlpha(0)
            pg.setColorAt(0.0, c1)
            pg.setColorAt(1.0, c2)
            p.setBrush(QBrush(pg))
            p.drawRect(r)
        p.restore()

        # ---- 6. 外圈精细描边 ----
        border = QLinearGradient(0, r.top(), 0, r.bottom())
        border.setColorAt(0.0, Theme.BORDER_TOP)
        border.setColorAt(0.40, Theme.BORDER)
        border.setColorAt(1.0, QColor(255, 255, 255, 11))
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(border, 1))
        p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)

        # ---- 7. 内侧顶部折射高光（双层边缘的关键）----
        p.save()
        clip_top = QPainterPath()
        clip_top.addRect(QRectF(r.left(), r.top(), r.width(),
                                r.height() * 0.5))
        p.setClipPath(clip_top)
        refr = QLinearGradient(r.left(), 0, r.right(), 0)
        refr.setColorAt(0.0, QColor(255, 255, 255, 0))
        refr.setColorAt(0.18, QColor(255, 255, 255, 40))
        refr.setColorAt(0.5, QColor(255, 255, 255, 62))
        refr.setColorAt(0.82, QColor(255, 255, 255, 40))
        refr.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(refr, 1.2))
        p.drawRoundedRect(r.adjusted(1.2, 1.2, -1.2, -1.2),
                          radius - 1.2, radius - 1.2)
        p.restore()

        # ---- 8. 展开态顶部强调光带 ----
        if self._morph > 0.55:
            ga = _smoothstep(0.55, 1.0, self._morph)
            accent = QLinearGradient(r.left(), 0, r.right(), 0)
            c0 = QColor(Theme.ACCENT)
            c0.setAlpha(0)
            c1 = QColor(Theme.ACCENT)
            c1.setAlphaF(0.55 * ga)
            c2 = QColor(Theme.ACCENT_2)
            c2.setAlphaF(0.55 * ga)
            c3 = QColor(Theme.ACCENT_2)
            c3.setAlpha(0)
            accent.setColorAt(0.06, c0)
            accent.setColorAt(0.35, c1)
            accent.setColorAt(0.65, c2)
            accent.setColorAt(0.94, c3)
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(accent))
            bar_w = r.width() * 0.5 * ga
            p.drawRoundedRect(
                QRectF(r.center().x() - bar_w / 2, r.top() + 1.0, bar_w, 1.2),
                0.6, 0.6,
            )
        p.end()

    # ---------------- 鼠标 ----------------
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_off = e.globalPos() - self.frameGeometry().topLeft()
            self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._dragging and e.buttons() & Qt.LeftButton:
            self.drag_to(e.globalPos() - self._drag_off)
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if self._dragging:
            self._dragging = False
            self.setCursor(Qt.ArrowCursor)
            self.finish_drag()
        super().mouseReleaseEvent(e)

    def drag_to(self, top_left):
        S = SHADOW_MARGIN
        nx = top_left.x() + S
        ny = top_left.y() + S
        screen = self.screen().availableGeometry()
        nx = max(screen.left() - self._content_w / 2 + 40,
                 min(nx, screen.right() - self._content_w / 2 - 40))
        ny = max(screen.top() - 10, min(ny, screen.bottom() - 60))
        self._content_x = float(nx)
        self._content_y = float(ny)
        self.setGeometry(
            int(self._content_x - S), int(self._content_y - S),
            self.width(), self.height(),
        )

    def finish_drag(self):
        self.cfg["x"] = int(self._content_x)
        self.cfg["y"] = int(self._content_y)
        self.persist()

    def mouseDoubleClickEvent(self, e):
        self.reset_position()
        super().mouseDoubleClickEvent(e)

    def wheelEvent(self, e):
        # 滚轮在紧凑态下切换面板并展开
        keys = [k for k, _, _ in ExpandedView.NAV]
        try:
            idx = keys.index(self._panel_key)
        except ValueError:
            idx = 0
        idx = (idx + (1 if e.angleDelta().y() < 0 else -1)) % len(keys)
        self.show_panel(keys[idx])

    def contextMenuEvent(self, e):
        menu = QMenu(self)
        menu.setStyleSheet(
            """
            QMenu { background:#1B1B20; color:#E9EAF0; border:1px solid rgba(255,255,255,0.10);
                    border-radius:10px; padding:6px; font-family:'Microsoft YaHei UI'; font-size:9pt; }
            QMenu::item { padding:6px 22px 6px 12px; border-radius:6px; }
            QMenu::item:selected { background:rgba(110,139,255,0.28); }
            QMenu::separator { height:1px; background:rgba(255,255,255,0.08); margin:4px 8px; }
            """
        )
        act_toggle = menu.addAction("收起面板" if self._expanded else "展开面板")
        act_top = menu.addAction("回到屏幕顶部")
        menu.addSeparator()
        act_pin = menu.addAction("始终置顶")
        act_pin.setCheckable(True)
        act_pin.setChecked(self._pin_top)
        act_auto = menu.addAction("开机自启")
        act_auto.setCheckable(True)
        act_auto.setChecked(win_utils.is_autostart_enabled())
        menu.addSeparator()
        act_set = menu.addAction("设置…")
        act_shot = menu.addAction("截图")
        menu.addSeparator()
        act_quit = menu.addAction("退出")

        chosen = menu.exec_(e.globalPos())
        if chosen is None:
            return
        if chosen is act_toggle:
            self.toggle()
        elif chosen is act_top:
            self.reset_position()
        elif chosen is act_pin:
            self.set_always_on_top(act_pin.isChecked())
        elif chosen is act_auto:
            win_utils.set_autostart(act_auto.isChecked())
            self.notify("开机自启", "已开启" if act_auto.isChecked() else "已关闭")
        elif chosen is act_set:
            self.show_panel("settings")
        elif chosen is act_shot:
            path = win_utils.screenshot()
            if path:
                self.notify("截图已保存", path, "camera")
        elif chosen is act_quit:
            self.quit_app()

    # ---------------- 公共动作 ----------------
    def notify(self, title, text="", icon="check"):
        self.notify_bubble.show_message(title, text, icon, self.frameGeometry())

    def reset_position(self):
        screen = self.screen().availableGeometry()
        self._content_x = (screen.width() - self._content_w) / 2 + screen.left()
        self._content_y = float(screen.top() + 64)
        S = SHADOW_MARGIN
        self.setGeometry(
            int(self._content_x - S), int(self._content_y - S),
            self.width(), self.height(),
        )
        self.cfg["x"] = int(self._content_x)
        self.cfg["y"] = int(self._content_y)
        self.persist()

    def _keep_topmost(self):
        """把窗口提到置顶层最前，但不抢焦点。"""
        if not self._pin_top or not self.isVisible():
            return
        try:
            import ctypes

            hwnd = int(self.winId())
            HWND_TOPMOST = -1
            swp = 0x0001 | 0x0002 | 0x0010  # NOSIZE | NOMOVE | NOACTIVATE
            ctypes.windll.user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, swp)
        except Exception:
            pass

    def showEvent(self, e):
        super().showEvent(e)
        QTimer.singleShot(120, self._keep_topmost)

    def set_always_on_top(self, flag):
        self._pin_top = bool(flag)
        self.cfg["always_on_top"] = self._pin_top
        flags = self.windowFlags()
        if self._pin_top:
            flags |= Qt.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()
        self.persist()

    def apply_opacity(self, value):
        self._opacity = max(0.3, min(1.0, float(value)))
        self.update()

    def persist(self):
        save_config(self.cfg)

    def quit_app(self):
        self.cfg["x"] = int(self._content_x)
        self.cfg["y"] = int(self._content_y)
        self.persist()
        from PyQt5.QtWidgets import QApplication
        QApplication.instance().quit()


def psutil_cpu():
    try:
        import psutil
        return psutil.cpu_percent(interval=None)
    except Exception:
        return 0.0
