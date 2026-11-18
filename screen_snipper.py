import os
import sys
import ctypes
import tkinter as tk
from PIL import Image, ImageTk, ImageEnhance, ImageGrab
import mss

# Enable Per-Monitor High DPI awareness
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

def get_virtual_screen_bounds():
    user32 = ctypes.windll.user32
    left = user32.GetSystemMetrics(76)   # SM_XVIRTUALSCREEN
    top = user32.GetSystemMetrics(77)    # SM_YVIRTUALSCREEN
    width = user32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
    height = user32.GetSystemMetrics(79) # SM_CYVIRTUALSCREEN
    if width <= 0 or height <= 0:
        width = user32.GetSystemMetrics(0)
        height = user32.GetSystemMetrics(1)
        left, top = 0, 0
    return left, top, width, height

def capture_screen_image():
    """Captures all displays into a single PIL Image."""
    try:
        img = ImageGrab.grab(all_screens=True)
        if img:
            return img
    except Exception:
        pass

    try:
        with mss.MSS() as sct:
            mon = sct.monitors[0]
            sct_img = sct.grab(mon)
            return Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
    except Exception:
        pass

    return ImageGrab.grab()

class ScreenSnipper:
    def __init__(self, root, on_complete, on_cancel=None):
        self.root = root
        self.on_complete = on_complete
        self.on_cancel = on_cancel

        self.start_x = None
        self.start_y = None
        self.current_x = None
        self.current_y = None

        self.original_img = None
        self.dimmed_img = None
        self.tk_dimmed = None
        self.win = None
        self.canvas = None

    def start(self):
        # 1. Grab screen first before showing window
        self.original_img = capture_screen_image()
        if not self.original_img:
            if self.on_cancel:
                self.on_cancel()
            return

        # 2. Prepare darkened image for the Circle-to-Search dimming effect
        enhancer = ImageEnhance.Brightness(self.original_img)
        self.dimmed_img = enhancer.enhance(0.55)

        # 3. Create fullscreen topmost window
        left, top, width, height = get_virtual_screen_bounds()
        self.win = tk.Toplevel(self.root)
        self.win.overrideredirect(True)
        self.win.geometry(f"{width}x{height}+{left}+{top}")
        self.win.attributes("-topmost", True)
        self.win.config(cursor="cross")

        # 4. Canvas
        self.canvas = tk.Canvas(self.win, width=width, height=height, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.tk_dimmed = ImageTk.PhotoImage(self.dimmed_img)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_dimmed)

        # Banner at the top
        banner_w = 680
        banner_h = 42
        bx1 = (width - banner_w) // 2
        by1 = 20
        bx2 = bx1 + banner_w
        by2 = by1 + banner_h

        self.canvas.create_rectangle(bx1, by1, bx2, by2, fill="#181825", outline="#89b4fa", width=2)
        self.canvas.create_text(
            (bx1 + bx2) // 2,
            (by1 + by2) // 2,
            text="🔍 حدد بالماوس لعرض الترجمة فوق الشاشة  |  Enter: ترجمة الشاشة كاملة  |  Esc: إلغاء",
            fill="#cdd6f4",
            font=("Segoe UI", 11, "bold")
        )

        # Event bindings
        self.win.bind("<ButtonPress-1>", self.on_button_press)
        self.win.bind("<B1-Motion>", self.on_move_press)
        self.win.bind("<ButtonRelease-1>", self.on_button_release)
        self.win.bind("<Return>", self.on_enter_pressed)
        self.win.bind("<Escape>", self.on_escape_pressed)
        self.win.bind("<Button-3>", self.on_escape_pressed)
        self.win.bind("<Double-Button-1>", self.on_enter_pressed)

        self.win.focus_force()

    def on_button_press(self, event):
        self.start_x = event.x
        self.start_y = event.y

    def on_move_press(self, event):
        self.current_x = event.x
        self.current_y = event.y

        # Clear previous selection drawings
        self.canvas.delete("selection_box")
        self.canvas.delete("selection_img")
        self.canvas.delete("size_badge")

        x1 = min(self.start_x, self.current_x)
        y1 = min(self.start_y, self.current_y)
        x2 = max(self.start_x, self.current_x)
        y2 = max(self.start_y, self.current_y)

        if x2 - x1 > 2 and y2 - y1 > 2:
            img_w, img_h = self.original_img.size
            win_w = self.win.winfo_width()
            win_h = self.win.winfo_height()

            scale_x = img_w / win_w if win_w > 0 else 1.0
            scale_y = img_h / win_h if win_h > 0 else 1.0

            crop_box = (
                int(x1 * scale_x),
                int(y1 * scale_y),
                int(x2 * scale_x),
                int(y2 * scale_y)
            )

            try:
                bright_crop = self.original_img.crop(crop_box)
                bright_crop = bright_crop.resize((x2 - x1, y2 - y1), Image.Resampling.BILINEAR)
                self.tk_bright = ImageTk.PhotoImage(bright_crop)
                self.canvas.create_image(x1, y1, anchor=tk.NW, image=self.tk_bright, tags="selection_img")
            except Exception:
                pass

            # Glowing border
            self.canvas.create_rectangle(
                x1, y1, x2, y2,
                outline="#38bdf8",
                width=2,
                tags="selection_box"
            )

            # Dimensions badge
            w_px = int((x2 - x1) * scale_x)
            h_px = int((y2 - y1) * scale_y)
            badge_text = f"{w_px} × {h_px} px"
            self.canvas.create_rectangle(
                x1, y2 + 5, x1 + 100, y2 + 25,
                fill="#1e1e2e",
                outline="#89b4fa",
                tags="size_badge"
            )
            self.canvas.create_text(
                x1 + 50, y2 + 15,
                text=badge_text,
                fill="#a6adc8",
                font=("Segoe UI", 8),
                tags="size_badge"
            )

    def on_button_release(self, event):
        if self.start_x is None or self.current_x is None:
            return

        x1 = min(self.start_x, self.current_x)
        y1 = min(self.start_y, self.current_y)
        x2 = max(self.start_x, self.current_x)
        y2 = max(self.start_y, self.current_y)

        # Min threshold: 10 pixels
        if (x2 - x1) < 10 or (y2 - y1) < 10:
            return

        img_w, img_h = self.original_img.size
        win_w = self.win.winfo_width()
        win_h = self.win.winfo_height()

        scale_x = img_w / win_w if win_w > 0 else 1.0
        scale_y = img_h / win_h if win_h > 0 else 1.0

        crop_box = (
            int(x1 * scale_x),
            int(y1 * scale_y),
            int(x2 * scale_x),
            int(y2 * scale_y)
        )

        cropped = self.original_img.crop(crop_box)
        full_img = self.original_img
        self.close()

        if self.on_complete:
            self.on_complete(cropped, full_img, crop_box)

    def on_enter_pressed(self, event=None):
        full_img = self.original_img
        w, h = full_img.size
        self.close()
        if self.on_complete and full_img:
            self.on_complete(full_img, full_img, (0, 0, w, h))

    def on_escape_pressed(self, event=None):
        self.close()
        if self.on_cancel:
            self.on_cancel()

    def close(self):
        if self.win:
            self.win.destroy()
            self.win = None
        self.original_img = None
        self.dimmed_img = None
        self.tk_dimmed = None
        self.tk_bright = None
        self.canvas = None
