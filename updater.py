import os
import sys
import json
import base64
import urllib.request
import urllib.error
import subprocess
import tempfile
import zipfile
import threading

CURRENT_VERSION = "2.0.0"
CURRENT_VERSION_CODE = 200

GITHUB_OWNER = "riadsaleem"
GITHUB_REPO = "Smart-Screen-Translator-PC"
DEFAULT_GITHUB_TOKEN = ""

def get_app_dir():
    """Returns the base application directory."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def get_executable_path():
    """Returns the path to the running executable or main entry script."""
    if getattr(sys, "frozen", False):
        return sys.executable
    return os.path.join(get_app_dir(), "main.py")

def get_token(config=None):
    """Retrieves optional GitHub token from config or environment."""
    if config and config.get("github_token"):
        return config.get("github_token")
    env_token = os.environ.get("GITHUB_TOKEN")
    if env_token:
        return env_token
    return DEFAULT_GITHUB_TOKEN

def _urlopen_with_public_fallback(url, accept_header, token=None, timeout=15):
    """Opens URL with optional GitHub token, retrying anonymously if a stale token triggers HTTP 401."""
    def _build_req(use_token):
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "SmartScreenTranslator-PC")
        req.add_header("Accept", accept_header)
        if use_token and token and "github.com" in url:
            req.add_header("Authorization", f"token {token}")
        return req

    try:
        return urllib.request.urlopen(_build_req(bool(token)), timeout=timeout)
    except urllib.error.HTTPError as e:
        if e.code == 401 and token:
            return urllib.request.urlopen(_build_req(False), timeout=timeout)
        raise

def parse_version(ver_str):
    """Converts version string like '2.0.1' into tuple of integers (2, 0, 1)."""
    try:
        clean = ver_str.strip().lstrip("vV")
        parts = [int(p) for p in clean.split(".") if p.isdigit()]
        return tuple(parts)
    except Exception:
        return (0, 0, 0)

def is_newer_version(remote_ver, local_ver=CURRENT_VERSION):
    """Checks if remote version is strictly greater than local version."""
    return parse_version(remote_ver) > parse_version(local_ver)

def check_for_updates(token=None, config=None):
    """
    Checks GitHub repository for updates by fetching version.json.
    Returns a dict with update status and details.
    """
    if not token:
        token = get_token(config)

    api_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/version.json"

    try:
        with _urlopen_with_public_fallback(api_url, "application/vnd.github.raw", token=token, timeout=10) as response:
            raw_data = response.read().decode("utf-8")
            data = json.loads(raw_data)

            remote_ver = data.get("version", CURRENT_VERSION)
            update_avail = is_newer_version(remote_ver, CURRENT_VERSION)
            
            # Determine update type: 'patch' (delta) or 'major' (full installer)
            update_type = data.get("update_type", "patch").lower()
            min_full_req = data.get("min_full_version_required", "2.0.0")
            if parse_version(CURRENT_VERSION) < parse_version(min_full_req):
                update_type = "major"

            download_info = data.get("download", {})

            return {
                "success": True,
                "update_available": update_avail,
                "current_version": CURRENT_VERSION,
                "latest_version": remote_ver,
                "update_type": update_type,
                "title": data.get("title", f"الإصدار {remote_ver}"),
                "release_date": data.get("release_date", ""),
                "changelog": data.get("changelog", []),
                "patch_url": download_info.get("patch_url", ""),
                "patch_size_mb": download_info.get("patch_size_mb", 1.0),
                "full_installer_url": download_info.get("full_installer_url", ""),
                "full_installer_size_mb": download_info.get("full_installer_size_mb", 180.0),
                "raw_data": data,
                "error": None
            }

    except urllib.error.HTTPError as e:
        if e.code == 404:
            # File or repo not found
            return {
                "success": False,
                "update_available": False,
                "error": f"لم يتم العثور على ملف الإصدارات version.json في المستودع (404)."
            }
        elif e.code == 401 or e.code == 403:
            return {
                "success": False,
                "update_available": False,
                "error": f"خطأ في صلاحيات المصادقة على GitHub ({e.code}). تحقق من رمز التوكن."
            }
        else:
            return {
                "success": False,
                "update_available": False,
                "error": f"خطأ خادم GitHub HTTP {e.code}: {e.reason}"
            }
    except Exception as e:
        return {
            "success": False,
            "update_available": False,
            "error": f"فشل الاتصال بالإنترنت أو الخادم: {str(e)}"
        }

def download_file(url, dest_path, token=None, progress_callback=None, cancel_event=None):
    """
    Downloads a file with streaming progress callback:
    progress_callback(percent_int, downloaded_mb, total_mb, status_str)
    """
    with _urlopen_with_public_fallback(url, "application/octet-stream", token=token, timeout=30) as response:
        total_size = int(response.headers.get("content-length", 0))
        total_mb = round(total_size / (1024 * 1024), 2) if total_size > 0 else 0
        downloaded = 0
        chunk_size = 64 * 1024

        with open(dest_path, "wb") as f:
            while True:
                if cancel_event and cancel_event.is_set():
                    return False
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                downloaded_mb = round(downloaded / (1024 * 1024), 2)
                percent = int((downloaded / total_size) * 100) if total_size > 0 else 50
                if progress_callback:
                    progress_callback(percent, downloaded_mb, total_mb, f"{downloaded_mb}MB / {total_mb}MB ({percent}%)")

    return True

def apply_delta_patch(zip_path):
    """
    Applies a delta patch zip file to the application directory.
    If the application is running, creates a detached update runner script.
    """
    app_dir = get_app_dir()
    exe_path = get_executable_path()
    is_frozen = getattr(sys, "frozen", False)

    # 1. If not frozen (development or python script mode), extract directly
    if not is_frozen:
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(app_dir)
            return True, "تم تطبيق التحديث الفرعي بنجاح على ملفات المشروع!"
        except Exception as e:
            return False, f"فشل فك ضغط التحديث: {e}"

    # 2. If frozen (.exe mode), we create a lightweight batch updater to replace in-use files
    temp_dir = tempfile.gettempdir()
    batch_file = os.path.join(temp_dir, "sst_apply_patch.bat")
    
    # PowerShell command to extract safely
    ps_extract = (
        f'Expand-Archive -LiteralPath "{zip_path}" -DestinationPath "{app_dir}" -Force'
    )
    
    script_content = f"""@echo off
chcp 65001 > nul
echo جاري انتظار إغلاق البرنامج لتطبيق التحديث...
timeout /t 2 /nobreak > nul
taskkill /f /im SmartScreenTranslator.exe > nul 2>&1

echo جاري استخراج وتطبيق التحديثات الفرعية...
powershell -NoProfile -Command "{ps_extract}"

echo جاري إعادة تشغيل مترجم الشاشة الذكي...
start "" "{exe_path}"

del "{zip_path}" > nul 2>&1
(goto) 2>nul & del "%~f0"
"""

    with open(batch_file, "w", encoding="utf-8") as f:
        f.write(script_content)

    # Launch batch detached and exit app
    subprocess.Popen(["cmd.exe", "/c", batch_file], creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    return True, "جاري إعادة تشغيل البرنامج لتطبيق التحديث..."

def launch_full_installer(installer_path):
    """Launches full installer and prepares to terminate current app."""
    try:
        subprocess.Popen([installer_path], cwd=os.path.dirname(installer_path))
        return True, "تم تشغيل برنامج التثبيت الشامل بنجاح."
    except Exception as e:
        return False, f"فشل تشغيل برنامج التثبيت: {e}"
