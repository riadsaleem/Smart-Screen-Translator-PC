import os
import sys
import re
import html
import time
import types
import tempfile
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont

# Lazy loading flags and instances (STRICT lazy loading to prevent heavy startup bloat)
_ARGOS_INITIALIZED = False
_RAPID_OCR_INSTANCE = None


def get_base_dir():
    if hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _ensure_argos():
    """
    Lazily loads Argos Translate with MINISBD chunking and lightweight stanza/spacy stubs
    so torch, stanza, and spacy are never required at runtime.
    """
    global _ARGOS_INITIALIZED
    if not _ARGOS_INITIALIZED:
        # Inject lightweight stubs so argostranslate.sbd does not pull in torch/stanza/spacy
        if "stanza" not in sys.modules:
            sys.modules["stanza"] = types.ModuleType("stanza")
        if "spacy" not in sys.modules:
            sys.modules["spacy"] = None

        import argostranslate.settings
        from pathlib import Path

        # Add bundled offline language models (English/Arabic) if present
        candidates = [
            os.path.join(get_base_dir(), "packages"),
            os.path.join(get_base_dir(), "_internal", "packages"),
            os.path.join(os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else "", "packages"),
        ]
        for c in candidates:
            if c and os.path.exists(c):
                p = Path(c)
                if p not in argostranslate.settings.package_dirs:
                    argostranslate.settings.package_dirs.insert(0, p)

        # MINISBD must be set BEFORE importing argostranslate.translate
        argostranslate.settings.chunk_type = argostranslate.settings.ChunkType.MINISBD
        import argostranslate.translate
        import argostranslate.package

        # Point minisbd cache_dir to bundled models if available
        try:
            from minisbd import models as minisbd_models
            for c in candidates:
                msbd = os.path.join(c, "minisbd")
                if c and os.path.exists(msbd):
                    minisbd_models.cache_dir = msbd
                    break
        except Exception:
            pass

        _ARGOS_INITIALIZED = True


def get_ocr_engine():
    """Lazily loads RapidOCR ONNX model tuned for dense desktop screenshots."""
    global _RAPID_OCR_INSTANCE
    if _RAPID_OCR_INSTANCE is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            _RAPID_OCR_INSTANCE = RapidOCR(
                use_angle_cls=False,
                text_score=0.25,
                min_height=6,
                width_height_ratio=-1,
                det_model_path=None,
                det_thresh=0.20,
                det_box_thresh=0.24,
                det_unclip_ratio=1.55,
                det_limit_side_len=1280,
                det_limit_type="min",
                det_use_dilation=False,
                det_score_mode="fast",
                rec_model_path=None,
                rec_batch_num=16,
            )
        except Exception as e:
            print("Failed to initialize RapidOCR:", e)
    return _RAPID_OCR_INSTANCE


LANGUAGE_NAMES = {
    "ar": "العربية",
    "en": "English",
    "fr": "Français",
    "es": "Español",
    "de": "Deutsch",
    "tr": "Türkçe",
    "ru": "Русский",
    "zh": "中文",
    "ja": "日本語",
    "it": "Italiano",
    "pt": "Português",
}

# ---------------- Technical Term & UI Label Preservation ----------------
UI_MENU_WORDS = {
    "file": "ملف",
    "edit": "تعديل",
    "view": "عرض",
    "navigate": "تنقل",
    "code": "كود",
    "refactor": "إعادة هيكلة",
    "build": "بناء",
    "run": "تشغيل",
    "tools": "أدوات",
    "vcs": "التحكم بالإصدارات",
    "window": "نافذة",
    "help": "مساعدة",
    "settings": "الإعدادات",
    "preferences": "التفضيلات",
    "options": "الخيارات",
    "plugins": "الإضافات",
    "plugin": "الإضافة",
    "extensions": "الملحقات",
    "extension": "الملحق",
    "terminal": "الطرفية",
    "project": "المشروع",
    "install": "تثبيت",
    "open": "افتح",
    "close": "إغلاق",
    "new": "جديد",
    "save": "حفظ",
    "delete": "حذف",
    "remove": "إزالة",
    "copy": "نسخ",
    "paste": "لصق",
    "cut": "قص",
    "export": "تصدير",
    "import": "استيراد",
    "appearance": "المظهر",
    "editor": "المحرر",
    "keymap": "اختصارات المفاتيح",
    "version control": "التحكم بالإصدارات",
    "marketplace": "سوق الإضافات",
    "installed": "المثبتة",
    "updates": "التحديثات",
    "search": "بحث",
    "ok": "موافق",
    "cancel": "إلغاء",
    "apply": "تطبيق",
    "next": "التالي",
    "back": "السابق",
    "finish": "إنهاء",
    "menu": "القائمة",
    "home": "الرئيسية",
    "dashboard": "لوحة التحكم",
    "profile": "الملف الشخصي",
    "notifications": "الإشعارات",
    "language": "اللغة",
    "theme": "المظهر",
    "download": "تنزيل",
    "upload": "رفع",
    "login": "تسجيل الدخول",
    "sign in": "تسجيل الدخول",
    "sign out": "تسجيل الخروج",
    "logout": "تسجيل الخروج",
    "about": "حول",
    "note": "ملاحظة",
    "warning": "تحذير",
    "error": "خطأ",
    "success": "نجاح",
    "tip": "تلميح",
    "loading": "جاري التحميل",
    "loading...": "جاري التحميل...",
    "general": "عام",
    "advanced": "متقدم",
    "security": "الأمان",
    "privacy": "الخصوصية",
    "account": "الحساب",
    "submit": "إرسال",
    "confirm": "تأكيد",
    "reset": "إعادة تعيين",
    "refresh": "تحديث",
    "retry": "إعادة المحاولة",
    "version": "الإصدار",
    "stable": "مستقر",
    "enable": "تفعيل",
    "disable": "تعطيل",
    "enabled": "مفعّل",
    "disabled": "معطّل",
    "history": "السجل",
    "bookmarks": "الإشارات المرجعية",
    "downloads": "التنزيلات",
    "extensions & plugins": "الملحقات والإضافات",
    "privacy & security": "الخصوصية والأمان",
    "privacy&security": "الخصوصية والأمان",
    "privacy and security": "الخصوصية والأمان",
    "checkfor updates": "التحقق من التحديثات",
    "terms of service": "شروط الخدمة",
    "sign up": "إنشاء حساب",
    "continue": "متابعة",
    "skip": "تخطي",
    "done": "تم",
    "exit": "خروج",
    "quit": "إنهاء",
    "help & support": "المساعدة والدعم",
}

TECH_TERMS = {
    "android studio": "أندرويد ستوديو",
    "flutter": "فلاتر",
    "dart": "دارت",
    "macos": "macOS",
    "mac os": "macOS",
    "windows": "ويندوز",
    "linux": "لينكس",
    "sdk": "SDK",
    "api": "API",
    "terminal": "الطرفية",
    "command prompt": "موجه الأوامر",
    "powershell": "باور شيل",
    "git": "Git",
    "github": "GitHub",
    "gitlab": "GitLab",
    "vs code": "Visual Studio Code",
    "visual studio code": "Visual Studio Code",
    "xcode": "Xcode",
    "flutter bin": "مجلد flutter/bin",
    "flutter doctor": "flutter doctor",
    "flutter channel stable": "Flutter Channel Stable",
    "channel stable": "القناة المستقرة (Stable)",
    "connected device": "الجهاز المتصل",
    "connected devices": "الأجهزة المتصلة",
    "no devices available": "لا توجد أجهزة متوفرة",
    "doctor found issues in 1 category": "وجد الفحص مشاكل في فئة واحدة",
    "doctor summary": "ملخص الفحص (Doctor summary)",
    "android toolchain": "أدوات Android Toolchain",
    "general settings": "الإعدادات العامة",
    "navigation menu": "قائمة التنقل",
    "offline mode": "وضع عدم الاتصال",
    "online mode": "وضع الاتصال بالإنترنت",
    "save changes": "حفظ التغييرات",
    "check for updates": "التحقق من التحديثات",
    "dark mode": "الوضع الداكن",
    "light mode": "الوضع الفاتح",
    "control center": "مركز التحكم",
    "application control center": "مركز التحكم بالتطبيقات",
    "google lens": "عدسة Google",
    "fullscreen": "ملء الشاشة",
    "full screen": "ملء الشاشة",
    "left column": "العمود الأيسر",
    "right column": "العمود الأيمن",
    "left column title": "عنوان العمود الأيسر",
    "right column title": "عنوان العمود الأيمن",
    "press escape": "اضغط Esc",
    "press esc": "اضغط Esc",
    "press enter": "اضغط Enter",
}

