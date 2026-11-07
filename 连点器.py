# -*- coding: utf-8 -*-
"""老式托盘连点器 - Windows 版
托盘小图标 + 右键菜单 + 简陋设置窗，老式工具软件风格，无花哨界面。
用法：双击运行 → 托盘图标常驻 → 右键"开始连点"（或 Ctrl+Shift+Z）→ 鼠标移到目标上开始。
热键：Ctrl+Shift+Z 开始/停止，Ctrl+Shift+Q 退出。
参数可在"设置"窗口修改，自动保存到 exe 同目录的 clicker_config.json。
"""
import sys, os, time, threading, random, json
from pynput.mouse import Button, Controller as MouseController
from pynput import keyboard
import pystray
from PIL import Image, ImageDraw
import tkinter as tk

APP_NAME = "老式连点器"
BASE_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
CONFIG_FILE = os.path.join(BASE_DIR, "clicker_config.json")
LOG_FILE = os.path.join(BASE_DIR, "clicker_log.txt")

# ============ 默认参数（设置窗口里也能改） ============
DEFAULTS = {
    "interval_min": 0.10,   # 最小间隔（秒）
    "interval_max": 0.22,   # 最大间隔（秒）
    "jitter_px": 4,         # 点击位置抖动（像素）
    "pause_rate": 3,        # 随机停顿概率（%）
    "follow_mouse": False,  # False=固定在开始位置，True=跟随鼠标当前位置
}

clicking = False
click_count = 0
anchor = None
settings = dict(DEFAULTS)
stop_flag = False
settings_window = None
icon = None
log_lock = threading.Lock()
mouse = MouseController()


def log(msg):
    with log_lock:
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
        except Exception:
            pass


def load_config():
    global settings
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        for k in DEFAULTS:
            if k in saved:
                settings[k] = saved[k]
    except Exception:
        pass


def save_config():
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log("保存配置失败: " + str(e))


def click_loop():
    global clicking, click_count, anchor
    while not stop_flag:
        if clicking:
            if settings["follow_mouse"]:
                anchor = mouse.position
            elif anchor is None:
                anchor = mouse.position
            dx = random.randint(-settings["jitter_px"], settings["jitter_px"])
            dy = random.randint(-settings["jitter_px"], settings["jitter_px"])
            mouse.position = (anchor[0] + dx, anchor[1] + dy)
            mouse.click(Button.left, 1)
            click_count += 1
            interval = random.uniform(settings["interval_min"], settings["interval_max"])
            if settings["pause_rate"] > 0 and random.random() < settings["pause_rate"] / 100.0:
                interval += random.uniform(0.25, 0.65)
        else:
            interval = 0.05
        time.sleep(interval)


def toggle():
    global clicking, anchor
    if clicking:
        clicking = False
        log("连点停止")
    else:
        anchor = None
        clicking = True
        log("连点开始")
    try:
        icon.update_menu()
    except Exception:
        pass


def quit_app():
    global stop_flag, clicking
    clicking = False
    stop_flag = True
    log("程序退出")
    try:
        icon.stop()
    except Exception:
        pass
    os._exit(0)


def make_icon():
    """画一个简单像素风图标：鼠标箭头 + 红点（无任何花哨装饰）"""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.polygon([(6, 4), (6, 42), (16, 32), (23, 45), (30, 41), (23, 29), (34, 29)], fill=(25, 25, 25))
    d.ellipse([38, 38, 60, 60], fill=(200, 25, 25))
    return img


def open_settings_window(icon_item=None, _=None):
    global settings_window

    def build():
        global settings_window
        if settings_window is not None:
            try:
                settings_window.deiconify()
                settings_window.lift()
                return
            except Exception:
                settings_window = None

        win = tk.Tk()
        settings_window = win
        win.title("连点器设置")
        win.resizable(False, False)

        rows = [
            ("最小间隔 (秒)", "interval_min"),
            ("最大间隔 (秒)", "interval_max"),
            ("位置抖动 (像素)", "jitter_px"),
            ("停顿概率 (%)", "pause_rate"),
        ]
        entries = {}
        for i, (label, key) in enumerate(rows):
            tk.Label(win, text=label).grid(row=i, column=0, padx=10, pady=4, sticky="w")
            v = tk.StringVar(value=str(settings[key]))
            entries[key] = v
            tk.Entry(win, textvariable=v, width=12).grid(row=i, column=1, padx=10, pady=4)

        follow_var = tk.BooleanVar(value=bool(settings["follow_mouse"]))
        tk.Checkbutton(
            win, text="跟随鼠标当前位置（不勾=固定在开始时的位置）",
            variable=follow_var
        ).grid(row=len(rows), column=0, columnspan=2, padx=10, pady=4, sticky="w")

        status = tk.Label(win, text="已停止", fg="gray30")
        status.grid(row=len(rows) + 1, column=0, columnspan=2, pady=2)

        def save():
            try:
                settings["interval_min"] = float(entries["interval_min"].get())
                settings["interval_max"] = float(entries["interval_max"].get())
                settings["jitter_px"] = int(entries["jitter_px"].get())
                settings["pause_rate"] = float(entries["pause_rate"].get())
                settings["follow_mouse"] = bool(follow_var.get())
                if settings["interval_min"] < 0.01:
                    settings["interval_min"] = 0.01
                if settings["interval_max"] < settings["interval_min"]:
                    settings["interval_max"] = settings["interval_min"]
                save_config()
                status.config(text="已保存", fg="green")
            except Exception:
                status.config(text="数字填错了，检查一下", fg="red")

        def reset_defaults():
            global settings
            settings = dict(DEFAULTS)
            for key, v in entries.items():
                v.set(str(settings[key]))
            follow_var.set(bool(settings["follow_mouse"]))
            save_config()
            status.config(text="已恢复默认并保存", fg="green")

        btn_row = len(rows) + 2
        tk.Button(win, text="保存", width=10, command=save).grid(row=btn_row, column=0, padx=10, pady=8)
        tk.Button(win, text="恢复默认", width=10, command=reset_defaults).grid(row=btn_row, column=1, padx=10, pady=8)
        tk.Label(
            win, text="热键: Ctrl+Shift+Z 开始/停止    Ctrl+Shift+Q 退出",
            fg="gray30"
        ).grid(row=btn_row + 1, column=0, columnspan=2, padx=10, pady=(0, 10))

        def tick():
            if clicking:
                status.config(text="连点中… 已点 %d 次" % click_count, fg="black")
            else:
                status.config(text="已停止", fg="gray30")
            win.after(500, tick)

        tick()

        def on_close():
            global settings_window
            settings_window = None
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", on_close)
        win.mainloop()

    threading.Thread(target=build, daemon=True).start()


def keyboard_listen():
    with keyboard.GlobalHotKeys({
        '<ctrl>+<shift>+z': toggle,
        '<ctrl>+<shift>+q': quit_app,
    }) as h:
        h.join()


if __name__ == "__main__":
    load_config()
    threading.Thread(target=click_loop, daemon=True).start()
    threading.Thread(target=keyboard_listen, daemon=True).start()
    menu = pystray.Menu(
        pystray.MenuItem(
            lambda item: "停止连点 (Ctrl+Shift+Z)" if clicking else "开始连点 (Ctrl+Shift+Z)",
            lambda item: toggle(),
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("设置…", open_settings_window),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("退出", lambda item: quit_app()),
    )
    icon = pystray.Icon(APP_NAME, make_icon(), APP_NAME + " - 右键设置", menu)
    icon.run()
