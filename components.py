# -*- coding: utf-8 -*-
"""
通用 UI 组件
------------
全部基于 QPainter 手绘，不依赖任何图片/字体图标资源。
"""

import functools
import traceback
from collections import deque

from PyQt5.QtCore import (
    QEasingCurve, QPointF, QRectF, Qt, QTimer, QVariantAnimation, pyqtSignal,
)
from PyQt5.QtGui import (
    QBrush, QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath,
    QPen, QPixmap, QRadialGradient,
)
from PyQt5.QtWidgets import QSizePolicy, QWidget

from config import Theme


# ============================================================
#  磨砂噪点纹理（玻璃质感）
# ============================================================
_noise_cache = None


def noise_pixmap(size=64, alpha_max=3):
    """生成一次磨砂噪点纹理并缓存，用于叠加在玻璃背景上。"""
    global _noise_cache
    if _noise_cache is not None:
        return _noise_cache
    import random

    img = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    rnd = random.Random(20251101)   # 固定种子，纹理稳定
    for y in range(size):
        for x in range(size):
            v = rnd.randint(150, 255)
            a = rnd.randint(0, alpha_max)
            img.setPixelColor(x, y, QColor(v, v, v, a))
    _noise_cache = QPixmap.fromImage(img)
    return _noise_cache


# ============================================================
#  绘制异常保护
# ============================================================
def safe_paint(fn):
    """包装 paintEvent：任何绘制异常都只记录，绝不让它穿越 Qt C++ 边界。

    PyQt5 中槽函数/虚函数里未捕获的异常会触发 qFatal 直接终止进程，
    这对常驻桌面组件是致命的，所以统一在此兜底。
    """
    @functools.wraps(fn)
    def wrapper(self, e):
        try:
            return fn(self, e)
        except Exception:
            traceback.print_exc()
        return None
    return wrapper


# ============================================================
#  渐变文字（大字时间等）
# ============================================================
class GradientLabel(QWidget):
    """垂直渐变填充的大号文字，自带字距收紧效果。"""

    def __init__(self, text="", size=44, top=None, bottom=None, parent=None):
        super().__init__(parent)
        self._text = text
        self._size = size
        self.c_top = top or QColor(255, 255, 255)
        self.c_bot = bottom or QColor(178, 185, 200)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        fm = self.fontMetrics()
        self.setMinimumHeight(int(size * 1.45))

    def set_text(self, text):
        if text != self._text:
            self._text = text
            self.update()

    @safe_paint
    def paintEvent(self, e):
        if not self._text:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)

        f = QFont("Microsoft YaHei UI", self._size, QFont.DemiBold)
        f.setLetterSpacing(QFont.PercentageSpacing, 98)

        path = QPainterPath()
        path.addText(0, 0, f, self._text)
        br = path.boundingRect()
        r = QRectF(self.rect())
        path.translate(
            r.center().x() - br.center().x(),
            r.center().y() - br.center().y(),
        )

        grad = QLinearGradient(r.top(), 0, r.bottom(), 0)
        grad.setColorAt(0.0, self.c_top)
        grad.setColorAt(0.72, self.c_bot)
        grad.setColorAt(1.0, self.c_bot)
        p.setPen(Qt.NoPen)
        p.fillPath(path, QBrush(grad))
        p.end()


# ============================================================
#  图标绘制（0..1 归一化坐标 → 实际矩形）
# ============================================================
def _p(r, x, y):
    return QPointF(r.left() + x * r.width(), r.top() + y * r.height())


