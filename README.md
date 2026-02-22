# DrawMySTEP

Windows GUI for converting 3D STEP files into laser-cut-ready DXF, SVG, and PDF.

<img width="542" height="444" alt="DrawMySTEP_STEP_interface" src="https://github.com/user-attachments/assets/7efc336c-61ef-4cda-ae34-0957e6c94045" />
<img width="542" height="444" alt="DrawMySTEP_DXF_Rotator" src="https://github.com/user-attachments/assets/41db0f3f-86a4-462e-921b-efee0705eeea" />

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
