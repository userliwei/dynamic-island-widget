# -*- coding: utf-8 -*-
"""
Windows 系统集成
----------------
全部基于 ctypes 直接调用系统 API，无需第三方库。
若环境中有 pycaw，则额外支持读取/设置真实音量。
"""

import ctypes
import os
import subprocess
import sys
import time

user32 = ctypes.windll.user32

# ---------------- 虚拟键码 ----------------
VK_MEDIA_NEXT = 0xB0
VK_MEDIA_PREV = 0xB1
VK_MEDIA_STOP = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xB3
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF

KEYEVENTF_KEYUP = 0x0002


def _send_vk(vk):
    """发送一次完整的按键（按下+抬起）。"""
    try:
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
        return True
    except Exception:
        return False


# ---------------- 媒体控制 ----------------
def media_play_pause():
    return _send_vk(VK_MEDIA_PLAY_PAUSE)


def media_next():
    return _send_vk(VK_MEDIA_NEXT)


def media_prev():
    return _send_vk(VK_MEDIA_PREV)


def media_stop():
    return _send_vk(VK_MEDIA_STOP)


# ---------------- 音量控制 ----------------
def volume_up():
    return _send_vk(VK_VOLUME_UP)


def volume_down():
    return _send_vk(VK_VOLUME_DOWN)


def volume_mute():
    return _send_vk(VK_VOLUME_MUTE)


# --- 真实音量（可选：需要 pycaw） ---
_pycaw = None
_pycaw_failed = False


def _load_pycaw():
    global _pycaw, _pycaw_failed
    if _pycaw is not None or _pycaw_failed:
        return _pycaw
    try:
        from pycaw.pycaw import AudioUtilities

        device = AudioUtilities.GetSpeakers()
        # 新版 pycaw：AudioDevice 直接暴露 EndpointVolume
        ep = getattr(device, "EndpointVolume", None)
        if ep is not None and hasattr(ep, "GetMasterVolumeLevelScalar"):
            _pycaw = ep
        elif hasattr(device, "Activate"):
            # 旧版 pycaw：需手动 Activate
            from ctypes import POINTER, cast
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import IAudioEndpointVolume

            interface = device.Activate(
                IAudioEndpointVolume._iid_, CLSCTX_ALL, None
            )
            _pycaw = cast(interface, POINTER(IAudioEndpointVolume))
        else:
            _pycaw_failed = True
            _pycaw = None
    except Exception:
        _pycaw_failed = True
        _pycaw = None
    return _pycaw


def volume_available():
    return _load_pycaw() is not None


def get_volume():
    """返回 0..100 的整数；不可用时返回 None。"""
    vol = _load_pycaw()
    if vol is None:
        return None
    try:
        return int(round(vol.GetMasterVolumeLevelScalar() * 100))
    except Exception:
        return None


def is_muted():
    vol = _load_pycaw()
    if vol is None:
        return None
    try:
        return bool(vol.GetMute())
    except Exception:
        return None


def set_volume(percent):
    """设置主音量 0..100；不可用返回 False。"""
    vol = _load_pycaw()
    if vol is None:
        return False
    try:
        percent = max(0, min(100, int(percent)))
        vol.SetMasterVolumeLevelScalar(percent / 100.0, None)
        return True
    except Exception:
        return False


def set_mute(flag):
    vol = _load_pycaw()
    if vol is None:
        return False
    try:
        vol.SetMute(1 if flag else 0, None)
        return True
    except Exception:
        return False


# ---------------- 系统操作 ----------------
def lock_screen():
    try:
        user32.LockWorkStation()
        return True
    except Exception:
        return False


