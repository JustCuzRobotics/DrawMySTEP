"""
dxf-min-bound: Rotate DXF files to minimize axis-aligned bounding box area.

Usage:
    python -m dxf_min_bound.main <folder_path>

Scans <folder_path> for .dxf files, rotates each for minimum bounding box,
and writes results to an output_MM-DD-YYYY subfolder.
"""
import math
import sys
import traceback
from pathlib import Path
from typing import List, Tuple

import click
import ezdxf
from ezdxf import bbox as ezdxf_bbox
import numpy as np
from shapely.geometry import MultiPoint


def _sample_entity_points(entity, n: int = 64) -> List[Tuple[float, float]]:
    """Extract representative 2D points from a DXF entity."""
    dxftype = entity.dxftype()
    pts: List[Tuple[float, float]] = []

    if dxftype == "LINE":
        pts.append((entity.dxf.start[0], entity.dxf.start[1]))
        pts.append((entity.dxf.end[0], entity.dxf.end[1]))

    elif dxftype == "CIRCLE":
        cx, cy, r = entity.dxf.center[0], entity.dxf.center[1], entity.dxf.radius
        for i in range(n):
            a = 2 * math.pi * i / n
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))

    elif dxftype == "ARC":
        cx, cy, r = entity.dxf.center[0], entity.dxf.center[1], entity.dxf.radius
        sa = entity.dxf.start_angle
        ea = entity.dxf.end_angle
        span = (ea - sa) % 360.0
        if span == 0:
            span = 360.0
        steps = max(8, int(span / 360 * n))
        for i in range(steps + 1):
            a = math.radians(sa + span * i / steps)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))

    elif dxftype == "LWPOLYLINE":
        pts.extend((x, y) for x, y in entity.get_points(format="xy"))

    return pts


def _find_optimal_angle(all_pts: List[Tuple[float, float]]) -> float:
    """Return the MRR edge angle (degrees) that minimizes bounding box area."""
    if len(all_pts) < 3:
        return 0.0
    hull = MultiPoint(all_pts).convex_hull
    mrr = hull.minimum_rotated_rectangle
    coords = list(mrr.exterior.coords)
    edge_vec = np.array(coords[1]) - np.array(coords[0])
    return math.degrees(math.atan2(edge_vec[1], edge_vec[0]))


def _rotate_pt(x: float, y: float, cos_a: float, sin_a: float) -> Tuple[float, float]:
    return (x * cos_a - y * sin_a, x * sin_a + y * cos_a)


def _apply_rotation(msp, angle_deg: float) -> Tuple[float, float]:
    """
    Rotate all entities in msp by angle_deg (in-place), translate so the
    minimum corner is at (0, 0), and return (bbox_w, bbox_h).
    """
    rad = math.radians(angle_deg)
    cos_a, sin_a = math.cos(rad), math.sin(rad)

    for entity in msp:
        dxftype = entity.dxftype()

        if dxftype == "LINE":
            sx, sy = _rotate_pt(entity.dxf.start[0], entity.dxf.start[1], cos_a, sin_a)
            ex, ey = _rotate_pt(entity.dxf.end[0], entity.dxf.end[1], cos_a, sin_a)
            entity.dxf.start = (sx, sy, 0)
            entity.dxf.end = (ex, ey, 0)

        elif dxftype in ("CIRCLE", "ARC"):
            cx, cy = _rotate_pt(entity.dxf.center[0], entity.dxf.center[1], cos_a, sin_a)
            entity.dxf.center = (cx, cy, 0)
            if dxftype == "ARC":
                # Rotate both angles by the same amount
                entity.dxf.start_angle = (entity.dxf.start_angle + angle_deg) % 360
                entity.dxf.end_angle = (entity.dxf.end_angle + angle_deg) % 360

        elif dxftype == "LWPOLYLINE":
            new_pts = []
            for pt in entity.get_points(format="xyb"):
                rx, ry = _rotate_pt(pt[0], pt[1], cos_a, sin_a)
                new_pts.append((rx, ry, pt[2]))  # bulge is rotation-invariant
            entity.set_points(new_pts, format="xyb")

    # Translate so min corner sits at (0, 0)
    extents = ezdxf_bbox.extents(msp)
    ox, oy = extents.extmin[0], extents.extmin[1]

    for entity in msp:
        dxftype = entity.dxftype()
        if dxftype == "LINE":
            entity.dxf.start = (entity.dxf.start[0] - ox, entity.dxf.start[1] - oy, 0)
            entity.dxf.end = (entity.dxf.end[0] - ox, entity.dxf.end[1] - oy, 0)
        elif dxftype in ("CIRCLE", "ARC"):
            entity.dxf.center = (entity.dxf.center[0] - ox, entity.dxf.center[1] - oy, 0)
        elif dxftype == "LWPOLYLINE":
            new_pts = [(pt[0] - ox, pt[1] - oy, pt[2])
                       for pt in entity.get_points(format="xyb")]
            entity.set_points(new_pts, format="xyb")

    extents = ezdxf_bbox.extents(msp)
    return extents.extmax[0], extents.extmax[1]


def process_dxf(dxf_path: Path) -> None:
    """Rotate one DXF file to its minimum bounding box and write alongside it."""
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()

    all_pts: List[Tuple[float, float]] = []
    for entity in msp:
        all_pts.extend(_sample_entity_points(entity))

    if not all_pts:
        raise ValueError("No geometry found in DXF")

    mrr_angle = _find_optimal_angle(all_pts)
    angle_deg = -mrr_angle  # negate to align MRR edge with X-axis
    print(f"  Rotation: {angle_deg:.1f}\u00b0")

    bbox_w, bbox_h = _apply_rotation(msp, angle_deg)
    print(f"  Bounding box: {bbox_w:.3f} \u00d7 {bbox_h:.3f}")

    stem = dxf_path.stem.replace(" ", "_") + "_rotated"
    out_path = dxf_path.parent / f"{stem}.dxf"
    doc.saveas(str(out_path))
    print(f"  Saved: {out_path.name}")


@click.command()
@click.argument("folder", type=click.Path(exists=True, file_okay=False))
def main(folder: str) -> None:
    """Rotate DXF files in FOLDER to minimize bounding box area."""
    folder_path = Path(folder).resolve()

    # Skip files that are already rotated outputs
    dxf_files = sorted(
        (p for p in folder_path.glob("*.dxf") if not p.stem.endswith("_rotated")),
        key=lambda p: p.name.lower(),
    )
    if not dxf_files:
        click.echo(f"No .dxf files found in {folder_path}")
        sys.exit(1)

    click.echo(f"Found {len(dxf_files)} DXF file(s) in: {folder_path.name}\n")

    success = 0
    errors = []

    for i, dxf_path in enumerate(dxf_files, 1):
        click.echo(f"[{i}/{len(dxf_files)}] {dxf_path.name}")
        try:
            process_dxf(dxf_path)
            success += 1
            click.echo()
        except Exception as e:
            errors.append((dxf_path.name, str(e)))
            click.echo(f"  ERROR: {e}")
            traceback.print_exc()
            click.echo()

    click.echo("=" * 50)
    click.echo(f"Processed: {success}/{len(dxf_files)} files successfully")
    if errors:
        click.echo(f"Errors ({len(errors)}):")
        for name, err in errors:
            click.echo(f"  - {name}: {err}")
    click.echo(f"Output: {folder_path}")


if __name__ == "__main__":
    main()
