"""
SVG file exporter — reads a DXF file and writes clean SVG.

Directly converts DXF entities (LINE, CIRCLE, ARC, LWPOLYLINE) to SVG
elements, preserving true arcs and circles.  Output uses inch units.
"""
import math
from pathlib import Path

import ezdxf
from ezdxf import bbox as ezdxf_bbox


def export_svg(dxf_path: Path, output_path: Path) -> None:
    """Read a DXF file and write an SVG with inch units."""
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()

    # Compute extents from actual entity geometry
    extents = ezdxf_bbox.extents(msp)
    ox = extents.extmin[0]
    oy = extents.extmin[1]
    width = extents.extmax[0] - ox
    height = extents.extmax[1] - oy

    parts: list[str] = []

    for entity in msp:
        dxftype = entity.dxftype()

        if dxftype == "LINE":
            x1 = entity.dxf.start[0] - ox
            y1 = height - (entity.dxf.start[1] - oy)
            x2 = entity.dxf.end[0] - ox
            y2 = height - (entity.dxf.end[1] - oy)
            parts.append(
                f'<line x1="{x1:.6f}" y1="{y1:.6f}" '
                f'x2="{x2:.6f}" y2="{y2:.6f}"/>'
            )

        elif dxftype == "CIRCLE":
            cx = entity.dxf.center[0] - ox
            cy = height - (entity.dxf.center[1] - oy)
            r = entity.dxf.radius
            parts.append(
                f'<circle cx="{cx:.6f}" cy="{cy:.6f}" r="{r:.6f}"/>'
            )

        elif dxftype == "ARC":
            cx = entity.dxf.center[0] - ox
            cy_dxf = entity.dxf.center[1] - oy
            r = entity.dxf.radius
            sa = math.radians(entity.dxf.start_angle)
            ea = math.radians(entity.dxf.end_angle)

            # Start / end points in offset-adjusted DXF coords
            sx = cx + r * math.cos(sa)
            sy_dxf = cy_dxf + r * math.sin(sa)
            ex = cx + r * math.cos(ea)
            ey_dxf = cy_dxf + r * math.sin(ea)

            # Flip Y for SVG (Y-down)
            sy = height - sy_dxf
            ey = height - ey_dxf

            # DXF arcs are always CCW; compute angular span
            span = (entity.dxf.end_angle - entity.dxf.start_angle) % 360.0
            if span == 0:
                span = 360.0
            large_arc = 1 if span > 180.0 else 0
            # Y-flip preserves CCW winding in SVG screen coords
            sweep_flag = 0

            parts.append(
                f'<path d="M {sx:.6f},{sy:.6f} '
                f'A {r:.6f},{r:.6f} 0 {large_arc},{sweep_flag} '
                f'{ex:.6f},{ey:.6f}"/>'
            )

        elif dxftype == "LWPOLYLINE":
            pts = list(entity.get_points(format="xy"))
            if len(pts) >= 2:
                px, py = pts[0]
                d = f"M {px - ox:.6f},{height - (py - oy):.6f}"
                for px, py in pts[1:]:
                    d += f" L {px - ox:.6f},{height - (py - oy):.6f}"
                if entity.closed:
                    d += " Z"
                parts.append(f'<path d="{d}"/>')

    elements = "\n".join(parts)
    svg_content = (
        f'<?xml version="1.0" encoding="utf-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg"'
        f' width="{width:.6f}in" height="{height:.6f}in"'
        f' viewBox="0 0 {width:.6f} {height:.6f}">\n'
        f'<g fill="none" stroke="black" stroke-width="0.01">\n'
        f'{elements}\n'
        f'</g>\n'
        f'</svg>\n'
    )

    with open(str(output_path), "wt", encoding="utf-8") as f:
        f.write(svg_content)
