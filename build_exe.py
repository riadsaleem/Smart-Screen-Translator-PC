import os
import sys
import shutil
import zipfile
import PyInstaller.__main__

EXCLUDED_MODULES = [
    "torch", "torchvision", "torchaudio", "stanza",
    "spacy", "thinc", "blis", "cymem", "preshed", "murmurhash",
    "srsly", "catalogue", "confection", "weasel", "cloudpathlib", "typer",
    "scipy", "pyarrow", "pandas", "matplotlib", "kiwisolver", "fontTools",
    "jedi", "parso", "IPython", "nbformat", "jsonschema", "jsonschema_specifications",
    "psycopg", "psycopg_binary", "sqlalchemy", "lxml",
    "pytest", "sympy", "networkx", "sklearn",
    "cryptography", "_cffi_backend", "sacremoses", "rich", "pygments",
    "setuptools", "pkg_resources", "distutils", "unittest", "pydoc", "doctest",
    "lib2to3", "test", "ensurepip", "pip", "wheel",
    "PyQt5", "PyQt6", "PySide2", "PySide6",
]

# Unused bulky native binaries & model files inside dependencies that are never invoked at runtime
UNUSED_BINARIES = {
    "opencv_videoio_ffmpeg500_64.dll",
    "_avif.cp314-win_amd64.pyd",
    "cudnn64_9.dll",
    "ch_ppocr_mobile_v2.0_cls_infer.onnx",
}

UNUSED_DIRS = [
    os.path.join("_internal", "_tcl_data", "tzdata"),
    os.path.join("_internal", "_tcl_data", "demos"),
    os.path.join("_internal", "_tk_data", "demos"),
    os.path.join("_internal", "_tk_data", "images"),
    os.path.join("_internal", "ctranslate2", "converters"),
]


def _write_version_file(path, file_desc, orig_name):
    content = f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(2, 0, 0, 0),
    prodvers=(2, 0, 0, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', 'Riad Saleem'),
          StringStruct('FileDescription', '{file_desc}'),
          StringStruct('FileVersion', '2.0.0.0'),
          StringStruct('InternalName', 'SmartScreenTranslator'),
          StringStruct('LegalCopyright', 'Copyright (C) 2026 Riad Saleem'),
          StringStruct('OriginalFilename', '{orig_name}'),
          StringStruct('ProductName', 'Smart Screen Translator PC'),
          StringStruct('ProductVersion', '2.0.0.0')
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def build():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)

    icon_ico = os.path.join(base_dir, "icon.ico")
    icon_png = os.path.join(base_dir, "icon.png")
    config_json = os.path.join(base_dir, "config.json")
    version_json = os.path.join(base_dir, "version.json")
    en_ar_dir = os.path.join(base_dir, "packages", "en_ar")

    import tempfile
    ver_file = os.path.join(tempfile.gettempdir(), "sst_app_version.txt")
    _write_version_file(ver_file, "Smart Screen Translator PC", "SmartScreenTranslator.exe")

    args = [
        "main.py",
        "--name=SmartScreenTranslator",
        "--onedir",
        "--noconsole",
        f"--icon={icon_ico}",
        f"--version-file={ver_file}",
        f"--add-data={icon_ico};.",
        f"--add-data={icon_png};.",
        f"--add-data={config_json};.",
        f"--add-data={version_json};.",
        "--collect-all=chrome_lens_py",
        "--collect-all=arabic_reshaper",
        "--collect-all=bidi",
        "--collect-all=pystray",
        "--collect-all=keyboard",
        "--collect-all=mss",
        "--collect-all=rapidocr_onnxruntime",
        "--collect-all=onnxruntime",
        "--collect-all=argostranslate",
        "--collect-all=ctranslate2",
        "--collect-all=sentencepiece",
        "--collect-all=minisbd",
        "--hidden-import=PIL._imagingtk",
        "--hidden-import=PIL.ImageTk",
        "--hidden-import=ui_theme",
        "--hidden-import=ui_icons",
        "--hidden-import=ui_components",
        "--hidden-import=settings_window",
        "--clean",
        "--noconfirm",
    ]

    # Bundle ONLY English -> Arabic offline package (other pairs can be downloaded on demand in Settings)
    if os.path.exists(en_ar_dir):
        args.append(f"--add-data={en_ar_dir};packages/en_ar")

    for mod in EXCLUDED_MODULES:
        args.append(f"--exclude-module={mod}")

    print("Starting PyInstaller build (lean mode, Arabic-only offline model, excluding bloat)...")
    PyInstaller.__main__.run(args)
    print("Build finished successfully!")

    dist_app_dir = os.path.join(base_dir, "dist", "SmartScreenTranslator")
    if os.path.exists(dist_app_dir):
        # Strip unused bulky binaries
        for root, dirs, files in os.walk(dist_app_dir):
            for file in files:
                if file.lower() in UNUSED_BINARIES:
                    full_p = os.path.join(root, file)
                    try:
                        os.remove(full_p)
                        print(f"Removed unused binary: {file}")
                    except Exception as e:
                        print(f"Could not remove {file}: {e}")

        # Strip unused Tcl/Tk demos/tzdata & converter dirs
        for rel_dir in UNUSED_DIRS:
            full_d = os.path.join(dist_app_dir, rel_dir)
            if os.path.exists(full_d):
                try:
                    shutil.rmtree(full_d, ignore_errors=True)
                    print(f"Removed unused dir: {rel_dir}")
                except Exception:
                    pass

        payload_zip = os.path.join(base_dir, "app_payload.zip")
        print(f"Packaging {dist_app_dir} into {payload_zip} (standard DEFLATE)...")
        with zipfile.ZipFile(payload_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for root, dirs, files in os.walk(dist_app_dir):
                for file in files:
                    full_p = os.path.join(root, file)
                    rel_p = os.path.relpath(full_p, dist_app_dir)
                    zf.write(full_p, rel_p)
        print(f"Successfully packaged app_payload.zip! ({os.path.getsize(payload_zip):,} bytes)")


if __name__ == "__main__":
    build()
