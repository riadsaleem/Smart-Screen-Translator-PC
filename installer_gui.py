import os
import sys
import ctypes

try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SmartScreenTranslator.PC.App.v2_3")
    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
except Exception:
    pass

import zipfile
import threading
import subprocess
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from ui_components import ModernButton, ModernEntry, ModernCheckbox, ModernCard

APP_NAME = "SmartScreenTranslator"
DISPLAY_NAME = "مترجم الشاشة الذكي"
DEV_NAME = "م. رياض سليم"
DEV_PHONE = "775630269"

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def get_bundle_dir():
    if hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

def get_res(fname):
    bundle = get_bundle_dir()
    p = os.path.join(bundle, fname)
    if os.path.exists(p):
        return p
    p2 = os.path.join(os.path.dirname(os.path.abspath(__file__)), fname)
    if os.path.exists(p2):
        return p2
    if getattr(sys, "frozen", False):
        p3 = os.path.join(os.path.dirname(sys.executable), fname)
        if os.path.exists(p3):
            return p3
    return p

def run_hidden(cmd):
    """Executes a command completely hidden with zero console window popup."""
    startupinfo = None
    creationflags = 0
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            startupinfo=startupinfo,
            creationflags=creationflags
        )
    except Exception as e:
        return None

def run_hidden_popen(cmd, cwd=None):
    """Launches a detached process completely hidden without any console window."""
    startupinfo = None
    creationflags = 0
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    try:
        return subprocess.Popen(
            cmd,
            cwd=cwd,
            startupinfo=startupinfo,
            creationflags=creationflags
        )
    except Exception:
        return None

def terminate_app_instances():
    """Gracefully closes any running instance of the application before updating."""
    try:
        import socket
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.settimeout(1.0)
        client.connect(("127.0.0.1", 58921))
        client.sendall(b"QUIT")
        client.close()
        time.sleep(0.8)
        return
    except Exception:
        pass
    run_hidden(["taskkill", "/f", "/im", f"{APP_NAME}.exe"])

def create_windows_shortcut(target_exe, shortcut_path, icon_path=None, work_dir=None, arguments=""):
    if not work_dir:
        work_dir = os.path.dirname(target_exe)
    if not icon_path:
        icon_path = target_exe

    # 1. Direct COM via win32com (in-process, fastest, zero window)
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.TargetPath = target_exe
        shortcut.WorkingDirectory = work_dir
        if arguments:
            shortcut.Arguments = arguments
        shortcut.IconLocation = f"{icon_path},0"
        shortcut.save()
        try:
            ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
        except Exception:
            pass
        return True
    except Exception:
        pass

    # 2. Pure GUI fallback via wscript.exe (wscript is a pure GUI process, NO console window)
    try:
        import tempfile
        vbs_path = os.path.join(tempfile.gettempdir(), "sst_mklnk.vbs")
        arg_line = f'S.Arguments = "{arguments}"\n' if arguments else ""
        vbs_code = (
            f'Set W = WScript.CreateObject("WScript.Shell")\n'
            f'Set S = W.CreateShortcut("{shortcut_path}")\n'
            f'S.TargetPath = "{target_exe}"\n'
            f'S.WorkingDirectory = "{work_dir}"\n'
            f'{arg_line}'
            f'S.IconLocation = "{icon_path},0"\n'
            f'S.Save\n'
        )
        with open(vbs_path, "w", encoding="utf-8") as f:
            f.write(vbs_code)
        run_hidden(["wscript.exe", vbs_path])
        try:
            os.remove(vbs_path)
        except Exception:
            pass
        try:
            ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
        except Exception:
            pass
        return True
    except Exception:
        pass

    # 3. Fallback to PowerShell using CREATE_NO_WINDOW
    try:
        arg_ps = f'$S.Arguments = "{arguments}"; ' if arguments else ""
        ps_script = (
            f'$W = New-Object -ComObject WScript.Shell; '
            f'$S = $W.CreateShortcut("{shortcut_path}"); '
            f'$S.TargetPath = "{target_exe}"; '
            f'$S.WorkingDirectory = "{work_dir}"; '
            f'{arg_ps}'
            f'$S.IconLocation = "{icon_path},0"; '
            f'$S.Save()'
        )
        run_hidden(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_script])
        try:
            ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
        except Exception:
            pass
        return True
    except Exception as e:
        print("Shortcut creation error:", e)
        return False