def draw_icon(p, rect, name, color, lw=1.6):
    """在 rect 内绘制名为 name 的线性图标。"""
    r = QRectF(rect)
    if r.width() <= 0 or r.height() <= 0:
        return
    p.save()
    p.setRenderHint(QPainter.Antialiasing, True)
    pen = QPen(color, lw)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    if name == "clock":
        p.drawEllipse(r.adjusted(0.08 * r.width(), 0.08 * r.height(),
                                 -0.08 * r.width(), -0.08 * r.height()))
        p.drawLine(_p(r, 0.5, 0.5), _p(r, 0.5, 0.26))
        p.drawLine(_p(r, 0.5, 0.5), _p(r, 0.68, 0.6))

    elif name == "cpu":
        inner = r.adjusted(0.24 * r.width(), 0.24 * r.height(),
                           -0.24 * r.width(), -0.24 * r.height())
        p.drawRoundedRect(inner, 2, 2)
        for t in (0.34, 0.5, 0.66):
            p.drawLine(_p(r, t, 0.0), _p(r, t, 0.2))
            p.drawLine(_p(r, t, 0.8), _p(r, t, 1.0))
            p.drawLine(_p(r, 0.0, t), _p(r, 0.2, t))
            p.drawLine(_p(r, 0.8, t), _p(r, 1.0, t))

    elif name == "music":
        p.drawLine(_p(r, 0.62, 0.62), _p(r, 0.62, 0.14))
        p.drawLine(_p(r, 0.62, 0.14), _p(r, 0.9, 0.22))
        p.drawEllipse(_p(r, 0.44, 0.66), 0.18 * r.width(), 0.15 * r.height())

    elif name == "bolt":
        path = QPainterPath()
        path.moveTo(_p(r, 0.56, 0.04))
        path.lineTo(_p(r, 0.2, 0.56))
        path.lineTo(_p(r, 0.46, 0.56))
        path.lineTo(_p(r, 0.4, 0.96))
        path.lineTo(_p(r, 0.8, 0.42))
        path.lineTo(_p(r, 0.52, 0.42))
        path.lineTo(_p(r, 0.62, 0.04))
        path.closeSubpath()
        p.drawPath(path)

    elif name == "timer":
        p.drawArc(QRectF(r.left() + 0.1 * r.width(), r.top() + 0.18 * r.height(),
                         0.8 * r.width(), 0.8 * r.height()), 40 * 16, 280 * 16)
        p.drawLine(_p(r, 0.5, 0.18), _p(r, 0.5, 0.5))
        p.drawLine(_p(r, 0.38, 0.03), _p(r, 0.62, 0.03))

    elif name == "cloud":
        path = QPainterPath()
        path.addRoundedRect(
            QRectF(r.left() + 0.16 * r.width(), r.top() + 0.46 * r.height(),
                   0.68 * r.width(), 0.26 * r.height()),
            0.12 * r.width(), 0.12 * r.width(),
        )
        path.addEllipse(
            QPointF(r.left() + 0.33 * r.width(), r.top() + 0.52 * r.height()),
            0.17 * r.width(), 0.17 * r.height(),
        )
        path.addEllipse(
            QPointF(r.left() + 0.54 * r.width(), r.top() + 0.42 * r.height()),
            0.23 * r.width(), 0.23 * r.height(),
        )
        path.addEllipse(
            QPointF(r.left() + 0.73 * r.width(), r.top() + 0.54 * r.height()),
            0.15 * r.width(), 0.15 * r.height(),
        )
        p.setBrush(QBrush(color))
        p.setPen(Qt.NoPen)
        p.drawPath(path.simplified())

    elif name == "gear":
        import math
        cx, cy = r.center().x(), r.center().y()
        # 齿
        for i in range(8):
            a = i * math.pi / 4 + math.pi / 8
            p.drawLine(
                QPointF(cx + math.cos(a) * 0.33 * r.width(),
                        cy + math.sin(a) * 0.33 * r.height()),
                QPointF(cx + math.cos(a) * 0.46 * r.width(),
                        cy + math.sin(a) * 0.46 * r.height()),
            )
        # 外圈
        p.drawEllipse(QRectF(cx - 0.32 * r.width(), cy - 0.32 * r.height(),
                             0.64 * r.width(), 0.64 * r.height()))
        # 中心孔
        p.drawEllipse(QRectF(cx - 0.12 * r.width(), cy - 0.12 * r.height(),
                             0.24 * r.width(), 0.24 * r.height()))

    elif name == "play":
        path = QPainterPath()
        path.moveTo(_p(r, 0.34, 0.18))
        path.lineTo(_p(r, 0.82, 0.5))
        path.lineTo(_p(r, 0.34, 0.82))
        path.closeSubpath()
        p.setBrush(QBrush(color))
        p.drawPath(path)

    elif name == "pause":
        p.setBrush(QBrush(color))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(r.left() + 0.3 * r.width(), r.top() + 0.2 * r.height(),
                                 0.14 * r.width(), 0.6 * r.height()), 1, 1)
        p.drawRoundedRect(QRectF(r.left() + 0.56 * r.width(), r.top() + 0.2 * r.height(),
                                 0.14 * r.width(), 0.6 * r.height()), 1, 1)

    elif name == "next":
        p.setBrush(QBrush(color))
        p.setPen(Qt.NoPen)
        path = QPainterPath()
        path.moveTo(_p(r, 0.28, 0.22))
        path.lineTo(_p(r, 0.66, 0.5))
        path.lineTo(_p(r, 0.28, 0.78))
        path.closeSubpath()
        p.drawPath(path)
        p.drawRoundedRect(QRectF(r.left() + 0.68 * r.width(), r.top() + 0.22 * r.height(),
                                 0.1 * r.width(), 0.56 * r.height()), 1, 1)

    elif name == "prev":
        p.setBrush(QBrush(color))
        p.setPen(Qt.NoPen)
        path = QPainterPath()
        path.moveTo(_p(r, 0.72, 0.22))
        path.lineTo(_p(r, 0.34, 0.5))
        path.lineTo(_p(r, 0.72, 0.78))
        path.closeSubpath()
        p.drawPath(path)
        p.drawRoundedRect(QRectF(r.left() + 0.22 * r.width(), r.top() + 0.22 * r.height(),
                                 0.1 * r.width(), 0.56 * r.height()), 1, 1)

    elif name == "volume":
        path = QPainterPath()
        path.moveTo(_p(r, 0.12, 0.38))
        path.lineTo(_p(r, 0.3, 0.38))
        path.lineTo(_p(r, 0.5, 0.2))
        path.lineTo(_p(r, 0.5, 0.8))
        path.lineTo(_p(r, 0.3, 0.62))
        path.lineTo(_p(r, 0.12, 0.62))
        path.closeSubpath()
        p.drawPath(path)
        p.drawArc(QRectF(r.left() + 0.42 * r.width(), r.top() + 0.3 * r.height(),
                         0.3 * r.width(), 0.4 * r.height()), -60 * 16, 120 * 16)

    elif name == "mute":
        path = QPainterPath()
        path.moveTo(_p(r, 0.12, 0.38))
        path.lineTo(_p(r, 0.3, 0.38))
        path.lineTo(_p(r, 0.5, 0.2))
        path.lineTo(_p(r, 0.5, 0.8))
        path.lineTo(_p(r, 0.3, 0.62))
        path.lineTo(_p(r, 0.12, 0.62))
        path.closeSubpath()
        p.drawPath(path)
        p.drawLine(_p(r, 0.62, 0.36), _p(r, 0.88, 0.64))
        p.drawLine(_p(r, 0.88, 0.36), _p(r, 0.62, 0.64))

    elif name == "lock":
        p.drawRoundedRect(QRectF(r.left() + 0.22 * r.width(), r.top() + 0.46 * r.height(),
                                 0.56 * r.width(), 0.42 * r.height()), 2, 2)
        p.drawArc(QRectF(r.left() + 0.32 * r.width(), r.top() + 0.14 * r.height(),
                         0.36 * r.width(), 0.44 * r.height()), 0, 180 * 16)

    elif name == "camera":
        p.drawRoundedRect(QRectF(r.left() + 0.1 * r.width(), r.top() + 0.3 * r.height(),
                                 0.8 * r.width(), 0.52 * r.height()), 2, 2)
        p.drawEllipse(QPointF(r.center().x(), r.top() + 0.56 * r.height()),
                      0.15 * r.width(), 0.15 * r.width())
        p.drawLine(_p(r, 0.36, 0.3), _p(r, 0.42, 0.18))
        p.drawLine(_p(r, 0.58, 0.3), _p(r, 0.64, 0.18))

    elif name == "trash":
        p.drawLine(_p(r, 0.16, 0.26), _p(r, 0.84, 0.26))
        p.drawLine(_p(r, 0.4, 0.26), _p(r, 0.42, 0.14))
        p.drawLine(_p(r, 0.6, 0.26), _p(r, 0.58, 0.14))
        path = QPainterPath()
        path.moveTo(_p(r, 0.24, 0.32))
        path.lineTo(_p(r, 0.3, 0.88))
        path.lineTo(_p(r, 0.7, 0.88))
        path.lineTo(_p(r, 0.76, 0.32))
        p.drawPath(path)

    elif name == "folder":
        path = QPainterPath()
        path.moveTo(_p(r, 0.1, 0.3))
        path.lineTo(_p(r, 0.42, 0.3))
        path.lineTo(_p(r, 0.5, 0.42))
        path.lineTo(_p(r, 0.9, 0.42))
        path.lineTo(_p(r, 0.9, 0.8))
        path.lineTo(_p(r, 0.1, 0.8))
        path.closeSubpath()
        p.drawPath(path)

    elif name == "refresh":
        p.drawArc(QRectF(r.left() + 0.14 * r.width(), r.top() + 0.14 * r.height(),
                         0.72 * r.width(), 0.72 * r.height()), 60 * 16, 260 * 16)
        p.drawLine(_p(r, 0.82, 0.14), _p(r, 0.84, 0.38))
        p.drawLine(_p(r, 0.82, 0.14), _p(r, 0.6, 0.2))

    elif name == "power":
        p.drawArc(QRectF(r.left() + 0.14 * r.width(), r.top() + 0.2 * r.height(),
                         0.72 * r.width(), 0.72 * r.height()), 50 * 16, 260 * 16)
        p.drawLine(_p(r, 0.5, 0.08), _p(r, 0.5, 0.46))

    elif name == "sun":
        p.drawEllipse(QPointF(r.center().x(), r.center().y()),
                      0.2 * r.width(), 0.2 * r.width())
        import math
        for i in range(8):
            a = i * math.pi / 4
            p.drawLine(
                QPointF(r.center().x() + math.cos(a) * 0.3 * r.width(),
                        r.center().y() + math.sin(a) * 0.3 * r.height()),
                QPointF(r.center().x() + math.cos(a) * 0.44 * r.width(),
                        r.center().y() + math.sin(a) * 0.44 * r.height()),
            )

    elif name == "check":
        p.drawLine(_p(r, 0.2, 0.52), _p(r, 0.42, 0.74))
        p.drawLine(_p(r, 0.42, 0.74), _p(r, 0.82, 0.26))

    elif name == "plus":
        p.drawLine(_p(r, 0.5, 0.2), _p(r, 0.5, 0.8))
        p.drawLine(_p(r, 0.2, 0.5), _p(r, 0.8, 0.5))

    elif name == "minus":
        p.drawLine(_p(r, 0.2, 0.5), _p(r, 0.8, 0.5))

    elif name == "terminal":
        p.drawRoundedRect(QRectF(r.left() + 0.06 * r.width(), r.top() + 0.16 * r.height(),
                                 0.88 * r.width(), 0.68 * r.height()), 2, 2)
        p.drawLine(_p(r, 0.24, 0.4), _p(r, 0.36, 0.5))
        p.drawLine(_p(r, 0.36, 0.5), _p(r, 0.24, 0.6))
        p.drawLine(_p(r, 0.46, 0.62), _p(r, 0.68, 0.62))

    elif name == "browser":
        p.drawEllipse(QRectF(r.left() + 0.08 * r.width(), r.top() + 0.08 * r.height(),
                             0.84 * r.width(), 0.84 * r.height()))
        p.drawEllipse(QRectF(r.left() + 0.34 * r.width(), r.top() + 0.08 * r.height(),
                             0.32 * r.width(), 0.84 * r.height()))
        p.drawLine(_p(r, 0.08, 0.5), _p(r, 0.92, 0.5))

    elif name == "grid":
        for gx in (0.14, 0.56):
            for gy in (0.14, 0.56):
                p.drawRoundedRect(
                    QRectF(r.left() + gx * r.width(), r.top() + gy * r.height(),
                           0.3 * r.width(), 0.3 * r.height()), 1.5, 1.5)

    elif name == "moon":
        path = QPainterPath()
        path.addEllipse(QRectF(r.left() + 0.14 * r.width(), r.top() + 0.1 * r.height(),
                               0.72 * r.width(), 0.72 * r.height()))
        cut = QPainterPath()
        cut.addEllipse(QRectF(r.left() + 0.34 * r.width(), r.top() + 0.02 * r.height(),
                              0.66 * r.width(), 0.66 * r.height()))
        p.drawPath(path.subtracted(cut))

    elif name == "monitor":
        p.drawRoundedRect(QRectF(r.left() + 0.08 * r.width(), r.top() + 0.16 * r.height(),
                                 0.84 * r.width(), 0.56 * r.height()), 2, 2)
        p.drawLine(_p(r, 0.5, 0.72), _p(r, 0.5, 0.86))
        p.drawLine(_p(r, 0.3, 0.88), _p(r, 0.7, 0.88))

    p.restore()


