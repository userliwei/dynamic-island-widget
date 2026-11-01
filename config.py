# -*- coding: utf-8 -*-
"""
配置与主题
----------
所有可调参数集中在此：几何尺寸、配色、持久化配置读写。
"""

import json
import os
from PyQt5.QtGui import QColor

# ---------------- 路径 ----------------
APP_NAME = "DynamicIsland"
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".dynamic_island")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

# ---------------- 几何 ----------------
SHADOW_MARGIN = 18          # 窗口四周预留的阴影空间

IDLE_W, IDLE_H = 196, 36    # 休眠胶囊
IDLE_R = 18                 # 休眠圆角（= 高/2，正胶囊）

EXP_W, EXP_H = 476, 306     # 展开面板
EXP_R = 34                  # 展开圆角

NAV_W = 50                  # 左侧导航栏宽度
PAD = 12                    # 内边距

# ---------------- 主题色 ----------------
class Theme:
    BG_TOP = QColor(37, 40, 49, 243)        # 玻璃渐变色 上（带蓝调）
    BG_BOT = QColor(17, 18, 23, 249)        # 玻璃渐变色 下
    BORDER = QColor(255, 255, 255, 22)      # 1px 高光描边
    BORDER_TOP = QColor(255, 255, 255, 52)  # 顶部更亮的描边

    TEXT = QColor(245, 246, 250)
    TEXT_DIM = QColor(148, 152, 163)
    TEXT_FAINT = QColor(96, 100, 110)

    ACCENT = QColor(110, 139, 255)          # 主强调色（蓝紫）
    ACCENT_2 = QColor(167, 108, 255)        # 次强调（紫）
    OK = QColor(72, 209, 141)               # 绿
    WARN = QColor(255, 196, 66)             # 黄
    DANGER = QColor(255, 96, 96)            # 红

    NAV_IDLE = QColor(255, 255, 255, 0)
    NAV_HOVER = QColor(255, 255, 255, 18)
    NAV_ACTIVE = QColor(110, 139, 255, 46)

    CARD = QColor(255, 255, 255, 10)        # 卡片底色
    CARD_EDGE = QColor(255, 255, 255, 16)

    # 状态圆点颜色
    @staticmethod
    def load_color(percent):
        if percent >= 80:
            return Theme.DANGER
        if percent >= 55:
            return Theme.WARN
        return Theme.OK


# ---------------- 持久化配置 ----------------
DEFAULTS = {
    "x": None,                  # None = 屏幕水平居中
    "y": 64,                    # 内容顶部距屏幕顶部的像素
                               # 预留顶部区（歌词条/工具条）避免被遮挡
    "always_on_top": True,
    "opacity": 0.96,
    "autostart": False,
    "panel": "clock",           # 上次停留的面板
    "focus_minutes": 25,
    "focus_break": 5,
    "collapse_delay_ms": 900,   # 鼠标离开后多久收起
    "accent": "#6E8BFF",
    "show_seconds": False,
}


def _ensure_dir():
    if not os.path.isdir(CONFIG_DIR):
        os.makedirs(CONFIG_DIR, exist_ok=True)


def load_config():
    """读取配置，缺失项回落到默认值。"""
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        if isinstance(saved, dict):
            for k, v in saved.items():
                if k in DEFAULTS:
                    cfg[k] = v
    except (OSError, ValueError):
        pass
    return cfg


def save_config(cfg):
    """保存配置；失败静默（不影响主流程）。"""
    try:
        _ensure_dir()
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False
