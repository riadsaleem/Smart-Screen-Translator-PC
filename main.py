import os
import sys

from ui_theme import get_theme, setup_process_app_id, apply_window_icon
setup_process_app_id()

import gc
import socket
import threading
import tkinter as tk
from tkinter import messagebox
from PIL import Image
import pystray
from pystray import MenuItem as item
import keyboard

from config import load_config, save_config
from translator_service import TranslatorService
from screen_snipper import ScreenSnipper, capture_screen_image, get_virtual_screen_bounds
from fullscreen_overlay import FullscreenOverlay
from updater import check_for_updates, CURRENT_VERSION

SINGLE_INSTANCE_PORT = 58921
_wakeup_handler = None
_quit_handler = None


def trim_process_memory():
    """Collects Python garbage to keep idle memory footprint low."""
    try:
        gc.collect()
    except Exception:
        pass

def is_silent_launch():
    """Returns True when launched silently on Windows boot (--startup / --silent / --minimized)."""
    return any(flag in sys.argv for flag in ("--startup", "--silent", "--minimized"))


def init_single_instance(silent_if_running=False):
    """Ensures only a single instance of the application runs at any time."""
    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(("127.0.0.1", SINGLE_INSTANCE_PORT))
        server.listen(5)

        def _listen():
            while True:
                try:
                    conn, _ = server.accept()
                    msg = conn.recv(1024).decode("utf-8")
                    conn.close()
                    if msg == "SHOW" and _wakeup_handler:
                        _wakeup_handler()
                    elif msg == "QUIT" and _quit_handler:
                        _quit_handler()
                        break
                except Exception:
                    break

        t = threading.Thread(target=_listen, daemon=True)
        t.start()
        return True
    except OSError:
        # Address in use: An instance is already running
        if not silent_if_running:
            try:
                client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client.connect(("127.0.0.1", SINGLE_INSTANCE_PORT))
                client.sendall(b"SHOW")
                client.close()
            except Exception:
                pass
        return False

class SmartScreenTranslatorApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()  # Hidden main loop

        self.config = load_config()
        print("==================================================")
        print("مترجم الشاشة الذكي للكمبيوتر (Smart Screen Translator PC)")
        print("تطوير: رياض سليم")
        print("هاتف: 775630269")
        print(f"الإصدار: v{CURRENT_VERSION}")
        print("==================================================")
        self.translator = TranslatorService(
            target_lang=self.config.get("target_language", "ar"),
            mode=self.config.get("translation_mode", "auto")
        )

        self.tray_icon = None
        self.current_hotkey = None
        self.secondary_hotkey = "ctrl+shift+t"
        self.is_busy = False
        self.loading_win = None
        self.active_overlay = None
        self.last_captured_image = None

        def get_res(fname):
            if hasattr(sys, "_MEIPASS"):
                p = os.path.join(sys._MEIPASS, fname)
                if os.path.exists(p):
                    return p
            p2 = os.path.join(os.path.dirname(os.path.abspath(__file__)), fname)
            if os.path.exists(p2):
                return p2
            if getattr(sys, "frozen", False):
                return os.path.join(os.path.dirname(sys.executable), fname)
            return p2

        self.icon_path = get_res("icon.png")
        self.ico_path = get_res("icon.ico")
        apply_window_icon(self.root, self.ico_path, self.icon_path)

        self.settings_win = None

        # Bind wakeup and quit handlers for single-instance / clean updater exit
        global _wakeup_handler, _quit_handler
        _wakeup_handler = lambda: self.root.after(0, lambda: self.open_settings("general"))
        _quit_handler = lambda: self.root.after(0, self.quit_app)

        self.setup_tray()
        self.register_hotkeys()

        # When launched via Windows startup (--startup), stay silently in the system tray to keep boot lightweight
        is_startup_launch = is_silent_launch()
        if not is_startup_launch and self.config.get("show_settings_on_startup", self.config.get("show_launcher_on_startup", False)):
            self.root.after(350, lambda: self.open_settings("general"))

        # Trim initial working set once startup settles so background RAM stays minimal
        self.root.after(2500, trim_process_memory)

        # Schedule silent background update check after startup
        self.root.after(15000, self.check_updates_silently)

    # ---------------- Hotkey Management ----------------
    def register_hotkeys(self):
        hotkey = self.config.get("hotkey", "ctrl+t").lower()
        if self.current_hotkey:
            try:
                keyboard.remove_hotkey(self.current_hotkey)
            except Exception:
                pass

        try:
            keyboard.add_hotkey(hotkey, self.trigger_fullscreen_from_hotkey)
            self.current_hotkey = hotkey
            print(f"Registered primary hotkey: {hotkey}")
        except Exception as e:
            print(f"Failed to register primary hotkey {hotkey}: {e}")

        try:
            keyboard.add_hotkey(self.secondary_hotkey, self.trigger_snipping_from_hotkey)
            print(f"Registered secondary hotkey: {self.secondary_hotkey}")
        except Exception as e:
            print(f"Failed to register secondary hotkey: {e}")

    def trigger_fullscreen_from_hotkey(self):
        self.root.after(10, self.translate_fullscreen_direct)

    def trigger_snipping_from_hotkey(self):
        self.root.after(10, self.start_snipping)

    # ---------------- Direct Fullscreen Translation ----------------
    def translate_fullscreen_direct(self):
        if self.is_busy:
            return
        self.is_busy = True

        full_img = capture_screen_image()
        if not full_img:
            self.is_busy = False
            return

        self.last_captured_image = full_img
        if self.translator.mode == "offline":
            self.show_loading("⏳ جاري ترجمة الشاشة محلياً بدون إنترنت...")
        else:
            self.show_loading("⏳ جاري ترجمة الشاشة وعرضها مباشرة...")
        target_lang = self.config.get("target_language", "ar")
        source_lang = self.config.get("source_language", "auto")
        threading.Thread(
            target=self.do_translation,
            args=(full_img, full_img, None, target_lang, source_lang),
            daemon=True
        ).start()

    # ---------------- Snipping Area Translation ----------------
    def start_snipping(self):
        if self.is_busy:
            return
        self.is_busy = True

        snipper = ScreenSnipper(
            root=self.root,
            on_complete=self.on_snip_completed,
            on_cancel=self.on_snip_cancelled
        )
        snipper.start()

    def on_snip_cancelled(self):
        self.is_busy = False

    def on_snip_completed(self, cropped_img, full_img, crop_box):
        self.last_captured_image = full_img
        if self.translator.mode == "offline":
            self.show_loading("⏳ جاري ترجمة المنطقة المحددة بدون إنترنت...")
        else:
            self.show_loading("⏳ جاري ترجمة المنطقة المحددة...")
        target_lang = self.config.get("target_language", "ar")
        source_lang = self.config.get("source_language", "auto")
        threading.Thread(
            target=self.do_translation,
            args=(cropped_img, full_img, crop_box, target_lang, source_lang),
            daemon=True
        ).start()

    # ---------------- Background Translation ----------------
    def do_translation(self, image, full_image, crop_box, target_lang, source_lang="auto"):
        result = self.translator.translate_image(
            image=image,
            full_image=full_image,
            crop_box=crop_box,
            target_lang=target_lang,
            source_lang=source_lang
        )
        self.root.after(0, lambda: self.on_translation_finished(result))

    def on_translation_finished(self, result):
        self.hide_loading()
        self.is_busy = False

        if not result.get("success", False) or not result.get("overlay_path"):
            err_msg = result.get("error", "تعذر الحصول على الصورة المترجمة.")
            messagebox.showwarning("تنبيه الترجمة", f"لم تنجح الترجمة:\n{err_msg}")
            return

        # Auto-copy translation text if enabled
        if self.config.get("auto_copy_translation", True):
            trans = result.get("translated_text", "")
            if trans:
                self.root.clipboard_clear()
                self.root.clipboard_append(trans)

        # DISPLAY THE TRANSLATED IMAGE FULL SCREEN DIRECTLY OVER THE SCREEN
        det_lang = result.get("detected_language")
        if not det_lang or det_lang == "auto":
            ocr_text = result.get("ocr_text", "")
            has_arabic = any('\u0600' <= c <= '\u06FF' for c in ocr_text)
            det_lang = "ar" if has_arabic else "en"

        self.config = load_config()
        overlay_theme = self.config.get("overlay_theme", "light")
        self.active_overlay = FullscreenOverlay(
            root=self.root,
            overlay_image_path=result["overlay_path"],
            translated_text=result.get("translated_text", ""),
            source_lang=det_lang,
            target_lang=result.get("target_language", "ar"),
            is_offline=result.get("is_offline", False),
            theme_name=overlay_theme,
            on_change_language=self.on_overlay_change_language,
            on_dismiss=self.on_overlay_dismissed
        )
        self.active_overlay.show()

    def on_overlay_dismissed(self):
        self.active_overlay = None
        self.last_captured_image = None
        trim_process_memory()

    def on_overlay_change_language(self, new_lang_code, source_lang=None):
        if self.last_captured_image and self.active_overlay:
            self.config["target_language"] = new_lang_code
            save_config(self.config)
            self.translator.target_lang = new_lang_code

            threading.Thread(
                target=self.do_retranslate,
                args=(self.last_captured_image, new_lang_code, source_lang),
                daemon=True
            ).start()

    def do_retranslate(self, image, new_lang_code, source_lang=None):
        result = self.translator.translate_image(
            image=image,
            full_image=image,
            target_lang=new_lang_code,
            source_lang=source_lang
        )
        self.root.after(0, lambda: self.on_retranslate_finished(result))

    def on_retranslate_finished(self, result):
        if self.active_overlay and result.get("success", False) and result.get("overlay_path"):
            self.active_overlay.update_translated_image(
                new_image_path=result["overlay_path"],
                new_text=result.get("translated_text", ""),
                new_target_lang=result.get("target_language"),
                is_offline=result.get("is_offline", False)
            )
        trim_process_memory()

    # ---------------- Loading Indicator ----------------
    def show_loading(self, message="⏳ جاري الترجمة عبر عدسة Google..."):
        current_theme = get_theme(self.config.get("theme", "dark"))
        self.loading_win = tk.Toplevel(self.root)
        self.loading_win.overrideredirect(True)
        self.loading_win.attributes("-topmost", True)
        self.loading_win.configure(bg=current_theme["card_border"])

        w, h = 420, 52
        left, top, sw, sh = get_virtual_screen_bounds()
        x = left + (sw - w) // 2
        y = top + 24
        self.loading_win.geometry(f"{w}x{h}+{x}+{y}")

        frame = tk.Frame(self.loading_win, bg=current_theme["card_bg"], bd=0, highlightthickness=1, highlightbackground=current_theme["primary"], padx=16, pady=10)
        frame.pack(fill=tk.BOTH, expand=True)

        lbl = tk.Label(
            frame,
            text=message,
            font=("Segoe UI", 11, "bold"),
            fg=current_theme["primary"],
            bg=current_theme["card_bg"]
        )
        lbl.pack(expand=True)
        self.loading_win.update()

    def hide_loading(self):
        if self.loading_win:
            self.loading_win.destroy()
            self.loading_win = None

    # ---------------- System Tray ----------------
    def setup_tray(self):
        if os.path.exists(self.icon_path):
            img = Image.open(self.icon_path)
        else:
            img = Image.new("RGBA", (64, 64), color="#2563eb")

        hotkey_label = self.config.get("hotkey", "ctrl+t").upper()

        menu = pystray.Menu(
            item("🚀 لوحة التحكم والإعدادات", lambda: self.root.after(10, lambda: self.open_settings("general")), default=True),
            item("💡 كيفية الاستخدام", lambda: self.root.after(10, lambda: self.open_settings("how_to_use"))),
            pystray.Menu.SEPARATOR,
            item(f"⚡ ترجمة كامل الشاشة ({hotkey_label})", lambda: self.root.after(10, self.translate_fullscreen_direct)),
            item(f"✂️ تحديد منطقة وترجمتها ({self.secondary_hotkey.upper()})", lambda: self.root.after(10, self.start_snipping)),
            pystray.Menu.SEPARATOR,
            item("🔄 فحص التحديثات", lambda: self.root.after(10, self.open_updates)),
            item("ℹ️ حول البرنامج", lambda: self.root.after(10, self.show_about)),
            pystray.Menu.SEPARATOR,
            item("❌ خروج", self.quit_app)
        )

        self.tray_icon = pystray.Icon("SmartScreenTranslator", img, f"مترجم الشاشة الذكي ({hotkey_label})", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def open_settings(self, tab="general"):
        if not self.settings_win or not self.settings_win.win or not self.settings_win.win.winfo_exists():
            from settings_window import SettingsWindow
            self.settings_win = SettingsWindow(
                self.root,
                on_saved=self.on_settings_saved,
                initial_tab=tab,
                on_translate_fullscreen=self.translate_fullscreen_direct,
                on_translate_snipping=self.start_snipping
            )
        self.settings_win.show(tab)

    def open_updates(self):
        self.open_settings("updates")
        if self.settings_win:
            self.settings_win.start_check_updates()

    def check_updates_silently(self):
        threading.Thread(target=self._thread_silent_update_check, daemon=True).start()

    def _thread_silent_update_check(self):
        try:
            res = check_for_updates(config=self.config)
            if res.get("success") and res.get("update_available"):
                self.root.after(0, lambda: self.notify_update_available(res))
        except Exception:
            pass

    def notify_update_available(self, res):
        latest = res.get("latest_version")
        upd_type = res.get("update_type", "patch")
        p_size = res.get("patch_size_mb", 1.0)
        f_size = res.get("full_installer_size_mb", 180.0)
        
        if upd_type == "patch":
            type_text = f"تحديث فرعي خفيف سريع (Delta Patch) بحجم ~{p_size} ميجابايت فقط"
        else:
            type_text = f"تحديث رئيسي شامل بحجم ~{f_size} ميجابايت"

        ans = messagebox.askyesno(
            "🎉 يتوفر تحديث جديد لمترجم الشاشة",
            f"تم اكتشاف إصدار أحدث على GitHub: {res.get('title')} (v{latest})!\n\n"
            f"• نوع التحديث: {type_text}\n"
            f"• سيتم تنزيل وتطبيق التحديث بسلاسة دون تعقيد.\n\n"
            f"هل ترغب في فتح صفحة التحديثات للمعاينة والتحميل الآن؟"
        )
        if ans:
            self.open_updates()

    def on_settings_saved(self, new_config):
        self.config = new_config
        self.translator.target_lang = self.config.get("target_language", "ar")
        self.translator.mode = self.config.get("translation_mode", "auto")
        self.register_hotkeys()

        hotkey_label = self.config.get("hotkey", "ctrl+t").upper()
        if self.tray_icon:
            self.tray_icon.title = f"مترجم الشاشة الذكي ({hotkey_label})"

    def show_about(self):
        msg = (
            "مترجم الشاشة الذكي للكمبيوتر (Smart Screen Translator PC)\n"
            "الإصدار الاحترافي v2.0\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "👨‍💻 برمجة وتطوير: م. رياض سليم\n"
            "📱 هاتف / واتساب: 775630269\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "• استدعاء مباشر لعدسة Google (Google Lens) بجودة فائقة\n"
            "• دعم كامل للترجمة بدون إنترنت (RapidOCR + Argos Neural MT)\n"
            "• عرض الصورة المترجمة مباشرة فوق الشاشة كاملة 100%\n"
            "• شريط عائم زجاجي حديث لتبديل لغات الترجمة فوراً\n"
            "• تكبير وتصغير فائق النقاء بعجلة الماوس أو Ctrl + A مع إمكانية السحب\n"
            "• دعم إدخال وتسجيل أي اختصار يريده المستخدم بحرية تامة\n"
            "• إغلاق سريع بالضغط على Esc أو Enter أو زر ✕"
        )
        messagebox.showinfo("حول مترجم الشاشة الذكي", msg)

    def quit_app(self):
        try:
            self.translator.close()
        except Exception:
            pass
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.quit()
        sys.exit(0)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    if not init_single_instance(silent_if_running=is_silent_launch()):
        # Another instance is already running
        sys.exit(0)

    try:
        app = SmartScreenTranslatorApp()
        app.run()
    except Exception as e:
        import traceback
        from config import get_user_data_dir
        log_path = os.path.join(get_user_data_dir(), "app.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(traceback.format_exc() + "\n")
