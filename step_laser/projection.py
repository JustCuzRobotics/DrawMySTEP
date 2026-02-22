"""
3D -> 2D projection: axis detection, face extraction, edge extraction.

Every part is an extrusion of a 2D profile along one of the three main axes.
This module detects which axis is the extrusion direction (the thinnest bbox
dimension), extracts the flat face with the full profile, and converts its
edges into a list of 2D geometry primitives scaled to inches.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np

from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Line
from OCP.gp import gp_Vec

import cadquery as cq

# -- Primitive types returned by extract_profile --------------------------

@dataclass
class Line2D:
    x1: float; y1: float; x2: float; y2: float

@dataclass
class Circle2D:
    cx: float; cy: float; r: float

@dataclass
class Arc2D:
    cx: float; cy: float; r: float
    start_deg: float   # angle of start point from center (degrees)
    sweep_deg: float   # angular extent: positive=CCW, negative=CW
    x1: float; y1: float  # start point
    x2: float; y2: float  # end point

@dataclass
class Polyline2D:
    points: List[Tuple[float, float]]

@dataclass
class ProfileResult:
    """Complete 2D profile extracted from a STEP solid."""
    edges: List          # list of Line2D | Circle2D | Arc2D | Polyline2D
    wires: List[List]    # grouped as [outer_wire_edges, *inner_wire_edges]
    thickness_inches: float
    extrusion_axis: str  # 'X', 'Y', or 'Z'

# -- Helpers --------------------------------------------------------------

AXIS_VECTORS = {
    "X": gp_Vec(1, 0, 0),
    "Y": gp_Vec(0, 1, 0),
    "Z": gp_Vec(0, 0, 1),
}


def _normalize_angle(a: float) -> float:
    """Normalize angle to [0, 360) degrees."""
    a = a % 360
    if a < 0:
        a += 360
    return a


def _face_area(face) -> float:
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face.wrapped, props)
    return props.Mass()


def _is_rectangle(edges_2d: list) -> bool:
    """Check if a set of 2D edges forms a simple rectangle."""
    lines = [e for e in edges_2d if isinstance(e, Line2D)]
    if len(lines) != len(edges_2d) or len(lines) != 4:
        return False
    for i in range(4):
        a = lines[i]
        b = lines[(i + 1) % 4]
        va = np.array([a.x2 - a.x1, a.y2 - a.y1])
        vb = np.array([b.x2 - b.x1, b.y2 - b.y1])
        dot = np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb) + 1e-12)
        if abs(dot) > 0.05:
            return False
    return True


def _drop_axis(x, y, z, axis: str) -> Tuple[float, float]:
    """Project a 3D point to 2D by dropping the extrusion axis."""
    if axis == "X":
        return (y, z)
    elif axis == "Y":
        return (x, z)
    else:  # Z
        return (x, y)


def _extract_edges_from_wire(wire, axis: str, scale: float) -> list:
    """
    Extract 2D edge primitives from an OCC wire.

    wire  - a cadquery Wire object
    axis  - the extrusion axis to drop ('X', 'Y', or 'Z')
    scale - unit_to_inches conversion factor
    """
    edges_2d = []

    for edge in wire.Edges():
        adaptor = BRepAdaptor_Curve(edge.wrapped)
        curve_type = adaptor.GetType()
        first = adaptor.FirstParameter()
        last = adaptor.LastParameter()

        # Skip degenerate edges (near-zero parametric span — OCC seam markers)
        if abs(last - first) < 1e-3:
            continue

        if curve_type == GeomAbs_Line:
            p1 = adaptor.Value(first)
            p2 = adaptor.Value(last)
            u1, v1 = _drop_axis(p1.X(), p1.Y(), p1.Z(), axis)
            u2, v2 = _drop_axis(p2.X(), p2.Y(), p2.Z(), axis)
            edges_2d.append(Line2D(
                u1 * scale, v1 * scale,
                u2 * scale, v2 * scale,
            ))

        elif curve_type == GeomAbs_Circle:
            circ = adaptor.Circle()
            center = circ.Location()
            radius = circ.Radius()
            cx, cy = _drop_axis(center.X(), center.Y(), center.Z(), axis)
            cx *= scale
            cy *= scale
            r = radius * scale

            p1 = adaptor.Value(first)
            p2 = adaptor.Value(last)
            u1, v1 = _drop_axis(p1.X(), p1.Y(), p1.Z(), axis)
            u2, v2 = _drop_axis(p2.X(), p2.Y(), p2.Z(), axis)
            u1 *= scale; v1 *= scale; u2 *= scale; v2 *= scale

            # Full circle check
            if abs(last - first - 2 * math.pi) < 1e-6:
                edges_2d.append(Circle2D(cx, cy, r))
            else:
                # Compute start/end angles from projected 2D points
                start_rad = math.atan2(v1 - cy, u1 - cx)
                end_rad = math.atan2(v2 - cy, u2 - cx)

                # Use the parametric midpoint to determine sweep direction.
                # The OCC edge goes from first -> last in its parameterization;
                # by sampling the midpoint we know which way the arc actually goes.
                p_mid = adaptor.Value((first + last) / 2)
                um, vm = _drop_axis(p_mid.X(), p_mid.Y(), p_mid.Z(), axis)
                um *= scale; vm *= scale
                mid_rad = math.atan2(vm - cy, um - cx)

                start_deg = math.degrees(start_rad)
                end_deg = math.degrees(end_rad)
                mid_deg = math.degrees(mid_rad)

                # Compute CCW sweep from start to end
                ccw_sweep = _normalize_angle(end_deg - start_deg)
                if ccw_sweep == 0:
                    ccw_sweep = 360.0

                # Check if midpoint lies within the CCW sweep
                mid_from_start = _normalize_angle(mid_deg - start_deg)

                if mid_from_start <= ccw_sweep + 0.5:
                    # CCW direction is correct
                    sweep_deg = ccw_sweep
                else:
                    # CW direction: negative sweep
                    sweep_deg = ccw_sweep - 360.0

                edges_2d.append(Arc2D(
                    cx, cy, r,
                    start_deg, sweep_deg,
                    u1, v1, u2, v2,
                ))

        else:
            # Spline, ellipse, or other curve -> tessellate
            n_points = max(20, int((last - first) * 50))
            pts = []
            for i in range(n_points + 1):
                t = first + (last - first) * i / n_points
                p = adaptor.Value(t)
                u, v = _drop_axis(p.X(), p.Y(), p.Z(), axis)
                pts.append((u * scale, v * scale))
            edges_2d.append(Polyline2D(pts))

    return edges_2d


# -- Main entry point -----------------------------------------------------

def extract_profile(shape: cq.Workplane, unit_to_inches: float) -> ProfileResult:
    """
    Given a CadQuery Workplane containing a single extruded solid, detect the
    extrusion axis, extract the 2D profile from the largest flat face, and
    return all edges as 2D primitives in inches.
    """
    bb = shape.val().BoundingBox()
    extents = {
        "X": bb.xmax - bb.xmin,
        "Y": bb.ymax - bb.ymin,
        "Z": bb.zmax - bb.zmin,
    }

    # Sort axes by extent size (smallest = extrusion/thickness direction)
    axes_sorted = sorted(extents.keys(), key=lambda a: extents[a])

    for axis in axes_sorted:
        thickness = extents[axis]
        thickness_inches = thickness * unit_to_inches
        axis_vec = AXIS_VECTORS[axis]

        # Find planar faces whose normal is ~parallel to this axis
        candidate_faces = []
        for face in shape.faces().vals():
            if face.geomType() != "PLANE":
                continue
            try:
                normal = gp_Vec(*face.normalAt(face.Center()))
            except Exception:
                continue
            if abs(normal.Dot(axis_vec)) > 0.999:
                candidate_faces.append(face)

        if not candidate_faces:
            continue

        best_face = max(candidate_faces, key=_face_area)

        # Extract edges from outer wire and inner wires (holes)
        outer_wire = best_face.outerWire()
        outer_edges = _extract_edges_from_wire(outer_wire, axis, unit_to_inches)

        inner_wires_edges = []
        for iw in best_face.innerWires():
            inner_wires_edges.append(
                _extract_edges_from_wire(iw, axis, unit_to_inches)
            )

        all_edges = outer_edges[:]
        for iw_edges in inner_wires_edges:
            all_edges.extend(iw_edges)

        # Rectangle check: if it looks like a plain rectangle, wrong axis
        if _is_rectangle(all_edges):
            continue

        return ProfileResult(
            edges=all_edges,
            wires=[outer_edges] + inner_wires_edges,
            thickness_inches=thickness_inches,
            extrusion_axis=axis,
        )

    # Fallback: use the smallest axis anyway
    axis = axes_sorted[0]
    thickness_inches = extents[axis] * unit_to_inches
    axis_vec = AXIS_VECTORS[axis]

    planar_faces = []
    for face in shape.faces().vals():
        if face.geomType() != "PLANE":
            continue
        try:
            normal = gp_Vec(*face.normalAt(face.Center()))
        except Exception:
            continue
        if abs(normal.Dot(axis_vec)) > 0.999:
            planar_faces.append(face)

    best_face = max(planar_faces, key=_face_area) if planar_faces else shape.faces().vals()[0]
    outer_wire = best_face.outerWire()
    outer_edges = _extract_edges_from_wire(outer_wire, axis, unit_to_inches)
    inner_wires_edges = []
    for iw in best_face.innerWires():
        inner_wires_edges.append(
            _extract_edges_from_wire(iw, axis, unit_to_inches)
        )
    all_edges = outer_edges[:]
    for iw_edges in inner_wires_edges:
        all_edges.extend(iw_edges)

    return ProfileResult(
        edges=all_edges,
        wires=[outer_edges] + inner_wires_edges,
        thickness_inches=thickness_inches,
        extrusion_axis=axis,
    )
