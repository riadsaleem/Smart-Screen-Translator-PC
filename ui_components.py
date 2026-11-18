"""
Modern UI components with rounded corners, custom dropdowns, vector icons,
and responsive theme styling for Smart Screen Translator PC.
"""

import time
import ctypes
import tkinter as tk
from ui_icons import get_icon_photo
from ui_theme import get_theme, get_current_theme, create_rounded_rect_image, create_checkbox_image, blend_color, to_hex_color


class ModernButton(tk.Canvas):
    """
    True rounded capsule/pill button rendered with 4x anti-aliased PIL images:
    - Displays optional high-res vector icon and label text.
    - Responsive hover feedback.
    - Rich pressed color tint/gradient feedback ('يتغير تدرج لونا عند الضغط عليها بدون ما يكبر حجمها').
    - Zero size change or jitter on press/hover.
    """
    def __init__(
        self,
        parent,
        text="",
        icon_name=None,
        command=None,
        width=120,
        height=36,
        radius=14,
        bg=None,
        fg=None,
        gradient_bottom=None,
        hover_bg=None,
        pressed_bg=None,
        border_color=None,
        border_width=1,
        parent_bg=None,
        font=("Segoe UI", 9, "bold"),
        cursor="hand2",
        **kwargs
    ):
        self.btn_width = max(24, int(width))
        self.btn_height = max(24, int(height))
        self.radius = max(0, int(radius))
        self.border_width = max(0, int(border_width))

        self.btn_text = text
        self.icon_name = icon_name
        self.command = command
        self.custom_font = font

        # Theme fallback colors
        self.bg_color = bg or "#282d3f"
        self.fg_color = fg or "#cdd6f4"
        self.gradient_bottom = gradient_bottom or blend_color(self.bg_color, "#000000", 0.12)
        self.hover_bg = hover_bg or blend_color(self.bg_color, "#ffffff", 0.14)
        self.hover_bottom = blend_color(self.gradient_bottom, "#ffffff", 0.10)
        self.pressed_bg = pressed_bg or blend_color(self.bg_color, "#000000", 0.20)
        self.pressed_bottom = blend_color(self.gradient_bottom, "#000000", 0.25)
        self.border_color = border_color
        
        if parent_bg:
            self.parent_bg = to_hex_color(parent, parent_bg)
        elif hasattr(parent, "card_bg"):
            self.parent_bg = to_hex_color(parent, parent.card_bg)
        elif hasattr(parent, "cget"):
            self.parent_bg = to_hex_color(parent, parent.cget("bg"))
        else:
            self.parent_bg = to_hex_color(parent, None)

        super().__init__(
            parent,
            width=self.btn_width,
            height=self.btn_height,
            highlightthickness=0,
            bg=self.parent_bg,
            cursor=cursor,
            **kwargs
        )
        self.pack_propagate(False)

        self.state = "normal"  # normal, hover, pressed
        self._bg_items = {}
        self._draw_button()

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    def _get_bg_image(self, state):
        if state == "pressed":
            fill = self.pressed_bg
            bot = self.pressed_bottom
            border = self.border_color
        elif state == "hover":
            fill = self.hover_bg
            bot = self.hover_bottom
            border = self.border_color
        else:
            fill = self.bg_color
            bot = self.gradient_bottom
            border = self.border_color

        return create_rounded_rect_image(
            self.btn_width,
            self.btn_height,
            self.radius,
            fill,
            border,
            self.border_width,
            parent_bg=self.parent_bg,
            gradient_bottom=bot
        )

    def _draw_button(self):
        self.delete("all")
        if self.cget("bg") != self.parent_bg:
            super().configure(bg=self.parent_bg)
        # 1. Background image with true rounded corners
        img = self._get_bg_image(self.state)
        self.bg_img_ref = img
        self.create_image(0, 0, anchor="nw", image=img, tags="bg")

        cx = self.btn_width / 2.0
        cy = self.btn_height / 2.0

        # Calculate positioning for icon + text
        has_icon = bool(self.icon_name)
        has_text = bool(self.btn_text)

        if has_icon and has_text:
            icon_size = max(14, int(self.btn_height * 0.44))
            icon_img = get_icon_photo(self.icon_name, size=icon_size, color=self.fg_color)
            self.icon_img_ref = icon_img

            # RTL layout: Icon on right, text on left
            offset = 8
            self.create_text(
                cx - offset,
                cy,
                text=self.btn_text,
                fill=self.fg_color,
                font=self.custom_font,
                anchor="center",
                tags="fg"
            )
            # Find right side of text to place icon
            bbox = self.bbox("fg")
            icon_x = (bbox[2] + icon_size / 2.0 + 6) if bbox else (cx + 20)
            if icon_x > self.btn_width - icon_size / 2.0 - 4:
                icon_x = self.btn_width - icon_size / 2.0 - 4
            self.create_image(icon_x, cy, image=icon_img, tags="icon")

        elif has_icon and not has_text:
            icon_size = max(16, int(self.btn_height * 0.50))
            icon_img = get_icon_photo(self.icon_name, size=icon_size, color=self.fg_color)
            self.icon_img_ref = icon_img
            self.create_image(cx, cy, image=icon_img, tags="icon")

        elif has_text:
            self.create_text(
                cx,
                cy,
                text=self.btn_text,
                fill=self.fg_color,
                font=self.custom_font,
                anchor="center",
                tags="fg"
            )

    def _on_enter(self, e):
        if getattr(self, "config_state", "normal") == "disabled":
            return
        self.state = "hover"
        img = self._get_bg_image("hover")
        self.bg_img_ref = img
        self.itemconfig("bg", image=img)

    def _on_leave(self, e):
        if getattr(self, "config_state", "normal") == "disabled":
            return
        self.state = "normal"
        img = self._get_bg_image("normal")
        self.bg_img_ref = img
        self.itemconfig("bg", image=img)

    def _on_press(self, e):
        if getattr(self, "config_state", "normal") == "disabled":
            return
        self.state = "pressed"
        img = self._get_bg_image("pressed")
        self.bg_img_ref = img
        self.itemconfig("bg", image=img)

    def _on_release(self, e):
        if getattr(self, "config_state", "normal") == "disabled":
            return
        if self.state == "pressed":
            self.state = "hover"
            img = self._get_bg_image("hover")
            self.bg_img_ref = img
            self.itemconfig("bg", image=img)
            if self.command:
                self.command()

    def update_colors(self, bg=None, fg=None, hover_bg=None, pressed_bg=None, border_color=None, parent_bg=None):
        if bg: self.bg_color = bg
        if fg: self.fg_color = fg
        if hover_bg: self.hover_bg = hover_bg
        if pressed_bg: self.pressed_bg = pressed_bg
        if border_color is not None: self.border_color = border_color
        if parent_bg:
            self.parent_bg = to_hex_color(self.master, parent_bg)
            super().configure(bg=self.parent_bg)
        self._draw_button()

    def update_parent_bg(self, parent_bg=None):
        """Refreshes parent_bg and redraws button."""
        if parent_bg:
            self.parent_bg = to_hex_color(self.master, parent_bg)
        elif hasattr(self.master, "card_bg"):
            self.parent_bg = to_hex_color(self.master, self.master.card_bg)
        elif hasattr(self.master, "cget"):
            self.parent_bg = to_hex_color(self.master, self.master.cget("bg"))
        else:
            self.parent_bg = to_hex_color(self.master, None)
        super().configure(bg=self.parent_bg)
        self._draw_button()

    def update_theme(self, theme_name_or_dict, parent_bg=None):
        """Updates button theme palette and parent_bg seamlessly."""
        theme = theme_name_or_dict if isinstance(theme_name_or_dict, dict) else get_theme(theme_name_or_dict)
        if parent_bg:
            self.parent_bg = to_hex_color(self.master, parent_bg)
        elif hasattr(self.master, "card_bg"):
            self.parent_bg = to_hex_color(self.master, self.master.card_bg)
        elif hasattr(self.master, "cget"):
            self.parent_bg = to_hex_color(self.master, self.master.cget("bg"))
        else:
            self.parent_bg = to_hex_color(self.master, None)
        super().configure(bg=self.parent_bg)
        self._draw_button()

    def set_state_content(self, text=None, icon_name=None, bg=None, fg=None):
        if text is not None: self.btn_text = text
        if icon_name is not None: self.icon_name = icon_name
        if bg:
            self.bg_color = bg
            self.hover_bg = blend_color(bg, "#ffffff", 0.08)
            self.pressed_bg = blend_color(bg, "#000000", 0.15)
        if fg: self.fg_color = fg
        self._draw_button()

    def configure(self, **kwargs):
        redraw = False
        if "text" in kwargs:
            self.btn_text = kwargs.pop("text")
            redraw = True
        if "image" in kwargs:
            img_val = kwargs.pop("image")
            if isinstance(img_val, str):
                self.icon_name = img_val if img_val else None
            elif not img_val:
                self.icon_name = None
            redraw = True
        if "icon_name" in kwargs:
            self.icon_name = kwargs.pop("icon_name")
            redraw = True
        if "bg" in kwargs:
            self.bg_color = kwargs.pop("bg")
            self.hover_bg = blend_color(self.bg_color, "#ffffff", 0.08)
            self.pressed_bg = blend_color(self.bg_color, "#000000", 0.15)
            redraw = True
        if "parent_bg" in kwargs:
            self.parent_bg = to_hex_color(self.master, kwargs.pop("parent_bg"))
            super().configure(bg=self.parent_bg)
            redraw = True
        if "fg" in kwargs:
            self.fg_color = kwargs.pop("fg")
            redraw = True
        if "border_color" in kwargs:
            self.border_color = kwargs.pop("border_color")
            redraw = True
        if "state" in kwargs:
            st = kwargs.pop("state")
            if st == "disabled":
                self.config_state = "disabled"
                self.config(cursor="")
            else:
                self.config_state = "normal"
                self.config(cursor="hand2")
            redraw = True
        if "command" in kwargs:
            self.command = kwargs.pop("command")
        if redraw:
            self._draw_button()
        if kwargs:
            super().configure(**kwargs)

    def config(self, **kwargs):
        return self.configure(**kwargs)


