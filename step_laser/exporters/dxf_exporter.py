"""
DXF file exporter using ezdxf.
Outputs 2D profile edges in inch coordinates.
"""
from pathlib import Path

import ezdxf

from ..projection import Arc2D, Circle2D, Line2D, Polyline2D
from ..optimizer import OptimizedProfile


def export_dxf(profile: OptimizedProfile, output_path: Path) -> None:
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 1  # 1 = inches
    doc.header["$LUNITS"] = 2    # decimal
    msp = doc.modelspace()

    for edge in profile.edges:
        if isinstance(edge, Line2D):
            msp.add_line(
                (edge.x1, edge.y1),
                (edge.x2, edge.y2),
            )
        elif isinstance(edge, Circle2D):
            msp.add_circle(
                (edge.cx, edge.cy),
                edge.r,
            )
        elif isinstance(edge, Arc2D):
            # DXF arcs always go CCW from start_angle to end_angle.
            end_angle = edge.start_deg + edge.sweep_deg
            if edge.sweep_deg > 0:
                # CCW: use directly
                msp.add_arc(
                    center=(edge.cx, edge.cy),
                    radius=edge.r,
                    start_angle=edge.start_deg,
                    end_angle=end_angle,
                )
            else:
                # CW: swap start/end so DXF draws it CCW the other way
                msp.add_arc(
                    center=(edge.cx, edge.cy),
                    radius=edge.r,
                    start_angle=end_angle,
                    end_angle=edge.start_deg,
                )
        elif isinstance(edge, Polyline2D):
            if len(edge.points) >= 2:
                msp.add_lwpolyline(edge.points)

    # Set extents
    doc.header["$EXTMIN"] = (0, 0, 0)
    doc.header["$EXTMAX"] = (profile.bbox_w, profile.bbox_h, 0)

    doc.saveas(str(output_path))
