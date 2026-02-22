"""
Minimum bounding box rotation optimizer.

Finds the rotation angle that minimizes the axis-aligned bounding box area
of the 2D profile, then applies that rotation to all edge primitives and
translates so the minimum corner sits at (0, 0).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
from shapely.geometry import MultiPoint

from .projection import (
    Arc2D,
    Circle2D,
    Line2D,
    Polyline2D,
    ProfileResult,
)


@dataclass
class OptimizedProfile:
    """Profile after optimal rotation, with edges in inches at origin."""
    edges: List
    wires: List[List]
    bbox_w: float   # bounding box width in inches
    bbox_h: float   # bounding box height in inches
    rotation_deg: float
    thickness_inches: float


def _sample_arc_points(arc: Arc2D, n_per_full_circle: int = 64) -> List[Tuple[float, float]]:
    """Sample points along an arc using its sweep_deg."""
    pts = [(arc.x1, arc.y1), (arc.x2, arc.y2)]
    sa = math.radians(arc.start_deg)
    sweep_rad = math.radians(arc.sweep_deg)
    n = max(8, int(abs(arc.sweep_deg) / 360 * n_per_full_circle))
    for i in range(1, n):
        a = sa + sweep_rad * i / n
        pts.append((arc.cx + arc.r * math.cos(a), arc.cy + arc.r * math.sin(a)))
    return pts


def _sample_points(edges: list) -> List[Tuple[float, float]]:
    """Collect representative 2D points from all edges for convex hull."""
    pts = []
    for e in edges:
        if isinstance(e, Line2D):
            pts.append((e.x1, e.y1))
            pts.append((e.x2, e.y2))
        elif isinstance(e, Circle2D):
            for i in range(64):
                a = 2 * math.pi * i / 64
                pts.append((e.cx + e.r * math.cos(a), e.cy + e.r * math.sin(a)))
        elif isinstance(e, Arc2D):
            pts.extend(_sample_arc_points(e))
        elif isinstance(e, Polyline2D):
            pts.extend(e.points)
    return pts


def _find_optimal_angle(pts: List[Tuple[float, float]]) -> float:
    """
    Find the rotation angle (degrees) that minimizes the axis-aligned
    bounding box area using shapely's minimum_rotated_rectangle.
    """
    if len(pts) < 3:
        return 0.0

    mp = MultiPoint(pts)
    hull = mp.convex_hull
    mrr = hull.minimum_rotated_rectangle

    coords = list(mrr.exterior.coords)
    edge_vec = np.array(coords[1]) - np.array(coords[0])
    angle_rad = math.atan2(edge_vec[1], edge_vec[0])
    return math.degrees(angle_rad)


def _rotate_point(x: float, y: float, cos_a: float, sin_a: float) -> Tuple[float, float]:
    return (x * cos_a - y * sin_a, x * sin_a + y * cos_a)


def _rotate_edge(edge, cos_a: float, sin_a: float):
    """Return a new edge primitive rotated by angle."""
    if isinstance(edge, Line2D):
        x1r, y1r = _rotate_point(edge.x1, edge.y1, cos_a, sin_a)
        x2r, y2r = _rotate_point(edge.x2, edge.y2, cos_a, sin_a)
        return Line2D(x1r, y1r, x2r, y2r)
    elif isinstance(edge, Circle2D):
        cxr, cyr = _rotate_point(edge.cx, edge.cy, cos_a, sin_a)
        return Circle2D(cxr, cyr, edge.r)
    elif isinstance(edge, Arc2D):
        cxr, cyr = _rotate_point(edge.cx, edge.cy, cos_a, sin_a)
        x1r, y1r = _rotate_point(edge.x1, edge.y1, cos_a, sin_a)
        x2r, y2r = _rotate_point(edge.x2, edge.y2, cos_a, sin_a)
        angle_offset = math.degrees(math.atan2(sin_a, cos_a))
        return Arc2D(
            cxr, cyr, edge.r,
            edge.start_deg + angle_offset,
            edge.sweep_deg,  # sweep magnitude/direction unchanged by rotation
            x1r, y1r, x2r, y2r,
        )
    elif isinstance(edge, Polyline2D):
        new_pts = [_rotate_point(x, y, cos_a, sin_a) for x, y in edge.points]
        return Polyline2D(new_pts)
    return edge


def _translate_edge(edge, dx: float, dy: float):
    """Return a new edge primitive translated by (dx, dy)."""
    if isinstance(edge, Line2D):
        return Line2D(edge.x1 + dx, edge.y1 + dy, edge.x2 + dx, edge.y2 + dy)
    elif isinstance(edge, Circle2D):
        return Circle2D(edge.cx + dx, edge.cy + dy, edge.r)
    elif isinstance(edge, Arc2D):
        return Arc2D(
            edge.cx + dx, edge.cy + dy, edge.r,
            edge.start_deg, edge.sweep_deg,
            edge.x1 + dx, edge.y1 + dy,
            edge.x2 + dx, edge.y2 + dy,
        )
    elif isinstance(edge, Polyline2D):
        return Polyline2D([(x + dx, y + dy) for x, y in edge.points])
    return edge


def optimize_rotation(profile: ProfileResult) -> OptimizedProfile:
    """
    Find the rotation that minimizes the AABB, apply it to all edges,
    and translate so the min corner is at (0, 0).
    """
    pts = _sample_points(profile.edges)
    angle_deg = _find_optimal_angle(pts)

    # Rotate by the negative of the MRR angle to align axis-aligned
    rad = math.radians(-angle_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)

    rotated_edges = [_rotate_edge(e, cos_a, sin_a) for e in profile.edges]
    rotated_wires = [
        [_rotate_edge(e, cos_a, sin_a) for e in wire]
        for wire in profile.wires
    ]

    # Find bounding box of rotated geometry
    rotated_pts = _sample_points(rotated_edges)
    xs = [p[0] for p in rotated_pts]
    ys = [p[1] for p in rotated_pts]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)

    dx, dy = -xmin, -ymin
    translated_edges = [_translate_edge(e, dx, dy) for e in rotated_edges]
    translated_wires = [
        [_translate_edge(e, dx, dy) for e in wire]
        for wire in rotated_wires
    ]

    return OptimizedProfile(
        edges=translated_edges,
        wires=translated_wires,
        bbox_w=xmax - xmin,
        bbox_h=ymax - ymin,
        rotation_deg=-angle_deg,
        thickness_inches=profile.thickness_inches,
    )