class ModernCard(tk.Canvas):
    """
    Modern container card with true rounded visual corners, subtle border,
    and dynamic auto-height container.
    """
    def __init__(
        self,
        parent,
        title=None,
        theme_name="dark",
        radius=16,
        padx=16,
        pady=14,
        bg=None,
        border=None,
        parent_bg=None,
        **kwargs
    ):
        self.theme = get_theme(theme_name)
        self.radius = radius
        self.pad_x = padx
        self.pad_y = pady
        self.card_bg = bg or self.theme["card_bg"]
        self.border_color = border or self.theme["card_border"]
        raw_pbg = parent_bg or (parent.cget("bg") if hasattr(parent, "cget") else self.theme["bg"])
        self.parent_bg = to_hex_color(parent, raw_pbg)
        self.title_text = title
        self._bg_img = None

        kwargs.pop("bg", None)
        kwargs.pop("background", None)
        kwargs.pop("highlightthickness", None)
        kwargs.pop("bd", None)

        super().__init__(parent, bg=self.parent_bg, highlightthickness=0, bd=0, **kwargs)

        self.body = tk.Frame(self, bg=self.card_bg)
        self.inner = self.body  # alias

        if self.title_text:
            self.title_lbl = tk.Label(
                self.body,
                text=self.title_text,
                font=("Segoe UI", 9, "bold"),
                fg=self.theme["primary"],
                bg=self.card_bg,
                anchor=tk.E,
                justify=tk.RIGHT
            )
            self.title_lbl.pack(fill=tk.X, pady=(0, 10))

        self.win_id = self.create_window(self.pad_x, self.pad_y, window=self.body, anchor="nw")
        self.body.bind("<Configure>", self._on_body_cfg)
        self.bind("<Configure>", self._on_canvas_cfg)

    def _on_body_cfg(self, evt=None):
        req_h = self.body.winfo_reqheight() + (self.pad_y * 2)
        self.config(height=req_h)
        self._redraw_bg()

    def _on_canvas_cfg(self, evt):
        w = max(10, evt.width - (self.pad_x * 2))
        self.itemconfigure(self.win_id, width=w)
        self._redraw_bg()

    def _redraw_bg(self):
        w = self.winfo_width()
        h = self.winfo_height()
        if w > 10 and h > 10:
            self._bg_img = create_rounded_rect_image(
                w,
                h,
                self.radius,
                self.card_bg,
                self.border_color,
                1,
                self.parent_bg
            )
            self.delete("bg_rect")
            self.create_image(0, 0, anchor="nw", image=self._bg_img, tags="bg_rect")
            self.tag_lower("bg_rect")

    def update_theme(self, theme_name):
        self.theme = get_theme(theme_name)
        self.card_bg = self.theme["card_bg"]
        self.border_color = self.theme["card_border"]
        self.parent_bg = self.theme["bg"]
        self.config(bg=self.parent_bg)
        self.body.config(bg=self.card_bg)
        if hasattr(self, "title_lbl"):
            self.title_lbl.config(
                bg=self.card_bg,
                fg=self.theme["primary"]
            )
        self._redraw_bg()


