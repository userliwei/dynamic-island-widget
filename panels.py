# -*- coding: utf-8 -*-
"""
功能面板
--------
每个面板是一个独立 QWidget，由主窗口的 QStackedWidget 切换显示。
约定尺寸约 386 x 278。
"""

import json
import os
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime

import psutil
from PyQt5.QtCore import (
    QEasingCurve, QObject, QPointF, QRectF, Qt, QThread, QTimer,
    QVariantAnimation, pyqtSignal,
)
from PyQt5.QtGui import (
    QBrush, QColor, QFont, QLinearGradient, QPainter, QPen, QRadialGradient,
)
from PyQt5.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QSizePolicy, QSlider,
    QVBoxLayout, QWidget,
)

import win_utils
from components import (
    Bar, Dot, GradientLabel, MiniGraph, PillButton, RingProgress, draw_icon,
    safe_paint,
)
from config import Theme

WEEKDAYS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

# wttr.in 的 WW 天气代码 → 中文描述
WEATHER_ZH = {
    113: "晴", 116: "多云", 119: "阴", 122: "阴天",
    143: "薄雾", 248: "雾", 260: "冻雾",
    176: "局部有雨", 179: "局部有雪", 182: "雨夹雪", 185: "冻毛毛雨",
    200: "雷阵雨", 227: "扬雪", 230: "暴雪",
    263: "零星毛毛雨", 266: "毛毛雨", 281: "冻毛毛雨", 284: "强冻毛毛雨",
    293: "零星小雨", 296: "小雨", 299: "间歇中雨", 302: "中雨",
    305: "间歇大雨", 308: "大雨",
    311: "小冻雨", 314: "冻雨", 317: "小阵雨夹雪", 320: "阵雨夹雪",
    323: "小阵雪", 326: "小雪", 329: "中阵雪", 332: "中雪",
    335: "大阵雪", 338: "大雪", 350: "冰粒",
    353: "小阵雨", 356: "大阵雨", 359: "暴雨",
    362: "小阵雨夹雪", 365: "大阵雨夹雪",
    368: "小阵雪", 371: "大阵雪", 374: "小冰粒", 377: "大冰粒",
    386: "雷阵雨", 389: "强雷雨", 392: "雷阵雪", 395: "强雷阵雪",
}


def weather_kind(code):
    """把 WW 代码归类为图标类型。"""
    if code in (113,):
        return "clear"
    if code in (116,):
        return "partly"
    if code in (119, 122, 143):
        return "cloudy"
    if code in (248, 260):
        return "fog"
    if code in (200, 386, 389, 392, 395):
        return "thunder"
    if code in (179, 227, 230, 323, 326, 329, 332, 335, 338, 368, 371):
        return "snow"
    if code in (182, 185, 281, 284, 311, 314, 317, 320, 350, 362, 365, 374, 377):
        return "sleet"
    return "rain"


# ============================================================
#  小工具
# ============================================================
def make_label(text, size=9, color=None, bold=False, align=None):
    lb = QLabel(text)
    lb.setStyleSheet(
        "color: %s; background: transparent;" % (color or Theme.TEXT_DIM).name()
        if isinstance(color, QColor) else
        "color: %s; background: transparent;" % (color or "#9499A3")
    )
    f = QFont("Microsoft YaHei UI", size)
    if bold:
        f.setWeight(QFont.DemiBold)
    lb.setFont(f)
    if align is not None:
        lb.setAlignment(align)
    lb.setAttribute(Qt.WA_TransparentForMouseEvents)
    return lb


def hline():
    ln = QFrame()
    ln.setFixedHeight(1)
    ln.setStyleSheet("background: rgba(255,255,255,0.07); border: none;")
    return ln


def human_speed(bps):
    """字节/秒 → 可读字符串"""
    if bps < 1024:
        return f"{bps:.0f} B/s"
    if bps < 1024 * 1024:
        return f"{bps / 1024:.1f} KB/s"
    return f"{bps / 1024 / 1024:.2f} MB/s"


