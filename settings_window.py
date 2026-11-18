import os
import sys
import ctypes
import threading
import winreg
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox
import keyboard

from config import load_config, save_config
from offline_manager import OfflineManager
from updater import (
    check_for_updates,
    download_file,
    apply_delta_patch,
    launch_full_installer,
    CURRENT_VERSION,
    get_token
)
from ui_theme import get_theme, set_current_theme, clear_theme_caches, setup_process_app_id, apply_window_icon
from ui_icons import get_icon_photo
from ui_components import (
    ModernLanguageDropdown,
    NavigationTabButton,
    ThemeToggleButton,
    ModernButton,
    ModernCard,
    ModernEntry,
    ModernCheckbox,
    ModernRadioGroup
)

# Set Windows AppUserModelID immediately
setup_process_app_id()

STARTUP_KEY_NAME = "SmartScreenTranslatorPC"
STARTUP_LNK_NAME = "مترجم الشاشة الذكي.lnk"

TARGET_LANGUAGES = {
    "ar": "العربية (Arabic)",
    "en": "English (الإنجليزية)",
    "fr": "Français (الفرنسية)",
    "es": "Español (الإسبانية)",
    "tr": "Türkçe (التركية)",
    "de": "Deutsch (الألمانية)",
    "ru": "Русский (الروسية)",
    "ur": "اردو (الأردية)",
    "fa": "فارسی (الفارسية)",
    "zh": "中文 (الصينية)",
    "ja": "日本語 (اليابانية)"
}
LANG_DISPLAY_TO_CODE = {display: code for code, display in TARGET_LANGUAGES.items()}

def _get_startup_lnk_path():
    appdata = os.environ.get("APPDATA", "")
    return os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup", STARTUP_LNK_NAME)

def is_startup_enabled():
    if os.path.exists(_get_startup_lnk_path()):
        return True
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_READ
        )
        winreg.QueryValueEx(key, STARTUP_KEY_NAME)
        winreg.CloseKey(key)
        return True
    except Exception:
        return False

def set_startup(enable=True):
    lnk_path = _get_startup_lnk_path()
    try:
        if enable:
            os.makedirs(os.path.dirname(lnk_path), exist_ok=True)
            if getattr(sys, "frozen", False):
                target = sys.executable
                args = "--startup"
                work_dir = os.path.dirname(sys.executable)
                ico = os.path.join(work_dir, "icon.ico")
            else:
                target = "pythonw.exe"
                script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
                args = f'"{script}" --startup'
                work_dir = os.path.dirname(script)
                ico = os.path.join(work_dir, "icon.ico")

            import win32com.client
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(lnk_path)
            shortcut.TargetPath = target
            shortcut.Arguments = args
            shortcut.WorkingDirectory = work_dir
            if os.path.exists(ico):
                shortcut.IconLocation = f"{ico},0"
            shortcut.save()
        else:
            if os.path.exists(lnk_path):
                os.remove(lnk_path)
            # Also clean any legacy HKCU Run entry if user disables startup
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Run",
                    0, winreg.KEY_SET_VALUE
                )
                winreg.DeleteValue(key, STARTUP_KEY_NAME)
                winreg.CloseKey(key)
            except Exception:
                pass
    except Exception as e:
        print("Failed to configure startup shortcut:", e)