# ============================================================
#  导航按钮
# ============================================================
class NavButton(QWidget):
    """左侧栏的图标导航按钮（自绘，带 hover 动画）。"""

    clicked = pyqtSignal(str)

    def __init__(self, key, icon, tooltip="", parent=None):
        super().__init__(parent)
        self.key = key
        self.icon = icon
        self._hover = 0.0
        self._active = False
        self._active_p = 0.0
        self.setFixedSize(38, 38)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tooltip)
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(140)
        self._anim.valueChanged.connect(self._on_anim)
        self._activate_anim = QVariantAnimation(self)
        self._activate_anim.setDuration(220)
        self._activate_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._activate_anim.valueChanged.connect(self._on_activate)

    def _on_anim(self, v):
        self._hover = float(v)
        self.update()

    def _animate_to(self, target):
        self._anim.stop()
        self._anim.setStartValue(self._hover)
        self._anim.setEndValue(target)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.start()

    def enterEvent(self, e):
        self._animate_to(1.0)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._animate_to(0.0)
        super().leaveEvent(e)

    def set_active(self, flag):
        if self._active == flag:
            return
        self._active = flag
        self._activate_anim.stop()
        self._activate_anim.setStartValue(self._active_p)
        self._activate_anim.setEndValue(1.0 if flag else 0.0)
        self._activate_anim.start()

    def _on_activate(self, v):
        self._active_p = float(v)
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit(self.key)
        super().mousePressEvent(e)

    @safe_paint
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)

        ap = self._active_p
        if ap > 0.01:
            c = QColor(Theme.ACCENT)
            c.setAlphaF(0.20 * ap)
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            p.drawRoundedRect(r, 11, 11)
            # 左侧强调小条（随激活动画生长）
            bar_h = 15 * ap
            p.setBrush(QColor(Theme.ACCENT))
            p.drawRoundedRect(
                QRectF(r.left() - 0.6, r.center().y() - bar_h / 2, 2.6, bar_h),
                1.3, 1.3,
            )
        elif self._hover > 0.01:
            c = QColor(Theme.NAV_HOVER)
            c.setAlphaF(c.alphaF() * self._hover)
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            p.drawRoundedRect(r, 11, 11)

        if ap > 0.5:
            color = QColor(Theme.ACCENT).lighter(135)
        else:
            base = QColor(Theme.TEXT_DIM)
            hot = QColor(Theme.TEXT)
            t = self._hover
            color = QColor(
                int(base.red() + (hot.red() - base.red()) * t),
                int(base.green() + (hot.green() - base.green()) * t),
                int(base.blue() + (hot.blue() - base.blue()) * t),
            )

        icon_rect = QRectF(
            r.center().x() - 9, r.center().y() - 9, 18, 18
        )
        draw_icon(p, icon_rect, self.icon, color, 1.5)
        p.end()


