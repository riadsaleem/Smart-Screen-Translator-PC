"""
Theme engine and color palette management for Smart Screen Translator PC.
Provides cohesive dark mode and light mode palettes, rounded rectangle generation,
color tint/gradient blending, and Win32 taskbar & window icon management.
"""

import os
import sys
import ctypes
from PIL import Image, ImageDraw, ImageTk

THEMES = {
    "dark": {
        "name": "dark",
        "bg": "#14161f",            # Deep background
        "header_bg": "#1a1d29",     # Top banner / header
        "header_fg": "#89b4fa",     # Header title accent
        "header_sub": "#9399b2",    # Header subtitle
        "card_bg": "#1e2230",       # Content card background
        "card_border": "#2c3145",   # Card border
        "card_border_focus": "#89b4fa",
        "card_hover": "#252b3d",
        "primary": "#3b82f6",       # Vibrant accent blue
        "primary_fg": "#ffffff",    # White text on primary
        "primary_hover": "#60a5fa",
        "primary_pressed": "#2563eb",# Color shift on press without size jump
        "secondary_bg": "#282d3f",  # Secondary button bg
        "secondary_fg": "#cdd6f4",
        "secondary_hover": "#363d55",
        "secondary_pressed": "#1f2331",
        "text_primary": "#f1f5f9",  # Main text
        "text_secondary": "#94a3b8",# Muted text
        "text_dim": "#64748b",      # Dim / hint text
        "nav_bg": "#14161f",        # Tab bar background
        "nav_item_bg": "#1e2230",   # Inactive tab background
        "nav_item_border": "#2c3145",
        "nav_item_hover_bg": "#282e42",
        "nav_item_pressed_bg": "#1a1e2d",
        "nav_item_active_bg": "#1d2e4a", # Active tab background
        "nav_item_active_border": "#3b82f6",
        "nav_item_active_fg": "#60a5fa",
        "nav_item_fg": "#94a3b8",
        "success": "#22c55e",
        "danger": "#ef4444",
        "input_bg": "#181b26",
        "input_fg": "#60a5fa",
        "input_border": "#333a52",
        "preset_bg": "#222736",
        "preset_fg": "#cbd5e1",
        "preset_hover": "#2e3549",
        "preset_pressed": "#1a1e2a",
        "status_badge_bg": "#181b26",
        "theme_toggle_icon": "sun",  # Shows Sun in Dark mode
        "theme_toggle_color": "#fbbf24",
        "theme_toggle_bg": "#262b3b",
        "theme_toggle_hover": "#32394e",
        "theme_toggle_pressed": "#1b1f2b",
    },
    "light": {
        "name": "light",
        "bg": "#f1f5f9",            # Clean soft light slate background
        "header_bg": "#ffffff",     # Pure white header
        "header_fg": "#1d4ed8",     # Royal blue accent
        "header_sub": "#64748b",    # Subtitle slate
        "card_bg": "#ffffff",       # Pure white card surface
        "card_border": "#e2e8f0",   # Soft subtle border
        "card_border_focus": "#2563eb",
        "card_hover": "#f8fafc",
        "primary": "#2563eb",       # Professional blue
        "primary_fg": "#ffffff",    # White text on primary
        "primary_hover": "#1d4ed8",
        "primary_pressed": "#1e40af",# Color shift on press without size jump
        "secondary_bg": "#e2e8f0",  # Soft slate secondary
        "secondary_fg": "#1e293b",
        "secondary_hover": "#cbd5e1",
        "secondary_pressed": "#94a3b8",
        "text_primary": "#0f172a",  # Deep slate readable text
        "text_secondary": "#475569",# Slate body text
        "text_dim": "#94a3b8",      # Muted grey text
        "nav_bg": "#f1f5f9",
        "nav_item_bg": "#ffffff",
        "nav_item_border": "#cbd5e1",
        "nav_item_hover_bg": "#f8fafc",
        "nav_item_pressed_bg": "#e2e8f0",
        "nav_item_active_bg": "#dbeafe", # Soft blue tint active tab
        "nav_item_active_border": "#2563eb",
        "nav_item_active_fg": "#1d4ed8",
        "nav_item_fg": "#64748b",
        "success": "#16a34a",
        "danger": "#dc2626",
        "input_bg": "#ffffff",
        "input_fg": "#1d4ed8",
        "input_border": "#94a3b8",
        "preset_bg": "#e2e8f0",
        "preset_fg": "#1e293b",
        "preset_hover": "#cbd5e1",
        "preset_pressed": "#94a3b8",
        "status_badge_bg": "#f8fafc",
        "theme_toggle_icon": "moon", # Shows Moon in Light mode
        "theme_toggle_color": "#4f46e5",
        "theme_toggle_bg": "#e2e8f0",
        "theme_toggle_hover": "#cbd5e1",
        "theme_toggle_pressed": "#94a3b8",
    }
}