# ============================================================
#  开关控件
# ============================================================
class Toggle(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self.setFixedSize(40, 22)
        self.setCursor(Qt.PointingHandCursor)
        self._on = bool(checked)
        self._pos = 1.0 if checked else 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on_anim)

    def _on_anim(self, v):
        self._pos = float(v)
        self.update()

    def is_on(self):
        return self._on

    def set_on(self, flag, emit=False):
        flag = bool(flag)
        if flag == self._on:
            return
        self._on = flag
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if flag else 0.0)
        self._anim.start()
        if emit:
            self.toggled.emit(flag)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.set_on(not self._on, emit=True)

    @safe_paint
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(1, 2, -1, -2)
        rad = r.height() / 2
        p.setPen(Qt.NoPen)
        off = QColor(255, 255, 255, 34)
        on = QColor(Theme.ACCENT)
        c = QColor(
            int(off.red() + (on.red() - off.red()) * self._pos),
            int(off.green() + (on.green() - off.green()) * self._pos),
            int(off.blue() + (on.blue() - off.blue()) * self._pos),
            int(off.alpha() + (on.alpha() - off.alpha()) * self._pos),
        )
        p.setBrush(c)
        p.drawRoundedRect(r, rad, rad)
        d = r.height() - 4
        x = r.left() + 2 + self._pos * (r.width() - d - 4)
        p.setBrush(QColor(255, 255, 255))
        p.drawEllipse(QRectF(x, r.top() + 2, d, d))
        p.end()


# ============================================================
#  应用磁贴（快捷启动）
# ============================================================
# ============================================================
#  1. 时钟面板
# ============================================================
class ClockPanel(QWidget):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 12)
        lay.setSpacing(0)
        lay.addStretch(1)

        self.lb_time = GradientLabel("00:00", size=42, parent=self)
        self.lb_time.setMinimumHeight(64)
        lay.addWidget(self.lb_time)

        self.lb_sec = make_label("", 9, Theme.ACCENT, align=Qt.AlignCenter)
        lay.addWidget(self.lb_sec)

        lay.addSpacing(4)
        self.lb_date = make_label("", 10, Theme.TEXT_DIM, align=Qt.AlignCenter)
        lay.addWidget(self.lb_date)

        lay.addSpacing(12)
        self.day_bar = Bar(height=4, color=QColor(Theme.ACCENT))
        holder = QHBoxLayout()
        holder.setContentsMargins(28, 0, 28, 0)
        holder.addWidget(self.day_bar)
        lay.addLayout(holder)

        self.lb_day = make_label("", 8, Theme.TEXT_FAINT, align=Qt.AlignCenter)
        lay.addWidget(self.lb_day)

        lay.addStretch(1)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 4, 0, 0)
        bottom.addStretch(1)
        self.dot = Dot(size=9)
        bottom.addWidget(self.dot)
        bottom.addSpacing(6)
        self.lb_status = make_label("系统运行正常", 8, Theme.TEXT_DIM)
        bottom.addWidget(self.lb_status)
        bottom.addStretch(1)
        lay.addLayout(bottom)

        self.refresh()

    def refresh(self):
        now = datetime.now()
        self.lb_time.set_text(now.strftime("%H:%M"))
        self.lb_sec.setText(now.strftime("%S 秒"))
        self.lb_date.setText(
            f"{now.year}年{now.month}月{now.day}日  {WEEKDAYS[now.weekday()]}"
        )
        passed = now.hour * 3600 + now.minute * 60 + now.second
        pct = passed / 86400.0 * 100
        self.day_bar.set_value(pct)
        self.lb_day.setText(f"今日已过 {pct:.0f}%")

        cpu = psutil.cpu_percent(interval=None)
        if cpu >= 80:
            self.dot.set_color(Theme.DANGER)
            self.lb_status.setText(f"CPU 高负载 {cpu:.0f}%")
        elif cpu >= 55:
            self.dot.set_color(Theme.WARN)
            self.lb_status.setText(f"CPU 偏忙 {cpu:.0f}%")
        else:
            self.dot.set_color(Theme.OK)
            self.lb_status.setText("系统运行正常")