class ModernEntry(tk.Canvas):
    """
    True rounded entry input with supersampled anti-aliased border,
    dynamic focus glow, and smooth padding.
    """
    def __init__(
        self,
        parent,
        width=240,
        height=36,
        radius=12,
        bg=None,
        fg=None,
        border_color=None,
        focus_border=None,
        parent_bg=None,
        font=("Segoe UI", 10),
        justify="left",
        **kwargs
    ):
        theme = get_theme(get_current_theme())
        self.w = max(40, int(width))
        self.h = max(24, int(height))
        self.radius = max(2, int(radius))
        self.bg_color = bg or theme["input_bg"]
        self.fg_color = fg or theme["input_fg"]
        self.border_color = border_color or theme["input_border"]
        self.focus_border = focus_border or theme["primary"]

        if parent_bg:
            self.parent_bg = to_hex_color(parent, parent_bg)
        elif hasattr(parent, "card_bg"):
            self.parent_bg = to_hex_color(parent, parent.card_bg)
        elif hasattr(parent, "cget"):
            self.parent_bg = to_hex_color(parent, parent.cget("bg"))
        else:
            self.parent_bg = to_hex_color(parent, theme["card_bg"])

        self.font = font
        self.is_focused = False
        self._bg_img = None

        super().__init__(parent, width=self.w, height=self.h, bg=self.parent_bg, highlightthickness=0, bd=0, **kwargs)
        self.pack_propagate(False)

        disabled_fg = blend_color(self.fg_color, self.bg_color, 0.45)
        self.entry = tk.Entry(
            self,
            font=self.font,
            bg=self.bg_color,
            fg=self.fg_color,
            disabledbackground=self.bg_color,
            disabledforeground=disabled_fg,
            readonlybackground=self.bg_color,
            bd=0,
            highlightthickness=0,
            insertbackground=self.focus_border,
            justify=justify
        )
        pad_x = max(10, self.radius)
        entry_w = max(10, self.w - (pad_x * 2))
        entry_h = max(16, self.h - 10)
        entry_y = (self.h - entry_h) // 2

        self.entry_win = self.create_window(pad_x, entry_y, window=self.entry, anchor="nw", width=entry_w, height=entry_h)

        self.entry.bind("<FocusIn>", self._on_focus_in)
        self.entry.bind("<FocusOut>", self._on_focus_out)
        self.bind("<Button-1>", lambda e: self.entry.focus_set())
        self.bind("<Configure>", self._on_configure)
        self._draw_bg()

    def _draw_bg(self):
        w = max(10, self.winfo_width() if self.winfo_width() > 10 else self.w)
        h = max(10, self.winfo_height() if self.winfo_height() > 10 else self.h)
        if self.cget("bg") != self.parent_bg:
            super().config(bg=self.parent_bg)
        bor = self.focus_border if self.is_focused else self.border_color
        bw = 2 if self.is_focused else 1
        self._bg_img = create_rounded_rect_image(w, h, self.radius, self.bg_color, bor, bw, self.parent_bg)
        super().delete("bg_img")
        self.create_image(0, 0, anchor="nw", image=self._bg_img, tags="bg_img")
        self.tag_lower("bg_img")

    def _on_focus_in(self, e):
        self.is_focused = True
        self._draw_bg()

    def _on_focus_out(self, e):
        self.is_focused = False
        self._draw_bg()

    def _on_configure(self, e):
        pad_x = max(10, self.radius)
        w = max(10, e.width - (pad_x * 2))
        self.itemconfigure(self.entry_win, width=w)
        self._draw_bg()

    def get(self):
        return self.entry.get()

    def insert(self, idx, s):
        self.entry.insert(idx, s)

    def delete(self, first, last=None):
        if isinstance(first, str) and first in ("bg_img", "all") and last is None:
            super().delete(first)
        else:
            self.entry.delete(first, last)

    def focus(self):
        self.entry.focus()

    def focus_set(self):
        self.entry.focus_set()

    def focus_force(self):
        self.entry.focus_force()

    def select_range(self, start, end):
        self.entry.select_range(start, end)

    def xview(self, *args):
        return self.entry.xview(*args)

    def xview_moveto(self, fraction):
        self.entry.xview_moveto(fraction)

    def config(self, **kwargs):
        if "state" in kwargs:
            st = kwargs.pop("state")
            if st == "disabled":
                disabled_fg = blend_color(self.fg_color, self.bg_color, 0.45)
                self.entry.config(
                    state=st,
                    disabledbackground=self.bg_color,
                    disabledforeground=disabled_fg
                )
            elif st == "readonly":
                self.entry.config(
                    state=st,
                    readonlybackground=self.bg_color
                )
            else:
                self.entry.config(
                    state=st,
                    bg=self.bg_color,
                    fg=self.fg_color
                )
        if "bg" in kwargs:
            self.bg_color = kwargs.pop("bg")
            self.entry.config(
                bg=self.bg_color,
                disabledbackground=self.bg_color,
                readonlybackground=self.bg_color
            )
            self._draw_bg()
        if "fg" in kwargs:
            self.fg_color = kwargs.pop("fg")
            self.entry.config(fg=self.fg_color)
        if "border_color" in kwargs:
            self.border_color = kwargs.pop("border_color")
            self._draw_bg()
        if "focus_border" in kwargs:
            self.focus_border = kwargs.pop("focus_border")
            self._draw_bg()
        if "parent_bg" in kwargs:
            self.parent_bg = to_hex_color(self.master, kwargs.pop("parent_bg"))
            super().config(bg=self.parent_bg)
            self._draw_bg()
        if kwargs:
            super().config(**kwargs)

    def configure(self, **kwargs):
        return self.config(**kwargs)