_ROUNDED_RECT_CACHE = {}
_CHECKBOX_CACHE = {}
_CURRENT_ACTIVE_THEME = "dark"


def set_current_theme(theme_name):
    """Sets the active UI theme name globally."""
    global _CURRENT_ACTIVE_THEME
    if theme_name in THEMES:
        _CURRENT_ACTIVE_THEME = theme_name


def get_current_theme():
    """Returns the current active UI theme name."""
    return _CURRENT_ACTIVE_THEME


def clear_theme_caches():
    """Clears cached rounded rectangle and checkbox PIL/Tkinter images."""
    _ROUNDED_RECT_CACHE.clear()
    _CHECKBOX_CACHE.clear()


def get_theme(theme_name="dark"):
    set_current_theme(theme_name)
    return THEMES.get(theme_name, THEMES["dark"])


def blend_color(hex1, hex2, factor=0.15):
    """
    Blends two hex colors by a factor (0.0 = all hex1, 1.0 = all hex2).
    Useful for generating dynamic pressed/hover shades.
    """
    try:
        h1 = hex1.lstrip("#")
        h2 = hex2.lstrip("#")
        r1, g1, b1 = int(h1[0:2], 16), int(h1[2:4], 16), int(h1[4:6], 16)
        r2, g2, b2 = int(h2[0:2], 16), int(h2[2:4], 16), int(h2[4:6], 16)
        r = int(r1 * (1 - factor) + r2 * factor)
        g = int(g1 * (1 - factor) + g2 * factor)
        b = int(b1 * (1 - factor) + b2 * factor)
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return hex1


def to_hex_color(widget, col):
    """
    Safely converts any Tkinter color (including SystemButtonFace, SystemWindow,
    named colors like 'white', or hex) into a valid #rrggbb string.
    """
    default_bg = THEMES.get(get_current_theme(), THEMES["dark"])["bg"]
    if not col:
        return default_bg
    if isinstance(col, str) and col.startswith("#") and len(col) in (7, 4):
        if len(col) == 4:
            return "#" + "".join(c * 2 for c in col[1:])
        return col
    try:
        if widget and hasattr(widget, "winfo_rgb"):
            r, g, b = widget.winfo_rgb(col)
            return f"#{r >> 8:02x}{g >> 8:02x}{b >> 8:02x}"
    except Exception:
        pass
    return default_bg


def hex_to_rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    except Exception:
        return (20, 22, 31)


def blend_rgb(c1, c2, f):
    return tuple(int(a + (b - a) * f) for a, b in zip(c1, c2))