# ============================================================
#  2. 系统监控面板
# ============================================================
class SystemPanel(QWidget):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self._prev_net = psutil.net_io_counters()
        self._prev_time = time.time()

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)

        rings = QHBoxLayout()
        rings.setSpacing(6)
        rings.addStretch(1)
        self.r_cpu = RingProgress(size=68, thickness=5, label="CPU")
        self.r_mem = RingProgress(size=68, thickness=5, label="内存")
        self.r_disk = RingProgress(size=68, thickness=5, label="磁盘")
        for r in (self.r_cpu, self.r_mem, self.r_disk):
            rings.addWidget(r)
        rings.addStretch(1)
        lay.addLayout(rings)

        lay.addWidget(hline())

        net_row = QHBoxLayout()
        net_row.setContentsMargins(4, 0, 4, 0)
        self.lb_down = make_label("↓ 0 B/s", 9, Theme.OK)
        self.lb_up = make_label("↑ 0 B/s", 9, Theme.ACCENT_2)
        net_row.addWidget(self.lb_down)
        net_row.addStretch(1)
        net_row.addWidget(self.lb_up)
        lay.addLayout(net_row)

        self.graph = MiniGraph(height=40, color=Theme.OK,
                               max_value=8 * 1024 * 1024, auto_scale=False,
                               log_scale=True)
        self.graph.setMinimumHeight(44)
        lay.addWidget(self.graph, 1)

        extra = QHBoxLayout()
        extra.setContentsMargins(2, 0, 2, 0)
        self.lb_uptime = make_label("", 8, Theme.TEXT_FAINT)
        self.lb_proc = make_label("", 8, Theme.TEXT_FAINT)
        extra.addWidget(self.lb_uptime)
        extra.addStretch(1)
        extra.addWidget(self.lb_proc)
        lay.addLayout(extra)

        self.refresh()

    def refresh(self):
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        disk_pct = win_utils.disk_percent()

        self.r_cpu.set_value(cpu, Theme.load_color(cpu))
        self.r_mem.set_value(mem.percent, Theme.load_color(mem.percent))
        self.r_disk.set_value(disk_pct, Theme.load_color(disk_pct))

        now = time.time()
        net = psutil.net_io_counters()
        dt = max(0.001, now - self._prev_time)
        down = max(0, (net.bytes_recv - self._prev_net.bytes_recv) / dt)
        up = max(0, (net.bytes_sent - self._prev_net.bytes_sent) / dt)
        self._prev_net = net
        self._prev_time = now

        self.lb_down.setText(f"↓ {human_speed(down)}")
        self.lb_up.setText(f"↑ {human_speed(up)}")
        self.graph.push(down)

        try:
            up_sec = time.time() - psutil.boot_time()
            h = int(up_sec // 3600)
            m = int((up_sec % 3600) // 60)
            self.lb_uptime.setText(f"已开机 {h}小时{m}分")
        except Exception:
            pass
        try:
            self.lb_proc.setText(f"进程 {len(psutil.pids())}")
        except Exception:
            pass


# ============================================================
#  3. 正在播放面板（纯信息展示 + 基础播放控制）
# ============================================================
class _AppBadge(QWidget):
    """圆角渐变徽章，内含应用/媒体类型图标。"""

    def __init__(self, size=38, icon="monitor", parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.icon = icon
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def set_icon(self, icon):
        if icon != self.icon:
            self.icon = icon
            self.update()

    @safe_paint
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        grad = QLinearGradient(r.topLeft(), r.bottomRight())
        grad.setColorAt(0.0, QColor(Theme.ACCENT).lighter(118))
        grad.setColorAt(1.0, QColor(Theme.ACCENT_2))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(grad))
        p.drawRoundedRect(r, 11, 11)
        inset = r.width() * 0.24
        draw_icon(p, r.adjusted(inset, inset, -inset, -inset),
                  self.icon, QColor(255, 255, 255, 242), 1.6)
        p.end()


class NowPlayingPanel(QWidget):
    """展示当前正在播放的音乐，不做音量控制。"""

    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self._last_key = object()

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(0)

        head = QHBoxLayout()
        head.setSpacing(6)
        self.dot = Dot(size=8)
        head.addWidget(self.dot)
        self.lb_state = make_label("未在播放", 8, Theme.TEXT_DIM)
        head.addWidget(self.lb_state)
        head.addStretch(1)
        self.lb_app = make_label("", 8, Theme.TEXT_FAINT)
        head.addWidget(self.lb_app)
        lay.addLayout(head)

        lay.addStretch(1)

        self.art = _DiscWidget()
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.art)
        row.addStretch(1)
        lay.addLayout(row)

        lay.addSpacing(10)
        self.lb_title = make_label("未在播放", 13, Theme.TEXT, bold=True,
                                   align=Qt.AlignCenter)
        lay.addWidget(self.lb_title)
        lay.addSpacing(3)
        self.lb_artist = make_label("打开任意播放器即可显示", 10,
                                    QColor(160, 166, 180), align=Qt.AlignCenter)
        lay.addWidget(self.lb_artist)

        lay.addStretch(1)

        ctrl = QHBoxLayout()
        ctrl.setSpacing(14)
        ctrl.addStretch(1)
        self.btn_prev = PillButton("prev", w=40, h=32, radius=12)
        self.btn_play = PillButton("play", w=52, h=40, radius=20, filled=True)
        self.btn_next = PillButton("next", w=40, h=32, radius=12)
        ctrl.addWidget(self.btn_prev)
        ctrl.addWidget(self.btn_play)
        ctrl.addWidget(self.btn_next)
        ctrl.addStretch(1)
        lay.addLayout(ctrl)

        self.btn_prev.clicked.connect(self._prev)
        self.btn_next.clicked.connect(self._next)
        self.btn_play.clicked.connect(self._toggle)

        self.refresh()

    @staticmethod
    def _elide(text, limit):
        text = (text or "").strip()
        if len(text) <= limit:
            return text
        return text[: max(1, limit - 1)] + "…"

    def _toggle(self):
        win_utils.media_play_pause()
        QTimer.singleShot(450, self.refresh)

    def _prev(self):
        win_utils.media_prev()
        QTimer.singleShot(450, self.refresh)

    def _next(self):
        win_utils.media_next()
        QTimer.singleShot(450, self.refresh)

    def _render_idle(self):
        self.lb_state.setText("未在播放")
        self.lb_app.setText("")
        self.lb_title.setText("未在播放")
        self.lb_artist.setText("打开任意播放器即可显示")
        self.dot.set_color(Theme.TEXT_FAINT)
        self.art.set_spinning(False)
        self.btn_play.icon = "play"
        self.btn_play.update()

    def refresh(self):
        try:
            info = win_utils.get_now_playing()
        except Exception:
            info = None

        if not info:
            if self._last_key is None:
                return
            self._last_key = None
            self._render_idle()
            return

        key = (info.get("title"), info.get("artist"),
               info.get("playing"), info.get("app"))
        if key == self._last_key:
            return
        self._last_key = key

        self.lb_app.setText(info.get("app", ""))
        self.lb_title.setText(self._elide(info.get("title"), 17))
        self.lb_artist.setText(self._elide(info.get("artist"), 24) or "未知歌手")
        playing = bool(info.get("playing"))
        self.lb_state.setText("正在播放" if playing else "已暂停")
        self.dot.set_color(Theme.OK if playing else Theme.WARN)
        self.art.set_spinning(playing)
        self.btn_play.icon = "pause" if playing else "play"
        self.btn_play.update()


class _DiscWidget(QWidget):
    """旋转唱片视觉元素。"""

    def __init__(self, parent=None, size=76):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._angle = 0.0
        self._spinning = False
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(40)

    def set_spinning(self, flag):
        self._spinning = flag

    def _tick(self):
        if self._spinning:
            self._angle = (self._angle + 2.0) % 360
            self.update()

    @safe_paint
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(3, 3, -3, -3)

        grad = QRadialGradient(r.center(), r.width() / 2)
        c1 = QColor(Theme.ACCENT)
        c1.setAlpha(70)
        c2 = QColor(Theme.ACCENT_2)
        c2.setAlpha(20)
        grad.setColorAt(0.0, c1)
        grad.setColorAt(1.0, c2)
        p.setPen(Qt.NoPen)
        p.setBrush(grad)
        p.drawEllipse(r)

        p.save()
        p.translate(r.center())
        p.rotate(self._angle)
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        for i in range(3):
            p.drawEllipse(QRectF(-r.width() * (0.22 + i * 0.11),
                                 -r.width() * (0.22 + i * 0.11),
                                 r.width() * 2 * (0.22 + i * 0.11),
                                 r.width() * 2 * (0.22 + i * 0.11)))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 200))
        p.drawEllipse(QRectF(-3, -3, 6, 6))
        p.restore()

        draw_icon(p, QRectF(r.center().x() - 9, r.center().y() - 9, 18, 18),
                  "music", QColor(255, 255, 255, 120), 1.4)
        p.end()