class ModernCheckbox(tk.Frame):
    """
    True rounded checkbox widget (radius 6px) with anti-aliased checkmark,
    gradient fill when active, and full label click support.
    """
    def __init__(
        self,
        parent,
        text="",
        variable=None,
        command=None,
        bg=None,
        fg=None,
        active_top="#3b82f6",
        active_bot="#1d4ed8",
        border_color="#45475a",
        box_size=20,
        radius=6,
        font=("Segoe UI", 9),
        rtl=True,
        **kwargs
    ):
        if bg:
            raw_pbg = bg
        elif hasattr(parent, "card_bg"):
            raw_pbg = parent.card_bg
        elif hasattr(parent, "cget"):
            raw_pbg = parent.cget("bg")
        else:
            raw_pbg = "#181825"
        self.parent_bg = to_hex_color(parent, raw_pbg)
        super().__init__(parent, bg=self.parent_bg, cursor="hand2", **kwargs)

        self.text = text
        self.variable = variable if variable is not None else tk.BooleanVar(value=False)
        self.command = command
        self.fg_color = fg or "#cdd6f4"
        self.active_top = active_top
        self.active_bot = active_bot
        self.border_color = border_color
        self.box_size = box_size
        self.radius = radius
        self.font = font
        self.rtl = rtl

        self.box_canvas = tk.Canvas(
            self,
            width=self.box_size,
            height=self.box_size,
            bg=self.parent_bg,
            highlightthickness=0,
            bd=0,
            cursor="hand2"
        )

        self.lbl = tk.Label(
            self,
            text=self.text,
            font=self.font,
            fg=self.fg_color,
            bg=self.parent_bg,
            cursor="hand2",
            justify=tk.RIGHT if self.rtl else tk.LEFT
        )

        if self.rtl:
            self.box_canvas.pack(side=tk.RIGHT, padx=(8, 0))
            self.lbl.pack(side=tk.RIGHT)
        else:
            self.box_canvas.pack(side=tk.LEFT, padx=(0, 8))
            self.lbl.pack(side=tk.LEFT)

        for w in (self, self.box_canvas, self.lbl):
            w.bind("<Button-1>", self._on_click)

        self._update_icon()

    def _update_icon(self):
        is_chk = bool(self.variable.get())
        img = create_checkbox_image(
            size=self.box_size,
            radius=self.radius,
            checked=is_chk,
            bg=blend_color(self.parent_bg, "#ffffff", 0.05),
            border=self.border_color,
            active_top=self.active_top,
            active_bot=self.active_bot,
            parent_bg=self.parent_bg
        )
        self._box_img = img
        self.box_canvas.delete("all")
        self.box_canvas.create_image(0, 0, anchor="nw", image=img)

    def _on_click(self, evt=None):
        self.variable.set(not self.variable.get())
        self._update_icon()
        if self.command:
            self.command()

    def get(self):
        return self.variable.get()

    def set(self, val):
        self.variable.set(bool(val))
        self._update_icon()