# ============================================================
#  圆角小按钮
# ============================================================
class PillButton(QWidget):
    """胶囊形/圆角图标按钮。"""

    clicked = pyqtSignal()

    def __init__(self, icon=None, text="", parent=None,
                 w=34, h=30, radius=10, filled=False, accent=None):
        super().__init__(parent)
        self.icon = icon
        self.text = text
        self._hover = 0.0
        self._pressed = False
        self.filled = filled
        self.accent = accent or Theme.ACCENT
        self.radius = radius
        self.setFixedSize(w, h)
        self.setCursor(Qt.PointingHandCursor)
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(120)
        self._anim.valueChanged.connect(self._on_anim)

    def _on_anim(self, v):
        self._hover = float(v)
        self.update()

    def _animate_to(self, target):
        self._anim.stop()
        self._anim.setStartValue(self._hover)
        self._anim.setEndValue(target)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.start()

    def enterEvent(self, e):
        self._animate_to(1.0)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._animate_to(0.0)
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._pressed = True
            self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self._pressed:
            self._pressed = False
            self.update()
            if self.rect().contains(e.pos()):
                self.clicked.emit()
        super().mouseReleaseEvent(e)

    @safe_paint
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        if self.filled:
            base = QColor(self.accent)
            if self._hover > 0.01:
                base = QColor(
                    min(255, int(base.red() + (255 - base.red()) * 0.18 * self._hover)),
                    min(255, int(base.green() + (255 - base.green()) * 0.18 * self._hover)),
                    min(255, int(base.blue() + (255 - base.blue()) * 0.18 * self._hover)),
                )
            if self._pressed:
                base = base.darker(115)
            p.setPen(Qt.NoPen)
            p.setBrush(base)
            p.drawRoundedRect(r, self.radius, self.radius)
            fg = QColor(255, 255, 255)
        else:
            c = QColor(255, 255, 255, int(12 + 20 * self._hover))
            if self._pressed:
                c = QColor(255, 255, 255, 46)
            p.setPen(QPen(QColor(255, 255, 255, int(18 + 22 * self._hover)), 1))
            p.setBrush(c)
            p.drawRoundedRect(r, self.radius, self.radius)
            base = QColor(Theme.TEXT_DIM)
            hot = QColor(Theme.TEXT)
            fg = QColor(
                int(base.red() + (hot.red() - base.red()) * self._hover),
                int(base.green() + (hot.green() - base.green()) * self._hover),
                int(base.blue() + (hot.blue() - base.blue()) * self._hover),
            )

        if self.icon and not self.text:
            ir = QRectF(r.center().x() - 8, r.center().y() - 8, 16, 16)
            draw_icon(p, ir, self.icon, fg, 1.5)
        elif self.icon and self.text:
            f = QFont("Microsoft YaHei UI", 9)
            p.setFont(f)
            fm = p.fontMetrics()
            tw = fm.horizontalAdvance(self.text)
            total = 16 + 5 + tw
            x0 = r.center().x() - total / 2
            draw_icon(p, QRectF(x0, r.center().y() - 8, 16, 16), self.icon, fg, 1.5)
            p.setPen(QPen(fg))
            p.drawText(
                QRectF(x0 + 21, r.top(), tw + 2, r.height()),
                Qt.AlignVCenter | Qt.AlignLeft, self.text,
            )
        elif self.text:
            f = QFont("Microsoft YaHei UI", 9)
            p.setFont(f)
            p.setPen(QPen(fg))
            p.drawText(r, Qt.AlignCenter, self.text)
        p.end()