def sleep_pc():
    try:
        subprocess.Popen(
            "rundll32.exe powrprof.dll,SetSuspendState 0,1,0",
            shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


def empty_recycle_bin():
    try:
        subprocess.Popen(
            'powershell -NoProfile -Command "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"',
            shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=0x08000000,
        )
        return True
    except Exception:
        return False


def screenshot(save_dir=None):
    """截取全屏并保存为 PNG，返回文件路径或 None。"""
    try:
        from PyQt5.QtWidgets import QApplication
        if save_dir is None:
            pics = os.path.join(os.path.expanduser("~"), "Pictures", "DynamicIsland")
        else:
            pics = save_dir
        os.makedirs(pics, exist_ok=True)
        screen = QApplication.primaryScreen()
        pix = screen.grabWindow(0)
        path = os.path.join(pics, time.strftime("shot_%Y%m%d_%H%M%S.png"))
        pix.save(path, "PNG")
        return path
    except Exception:
        return None


def disk_percent(path=None):
    """读取磁盘使用百分比。

    直接调用 Win32 GetDiskFreeSpaceExW，绕过 psutil 在部分
    Python 版本上的兼容问题。
    """
    if path is None:
        path = os.environ.get("SystemDrive", "C:") + os.sep
    try:
        free = ctypes.c_ulonglong(0)
        total = ctypes.c_ulonglong(0)
        total_free = ctypes.c_ulonglong(0)
        ok = ctypes.windll.kernel32.GetDiskFreeSpaceExW(
            ctypes.c_wchar_p(path),
            ctypes.byref(free), ctypes.byref(total), ctypes.byref(total_free),
        )
        if ok and total.value > 0:
            return (total.value - free.value) / total.value * 100.0
    except Exception:
        pass
    try:
        import psutil
        return psutil.disk_usage(path).percent
    except Exception:
        return 0.0


def open_path(path):
    """用系统默认程序打开路径/网址/程序。"""
    try:
        if hasattr(os, "startfile"):
            os.startfile(path)  # noqa: S606
        else:
            subprocess.Popen(["xdg-open", path])
        return True
    except Exception:
        return False


def run_command(cmd):
    """后台静默启动命令。"""
    try:
        subprocess.Popen(
            cmd, shell=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=0x08000000 if sys.platform == "win32" else 0,
        )
        return True
    except Exception:
        return False


# ---------------- 开机自启 ----------------
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "DynamicIsland"


def _launch_target():
    """返回用于开机自启的命令行。"""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    entry = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    exe = pythonw if os.path.isfile(pythonw) else sys.executable
    return f'"{exe}" "{entry}"'


# ---------------- 前台应用 / 正在播放 ----------------
u = user32

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
AUDIO_STATE_ACTIVE = 1

# 不是音乐标题的系统窗口
_SKIP_TITLES = {
    "Default IME", "MSCTFIME UI", "Program Manager",
    "EVR Fullscreen Window", "Windows Input Experience",
}

# 浏览器/播放器附加在标题后的后缀
_APP_SUFFIX = (
    " - YouTube", " - YouTube Music", " - Spotify", " - SoundCloud",
    " | 网易云音乐", " - 网易云音乐", " - QQ音乐", " - 酷狗音乐",
    " - 酷我音乐", " - bilibili", " - NetEase Cloud Music",
    " - Google Chrome", " - Microsoft Edge", " - Mozilla Firefox",
)

# 不是音乐播放器的音频会话（系统声音、壁纸引擎等）
_IGNORE_AUDIO_APPS = {
    "wallpaper32.exe", "wallpaper64.exe", "nvcontainer.exe",
    "audiodg.exe", "svchost.exe", "system sounds.exe",
}


def _process_name(pid):
    """由 PID 取进程可执行文件名。"""
    try:
        k32 = ctypes.windll.kernel32
        handle = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = ctypes.wintypes.DWORD(1024)
            if k32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                return os.path.basename(buf.value)
        finally:
            k32.CloseHandle(handle)
    except Exception:
        pass
    return ""


def _window_title(hwnd):
    try:
        n = u.GetWindowTextLengthW(hwnd)
        if n <= 0:
            return ""
        buf = ctypes.create_unicode_buffer(n + 1)
        u.GetWindowTextW(hwnd, buf, n + 1)
        return buf.value
    except Exception:
        return ""


def get_foreground_app():
    """返回当前前台窗口的 (进程名, 窗口标题)。"""
    try:
        hwnd = u.GetForegroundWindow()
        if not hwnd:
            return ("", "")
        title = _window_title(hwnd)
        pid = ctypes.wintypes.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return (_process_name(pid.value), title)
    except Exception:
        return ("", "")


def _visible_titles_of_pid(pid):
    """枚举指定进程的所有可见窗口标题。"""
    out = []
    try:
        WNDENUMPROC = ctypes.WINFUNCTYPE(
            ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM
        )

        def _cb(hwnd, _lparam):
            p = ctypes.wintypes.DWORD()
            u.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
            if p.value == pid and u.IsWindowVisible(hwnd):
                t = _window_title(hwnd)
                if t:
                    out.append(t)
            return True

        u.EnumWindows(WNDENUMPROC(_cb), 0)
    except Exception:
        pass
    return out


def _pick_track_title(titles):
    """从窗口标题里选出最像“歌名”的那一条。"""
    for t in titles:
        t = (t or "").strip()
        if not t or t in _SKIP_TITLES:
            continue
        if t.startswith("GDI+ Window") or t.startswith("NVCap"):
            continue
        if t.startswith("{") or t.startswith("MSCTF"):
            continue
        return t
    return ""


def _split_track(text):
    """把窗口标题拆成 (歌名, 歌手)。"""
    t = (text or "").strip()
    for suffix in _APP_SUFFIX:
        if t.endswith(suffix):
            t = t[: -len(suffix)].strip()
            break
    for sep in (" - ", " – ", " — ", " | "):
        if sep in t:
            head, tail = t.split(sep, 1)
            return head.strip(), tail.strip()
    return t, ""


def get_now_playing():
    """读取当前正在播放的媒体信息。

    做法：通过音频会话找出真正在输出声音的进程，再读它的窗口标题解析
    歌名/歌手。无需 winsdk，兼容 Spotify / 网易云 / QQ音乐 / 浏览器等。

    返回 dict(app, title, artist, playing) 或 None。
    """
    try:
        from pycaw.pycaw import AudioUtilities
    except Exception:
        return None
    try:
        sessions = AudioUtilities.GetAllSessions()
    except Exception:
        return None

    best = None  # (playing, exe, track)
    for s in sessions:
        try:
            proc = s.Process
            if proc is None:
                continue
            exe = proc.name()
            if exe.lower() in _IGNORE_AUDIO_APPS:
                continue
            state = getattr(s, "State", 0)
            titles = _visible_titles_of_pid(s.ProcessId)
            track = _pick_track_title(titles)
            if not track:
                continue
            playing = int(state) == AUDIO_STATE_ACTIVE
            if best is None or (playing and not best[0]):
                best = (playing, exe, track)
        except Exception:
            continue

    if best is None:
        return None
    playing, exe, track = best
    title, artist = _split_track(track)
    return {
        "app": os.path.splitext(exe)[0],
        "title": title,
        "artist": artist,
        "playing": playing,
    }


def set_autostart(enable):
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
        )
        try:
            if enable:
                winreg.SetValueEx(
                    key, RUN_VALUE, 0, winreg.REG_SZ, _launch_target()
                )
            else:
                try:
                    winreg.DeleteValue(key, RUN_VALUE)
                except FileNotFoundError:
                    pass
        finally:
            winreg.CloseKey(key)
        return True
    except Exception:
        return False


def is_autostart_enabled():
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_QUERY_VALUE
        )
        try:
            winreg.QueryValueEx(key, RUN_VALUE)
            return True
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)
    except Exception:
        return False


# ---------------- 常用应用启动 ----------------
APPS = {
    "explorer": lambda: run_command("explorer.exe"),
    "terminal": lambda: run_command("wt.exe") or run_command("powershell.exe"),
    "notepad": lambda: run_command("notepad.exe"),
    "calc": lambda: run_command("calc.exe"),
    "browser": lambda: open_path("https://www.bing.com"),
    "settings": lambda: run_command("start ms-settings:"),
    "downloads": lambda: open_path(os.path.join(os.path.expanduser("~"), "Downloads")),
    "desktop": lambda: open_path(os.path.join(os.path.expanduser("~"), "Desktop")),
    "documents": lambda: open_path(os.path.join(os.path.expanduser("~"), "Documents")),
    "taskmgr": lambda: run_command("taskmgr.exe"),
    "vscode": lambda: run_command("code"),
    "control": lambda: run_command("control.exe"),
}


def launch_app(name):
    fn = APPS.get(name)
    if fn is None:
        return False
    try:
        result = fn()
        return True if result is None else bool(result)
    except Exception:
        return False