class ModernRadioGroup(tk.Frame):
    """
    Modern pill-shaped rounded radio button selection group.
    """
    def __init__(
        self,
        parent,
        options,
        variable,
        command=None,
        theme_name="dark",
        **kwargs
    ):
        self.theme = get_theme(theme_name)
        raw_pbg = parent.cget("bg") if hasattr(parent, "cget") else self.theme["card_bg"]
        self.parent_bg = to_hex_color(parent, raw_pbg)
        super().__init__(parent, bg=self.parent_bg, **kwargs)

        self.options = options  # list of (val, label)
        self.variable = variable
        self.command = command
        self.buttons = []

        for val, label in self.options:
            btn = self._create_option_button(val, label)
            btn.pack(fill=tk.X, pady=3)
            self.buttons.append((val, btn))

    def _create_option_button(self, val, label):
        c = tk.Canvas(self, height=36, bg=self.parent_bg, highlightthickness=0, cursor="hand2")
        c.pack_propagate(False)

        def redraw(state="normal"):
            w = max(10, c.winfo_width() if c.winfo_width() > 10 else 320)
            h = 36
            active = (self.variable.get() == val)
            if active:
                fill = blend_color(self.theme["primary"], "#ffffff", 0.08)
                bot = self.theme["primary"]
                bor = blend_color(self.theme["primary"], "#ffffff", 0.30)
                text_fg = "#ffffff"
            elif state == "hover":
                fill = blend_color(self.theme["card_bg"], "#ffffff", 0.08)
                bot = self.theme["card_bg"]
                bor = self.theme["primary"]
                text_fg = self.theme["text_primary"]
            else:
                fill = blend_color(self.theme["card_bg"], "#000000", 0.05)
                bot = fill
                bor = self.theme["card_border"]
                text_fg = self.theme["text_secondary"]

            img = create_rounded_rect_image(w, h, 12, fill, bor, 1, self.parent_bg, bot)
            c._img = img
            c.delete("all")
            c.create_image(0, 0, anchor="nw", image=img)

            # Circular indicator on right
            dot_x = w - 22
            dot_y = h / 2.0
            if active:
                c.create_oval(dot_x - 7, dot_y - 7, dot_x + 7, dot_y + 7, fill="#ffffff", outline="")
            else:
                c.create_oval(dot_x - 7, dot_y - 7, dot_x + 7, dot_y + 7, fill="", outline=bor, width=1.5)

            # Text label
            c.create_text(dot_x - 14, dot_y, text=label, fill=text_fg, font=("Segoe UI", 8, "bold" if active else "normal"), anchor=tk.E)

        def on_enter(e):
            redraw("hover")

        def on_leave(e):
            redraw("normal")

        def on_click(e):
            self.variable.set(val)
            self._update_all()
            if self.command:
                self.command(val)

        c.bind("<Enter>", on_enter)
        c.bind("<Leave>", on_leave)
        c.bind("<Button-1>", on_click)
        c.bind("<Configure>", lambda e: redraw())
        c._redraw = redraw
        return c

    def _update_all(self):
        for val, btn in self.buttons:
            if hasattr(btn, "_redraw"):
                btn._redraw()