POST_FIXES = [
    # Argos transliteration & literal mistranslation fixes
    (r'\bكليك فيل\b', 'انقر فوق ملف'),
    (r'\bكليك\b', 'انقر'),
    (r'\bستينغز\b|\bستينجز\b', 'الإعدادات'),
    (r'\bبلجنز\b|\bبلوجنز\b|\bالبلوجينز\b|\bالبوجينات\b|\bبلوجينات\b', 'الإضافات'),
    (r'\bالتمديدات\b', 'الملحقات'),
    (r'\bإنستل\b|\bانستل\b|\bأنستل\b', 'تثبيت'),
    (r'\bاستوديو الكويكبات\b|\bالكويكبات\b', 'أندرويد ستوديو'),
    (r'\bاستوديو أندرويد\b', 'أندرويد ستوديو'),
    (r'\bالأندور\b|\bأندور\b', 'أندرويد'),
    (r'\bماكاو\b|\bماكوس\b', 'macOS'),
    (r'\bفي macOS\b', 'على نظام macOS'),
    (r'\bفي ويندوز\b', 'على نظام ويندوز'),
    (r'\bلتركيب\b', 'لتثبيت'),
    (r'\bإختاروا\b|\bإختار\b', 'اختر'),
    (r'\bأضغطوا\b|\bاضغطوا\b', 'اضغط'),
    (r'\bسيت أب\b|\bسيت اب\b', 'إعداد'),
    (r'\bداونلود\b', 'تنزيل'),
    (r'\bونقر\b', 'وانقر'),
    (r'\bإنقاذ التغييرات\b', 'حفظ التغييرات'),
    (r'\bالنموذج الخارجي\b', 'وضع عدم الاتصال'),
    (r'\bهروب الصحافة\b|\bالصحافة الهروب\b|\bهروب صحافي\b|\bصحافي هروب\b', 'اضغط Esc'),
    (r'\bالصحافة\s+((?:Ctrl|Alt|Shift|Win|Cmd|Esc|Escape|Enter|Tab|Space)[^\s]*)', r'اضغط \1'),
    (r'\bغوغل لينز\b|\bجوجل لينز\b', 'عدسة Google'),
    (r'\bهذا الطلب\b', 'هذا التطبيق'),
    (r'\bمحفوظات الزبدة\b|\bأرشيف الزبدة\b|\bملف الزبدة\b', 'الملف المضغوط (ZIP)'),
    (r'\bطبيبا متقلبا\b|\bطبيب متقلب\b|\bطبيب فلاتر\b', 'أداة flutter doctor'),
    (r'\bموجز الدكتور\b', 'ملخص فحص flutter doctor'),
    (r'\bدليل فلاتر بن\b|\bدليل التفاخر\b|\bفلاتر بن\b', 'مجلد flutter/bin'),
    (r'\bتطوير المطاط\b|\bتحقيق التنمية\b', 'تطوير فلاتر'),
    (r'\bسيرشدك هذا الفصل من خلال تركيب\b', 'سيرشدك هذا الفصل خلال تثبيت'),
    (r'\bوقول\s*C:\s*/\s*flutter\b', 'على سبيل المثال C:\\flutter'),
    # HTML entities leftover or corrupted by OCR
    (r'&quot&;?|&quot;', '"'),
    (r'&amp&;?|&amp;', '&'),
    (r'&#39&;?|&#39;', "'"),
    (r'&lt&;?|&lt;', '<'),
    (r'&gt&;?|&gt;', '>'),
    # Remove parens around single words added by Argos
    (r'\(\s*([\u0600-\u06FFA-Za-z0-9_]+)\s*\)', r'\1'),
    (r'^\s*[\(\)]\s*', ''),
    (r'\s*[\(\)]\s*$', ''),
]


def _has_rtl(text: str) -> bool:
    for ch in text:
        code = ord(ch)
        if 0x0590 <= code <= 0x08FF or 0xFB1D <= code <= 0xFDFF or 0xFE70 <= code <= 0xFEFF:
            return True
    return False


def _has_arabic(text: str) -> bool:
    return any('\u0600' <= c <= '\u06FF' for c in text)


def clean_html_entities(text: str) -> str:
    """Decodes HTML entities and corrupted OCR sequences."""
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r'&quot&;?', '"', text)
    text = re.sub(r'&amp&;?', '&', text)
    text = re.sub(r'&#39&;?', "'", text)
    text = re.sub(r'&lt&;?', '<', text)
    text = re.sub(r'&gt&;?', '>', text)
    return text.strip()


def is_code_or_command(text: str) -> bool:
    """
    Detects genuine shell commands, file paths, URLs, or code statements so
    they aren't mangled — while NEVER misclassifying normal English UI prose
    like 'Set up your preferred...' or 'Find more documentation...'.
    """
    trimmed = text.strip()
    if not trimmed:
        return False
    # 1. Explicit shell prompts and Windows/Unix paths
    if trimmed.startswith(("$ ", "PS ", "C:\\", "D:\\", "d:\\", "~/", "./")):
        return True
    if re.match(r'^[A-Za-z]:\\', trimmed):
        return True
    # 2. URLs and URIs
    if re.match(r'^(https?://|ftp://|git@|ssh://|file://)', trimmed, re.IGNORECASE):
        return True
    # 3. Environment variable assignment (e.g. PATH=$PATH:...)
    if re.match(r'^[A-Za-z_][A-Za-z0-9_]*\s*=\s*\S+$', trimmed) and " " not in trimmed.split("=")[0]:
        return True
    # 4. Standalone file names, browser tab filenames, and archives
    if re.match(r'^[\w\.\-]+\.(zip|tar|gz|bz2|xz|7z|rar|exe|dll|bat|sh|py|dart|pdf|png|jpg|json|yaml|yml|md|xml|html|css|js|ts|onnx)$', trimmed, re.IGNORECASE):
        return True
    if len(trimmed.split()) <= 4 and re.search(
        r'\.(zip|tar|gz|bz2|xz|7z|rar|exe|dll|bat|sh|py|dart|pdf|png|jpg|jpeg|gif|webp|svg|txt|json|yaml|yml|md|xml|html|css|js|ts|onnx)\b',
        trimmed,
        re.IGNORECASE,
    ):
        return True
    if re.match(r'^[\w\.\-]+\s+-(?:pdf|png|jpg|jpeg|exe|zip|txt|py|dart|json)$', trimmed, re.IGNORECASE):
        return True
    # 5. Unambiguous CLI tool invocations (require CLI flags/paths/subcommands, not English prose)
    cli_tools = (
        "git ", "flutter ", "dart ", "npm ", "npx ", "yarn ", "pnpm ", "pip ", "pip3 ",
        "python ", "python3 ", "docker ", "docker-compose ", "kubectl ",
        "curl ", "wget ", "sudo ", "chmod ", "chown ", "brew ", "apt-get ",
        "gradle ", "./gradlew ", "mvn ", "cargo ", "setx ", "ssh ", "tar ", "unzip "
    )
    low = trimmed.lower()
    if any(low.startswith(p) for p in cli_tools):
        # Make sure it's actually a command (no trailing period or >7 prose words, or contains flags/paths)
        if ("--" in trimmed or "/" in trimmed or "\\" in trimmed or len(trimmed.split()) <= 4) and not trimmed.endswith("."):
            return True
    if re.match(r'^(cd|ls|mkdir|rm)\s+([~/.\-]|[\w\-]+[/\\])', low):
        return True
    return False


_PROTECTED_ASCII_TOKENS = frozenset({
    "macos", "windows", "linux", "github", "gitlab", "git", "google", "android",
    "flutter", "dart", "xcode", "vscode", "ctrl", "alt", "shift", "win", "cmd",
    "esc", "enter", "tab", "space", "api", "sdk", "ocr", "url", "uri", "pdf",
    "usb", "html", "css", "json", "yaml", "xml", "png", "jpg", "webp", "exe",
    "zip", "ram", "cpu", "gpu", "wifi", "wi-fi", "rgb", "rgba", "px", "hd", "ui",
    "pc", "ai", "v2", "http", "https", "fps", "dpi",
})


def _translate_breadcrumb_span(path_str: str) -> str:
    parts = re.split(r'\s*(?:>|->|→)\s*', path_str.strip())
    translated_parts = [UI_MENU_WORDS.get(p.strip().lower(), p.strip()) for p in parts]
    return " > ".join(translated_parts)


def translate_menu_path(text: str):
    """Translates UI breadcrumbs such as 'Click File > Settings > Plugins' to clean Arabic."""
    m = re.match(
        r'^(?:(Click|Select|Open|Choose)\s+)?([A-Za-z0-9][A-Za-z0-9\s]{0,28}(?:\s*(?:>|->|→)\s*[A-Za-z0-9][A-Za-z0-9\s]{0,28})+)$',
        text.strip(),
        re.IGNORECASE
    )
    if m:
        action = m.group(1)
        path = m.group(2)
        joined = _translate_breadcrumb_span(path)
        if action:
            act_lower = action.lower()
            if act_lower == "click":
                return f"انقر فوق {joined}"
            elif act_lower in ("select", "choose"):
                return f"اختر {joined}"
            elif act_lower == "open":
                return f"افتح {joined}"
        return joined
    return None