# ============================================================
#  4. 工作状态面板（当前在做什么 + 专注计时）
# ============================================================
_APP_ICON_RULES = (
    (("chrome", "msedge", "firefox", "brave", "opera", "360se"), "browser"),
    (("terminal", "powershell", "cmd", "conhost", "windowsterminal",
      "wt"), "terminal"),
    (("code", "devenv", "pycharm", "idea", "sublime", "notepad"), "terminal"),
    (("explorer",), "folder"),
    (("winword", "excel", "powerpnt", "wps", "acrobat", "sumatrapdf"),
     "grid"),
    (("spotify", "cloudmusic", "qqmusic", "kugou", "foobar", "musicbee"),
     "music"),
    (("photoshop", "illustrator", "figma", "blender", "cad", "revit"),
     "grid"),
    (("wechat", "weixin", "qq", "telegram", "discord", "dingtalk"), "cloud"),
)


_PROC_NAME_ZH = {
    "explorer": "资源管理器", "chrome": "Chrome", "msedge": "Edge",
    "firefox": "Firefox", "brave": "Brave", "code": "VS Code",
    "devenv": "Visual Studio", "pycharm64": "PyCharm",
    "pycharm": "PyCharm", "idea64": "IntelliJ", "notepad": "记事本",
    "notepad++": "Notepad++", "powershell": "PowerShell",
    "windowsterminal": "终端", "cmd": "命令提示符",
    "conhost": "控制台", "winword": "Word", "excel": "Excel",
    "powerpnt": "PowerPoint", "wps": "WPS", "acrobat": "Acrobat",
    "spotify": "Spotify", "cloudmusic": "网易云音乐",
    "qqmusic": "QQ音乐", "kugou": "酷狗音乐", "weixin": "微信",
    "wechat": "微信", "qq": "QQ", "dingtalk": "钉钉",
    "telegram": "Telegram", "discord": "Discord",
    "photoshop": "Photoshop", "illustrator": "Illustrator",
    "figma": "Figma", "blender": "Blender", "taskmgr": "任务管理器",
    "systemsettings": "系统设置", "applicationframehost": "系统设置",
    "shellexperiencehost": "桌面", "searchapp": "搜索",
    "pythonw": "灵动岛", "python": "Python",
}


