"""2GIS scraping command handler.

Invokes the embedded vendor/parser2gis CLI to parse 2GIS search result
pages via Chrome DevTools Protocol. Results are written as CSV/XLSX/JSON.
Optionally runs the contact enrichment pipeline (``--pipe``).

The vendor parser is called via direct Python import (sys.argv injection),
not subprocess, to keep everything in a single process.
"""

import argparse
import logging
import sys
from pathlib import Path

log = logging.getLogger(__name__)


def _get_output_dir(args: argparse.Namespace) -> Path:
    """Resolve output directory from args or fall back to default."""
    if args.output_dir:
        return Path(args.output_dir)
    base = Path(__file__).resolve().parents[2]
    return base / "maps_data" / "parsed_2gis"


def run_scrape_2gis(args: argparse.Namespace) -> None:
    """Run 2GIS parser and optionally the enrichment pipeline.

    Steps:
        1. Determine output directory and filename.
        2. Inject CLI args into sys.argv for vendor parser2gis.
        3. Call cli_app() from vendor/parser2gis.
        4. If ``--pipe`` is set, run Parser2GISPipe on the output.

    Args:
        args: Parsed argparse namespace from ``terra-dok scrape-2gis``.

    """
    from src.vendor.parser2gis.cli import cli_app
    from src.vendor.parser2gis.main import parse_arguments

    output_dir = _get_output_dir(args)
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = args.name or "result"
    output_file = output_dir / f"{filename}.{args.format}"

    # Build sys.argv for the vendor parser2gis argparse
    argv = [
        "parser-2gis",
        "-i",
        *args.urls,
        "-o",
        str(output_file),
        "-f",
        args.format,
    ]
    if args.headless:
        argv += ["--chrome.headless", "yes"]
    if args.max_records:
        argv += ["--parser.max-records", str(args.max_records)]

    old_argv = sys.argv
    sys.argv = argv
    try:
        _, config = parse_arguments()
        cli_app(args.urls, str(output_file), args.format, config)
    finally:
        sys.argv = old_argv

    if args.pipe:
        log.info("Running contact enrichment pipeline...")
        from src.pipelines.parser2gis_pipe import Parser2GISPipe

        Parser2GISPipe(data_dir=output_dir).run()

    log.info("2GIS scraping completed.")