def _normalize_title_case_for_argos(text: str) -> str:
    """
    Argos en->ar treats Title-Cased words as untranslatable proper nouns (e.g. 'Smart Screen'
    or 'Press Escape'). Converting non-acronym Title-Case words to lowercase lets Argos
    translate the true meaning while keeping genuine acronyms/brands intact.
    """
    words = text.split()
    if len(words) <= 1:
        return text
    cap_words = sum(1 for w in words if re.match(r'^[A-Z][a-z]{1,}$', w))
    if cap_words < 2 and not any(w.lower().rstrip(".,:;!?") in ("settings", "plugins", "escape", "column", "title") for w in words if w[:1].isupper()):
        return text

    out = []
    for idx, w in enumerate(words):
        bare = re.sub(r'^[^A-Za-z0-9]+|[^A-Za-z0-9]+$', '', w)
        low = bare.lower()
        # Keep genuine all-caps acronyms (API, SDK, USB, OCR) and mixed-case brands (macOS, GitHub)
        if bare.isupper() and len(bare) >= 2:
            out.append(w)
        elif low in ("macos", "github", "gitlab", "xcode", "google", "windows", "android", "flutter"):
            out.append(w)
        elif re.match(r'^[A-Z][a-z]+$', bare):
            # Lowercase Title-Case word (keep sentence-initial word capitalized unless whole string is Title-Case)
            if idx == 0 and cap_words < len(words):
                out.append(w)
            else:
                out.append(w.lower())
        else:
            out.append(w)
    return " ".join(out)


def _count_untranslated_english(out: str) -> int:
    tokens = re.findall(r'[A-Za-z]{3,}', out)
    return sum(1 for t in tokens if t.lower() not in _PROTECTED_ASCII_TOKENS)


def clean_argos_output(text: str, source_text: str = "") -> str:
    """Cleans up transliteration artifacts, broken parentheses, and entity remnants."""
    out = text
    src_low = (source_text or "").lower()
    for pat, repl in POST_FIXES:
        out = re.sub(pat, repl, out, flags=re.IGNORECASE)
    # Context-aware fixes where Argos picked the wrong homograph
    if "settings" in src_low and "car" not in src_low:
        out = re.sub(r'\bوالسيارات\b', 'والإعدادات', out)
        out = re.sub(r'\bالسيارات\b', 'الإعدادات', out)
        out = re.sub(r'\bتُقيمُ\b|\bتقيم\b', 'الإعدادات', out)
    if "right" in src_low and ("column" in src_low or "left" in src_low or "side" in src_low):
        out = re.sub(r'\bالصحيح\b', 'الأيمن', out)
    if "application" in src_low and "order" not in src_low and "request" not in src_low:
        out = re.sub(r'\bالطلب\b', 'التطبيق', out)
    open_count = out.count('(')
    close_count = out.count(')')
    if open_count != close_count:
        out = re.sub(r'[\(\)]', '', out)
    return re.sub(r'\s+', ' ', out).strip()


def _is_mostly_untranslated(src: str, out: str, to_code: str) -> bool:
    """Detects when Argos copied English verbatim instead of translating."""
    if not out or not out.strip():
        return True
    if to_code == "ar":
        has_ascii_words = bool(re.search(r'[A-Za-z]{2,}', src))
        if has_ascii_words and not _has_arabic(out):
            return True
    return out.strip().lower() == src.strip().lower()


def _argos_translate_resilient(trans_obj, text: str, from_code: str, to_code: str) -> str:
    """
    Runs Argos translation while working around Argos's Title-Case / colon-prefix
    verbatim-copy behavior, masking shortcuts/breadcrumbs, and preventing English leakage.
    """
    # 1. Mask keyboard shortcuts like Ctrl+T, Ctrl+Shift+T, Alt+F4 and inline breadcrumbs A > B > C
    masked_items = []

    def _mask_shortcut(m):
        masked_items.append(m.group(0))
        return f"9980{len(masked_items) - 1}"

    masked = re.sub(
        r'\b(?:Ctrl|Alt|Shift|Win|Cmd)(?:\s*\+\s*(?:Ctrl|Alt|Shift|Win|Cmd|F1[0-2]?|F[1-9]|Enter|Escape|Esc|Tab|Space|Backspace|Delete|Del|Insert|Ins|Home|End|PageUp|PageDown|Up|Down|Left|Right|[A-Za-z0-9]))+(?![A-Za-z0-9])',
        _mask_shortcut,
        text,
        flags=re.IGNORECASE,
    )

    def _mask_breadcrumb(m):
        masked_items.append(_translate_breadcrumb_span(m.group(0)))
        return f"9980{len(masked_items) - 1}"

    if to_code == "ar":
        masked = re.sub(
            r'\b[A-Za-z0-9]{1,20}(?:\s*(?:>|->|→)\s*[A-Za-z0-9]{1,20})+\b',
            _mask_breadcrumb,
            masked,
        )

    def _unmask(s: str) -> str:
        for idx, val in enumerate(masked_items):
            s = s.replace(f"9980{idx}", val)
        return s

    def _score_candidate(inp: str, cand: str) -> tuple:
        if _is_mostly_untranslated(inp, cand, to_code):
            return (0, -999, 0)
        inp_words = len(inp.split())
        cand_words = len(cand.split())
        # Heavily penalize severely truncated Argos hypotheses (e.g. 6 words collapsed to 1 word)
        trunc_penalty = -50 if (inp_words >= 4 and cand_words < max(2, int(inp_words * 0.35))) else 0
        if to_code == "ar":
            return (1, trunc_penalty - _count_untranslated_english(cand), min(cand_words, inp_words * 2))
        return (1, trunc_penalty, min(cand_words, inp_words * 2))

    def _best_call(inp: str) -> str:
        candidates = []
        norm_inp = _normalize_title_case_for_argos(inp) if from_code == "en" else inp
        inp_words = len(inp.split())

        for query in ([norm_inp] if norm_inp == inp else [norm_inp, inp]):
            res = trans_obj.translate(query)
            candidates.append(res)
            if (
                to_code == "ar"
                and _count_untranslated_english(res) == 0
                and not _is_mostly_untranslated(query, res, to_code)
                and not (inp_words >= 4 and len(res.split()) < max(2, int(inp_words * 0.35)))
            ):
                return res
            try:
                for h in trans_obj.hypotheses(query, num_hypotheses=4):
                    if h.value:
                        candidates.append(h.value)
            except Exception:
                pass

        # Full lowercase fallback if Title-Case still caused verbatim English leakage
        if from_code == "en":
            low_inp = inp.lower()
            if low_inp != norm_inp:
                res_low = trans_obj.translate(low_inp)
                candidates.append(res_low)
                try:
                    for h in trans_obj.hypotheses(low_inp, num_hypotheses=4):
                        if h.value:
                            candidates.append(h.value)
                except Exception:
                    pass

        return max(candidates, key=lambda c: _score_candidate(inp, c)) if candidates else inp

    out = _best_call(masked)

    # Capitalized sentence-case fallback for lowercase sentence fragments (e.g. 'a hard time...')
    if _is_mostly_untranslated(masked, out, to_code):
        stripped = masked.strip()
        if stripped and stripped[0].islower():
            cap_query = stripped[0].upper() + stripped[1:]
            cap_out = _best_call(cap_query)
            if not _is_mostly_untranslated(cap_query, cap_out, to_code):
                out = cap_out

    # Colon-prefix fallback (e.g. 'Note: Small 10px disclaimer...')
    if _is_mostly_untranslated(masked, out, to_code) and ":" in masked:
        prefix, rest = masked.split(":", 1)
        if prefix.strip() and rest.strip():
            p_key = prefix.strip().lower()
            p_trans = UI_MENU_WORDS.get(p_key) or TECH_TERMS.get(p_key) or _best_call(prefix.strip())
            r_trans = _best_call(rest.strip())
            if not _is_mostly_untranslated(rest.strip(), r_trans, to_code):
                out = f"{p_trans}: {r_trans}"

    # Patch stray untranslated English words ONLY when output is already substantially Arabic
    if to_code == "ar" and from_code == "en" and _has_arabic(out):
        ar_words = len(re.findall(r'[\u0600-\u06FF]{2,}', out))
        en_words = _count_untranslated_english(out)
        if ar_words >= max(1, en_words):
            def _fix_stray_en(m):
                w = m.group(0)
                wl = w.lower()
                if wl in _PROTECTED_ASCII_TOKENS:
                    return w
                if wl in UI_MENU_WORDS:
                    return UI_MENU_WORDS[wl]
                if wl in TECH_TERMS:
                    return TECH_TERMS[wl]
                try:
                    sub = trans_obj.translate(wl)
                    if sub and _has_arabic(sub):
                        return sub.strip()
                except Exception:
                    pass
                return w

            out = re.sub(r'\b[A-Za-z]{3,}\b', _fix_stray_en, out)

    return _unmask(out)


class TextLine:
    """Helper representing a detected OCR bounding box with coordinate & color metadata."""
    def __init__(self, box, text, score, bg_color=(255, 255, 255), fg_color=(15, 15, 15)):
        self.box = box
        self.text = text.strip()
        try:
            self.score = float(score)
        except Exception:
            self.score = 1.0
        xs = [pt[0] for pt in box]
        ys = [pt[1] for pt in box]
        self.x1 = int(round(min(xs)))
        self.y1 = int(round(min(ys)))
        self.x2 = int(round(max(xs)))
        self.y2 = int(round(max(ys)))
        self.w = max(8, self.x2 - self.x1)
        self.h = max(8, self.y2 - self.y1)
        self.bg_color = bg_color
        self.fg_color = fg_color


