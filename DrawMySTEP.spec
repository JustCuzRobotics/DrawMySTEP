# -*- mode: python ; coding: utf-8 -*-
# DrawMySTEP.spec — PyInstaller build configuration
#
# Build:
#   pyinstaller DrawMySTEP.spec
#
# Output:
#   dist/DrawMySTEP/DrawMySTEP.exe   (double-click to launch)
#   dist/DrawMySTEP/...              (supporting files — keep with the .exe)
#
# To share: zip the entire dist/DrawMySTEP/ folder.

from PyInstaller.utils.hooks import collect_all, collect_data_files

cadquery_datas,      cadquery_binaries,      cadquery_hiddenimports      = collect_all("cadquery")
ocp_datas,           ocp_binaries,           ocp_hiddenimports           = collect_all("OCP")
casadi_datas,        casadi_binaries,        casadi_hiddenimports        = collect_all("casadi")
customtkinter_datas, _,                      _                           = collect_all("customtkinter")
ezdxf_datas,         _,                      ezdxf_hiddenimports         = collect_all("ezdxf")
shapely_datas,       shapely_binaries,       shapely_hiddenimports       = collect_all("shapely")
reportlab_datas,     _,                      reportlab_hiddenimports     = collect_all("reportlab")

block_cipher = None

a = Analysis(
    ["DrawMySTEP.py"],
    pathex=["."],
    binaries=(
        cadquery_binaries
        + ocp_binaries
        + casadi_binaries
        + shapely_binaries
    ),
    datas=(
        cadquery_datas
        + ocp_datas
        + casadi_datas
        + customtkinter_datas
        + ezdxf_datas
        + shapely_datas
        + reportlab_datas
        + [("step_laser", "step_laser")]
        + [("dxf_min_bound", "dxf_min_bound")]
    ),
    hiddenimports=(
        cadquery_hiddenimports
        + ocp_hiddenimports
        + casadi_hiddenimports
        + ezdxf_hiddenimports
        + shapely_hiddenimports
        + reportlab_hiddenimports
        + [
            "casadi",
            "cadquery",
            "OCP",
            "ezdxf",
            "ezdxf.addons",
            "shapely",
            "shapely.geometry",
            "shapely.ops",
            "numpy",
            "reportlab",
            "reportlab.graphics",
            "reportlab.pdfgen",
            "reportlab.pdfgen.canvas",
            "reportlab.lib",
            "reportlab.lib.pagesizes",
            "reportlab.lib.units",
            "reportlab.lib.colors",
            "customtkinter",
            "click",
            "PIL",
            "PIL.Image",
            "step_laser",
            "step_laser.main",
            "step_laser.step_reader",
            "step_laser.projection",
            "step_laser.optimizer",
            "step_laser.exporters",
            "step_laser.exporters.dxf_exporter",
            "step_laser.exporters.svg_exporter",
            "step_laser.exporters.pdf_exporter",
            "dxf_min_bound",
            "dxf_min_bound.main",
        ]
    ),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["rthook_casadi.py"],
    excludes=[
        "matplotlib",
        "scipy",
        "IPython",
        "jupyter",
        "tkinter.test",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DrawMySTEP",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,   # windowed app — no console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="DrawMySTEP",
)
