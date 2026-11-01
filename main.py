# -*- coding: utf-8 -*-
"""
DynamicIsland · 灵动岛桌面小组件
--------------------------------
入口文件。启动后屏幕顶部会出现可展开的胶囊窗口。
"""

import os
import sys
import traceback

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# --- 高 DPI 支持（必须在 QApplication 之前设置）---
from PyQt5.QtCore import Qt
from PyQt5.QtGui import (
    QColor, QFont, QIcon, QLinearGradient, QPainter, QPainterPath, QPixmap,
)
from PyQt5.QtWidgets import QApplication, QMenu, QSystemTrayIcon

try:
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
except Exception:
    pass

from config import load_config, save_config  # noqa: E402
from island import DynamicIsland           # noqa: E402

LOG_FILE = os.path.join(
    os.path.expanduser("~"), ".dynamic_island", "error.log"
)


def log_exception(exc_type, exc_value, exc_tb):
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write("\n" + "=" * 60 + "\n")
            traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
    except OSError:
        pass


sys.excepthook = log_exception


def make_tray_icon(app):
    """程序化绘制托盘图标，避免依赖外部图片资源。"""
    size = 64
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing, True)

    grad = QLinearGradient(0, 0, 0, size)
    grad.setColorAt(0.0, QColor(48, 48, 56))
    grad.setColorAt(1.0, QColor(20, 20, 26))
    path = QPainterPath()
    path.addRoundedRect(4, 18, size - 8, 28, 14, 14)
    p.setPen(QColor(255, 255, 255, 40))
    p.setBrush(grad)
    p.drawPath(path)

    p.setPen(Qt.NoPen)
    p.setBrush(QColor(72, 209, 141))
    p.drawEllipse(14, 27, 9, 9)

    p.setBrush(QColor(245, 246, 250))
    p.drawRoundedRect(29, 28, 22, 4, 2, 2)
    p.drawRoundedRect(29, 35, 14, 4, 2, 2)
    p.end()

    return QSystemTrayIcon(QIcon(pix), app)


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("DynamicIsland")
    app.setFont(QFont("Microsoft YaHei UI", 9))

    cfg = load_config()
    island = DynamicIsland(cfg)

    # ---- 托盘 ----
    tray = make_tray_icon(app)
    menu = QMenu()
    menu.setStyleSheet(
        """
        QMenu { background:#1B1B20; color:#E9EAF0; border:1px solid rgba(255,255,255,0.10);
                border-radius:10px; padding:6px; font-family:'Microsoft YaHei UI'; font-size:9pt; }
        QMenu::item { padding:6px 22px 6px 12px; border-radius:6px; }
        QMenu::item:selected { background:rgba(110,139,255,0.28); }
        QMenu::separator { height:1px; background:rgba(255,255,255,0.08); margin:4px 8px; }
        """
    )

    act_show = menu.addAction("展开 / 收起")
    act_show.triggered.connect(island.toggle)
    act_top = menu.addAction("回到屏幕顶部")
    act_top.triggered.connect(island.reset_position)
    menu.addSeparator()

    act_pin = menu.addAction("始终置顶")
    act_pin.setCheckable(True)
    act_pin.setChecked(cfg.get("always_on_top", True))

    def on_pin(flag):
        island.set_always_on_top(flag)
        act_pin.setChecked(island._pin_top)

    act_pin.triggered.connect(on_pin)
    menu.addSeparator()

    act_set = menu.addAction("设置")
    act_set.triggered.connect(lambda: island.show_panel("settings"))

    def do_shot():
        import win_utils
        path = win_utils.screenshot()
        if path:
            island.notify("截图已保存", path, "camera")

    act_shot = menu.addAction("截图")
    act_shot.triggered.connect(do_shot)
    menu.addSeparator()
    act_quit = menu.addAction("退出 DynamicIsland")
    act_quit.triggered.connect(island.quit_app)

    tray.setContextMenu(menu)
    tray.setToolTip("DynamicIsland · 灵动岛")
    tray.activated.connect(
        lambda reason: island.toggle()
        if reason == QSystemTrayIcon.Trigger else None
    )
    tray.show()

    island.show()
    island.raise_()

    # 首次启动提示
    island.notify("灵动岛已启动", "把鼠标移到胶囊上即可展开", "check")

    code = app.exec_()
    save_config(island.cfg)
    return code


if __name__ == "__main__":
    sys.exit(main())