def _color_dist(c1, c2) -> float:
    return ((c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2 + (c1[2] - c2[2]) ** 2) ** 0.5


def _sample_line_colors(img_np, x1: int, y1: int, x2: int, y2: int):
    """
    Samples a 3px border ring around [x1, y1, x2, y2] using median to get the true
    background color, and extracts the contrasting foreground glyph color from the interior.
    """
    import numpy as np

    h, w = img_np.shape[:2]
    bx1 = max(0, x1 - 3)
    by1 = max(0, y1 - 3)
    bx2 = min(w, x2 + 3)
    by2 = min(h, y2 + 3)

    ring_pixels = []
    if by1 < y1:
        ring_pixels.append(img_np[by1:y1, bx1:bx2].reshape(-1, 3))
    if y2 < by2:
        ring_pixels.append(img_np[y2:by2, bx1:bx2].reshape(-1, 3))
    if bx1 < x1:
        ring_pixels.append(img_np[max(0, y1):min(h, y2), bx1:x1].reshape(-1, 3))
    if x2 < bx2:
        ring_pixels.append(img_np[max(0, y1):min(h, y2), x2:bx2].reshape(-1, 3))

    if ring_pixels:
        ring = np.concatenate(ring_pixels, axis=0)
        bg = tuple(int(v) for v in np.median(ring, axis=0))
    else:
        bg = (255, 255, 255)

    ix1, iy1 = max(0, x1), max(0, y1)
    ix2, iy2 = min(w, x2), min(h, y2)
    lum = 0.299 * bg[0] + 0.587 * bg[1] + 0.114 * bg[2]
    default_fg = (15, 15, 15) if lum > 135 else (245, 245, 245)

    if ix2 > ix1 and iy2 > iy1:
        patch = img_np[iy1:iy2, ix1:ix2].reshape(-1, 3).astype(np.float32)
        bg_arr = np.array(bg, dtype=np.float32)
        dists = np.linalg.norm(patch - bg_arr, axis=1)
        strong = patch[dists >= max(28.0, float(np.percentile(dists, 82)))]
        if len(strong) >= 3:
            fg = tuple(int(v) for v in np.median(strong, axis=0))
            # Ensure minimum readable contrast
            if _color_dist(fg, bg) >= 55:
                return bg, fg

    return bg, default_fg


def _merge_same_line_boxes(lines: list, img_np=None) -> list:
    """Merges horizontally adjacent word fragments sitting on the same visual line."""
    if len(lines) <= 1:
        return lines

    import numpy as np
    _tab_ext_re = re.compile(r'\.(pdf|png|jpg|jpeg|py|dart|exe|zip|txt|json|html|css|js|ts|md)$', re.IGNORECASE)
    _close_end_re = re.compile(r'(?:\.\.X|\.X|×)$')

    ordered = sorted(lines, key=lambda l: (l.y1, l.x1))
    merged = []

    for cur in ordered:
        matched = None
        for cand in reversed(merged):
            v_overlap = min(cand.y2, cur.y2) - max(cand.y1, cur.y1)
            min_h = min(cand.h, cur.h)
            max_h = max(cand.h, cur.h)
            cy_diff = abs((cand.y1 + cand.y2) / 2.0 - (cur.y1 + cur.y2) / 2.0)
            h_gap = cur.x1 - cand.x2

            if (
                v_overlap >= 0.45 * min_h
                and cy_diff <= 0.45 * max_h
                and 0.68 * cand.h <= cur.h <= 1.48 * cand.h
                and -4 <= h_gap <= max(14, int(1.0 * min_h))
                and _color_dist(cand.bg_color, cur.bg_color) < 40
                and _color_dist(cand.fg_color, cur.fg_color) < 85
            ):
                # Never merge across browser tab close markers, filenames, or vertical divider lines
                if _tab_ext_re.search(cand.text.strip()) or _tab_ext_re.search(cur.text.strip()):
                    continue
                if _close_end_re.search(cand.text.strip()) or cur.text.strip() in ("X", "x", "×"):
                    continue
                if h_gap < -1 and cand.w > 40 and cur.w > 40:
                    continue
                if img_np is not None and h_gap >= 2:
                    iy1 = max(0, max(cand.y1, cur.y1))
                    iy2 = min(img_np.shape[0], min(cand.y2, cur.y2))
                    ix1 = max(0, cand.x2)
                    ix2 = min(img_np.shape[1], cur.x1)
                    if iy2 > iy1 and ix2 > ix1:
                        gap_strip = img_np[iy1:iy2, ix1:ix2].astype(np.float32)
                        bg_arr = np.array(cand.bg_color, dtype=np.float32)
                        col_diff = np.max(np.linalg.norm(gap_strip - bg_arr, axis=2), axis=0)
                        # If a vertical separator/icon spans almost the full height in the gap, don't merge
                        dark_frac = np.mean(np.linalg.norm(gap_strip - bg_arr, axis=2) >= 24.0, axis=0)
                        if float(np.max(dark_frac)) >= 0.75 or float(np.max(col_diff)) >= 80.0:
                            continue
                matched = cand
                break

        if matched is not None:
            matched.text = f"{matched.text} {cur.text}".strip()
            matched.x1 = min(matched.x1, cur.x1)
            matched.y1 = min(matched.y1, cur.y1)
            matched.x2 = max(matched.x2, cur.x2)
            matched.y2 = max(matched.y2, cur.y2)
            matched.w = max(8, matched.x2 - matched.x1)
            matched.h = max(8, matched.y2 - matched.y1)
            matched.score = min(matched.score, cur.score)
        else:
            merged.append(cur)

    return merged


@lru_cache(maxsize=256)
def _get_cached_font(font_path: str, size: int):
    if font_path and os.path.exists(font_path):
        try:
            return ImageFont.truetype(font_path, size=size)
        except Exception:
            pass
    return ImageFont.load_default()


def _resolve_system_font_path(prefer_compact: bool = False) -> str:
    windir = os.environ.get("WINDIR", "C:\\Windows")
    fonts_dir = os.path.join(windir, "Fonts")
    candidates = ["tahoma.ttf", "segoeui.ttf", "arial.ttf"]
    for font_name in candidates:
        p = os.path.join(fonts_dir, font_name)
        if os.path.exists(p):
            return p
    return ""


def _shape_bidi(text: str, is_rtl: bool) -> str:
    if not text or not (is_rtl and _has_rtl(text)):
        return text
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped, base_dir="R")
    except Exception:
        return text


def _measure_text(font, shaped_text: str):
    """Returns (width, ink_height, top_offset) for accurate vertical & horizontal centering."""
    try:
        bbox = font.getbbox(shaped_text)
        w = max(1.0, float(bbox[2] - bbox[0]))
        h = max(1.0, float(bbox[3] - bbox[1]))
        return w, h, float(bbox[1])
    except Exception:
        return float(font.getlength(shaped_text)), float(getattr(font, "size", 14)), 0.0


def _available_horizontal_slack(img_np, line: TextLine, all_lines: list = None, max_probe: int = 44) -> tuple:
    """Probes left/right outside the box for uniform background space, stopping before any neighbor box."""
    import numpy as np

    ih, iw = img_np.shape[:2]
    bg = np.array(line.bg_color, dtype=np.float32)
    y_top = max(0, line.y1 + 2)
    y_bot = min(ih, max(y_top + 1, line.y2 - 2))

    # Clamp against neighboring boxes on the same vertical band
    min_left_x = 2
    max_right_x = iw - 2
    if all_lines:
        for other in all_lines:
            if other is line:
                continue
            v_over = min(line.y2, other.y2) - max(line.y1, other.y1)
            if v_over > 0:
                if other.x2 <= line.x1:
                    min_left_x = max(min_left_x, other.x2 + 6)
                elif other.x1 >= line.x2:
                    max_right_x = min(max_right_x, other.x1 - 6)

    left_slack = 0
    for step in range(4, max_probe + 1, 4):
        px = line.x1 - step
        if px < min_left_x:
            break
        col = img_np[y_top:y_bot, px:px + 4].astype(np.float32)
        if float(np.max(np.linalg.norm(col - bg, axis=2))) < 22.0:
            left_slack = step
        else:
            break

    right_slack = 0
    for step in range(4, max_probe + 1, 4):
        px = line.x2 + step
        if px >= max_right_x:
            break
        col = img_np[y_top:y_bot, px - 4:px].astype(np.float32)
        if float(np.max(np.linalg.norm(col - bg, axis=2))) < 22.0:
            right_slack = step
        else:
            break

    return max(0, left_slack - 4), max(0, right_slack - 4)


def _is_inside_centered_container(img_np, line: TextLine, max_probe: int = 80, bg_color=None) -> bool:
    """Returns True if the box sits symmetrically centered inside a bounded UI button/pill/card."""
    import numpy as np

    ih, iw = img_np.shape[:2]
    bg = np.array(bg_color if bg_color is not None else line.bg_color, dtype=np.float32)
    y_top = max(0, line.y1 + 2)
    y_bot = min(ih, max(y_top + 1, line.y2 - 2))

    left_wall = None
    for step in range(6, max_probe + 1, 2):
        px = line.x1 - step
        if px < 0:
            break
        col = img_np[y_top:y_bot, px:px + 2].astype(np.float32)
        if float(np.max(np.linalg.norm(col - bg, axis=2))) >= 24.0:
            left_wall = step
            break

    right_wall = None
    for step in range(6, max_probe + 1, 2):
        px = line.x2 + step
        if px >= iw:
            break
        col = img_np[y_top:y_bot, px - 2:px].astype(np.float32)
        if float(np.max(np.linalg.norm(col - bg, axis=2))) >= 24.0:
            right_wall = step
            break

    if left_wall is None or right_wall is None:
        return False
    tol = max(10, int(0.08 * min(left_wall, right_wall)))
    return (
        6 <= left_wall <= max_probe - 8
        and 6 <= right_wall <= max_probe - 8
        and abs(left_wall - right_wall) <= tol
    )


