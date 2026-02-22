"""
STEP file loading.

OpenCASCADE (used by CadQuery) always normalizes STEP coordinates to
millimetres internally, regardless of the units declared in the STEP header.
So we always convert from mm → inches (÷ 25.4).
"""
from pathlib import Path

import cadquery as cq

# OCC always gives us millimetres
MM_TO_INCHES = 1.0 / 25.4


def load_step(filepath: Path):
    """
    Load a STEP file and return (cq_shape, unit_to_inches).

    cq_shape       – a cadquery Workplane wrapping the imported solid
    unit_to_inches – multiplicative factor to convert OCC coords (mm) to inches
    """
    shape = cq.importers.importStep(str(filepath))
    return shape, MM_TO_INCHES
