import os
import sys
import json

def get_base_dir():
    """Returns base directory of application or PyInstaller bundle."""
    if hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def get_user_data_dir():
    """Returns a guaranteed writable user AppData directory."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        appdata = os.path.expanduser("~")
    data_dir = os.path.join(appdata, "SmartScreenTranslator")
    try:
        os.makedirs(data_dir, exist_ok=True)
    except Exception:
        pass
    return data_dir

USER_CONFIG_FILE = os.path.join(get_user_data_dir(), "config.json")

DEFAULT_CONFIG = {
    "hotkey": "ctrl+t",
    "target_language": "ar",
    "source_language": "auto",
    "auto_copy_translation": True,
    "show_overlay_image": True,
    "play_sound": True,
    "show_launcher_on_startup": False,
    "auto_start": True,
    "translation_mode": "auto",  # auto (Lens with Offline Fallback), offline (Offline Only), online (Lens Only)
    "theme": "dark",
    "overlay_theme": "light"
}

def load_config():
    """Loads configuration from user AppData, falling back to bundled template."""
    config = DEFAULT_CONFIG.copy()

    # 1. Try user AppData config first
    if os.path.exists(USER_CONFIG_FILE):
        try:
            with open(USER_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                config.update(data)
                return config
        except Exception:
            pass

    # 2. Try template config from base_dir or _internal
    template_candidates = [
        os.path.join(get_base_dir(), "config.json"),
        os.path.join(get_base_dir(), "_internal", "config.json")
    ]
    for cand in template_candidates:
        if os.path.exists(cand):
            try:
                with open(cand, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    config.update(data)
                    # Persist to user AppData for future runs
                    save_config(config)
                    return config
            except Exception:
                pass

    return config

def save_config(config):
    """Saves configuration safely to user AppData."""
    try:
        os.makedirs(get_user_data_dir(), exist_ok=True)
        with open(USER_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print("Error saving config to user data directory:", e)
        return False