class SettingsWindow:
    def __init__(self, root, on_saved=None, initial_tab="general", on_translate_fullscreen=None, on_translate_snipping=None):
        self.root = root
        self.on_saved = on_saved
        self.on_translate_fullscreen = on_translate_fullscreen
        self.on_translate_snipping = on_translate_snipping
        self.config = load_config()
        self.win = None
        self.downloading_now = False

        # Theme state
        self.current_theme = self.config.get("theme", "dark")
        set_current_theme(self.current_theme)
        self.theme = get_theme(self.current_theme)

        # Tab bar state
        self.current_tab = initial_tab
        self.tab_buttons = {}
        self.tab_frames = {}

        # Hotkey recording state
        self.is_recording = False
        self.record_bind_id = None

        # Updater state
        self.update_info = None
        self.is_checking_update = False
        self.is_downloading_update = False
        self.download_cancel_event = None

    def show(self, tab=None):
        if self.win and self.win.winfo_exists():
            if tab:
                self.switch_tab(tab)
            self.win.deiconify()
            self.win.lift()
            self.win.focus_force()
            return

        self.win = tk.Toplevel(self.root)
        self.win.title("مترجم الشاشة الذكي للكمبيوتر (PC)")
        self.win.geometry("590x690")
        self.win.resizable(False, False)
        self.win.configure(bg=self.theme["bg"])

        # Apply multi-resolution window and taskbar icons
        base_dir = os.path.dirname(os.path.abspath(__file__))
        ico = os.path.join(base_dir, "icon.ico")
        png = os.path.join(base_dir, "icon.png")
        if hasattr(sys, "_MEIPASS"):
            ico = os.path.join(sys._MEIPASS, "icon.ico")
            png = os.path.join(sys._MEIPASS, "icon.png")
        apply_window_icon(self.win, ico, png)

        # Center on screen
        self.win.update_idletasks()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        w = 590
        h = 690
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2)
        self.win.geometry(f"{w}x{h}+{x}+{y}")

        self.setup_ui()
        self.win.protocol("WM_DELETE_WINDOW", self._close_window)
        if tab:
            self.switch_tab(tab)
        self.win.focus_force()

    def switch_theme(self, new_theme_name):
        self.current_theme = new_theme_name
        set_current_theme(new_theme_name)
        clear_theme_caches()
        self.theme = get_theme(new_theme_name)
        self.config["theme"] = new_theme_name
        save_config(self.config)

        if self.win and self.win.winfo_exists():
            saved_tab = self.current_tab
            # Save any unsaved hotkey draft
            hotkey_draft = self.hotkey_entry.get() if hasattr(self, "hotkey_entry") else None

            for widget in self.win.winfo_children():
                widget.destroy()

            self.win.configure(bg=self.theme["bg"])
            self.setup_ui()

            if hotkey_draft and hasattr(self, "hotkey_entry"):
                self.hotkey_entry.delete(0, tk.END)
                self.hotkey_entry.insert(0, hotkey_draft)

            self.switch_tab(saved_tab)

    def setup_ui(self):
        # ---------------- 1. Top Header ----------------
        hdr = tk.Frame(self.win, bg=self.theme["header_bg"], height=70)
        hdr.pack(fill=tk.X, side=tk.TOP)
        hdr.pack_propagate(False)

        hdr_inner = tk.Frame(hdr, bg=self.theme["header_bg"])
        hdr_inner.pack(fill=tk.BOTH, expand=True, padx=18)

        # Left side: Theme Toggle (Moon/Sun icon only) & Logo
        left_box = tk.Frame(hdr_inner, bg=self.theme["header_bg"])
        left_box.pack(side=tk.LEFT, pady=12)

        self.theme_toggle = ThemeToggleButton(
            left_box,
            current_theme=self.current_theme,
            on_toggle=self.switch_theme
        )
        self.theme_toggle.pack(side=tk.LEFT, padx=(0, 10))

        # Display app logo thumbnail in header
        base_dir = os.path.dirname(os.path.abspath(__file__))
        png_path = os.path.join(base_dir, "icon.png")
        if hasattr(sys, "_MEIPASS"):
            png_path = os.path.join(sys._MEIPASS, "icon.png")

        if os.path.exists(png_path):
            try:
                from PIL import Image, ImageTk
                logo_raw = Image.open(png_path).resize((44, 44), Image.Resampling.LANCZOS)
                self._hdr_logo = ImageTk.PhotoImage(logo_raw)
                tk.Label(left_box, image=self._hdr_logo, bg=self.theme["header_bg"]).pack(side=tk.LEFT)
            except Exception:
                pass

        # Right side: App Title & Subtitle
        title_box = tk.Frame(hdr_inner, bg=self.theme["header_bg"])
        title_box.pack(side=tk.RIGHT, pady=12)

        title_lbl = tk.Label(
            title_box,
            text="🚀 مترجم الشاشة الذكي للكمبيوتر (PC)",
            font=("Segoe UI", 12, "bold"),
            fg=self.theme["header_fg"],
            bg=self.theme["header_bg"]
        )
        title_lbl.pack(anchor=tk.E)

        sub_lbl = tk.Label(
            title_box,
            text=f"الإصدار الاحترافي v{CURRENT_VERSION} • لوحة التحكم الشاملة والإعدادات",
            font=("Segoe UI", 8),
            fg=self.theme["header_sub"],
            bg=self.theme["header_bg"]
        )
        sub_lbl.pack(anchor=tk.E)

        # ---------------- 2. Navigation Tab Bar (Rounded pill buttons with vector icons) ----------------
        tab_bar = tk.Frame(self.win, bg=self.theme["nav_bg"], height=48)
        tab_bar.pack(fill=tk.X, padx=14, pady=(10, 0))
        tab_bar.pack_propagate(False)

        tabs_def = [
            ("general", "gear", "الإعدادات"),
            ("how_to_use", "guide", "كيفية الاستخدام"),
            ("offline", "offline", "بدون إنترنت"),
            ("updates", "updates", "التحديثات"),
            ("about", "about", "حول التطبيق")
        ]

        # Content container with smooth scrollable viewport
        self.content_container = tk.Frame(self.win, bg=self.theme["bg"])
        self.content_container.pack(fill=tk.BOTH, expand=True, padx=(14, 8), pady=(8, 8))
        self.content_container.rowconfigure(0, weight=1)
        self.content_container.columnconfigure(0, weight=1)

        self.scroll_canvas = tk.Canvas(
            self.content_container,
            bg=self.theme["bg"],
            highlightthickness=0,
            bd=0,
            yscrollincrement=1
        )
        self.scroll_canvas.grid(row=0, column=0, sticky="nsew")

        # Sleek, modern scrollbar matching the active theme
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        sb_style = f"Settings_{self.current_theme}.Vertical.TScrollbar"
        self._apply_scrollbar_style(sb_style)

        self.scrollbar = ttk.Scrollbar(
            self.content_container,
            orient="vertical",
            command=self.scroll_canvas.yview,
            style=sb_style
        )
        self.scroll_canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.grid(row=0, column=1, sticky="ns", padx=(4, 0))

        self.scroll_frame = tk.Frame(self.scroll_canvas, bg=self.theme["bg"])
        self.canvas_win = self.scroll_canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")

        def _on_canvas_configure(e):
            self.scroll_canvas.itemconfigure(self.canvas_win, width=e.width)
            self._update_scroll_region()

        def _on_frame_configure(e):
            self._update_scroll_region()

        self.scroll_canvas.bind("<Configure>", _on_canvas_configure)
        self.scroll_frame.bind("<Configure>", _on_frame_configure)

        self._wheel_accum = 0.0

        def _handle_scroll_delta(delta):
            if not self.win or not self.win.winfo_exists():
                return
            bbox = self.scroll_canvas.bbox("all")
            if not bbox:
                return
            content_h = bbox[3] - bbox[1]
            canvas_h = self.scroll_canvas.winfo_height()
            if content_h <= canvas_h:
                return

            if delta == 0:
                return

            # Windows standard: delta 120 = 1 notch ~= 48 pixels
            # Precision touchpad: small continuous deltas (10..40)
            # Continuous pixel scrolling for buttery-smooth 2-finger touchpad gestures
            self._wheel_accum += -delta * (48.0 / 120.0)
            pixels = int(self._wheel_accum)
            if pixels != 0:
                self._wheel_accum -= pixels
                self.scroll_canvas.yview_scroll(pixels, "units")

        def _on_mousewheel(e):
            _handle_scroll_delta(e.delta)
            return "break"

        def _on_button4(e):
            self.scroll_canvas.yview_scroll(-48, "units")
            return "break"

        def _on_button5(e):
            self.scroll_canvas.yview_scroll(48, "units")
            return "break"

        self.win.bind("<MouseWheel>", _on_mousewheel)
        self.win.bind("<Button-4>", _on_button4)
        self.win.bind("<Button-5>", _on_button5)

        self.tab_buttons = {}
        for i, (tab_id, icon_name, tab_label) in enumerate(tabs_def):
            tab_bar.columnconfigure(i, weight=1, uniform="tab_col")

            btn = NavigationTabButton(
                parent=tab_bar,
                tab_id=tab_id,
                icon_name=icon_name,
                label=tab_label,
                is_active=(tab_id == self.current_tab),
                on_click=self.switch_tab,
                theme_name=self.current_theme
            )
            btn.grid(row=0, column=i, sticky="nsew", padx=2)
            self.tab_buttons[tab_id] = btn

        # ---------------- 3. Build Tab Frames ----------------
        self.tab_frames = {}

        # Tab 1: General
        tab_gen = tk.Frame(self.scroll_frame, bg=self.theme["bg"])
        self.tab_frames["general"] = tab_gen
        self.setup_general_tab(tab_gen)

        # Tab 2: How to Use
        tab_how = tk.Frame(self.scroll_frame, bg=self.theme["bg"])
        self.tab_frames["how_to_use"] = tab_how
        self.setup_how_to_use_tab(tab_how)

        # Tab 3: Offline
        tab_off = tk.Frame(self.scroll_frame, bg=self.theme["bg"])
        self.tab_frames["offline"] = tab_off
        self.setup_offline_tab(tab_off)

        # Tab 4: Updates
        tab_upd = tk.Frame(self.scroll_frame, bg=self.theme["bg"])
        self.tab_frames["updates"] = tab_upd
        self.setup_updates_tab(tab_upd)

        # Tab 5: About
        tab_abt = tk.Frame(self.scroll_frame, bg=self.theme["bg"])
        self.tab_frames["about"] = tab_abt
        self.setup_about_tab(tab_abt)

        # Activate initial tab
        self.switch_tab(self.current_tab)

        # ---------------- 4. Footer Actions ----------------
        footer = tk.Frame(self.win, bg=self.theme["bg"], padx=16, pady=10)
        footer.pack(fill=tk.X, side=tk.BOTTOM)

        save_btn = ModernButton(
            footer,
            text="حفظ التغييرات",
            icon_name="check",
            width=145,
            height=36,
            radius=14,
            bg=self.theme["primary"],
            fg=self.theme["primary_fg"],
            hover_bg=self.theme["primary_hover"],
            pressed_bg=self.theme["primary_pressed"],
            command=self.save
        )
        save_btn.pack(side=tk.RIGHT, padx=6)

        cancel_btn = ModernButton(
            footer,
            text="إلغاء",
            width=90,
            height=36,
            radius=14,
            bg=self.theme["secondary_bg"],
            fg=self.theme["text_primary"],
            hover_bg=self.theme["secondary_hover"],
            pressed_bg=self.theme["secondary_pressed"],
            border_color=self.theme["card_border"],
            command=self._close_window
        )
        cancel_btn.pack(side=tk.RIGHT)

    def _apply_scrollbar_style(self, style_name):
        try:
            if self.current_theme == "light":
                thumb_col = "#cbd5e1"
                thumb_hover = "#94a3b8"
                trough_col = self.theme.get("bg", "#f1f5f9")
                arrow_col = "#64748b"
            else:
                thumb_col = "#3b425b"
                thumb_hover = self.theme.get("primary", "#3b82f6")
                trough_col = self.theme.get("bg", "#14161f")
                arrow_col = self.theme.get("text_dim", "#64748b")

            self.style.configure(
                style_name,
                gripcount=0,
                background=thumb_col,
                darkcolor=thumb_col,
                lightcolor=thumb_col,
                troughcolor=trough_col,
                bordercolor=trough_col,
                arrowcolor=arrow_col,
                arrowsize=11,
                width=10
            )
            self.style.map(
                style_name,
                background=[("active", thumb_hover), ("pressed", thumb_hover)]
            )
        except Exception:
            pass

    def _update_scroll_region(self):
        if not hasattr(self, "scroll_canvas") or not self.scroll_canvas.winfo_exists():
            return
        bbox = self.scroll_canvas.bbox("all")
        if bbox:
            self.scroll_canvas.configure(scrollregion=bbox)
            content_h = bbox[3] - bbox[1]
            canvas_h = self.scroll_canvas.winfo_height()
            if content_h > canvas_h and canvas_h > 20:
                if not self.scrollbar.winfo_ismapped():
                    self.scrollbar.grid(row=0, column=1, sticky="ns", padx=(4, 0))
            else:
                if self.scrollbar.winfo_ismapped():
                    self.scrollbar.grid_remove()

    def switch_tab(self, tab_id):
        self.current_tab = tab_id
        for tid, frame in self.tab_frames.items():
            frame.pack_forget()

        for tid, btn in self.tab_buttons.items():
            btn.set_active(tid == tab_id)

        if tab_id in self.tab_frames:
            self.tab_frames[tab_id].pack(fill=tk.BOTH, expand=True)
            self.scroll_frame.update_idletasks()
            self._update_scroll_region()
            self.scroll_canvas.yview_moveto(0)

    # ---------------- Tab 1: General Settings ----------------
    def setup_general_tab(self, parent):
        # 1. Hotkey Section
        hotkey_box = ModernCard(
            parent,
            title="⌨️ اختصار لوحة المفاتيح لتفعيل الترجمة",
            theme_name=self.current_theme
        )
        hotkey_box.pack(fill=tk.X, pady=(0, 10))

        tk.Label(
            hotkey_box.body,
            text="يمكنك كتابة أي اختصار تريده بحرية (مثل: ctrl+t, alt+t, ctrl+shift+x) أو الضغط على زر التسجيل:",
            font=("Segoe UI", 8),
            fg=self.theme["text_secondary"],
            bg=self.theme["card_bg"]
        ).pack(anchor=tk.E, pady=(0, 6))

        input_row = tk.Frame(hotkey_box.body, bg=self.theme["card_bg"])
        input_row.pack(fill=tk.X, pady=(0, 6))

        # Default button with high-res reset vector icon
        def_btn = ModernButton(
            input_row,
            text="افتراضي",
            icon_name="reset",
            width=100,
            height=34,
            radius=12,
            bg=self.theme["secondary_bg"],
            fg=self.theme["secondary_fg"],
            hover_bg=self.theme["secondary_hover"],
            pressed_bg=self.theme["secondary_pressed"],
            border_color=self.theme["card_border"],
            command=lambda: self.set_hotkey_value("ctrl+t")
        )
        def_btn.pack(side=tk.LEFT, padx=(0, 8))

        # Record button with high-res microphone vector icon
        self.record_btn = ModernButton(
            input_row,
            text="تسجيل اختصار",
            icon_name="mic",
            width=135,
            height=34,
            radius=12,
            bg=self.theme["secondary_bg"],
            fg=self.theme["secondary_fg"],
            hover_bg=self.theme["secondary_hover"],
            pressed_bg=self.theme["secondary_pressed"],
            border_color=self.theme["card_border"],
            command=self.toggle_record_hotkey
        )
        self.record_btn.pack(side=tk.LEFT, padx=(0, 8))

        # Entry - matching height and centered text
        current_hotkey = self.config.get("hotkey", "ctrl+t")
        self.hotkey_entry = ModernEntry(
            input_row,
            height=34,
            radius=12,
            bg=self.theme["input_bg"],
            fg=self.theme["input_fg"],
            border_color=self.theme["input_border"],
            focus_border=self.theme["primary"],
            parent_bg=self.theme["card_bg"],
            font=("Consolas", 11, "bold"),
            justify="center"
        )
        self.hotkey_entry.insert(0, current_hotkey)
        self.hotkey_entry.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        # Quick preset chips
        preset_row = tk.Frame(hotkey_box.body, bg=self.theme["card_bg"])
        preset_row.pack(fill=tk.X, pady=(2, 0))

        tk.Label(
            preset_row,
            text="اختصارات شائعة:",
            font=("Segoe UI", 8),
            fg=self.theme["text_dim"],
            bg=self.theme["card_bg"]
        ).pack(side=tk.RIGHT, padx=(6, 0))

        presets = ["ctrl+t", "alt+t", "ctrl+shift+t", "f2", "alt+q"]
        for p in presets:
            p_btn = ModernButton(
                preset_row,
                text=p,
                width=68,
                height=26,
                radius=10,
                bg=self.theme["preset_bg"],
                fg=self.theme["preset_fg"],
                hover_bg=self.theme["preset_hover"],
                pressed_bg=self.theme["preset_pressed"],
                border_color=self.theme["card_border"],
                font=("Consolas", 8, "bold"),
                command=lambda val=p: self.set_hotkey_value(val)
            )
            p_btn.pack(side=tk.RIGHT, padx=2)

        # Confirm / Apply Hotkey Row
        confirm_row = tk.Frame(hotkey_box.body, bg=self.theme["card_bg"])
        confirm_row.pack(fill=tk.X, pady=(8, 2))

        self.apply_hotkey_btn = ModernButton(
            confirm_row,
            text="اعتماد وتطبيق الاختصار الآن",
            icon_name="check",
            width=230,
            height=34,
            radius=12,
            bg=self.theme["primary"],
            fg=self.theme["primary_fg"],
            hover_bg=self.theme["primary_hover"],
            pressed_bg=self.theme["primary_pressed"],
            command=self.apply_current_hotkey
        )
        self.apply_hotkey_btn.pack(side=tk.RIGHT)

        self.hotkey_status_lbl = tk.Label(
            confirm_row,
            text="",
            font=("Segoe UI", 8, "bold"),
            fg=self.theme["success"],
            bg=self.theme["card_bg"]
        )
        self.hotkey_status_lbl.pack(side=tk.LEFT, padx=6)

        # 2. Target Language Selector (Dead-centered text + Clean rounded chevron ⌄ as requested in Image 1 & 2)
        lang_box = ModernCard(
            parent,
            title="🌐 لغة الترجمة المستهدفة",
            theme_name=self.current_theme
        )
        lang_box.pack(fill=tk.X, pady=(0, 10))

        current_lang_code = self.config.get("target_language", "ar")
        current_lang_display = TARGET_LANGUAGES.get(current_lang_code, TARGET_LANGUAGES["ar"])
        self.target_lang_var = tk.StringVar(value=current_lang_display)

        # Modern Language Dropdown with centered text, chevron toggle, and rounded popup
        self.lang_dropdown = ModernLanguageDropdown(
            parent=lang_box.body,
            languages_dict=TARGET_LANGUAGES,
            current_code=current_lang_code,
            on_change=self.on_target_language_changed,
            theme_name=self.current_theme
        )
        self.lang_dropdown.pack(fill=tk.X)

        # 3. Translation Mode
        mode_box = ModernCard(
            parent,
            title="⚙️ وضع تشغيل الترجمة",
            theme_name=self.current_theme
        )
        mode_box.pack(fill=tk.X, pady=(0, 10))

        self.mode_var = tk.StringVar(value=self.config.get("translation_mode", "auto"))
        mode_options = [
            ("auto", "تلقائي (عدسة Google مع تحويل فوري للأوفلاين عند انقطاع النت) - موصى به"),
            ("offline", "محلي فقط بدون إنترنت (Offline Mode) - خصوصية كاملة وسرعة فائقة"),
            ("online", "سحابي فقط عبر عدسة Google (Online Only)")
        ]
        self.mode_group = ModernRadioGroup(
            mode_box.body,
            options=mode_options,
            variable=self.mode_var,
            theme_name=self.current_theme
        )
        self.mode_group.pack(fill=tk.X, pady=2)

        # 4. Startup & Background Card
        chk_box = ModernCard(
            parent,
            title="🚀 بدء التشغيل والعمل بالخلفية",
            theme_name=self.current_theme
        )
        chk_box.pack(fill=tk.X, pady=(0, 14))

        self.auto_copy_var = tk.BooleanVar(value=self.config.get("auto_copy_translation", True))
        chk1 = ModernCheckbox(
            chk_box.body,
            text="نسخ الترجمة تلقائياً إلى الحافظة فور الانتهاء",
            variable=self.auto_copy_var,
            bg=self.theme["card_bg"],
            fg=self.theme["text_primary"],
            active_top=self.theme["primary"],
            active_bot=self.theme["primary_pressed"],
            border_color=self.theme["card_border"],
            radius=6
        )
        chk1.pack(anchor=tk.E, pady=(2, 4))

        self.startup_var = tk.BooleanVar(value=is_startup_enabled())
        chk2 = ModernCheckbox(
            chk_box.body,
            text="التشغيل التلقائي مع بدء تشغيل Windows",
            variable=self.startup_var,
            bg=self.theme["card_bg"],
            fg=self.theme["text_primary"],
            active_top=self.theme["primary"],
            active_bot=self.theme["primary_pressed"],
            border_color=self.theme["card_border"],
            radius=6
        )
        chk2.pack(anchor=tk.E, pady=(2, 4))

        self.show_on_startup_var = tk.BooleanVar(value=self.config.get("show_settings_on_startup", self.config.get("show_launcher_on_startup", True)))
        chk3 = ModernCheckbox(
            chk_box.body,
            text="فتح لوحة التحكم والإعدادات تلقائياً عند بدء التشغيل",
            variable=self.show_on_startup_var,
            bg=self.theme["card_bg"],
            fg=self.theme["text_primary"],
            active_top=self.theme["primary"],
            active_bot=self.theme["primary_pressed"],
            border_color=self.theme["card_border"],
            radius=6
        )
        chk3.pack(anchor=tk.E, pady=(2, 8))

    def on_target_language_changed(self, code, display_name):
        self.target_lang_var.set(display_name)

    def set_hotkey_value(self, val):
        self.stop_recording_hotkey()
        self.hotkey_entry.delete(0, tk.END)
        self.hotkey_entry.insert(0, val)
        self.apply_current_hotkey()

    def toggle_record_hotkey(self):
        if self.is_recording:
            self.stop_recording_hotkey()
        else:
            self.start_recording_hotkey()

    def start_recording_hotkey(self):
        self.is_recording = True
        if hasattr(self, "record_btn") and self.record_btn:
            self.record_btn.config(
                icon_name=None,
                text="🔴 اضغط المفاتيح...",
                bg=self.theme["danger"],
                fg="#ffffff"
            )
        if hasattr(self, "hotkey_entry") and self.hotkey_entry:
            self.hotkey_entry.delete(0, tk.END)
            self.hotkey_entry.insert(0, "اضغط المفاتيح معاً...")
        if self.win:
            self.win.focus_set()
            self.record_bind_id = self.win.bind("<KeyPress>", self.on_record_key_press)

    def stop_recording_hotkey(self):
        self.is_recording = False
        if hasattr(self, "record_btn") and self.record_btn:
            self.record_btn.config(
                icon_name="mic",
                text="تسجيل اختصار",
                bg=self.theme["secondary_bg"],
                fg=self.theme["secondary_fg"]
            )
        if hasattr(self, "record_bind_id") and self.record_bind_id and self.win:
            try:
                self.win.unbind("<KeyPress>", self.record_bind_id)
            except Exception:
                pass
            self.record_bind_id = None

    def apply_current_hotkey(self):
        hotkey_str = self.hotkey_entry.get().strip().lower()
        if not hotkey_str or "..." in hotkey_str:
            if hasattr(self, "hotkey_status_lbl"):
                self.hotkey_status_lbl.config(text="❌ يرجى إدخال أو تسجيل اختصار صالح أولاً!", fg=self.theme["danger"])
            return

        try:
            keyboard.parse_hotkey(hotkey_str)
        except Exception:
            if hasattr(self, "hotkey_status_lbl"):
                self.hotkey_status_lbl.config(text=f"❌ الاختصار '{hotkey_str}' غير صالح كاختصار ويندوز!", fg=self.theme["danger"])
            return

        self.config["hotkey"] = hotkey_str
        save_config(self.config)
        if self.on_saved:
            self.on_saved(self.config)

        if hasattr(self, "hotkey_status_lbl"):
            self.hotkey_status_lbl.config(
                text=f"✓ تم اعتماد وتطبيق الاختصار ({hotkey_str}) بنجاح!",
                fg=self.theme["success"]
            )

    def on_record_key_press(self, event):
        if not self.is_recording:
            return

        vk = event.keycode
        keysym = event.keysym
        if keysym == "Escape" or vk == 27:
            self.stop_recording_hotkey()
            self.hotkey_entry.delete(0, tk.END)
            self.hotkey_entry.insert(0, self.config.get("hotkey", "ctrl+t"))
            return "break"

        parts = []
        state = event.state

        # Check physical / logical key state using Win32 API to avoid NumLock (0x0008) or CapsLock (0x0002) false positives
        VK_CONTROL = 0x11
        VK_MENU = 0x12       # Alt key
        VK_SHIFT = 0x10
        VK_LWIN = 0x5B
        VK_RWIN = 0x5C

        try:
            get_async_key = ctypes.windll.user32.GetAsyncKeyState
            is_down = lambda code: bool(get_async_key(code) & 0x8000)
        except Exception:
            is_down = lambda code: False

        is_ctrl = is_down(VK_CONTROL) or bool(state & 0x0004) or vk in (17, 162, 163) or keysym.lower().startswith("control")
        # CRITICAL: Do NOT check (state & 0x0008) - on Windows Tkinter, 0x0008 is NumLock!
        is_alt = is_down(VK_MENU) or bool(state & 0x20000) or vk in (18, 164, 165) or keysym.lower().startswith("alt")
        is_shift = is_down(VK_SHIFT) or bool(state & 0x0001) or vk in (16, 160, 161) or keysym.lower().startswith("shift")
        is_win = is_down(VK_LWIN) or is_down(VK_RWIN) or bool(state & 0x0040) or vk in (91, 92) or keysym.lower().startswith("win")

        if is_ctrl and "ctrl" not in parts:
            parts.append("ctrl")
        if is_alt and "alt" not in parts:
            parts.append("alt")
        if is_shift and "shift" not in parts:
            parts.append("shift")
        if is_win and "windows" not in parts:
            parts.append("windows")

        # Ignore modifier keys alone or lock toggles: Shift, Ctrl, Alt, Win, CapsLock (20), NumLock (144), ScrollLock (145)
        if vk in (16, 17, 18, 20, 91, 92, 144, 145, 160, 161, 162, 163, 164, 165) or keysym.lower() in (
            "shift_l", "shift_r", "control_l", "control_r", "alt_l", "alt_r",
            "caps_lock", "num_lock", "scroll_lock", "win_l", "win_r"
        ):
            preview = "+".join(parts) + "+..." if parts else "اضغط مفتاحاً إضافياً..."
            self.hotkey_entry.delete(0, tk.END)
            self.hotkey_entry.insert(0, preview)
            return "break"

        vk_map = {
            8: "backspace", 9: "tab", 13: "enter", 19: "pause",
            32: "space", 33: "page up", 34: "page down", 35: "end",
            36: "home", 37: "left", 38: "up", 39: "right", 40: "down",
            45: "insert", 46: "delete",
        }
        for i in range(1, 13):
            vk_map[111 + i] = f"f{i}"
        for i in range(65, 91):
            vk_map[i] = chr(i).lower()
        for i in range(48, 58):
            vk_map[i] = chr(i)

        k = vk_map.get(vk, keysym.lower())
        if k not in parts:
            parts.append(k)

        combo = "+".join(parts)
        self.hotkey_entry.delete(0, tk.END)
        self.hotkey_entry.insert(0, combo)
        self.stop_recording_hotkey()
        self.apply_current_hotkey()
        return "break"

    # ---------------- Tab 2: How to Use ----------------
    def setup_how_to_use_tab(self, parent):
        container = tk.Frame(parent, bg=self.theme["bg"])
        container.pack(fill=tk.BOTH, expand=True)

        hk_label = self.config.get("hotkey", "ctrl+t").upper()
        sec_hk = "CTRL+SHIFT+T"

        # Card 1: Three Instructions Points
        card1 = ModernCard(
            container,
            title="⚡ كيفية استخدام الترجمة فوراً على أي شاشة",
            theme_name=self.current_theme
        )
        card1.pack(fill=tk.X, pady=(0, 10))

        # Point 1 (Rounded Capsule)
        p1_box = ModernCard(
            card1.body,
            radius=10,
            bg=self.theme["secondary_bg"],
            border=self.theme["card_border"],
            parent_bg=self.theme["card_bg"],
            padx=10,
            pady=8
        )
        p1_box.pack(fill=tk.X, pady=(0, 6))

        tk.Label(
            p1_box.body,
            text="1. لترجمة كامل الشاشة كصورة مباشرة 100%:",
            font=("Segoe UI", 9, "bold"),
            fg=self.theme["text_primary"],
            bg=self.theme["secondary_bg"]
        ).pack(anchor=tk.E)

        tk.Label(
            p1_box.body,
            text=f"اضغط الاختصار  [ {hk_label} ]  في أي وقت فوق أي برنامج أو لعبة أو متصفح أو مستند.",
            font=("Segoe UI", 9),
            fg=self.theme["text_secondary"],
            bg=self.theme["secondary_bg"]
        ).pack(anchor=tk.E, pady=(2, 0))

        # Point 2 (Rounded Capsule)
        p2_box = ModernCard(
            card1.body,
            radius=10,
            bg=self.theme["secondary_bg"],
            border=self.theme["card_border"],
            parent_bg=self.theme["card_bg"],
            padx=10,
            pady=8
        )
        p2_box.pack(fill=tk.X, pady=(0, 6))

        tk.Label(
            p2_box.body,
            text="2. لتحديد وقص منطقة معينة وترجمتها:",
            font=("Segoe UI", 9, "bold"),
            fg=self.theme["text_primary"],
            bg=self.theme["secondary_bg"]
        ).pack(anchor=tk.E)

        tk.Label(
            p2_box.body,
            text=f"اضغط الاختصار  [ {sec_hk} ]  ثم اسحب بمؤشر الماوس لتحديد النص أو الصندوق المطلوب.",
            font=("Segoe UI", 9),
            fg=self.theme["text_secondary"],
            bg=self.theme["secondary_bg"]
        ).pack(anchor=tk.E, pady=(2, 0))

        # Point 3 (Rounded Capsule)
        p3_box = ModernCard(
            card1.body,
            radius=10,
            bg=self.theme["secondary_bg"],
            border=self.theme["card_border"],
            parent_bg=self.theme["card_bg"],
            padx=10,
            pady=8
        )
        p3_box.pack(fill=tk.X)

        tk.Label(
            p3_box.body,
            text="3. للإغلاق والخروج السريع من شاشة الترجمة:",
            font=("Segoe UI", 9, "bold"),
            fg=self.theme["text_primary"],
            bg=self.theme["secondary_bg"]
        ).pack(anchor=tk.E)

        tk.Label(
            p3_box.body,
            text="اضغط زر  [ Esc ]  أو زر  [ Enter ]  أو علامة  [ ✕ ]  للخروج فوراً والعودة لسطح المكتب.",
            font=("Segoe UI", 9),
            fg=self.theme["text_secondary"],
            bg=self.theme["secondary_bg"]
        ).pack(anchor=tk.E, pady=(2, 0))

        # Card 2: Engine Status
        status_box = ModernCard(
            container,
            title="📊 حالة محركات الذكاء الاصطناعي والترجمة",
            theme_name=self.current_theme
        )
        status_box.pack(fill=tk.X, pady=(0, 10))

        st_row1 = tk.Frame(status_box.body, bg=self.theme["card_bg"])
        st_row1.pack(fill=tk.X, pady=2)
        tk.Label(st_row1, text="🌐 ترجمة عدسة Google الذكية (Google Lens):", font=("Segoe UI", 8, "bold"), fg=self.theme["text_primary"], bg=self.theme["card_bg"]).pack(side=tk.RIGHT)
        tk.Label(st_row1, text="🟢 متصلة وجاهزة", font=("Segoe UI", 8, "bold"), fg=self.theme["success"], bg=self.theme["card_bg"]).pack(side=tk.LEFT)

        st_row2 = tk.Frame(status_box.body, bg=self.theme["card_bg"])
        st_row2.pack(fill=tk.X, pady=2)
        tk.Label(st_row2, text="📴 الترجمة بدون إنترنت (RapidOCR + Argos MT):", font=("Segoe UI", 8, "bold"), fg=self.theme["text_primary"], bg=self.theme["card_bg"]).pack(side=tk.RIGHT)
        tk.Label(st_row2, text="🟢 مثبتة ومفعلة محلياً", font=("Segoe UI", 8, "bold"), fg=self.theme["success"], bg=self.theme["card_bg"]).pack(side=tk.LEFT)

        # Card 3: Test Translation Buttons
        btn_row = tk.Frame(container, bg=self.theme["bg"])
        btn_row.pack(fill=tk.X, pady=(4, 0))

        test_fs_btn = ModernButton(
            btn_row,
            text="ترجمة كامل الشاشة للتجربة",
            icon_name="play",
            width=240,
            height=36,
            radius=14,
            bg=self.theme["primary"],
            fg=self.theme["primary_fg"],
            hover_bg=self.theme["primary_hover"],
            pressed_bg=self.theme["primary_pressed"],
            command=self.trigger_test_fs
        )
        test_fs_btn.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=(4, 0))

        test_snip_btn = ModernButton(
            btn_row,
            text="تجربة تحديد وقص منطقة",
            icon_name="guide",
            width=200,
            height=36,
            radius=14,
            bg=self.theme["secondary_bg"],
            fg=self.theme["text_primary"],
            hover_bg=self.theme["secondary_hover"],
            pressed_bg=self.theme["secondary_pressed"],
            border_color=self.theme["card_border"],
            command=self.trigger_test_snip
        )
        test_snip_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 4))

    def trigger_test_fs(self):
        if self.on_translate_fullscreen:
            self.win.withdraw()
            self.root.after(250, self.on_translate_fullscreen)

    def trigger_test_snip(self):
        if self.on_translate_snipping:
            self.win.withdraw()
            self.root.after(250, self.on_translate_snipping)

    # ---------------- Tab 3: Offline Translation ----------------
    def setup_offline_tab(self, parent):
        # Engine Status Banner
        status_card = ModernCard(
            parent,
            title="⚡ محرك الترجمة المحلي (Offline Engine): جاهز ومفعّل",
            theme_name=self.current_theme
        )
        status_card.pack(fill=tk.X, pady=(0, 10))

        tk.Label(
            status_card.body,
            text="يستخدم RapidOCR للتعرف الضوئي وArgos Neural MT للترجمة الذاتية دون أي اتصال بالإنترنت.",
            font=("Segoe UI", 8),
            fg=self.theme["text_secondary"],
            bg=self.theme["card_bg"],
            wraplength=510,
            justify=tk.RIGHT
        ).pack(anchor=tk.E, pady=(2, 0))

        # Test Box
        test_box = ModernCard(
            parent,
            title="🧪 اختبار الترجمة بدون إنترنت للتحقق من السرعة والدقة",
            theme_name=self.current_theme
        )
        test_box.pack(fill=tk.X, pady=(0, 10))

        self.test_btn = ModernButton(
            test_box.body,
            text="اختبار الترجمة بدون إنترنت الآن",
            icon_name="flask",
            width=230,
            height=34,
            radius=12,
            bg=self.theme["primary"],
            fg=self.theme["primary_fg"],
            hover_bg=self.theme["primary_hover"],
            pressed_bg=self.theme["primary_pressed"],
            command=self.run_offline_test
        )
        self.test_btn.pack(anchor=tk.E, pady=(0, 4))

        self.test_result_lbl = tk.Label(
            test_box.body,
            text="اضغط على زر الاختبار أعلاه للتحقق الفوري من سرعة ودقة الترجمة بدون إنترنت.",
            font=("Segoe UI", 8),
            fg=self.theme["text_primary"],
            bg=self.theme["card_bg"],
            wraplength=510,
            justify=tk.RIGHT
        )
        self.test_result_lbl.pack(anchor=tk.E)

        # Available Language Packages Section
        pkg_box = ModernCard(
            parent,
            title="📦 حزم اللغات المتاحة للترجمة بدون إنترنت",
            theme_name=self.current_theme
        )
        pkg_box.pack(fill=tk.BOTH, expand=True)

        self.pkg_list_frame = tk.Frame(pkg_box.body, bg=self.theme["card_bg"])
        self.pkg_list_frame.pack(fill=tk.BOTH, expand=True)

        self.refresh_packages_list()

    def refresh_packages_list(self):
        for widget in self.pkg_list_frame.winfo_children():
            widget.destroy()

        catalog = OfflineManager.get_supported_packages_catalog()
        for pkg in catalog:
            row = ModernCard(
                self.pkg_list_frame,
                radius=10,
                bg=self.theme["card_bg"],
                border=self.theme["card_border"],
                parent_bg=self.theme["card_bg"],
                padx=8,
                pady=4
            )
            row.pack(fill=tk.X, pady=2)

            if pkg["installed"]:
                tk.Label(
                    row.body,
                    text="✓ مثبتة ومفعّلة",
                    font=("Segoe UI", 8, "bold"),
                    fg=self.theme["success"],
                    bg=self.theme["card_bg"]
                ).pack(side=tk.LEFT, padx=6)
            else:
                dl_btn = ModernButton(
                    row.body,
                    text="تحميل وتثبيت",
                    icon_name="download",
                    width=115,
                    height=28,
                    radius=10,
                    bg=self.theme["primary"],
                    fg=self.theme["primary_fg"],
                    hover_bg=self.theme["primary_hover"],
                    pressed_bg=self.theme["primary_pressed"],
                    command=lambda f=pkg["from"], t=pkg["to"], l=pkg["label"]: self.download_package(f, t, l)
                )
                dl_btn.pack(side=tk.LEFT, padx=6)

            info_frame = tk.Frame(row.body, bg=self.theme["card_bg"])
            info_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

            tk.Label(
                info_frame,
                text=pkg["label"],
                font=("Segoe UI", 8, "bold"),
                fg=self.theme["text_primary"],
                bg=self.theme["card_bg"]
            ).pack(anchor=tk.E)

            tk.Label(
                info_frame,
                text=pkg["desc"],
                font=("Segoe UI", 7),
                fg=self.theme["text_secondary"],
                bg=self.theme["card_bg"]
            ).pack(anchor=tk.E)

    def run_offline_test(self):
        self.test_btn.config(state="disabled", text="⏳ جاري الاختبار...")
        self.test_result_lbl.config(text="جاري معالجة الجملة عبر المحرك العصبي المحلي...", fg=self.theme["primary"])

        def task():
            res = OfflineManager.test_offline_translation("en", "ar")
            self.win.after(0, lambda: self.on_offline_test_finished(res))

        threading.Thread(target=task, daemon=True).start()

    def on_offline_test_finished(self, res):
        self.test_btn.config(state="normal", text="اختبار الترجمة بدون إنترنت الآن", icon_name="flask")
        if res.get("success", False):
            self.test_result_lbl.config(
                text=f"✓ نجح الاختبار ({res['elapsed_ms']} ميلي ثانية):\nالنص: \"{res['output']}\"",
                fg=self.theme["success"]
            )
        else:
            self.test_result_lbl.config(
                text=f"تعذر الاختبار: {res.get('error', 'خطأ غير معروف')}",
                fg=self.theme["danger"]
            )

    def download_package(self, from_code, to_code, label):
        if self.downloading_now:
            messagebox.showinfo("تنبيه", "يوجد بالفعل تحميل قيد التنفيذ، يرجى الانتظار حتى اكتماله.")
            return

        self.downloading_now = True
        self.test_result_lbl.config(
            text=f"⏳ جاري تحميل وتثبيت حزمة ({label})... يرجى الانتظار...",
            fg=self.theme["primary"]
        )

        def task():
            def progress(msg):
                self.win.after(0, lambda: self.test_result_lbl.config(text=msg, fg=self.theme["primary"]))

            ok, msg = OfflineManager.download_and_install_package(from_code, to_code, progress_callback=progress)
            self.win.after(0, lambda: self.on_download_finished(ok, msg))

        threading.Thread(target=task, daemon=True).start()

    def on_download_finished(self, success, message):
        self.downloading_now = False
        self.refresh_packages_list()
        if success:
            self.test_result_lbl.config(text=f"✓ {message}", fg=self.theme["success"])
            messagebox.showinfo("نجاح التثبيت", message)
        else:
            self.test_result_lbl.config(text=f"❌ {message}", fg=self.theme["danger"])
            messagebox.showwarning("خطأ في التحميل", message)

    # ---------------- Tab 4: Updates ----------------
    def setup_updates_tab(self, parent):
        curr_card = ModernCard(parent, theme_name=self.current_theme)
        curr_card.pack(fill=tk.X, pady=(0, 10))

        v_row = tk.Frame(curr_card.body, bg=self.theme["card_bg"])
        v_row.pack(fill=tk.X)

        tk.Label(
            v_row,
            text=f"الإصدار المثبت حالياً:  v{CURRENT_VERSION}",
            font=("Segoe UI", 10, "bold"),
            fg=self.theme["primary"],
            bg=self.theme["card_bg"]
        ).pack(side=tk.RIGHT)

        tk.Label(
            v_row,
            text="🟢 الحالة: مستقر",
            font=("Segoe UI", 9),
            fg=self.theme["success"],
            bg=self.theme["card_bg"]
        ).pack(side=tk.LEFT)

        tk.Label(
            curr_card.body,
            text="المستودع السحابي: GitHub (riadsaleem/Smart-Screen-Translator-PC)",
            font=("Segoe UI", 8),
            fg=self.theme["text_dim"],
            bg=self.theme["card_bg"]
        ).pack(anchor=tk.E, pady=(4, 8))

        self.check_update_btn = ModernButton(
            curr_card.body,
            text="فحص التحديثات الآن",
            icon_name="updates",
            width=180,
            height=34,
            radius=12,
            bg=self.theme["primary"],
            fg=self.theme["primary_fg"],
            hover_bg=self.theme["primary_hover"],
            pressed_bg=self.theme["primary_pressed"],
            command=self.start_check_updates
        )
        self.check_update_btn.pack(anchor=tk.E)

        self.upd_card = ModernCard(
            parent,
            title="📋 تفاصيل التحديث الأخير والتحسينات",
            theme_name=self.current_theme
        )
        self.upd_card.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.upd_status_lbl = tk.Label(
            self.upd_card.body,
            text="اضغط على زر 'فحص التحديثات الآن' للتحقق من وجود إصدارات جديدة.",
            font=("Segoe UI", 9),
            fg=self.theme["text_secondary"],
            bg=self.theme["card_bg"],
            wraplength=510,
            justify=tk.RIGHT
        )
        self.upd_status_lbl.pack(anchor=tk.E, pady=(0, 6))

        self.upd_type_lbl = tk.Label(
            self.upd_card.body,
            text="",
            font=("Segoe UI", 8, "bold"),
            fg=self.theme["primary"],
            bg=self.theme["card_bg"],
            padx=8,
            pady=4,
            relief=tk.FLAT,
            wraplength=510,
            justify=tk.RIGHT
        )

        self.changelog_box = ModernCard(
            self.upd_card.body,
            title=" سجل التغييرات والتحسينات ",
            radius=10,
            bg=self.theme["card_bg"],
            border=self.theme["card_border"],
            parent_bg=self.theme["card_bg"],
            padx=8,
            pady=6
        )

        self.changelog_lbl = tk.Label(
            self.changelog_box.body,
            text="",
            font=("Segoe UI", 8),
            fg=self.theme["text_primary"],
            bg=self.theme["card_bg"],
            justify=tk.RIGHT,
            anchor=tk.E,
            wraplength=480
        )
        self.changelog_lbl.pack(fill=tk.X, anchor=tk.E)

        style = ttk.Style()
        style.theme_use("clam")
        pbar_trough = self.theme["secondary_bg"]
        pbar_bar = self.theme["primary"]
        style.configure("Update.Horizontal.TProgressbar", troughcolor=pbar_trough, background=pbar_bar, bordercolor=self.theme["card_border"])

        self.upd_pbar = ttk.Progressbar(
            self.upd_card.body,
            style="Update.Horizontal.TProgressbar",
            orient=tk.HORIZONTAL,
            mode="determinate"
        )

        self.upd_progress_lbl = tk.Label(
            self.upd_card.body,
            text="",
            font=("Segoe UI", 8),
            fg=self.theme["text_secondary"],
            bg=self.theme["card_bg"]
        )

        self.action_update_btn = ModernButton(
            self.upd_card.body,
            text="تنزيل وتثبيت التحديث الآن",
            icon_name="download",
            width=210,
            height=34,
            radius=12,
            bg=self.theme["primary"],
            fg=self.theme["primary_fg"],
            hover_bg=self.theme["primary_hover"],
            pressed_bg=self.theme["primary_pressed"],
            command=self.start_download_update
        )
        self.action_update_btn.config(state="disabled")
        self.action_update_btn.pack(side=tk.BOTTOM, anchor=tk.E, pady=(6, 0))

    def start_check_updates(self):
        if self.is_checking_update or self.is_downloading_update:
            return
        self.is_checking_update = True
        self.check_update_btn.config(text="⏳ جاري الفحص...", state="disabled")
        self.upd_status_lbl.config(text="⏳ جاري الاتصال بمستودع GitHub وفحص ملف الإصدارات...", fg=self.theme["primary"])
        self.action_update_btn.config(state="disabled")

        threading.Thread(target=self._thread_check_updates, daemon=True).start()

    def _thread_check_updates(self):
        res = check_for_updates(config=self.config)
        self.win.after(0, lambda: self._on_check_updates_result(res))

    def _on_check_updates_result(self, res):
        self.is_checking_update = False
        self.check_update_btn.config(text="🔄 فحص التحديثات الآن", state="normal")

        if not res.get("success"):
            err = res.get("error", "فشل غير معروف.")
            self.upd_status_lbl.config(text=f"❌ فشل فحص التحديثات: {err}", fg=self.theme["danger"])
            self.upd_type_lbl.pack_forget()
            self.changelog_box.pack_forget()
            self.action_update_btn.config(state="disabled")
            return

        if not res.get("update_available"):
            self.upd_status_lbl.config(
                text=f"✓ أنت تستخدم أحدث إصدار متوفر بالفعل! (v{CURRENT_VERSION})",
                fg=self.theme["success"]
            )
            self.upd_type_lbl.pack_forget()
            self.changelog_box.pack_forget()
            self.action_update_btn.config(state="disabled")
            return

        self.update_info = res
        latest = res.get("latest_version", "")
        title = res.get("title", f"الإصدار {latest}")
        upd_type = res.get("update_type", "patch")

        self.upd_status_lbl.config(
            text=f"🎉 يتوفر إصدار أحدث: {title} (v{latest})",
            fg=self.theme["primary"]
        )

        if upd_type == "patch":
            p_size = res.get("patch_size_mb", 1.0)
            self.upd_type_lbl.config(
                text=f"⚡ نوع التحديث: تحديث فرعي خفيف وسريع (Delta Patch)\n"
                     f"• سيتم تنزيل التعديلات الأخيرة فقط بحجم (~{p_size} ميجابايت) بدلاً من إعادة تنزيل كامل التطبيق!",
                fg=self.theme["success"],
                bg=self.theme["secondary_bg"]
            )
            self.action_update_btn.config(text="🚀 تنزيل وتثبيت التحديث الفرعي السريع الآن", state="normal")
        else:
            f_size = res.get("full_installer_size_mb", 180.0)
            self.upd_type_lbl.config(
                text=f"📦 نوع التحديث: تحديث رئيسي شامل (Full Upgrade)\n"
                     f"• يتطلب تنزيل حزمة التثبيت الكاملة بحجم (~{f_size} ميجابايت) لتحديث البنية الأساسية.",
                fg=self.theme["primary"],
                bg=self.theme["secondary_bg"]
            )
            self.action_update_btn.config(text="🚀 تنزيل حزمة التثبيت الشاملة الآن", state="normal")

        self.upd_type_lbl.pack(fill=tk.X, anchor=tk.E, pady=(0, 6))

        changelog_items = res.get("changelog", [])
        if changelog_items:
            lines = [f"• {item}" for item in changelog_items]
            self.changelog_lbl.config(text="\n".join(lines))
            self.changelog_box.pack(fill=tk.X, pady=(0, 6))
        else:
            self.changelog_box.pack_forget()

    def start_download_update(self):
        if not self.update_info or self.is_downloading_update:
            return

        self.is_downloading_update = True
        self.action_update_btn.config(state="disabled", text="⏳ جاري التحميل...")
        self.check_update_btn.config(state="disabled")

        self.upd_pbar.pack(fill=tk.X, pady=(6, 2))
        self.upd_pbar["value"] = 0
        self.upd_progress_lbl.config(text="جاري الاتصال بالسيرفر والبدء بالتحميل...")
        self.upd_progress_lbl.pack(anchor=tk.E, pady=(0, 6))

        threading.Thread(target=self._thread_download_update, daemon=True).start()

    def _thread_download_update(self):
        info = self.update_info
        upd_type = info.get("update_type", "patch")
        token = get_token(self.config)

        import tempfile
        temp_dir = tempfile.gettempdir()

        if upd_type == "patch":
            target_url = info.get("patch_url")
            dest_file = os.path.join(temp_dir, f"SmartScreenTranslator_patch_v{info.get('latest_version')}.zip")
        else:
            target_url = info.get("full_installer_url")
            dest_file = os.path.join(temp_dir, "Setup_SmartScreenTranslator.exe")

        if not target_url:
            target_url = f"https://api.github.com/repos/riadsaleem/Smart-Screen-Translator-PC/releases"

        try:
            success = download_file(
                url=target_url,
                dest_path=dest_file,
                token=token,
                progress_callback=self._on_download_progress
            )
            if success:
                self.win.after(0, lambda: self._on_download_completed(upd_type, dest_file))
            else:
                self.win.after(0, lambda: self._on_download_failed("تم إلغاء عملية التنزيل."))
        except Exception as e:
            self.win.after(0, lambda err=str(e): self._on_download_failed(err))

    def _on_download_progress(self, percent, downloaded_mb, total_mb, status_str):
        self.win.after(0, lambda: self._update_pbar(percent, status_str))

    def _update_pbar(self, percent, status_str):
        self.upd_pbar["value"] = percent
        self.upd_progress_lbl.config(text=f"جاري التحميل: {status_str}")

    def _on_download_completed(self, upd_type, file_path):
        self.is_downloading_update = False
        self.upd_pbar["value"] = 100
        self.upd_progress_lbl.config(text="✓ اكتمل التحميل بنجاح تام!", fg=self.theme["success"])

        if upd_type == "patch":
            ans = messagebox.askyesno(
                "اكتمل تحميل التحديث الفرعي",
                "تم تحميل ملف التحديث الفرعي الخفيف بنجاح!\n\n"
                "هل ترغب في تطبيق التحديث وإعادة تشغيل البرنامج الآن لتفعيل الميزات الجديدة؟"
            )
            if ans:
                ok, msg = apply_delta_patch(file_path)
                if ok:
                    self.win.quit()
                    sys.exit(0)
                else:
                    messagebox.showerror("خطأ في التحديث", msg)
        else:
            ans = messagebox.askyesno(
                "اكتمل تحميل برنامج التثبيت",
                "تم تحميل برنامج التثبيت الشامل Setup_SmartScreenTranslator.exe بنجاح!\n\n"
                "هل ترغب في بدء التثبيت الآن؟"
            )
            if ans:
                launch_full_installer(file_path)
                self.win.quit()
                sys.exit(0)

        self.action_update_btn.config(state="normal", text="🚀 تنزيل وتثبيت التحديث الآن")
        self.check_update_btn.config(state="normal")

    def _on_download_failed(self, error_msg):
        self.is_downloading_update = False
        self.upd_progress_lbl.config(text=f"❌ فشل التحميل: {error_msg}", fg=self.theme["danger"])
        self.action_update_btn.config(state="normal", text="إعادة محاولة التنزيل")
        self.check_update_btn.config(state="normal")
        messagebox.showerror("خطأ أثناء تنزيل التحديث", f"تعذر تنزيل التحديث من الخادم:\n{error_msg}")

    # ---------------- Tab 5: About & Developer Credits ----------------
    def setup_about_tab(self, parent):
        info_card = ModernCard(parent, theme_name=self.current_theme)
        info_card.pack(fill=tk.X, pady=(0, 12))

        tk.Label(
            info_card.body,
            text="مترجم الشاشة الذكي للكمبيوتر (Smart Screen Translator PC)",
            font=("Segoe UI", 11, "bold"),
            fg=self.theme["primary"],
            bg=self.theme["card_bg"]
        ).pack(anchor=tk.E)

        tk.Label(
            info_card.body,
            text=f"الإصدار الاحترافي v{CURRENT_VERSION} • بنية فائقة السرعة للترجمة الذكية عبر عدسة Google وبدون إنترنت 100%",
            font=("Segoe UI", 8),
            fg=self.theme["text_secondary"],
            bg=self.theme["card_bg"],
            justify=tk.RIGHT
        ).pack(anchor=tk.E, pady=(2, 0))

        # Developer Credit Card
        dev_card = ModernCard(
            parent,
            title="👨‍💻 معلومات المطور والجهة البرمجية",
            theme_name=self.current_theme
        )
        dev_card.pack(fill=tk.X, pady=(0, 12))

        tk.Label(
            dev_card.body,
            text="برمجة وتطوير: م. رياض سليم",
            font=("Segoe UI", 10, "bold"),
            fg=self.theme["text_primary"],
            bg=self.theme["card_bg"]
        ).pack(anchor=tk.E, pady=(0, 2))

        tk.Label(
            dev_card.body,
            text="هاتف / واتساب: 775630269",
            font=("Segoe UI", 10, "bold"),
            fg=self.theme["success"],
            bg=self.theme["card_bg"]
        ).pack(anchor=tk.E, pady=(0, 8))

        def open_whatsapp():
            webbrowser.open("https://wa.me/967775630269")

        whatsapp_btn = ModernButton(
            dev_card.body,
            text="تواصل مباشرة عبر واتساب",
            icon_name="whatsapp",
            width=220,
            height=36,
            radius=14,
            bg="#25D366",
            fg="#ffffff",
            hover_bg="#1ebe5d",
            pressed_bg="#179b4b",
            command=open_whatsapp
        )
        whatsapp_btn.pack(anchor=tk.E)

        # Features Summary Card
        feat_card = ModernCard(
            parent,
            title="💡 أبرز ميزات البرنامج وإرشادات الاستخدام",
            theme_name=self.current_theme
        )
        feat_card.pack(fill=tk.BOTH, expand=True)

        features = [
            "⚡ ترجمة فورية للشاشة كاملة أو تحديد منطقة بضغطة زر واحدة.",
            "🌐 تكامل مباشر مع عدسة Google (Google Lens) لتفريغ النصوص والترجمة البصرية.",
            "📴 دعم كامل للترجمة بدون إنترنت (RapidOCR + Argos Neural MT) عند انقطاع الشبكة.",
            "🎨 مظهر عصري يدعم التبديل السلس بين الوضع الداكن والوضع الفاتح بنقرة زر واحدة.",
            "🔍 تكبير وتصغير فائق النقاء بعجلة الماوس أو اختصار Ctrl+A مع فلاتر Lanczos.",
            "📋 شريط تحكم عائم زجاجي مع تبديل سريع للغات ونسخ الترجمة بنقرة واحدة."
        ]
        for f in features:
            tk.Label(
                feat_card.body,
                text=f,
                font=("Segoe UI", 8),
                fg=self.theme["text_secondary"],
                bg=self.theme["card_bg"],
                justify=tk.RIGHT,
                anchor=tk.E
            ).pack(fill=tk.X, pady=2)

    # ---------------- Save Settings ----------------
    def save(self):
        hotkey_str = self.hotkey_entry.get().strip().lower()
        if not hotkey_str:
            messagebox.showwarning("تنبيه", "يرجى إدخال أو تسجيل اختصار للبرنامج!")
            return

        try:
            keyboard.parse_hotkey(hotkey_str)
        except Exception:
            messagebox.showwarning(
                "اختصار غير صالح",
                f"الرمز '{hotkey_str}' غير صالح كاختصار لوحة مفاتيح.\nأمثلة صحيحة: ctrl+t أو alt+t أو ctrl+shift+x"
            )
            return

        target_code = self.lang_dropdown.get_selected_code()

        self.config["hotkey"] = hotkey_str
        self.config["target_language"] = target_code
        self.config["translation_mode"] = self.mode_var.get().strip().lower()
        self.config["auto_copy_translation"] = self.auto_copy_var.get()
        self.config["auto_start"] = self.startup_var.get()
        self.config["theme"] = self.current_theme
        if hasattr(self, "show_on_startup_var"):
            self.config["show_settings_on_startup"] = self.show_on_startup_var.get()
            self.config["show_launcher_on_startup"] = self.show_on_startup_var.get()
        save_config(self.config)

        set_startup(self.startup_var.get())

        if self.on_saved:
            self.on_saved(self.config)

        self._close_window()

    def _close_window(self):
        if self.win:
            try:
                self.win.destroy()
            except Exception:
                pass
            self.win = None
        clear_theme_caches()
        try:
            import gc
            gc.collect()
        except Exception:
            pass