def _detect_group_alignment(group_idx: int, group_boxes: list, group_srcs: list, img_np, bg_color=None) -> str:
    """
    Infers the true original visual alignment ('left', 'center', or 'right') of a group
    from the source language, page/column geometry, and surrounding UI containers.
    """
    gx1, gy1, gx2, gy2, gw, gh, avg_h = group_boxes[group_idx]
    src = group_srcs[group_idx]
    src_is_rtl = _has_rtl(src)

    tol = max(12, int(round(avg_h * 0.9)))
    left_matches = 0
    right_matches = 0
    center_parent = False
    gcx = (gx1 + gx2) / 2.0

    for j, (ox1, oy1, ox2, oy2, ow, oh, _) in enumerate(group_boxes):
        if j == group_idx:
            continue
        # Only compare with reasonably nearby elements in vertical span
        if abs((gy1 + gy2) / 2.0 - (oy1 + oy2) / 2.0) > 420:
            continue
        ocx = (ox1 + ox2) / 2.0
        l_near = abs(gx1 - ox1) <= tol
        r_near = abs(gx2 - ox2) <= tol
        if l_near and r_near and abs(gcx - ocx) <= 8 and abs(gw - ow) >= 12:
            # Both edges are nearly equidistant from a shared center axis -> centered siblings
            center_parent = True
            continue
        if l_near:
            left_matches += 1
        if r_near:
            right_matches += 1
        # Check if this group sits horizontally centered relative to a nearby neighbor block
        if abs(gy1 - oy2) <= 75 or abs(oy1 - gy2) <= 75:
            if abs(gcx - ocx) <= 10 and abs(gx1 - ox1) > 14 and abs(gx2 - ox2) > 14:
                if ow > gw * 1.15 or gw > ow * 1.15:
                    center_parent = True

    if src_is_rtl:
        if left_matches >= 2 and right_matches == 0:
            return "left"
        return "right"

    # LTR source (e.g. English)
    if right_matches >= 2 and left_matches == 0:
        return "right"
    if left_matches >= 1:
        return "left"
    if center_parent:
        return "center"
    if img_np is not None:
        probe_box = TextLine([[gx1, gy1], [gx2, gy1], [gx2, gy2], [gx1, gy2]], src, 1.0, bg_color=bg_color or (255, 255, 255))
        if _is_inside_centered_container(img_np, probe_box, max_probe=260, bg_color=bg_color):
            return "center"
    return "left"


def _compute_safe_erase_rect(img_np, bg_color, x1: int, y1: int, x2: int, y2: int, pad_x: int = 2, pad_y: int = 2) -> tuple:
    """
    Expands [x1, y1, x2, y2] up to (pad_x, pad_y) while stopping strictly before any
    continuous horizontal divider rule or vertical container border so lines stay intact.
    Note: Pillow draw.rectangle([ex1, ey1, ex2, ey2]) is inclusive of ex2 and ey2.
    """
    import numpy as np

    ih, iw = img_np.shape[:2]
    bg = np.array(bg_color, dtype=np.float32)

    def _is_h_rule(y: int) -> bool:
        if y < 0 or y >= ih:
            return False
        rx1, rx2 = max(0, x1), min(iw, x2)
        if rx2 <= rx1:
            return False
        in_frac = float(np.mean(np.linalg.norm(img_np[y, rx1:rx2].astype(np.float32) - bg, axis=1) >= 22.0))
        if in_frac < 0.80:
            return False
        ext_left = max(0, rx1 - 24)
        ext_right = min(iw, rx2 + 24)
        ext_hit = False
        if rx1 - ext_left >= 8:
            if float(np.mean(np.linalg.norm(img_np[y, ext_left:rx1].astype(np.float32) - bg, axis=1) >= 22.0)) >= 0.75:
                ext_hit = True
        if not ext_hit and ext_right - rx2 >= 8:
            if float(np.mean(np.linalg.norm(img_np[y, rx2:ext_right].astype(np.float32) - bg, axis=1) >= 22.0)) >= 0.75:
                ext_hit = True
        return ext_hit

    def _is_v_rule(x: int) -> bool:
        if x < 0 or x >= iw:
            return False
        ry1, ry2 = max(0, y1), min(ih, y2)
        if ry2 <= ry1:
            return False
        in_frac = float(np.mean(np.linalg.norm(img_np[ry1:ry2, x].astype(np.float32) - bg, axis=1) >= 22.0))
        if in_frac < 0.80:
            return False
        ext_top = max(0, ry1 - 16)
        ext_bot = min(ih, ry2 + 16)
        if ry1 - ext_top >= 6 and float(np.mean(np.linalg.norm(img_np[ext_top:ry1, x].astype(np.float32) - bg, axis=1) >= 22.0)) >= 0.75:
            return True
        if ext_bot - ry2 >= 6 and float(np.mean(np.linalg.norm(img_np[ry2:ext_bot, x].astype(np.float32) - bg, axis=1) >= 22.0)) >= 0.75:
            return True
        return False

    ey1 = max(0, y1)
    for d in range(1, pad_y + 1):
        cand_y = y1 - d
        if cand_y < 0 or _is_h_rule(cand_y):
            break
        ey1 = cand_y

    ey2 = min(ih - 1, y2)
    for d in range(1, pad_y + 1):
        cand_y = y2 + d
        if cand_y >= ih or _is_h_rule(cand_y):
            break
        ey2 = cand_y

    ex1 = max(0, x1)
    for d in range(1, pad_x + 1):
        cand_x = x1 - d
        if cand_x < 0 or _is_v_rule(cand_x):
            break
        ex1 = cand_x

    ex2 = min(iw - 1, x2)
    for d in range(1, pad_x + 1):
        cand_x = x2 + d
        if cand_x >= iw or _is_v_rule(cand_x):
            break
        ex2 = cand_x

    return ex1, ey1, max(ex1, ex2), max(ey1, ey2)