# ============================================================
#  迷你折线图
# ============================================================
class MiniGraph(QWidget):
    """滚动折线图，用于展示网速 / CPU 趋势。"""

    def __init__(self, parent=None, max_points=48, color=None, fill=True,
                 max_value=100.0, auto_scale=True, height=None,
                 log_scale=False):
        super().__init__(parent)
        self.data = deque([0.0] * max_points, maxlen=max_points)
        self.color = color or Theme.ACCENT
        self.fill = fill
        self.max_value = max_value
        self.auto_scale = auto_scale
        self.log_scale = log_scale
        self.setMinimumHeight(height or 34)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def _norm(self, v, top):
        import math

        if self.log_scale:
            return math.log10(1.0 + max(0.0, v)) / math.log10(1.0 + top)
        return min(max(0.0, v), top) / top

    def push(self, value):
        self.data.append(float(value))
        self.update()

    @safe_paint
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect())

        top = self.max_value
        if self.auto_scale and not self.log_scale:
            top = max(self.max_value * 0.15, max(self.data) * 1.25)
        if top <= 0:
            top = 1.0

        n = len(self.data)
        if n < 2:
            p.end()
            return
        step = r.width() / (n - 1)

        pts = [
            QPointF(r.left() + i * step,
                    r.bottom() - self._norm(v, top) * (r.height() - 3) - 1.5)
            for i, v in enumerate(self.data)
        ]

        path = QPainterPath()
        path.moveTo(pts[0])
        for i in range(1, len(pts)):
            prev, cur = pts[i - 1], pts[i]
            midx = (prev.x() + cur.x()) / 2
            path.cubicTo(QPointF(midx, prev.y()), QPointF(midx, cur.y()), cur)

        if self.fill:
            area = QPainterPath(path)
            area.lineTo(r.right(), r.bottom())
            area.lineTo(r.left(), r.bottom())
            area.closeSubpath()
            grad = QLinearGradient(0, r.top(), 0, r.bottom())
            c1 = QColor(self.color)
            c1.setAlpha(90)
            c2 = QColor(self.color)
            c2.setAlpha(0)
            grad.setColorAt(0.0, c1)
            grad.setColorAt(1.0, c2)
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(grad))
            p.drawPath(area)

        pen = QPen(self.color, 1.6)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)

        # 末端光点
        last = pts[-1]
        glow = QRadialGradient(last, 5)
        gc = QColor(self.color)
        gc.setAlpha(170)
        glow.setColorAt(0, gc)
        gc2 = QColor(self.color)
        gc2.setAlpha(0)
        glow.setColorAt(1, gc2)
        p.setBrush(QBrush(glow))
        p.setPen(Qt.NoPen)
        p.drawEllipse(last, 5, 5)
        p.setBrush(QColor(self.color))
        p.drawEllipse(last, 1.8, 1.8)
        p.end()


