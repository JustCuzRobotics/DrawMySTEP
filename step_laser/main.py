"""
step-laser: Batch convert STEP files to DXF, SVG, and PDF for laser cutting.

Usage:
    python -m step_laser.main <folder_path>

Scans <folder_path> for .step files and generates DXF, SVG, and PDF for each
part in the same folder, with filenames like <stem>_converted.dxf.
"""
import sys
import traceback
from pathlib import Path

import click

from .step_reader import load_step
from .projection import extract_profile
from .optimizer import optimize_rotation
from .exporters.dxf_exporter import export_dxf
from .exporters.svg_exporter import export_svg
from .exporters.pdf_exporter import export_pdf


def process_step_file(step_path: Path) -> None:
    """Process a single STEP file: extract profile, optimize, export."""
    stem = step_path.stem.replace(" ", "_")
    part_name = step_path.stem  # human-readable, with spaces

    print(f"  Loading STEP file...")
    shape, unit_to_inches = load_step(step_path)

    print(f"  Extracting 2D profile...")
    profile = extract_profile(shape, unit_to_inches)
    print(f"    Extrusion axis: {profile.extrusion_axis}")
    print(f"    Thickness: {profile.thickness_inches:.3f}\"")
    print(f"    Edges extracted: {len(profile.edges)}")

    print(f"  Optimizing rotation...")
    optimized = optimize_rotation(profile)
    print(f"    Rotation: {optimized.rotation_deg:.1f}\u00b0")
    print(f"    Bounding box: {optimized.bbox_w:.3f}\" \u00d7 {optimized.bbox_h:.3f}\"")

    out = step_path.parent

    dxf_out = out / f"{stem}.dxf"
    export_dxf(optimized, dxf_out)
    print(f"  Exported: {dxf_out.name}")

    svg_out = out / f"{stem}.svg"
    export_svg(dxf_out, svg_out)
    print(f"  Exported: {svg_out.name}")

    pdf_out = out / f"{stem}.pdf"
    export_pdf(optimized, pdf_out, part_name)
    print(f"  Exported: {pdf_out.name}")


@click.command()
@click.argument("folder", type=click.Path(exists=True, file_okay=False))
def main(folder: str) -> None:
    """Batch convert STEP files in FOLDER to DXF/SVG/PDF for laser cutting."""
    folder_path = Path(folder).resolve()

    step_files = sorted(folder_path.glob("*.step"), key=lambda p: p.name.lower())
    if not step_files:
        click.echo(f"No .step files found in {folder_path}")
        sys.exit(1)

    click.echo(f"Found {len(step_files)} STEP file(s) in: {folder_path.name}\n")

    success = 0
    errors = []

    for i, step_path in enumerate(step_files, 1):
        click.echo(f"[{i}/{len(step_files)}] Processing: {step_path.name}")
        try:
            process_step_file(step_path)
            success += 1
            click.echo(f"  Done.\n")
        except Exception as e:
            errors.append((step_path.name, str(e)))
            click.echo(f"  ERROR: {e}")
            traceback.print_exc()
            click.echo()

    click.echo("=" * 50)
    click.echo(f"Processed: {success}/{len(step_files)} files successfully")
    if errors:
        click.echo(f"Errors ({len(errors)}):")
        for name, err in errors:
            click.echo(f"  - {name}: {err}")
    click.echo(f"Output: {folder_path}")


if __name__ == "__main__":
    main()