class OfflineManager:
    """Manages offline language packages and offline screen OCR translation with high quality."""

    @staticmethod
    def get_installed_languages():
        """Returns list of installed languages."""
        try:
            _ensure_argos()
            import argostranslate.translate
            installed = argostranslate.translate.get_installed_languages()
            return [
                {
                    "code": lang.code,
                    "name": LANGUAGE_NAMES.get(lang.code, lang.name)
                }
                for lang in installed
            ]
        except Exception as e:
            print("Error getting installed languages:", e)
            return []

    @staticmethod
    def get_installed_pairs():
        """Returns list of installed (from_code, to_code) tuples."""
        try:
            _ensure_argos()
            import argostranslate.package
            packages = argostranslate.package.get_installed_packages()
            return [(p.from_code, p.to_code) for p in packages]
        except Exception as e:
            print("Error getting installed packages:", e)
            return []

    @staticmethod
    def is_pair_available(from_code, to_code):
        """Checks if translation can be performed between two languages (direct or via pivot)."""
        pairs = OfflineManager.get_installed_pairs()
        if (from_code, to_code) in pairs:
            return True
        if from_code != "en" and to_code != "en":
            if (from_code, "en") in pairs and ("en", to_code) in pairs:
                return True
        return False

    @staticmethod
    def get_supported_packages_catalog():
        """Returns catalog of commonly used language packages with installation status."""
        installed_pairs = set(OfflineManager.get_installed_pairs())
        catalog = [
            {"from": "en", "to": "ar", "label": "الإنجليزية ➔ العربية", "desc": "ترجمة شاشة اللابتوب الإنجليزية إلى العربية بدون نت"},
            {"from": "ar", "to": "en", "label": "العربية ➔ الإنجليزية", "desc": "ترجمة النصوص العربية إلى الإنجليزية بدون نت"},
            {"from": "fr", "to": "en", "label": "الفرنسية ➔ الإنجليزية (للترجمة إلى العربية)", "desc": "تتيح الترجمة من الفرنسية إلى العربية عبر الإنجليزية"},
            {"from": "es", "to": "en", "label": "الإسبانية ➔ الإنجليزية (للترجمة إلى العربية)", "desc": "تتيح الترجمة من الإسبانية إلى العربية عبر الإنجليزية"},
            {"from": "de", "to": "en", "label": "الألمانية ➔ الإنجليزية (للترجمة إلى العربية)", "desc": "تتيح الترجمة من الألمانية إلى العربية عبر الإنجليزية"},
            {"from": "tr", "to": "en", "label": "التركية ➔ الإنجليزية (للترجمة إلى العربية)", "desc": "تتيح الترجمة من التركية إلى العربية عبر الإنجليزية"},
            {"from": "ru", "to": "en", "label": "الروسية ➔ الإنجليزية (للترجمة إلى العربية)", "desc": "تتيح الترجمة من الروسية إلى العربية عبر الإنجليزية"}
        ]
        for item in catalog:
            item["installed"] = (item["from"], item["to"]) in installed_pairs
        return catalog

    @staticmethod
    def download_and_install_package(from_code, to_code, progress_callback=None):
        """Downloads and installs a language package from Argos repository."""
        try:
            _ensure_argos()
            import argostranslate.package

            if progress_callback:
                progress_callback("جاري تحديث فهرس الحزم...")
            argostranslate.package.update_package_index()

            available = argostranslate.package.get_available_packages()
            target_pkg = next(
                (p for p in available if p.from_code == from_code and p.to_code == to_code),
                None
            )
            if not target_pkg:
                return False, f"لم يتم العثور على حزمة للترجمة من {from_code} إلى {to_code}"

            if progress_callback:
                progress_callback(f"جاري تحميل حزمة {from_code} ➔ {to_code} ({target_pkg.package_version})...")

            download_path = target_pkg.download()

            if progress_callback:
                progress_callback("جاري تثبيت الحزمة على جهازك...")

            argostranslate.package.install_from_path(download_path)
            return True, f"تم تثبيت حزمة {from_code} ➔ {to_code} بنجاح!"
        except Exception as e:
            return False, f"حدث خطأ أثناء تحميل الحزمة: {e}"

    @staticmethod
    def translate_text(text: str, from_code: str = "en", to_code: str = "ar") -> str:
        """Translates text completely offline with UI glossary, shortcut preservation, and post-processing."""
        if not text or not text.strip():
            return ""

        cleaned = clean_html_entities(text)
        if not cleaned:
            return ""

        # Skip pure punctuation, numbers, or isolated 1-letter icon/page artifacts (e.g. '7/ 185 i')
        if not re.search(r'[A-Za-z\u0600-\u06FF]', cleaned):
            return cleaned
        if from_code in ("en", "auto") and to_code == "ar" and not _has_arabic(cleaned):
            if not re.search(r'[A-Za-z]{2,}', cleaned):
                return cleaned
            # Skip OCR gibberish from non-Latin browser tabs (e.g. '20222JljLiaJw3..X', 'ljuoueluaJlJgmX')
            if re.search(r'\.\.[Xx](?:\s|$)', cleaned) or re.search(r'\d[A-Za-z]{3,}\d', cleaned):
                return cleaned

        # Same source and target language
        if from_code == to_code:
            return cleaned

        # 1. Preserve genuine terminal commands, code statements, file paths, URLs, or underscore identifiers
        if is_code_or_command(cleaned):
            return cleaned
        if "_" in cleaned and " " not in cleaned and cleaned.lower() not in TECH_TERMS:
            return cleaned

        # Separate OCR-glued single-letter shortcut key from following lowercase word (e.g. 'Ctrl+Tto...' -> 'Ctrl+T to...')
        if from_code in ("en", "auto"):
            _known_keys = {
                "tab", "enter", "escape", "esc", "space", "backspace", "delete", "del",
                "insert", "ins", "home", "end", "pageup", "pagedown", "left", "right",
                "up", "down", "shift", "ctrl", "alt", "win", "cmd", "pause", "printscreen",
            }
            def _split_glued_shortcut(m):
                mod, k, rest = m.group(1), m.group(2), m.group(3)
                full_key = (k + rest).lower()
                if full_key in _known_keys or re.match(r'^f(?:1[0-2]|[1-9])$', full_key):
                    return m.group(0)
                return f"{mod}+{k} {rest}"
            cleaned = re.sub(
                r'\b(Ctrl|Alt|Shift|Win|Cmd)\+([A-Za-z])([a-z]{2,})\b',
                _split_glued_shortcut,
                cleaned,
                flags=re.IGNORECASE,
            )

        # Split accidental OCR-joined TitleCase words (e.g. 'LeftColumnTitle', 'AdvantagesofFlutter')
        # while preserving real brands like macOS, GitHub, YouTube, PyInstaller
        if from_code in ("en", "auto") and re.search(r'[a-z]{2,}[A-Z][a-z]{2,}', cleaned):
            _brand_skip = {"macos", "github", "gitlab", "youtube", "whatsapp", "javascript", "typescript", "pyinstaller", "rapidocr", "argostranslate"}
            def _split_camel(m):
                w = m.group(0)
                if w.lower() in _brand_skip:
                    return w
                s = re.sub(r'([a-z]{3,})(of|in|to|for|and|the|on|at|by|with)([A-Z][a-z]+)', r'\1 \2 \3', w)
                return re.sub(r'([a-z])([A-Z])', r'\1 \2', s)
            cleaned = re.sub(r'\b[A-Za-z]+\b', _split_camel, cleaned)

        # 2. Check UI menu breadcrumbs (e.g. Click File > Settings > Plugins)
        if to_code == "ar":
            menu_trans = translate_menu_path(cleaned)
            if menu_trans:
                return menu_trans

            low_key = cleaned.strip().lower()
            if low_key in TECH_TERMS:
                return TECH_TERMS[low_key]
            if low_key in UI_MENU_WORDS:
                return UI_MENU_WORDS[low_key]

            m_ver = re.match(r'^Version\s+([0-9]+(?:\.[0-9]+)*)\s*(?:[-–]\s*(.+))?$', cleaned.strip(), re.IGNORECASE)
            if m_ver:
                ver_num = m_ver.group(1)
                tail = m_ver.group(2)
                if tail:
                    tail_tr = OfflineManager.translate_text(tail.strip(), from_code=from_code, to_code=to_code)
                    return f"الإصدار {ver_num} - {tail_tr}"
                return f"الإصدار {ver_num}"

        # 3. Direct action phrases
        m_action = re.match(r'^(Open|Start|Launch)\s+(.+)$', cleaned, re.IGNORECASE)
        if m_action and to_code == "ar":
            rest = m_action.group(2)
            rest_key = rest.strip().lower()
            if rest_key in TECH_TERMS:
                return f"افتح {TECH_TERMS[rest_key]}"
            if rest_key in UI_MENU_WORDS:
                return f"افتح {UI_MENU_WORDS[rest_key]}"
            rest_trans = OfflineManager.translate_text(rest, from_code=from_code, to_code=to_code)
            return f"افتح {rest_trans}"

        # 4. Neural translation via Argos
        _ensure_argos()
        import argostranslate.translate

        langs = argostranslate.translate.get_installed_languages()
        if from_code == "auto" or not from_code:
            from_code = "ar" if _has_arabic(cleaned) else "en"

        if from_code == to_code:
            return cleaned

        from_lang = next((l for l in langs if l.code == from_code), None)
        to_lang = next((l for l in langs if l.code == to_code), None)

        if not from_lang or not to_lang:
            return cleaned

        # Normalize common brand names before translation
        prep_text = cleaned
        prep_text = re.sub(r'\bmacOS\b', 'macOS', prep_text, flags=re.IGNORECASE)
        prep_text = re.sub(r'\bAndroid Studio\b', 'Android Studio', prep_text, flags=re.IGNORECASE)

        trans = from_lang.get_translation(to_lang)
        raw_translation = None
        if trans:
            raw_translation = _argos_translate_resilient(trans, prep_text, from_code, to_code)
        else:
            # Pivot via English
            en_lang = next((l for l in langs if l.code == "en"), None)
            if en_lang and from_lang != en_lang and to_lang != en_lang:
                trans1 = from_lang.get_translation(en_lang)
                trans2 = en_lang.get_translation(to_lang)
                if trans1 and trans2:
                    mid = _argos_translate_resilient(trans1, prep_text, from_code, "en")
                    raw_translation = _argos_translate_resilient(trans2, mid, "en", to_code)

        if not raw_translation:
            raw_translation = cleaned

        if to_code == "ar":
            return clean_argos_output(raw_translation, cleaned)
        return raw_translation.strip()

    @staticmethod
    def test_offline_translation(from_code: str = "en", to_code: str = "ar", sample_text: str = None) -> dict:
        """Runs a verification test for offline translation and returns details."""
        if not sample_text:
            if from_code == "en":
                sample_text = "Click File > Settings > Plugins to install Flutter on macOS."
            elif from_code == "ar":
                sample_text = "مترجم الشاشة الذكي يعمل الآن بدون إنترنت وبأعلى كفاءة."
            else:
                sample_text = "Hello world! Offline mode test."

        t0 = time.time()
        try:
            result = OfflineManager.translate_text(sample_text, from_code=from_code, to_code=to_code)
            elapsed = round((time.time() - t0) * 1000)
            return {
                "success": True,
                "input": sample_text,
                "output": result,
                "from_code": from_code,
                "to_code": to_code,
                "elapsed_ms": elapsed
            }
        except Exception as e:
            return {
                "success": False,
                "input": sample_text,
                "error": str(e)
            }

    @staticmethod
    def get_system_font(size=16):
        """Retrieves a cached readable font supporting Arabic glyphs."""
        return _get_cached_font(_resolve_system_font_path(), max(8, int(size)))

    @staticmethod
    def _group_detected_lines(lines: list) -> list:
        """
        Column-aware paragraph grouping:
        Groups vertically adjacent lines ONLY when they belong to the same column,
        share background & foreground colors, have matching font height, and are not
        separate short titles/menu/button items.
        """
        if not lines:
            return []

        sorted_lines = sorted(lines, key=lambda l: (l.y1, l.x1))
        groups = []

        for line in sorted_lines:
            is_cur_code = is_code_or_command(line.text)
            cur_words = len(line.text.split())
            matched_group = None

            # Search recent groups in reverse so two parallel columns don't interfere
            for group in reversed(groups):
                prev = group[-1]
                v_gap = line.y1 - prev.y2
                max_neg_overlap = -max(6, int(0.35 * min(prev.h, line.h)))
                if v_gap < max_neg_overlap:
                    continue
                if v_gap > max(6, int(0.50 * prev.h)):
                    continue

                # Ensure line actually lies below prev vertically (not horizontally adjacent)
                cy_diff = ((line.y1 + line.y2) - (prev.y1 + prev.y2)) / 2.0
                if cy_diff < 0.45 * min(prev.h, line.h):
                    continue

                # Allow natural last-line bbox height variation while separating headings from body
                ref_h = max(g.h for g in group)
                if not (0.68 * ref_h <= line.h <= 1.45 * ref_h):
                    continue
                if _color_dist(line.bg_color, prev.bg_color) > 38:
                    continue
                if _color_dist(line.fg_color, prev.fg_color) > 70:
                    continue

                # Must overlap horizontally and align on left or right edge
                h_overlap = min(line.x2, prev.x2) - max(line.x1, prev.x1)
                if h_overlap <= 0:
                    continue
                edge_aligned = (
                    abs(line.x1 - prev.x1) <= max(24, int(1.4 * prev.h))
                    or abs(line.x2 - prev.x2) <= max(24, int(1.4 * prev.h))
                )
                if not edge_aligned:
                    continue

                if is_cur_code or is_code_or_command(prev.text):
                    continue

                # Keep short headings, UI menu items, and buttons separate from body paragraphs
                prev_words = len(prev.text.split())
                if len(group) == 1 and prev_words <= 4 and not prev.text.endswith((",", ";")) and (
                    cur_words <= 4 or prev.w < 0.72 * line.w or v_gap > max(3, int(0.28 * prev.h))
                ):
                    continue

                if prev.text.endswith((":", "!", "?")):
                    continue
                if prev.text.endswith(".") and prev_words <= 6:
                    continue

                matched_group = group
                break

            if matched_group is not None:
                matched_group.append(line)
            else:
                groups.append([line])

        return groups

    @staticmethod
    def _fit_single_line_font(font_path: str, text: str, is_rtl: bool, max_w: float, max_h: float, min_font: int = 7):
        """Binary-searches the largest font size whose (ascent+descent) and width fit cleanly inside (max_w, max_h)."""
        shaped = _shape_bidi(text, is_rtl)
        max_em = max(float(min_font + 2), float(max_h) * 1.05)
        low, high = min_font, max(min_font + 2, min(72, int(round(max_h))))
        best_size = low
        best_font = _get_cached_font(font_path, low)

        while low <= high:
            mid = (low + high) // 2
            font = _get_cached_font(font_path, mid)
            ascent, descent = font.getmetrics()
            em = ascent + descent
            tw = font.getlength(shaped)
            if tw <= max_w and em <= max_em:
                best_size = mid
                best_font = font
                low = mid + 1
            else:
                high = mid - 1

        return best_font, best_size, shaped

    @staticmethod
    def _fit_paragraph_font(font_path: str, text: str, is_rtl: bool, box_w: float, box_h: float, avg_line_h: float, min_font: int = 6):
        """Binary-searches the largest font size (matching source line height) whose wrapped lines fit inside (box_w, box_h)."""
        words = text.split()
        if not words:
            font = _get_cached_font(font_path, 12)
            return font, 12, []

        max_em = max(float(min_font + 2), float(avg_line_h) * 1.05)
        low, high = min_font, max(min_font + 2, min(48, int(round(avg_line_h))))
        best_font = _get_cached_font(font_path, low)
        best_size = low
        best_lines = None

        while low <= high:
            mid = (low + high) // 2
            font = _get_cached_font(font_path, mid)
            ascent, descent = font.getmetrics()
            em = ascent + descent
            if em > max_em:
                high = mid - 1
                continue

            wrapped_raw = []
            cur = []
            for w in words:
                cand = " ".join(cur + [w])
                cand_shaped = _shape_bidi(cand, is_rtl)
                if font.getlength(cand_shaped) <= box_w or not cur:
                    cur.append(w)
                else:
                    wrapped_raw.append(" ".join(cur))
                    cur = [w]
            if cur:
                wrapped_raw.append(" ".join(cur))

            shaped_lines = [_shape_bidi(wl, is_rtl) for wl in wrapped_raw]
            total_h = len(shaped_lines) * (em + 1)
            widest = max((font.getlength(sl) for sl in shaped_lines), default=0.0)

            if total_h <= box_h * 1.02 and widest <= box_w * 1.02:
                best_font = font
                best_size = mid
                best_lines = shaped_lines
                low = mid + 1
            else:
                high = mid - 1

        if best_lines is None:
            font = _get_cached_font(font_path, min_font)
            cur = []
            wrapped_raw = []
            for w in words:
                cand = " ".join(cur + [w])
                if font.getlength(_shape_bidi(cand, is_rtl)) <= box_w or not cur:
                    cur.append(w)
                else:
                    wrapped_raw.append(" ".join(cur))
                    cur = [w]
            if cur:
                wrapped_raw.append(" ".join(cur))
            best_lines = [_shape_bidi(wl, is_rtl) for wl in wrapped_raw]
            best_font = font
            best_size = min_font

        return best_font, best_size, best_lines

    @staticmethod
    def render_offline_screen_translation(image: Image.Image, to_code: str = "ar", from_code: str = "auto") -> dict:
        """
        Executes full offline OCR and layout-preserving in-place translation overlay generation.
        """
        import gc
        import numpy as np

        ocr = get_ocr_engine()
        if ocr is None:
            return {"success": False, "error": "محرك RapidOCR غير مثبت أو تعذر تشغيله."}

        rgb_img = image.convert("RGB")
        img_np = np.array(rgb_img)

        # Upscale smaller snips/regions so small UI text is detected reliably
        scale = 1.0
        if min(rgb_img.width, rgb_img.height) < 280:
            scale = 2.0
        elif min(rgb_img.width, rgb_img.height) < 520 or max(rgb_img.width, rgb_img.height) < 900:
            scale = 1.5

        if scale != 1.0:
            up_img = rgb_img.resize(
                (int(round(rgb_img.width * scale)), int(round(rgb_img.height * scale))),
                Image.Resampling.LANCZOS
            )
            ocr_input = np.array(up_img)[:, :, ::-1]  # BGR for RapidOCR
        else:
            ocr_input = img_np[:, :, ::-1]

        try:
            ocr_results, _ = ocr(ocr_input)
        except Exception as ocr_err:
            return {"success": False, "error": f"خطأ في التعرف الضوئي (OCR): {ocr_err}"}

        if not ocr_results and scale == 1.0:
            scale = 1.5
            up_img = rgb_img.resize(
                (int(round(rgb_img.width * scale)), int(round(rgb_img.height * scale))),
                Image.Resampling.LANCZOS
            )
            try:
                ocr_results, _ = ocr(np.array(up_img)[:, :, ::-1])
            except Exception:
                ocr_results = None

        if not ocr_results:
            return {
                "success": False,
                "error": "لم يتم العثور على أي نصوص في هذه الشاشة لقراءتها."
            }

        valid_lines = []
        for item in ocr_results:
            raw_box, txt, score = item[0], item[1], item[2]
            if scale != 1.0:
                raw_box = [[pt[0] / scale, pt[1] / scale] for pt in raw_box]
            tl = TextLine(raw_box, txt, score)
            min_sc = 0.58 if len(tl.text) <= 2 else 0.45
            if tl.text and tl.score >= min_sc and (len(tl.text) > 1 or tl.text.isalnum()):
                bg_c, fg_c = _sample_line_colors(img_np, tl.x1, tl.y1, tl.x2, tl.y2)
                tl.bg_color = bg_c
                tl.fg_color = fg_c
                valid_lines.append(tl)

        if not valid_lines:
            return {
                "success": False,
                "error": "لم يتم العثور على نصوص واضحة بما يكفي للترجمة."
            }

        # Merge horizontally fragmented word boxes on the same line (respecting tab dividers)
        valid_lines = _merge_same_line_boxes(valid_lines, img_np=img_np)

        # Determine source language
        if not from_code or from_code == "auto":
            all_text = " ".join(l.text for l in valid_lines)
            detected_lang = "ar" if _has_arabic(all_text) else "en"
        else:
            detected_lang = from_code

        # Verify local translation model availability before painting
        if detected_lang != to_code and not OfflineManager.is_pair_available(detected_lang, to_code):
            src_lbl = LANGUAGE_NAMES.get(detected_lang, detected_lang)
            tgt_lbl = LANGUAGE_NAMES.get(to_code, to_code)
            return {
                "success": False,
                "error": f"حزمة الترجمة المحلية ({src_lbl} ➔ {tgt_lbl}) غير مثبتة.\nيمكنك تثبيتها من تبويب (بدون إنترنت) في الإعدادات أو التبديل إلى الوضع التلقائي."
            }

        # Group lines into true paragraphs
        line_groups = OfflineManager._group_detected_lines(valid_lines)

        overlay_img = rgb_img.copy()
        draw = ImageDraw.Draw(overlay_img)
        active_font_path = _resolve_system_font_path()

        # Precompute group bounding boxes & source texts so alignment detection sees the full page geometry
        group_boxes = []
        group_srcs = []
        for group in line_groups:
            gx1 = min(l.x1 for l in group)
            gy1 = min(l.y1 for l in group)
            gx2 = max(l.x2 for l in group)
            gy2 = max(l.y2 for l in group)
            gw = max(10, gx2 - gx1)
            gh = max(10, gy2 - gy1)
            avg_h = sum(l.h for l in group) / len(group)
            group_boxes.append((gx1, gy1, gx2, gy2, gw, gh, avg_h))
            group_srcs.append(" ".join(l.text for l in group))

        ocr_lines = []
        translated_lines = []

        for g_idx, group in enumerate(line_groups):
            merged_src = group_srcs[g_idx]
            ocr_lines.append(merged_src)

            trans_text = OfflineManager.translate_text(merged_src, from_code=detected_lang, to_code=to_code)
            translated_lines.append(trans_text)

            # If translation didn't change the text (e.g. filename, URL, code, gibberish tab), leave original pixels untouched
            if not trans_text or trans_text.strip() == merged_src.strip():
                continue

            gx1, gy1, gx2, gy2, gw, gh, avg_line_h = group_boxes[g_idx]

            # Median colors across lines in group for clean consistency
            bg_color = group[len(group) // 2].bg_color
            text_color = group[len(group) // 2].fg_color

            # Erase original text cleanly without eating into surrounding divider lines/borders/icons
            for l in group:
                ex1, ey1, ex2, ey2 = _compute_safe_erase_rect(img_np, l.bg_color, l.x1, l.y1, l.x2, l.y2, pad_x=2, pad_y=2)
                draw.rectangle([ex1, ey1, ex2, ey2], fill=l.bg_color)

            if len(group) > 1:
                ex1, ey1, ex2, ey2 = _compute_safe_erase_rect(img_np, bg_color, gx1, gy1, gx2, gy2, pad_x=2, pad_y=2)
                draw.rectangle([ex1, ey1, ex2, ey2], fill=bg_color)

            # ONLY treat as RTL shaping if translated text actually has RTL/Arabic characters!
            is_rtl = _has_rtl(trans_text)
            align = _detect_group_alignment(g_idx, group_boxes, group_srcs, img_np, bg_color=bg_color)

            if len(group) == 1:
                line = group[0]
                left_slack, right_slack = _available_horizontal_slack(img_np, line, valid_lines)
                if align == "left" and _is_inside_centered_container(img_np, line):
                    align = "center"

                if align == "center":
                    safe_side = min(left_slack, right_slack)
                    min_x = max(2, gx1 - safe_side)
                    max_x = min(rgb_img.width - 2, gx2 + safe_side)
                elif align == "right":
                    # Anchor right edge at gx2; only borrow left slack if translation is wider than gw
                    safe_left = min(left_slack, max(12, int(gw * 0.35)))
                    min_x = max(2, gx1 - safe_left)
                    max_x = min(rgb_img.width - 2, gx2)
                else:
                    # Anchor left edge at gx1 (never spill left into bullets/icons!); borrow right slack if needed
                    safe_right = min(right_slack, max(12, int(gw * 0.35)))
                    min_x = max(2, gx1)
                    max_x = min(rgb_img.width - 2, gx2 + safe_right)

                avail_w = max(12, max_x - min_x)

                font, font_size, shaped = OfflineManager._fit_single_line_font(
                    active_font_path, trans_text, is_rtl, avail_w, gh, min_font=7
                )
                tw, th, top_off = _measure_text(font, shaped)

                # If single-line still exceeds safe box bounds, wrap cleanly inside [min_x, max_x]
                if tw > avail_w * 1.02 and len(trans_text.split()) >= 2:
                    box_h_wrap = max(gh + 4, int(gh * 1.35))
                    w_font, w_size, wrapped_lines = OfflineManager._fit_paragraph_font(
                        active_font_path, trans_text, is_rtl, avail_w, box_h_wrap, max(9.0, avg_line_h * 0.85), min_font=6
                    )
                    if wrapped_lines and len(wrapped_lines) >= 1:
                        w_asc, w_desc = w_font.getmetrics()
                        line_step = max(w_asc + w_desc, w_size + 2)
                        total_h = line_step * len(wrapped_lines)
                        cur_y = gy1 + (gh - total_h) / 2.0
                        ex1, ey1, ex2, ey2 = _compute_safe_erase_rect(
                            img_np, bg_color, min_x, int(cur_y), max_x, int(cur_y + total_h), pad_x=1, pad_y=1
                        )
                        draw.rectangle([ex1, ey1, ex2, ey2], fill=bg_color)
                        w_max_tw = max(_measure_text(w_font, wl)[0] for wl in wrapped_lines)
                        w_block_right = min(float(max_x), float(min_x) + w_max_tw)
                        for wl in wrapped_lines:
                            w_tw, w_th, w_top = _measure_text(w_font, wl)
                            if align == "center":
                                dx = min_x + (avail_w - w_tw) / 2.0
                            elif align == "right":
                                dx = max(float(min_x), float(max_x) - w_tw)
                            elif is_rtl and len(wrapped_lines) > 1:
                                dx = max(float(min_x), w_block_right - w_tw)
                            else:
                                dx = float(min_x)
                            dy = cur_y + (line_step - w_th) / 2.0 - w_top
                            draw.text((dx, dy), wl, fill=text_color, font=w_font)
                            cur_y += line_step
                        continue

                if align == "center":
                    draw_x = (gx1 + gx2 - tw) / 2.0
                elif align == "right":
                    draw_x = float(gx2) - tw
                else:
                    draw_x = float(gx1)

                # Strictly clamp inside safe bounds [min_x, max_x - tw]
                draw_x = max(float(min_x), min(float(max_x) - tw, draw_x))
                draw_x = max(2.0, min(float(rgb_img.width) - tw - 2.0, draw_x))
                draw_y = gy1 + (gh - th) / 2.0 - top_off

                if draw_x < gx1 or draw_x + tw > gx2:
                    ex1, ey1, ex2, ey2 = _compute_safe_erase_rect(
                        img_np, bg_color, int(draw_x), gy1, int(draw_x + tw), gy2, pad_x=2, pad_y=2
                    )
                    draw.rectangle([ex1, ey1, ex2, ey2], fill=bg_color)

                draw.text((draw_x, draw_y), shaped, fill=text_color, font=font)
            else:
                # Multi-line paragraph: fit wrapped lines inside exact (gw, gh) preserving column alignment
                font, font_size, shaped_lines = OfflineManager._fit_paragraph_font(
                    active_font_path, trans_text, is_rtl, gw, gh, avg_line_h, min_font=6
                )
                if not shaped_lines:
                    continue

                ascent, descent = font.getmetrics()
                em = ascent + descent
                natural_step = max(em + 1, int(round(avg_line_h * 1.08)))
                if len(shaped_lines) >= len(group):
                    line_step = max(float(em), min(float(natural_step), gh / max(1, len(shaped_lines))))
                else:
                    line_step = natural_step
                total_block_h = line_step * len(shaped_lines)
                # Keep Line 1 anchored near gy1 when paragraph wraps into fewer lines (matches bullet Y)
                if len(shaped_lines) < len(group):
                    cur_y = float(gy1)
                else:
                    cur_y = gy1 + max(0.0, (gh - total_block_h) / 2.0)

                # For multi-line wrapped RTL paragraphs in a left-aligned column, anchor the block's
                # left edge at gx1 (so Line 1 touches bullets/margin with zero gap) and right-align
                # shorter trailing lines to block_right = gx1 + max_line_w under Line 1's Arabic start.
                max_line_w = max(_measure_text(font, sl)[0] for sl in shaped_lines)
                block_right = min(float(gx2), float(gx1) + max_line_w)
                use_block_rtl = (is_rtl and align == "left" and len(shaped_lines) > 1)
                for sl in shaped_lines:
                    tw, th, top_off = _measure_text(font, sl)
                    if align == "center":
                        draw_x = gx1 + max(0.0, (gw - tw) / 2.0)
                    elif align == "right":
                        draw_x = max(float(gx1), float(gx2) - tw)
                    elif use_block_rtl:
                        draw_x = max(float(gx1), block_right - tw)
                    else:
                        draw_x = float(gx1)
                    line_y = cur_y + (line_step - th) / 2.0 - top_off
                    draw.text((draw_x, line_y), sl, fill=text_color, font=font)
                    cur_y += line_step

        # Save to temp overlay
        temp_dir = os.path.join(tempfile.gettempdir(), "smart_screen_translator")
        os.makedirs(temp_dir, exist_ok=True)
        overlay_path = os.path.join(temp_dir, "capture_overlay_offline.png")
        overlay_img.save(overlay_path, format="PNG")
        gc.collect()

        return {
            "success": True,
            "ocr_text": "\n".join(ocr_lines),
            "translated_text": "\n".join(translated_lines),
            "detected_language": detected_lang,
            "target_language": to_code,
            "overlay_path": overlay_path,
            "is_offline": True
        }
