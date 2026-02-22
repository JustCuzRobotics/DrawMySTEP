"""
PDF drawing exporter using reportlab.
Produces a letter-size page with the 2D profile, bounding box dimensions,
part name, and thickness.
"""
from __future__ import annotations

import math
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from ..projection import Arc2D, Circle2D, Line2D, Polyline2D
from ..optimizer import OptimizedProfile

# Page layout constants (all in points; 1 inch = 72 points)
PAGE_W, PAGE_H = letter  # 612 × 792 points (8.5" × 11")
MARGIN = 0.75 * inch
TITLE_BLOCK_H = 1.25 * inch
DRAW_AREA_X = MARGIN
DRAW_AREA_Y = MARGIN + TITLE_BLOCK_H + 0.25 * inch
DRAW_AREA_W = PAGE_W - 2 * MARGIN
DRAW_AREA_H = PAGE_H - DRAW_AREA_Y - MARGIN


def _draw_profile(c: canvas.Canvas, profile: OptimizedProfile,
                  ox: float, oy: float, scale: float) -> None:
    """Draw all edge primitives on the PDF canvas."""
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(0.5)

    for edge in profile.edges:
        if isinstance(edge, Line2D):
            c.line(
                ox + edge.x1 * scale, oy + edge.y1 * scale,
                ox + edge.x2 * scale, oy + edge.y2 * scale,
            )

        elif isinstance(edge, Circle2D):
            cx = ox + edge.cx * scale
            cy = oy + edge.cy * scale
            r = edge.r * scale
            c.circle(cx, cy, r, stroke=1, fill=0)

        elif isinstance(edge, Arc2D):
            cx = ox + edge.cx * scale
            cy = oy + edge.cy * scale
            r = edge.r * scale
            # reportlab arc uses bounding box of the full circle
            x1 = cx - r
            y1 = cy - r
            x2 = cx + r
            y2 = cy + r
            c.arc(x1, y1, x2, y2, startAng=edge.start_deg, extent=edge.sweep_deg)

        elif isinstance(edge, Polyline2D):
            if len(edge.points) >= 2:
                path = c.beginPath()
                px, py = edge.points[0]
                path.moveTo(ox + px * scale, oy + py * scale)
                for px, py in edge.points[1:]:
                    path.lineTo(ox + px * scale, oy + py * scale)
                c.drawPath(path, stroke=1, fill=0)


def _draw_dimensions(c: canvas.Canvas, profile: OptimizedProfile,
                     ox: float, oy: float, scale: float) -> None:
    """Draw bounding box dimension lines with arrows."""
    w_pts = profile.bbox_w * scale
    h_pts = profile.bbox_h * scale
    arrow_gap = 12  # offset from shape
    arrow_size = 4

    c.setStrokeColorRGB(0.3, 0.3, 0.3)
    c.setFillColorRGB(0.3, 0.3, 0.3)
    c.setLineWidth(0.4)
    c.setFont("Helvetica", 8)

    # --- Width dimension (bottom) ---
    dy = oy - arrow_gap
    # Line
    c.line(ox, dy, ox + w_pts, dy)
    # Left arrow
    c.line(ox, dy, ox + arrow_size, dy + arrow_size / 2)
    c.line(ox, dy, ox + arrow_size, dy - arrow_size / 2)
    # Right arrow
    c.line(ox + w_pts, dy, ox + w_pts - arrow_size, dy + arrow_size / 2)
    c.line(ox + w_pts, dy, ox + w_pts - arrow_size, dy - arrow_size / 2)
    # Extension lines
    c.setDash(1, 2)
    c.line(ox, oy, ox, dy - 4)
    c.line(ox + w_pts, oy, ox + w_pts, dy - 4)
    c.setDash()
    # Label
    label_w = f'{profile.bbox_w:.3f}"'
    c.drawCentredString(ox + w_pts / 2, dy - 12, label_w)

    # --- Height dimension (right) ---
    dx = ox + w_pts + arrow_gap
    # Line
    c.line(dx, oy, dx, oy + h_pts)
    # Bottom arrow
    c.line(dx, oy, dx - arrow_size / 2, oy + arrow_size)
    c.line(dx, oy, dx + arrow_size / 2, oy + arrow_size)
    # Top arrow
    c.line(dx, oy + h_pts, dx - arrow_size / 2, oy + h_pts - arrow_size)
    c.line(dx, oy + h_pts, dx + arrow_size / 2, oy + h_pts - arrow_size)
    # Extension lines
    c.setDash(1, 2)
    c.line(ox + w_pts, oy, dx + 4, oy)
    c.line(ox + w_pts, oy + h_pts, dx + 4, oy + h_pts)
    c.setDash()
    # Label (rotated)
    label_h = f'{profile.bbox_h:.3f}"'
    c.saveState()
    c.translate(dx + 12, oy + h_pts / 2)
    c.rotate(90)
    c.drawCentredString(0, 0, label_h)
    c.restoreState()


def _draw_title_block(c: canvas.Canvas, part_name: str,
                      profile: OptimizedProfile) -> None:
    """Draw the title block at the bottom of the page."""
    block_x = MARGIN
    block_y = MARGIN
    block_w = PAGE_W - 2 * MARGIN
    block_h = TITLE_BLOCK_H

    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(1)
    c.rect(block_x, block_y, block_w, block_h)

    # Inner divider
    mid_y = block_y + block_h / 2
    c.setLineWidth(0.5)
    c.line(block_x, mid_y, block_x + block_w, mid_y)

    c.setFillColorRGB(0, 0, 0)

    # Top row: Part name
    c.setFont("Helvetica-Bold", 14)
    c.drawString(block_x + 10, mid_y + 14, part_name)

    # Bottom row: Thickness and bounding box
    c.setFont("Helvetica", 11)
    thickness_str = f'Thickness: {profile.thickness_inches:.3f}"'
    bbox_str = f'Bounding Box: {profile.bbox_w:.3f}" \u00d7 {profile.bbox_h:.3f}"'

    c.drawString(block_x + 10, block_y + 16, thickness_str)
    c.drawString(block_x + block_w / 2, block_y + 16, bbox_str)


def export_pdf(profile: OptimizedProfile, output_path: Path,
               part_name: str) -> None:
    """Generate a PDF drawing with the 2D profile and title block."""
    c = canvas.Canvas(str(output_path), pagesize=letter)

    # Compute scale to fit the drawing area (with room for dimension labels)
    usable_w = DRAW_AREA_W - 40  # room for right-side dim label
    usable_h = DRAW_AREA_H - 30  # room for bottom dim label
    scale = min(usable_w / profile.bbox_w, usable_h / profile.bbox_h)

    # Center the drawing in the available area
    shape_w = profile.bbox_w * scale
    shape_h = profile.bbox_h * scale
    ox = DRAW_AREA_X + (DRAW_AREA_W - shape_w) / 2
    oy = DRAW_AREA_Y + (DRAW_AREA_H - shape_h) / 2

    _draw_profile(c, profile, ox, oy, scale)
    _draw_dimensions(c, profile, ox, oy, scale)
    _draw_title_block(c, part_name, profile)

    c.save()