# ============================================================
#  圆环进度
# ============================================================
class RingProgress(QWidget):
    """圆环进度指示器（CPU / 内存 / 倒计时）。"""

    def __init__(self, parent=None, size=64, thickness=5, label="", value=0.0,
                 color=None, show_value=True):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.thickness = thickness
        self.label = label
        self.value = value          # 0..100
        self.text = None            # 自定义中心文本（如 "12:34"）
        self.color = color or Theme.ACCENT
        self.show_value = show_value
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def set_value(self, v, color=None):
        self.value = max(0.0, min(100.0, float(v)))
        if color is not None:
            self.color = color
        self.update()

    @safe_paint
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(
            self.thickness / 2 + 1, self.thickness / 2 + 1,
            -self.thickness / 2 - 1, -self.thickness / 2 - 1
        )

        # 底环
        p.setPen(QPen(QColor(255, 255, 255, 18), self.thickness))
        p.setBrush(Qt.NoBrush)
        p.drawArc(r, 0, 360 * 16)

        # 进度弧（渐变描边 + 末端柔光）
        if self.value > 0.5:
            grad = QLinearGradient(r.topLeft(), r.bottomRight())
            grad.setColorAt(0.0, QColor(self.color).lighter(155))
            grad.setColorAt(0.55, QColor(self.color))
            grad.setColorAt(1.0, QColor(self.color).darker(112))
            pen = QPen(QBrush(grad), self.thickness)
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            p.drawArc(r, 90 * 16, -int(self.value / 100.0 * 360 * 16))

        # 文本
        if self.text is not None:
            main = self.text
            sub = self.label
        elif self.show_value:
            main = f"{int(round(self.value))}"
            sub = self.label
        else:
            main = ""
            sub = self.label

        shift = -5 if sub else 0
        if main:
            f = QFont("Microsoft YaHei UI", 11, QFont.DemiBold)
            p.setFont(f)
            p.setPen(QPen(Theme.TEXT))
            p.drawText(QRectF(self.rect().left(), self.rect().top() + shift,
                              self.rect().width(), self.rect().height()),
                       Qt.AlignCenter, main)
        if sub:
            f2 = QFont("Microsoft YaHei UI", 7)
            p.setFont(f2)
            p.setPen(QPen(Theme.TEXT_FAINT))
            p.drawText(QRectF(self.rect().left(), self.rect().center().y() + 9,
                              self.rect().width(), 14),
                       Qt.AlignCenter, sub)
        p.end()