def sync_auto_start_config(enable=True):
    """Keeps user AppData config auto_start aligned with installer choice."""
    try:
        import json
        appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
        cfg_dir = os.path.join(appdata, APP_NAME)
        cfg_path = os.path.join(cfg_dir, "config.json")
        if os.path.exists(cfg_path):
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["auto_start"] = bool(enable)
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception:
        pass


def get_startup_shortcut_path():
    appdata = os.environ.get("APPDATA", "")
    startup_dir = os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
    return os.path.join(startup_dir, f"{DISPLAY_NAME}.lnk")


def set_windows_startup(target_exe, enable=True, icon_path=None, work_dir=None):
    """Registers or removes autostart via standard Windows Startup folder shortcut."""
    sync_auto_start_config(enable)
    try:
        lnk_path = get_startup_shortcut_path()
        if enable:
            os.makedirs(os.path.dirname(lnk_path), exist_ok=True)
            return create_windows_shortcut(
                target_exe,
                lnk_path,
                icon_path=icon_path or target_exe,
                work_dir=work_dir or os.path.dirname(target_exe),
                arguments="--startup"
            )
        else:
            if os.path.exists(lnk_path):
                os.remove(lnk_path)
            return True
    except Exception as e:
        print("Startup shortcut error:", e)
        return False

def clean_old_internal(install_dir):
    """Removes stale _internal folder from older bloated installs before extracting fresh payload."""
    import shutil
    old_internal = os.path.join(install_dir, "_internal")
    if os.path.exists(old_internal):
        try:
            shutil.rmtree(old_internal, ignore_errors=True)
        except Exception:
            pass

def perform_silent_install():
    """Performs 100% silent, headless installation without showing any UI or console windows."""
    try:
        # 1. Close running instances
        terminate_app_instances()
        time.sleep(0.5)

        # 2. Determine target install directory
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        install_dir = os.path.join(program_files, APP_NAME)
        try:
            os.makedirs(install_dir, exist_ok=True)
        except Exception:
            # Fallback to LocalAppData if admin permissions not granted
            local_appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
            install_dir = os.path.join(local_appdata, "Programs", APP_NAME)
            os.makedirs(install_dir, exist_ok=True)

        # 3. Locate and extract payload zip
        bundle_dir = get_bundle_dir()
        zip_path = os.path.join(bundle_dir, "app_payload.zip")
        if not os.path.exists(zip_path):
            zip_path = os.path.join(os.path.dirname(sys.executable), "app_payload.zip")

        if not os.path.exists(zip_path):
            return False

        clean_old_internal(install_dir)

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(install_dir)

        target_exe = os.path.join(install_dir, f"{APP_NAME}.exe")
        target_ico = os.path.join(install_dir, "icon.ico")
        if not os.path.exists(target_ico):
            target_ico = target_exe

        # 4. Enable Windows autostart via Startup shortcut immediately from first installation
        set_windows_startup(target_exe, True, icon_path=target_ico, work_dir=install_dir)

        # 5. Create Desktop shortcut
        desktop_dir = os.path.join(os.environ.get("USERPROFILE", ""), "Desktop")
        if not os.path.exists(desktop_dir):
            desktop_dir = os.path.join(os.environ.get("HOMEDRIVE", "C:"), os.environ.get("HOMEPATH", ""), "Desktop")
        create_windows_shortcut(target_exe, os.path.join(desktop_dir, f"{DISPLAY_NAME}.lnk"), target_ico, install_dir)

        # 6. Create Start Menu shortcut
        appdata = os.environ.get("APPDATA", "")
        start_menu_dir = os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", DISPLAY_NAME)
        os.makedirs(start_menu_dir, exist_ok=True)
        create_windows_shortcut(target_exe, os.path.join(start_menu_dir, f"{DISPLAY_NAME}.lnk"), target_ico, install_dir)

        # 7. Create uninstaller batch
        uninst_bat = os.path.join(install_dir, "Uninstall.bat")
        with open(uninst_bat, "w", encoding="utf-8") as f:
            f.write(
                f'@echo off\n'
                f'chcp 65001 > nul\n'
                f'taskkill /f /im "{APP_NAME}.exe" > nul 2>&1\n'
                f'echo جاري إزالة الاختصارات...\n'
                f'del "%USERPROFILE%\\Desktop\\{DISPLAY_NAME}.lnk" > nul 2>&1\n'
                f'del "%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Startup\\{DISPLAY_NAME}.lnk" > nul 2>&1\n'
                f'rmdir /s /q "%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\{DISPLAY_NAME}" > nul 2>&1\n'
                f'echo تم حذف الاختصارات بنجاح.\n'
                f'echo يمكنك الآن حذف المجلد: "{install_dir}"\n'
                f'pause\n'
            )

        # 8. Launch installed app cleanly in background tray
        if os.path.exists(target_exe):
            subprocess.Popen([target_exe, "--startup"], cwd=install_dir)

        return True
    except Exception as e:
        print("Silent install error:", e)
        return False

class InstallerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"تثبيت {DISPLAY_NAME}")
        self.root.geometry("540x545")
        self.root.resizable(False, False)
        self.root.configure(bg="#181825")

        # Set application icon (eliminates Tkinter feather icon)
        ico_path = get_res("icon.ico")
        png_path = get_res("icon.png")
        if os.path.exists(ico_path):
            try:
                self.root.iconbitmap(default=ico_path)
            except Exception:
                pass
        if os.path.exists(png_path):
            try:
                self._icon_img = tk.PhotoImage(file=png_path)
                self.root.iconphoto(True, self._icon_img)
            except Exception:
                pass

        # Center on screen
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w, h = 540, 545
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

        # Default install dir: C:\Program Files\SmartScreenTranslator
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        self.default_install_dir = os.path.join(program_files, APP_NAME)

        self.setup_ui()

    def setup_ui(self):
        # Header banner
        header = tk.Frame(self.root, bg="#1e1e2e", height=80)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)

        hdr_inner = tk.Frame(header, bg="#1e1e2e")
        hdr_inner.pack(fill=tk.BOTH, expand=True, padx=20)

        # Show mini logo thumbnail in header if available
        png_path = get_res("icon.png")
        if os.path.exists(png_path):
            try:
                from PIL import Image, ImageTk
                im = Image.open(png_path).resize((46, 46), Image.Resampling.LANCZOS)
                self._hdr_logo = ImageTk.PhotoImage(im)
                tk.Label(hdr_inner, image=self._hdr_logo, bg="#1e1e2e").pack(side=tk.LEFT, pady=16)
            except Exception:
                pass

        title_box = tk.Frame(hdr_inner, bg="#1e1e2e")
        title_box.pack(side=tk.RIGHT, pady=14)

        tk.Label(
            title_box,
            text=f"🚀 برنامج تثبيت {DISPLAY_NAME}",
            font=("Segoe UI", 13, "bold"),
            fg="#89b4fa",
            bg="#1e1e2e"
        ).pack(anchor=tk.E)

        tk.Label(
            title_box,
            text=f"الإصدار الاحترافي v2.0 • برمجة وتطوير: {DEV_NAME} • هاتف: {DEV_PHONE}",
            font=("Segoe UI", 8),
            fg="#a6adc8",
            bg="#1e1e2e"
        ).pack(anchor=tk.E)

        # Body
        body = tk.Frame(self.root, bg="#181825", padx=20, pady=14)
        body.pack(fill=tk.BOTH, expand=True)

        # Install Path Card with Rounded Corners
        path_box = ModernCard(
            body,
            title="📂 مسار التثبيت على الجهاز",
            theme_name="dark",
            radius=14
        )
        path_box.pack(fill=tk.X, pady=(0, 12))

        path_row = tk.Frame(path_box.body, bg=path_box.card_bg)
        path_row.pack(fill=tk.X, pady=4)

        browse_btn = ModernButton(
            path_row,
            text="استعراض...",
            icon_name="folder",
            width=115,
            height=36,
            radius=12,
            bg="#282d3f",
            fg="#89b4fa",
            hover_bg="#363d55",
            pressed_bg="#1f2331",
            border_color="#333a52",
            parent_bg=path_box.card_bg,
            command=self.browse_path
        )
        browse_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.path_entry = ModernEntry(
            path_row,
            height=36,
            radius=12,
            bg="#181b26",
            fg="#f1f5f9",
            border_color="#333a52",
            focus_border="#3b82f6",
            parent_bg=path_box.card_bg,
            font=("Segoe UI", 9, "bold")
        )
        self.path_entry.insert(0, self.default_install_dir)
        self.path_entry.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        self.path_entry.xview_moveto(0)

        # Options Box with Rounded Corners
        opts_box = ModernCard(
            body,
            title="⚙️ خيارات التثبيت والاختصارات",
            theme_name="dark",
            radius=14
        )
        opts_box.pack(fill=tk.X, pady=(0, 12))

        self.desktop_var = tk.BooleanVar(value=True)
        chk_desk = ModernCheckbox(
            opts_box.body,
            text="إنشاء أيقونة اختصار على سطح المكتب (Desktop Shortcut)",
            variable=self.desktop_var,
            bg=opts_box.card_bg,
            fg="#cdd6f4",
            active_top="#89b4fa",
            active_bot="#3b82f6",
            border_color="#45475a",
            radius=6
        )
        chk_desk.pack(anchor=tk.E, pady=3)

        self.startmenu_var = tk.BooleanVar(value=True)
        chk_menu = ModernCheckbox(
            opts_box.body,
            text="إضافة البرنامج إلى قائمة ابدأ (Start Menu)",
            variable=self.startmenu_var,
            bg=opts_box.card_bg,
            fg="#cdd6f4",
            active_top="#89b4fa",
            active_bot="#3b82f6",
            border_color="#45475a",
            radius=6
        )
        chk_menu.pack(anchor=tk.E, pady=3)

        self.launch_var = tk.BooleanVar(value=True)
        chk_launch = ModernCheckbox(
            opts_box.body,
            text="تشغيل المترجم فور الانتهاء من التثبيت مباشرة",
            variable=self.launch_var,
            bg=opts_box.card_bg,
            fg="#cdd6f4",
            active_top="#89b4fa",
            active_bot="#3b82f6",
            border_color="#45475a",
            radius=6
        )
        chk_launch.pack(anchor=tk.E, pady=3)

        self.startup_var = tk.BooleanVar(value=True)
        chk_startup = ModernCheckbox(
            opts_box.body,
            text="التشغيل التلقائي في الخلفية مع بدء تشغيل Windows (خفيف بالخلفية)",
            variable=self.startup_var,
            bg=opts_box.card_bg,
            fg="#cdd6f4",
            active_top="#89b4fa",
            active_bot="#3b82f6",
            border_color="#45475a",
            radius=6
        )
        chk_startup.pack(anchor=tk.E, pady=3)

        # Progress bar
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Installer.Horizontal.TProgressbar", troughcolor="#1e1e2e", background="#89b4fa", bordercolor="#313244")

        self.pbar = ttk.Progressbar(body, style="Installer.Horizontal.TProgressbar", orient=tk.HORIZONTAL, mode="determinate")
        self.pbar.pack(fill=tk.X, pady=(8, 4))

        self.status_lbl = tk.Label(
            body,
            text="جاهز للتثبيت السريع الصامت. اضغط على زر 'بدء التثبيت الآن'.",
            font=("Segoe UI", 9),
            fg="#a6adc8",
            bg="#181825"
        )
        self.status_lbl.pack(anchor=tk.E)

        # Footer
        footer = tk.Frame(self.root, bg="#1e1e2e", height=58, padx=20)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        footer.pack_propagate(False)

        self.install_btn = ModernButton(
            footer,
            text="بدء التثبيت الفوري",
            icon_name="rocket",
            width=180,
            height=38,
            radius=16,
            bg="#89b4fa",
            gradient_bottom="#3b82f6",
            fg="#11111b",
            hover_bg="#b4befe",
            pressed_bg="#2563eb",
            command=self.start_install
        )
        self.install_btn.pack(side=tk.RIGHT, pady=10)

        self.cancel_btn = ModernButton(
            footer,
            text="إلغاء",
            width=90,
            height=38,
            radius=16,
            bg="#313244",
            fg="#cdd6f4",
            hover_bg="#45475a",
            pressed_bg="#252739",
            border_color="#45475a",
            command=self.root.destroy
        )
        self.cancel_btn.pack(side=tk.LEFT, pady=10)

    def browse_path(self):
        current = self.path_entry.get().strip()
        initial_dir = current if os.path.exists(current) else r"C:\Program Files"
        if not os.path.exists(initial_dir):
            initial_dir = "C:\\"
        folder = filedialog.askdirectory(title="اختر مجلد التثبيت", initialdir=initial_dir)
        if folder:
            folder = os.path.normpath(folder)
            if not folder.endswith(APP_NAME):
                folder = os.path.join(folder, APP_NAME)
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, folder)
            self.path_entry.xview_moveto(0)

    def start_install(self):
        install_dir = self.path_entry.get().strip()
        if not install_dir:
            messagebox.showwarning("تنبيه", "يرجى تحديد مسار صالح للتثبيت.")
            return

        self.install_btn.config(state="disabled", text="⏳ جاري التثبيت الصامت...")
        self.cancel_btn.config(state="disabled")
        self.path_entry.config(state="disabled")

        threading.Thread(target=self.do_install, args=(install_dir,), daemon=True).start()

    def do_install(self, install_dir):
        try:
            # 1. Silently terminate any running instances (Zero black console window)
            self.root.after(0, lambda: self.update_progress(5, "جاري إغلاق أي جلسات سابقة للمترجم..."))
            terminate_app_instances()
            time.sleep(0.8)

            # 2. Locate payload zip
            bundle_dir = get_bundle_dir()
            zip_path = os.path.join(bundle_dir, "app_payload.zip")
            if not os.path.exists(zip_path):
                zip_path = os.path.join(os.path.dirname(sys.executable), "app_payload.zip")

            if not os.path.exists(zip_path):
                raise FileNotFoundError(f"لم يتم العثور على ملف الحزمة app_payload.zip في: {zip_path}")

            os.makedirs(install_dir, exist_ok=True)
            clean_old_internal(install_dir)

            # 3. Extract zip with retry logic if any file was locked
            with zipfile.ZipFile(zip_path, "r") as zf:
                total_files = len(zf.namelist())
                for idx, item in enumerate(zf.namelist(), 1):
                    extracted = False
                    for attempt in range(3):
                        try:
                            zf.extract(item, install_dir)
                            extracted = True
                            break
                        except PermissionError:
                            terminate_app_instances()
                            time.sleep(0.8)
                    if not extracted:
                        zf.extract(item, install_dir)

                    progress = int(5 + (idx / total_files) * 85)
                    if idx % 15 == 0 or idx == total_files:
                        self.root.after(0, lambda p=progress, f=item: self.update_progress(p, f"جاري استخراج: {os.path.basename(f)}"))

            self.root.after(0, lambda: self.update_progress(92, "جاري إنشاء الاختصارات وتفعيل التشغيل التلقائي..."))

            target_exe = os.path.join(install_dir, f"{APP_NAME}.exe")
            target_ico = os.path.join(install_dir, "icon.ico")
            if not os.path.exists(target_ico):
                target_ico = target_exe

            # Enable Windows autostart via Startup shortcut immediately from first installation
            set_windows_startup(target_exe, self.startup_var.get(), icon_path=target_ico, work_dir=install_dir)

            # 4. Create Desktop shortcut
            if self.desktop_var.get():
                desktop_dir = os.path.join(os.environ.get("USERPROFILE", ""), "Desktop")
                if not os.path.exists(desktop_dir):
                    desktop_dir = os.path.join(os.environ.get("HOMEDRIVE", "C:"), os.environ.get("HOMEPATH", ""), "Desktop")
                lnk_path = os.path.join(desktop_dir, f"{DISPLAY_NAME}.lnk")
                create_windows_shortcut(target_exe, lnk_path, target_ico, install_dir)

            # 5. Create Start Menu shortcut
            if self.startmenu_var.get():
                appdata = os.environ.get("APPDATA", "")
                start_menu_dir = os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", DISPLAY_NAME)
                os.makedirs(start_menu_dir, exist_ok=True)
                lnk_path = os.path.join(start_menu_dir, f"{DISPLAY_NAME}.lnk")
                create_windows_shortcut(target_exe, lnk_path, target_ico, install_dir)

            # 6. Create uninstaller batch
            uninst_bat = os.path.join(install_dir, "Uninstall.bat")
            with open(uninst_bat, "w", encoding="utf-8") as f:
                f.write(
                    f'@echo off\n'
                    f'chcp 65001 > nul\n'
                    f'taskkill /f /im "{APP_NAME}.exe" > nul 2>&1\n'
                    f'echo جاري إزالة الاختصارات...\n'
                    f'del "%USERPROFILE%\\Desktop\\{DISPLAY_NAME}.lnk" > nul 2>&1\n'
                    f'del "%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Startup\\{DISPLAY_NAME}.lnk" > nul 2>&1\n'
                    f'rmdir /s /q "%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\{DISPLAY_NAME}" > nul 2>&1\n'
                    f'echo تم حذف الاختصارات بنجاح.\n'
                    f'echo يمكنك الآن حذف المجلد: "{install_dir}"\n'
                    f'pause\n'
                )

            self.root.after(0, lambda: self.on_install_completed(target_exe))

        except Exception as e:
            self.root.after(0, lambda err=str(e): self.on_install_failed(err))

    def update_progress(self, percent, msg):
        self.pbar["value"] = percent
        self.status_lbl.config(text=msg, fg="#cdd6f4")

    def on_install_completed(self, target_exe):
        self.pbar["value"] = 100
        self.status_lbl.config(text="✓ تم التثبيت بنجاح تام!", fg="#a6e3a1")
        self.install_btn.config(
            text="إنهاء وإغلاق",
            icon_name="check",
            state="normal",
            bg="#a6e3a1",
            fg="#11111b",
            command=self.finish_installer
        )

        if self.launch_var.get() and os.path.exists(target_exe):
            try:
                os.startfile(target_exe)
            except Exception:
                run_hidden_popen([target_exe], cwd=os.path.dirname(target_exe))

        messagebox.showinfo(
            "اكتمل التثبيت بنجاح",
            f"تم تثبيت '{DISPLAY_NAME}' بنجاح على جهازك!\n\n"
            f"• مسار التثبيت: {self.path_entry.get().strip()}\n"
            f"• تم إنشاء اختصار سطح المكتب بالأيقونة الجديدة.\n"
            f"• سيتم الآن تشغيل المترجم وعرض شاشة البداية.\n"
            f"• الاختصار الافتراضي للترجمة: Ctrl + T\n\n"
            f"برمجة وتطوير: {DEV_NAME} • هاتف: {DEV_PHONE}"
        )
        self.root.destroy()

    def on_install_failed(self, error_msg):
        self.status_lbl.config(text=f"❌ فشل التثبيت: {error_msg}", fg="#f38ba8")
        self.install_btn.config(state="normal", text="إعادة المحاولة", icon_name="reset", bg="#f38ba8", fg="#11111b")
        self.cancel_btn.config(state="normal")
        self.path_entry.config(state="normal")
        messagebox.showerror("خطأ أثناء التثبيت", f"حدث خطأ أثناء تثبيت البرنامج:\n{error_msg}")

    def finish_installer(self):
        self.root.destroy()

if __name__ == "__main__":
    # Check for silent installation arguments: /silent, /S, -s, --silent, /quiet
    args_lower = [a.lower().strip("-/") for a in sys.argv[1:]]
    silent_flags = {"silent", "s", "quiet", "q", "verysilent"}
    if any(flag in args_lower for flag in silent_flags):
        success = perform_silent_install()
        sys.exit(0 if success else 1)

    # Standard interactive / GUI mode
    root = tk.Tk()
    app = InstallerGUI(root)
    root.mainloop()
