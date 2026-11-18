import os
import sys
import shutil
import PyInstaller.__main__


def _write_setup_version_file(path):
    content = """VSVersionInfo(
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
          StringStruct('FileDescription', 'Smart Screen Translator PC Installer'),
          StringStruct('FileVersion', '2.0.0.0'),
          StringStruct('InternalName', 'Setup_SmartScreenTranslator'),
          StringStruct('LegalCopyright', 'Copyright (C) 2026 Riad Saleem'),
          StringStruct('OriginalFilename', 'Setup_SmartScreenTranslator.exe'),
          StringStruct('ProductName', 'Smart Screen Translator PC Setup'),
          StringStruct('ProductVersion', '2.0.0.0')
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def build_installer():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)

    icon_ico = os.path.join(base_dir, "icon.ico")
    icon_png = os.path.join(base_dir, "icon.png")
    zip_payload = os.path.join(base_dir, "app_payload.zip")

    if not os.path.exists(zip_payload):
        print("Error: app_payload.zip not found!")
        sys.exit(1)

    import tempfile
    ver_file = os.path.join(tempfile.gettempdir(), "sst_setup_version.txt")
    _write_setup_version_file(ver_file)

    args = [
        "installer_gui.py",
        "--name=Setup_SmartScreenTranslator",
        "--onefile",
        "--noconsole",
        "--uac-admin",
        f"--icon={icon_ico}",
        f"--version-file={ver_file}",
        f"--add-data={zip_payload};.",
        f"--add-data={icon_ico};.",
        f"--add-data={icon_png};.",
        "--hidden-import=ui_theme",
        "--hidden-import=ui_icons",
        "--hidden-import=ui_components",
        "--hidden-import=PIL.Image",
        "--hidden-import=PIL.ImageTk",
        "--hidden-import=PIL.ImageDraw",
        "--hidden-import=win32com.client",
        "--exclude-module=cv2",
        "--exclude-module=numpy",
        "--exclude-module=onnxruntime",
        "--exclude-module=ctranslate2",
        "--exclude-module=rapidocr_onnxruntime",
        "--exclude-module=argostranslate",
        "--exclude-module=cryptography",
        "--exclude-module=scipy",
        "--exclude-module=pandas",
        "--exclude-module=torch",
        "--clean",
        "--noconfirm",
    ]

    print("Building standalone Setup_SmartScreenTranslator.exe...")
    PyInstaller.__main__.run(args)
    print("Installer built successfully!")

    dist_setup = os.path.join(base_dir, "dist", "Setup_SmartScreenTranslator.exe")
    root_setup = os.path.join(base_dir, "Setup_SmartScreenTranslator.exe")
    if os.path.exists(dist_setup):
        print(f"Copying {dist_setup} to {root_setup}...")
        try:
            shutil.copy2(dist_setup, root_setup)
            print(f"Setup copied to root directory successfully! ({os.path.getsize(root_setup):,} bytes)")
        except Exception as e:
            print(f"Note: Could not copy to root ({e}), dist copy is ready.")


if __name__ == "__main__":
    build_installer()