class NavigationTabButton(tk.Canvas):
    """
    Modern rounded navigation tab button:
    - High-res vector icon (via PIL)
    - Clean typography
    - True capsule radius with subtle border
    - Active state with accent gradient/color
    - Smooth hover transitions and pressed color shift without size jitter
    """
    def __init__(self, parent, tab_id, icon_name, label, is_active=False, on_click=None, theme_name="dark", **kwargs):
        self.theme = get_theme(theme_name)
        self.tab_id = tab_id
        self.icon_name = icon_name
        self.label_text = label
        self.is_active = is_active
        self.on_click = on_click
        self.parent_bg = to_hex_color(parent, self.theme["nav_bg"])

        self.btn_width = 106
        self.btn_height = 36
        self.radius = 16
        self.border_width = 1

        super().__init__(
            parent,
            width=self.btn_width,
            height=self.btn_height,
            highlightthickness=0,
            bg=self.parent_bg,
            cursor="hand2",
            **kwargs
        )
        self.state = "normal"
        self._draw_tab()

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Configure>", self._on_configure)

    def _on_configure(self, event):
        if event.width > 20 and event.height > 10:
            if event.width != self.btn_width or event.height != self.btn_height:
                self.btn_width = event.width
                self.btn_height = event.height
                self._draw_tab()

    def _get_colors(self, state):
        if self.is_active:
            bg = self.theme["nav_item_active_bg"]
            border = self.theme["nav_item_active_border"]
            fg = self.theme["nav_item_active_fg"]
            if state == "pressed":
                bg = blend_color(bg, "#000000", 0.15)
        else:
            if state == "pressed":
                bg = self.theme["nav_item_pressed_bg"]
                border = self.theme["nav_item_border"]
                fg = self.theme["text_primary"]
            elif state == "hover":
                bg = self.theme["nav_item_hover_bg"]
                border = self.theme["card_border_focus"]
                fg = self.theme["text_primary"]
            else:
                bg = self.theme["nav_item_bg"]
                border = self.theme["nav_item_border"]
                fg = self.theme["nav_item_fg"]
        return bg, border, fg

    def _draw_tab(self):
        self.delete("all")
        if self.cget("bg") != self.parent_bg:
            super().configure(bg=self.parent_bg)
        bg_col, border_col, fg_col = self._get_colors(self.state)

        img = create_rounded_rect_image(
            self.btn_width,
            self.btn_height,
            self.radius,
            bg_col,
            border_col,
            self.border_width,
            parent_bg=self.parent_bg
        )
        self.bg_img_ref = img
        self.create_image(0, 0, anchor="nw", image=img, tags="bg")

        cx = self.btn_width / 2.0
        cy = self.btn_height / 2.0

        # High-res icon
        icon_size = 18
        icon_img = get_icon_photo(self.icon_name, size=icon_size, color=fg_col)
        self.icon_img_ref = icon_img

        font_weight = "bold" if self.is_active else "normal"
        tab_font = ("Segoe UI", 8, font_weight)

        # RTL layout: Icon on right, label on left
        self.create_text(
            cx - 9,
            cy,
            text=self.label_text,
            fill=fg_col,
            font=tab_font,
            anchor="center",
            tags="fg"
        )
        bbox = self.bbox("fg")
        icon_x = (bbox[2] + icon_size / 2.0 + 4) if bbox else (cx + 26)
        if icon_x > self.btn_width - icon_size / 2.0 - 4:
            icon_x = self.btn_width - icon_size / 2.0 - 4
        self.create_image(icon_x, cy, image=icon_img, tags="icon")

    def _on_enter(self, e):
        self.state = "hover"
        self._draw_tab()

    def _on_leave(self, e):
        self.state = "normal"
        self._draw_tab()

    def _on_press(self, e):
        self.state = "pressed"
        self._draw_tab()

    def _on_release(self, e):
        if self.state == "pressed":
            self.state = "hover"
            self._draw_tab()
            if self.on_click:
                self.on_click(self.tab_id)

    def set_active(self, active):
        self.is_active = active
        self._draw_tab()

    def update_theme(self, theme_name):
        self.theme = get_theme(theme_name)
        self.parent_bg = to_hex_color(self.master, self.theme["nav_bg"])
        self.config(bg=self.parent_bg)
        self._draw_tab()


class ThemeToggleButton(tk.Canvas):
    """
    Sleek Moon/Sun icon-only toggle button for the header.
    - Shows Sun icon ☀️ in Dark mode (to switch to light)
    - Shows Moon icon 🌙 in Light mode (to switch to dark)
    - True rounded capsule border (radius=14)
    - Instant hover and pressed gradient feedback
    """
    def __init__(self, parent, current_theme="dark", on_toggle=None, radius=12, **kwargs):
        self.theme_name = current_theme
        self.theme = get_theme(current_theme)
        self.on_toggle = on_toggle
        self.btn_width = 38
        self.btn_height = 32
        self.radius = max(0, int(radius))
        self.border_width = 1
        raw_pbg = parent.cget("bg") if hasattr(parent, "cget") else self.theme["header_bg"]
        self.parent_bg = to_hex_color(parent, raw_pbg)

        super().__init__(
            parent,
            width=self.btn_width,
            height=self.btn_height,
            highlightthickness=0,
            bg=self.parent_bg,
            cursor="hand2",
            **kwargs
        )
        self.state = "normal"
        self._draw_toggle()

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    def _draw_toggle(self):
        self.delete("all")
        if self.cget("bg") != self.parent_bg:
            super().configure(bg=self.parent_bg)
        if self.state == "pressed":
            fill = self.theme["theme_toggle_pressed"]
            border = self.theme["primary"]
        elif self.state == "hover":
            fill = self.theme["theme_toggle_hover"]
            border = self.theme["primary"]
        else:
            fill = self.theme["theme_toggle_bg"]
            border = self.theme["card_border"]

        img = create_rounded_rect_image(
            self.btn_width,
            self.btn_height,
            self.radius,
            fill,
            border,
            self.border_width,
            parent_bg=self.parent_bg
        )
        self.bg_img_ref = img
        self.create_image(0, 0, anchor="nw", image=img, tags="bg")

        cx = self.btn_width / 2.0
        cy = self.btn_height / 2.0
        icon_name = self.theme["theme_toggle_icon"]
        icon_color = self.theme["theme_toggle_color"]
        icon_photo = get_icon_photo(icon_name, size=18, color=icon_color)
        self.icon_ref = icon_photo
        self.create_image(cx, cy, image=icon_photo, tags="icon")

    def _on_enter(self, e):
        self.state = "hover"
        self._draw_toggle()

    def _on_leave(self, e):
        self.state = "normal"
        self._draw_toggle()

    def _on_press(self, e):
        self.state = "pressed"
        self._draw_toggle()

    def _on_release(self, e):
        if self.state == "pressed":
            self.state = "hover"
            self.toggle()

    def set_theme(self, theme_name):
        self.theme_name = theme_name
        self.theme = get_theme(theme_name)
        raw_pbg = self.master.cget("bg") if hasattr(self.master, "cget") else self.theme["header_bg"]
        self.parent_bg = to_hex_color(self.master, raw_pbg)
        self.config(bg=self.parent_bg)
        self._draw_toggle()

    def toggle(self):
        new_theme = "light" if self.theme_name == "dark" else "dark"
        self.set_theme(new_theme)
        if self.on_toggle:
            self.on_toggle(new_theme)


