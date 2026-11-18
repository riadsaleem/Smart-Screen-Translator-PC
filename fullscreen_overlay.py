import os
import time
import tkinter as tk
from PIL import Image, ImageTk, ImageFilter, ImageEnhance
from screen_snipper import get_virtual_screen_bounds
from ui_theme import get_theme, blend_color, clear_theme_caches, create_rounded_rect_image, to_hex_color
from ui_components import ModernButton, ThemeToggleButton

LANGUAGES = {
    "auto": "كشف تلقائي",
    "ar": "العربية",
    "en": "English",
    "fr": "Français",
    "es": "Español",
    "tr": "Türkçe",
    "de": "Deutsch",
    "ru": "Русский",
    "ur": "اردو",
    "fa": "فارسی",
    "zh": "中文",
    "ja": "日本語"
}
LANG_NAME_TO_CODE = {name: code for code, name in LANGUAGES.items()}


class ModernDropdown(tk.Canvas):
    """
    Sleek, theme-aware custom dropdown capsule component with true rounded corners.
    Eliminates sharp rectangular native combobox widgets completely so text never vanishes
    and seamlessly respects light and dark palettes with anti-aliased 4x PIL rendering.
    """
    def __init__(
        self,
        parent,
        values,
        initial_value,
        on_select,
        min_width=115,
        height=32,
        radius=12,
        border_width=1,
        on_open_callback=None,
        theme_name="light",
        **kwargs
    ):
        self.theme_name = theme_name
        self.theme = get_theme(theme_name)
        self.values = values
        self.current_value = initial_value
        self.on_select = on_select
        self.min_width = int(min_width)
        self.btn_height = int(height)
        self.radius = int(radius)
        self.border_width = int(border_width)
        self.on_open_callback = on_open_callback
        self.popup = None
        self._last_close_time = 0
        self.state = "normal"  # normal, hover, pressed

        raw_pbg = parent.cget("bg") if hasattr(parent, "cget") else self.theme["header_bg"]
        self.parent_bg = to_hex_color(parent, raw_pbg)

        self.custom_font = ("Segoe UI", 9, "bold")
        self.btn_width = self._compute_width(self.current_value)

        super().__init__(
            parent,
            width=self.btn_width,
            height=self.btn_height,
            highlightthickness=0,
            bg=self.parent_bg,
            cursor="hand2",
            **kwargs
        )
        self.pack_propagate(False)

        self._draw_dropdown()

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    def _compute_width(self, val):
        import tkinter.font as tkfont
        try:
            f = tkfont.Font(font=self.custom_font)
            w = f.measure(self._format_label(val)) + 26
        except Exception:
            w = len(self._format_label(val)) * 8 + 26
        return max(self.min_width, w)

    def _format_label(self, val):
        return f"{val}  ⌄"

    def _draw_dropdown(self):
        self.delete("all")
        if self.cget("bg") != self.parent_bg:
            super().configure(bg=self.parent_bg)

        if self.state == "pressed":
            fill = self.theme["secondary_pressed"]
            border = self.theme["primary"]
            fg = self.theme["primary"]
        elif self.state == "hover":
            fill = self.theme["secondary_hover"]
            border = self.theme["primary"]
            fg = self.theme["primary"]
        else:
            fill = self.theme["secondary_bg"]
            border = self.theme["card_border"]
            fg = self.theme["text_primary"]

        img = create_rounded_rect_image(
            self.btn_width,
            self.btn_height,
            self.radius,
            fill,
            border,
            self.border_width,
            parent_bg=self.parent_bg
        )
        self._bg_img = img
        self.create_image(0, 0, anchor="nw", image=img)

        cx = self.btn_width / 2.0
        cy = self.btn_height / 2.0
        self.create_text(
            cx,
            cy,
            text=self._format_label(self.current_value),
            fill=fg,
            font=self.custom_font,
            anchor="center"
        )

    def _on_enter(self, e):
        self.state = "hover"
        self._draw_dropdown()

    def _on_leave(self, e):
        self.state = "normal"
        self._draw_dropdown()

    def _on_press(self, e):
        self.state = "pressed"
        self._draw_dropdown()

    def _on_release(self, e):
        if self.state == "pressed":
            self.state = "hover"
            self._draw_dropdown()
            self.toggle_popup()

    def update_theme(self, theme_name):
        self.theme_name = theme_name
        self.theme = get_theme(theme_name)
        raw_pbg = self.master.cget("bg") if hasattr(self.master, "cget") else self.theme["header_bg"]
        self.parent_bg = to_hex_color(self.master, raw_pbg)
        self.config(bg=self.parent_bg)
        self._draw_dropdown()

    def set_value(self, val):
        self.current_value = val
        new_w = self._compute_width(val)
        if new_w != self.btn_width:
            self.btn_width = new_w
            self.config(width=self.btn_width)
        self._draw_dropdown()

    def toggle_popup(self):
        now = time.time()
        if now - self._last_close_time < 0.22:
            return
        if self.popup and self.popup.winfo_exists():
            self.close_popup()
            return
        self.open_popup()

    def close_popup(self):
        self._last_close_time = time.time()
        if self.popup:
            try:
                if self.popup.winfo_exists():
                    self.popup.destroy()
            except Exception:
                pass
            self.popup = None

    def open_popup(self):
        if self.on_open_callback:
            self.on_open_callback(self)

        self.close_popup()
        toplevel = self.winfo_toplevel()
        self.popup = tk.Toplevel(toplevel)
        self.popup.overrideredirect(True)
        self.popup.attributes("-topmost", True)
        self.popup.configure(bg=self.theme["card_border"])

        self.update_idletasks()
        bx = self.winfo_rootx()
        by = self.winfo_rooty()
        bw = self.winfo_width()
        bh = self.winfo_height()

        w = max(bw, self.min_width)
        x = bx
        y = by + bh + 4

        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        if x + w > sw - 10:
            x = sw - w - 10
        if x < 10:
            x = 10

        outer = tk.Frame(
            self.popup,
            bg=self.theme["card_bg"],
            bd=0,
            highlightthickness=1,
            highlightbackground=self.theme["card_border"]
        )
        outer.pack(fill=tk.BOTH, expand=True)

        item_h = 28
        max_visible = 10
        total_items = len(self.values)
        view_h = min(total_items, max_visible) * item_h + 4

        if y + view_h > sh - 20:
            y = max(10, by - view_h - 4)

        canvas = tk.Canvas(
            outer,
            bg=self.theme["card_bg"],
            width=w,
            height=view_h,
            highlightthickness=0,
            bd=0
        )
        items_frame = tk.Frame(canvas, bg=self.theme["card_bg"])

        def on_scroll(event):
            if event.delta:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind("<MouseWheel>", on_scroll)

        for val in self.values:
            is_active = (val == self.current_value or (isinstance(self.current_value, str) and val in self.current_value))
            active_bg = self.theme["nav_item_active_bg"]
            norm_bg = self.theme["card_bg"]
            active_fg = self.theme["primary"]
            norm_fg = self.theme["text_primary"]
            hover_bg = self.theme["card_hover"]

            lbl = tk.Label(
                items_frame,
                text=val,
                font=("Segoe UI", 9, "bold" if is_active else "normal"),
                fg=active_fg if is_active else norm_fg,
                bg=active_bg if is_active else norm_bg,
                anchor=tk.W,
                padx=12,
                pady=4,
                cursor="hand2"
            )
            lbl.pack(fill=tk.X, expand=True)

            def bind_item(label, v, active):
                label.bind("<Enter>", lambda e: label.config(bg=hover_bg, fg=active_fg))
                label.bind("<Leave>", lambda e: label.config(bg=active_bg if active else norm_bg, fg=active_fg if active else norm_fg))
                label.bind("<Button-1>", lambda e: self.select_val(v))
                label.bind("<MouseWheel>", on_scroll)

            bind_item(lbl, val, is_active)

        canvas.create_window((0, 0), window=items_frame, anchor="nw", width=w)
        items_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
        canvas.pack(fill=tk.BOTH, expand=True)

        self.popup.geometry(f"{w}x{view_h}+{x}+{y}")
        self.popup.focus_force()

        # Keyboard and outside dismissal
        self.popup.bind("<Escape>", lambda e: self.close_popup())
        self.popup.bind("<FocusOut>", self._on_focus_out)

    def _on_focus_out(self, event=None):
        if self.popup:
            focused = self.popup.focus_get()
            if focused is None or (focused != self.popup and focused.winfo_toplevel() != self.popup):
                self.close_popup()

    def select_val(self, val):
        self.set_value(val)
        self.close_popup()
        if self.on_select:
            self.on_select(val)