def friendly_app_name(exe):
    stem = os.path.splitext(exe or "")[0]
    low = stem.lower()
    if low in _PROC_NAME_ZH:
        return _PROC_NAME_ZH[low]
    return stem if stem else "桌面"


def app_icon_for(exe):
    low = (exe or "").lower()
    for keys, icon in _APP_ICON_RULES:
        for k in keys:
            if k in low:
                return icon
    return "monitor"


class WorkStatusPanel(QWidget):
    """展示当前活动窗口，并提供专注计时。"""

    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.focus_min = int(app.cfg.get("focus_minutes", 25))
        self.remaining = self.focus_min * 60
        self.running = False
        self.today_seconds = 0
        self._last_win = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(0)

        lay.addWidget(make_label("当前窗口", 8, Theme.TEXT_FAINT))
        lay.addSpacing(7)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.badge = _AppBadge(size=38, icon="monitor")
        row.addWidget(self.badge)
        col = QVBoxLayout()
        col.setSpacing(1)
        self.lb_app = make_label("—", 10, Theme.TEXT, bold=True)
        self.lb_title = make_label("正在识别…", 8, Theme.TEXT_FAINT)
        col.addWidget(self.lb_app)
        col.addWidget(self.lb_title)
        row.addLayout(col, 1)
        lay.addLayout(row)

        lay.addSpacing(10)
        lay.addWidget(hline())
        lay.addSpacing(8)

        self.ring = RingProgress(size=112, thickness=6, label="专注")
        self.ring.show_value = False
        self.ring.set_value(0, Theme.ACCENT)
        holder = QHBoxLayout()
        holder.addStretch(1)
        holder.addWidget(self.ring)
        holder.addStretch(1)
        lay.addLayout(holder)

        lay.addSpacing(4)
        self.lb_today = make_label("今日专注 0 分钟", 8, Theme.TEXT_FAINT,
                                   align=Qt.AlignCenter)
        lay.addWidget(self.lb_today)

        lay.addSpacing(8)
        ctrl = QHBoxLayout()
        ctrl.setSpacing(10)
        ctrl.addStretch(1)
        self.btn_start = PillButton(text="开始专注", w=92, h=28, radius=14,
                                    filled=True)
        self.btn_reset = PillButton("refresh", w=34, h=28, radius=14)
        ctrl.addWidget(self.btn_start)
        ctrl.addWidget(self.btn_reset)
        ctrl.addStretch(1)
        lay.addLayout(ctrl)

        self.btn_start.clicked.connect(self._toggle)
        self.btn_reset.clicked.connect(self._reset)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self._render()

    # ---- 当前窗口 ----
    def refresh(self):
        try:
            exe, title = win_utils.get_foreground_app()
        except Exception:
            exe, title = ("", "")
        key = (exe, title)
        if key == self._last_win:
            return
        self._last_win = key
        self.lb_app.setText(friendly_app_name(exe))
        short = (title or "").strip()
        if len(short) > 28:
            short = short[:27] + "…"
        self.lb_title.setText(short or "—")
        self.badge.set_icon(app_icon_for(exe))

    # ---- 专注计时 ----
    def _toggle(self):
        if self.running:
            self.running = False
            self.timer.stop()
            self.btn_start.text = "继续"
            self.btn_start.update()
        else:
            self.running = True
            self.timer.start(1000)
            self.btn_start.text = "暂停"
            self.btn_start.update()

    def _reset(self):
        self.running = False
        self.timer.stop()
        self.remaining = self.focus_min * 60
        self.btn_start.text = "开始专注"
        self.btn_start.update()
        self._render()

    def _tick(self):
        if not self.running:
            return
        self.remaining -= 1
        self.today_seconds += 1
        if self.remaining <= 0:
            self.running = False
            self.timer.stop()
            self.btn_start.text = "开始专注"
            self.btn_start.update()
            self.app.notify("专注完成", "这一轮结束了，休息一下 ☕", "timer")
            self._reset()
            return
        self._render()

    def _render(self):
        total = max(1, self.focus_min * 60)
        pct = (1 - self.remaining / total) * 100
        self.ring.color = Theme.ACCENT
        self.ring.text = "%02d:%02d" % (self.remaining // 60,
                                        self.remaining % 60)
        self.ring.label = "专注中" if self.running else "待开始"
        self.ring.set_value(pct, Theme.ACCENT)
        self.lb_today.setText(
            "今日专注 %d 分钟" % (self.today_seconds // 60)
        )


class _WeatherFetcher(QObject):
    """天气请求器。

    用 threading.Thread（daemon）+ Qt 信号回主线程，
    避开 QThread 对象被回收时“Destroyed while running”导致的硬崩溃。
    """

    done = pyqtSignal(dict)
    fail = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._busy = False

    def is_busy(self):
        return self._busy

    def fetch(self, city):
        if self._busy:
            return
        self._busy = True
        threading.Thread(
            target=self._run, args=(city,), daemon=True
        ).start()

    def _run(self, city):
        try:
            q = urllib.parse.quote(city) if city else ""
            url = f"https://wttr.in/{q}?format=j1&lang=zh"
            req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8", "ignore"))
            self.done.emit(data)
        except Exception as exc:
            self.fail.emit(str(exc))
        finally:
            self._busy = False


class WeatherPanel(QWidget):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self._fetcher = _WeatherFetcher(self)
        self._fetcher.done.connect(self._on_data)
        self._fetcher.fail.connect(self._on_fail)
        self._loaded = False
        self._city_query = "Chengdu"
        self._city_display = "成都"

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(6)

        head = QHBoxLayout()
        self.lb_city = make_label("成都", 10, Theme.TEXT, bold=True)
        head.addWidget(self.lb_city)
        head.addStretch(1)
        self.btn_refresh = PillButton("refresh", w=28, h=26, radius=8)
        self.btn_refresh.clicked.connect(self.refresh)
        head.addWidget(self.btn_refresh)
        lay.addLayout(head)

        self.icon_widget = _WeatherIcon()
        h2 = QHBoxLayout()
        h2.addStretch(1)
        h2.addWidget(self.icon_widget)
        h2.addSpacing(12)
        col = QVBoxLayout()
        col.setSpacing(0)
        self.lb_temp = make_label("--°", 30, Theme.TEXT, bold=True)
        self.lb_desc = make_label("正在获取…", 9, Theme.TEXT_DIM)
        col.addWidget(self.lb_temp)
        col.addWidget(self.lb_desc)
        h2.addLayout(col)
        h2.addStretch(1)

        lay.addStretch(1)
        lay.addLayout(h2)
        lay.addStretch(1)
        lay.addWidget(hline())

        self.lb_detail = make_label("", 8, Theme.TEXT_FAINT, align=Qt.AlignCenter)
        lay.addWidget(self.lb_detail)
        self.lb_hint = make_label("", 7, Theme.TEXT_FAINT, align=Qt.AlignCenter)
        lay.addWidget(self.lb_hint)

    def showEvent(self, e):
        super().showEvent(e)
        if not self._loaded:
            self.refresh()

    def set_city(self, city):
        self._city_query = city or ""
        self._city_display = city or "自动定位"
        self.lb_city.setText(self._city_display)
        self.refresh()

    def refresh(self):
        if self._fetcher.is_busy():
            return
        self.lb_desc.setText("正在获取…")
        self.lb_hint.setText("")
        self._fetcher.fetch(self._city_query)

    def _on_data(self, data):
        try:
            cur = data["current_condition"][0]
            area = data["nearest_area"][0]
            name = area["areaName"][0]["value"]
            region = area["region"][0]["value"]
            self.lb_city.setText(f"{name} · {region}" if region else name)
            self.lb_temp.setText(f"{cur['temp_C']}°")

            code = int(cur.get("weatherCode", "113"))
            desc = WEATHER_ZH.get(code, "")
            if not desc:
                raw = cur.get("weatherDesc")
                if isinstance(raw, list) and raw:
                    desc = raw[0].get("value", "")
                else:
                    desc = str(raw or "")
            self.lb_desc.setText(desc)

            feels = cur.get("FeelsLikeC", "-")
            hum = cur.get("humidity", "-")
            wind = cur.get("windspeedKmph", "-")
            self.lb_detail.setText(
                f"体感 {feels}°    湿度 {hum}%    风速 {wind} km/h"
            )
            self.icon_widget.set_code(code)
            self.lb_hint.setText("数据来源 wttr.in")
            self._loaded = True
        except Exception as exc:
            self._on_fail(str(exc))

    def _on_fail(self, msg):
        self.lb_temp.setText("--°")
        self.lb_desc.setText("获取失败")
        self.lb_detail.setText("")
        self.lb_hint.setText("检查网络后点右上角刷新")
        self._loaded = False


class _WeatherIcon(QWidget):
    """根据天气类型绘制的圆形天气图标。"""

    def __init__(self, parent=None, size=68):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.code = 116
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def set_code(self, code):
        self.code = code
        self.update()

    @safe_paint
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        kind = weather_kind(self.code)

        # 背景光晕（按天气类型给色调）
        palettes = {
            "clear": ((255, 214, 120), (255, 166, 58)),
            "partly": ((255, 205, 120), (150, 180, 255)),
            "cloudy": ((176, 186, 205), (122, 132, 152)),
            "fog": ((178, 188, 204), (130, 140, 158)),
            "rain": ((130, 176, 255), (86, 128, 220)),
            "sleet": ((154, 186, 240), (110, 144, 208)),
            "snow": ((200, 224, 255), (150, 186, 240)),
            "thunder": ((255, 206, 108), (140, 140, 220)),
        }
        c1, c2 = palettes.get(kind, ((176, 186, 205), (122, 132, 152)))
        grad = QRadialGradient(r.center(), r.width() / 2)
        grad.setColorAt(0.0, QColor(c1[0], c1[1], c1[2], 90))
        grad.setColorAt(1.0, QColor(c2[0], c2[1], c2[2], 22))
        p.setPen(QPen(QColor(255, 255, 255, 26), 1))
        p.setBrush(QBrush(grad))
        p.drawEllipse(r)

        white = QColor(255, 255, 255, 236)
        warm = QColor(255, 214, 120, 240)
        inner = r.adjusted(r.width() * 0.19, r.height() * 0.19,
                           -r.width() * 0.19, -r.height() * 0.19)

        if kind == "clear":
            draw_icon(p, inner, "sun", warm, 2.0)

        elif kind == "partly":
            # 小太阳 + 云
            sun_r = QRectF(inner.left() + inner.width() * 0.34,
                           inner.top(), inner.width() * 0.66,
                           inner.height() * 0.66)
            draw_icon(p, sun_r, "sun", warm, 1.8)
            cloud_r = QRectF(inner.left(), inner.top() + inner.height() * 0.34,
                             inner.width() * 0.8, inner.height() * 0.66)
            draw_icon(p, cloud_r, "cloud", white, 2.0)

        elif kind == "cloudy":
            big = r.adjusted(r.width() * 0.13, r.height() * 0.22,
                             -r.width() * 0.13, -r.height() * 0.22)
            draw_icon(p, big, "cloud", white, 2.0)

        elif kind == "fog":
            for i, w in enumerate((1.0, 0.78, 0.9, 0.62)):
                y = inner.top() + inner.height() * (0.18 + i * 0.22)
                x0 = inner.left() + inner.width() * (1 - w) / 2
                p.setPen(QPen(white, 2.0))
                p.drawLine(QPointF(x0, y),
                           QPointF(x0 + inner.width() * w, y))

        else:
            # 云体 + 下方降水符号
            cloud_r = QRectF(inner.left(), inner.top(),
                             inner.width(), inner.height() * 0.66)
            draw_icon(p, cloud_r, "cloud", white, 2.0)

            if kind == "rain":
                for i in range(3):
                    x = inner.left() + inner.width() * (0.28 + i * 0.22)
                    p.setPen(QPen(QColor(130, 186, 255, 240), 2.0))
                    p.drawLine(QPointF(x, inner.top() + inner.height() * 0.7),
                               QPointF(x - inner.width() * 0.06,
                                       inner.top() + inner.height() * 0.95))
            elif kind == "sleet":
                for i in range(3):
                    x = inner.left() + inner.width() * (0.28 + i * 0.22)
                    p.setPen(QPen(QColor(150, 196, 255, 240), 2.0))
                    if i % 2 == 0:
                        p.drawLine(QPointF(x, inner.top() + inner.height() * 0.7),
                                   QPointF(x - inner.width() * 0.06,
                                           inner.top() + inner.height() * 0.93))
                    else:
                        p.drawPoint(QPointF(x, inner.top() + inner.height() * 0.84))
            elif kind == "snow":
                import math
                for i in range(3):
                    cx = inner.left() + inner.width() * (0.28 + i * 0.22)
                    cy = inner.top() + inner.height() * 0.84
                    p.setPen(QPen(QColor(220, 238, 255, 245), 1.5))
                    for k in range(3):
                        a = k * math.pi / 3
                        dx = math.cos(a) * inner.width() * 0.07
                        dy = math.sin(a) * inner.width() * 0.07
                        p.drawLine(QPointF(cx - dx, cy - dy),
                                   QPointF(cx + dx, cy + dy))
            elif kind == "thunder":
                bolt_r = QRectF(inner.left() + inner.width() * 0.3,
                                inner.top() + inner.height() * 0.55,
                                inner.width() * 0.4, inner.height() * 0.45)
                draw_icon(p, bolt_r, "bolt", QColor(255, 214, 90, 245), 1.8)

        p.end()


# ============================================================
#  7. 设置面板
# ============================================================
class SettingsPanel(QWidget):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 10)
        lay.setSpacing(4)

        lay.addWidget(make_label("设置", 10, Theme.TEXT, bold=True))
        lay.addSpacing(4)

        # 置顶
        lay.addLayout(self._row(
            "始终置顶", "窗口保持在所有程序之上",
            Toggle(app.cfg.get("always_on_top", True), parent=self),
            self._on_top,
        ))
        # 开机自启
        lay.addLayout(self._row(
            "开机自启", "登录 Windows 后自动运行",
            Toggle(win_utils.is_autostart_enabled(), parent=self),
            self._on_autostart,
        ))

        # 透明度
        lay.addSpacing(2)
        lay.addWidget(make_label("面板不透明度", 8, Theme.TEXT_DIM))
        srow = QHBoxLayout()
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(60, 100)
        self.slider.setValue(int(app.cfg.get("opacity", 0.96) * 100))
        self.slider.setStyleSheet(
            """
            QSlider::groove:horizontal { height:4px; background:rgba(255,255,255,0.14);
                border-radius:2px; }
            QSlider::sub-page:horizontal { background:#6E8BFF; border-radius:2px; }
            QSlider::handle:horizontal { width:12px; height:12px; margin:-5px 0;
                border-radius:6px; background:#fff; }
            """
        )
        self.slider.valueChanged.connect(self._on_opacity)
        srow.addWidget(self.slider, 1)
        lay.addLayout(srow)

        lay.addStretch(1)
        lay.addWidget(hline())
        lay.addSpacing(4)

        btns = QHBoxLayout()
        btns.setSpacing(8)
        b_reset = PillButton("monitor", "回到顶部", w=104, h=30, radius=15)
        b_reset.clicked.connect(self.app.reset_position)
        b_quit = PillButton("power", "退出", w=76, h=30, radius=15)
        b_quit.clicked.connect(self.app.quit_app)
        btns.addWidget(b_reset)
        btns.addStretch(1)
        btns.addWidget(b_quit)
        lay.addLayout(btns)

        lay.addWidget(make_label(
            "拖动胶囊可移动位置 · 右键打开菜单", 7, Theme.TEXT_FAINT,
            align=Qt.AlignCenter))

    def _row(self, title, sub, toggle, handler):
        row = QHBoxLayout()
        row.setContentsMargins(0, 4, 0, 4)
        col = QVBoxLayout()
        col.setSpacing(0)
        col.addWidget(make_label(title, 9, Theme.TEXT))
        col.addWidget(make_label(sub, 7, Theme.TEXT_FAINT))
        row.addLayout(col)
        row.addStretch(1)
        toggle.toggled.connect(handler)
        row.addWidget(toggle)
        return row

    def _on_top(self, flag):
        self.app.set_always_on_top(flag)

    def _on_autostart(self, flag):
        ok = win_utils.set_autostart(flag)
        self.app.cfg["autostart"] = flag
        self.app.persist()
        self.app.notify(
            "开机自启", "已开启" if flag else "已关闭",
            "check" if ok else "power",
        )

    def _on_opacity(self, value):
        self.app.cfg["opacity"] = value / 100.0
        self.app.apply_opacity(value / 100.0)
        self.app.persist()