def create_rounded_rect_image(
    width,
    height,
    radius,
    fill_color,
    border_color=None,
    border_width=1,
    parent_bg=None,
    gradient_bottom=None
):
    """
    Renders a high-quality anti-aliased rounded rectangle image using Pillow supersampling.
    - If parent_bg is given, composites corners against parent_bg for 100% clean anti-aliasing in Tkinter GDI.
    - If gradient_bottom is given, renders a smooth vertical linear gradient.
    - Fully cached for maximum responsiveness.
    """
    width = max(4, int(width))
    height = max(4, int(height))
    radius = max(0, int(radius))
    border_width = max(0, int(border_width))

    pbg = parent_bg or THEMES.get(get_current_theme(), THEMES["dark"])["bg"]
    key = (width, height, radius, fill_color, gradient_bottom, border_color, border_width, pbg)
    if key in _ROUNDED_RECT_CACHE:
        return _ROUNDED_RECT_CACHE[key]

    scale = 4
    sw, sh = width * scale, height * scale
    sbw = border_width * scale
    sr = min(radius * scale, sw // 2, sh // 2)

    p_rgb = hex_to_rgb(pbg)
    t_rgb = hex_to_rgb(fill_color)
    b_rgb = hex_to_rgb(gradient_bottom) if gradient_bottom else t_rgb

    # 1. 1D Gradient column
    col = Image.new("RGB", (1, sh))
    for y in range(sh):
        factor = y / max(1, sh - 1)
        col.putpixel((0, y), blend_rgb(t_rgb, b_rgb, factor))
    grad = col.resize((sw, sh), Image.Resampling.BILINEAR)

    # 2. Base canvas with parent_bg
    base = Image.new("RGB", (sw, sh), p_rgb)
    d = ImageDraw.Draw(base)

    if border_color and border_width > 0:
        bor_rgb = hex_to_rgb(border_color)
        d.rounded_rectangle([0, 0, sw - 1, sh - 1], radius=sr, fill=bor_rgb)

        # Inner mask
        x0, y0 = sbw, sbw
        x1, y1 = max(x0, sw - 1 - sbw), max(y0, sh - 1 - sbw)
        inner_r = max(0, min(sr - sbw, (x1 - x0) // 2, (y1 - y0) // 2))

        mask = Image.new("L", (sw, sh), 0)
        d_mask = ImageDraw.Draw(mask)
        d_mask.rounded_rectangle([x0, y0, x1, y1], radius=inner_r, fill=255)
        base.paste(grad, (0, 0), mask)
    else:
        mask = Image.new("L", (sw, sh), 0)
        d_mask = ImageDraw.Draw(mask)
        d_mask.rounded_rectangle([0, 0, sw - 1, sh - 1], radius=sr, fill=255)
        base.paste(grad, (0, 0), mask)

    final_img = base.resize((width, height), Image.Resampling.LANCZOS)
    photo = ImageTk.PhotoImage(final_img)
    _ROUNDED_RECT_CACHE[key] = photo
    return photo


def create_checkbox_image(
    size=20,
    radius=6,
    checked=False,
    bg=None,
    border=None,
    active_top=None,
    active_bot=None,
    parent_bg=None
):
    """
    Renders an anti-aliased rounded checkbox icon (checked or unchecked)
    with smooth gradient fill, checkmark, and parent_bg blending.
    """
    theme = THEMES.get(get_current_theme(), THEMES["dark"])
    parent_bg = parent_bg or theme["card_bg"]
    bg = bg or theme["card_bg"]
    border = border or theme["card_border"]
    active_top = active_top or theme["primary"]
    active_bot = active_bot or theme["primary_pressed"]

    key = (size, radius, checked, bg, border, active_top, active_bot, parent_bg)
    if key in _CHECKBOX_CACHE:
        return _CHECKBOX_CACHE[key]

    scale = 4
    s = size * scale
    r = radius * scale
    sbw = int(1.5 * scale)

    p_rgb = hex_to_rgb(parent_bg)
    base = Image.new("RGB", (s, s), p_rgb)
    d = ImageDraw.Draw(base)

    if checked:
        # Gradient active background
        t_rgb = hex_to_rgb(active_top)
        b_rgb = hex_to_rgb(active_bot)
        col = Image.new("RGB", (1, s))
        for y in range(s):
            col.putpixel((0, y), blend_rgb(t_rgb, b_rgb, y / max(1, s - 1)))
        grad = col.resize((s, s), Image.Resampling.BILINEAR)

        mask = Image.new("L", (s, s), 0)
        md = ImageDraw.Draw(mask)
        md.rounded_rectangle([0, 0, s - 1, s - 1], radius=r, fill=255)
        base.paste(grad, (0, 0), mask)

        # Smooth checkmark
        bw = max(2, int(2.2 * scale))
        p1 = (int(0.26 * s), int(0.50 * s))
        p2 = (int(0.44 * s), int(0.70 * s))
        p3 = (int(0.76 * s), int(0.30 * s))
        d.line([p1, p2, p3], fill=(255, 255, 255), width=bw, joint="curve")
    else:
        # Rounded outline with background
        d.rounded_rectangle([0, 0, s - 1, s - 1], radius=r, fill=hex_to_rgb(border))
        d.rounded_rectangle([sbw, sbw, s - 1 - sbw, s - 1 - sbw], radius=max(0, r - sbw), fill=hex_to_rgb(bg))

    final_img = base.resize((size, size), Image.Resampling.LANCZOS)
    photo = ImageTk.PhotoImage(final_img)
    _CHECKBOX_CACHE[key] = photo
    return photo


def setup_process_app_id():
    """Sets explicit Windows AppUserModelID and notifies shell so taskbar displays the modern icon."""
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SmartScreenTranslator.PC.App.v2_3")
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
    except Exception:
        pass


def apply_window_icon(win, ico_path=None, png_path=None):
    """
    Applies multi-resolution window icons to ensure Windows taskbar and titlebar
    display the modern application icon cleanly without fallback or caching issues.
    """
    import tkinter as tk

    if not ico_path or not os.path.exists(ico_path):
        candidates = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico"),
            getattr(sys, "_MEIPASS", "") and os.path.join(sys._MEIPASS, "icon.ico")
        ]
        for c in candidates:
            if c and os.path.exists(c):
                ico_path = c
                break

    if not png_path or not os.path.exists(png_path):
        candidates = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.png"),
            getattr(sys, "_MEIPASS", "") and os.path.join(sys._MEIPASS, "icon.png")
        ]
        for c in candidates:
            if c and os.path.exists(c):
                png_path = c
                break

    # Tkinter iconbitmap
    if ico_path and os.path.exists(ico_path):
        try:
            win.iconbitmap(ico_path)
        except Exception:
            pass

    # Tkinter iconphoto (32-bit ARGB)
    if png_path and os.path.exists(png_path):
        try:
            photo = tk.PhotoImage(file=png_path)
            win.iconphoto(True, photo)
            win._applied_win_photo = photo
        except Exception:
            pass

    # Direct Win32 WM_SETICON & Class icon for immediate Windows taskbar sync
    if ico_path and os.path.exists(ico_path):
        try:
            IMAGE_ICON = 1
            LR_LOADFROMFILE = 0x00000010
            GA_ROOT = 2
            GCLP_HICON = -14
            GCLP_HICONSM = -34

            # Explicit 48x48 icon for Windows Taskbar / Alt-Tab
            hicon_big = ctypes.windll.user32.LoadImageW(0, ico_path, IMAGE_ICON, 48, 48, LR_LOADFROMFILE)
            # Explicit 16x16 icon for Titlebar / System menu
            hicon_small = ctypes.windll.user32.LoadImageW(0, ico_path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)

            if hicon_big or hicon_small:
                win.update_idletasks()
                hwnd = win.winfo_id()
                root_hwnd = ctypes.windll.user32.GetAncestor(hwnd, GA_ROOT)
                target_hwnd = root_hwnd if root_hwnd else hwnd

                if hicon_big:
                    ctypes.windll.user32.SendMessageW(target_hwnd, 0x0080, 1, hicon_big) # ICON_BIG
                    if hasattr(ctypes.windll.user32, "SetClassLongPtrW"):
                        ctypes.windll.user32.SetClassLongPtrW(target_hwnd, GCLP_HICON, hicon_big)
                if hicon_small:
                    ctypes.windll.user32.SendMessageW(target_hwnd, 0x0080, 0, hicon_small) # ICON_SMALL
                    if hasattr(ctypes.windll.user32, "SetClassLongPtrW"):
                        ctypes.windll.user32.SetClassLongPtrW(target_hwnd, GCLP_HICONSM, hicon_small)

            ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
        except Exception:
            pass