# ============================================================
#  细进度条
# ============================================================
class Bar(QWidget):
    def __init__(self, parent=None, height=5, color=None, value=0.0):
        super().__init__(parent)
        self.setFixedHeight(height)
        self.color = color or Theme.ACCENT
        self.value = value
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_value(self, v, color=None):
        self.value = max(0.0, min(100.0, float(v)))
        if color is not None:
            self.color = color
        self.update()

    @safe_paint
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect())
        rad = r.height() / 2
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 22))
        p.drawRoundedRect(r, rad, rad)
        if self.value > 0:
            w = max(r.height(), r.width() * self.value / 100.0)
            grad = QLinearGradient(r.left(), 0, r.left() + w, 0)
            grad.setColorAt(0.0, QColor(self.color))
            grad.setColorAt(1.0, QColor(self.color).lighter(140))
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(QRectF(r.left(), r.top(), w, r.height()), rad, rad)
        p.end()


# ============================================================
#  呼吸小圆点
# ============================================================
class Dot(QWidget):
    """状态指示圆点，带呼吸动画。"""

    def __init__(self, parent=None, size=8, color=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.color = color or Theme.OK
        self._phase = 0.0
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(60)

    def _tick(self):
        self._phase = (self._phase + 0.06) % 1.0
        self.update()

    def set_color(self, color):
        self.color = color
        self.update()

    @safe_paint
    def paintEvent(self, e):
        import math
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect())
        pulse = 0.5 + 0.5 * math.sin(self._phase * 2 * math.pi)
        glow = QRadialGradient(r.center(), r.width())
        gc = QColor(self.color)
        gc.setAlpha(int(60 + 90 * pulse))
        glow.setColorAt(0.0, gc)
        gc2 = QColor(self.color)
        gc2.setAlpha(0)
        glow.setColorAt(1.0, gc2)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(glow))
        p.drawEllipse(r)
        p.setBrush(QColor(self.color))
        p.drawEllipse(r.adjusted(r.width() * 0.28, r.width() * 0.28,
                                 -r.width() * 0.28, -r.width() * 0.28))
        p.end()
