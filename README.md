# DrawMySTEP

Windows GUI for converting 3D STEP files into laser-cut-ready DXF, SVG, and PDF.

## Features

- **STEP → DXF / SVG / PDF** — Batch-converts STEP files. Auto-detects extrusion axis, optimizes rotation to minimize bounding box.
- **DXF Rotator** — Rotates existing DXF files to their minimum bounding box orientation.

## Requirements

```
pip install cadquery customtkinter ezdxf shapely numpy reportlab click
```

## Run

```
python DrawMySTEP.py
```

## Build standalone .exe

```
pip install pyinstaller
pyinstaller DrawMySTEP.spec
```

Distributable app will be in `dist/DrawMySTEP/`. Zip that folder to share.