class ModernBadge(tk.Canvas):
    """
    Sleek rounded status capsule matching modern UI buttons.
    Anti-aliased 4x PIL rendering with dynamic status updates.
    """
    def __init__(
        self,
        parent,
        text="",
        font=("Segoe UI", 8, "bold"),
        fg=None,
        bg=None,
        border_color=None,
        radius=12,
        height=32,
        theme_name="light",
        **kwargs
    ):
        self.theme_name = theme_name
        self.theme = get_theme(theme_name)
        self.text_content = text
        self.badge_font = font
        self.badge_height = int(height)
        self.radius = int(radius)
        self.border_width = 1

        raw_pbg = parent.cget("bg") if hasattr(parent, "cget") else self.theme["header_bg"]
        self.parent_bg = to_hex_color(parent, raw_pbg)

        self.fg_color = fg or self.theme["primary"]
        self.bg_color = bg or blend_color(self.theme["card_bg"], self.fg_color, 0.15)
        self.border_color = border_color or self.theme["card_border"]

        self.badge_width = self._compute_width(self.text_content)

        super().__init__(
            parent,
            width=self.badge_width,
            height=self.badge_height,
            highlightthickness=0,
            bg=self.parent_bg,
            **kwargs
        )
        self.pack_propagate(False)
        self._draw_badge()

    def _compute_width(self, text):
        import tkinter.font as tkfont
        try:
            f = tkfont.Font(font=self.badge_font)
            w = f.measure(text) + 24
        except Exception:
            w = len(text) * 8 + 24
        return max(75, w)

    def _draw_badge(self):
        self.delete("all")
        if self.cget("bg") != self.parent_bg:
            super().configure(bg=self.parent_bg)

        img = create_rounded_rect_image(
            self.badge_width,
            self.badge_height,
            self.radius,
            self.bg_color,
            self.border_color,
            self.border_width,
            parent_bg=self.parent_bg
        )
        self._bg_img = img
        self.create_image(0, 0, anchor="nw", image=img)

        cx = self.badge_width / 2.0
        cy = self.badge_height / 2.0
        self.create_text(
            cx,
            cy,
            text=self.text_content,
            fill=self.fg_color,
            font=self.badge_font,
            anchor="center"
        )

    def config(self, **kwargs):
        redraw = False
        if "text" in kwargs:
            self.text_content = kwargs.pop("text")
            new_w = self._compute_width(self.text_content)
            if new_w != self.badge_width:
                self.badge_width = new_w
                super().configure(width=self.badge_width)
            redraw = True
        if "fg" in kwargs:
            self.fg_color = kwargs.pop("fg")
            redraw = True
        if "bg" in kwargs:
            self.bg_color = kwargs.pop("bg")
            redraw = True
        if "border_color" in kwargs:
            self.border_color = kwargs.pop("border_color")
            redraw = True
        if kwargs:
            super().config(**kwargs)
        if redraw:
            self._draw_badge()

    def configure(self, **kwargs):
        return self.config(**kwargs)

    def update_theme(self, theme_name, fg=None, bg=None):
        self.theme_name = theme_name
        self.theme = get_theme(theme_name)
        raw_pbg = self.master.cget("bg") if hasattr(self.master, "cget") else self.theme["header_bg"]
        self.parent_bg = to_hex_color(self.master, raw_pbg)
        if fg:
            self.fg_color = fg
        if bg:
            self.bg_color = bg
        self.border_color = self.theme["card_border"]
        super().configure(bg=self.parent_bg)
        self._draw_badge()