class ModernLanguageDropdown(tk.Frame):
    """
    Sleek language dropdown matching modern UI standards:
    - Text perfectly centered in the horizontal middle of the rectangle (Dead Center)
    - Clean rounded chevron-down icon inside a subtle rounded capsule on the right (Image 2)
    - Toggle behavior: clicking the rectangle, text, or chevron opens/closes the dropdown smoothly
    - Dropdown popup opens right beneath the rectangle with matching width and rounded styling
    - Active item checkmark and smooth hover transitions
    - Auto-closes on outside click or Escape
    """
    def __init__(self, parent, languages_dict, current_code, on_change=None, theme_name="dark", **kwargs):
        self.theme = get_theme(theme_name)
        super().__init__(parent, bg=self.theme["card_bg"], **kwargs)

        self.languages_dict = languages_dict  # code -> display_name
        self.current_code = current_code
        self.on_change = on_change
        self.popup = None
        self._last_close_time = 0
        self._outside_bind_id = None

        self.setup_ui()

    def update_theme(self, theme_name):
        self.theme = get_theme(theme_name)
        self.config(bg=self.theme["card_bg"])
        self.card.config(
            bg=self.theme["card_bg"],
            highlightbackground=self.theme["card_border"],
            highlightcolor=self.theme["primary"]
        )
        self.lang_lbl.config(
            bg=self.theme["card_bg"],
            fg=self.theme["text_primary"]
        )
        self.chevron_capsule.config(
            bg=self.theme["secondary_bg"],
            highlightbackground=self.theme["card_border"]
        )
        self.chevron_lbl.config(
            bg=self.theme["secondary_bg"]
        )
        self.update_chevron_icon()

    def update_chevron_icon(self):
        icon = get_icon_photo("chevron_down", size=14, color=self.theme["primary"])
        self.chevron_lbl.config(image=icon)
        self.chevron_lbl.image = icon

    def setup_ui(self):
        # Outer Card with rounded visual appearance
        self.card = tk.Frame(
            self,
            bg=self.theme["card_bg"],
            bd=0,
            highlightthickness=1,
            highlightbackground=self.theme["card_border"],
            highlightcolor=self.theme["primary"],
            cursor="hand2",
            height=38
        )
        self.card.pack(fill=tk.X, expand=True)
        self.card.pack_propagate(False)

        # 1. Right side: Chevron down inside a subtle rounded mini-capsule (matching user Image 2)
        self.chevron_capsule = tk.Frame(
            self.card,
            bg=self.theme["secondary_bg"],
            bd=0,
            highlightthickness=1,
            highlightbackground=self.theme["card_border"],
            padx=7,
            pady=3,
            cursor="hand2"
        )
        self.chevron_capsule.pack(side=tk.RIGHT, padx=(0, 10), pady=4)

        self.chevron_lbl = tk.Label(
            self.chevron_capsule,
            bg=self.theme["secondary_bg"],
            cursor="hand2"
        )
        self.chevron_lbl.pack()
        self.update_chevron_icon()

        # 2. Dead-Center Language Name (Horizontal & Vertical Center of Rectangle)
        current_name = self.languages_dict.get(self.current_code, "العربية (Arabic)")
        self.lang_lbl = tk.Label(
            self.card,
            text=current_name,
            font=("Segoe UI", 10, "bold"),
            fg=self.theme["text_primary"],
            bg=self.theme["card_bg"],
            anchor=tk.CENTER,
            justify=tk.CENTER,
            cursor="hand2"
        )
        # Using place with relx=0.5, rely=0.5 guarantees 100% dead-center positioning!
        self.lang_lbl.place(relx=0.5, rely=0.5, anchor="center")

        # Bind clicks & hover
        for w in (self.card, self.chevron_capsule, self.chevron_lbl, self.lang_lbl):
            w.bind("<Button-1>", self.toggle_popup)
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)

    def _on_enter(self, e):
        self.card.config(highlightbackground=self.theme["primary"])
        self.chevron_capsule.config(bg=self.theme["card_hover"], highlightbackground=self.theme["primary"])
        self.chevron_lbl.config(bg=self.theme["card_hover"])

    def _on_leave(self, e):
        if not (self.popup and self.popup.winfo_exists()):
            self.card.config(highlightbackground=self.theme["card_border"])
            self.chevron_capsule.config(bg=self.theme["secondary_bg"], highlightbackground=self.theme["card_border"])
            self.chevron_lbl.config(bg=self.theme["secondary_bg"])

    def toggle_popup(self, event=None):
        now = time.time()
        # Debounce prevents immediate re-opening when clicking trigger while open
        if now - self._last_close_time < 0.25:
            return

        if self.popup and self.popup.winfo_exists():
            self.close_popup()
        else:
            self.open_popup()

    def close_popup(self):
        self._last_close_time = time.time()
        toplevel = self.winfo_toplevel()
        if self._outside_bind_id and toplevel:
            try:
                toplevel.unbind("<Button-1>", self._outside_bind_id)
            except Exception:
                pass
            self._outside_bind_id = None

        if self.popup:
            try:
                if self.popup.winfo_exists():
                    self.popup.destroy()
            except Exception:
                pass
            self.popup = None
        self._on_leave(None)

    def open_popup(self):
        self.close_popup()

        toplevel = self.winfo_toplevel()
        self.popup = tk.Toplevel(toplevel)
        self.popup.overrideredirect(True)
        self.popup.attributes("-topmost", True)
        self.popup.configure(bg=self.theme["card_border"])

        self.update_idletasks()
        bx = self.card.winfo_rootx()
        by = self.card.winfo_rooty()
        bw = max(200, self.card.winfo_width())
        bh = self.card.winfo_height()

        item_h = 32
        max_visible = 9
        total_items = len(self.languages_dict)
        view_h = min(total_items, max_visible) * item_h + 8

        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = bx
        y = by + bh + 4
        if y + view_h > sh - 20:
            y = max(10, by - view_h - 4)

        outer = tk.Frame(
            self.popup,
            bg=self.theme["card_bg"],
            bd=0,
            highlightthickness=1,
            highlightbackground=self.theme["primary"]
        )
        outer.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(
            outer,
            bg=self.theme["card_bg"],
            width=bw,
            height=view_h,
            highlightthickness=0,
            bd=0
        )
        items_frame = tk.Frame(canvas, bg=self.theme["card_bg"])

        def on_scroll(event):
            if event.delta:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind("<MouseWheel>", on_scroll)

        check_icon = get_icon_photo("check", size=14, color=self.theme["primary"])

        for code, display_name in self.languages_dict.items():
            is_active = (code == self.current_code)
            item_row = tk.Frame(
                items_frame,
                bg=self.theme["nav_item_active_bg"] if is_active else self.theme["card_bg"],
                cursor="hand2",
                padx=12,
                pady=6
            )
            item_row.pack(fill=tk.X, expand=True)

            check_lbl = tk.Label(
                item_row,
                image=check_icon if is_active else "",
                bg=item_row["bg"],
                width=16,
                cursor="hand2"
            )
            if is_active:
                check_lbl.image = check_icon
            check_lbl.pack(side=tk.LEFT, padx=(0, 8))

            name_lbl = tk.Label(
                item_row,
                text=display_name,
                font=("Segoe UI", 9, "bold" if is_active else "normal"),
                fg=self.theme["primary"] if is_active else self.theme["text_primary"],
                bg=item_row["bg"],
                anchor=tk.CENTER,
                cursor="hand2"
            )
            name_lbl.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            def bind_item(frame, c_lbl, n_lbl, c_code, active):
                def on_item_enter(e):
                    bg_col = self.theme["card_hover"]
                    frame.config(bg=bg_col)
                    c_lbl.config(bg=bg_col)
                    n_lbl.config(bg=bg_col)

                def on_item_leave(e):
                    bg_col = self.theme["nav_item_active_bg"] if active else self.theme["card_bg"]
                    frame.config(bg=bg_col)
                    c_lbl.config(bg=bg_col)
                    n_lbl.config(bg=bg_col)

                def on_item_click(e):
                    self.select_code(c_code)

                for w in (frame, c_lbl, n_lbl):
                    w.bind("<Enter>", on_item_enter)
                    w.bind("<Leave>", on_item_leave)
                    w.bind("<Button-1>", on_item_click)
                    w.bind("<MouseWheel>", on_scroll)

            bind_item(item_row, check_lbl, name_lbl, code, is_active)

        canvas.create_window((0, 0), window=items_frame, anchor="nw", width=bw)
        items_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
        canvas.pack(fill=tk.BOTH, expand=True)

        self.popup.geometry(f"{bw}x{view_h}+{x}+{y}")
        self.popup.update_idletasks()

        # Apply Windows native rounded corners via SetWindowRgn and DwmSetWindowAttribute
        try:
            hwnd = ctypes.windll.user32.GetParent(self.popup.winfo_id())
            target_h = hwnd if hwnd else self.popup.winfo_id()
            rgn = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, bw, view_h, 14, 14)
            ctypes.windll.user32.SetWindowRgn(target_h, rgn, True)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(target_h, 33, ctypes.byref(ctypes.c_int(2)), 4)
        except Exception:
            pass

        self.popup.focus_force()
        self.popup.bind("<Escape>", lambda e: self.close_popup())

        # Global click outside handler on parent window
        def on_global_click(event):
            if not self.popup or not self.popup.winfo_exists():
                return
            px = self.popup.winfo_rootx()
            py = self.popup.winfo_rooty()
            pw = self.popup.winfo_width()
            ph = self.popup.winfo_height()
            mx, my = event.x_root, event.y_root

            # Check if clicked inside dropdown trigger or popup
            tx = self.card.winfo_rootx()
            ty = self.card.winfo_rooty()
            tw = self.card.winfo_width()
            th = self.card.winfo_height()

            if (px <= mx <= px + pw and py <= my <= py + ph) or (tx <= mx <= tx + tw and ty <= my <= ty + th):
                return
            self.close_popup()

        self._outside_bind_id = toplevel.bind("<Button-1>", on_global_click, add="+")

    def select_code(self, code):
        self.current_code = code
        display_name = self.languages_dict.get(code, code)
        self.lang_lbl.config(text=display_name)
        self.close_popup()
        if self.on_change:
            self.on_change(code, display_name)

    def get_selected_code(self):
        return self.current_code

    def get_selected_display(self):
        return self.languages_dict.get(self.current_code, "")