class FullscreenOverlay:
    def __init__(
        self,
        root,
        overlay_image_path,
        translated_text="",
        source_lang="auto",
        target_lang="ar",
        is_offline=False,
        theme_name=None,
        on_change_language=None,
        on_dismiss=None
    ):
        self.root = root
        self.image_path = overlay_image_path
        self.translated_text = translated_text
        self.source_lang = source_lang or "auto"
        self.target_lang = target_lang or "ar"
        self.is_offline = is_offline
        self.detected_lang = source_lang if source_lang != "auto" else "en"
        self.on_change_language = on_change_language
        self.on_dismiss = on_dismiss

        if not theme_name:
            try:
                from config import load_config
                theme_name = load_config().get("overlay_theme", "light")
            except Exception:
                theme_name = "light"
        self.theme_name = theme_name
        self.theme = get_theme(theme_name)

        self.win = None
        self.canvas = None
        self.canvas_img_id = None

        self.screen_w = 1366
        self.screen_h = 768
        self.screen_left = 0
        self.screen_top = 0

        # Zoom & Pan State
        self.original_raw_img = None
        self.original_img = None
        self.zoom_level = 1.0
        self.min_zoom = 1.0
        self.max_zoom = 4.0
        self.pan_x = 0
        self.pan_y = 0
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.is_dragging = False

        self.cached_zoomed_img = None
        self.tk_img = None

        # UI elements
        self.pill = None
        self.status_lbl = None
        self.src_dd = None
        self.target_dd = None

    def show(self):
        left, top, width, height = get_virtual_screen_bounds()
        self.screen_left = left
        self.screen_top = top
        self.screen_w = width
        self.screen_h = height

        self.win = tk.Toplevel(self.root)
        self.win.overrideredirect(True)
        self.win.geometry(f"{width}x{height}+{left}+{top}")
        self.win.attributes("-topmost", True)
        self.win.configure(bg="#000000")

        # Load full pristine original image without destroying high-res detail
        if os.path.exists(self.image_path):
            self.original_raw_img = Image.open(self.image_path).convert("RGBA")
            if self.original_raw_img.size != (width, height):
                self.original_img = self.original_raw_img.resize((width, height), Image.Resampling.LANCZOS)
            else:
                self.original_img = self.original_raw_img
        else:
            self.dismiss()
            return

        self.canvas = tk.Canvas(
            self.win,
            width=width,
            height=height,
            highlightthickness=0,
            bg="#000000",
            cursor="fleur"
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.render_image_at_zoom()
        self.create_top_toolbar()
        self.bind_events()

        self.win.focus_force()

    # ---------------- Modern Floating Glassmorphism Pill / Capsule ----------------
    def create_top_toolbar(self):
        # Sleek capsule background with subtle border matching current theme
        self.pill = tk.Frame(
            self.win,
            bg=self.theme["header_bg"],
            bd=0,
            highlightthickness=1,
            highlightbackground=self.theme["card_border"],
            padx=12,
            pady=6
        )
        self.pill.place(relx=0.5, rely=0.038, anchor=tk.CENTER)
        self.pill.lift()

        # 1. Close Button with smooth red accent hover
        close_btn = ModernButton(
            self.pill,
            text="",
            icon_name="cross",
            width=32,
            height=32,
            radius=12,
            bg=self.theme["secondary_bg"],
            fg=self.theme["danger"],
            hover_bg=self.theme["danger"],
            pressed_bg=blend_color(self.theme["danger"], "#000000", 0.2),
            border_color=self.theme["card_border"],
            command=self.dismiss
        )
        close_btn.pack(side=tk.LEFT, padx=(0, 6))

        # 2. Modern Pill Copy Button with clean hover effect
        copy_btn = ModernButton(
            self.pill,
            text="نسخ",
            icon_name="copy",
            width=76,
            height=32,
            radius=12,
            bg=self.theme["secondary_bg"],
            fg=self.theme["text_primary"],
            hover_bg=self.theme["secondary_hover"],
            pressed_bg=self.theme["secondary_pressed"],
            border_color=self.theme["card_border"],
            command=self.copy_text
        )
        copy_btn.pack(side=tk.LEFT, padx=(0, 6))

        # Divider
        tk.Frame(self.pill, bg=self.theme["card_border"], width=1, height=22).pack(side=tk.LEFT, padx=5)

        # 3. Target Language Selector (on the LEFT side of swap button)
        target_name = LANGUAGES.get(self.target_lang, "العربية")
        target_options = [
            "العربية", "English", "Français", "Español", "Türkçe", "Deutsch", "Русский", "اردو", "فارسی", "中文", "日本語"
        ]
        self.target_dd = ModernDropdown(
            self.pill,
            values=target_options,
            initial_value=target_name,
            on_select=self.on_target_changed,
            min_width=110,
            on_open_callback=self.on_dropdown_opened,
            theme_name=self.theme_name
        )
        self.target_dd.pack(side=tk.LEFT, padx=3)

        # 4. Swap Button with vector swap arrows
        swap_btn = ModernButton(
            self.pill,
            text="",
            icon_name="swap",
            width=36,
            height=32,
            radius=12,
            bg=self.theme["secondary_bg"],
            fg=self.theme["primary"],
            hover_bg=self.theme["primary"],
            pressed_bg=self.theme["primary_pressed"],
            border_color=self.theme["card_border"],
            command=self.swap_languages
        )
        swap_btn.pack(side=tk.LEFT, padx=3)

        # 5. Source Language Selector (on the RIGHT side of swap button)
        src_display = self.get_source_display_name()
        src_options = [
            "كشف تلقائي",
            "العربية", "English", "Français", "Español", "Türkçe", "Deutsch", "Русский", "اردو", "فارسی", "中文", "日本語"
        ]
        self.src_dd = ModernDropdown(
            self.pill,
            values=src_options,
            initial_value=src_display,
            on_select=self.on_source_changed,
            min_width=135,
            on_open_callback=self.on_dropdown_opened,
            theme_name=self.theme_name
        )
        self.src_dd.pack(side=tk.LEFT, padx=3)

        # Divider
        tk.Frame(self.pill, bg=self.theme["card_border"], width=1, height=22).pack(side=tk.LEFT, padx=5)

        # 6. Status Badge (Subtle elegant pill badge)
        if self.is_offline:
            initial_status = "📴 بدون إنترنت"
            initial_fg = self.theme["success"]
            initial_bg = blend_color(self.theme["card_bg"], self.theme["success"], 0.15)
        else:
            initial_status = "🌐 عدسة Google"
            initial_fg = self.theme["primary"]
            initial_bg = blend_color(self.theme["card_bg"], self.theme["primary"], 0.15)

        self.status_lbl = ModernBadge(
            self.pill,
            text=initial_status,
            font=("Segoe UI", 8, "bold"),
            fg=initial_fg,
            bg=initial_bg,
            border_color=self.theme["card_border"],
            radius=12,
            height=32,
            theme_name=self.theme_name
        )
        self.status_lbl.pack(side=tk.LEFT, padx=4)

        # 7. Theme Toggle Button in the floating toolbar
        self.theme_toggle_btn = ThemeToggleButton(
            self.pill,
            current_theme=self.theme_name,
            radius=12,
            on_toggle=self.switch_theme
        )
        self.theme_toggle_btn.pack(side=tk.LEFT, padx=(6, 0))

    def switch_theme(self, new_theme_name):
        self.theme_name = new_theme_name
        clear_theme_caches()
        self.theme = get_theme(new_theme_name)
        try:
            from config import load_config, save_config
            cfg = load_config()
            cfg["overlay_theme"] = new_theme_name
            save_config(cfg)
        except Exception:
            pass

        if self.pill and self.pill.winfo_exists():
            self.pill.destroy()
            self.create_top_toolbar()

    def on_dropdown_opened(self, active_dd):
        if active_dd == self.src_dd and hasattr(self, "target_dd") and self.target_dd:
            self.target_dd.close_popup()
        elif active_dd == self.target_dd and hasattr(self, "src_dd") and self.src_dd:
            self.src_dd.close_popup()

    def close_all_popups(self):
        if hasattr(self, "src_dd") and self.src_dd:
            self.src_dd.close_popup()
        if hasattr(self, "target_dd") and self.target_dd:
            self.target_dd.close_popup()

    def set_status(self, text, fg=None, bg=None):
        if self.status_lbl and self.status_lbl.winfo_exists():
            fg_col = fg or self.theme["primary"]
            bg_col = bg or blend_color(self.theme["card_bg"], fg_col, 0.15)
            self.status_lbl.config(text=text, fg=fg_col, bg=bg_col)

    def reset_status(self):
        if self.is_offline:
            self.set_status("📴 بدون إنترنت", fg=self.theme["success"], bg=blend_color(self.theme["card_bg"], self.theme["success"], 0.15))
        else:
            self.set_status("🌐 عدسة Google", fg=self.theme["primary"], bg=blend_color(self.theme["card_bg"], self.theme["primary"], 0.15))

    def show_translating_status(self):
        if self.theme_name == "light":
            fg = "#b45309"
            bg = "#fef3c7"
        else:
            fg = "#f9e2af"
            bg = "#2d2a1e"
        self.set_status("⏳ جاري الترجمة...", fg=fg, bg=bg)

    def show_updated_status(self):
        if self.theme_name == "light":
            fg = self.theme["success"]
            bg = blend_color(self.theme["card_bg"], fg, 0.15)
        else:
            fg = "#a6e3a1"
            bg = "#1e2d24"
        self.set_status("✓ تم التحديث", fg=fg, bg=bg)
        if self.win and self.win.winfo_exists():
            self.win.after(2500, self.reset_status)

    def show_copied_status(self):
        if self.theme_name == "light":
            fg = self.theme["primary"]
            bg = blend_color(self.theme["card_bg"], fg, 0.15)
        else:
            fg = "#89b4fa"
            bg = "#1e2538"
        self.set_status("✓ تم نسخ النص", fg=fg, bg=bg)
        if self.win and self.win.winfo_exists():
            self.win.after(2000, self.reset_status)

    def get_source_display_name(self):
        if self.source_lang == "auto" or self.source_lang is None:
            det_name = LANGUAGES.get(self.detected_lang, self.detected_lang.upper())
            return f"كشف تلقائي ({det_name})"
        return LANGUAGES.get(self.source_lang, self.source_lang)

    # ---------------- Language Operations ----------------
    def on_source_changed(self, val):
        if "كشف تلقائي" in val:
            self.source_lang = "auto"
            if hasattr(self, "src_dd") and self.src_dd:
                self.src_dd.set_value(self.get_source_display_name())
        else:
            self.source_lang = LANG_NAME_TO_CODE.get(val, "auto")
        self.trigger_retranslation()

    def on_target_changed(self, selected_name):
        new_code = LANG_NAME_TO_CODE.get(selected_name, "ar")
        if new_code != self.target_lang:
            self.target_lang = new_code
            self.trigger_retranslation()

    def swap_languages(self):
        old_src = self.detected_lang if self.source_lang == "auto" else self.source_lang
        old_tgt = self.target_lang
        self.source_lang = old_tgt
        self.target_lang = old_src
        self.detected_lang = old_tgt

        if hasattr(self, "src_dd") and self.src_dd:
            self.src_dd.set_value(LANGUAGES.get(self.source_lang, self.source_lang))
        if hasattr(self, "target_dd") and self.target_dd:
            self.target_dd.set_value(LANGUAGES.get(self.target_lang, "العربية"))
        self.trigger_retranslation()

    def trigger_retranslation(self):
        self.show_translating_status()
        self.win.update_idletasks()
        if self.on_change_language:
            try:
                self.on_change_language(self.target_lang, self.source_lang)
            except TypeError:
                self.on_change_language(self.target_lang)

    def update_translated_image(self, new_image_path, new_text="", new_target_lang=None, detected_src=None, is_offline=False):
        """Called when new translation arrives without recreating the window."""
        self.image_path = new_image_path
        self.translated_text = new_text
        self.is_offline = is_offline
        if new_target_lang:
            self.target_lang = new_target_lang
            if hasattr(self, "target_dd") and self.target_dd:
                self.target_dd.set_value(LANGUAGES.get(self.target_lang, self.target_lang))
        if detected_src:
            self.detected_lang = detected_src
            if hasattr(self, "src_dd") and self.src_dd:
                self.src_dd.set_value(self.get_source_display_name())

        if os.path.exists(self.image_path):
            self.original_raw_img = Image.open(self.image_path).convert("RGBA")
            if self.original_raw_img.size != (self.screen_w, self.screen_h):
                self.original_img = self.original_raw_img.resize((self.screen_w, self.screen_h), Image.Resampling.LANCZOS)
            else:
                self.original_img = self.original_raw_img
            self.render_image_at_zoom()
            if self.status_lbl:
                self.show_updated_status()

    # ---------------- Crisp High-Resolution Zoom & Pan Logic ----------------
    def render_image_at_zoom(self):
        base_source = getattr(self, "original_raw_img", None) or self.original_img
        if not base_source:
            return

        cur_w = int(self.screen_w * self.zoom_level)
        cur_h = int(self.screen_h * self.zoom_level)

        if self.zoom_level == 1.0:
            self.pan_x = 0
            self.pan_y = 0
            if base_source.size == (self.screen_w, self.screen_h):
                self.cached_zoomed_img = base_source
            else:
                self.cached_zoomed_img = base_source.resize(
                    (self.screen_w, self.screen_h), Image.Resampling.LANCZOS
                )
        else:
            # High-quality Lanczos sinc interpolation directly from pristine master image
            zoomed = base_source.resize((cur_w, cur_h), Image.Resampling.LANCZOS)
            # Enhance text sharpness and contrast with Unsharp Mask to eliminate blurry/fuzzy font strokes
            try:
                zoomed = zoomed.filter(ImageFilter.UnsharpMask(radius=1.2, percent=160, threshold=1))
            except Exception:
                try:
                    enhancer = ImageEnhance.Sharpness(zoomed)
                    zoomed = enhancer.enhance(1.4)
                except Exception:
                    pass
            self.cached_zoomed_img = zoomed

        self.clamp_pan(cur_w, cur_h)
        self.tk_img = ImageTk.PhotoImage(self.cached_zoomed_img)

        if self.canvas_img_id is None:
            self.canvas_img_id = self.canvas.create_image(
                self.pan_x, self.pan_y, anchor=tk.NW, image=self.tk_img
            )
        else:
            self.canvas.itemconfig(self.canvas_img_id, image=self.tk_img)
            self.canvas.coords(self.canvas_img_id, self.pan_x, self.pan_y)

    def clamp_pan(self, cur_w=None, cur_h=None):
        if cur_w is None:
            cur_w = int(self.screen_w * self.zoom_level)
        if cur_h is None:
            cur_h = int(self.screen_h * self.zoom_level)

        if cur_w <= self.screen_w:
            self.pan_x = (self.screen_w - cur_w) // 2
        else:
            min_x = self.screen_w - cur_w
            self.pan_x = max(min_x, min(0, self.pan_x))

        if cur_h <= self.screen_h:
            self.pan_y = (self.screen_h - cur_h) // 2
        else:
            min_y = self.screen_h - cur_h
            self.pan_y = max(min_y, min(0, self.pan_y))

    def zoom_in(self, step=0.25, center_x=None, center_y=None):
        if center_x is None:
            center_x = self.screen_w / 2
        if center_y is None:
            center_y = self.screen_h / 2

        old_zoom = self.zoom_level
        new_zoom = min(self.max_zoom, round(self.zoom_level + step, 2))
        if new_zoom != old_zoom:
            self.zoom_level = new_zoom
            scale = new_zoom / old_zoom
            self.pan_x = int(center_x - (center_x - self.pan_x) * scale)
            self.pan_y = int(center_y - (center_y - self.pan_y) * scale)
            self.render_image_at_zoom()

    def zoom_out(self, step=0.25, center_x=None, center_y=None):
        if center_x is None:
            center_x = self.screen_w / 2
        if center_y is None:
            center_y = self.screen_h / 2

        old_zoom = self.zoom_level
        new_zoom = max(self.min_zoom, round(self.zoom_level - step, 2))
        if new_zoom != old_zoom:
            self.zoom_level = new_zoom
            scale = new_zoom / old_zoom
            self.pan_x = int(center_x - (center_x - self.pan_x) * scale)
            self.pan_y = int(center_y - (center_y - self.pan_y) * scale)
            self.render_image_at_zoom()

    def reset_zoom(self):
        self.zoom_level = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.render_image_at_zoom()

    def toggle_zoom_shortcut(self, event=None):
        """Triggered by Ctrl+A to easily enlarge/restore translation."""
        if self.zoom_level > 1.05:
            self.reset_zoom()
        else:
            self.zoom_in(step=0.5)

    # ---------------- Mouse & Keyboard Event Bindings ----------------
    def bind_events(self):
        # Mouse Drag to Pan
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)

        # Mouse Wheel to Zoom in/out seamlessly across entire window
        self.win.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)

        # Double click to toggle zoom
        self.canvas.bind("<Double-Button-1>", lambda e: self.zoom_in(0.5, e.x, e.y) if self.zoom_level < 2.0 else self.reset_zoom())

        # Keyboard: Return / Enter and Esc both return to before translation!
        self.win.bind("<Escape>", lambda e: self.dismiss())
        self.win.bind("<Return>", lambda e: self.dismiss())
        self.win.bind("<KP_Enter>", lambda e: self.dismiss())

        # Ctrl+A to zoom in / toggle zoom
        self.win.bind("<Control-a>", self.toggle_zoom_shortcut)
        self.win.bind("<Control-A>", self.toggle_zoom_shortcut)

        # Plus / Minus keys for zooming
        self.win.bind("<plus>", lambda e: self.zoom_in())
        self.win.bind("<equal>", lambda e: self.zoom_in())
        self.win.bind("<minus>", lambda e: self.zoom_out())
        self.win.bind("<Control-plus>", lambda e: self.zoom_in())
        self.win.bind("<Control-equal>", lambda e: self.zoom_in())
        self.win.bind("<Control-minus>", lambda e: self.zoom_out())
        self.win.bind("<Control-0>", lambda e: self.reset_zoom())

        # Arrow keys for smooth panning when zoomed in
        def _pan_key(dx, dy):
            if self.zoom_level > 1.0:
                self.pan_x += dx
                self.pan_y += dy
                self.clamp_pan()
                self.canvas.coords(self.canvas_img_id, self.pan_x, self.pan_y)

        self.win.bind("<Left>", lambda e: _pan_key(60, 0))
        self.win.bind("<Right>", lambda e: _pan_key(-60, 0))
        self.win.bind("<Up>", lambda e: _pan_key(0, 60))
        self.win.bind("<Down>", lambda e: _pan_key(0, -60))

    def on_mouse_down(self, event):
        self.close_all_popups()
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        self.is_dragging = False

    def on_mouse_drag(self, event):
        dx = event.x - self.drag_start_x
        dy = event.y - self.drag_start_y

        if abs(dx) > 2 or abs(dy) > 2:
            self.is_dragging = True
            if self.zoom_level > 1.0:
                self.pan_x += dx
                self.pan_y += dy
                self.clamp_pan()
                self.canvas.coords(self.canvas_img_id, self.pan_x, self.pan_y)
                self.drag_start_x = event.x
                self.drag_start_y = event.y

    def on_mouse_up(self, event):
        self.is_dragging = False

    def on_mouse_wheel(self, event):
        self.close_all_popups()
        delta = event.delta
        if delta == 0:
            return

        if not hasattr(self, "_zoom_wheel_accum"):
            self._zoom_wheel_accum = 0

        if abs(delta) >= 120:
            steps = int(delta / 120)
            if steps > 0:
                self.zoom_in(step=0.25 * steps, center_x=event.x, center_y=event.y)
            else:
                self.zoom_out(step=0.25 * abs(steps), center_x=event.x, center_y=event.y)
            self._zoom_wheel_accum = 0
        else:
            self._zoom_wheel_accum += delta
            threshold = 90
            if abs(self._zoom_wheel_accum) >= threshold:
                direction = 1 if self._zoom_wheel_accum > 0 else -1
                count = int(abs(self._zoom_wheel_accum) / threshold)
                self._zoom_wheel_accum = direction * (abs(self._zoom_wheel_accum) % threshold)
                if direction > 0:
                    self.zoom_in(step=0.25 * count, center_x=event.x, center_y=event.y)
                else:
                    self.zoom_out(step=0.25 * count, center_x=event.x, center_y=event.y)
        return "break"

    def copy_text(self):
        self.close_all_popups()
        if self.translated_text:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.translated_text)
            self.show_copied_status()

    def dismiss(self):
        self.close_all_popups()
        if self.win:
            self.win.destroy()
            self.win = None
        self.pill = None
        self.status_lbl = None
        self.src_dd = None
        self.target_dd = None
        self.canvas = None
        self.original_raw_img = None
        self.original_img = None
        self.cached_zoomed_img = None
        self.tk_img = None
        if self.on_dismiss:
            self.on_dismiss()
